"""Varianten (AP6): Dimensionen mit Wahlmöglichkeiten, `only`-Filter, Inline-Alternativen.

Schreibweise (REZEPTFORMAT §11):
  Kopf:     *Varianten: Mehl = Weizen | Weizen-Roggen | Dinkel · Weg = Einfrieren | Direkt backen | Kombi*
  Schritt:  Meta-Klausel `nur Dinkel` / `nur Einfrieren, Kombi` (mehrere Klauseln = und)
  Text:     `80 g Wasser (Weizen-Roggen: 90 g, Dinkel: 40 g)` — Klammer direkt hinter einer Menge
  Posten:   `- [ ] 1 kg Dinkelvollkornmehl — nur Dinkel`

Eine Wahl ist ein Ref `dimension=wahl` („mehl=dinkel“). `only` ist eine Liste solcher Refs:
innerhalb einer Dimension oder, über Dimensionen und. Die erste Wahl jeder Dimension ist der Default.
"""
from __future__ import annotations

import copy
import itertools
import re

from .util import slugify

DECL_RE = re.compile(r"^\*Varianten:\s*(?P<body>.+?)\*\s*$", re.M)


def parse_declaration(head: str) -> list[dict]:
    m = DECL_RE.search(head)
    if not m:
        return []
    dims = []
    for part in re.split(r"\s·\s", m["body"].strip().rstrip(".")):
        name, _, choices = part.partition("=")
        labels = [c.strip() for c in choices.split("|") if c.strip()]
        if not name.strip() or not labels:
            continue
        dims.append({"id": slugify(name.strip()), "label": name.strip(),
                     "choices": [{"id": slugify(c), "label": c} for c in labels], "default": slugify(labels[0])})
    return dims


def choice_index(dims: list[dict]) -> dict[str, str]:
    """Label oder Slug einer Wahl (klein) → Ref „dim=wahl“. Wahl-Namen sind rezeptweit eindeutig."""
    return {k: f"{d['id']}={c['id']}" for d in dims for c in d["choices"] for k in (c["label"].lower(), c["id"])}


def parse_only(text: str, dims: list[dict]) -> tuple[list[str] | None, list[str]]:
    """„Einfrieren, Kombi“ → (["weg=einfrieren", "weg=kombi"], unbekannte Namen)."""
    idx = choice_index(dims)
    refs, unknown = [], []
    for name in (x.strip() for x in re.split(r",\s*|\s+und\s+", text) if x.strip()):
        (refs if name.lower() in idx else unknown).append(idx.get(name.lower(), name))
    return (refs or None), unknown


def _label_alt(dims: list[dict]) -> str:
    """Alle Wahl-Namen als Regex-Alternative, längste zuerst („Weizen-Roggen“ vor „Weizen“)."""
    return "|".join(re.escape(x) for x in sorted({c["label"] for d in dims for c in d["choices"]}, key=len, reverse=True))


def alt_pattern(dims: list[dict]) -> re.Pattern | None:
    """Klammer, deren Teile alle mit „<Wahl>:“ beginnen: „(Weizen-Roggen: 90 g, Dinkel: 40 g)“."""
    if not dims:
        return None
    lab = _label_alt(dims)
    return re.compile(rf"\((?P<body>(?:{lab}):\s[^()]*(?:\([^()]*\)[^()]*)*)\)")


def split_alt(body: str, dims: list[dict]) -> list[tuple[str, str]]:
    """„Weizen-Roggen: 90 g, Dinkel: 40 g“ → [(„weizen-roggen“-Ref, „90 g“), …]."""
    idx = choice_index(dims)
    parts = re.split(rf",\s(?=(?:{_label_alt(dims)}):\s)", body)
    out = []
    for p in parts:
        name, _, text = p.partition(":")
        if name.strip().lower() in idx:
            out.append((idx[name.strip().lower()], text.strip()))
    return out


# ---------------------------------------------------------------- Auswahl

def default_selection(dims: list[dict]) -> dict[str, str]:
    return {d["id"]: d["default"] for d in dims}


def selections(dims: list[dict]) -> list[dict[str, str]]:
    """Alle Kombinationen, Default zuerst."""
    combos = [dict(zip([d["id"] for d in dims], cs)) for cs in itertools.product(*[[c["id"] for c in d["choices"]] for d in dims])]
    default = default_selection(dims)
    return [default] + [c for c in combos if c != default]


def selection_key(sel: dict[str, str]) -> str:
    return ",".join(f"{k}={sel[k]}" for k in sorted(sel))


def active(only: list[str] | None, sel: dict[str, str]) -> bool:
    if not only:
        return True
    by_dim: dict[str, set[str]] = {}
    for ref in only:
        dim, _, choice = ref.partition("=")
        by_dim.setdefault(dim, set()).add(choice)
    return all(sel.get(dim) in choices for dim, choices in by_dim.items())


def view(recipe: dict, sel: dict[str, str]) -> dict:
    """Rezept, wie es bei dieser Wahl gekocht wird: inaktive Tasks/Schritte/Zutaten/Zeitplan-Einträge fallen weg,
    Dosierungen mit `byVariant` werden durch die Alternative ersetzt. Grundlage für derive() pro Kombination."""
    r = copy.deepcopy({k: v for k, v in recipe.items() if k != "derived"})  # der alte derived-Block wird nicht gebraucht
    keys = {f"{k}={v}" for k, v in sel.items()}
    live = {i["id"] for i in r["ingredients"] if active(i.get("only"), sel)}  # „ggf. 4–6 g Brotgewürz“ fällt mit der Zutat weg

    def fix_tasks(container: dict):
        for sec in container.get("sections", []):
            if sec.get("type") == "tasks":
                sec["tasks"] = [t for t in sec["tasks"] if active(t.get("only"), sel)]
                for t in sec["tasks"]:
                    t["steps"] = [s for s in t["steps"] if active(s.get("only"), sel)]
                    for s in t["steps"]:
                        out = []
                        for si in s.get("ingredients", []):
                            alt = next((si["byVariant"][k] for k in si.get("byVariant", {}) if k in keys), None)
                            out += alt if alt is not None else [si]
                        s["ingredients"] = [si for si in out if si["ref"] in live]
            elif sec.get("type") == "courses":
                for c in sec["courses"]:
                    fix_tasks(c)
            elif sec.get("type") == "schedule":
                sch = sec["schedule"]
                sch["entries"] = [e for e in sch["entries"] if active(e.get("only"), sel)]

    fix_tasks(r)
    r["sections"] = [s for s in r["sections"] if s.get("type") != "schedule" or active(s["schedule"].get("only"), sel)]
    r["ingredients"] = [i for i in r["ingredients"] if active(i.get("only"), sel)]
    return r
