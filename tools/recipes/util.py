"""Gemeinsame Helfer: Laden, Normalisieren, Tokenisieren, Traversieren."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schema" / "recipe.schema.json"

# Sektionen, die generiert werden und nicht verbatim im JSON stehen (Check K/L).
GENERATED_SECTIONS = ("Einkaufsliste", "Mengen-Check")
SHOPPING_SECTION = GENERATED_SECTIONS[0]

# Regex-Bausteine, aus denen Check B (util) und Check K (shopping) ihre Muster bauen.
NUM = r"\d+(?:[,.]\d+)?"
NOT_WORD = r"(?![\wäöüßÄÖÜ])"
UNITS_MASS_VOL = ("kg", "g", "ml", "l", "EL", "TL", "Prise")
UNITS_ALL = UNITS_MASS_VOL + ("Min.", "Min", "Std.", "Std", "Sek.", "Sek", "h", "°C", "%", "cm")


def unit_alt(units: tuple[str, ...]) -> str:
    return "(?:" + "|".join(re.escape(u) for u in sorted(units, key=len, reverse=True)) + ")" + NOT_WORD


# Zahl + Einheit, inkl. Spannen (2–3 EL, 90–120 Min.) und Dezimalkomma (2,5 Std.).
UNIT_TOKEN = re.compile(rf"{NUM}(?:\s?[–-]\s?{NUM})?\s?{unit_alt(UNITS_ALL)}")
TASK_ITEM = re.compile(r"^\s*[-*]\s+\[([ x])\]\s+(.*)$")
_WS = re.compile(r"\s+")
_EMPH = re.compile(r"\*{1,3}")
_H2 = re.compile(r"^## +(.*)$")
_WORD = re.compile(r"[a-zäöüß]{4,}")
# Satzende: Punkt/Ausrufe-/Fragezeichen, Leerraum, dann Großbuchstabe/Ziffer/Anführung.
# Bewusst ohne Abkürzungslogik: Check C fragt nur, ob action an *irgendeiner* Grenze endet.
_SENT_END = re.compile(r"[.!?]\s+(?=[A-ZÄÖÜ0-9„\"*(½¼¾])")


def ws_key(s: str) -> str:
    """Schlüssel für Verbatim-Vergleiche (L2): Tilde-Escape auflösen, Whitespace zusammenziehen."""
    return _WS.sub(" ", s.replace("\\~", "~")).strip()


def quote_key(s: str) -> str:
    """Schlüssel für Zitat-Vergleiche (L3): wie ws_key, zusätzlich ohne Fett-/Kursiv-Marker."""
    return ws_key(_EMPH.sub("", s))


def unit_tokens(s: str) -> Counter:
    return Counter(ws_key(m.group(0)) for m in UNIT_TOKEN.finditer(s))


def words(s: str) -> set[str]:
    return set(_WORD.findall(quote_key(s).lower()))


def is_generated(title: str) -> bool:
    return title.startswith(GENERATED_SECTIONS)


def load_json(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def source_path(recipe: dict) -> Path:
    return ROOT / (recipe["id"] + ".md")


def read_source(recipe: dict) -> str:
    return source_path(recipe).read_text(encoding="utf-8")


def split_h2(md: str) -> list[tuple[str, str]]:
    """[(titel, text)] der ##-Sektionen; der Kopf vor der ersten ## hat den Titel ''."""
    parts: list[tuple[str, str]] = []
    title, buf = "", []
    for line in md.splitlines():
        if m := _H2.match(line):
            parts.append((title, "\n".join(buf)))
            title, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    parts.append((title, "\n".join(buf)))
    return parts


def source_without_generated(md: str) -> str:
    return "\n".join(text for title, text in split_h2(md) if not is_generated(title))


def sections(recipe: dict, type_: str) -> list[dict]:
    return [s for s in recipe.get("sections", []) if s.get("type") == type_]


def section(recipe: dict, type_: str) -> dict | None:
    return next(iter(sections(recipe, type_)), None)


def iter_courses(recipe: dict) -> Iterator[dict]:
    for sec in sections(recipe, "courses"):
        yield from sec["courses"]


def iter_tasks_with_course(recipe: dict, course: str | None = None) -> Iterator[tuple[str | None, dict]]:
    for sec in sections(recipe, "tasks"):
        for task in sec["tasks"]:
            yield course, task
    for c in iter_courses(recipe):
        yield from iter_tasks_with_course(c, c["id"])


def iter_tasks(recipe: dict) -> Iterator[dict]:
    for _, task in iter_tasks_with_course(recipe):
        yield task


def iter_steps(recipe: dict) -> Iterator[tuple[dict, dict]]:
    for task in iter_tasks(recipe):
        for step in task["steps"]:
            yield task, step


def verbatim_strings(recipe: dict) -> list[str]:
    """Felder, die den Quelltext wortgleich tragen (Grundlage für Check B)."""
    out = [recipe.get("title", ""), recipe.get("intro", ""), recipe.get("statusNote", "")]
    for sec in recipe.get("sections", []):
        t = sec.get("type")
        if t == "markdown":
            out.append(sec["markdown"])
        elif t == "tasks":
            out.append(sec.get("intro", ""))
            for task in sec["tasks"]:
                out += [task.get("heading", ""), task.get("intro", "")]
                for step in task["steps"]:
                    out += [step.get("heading", ""), step["text"]]
        elif t == "learnings":
            out += [sec["summary"], sec.get("details", "")]
        elif t == "todo":
            out += [sec.get("intro", "")] + [i["text"] for i in sec["items"]]
        elif t == "courses":
            out.append(sec.get("intro", ""))
            for c in sec["courses"]:
                out += verbatim_strings(c)
        elif t == "schedule":
            out += [sec.get("intro", ""), sec.get("note", "")]
            out += [e["text"] for e in sec["schedule"]["entries"]]
            out += [ph["label"] for ph in sec["schedule"]["phases"]]
    return [s for s in out if s]


def annotation_quotes(recipe: dict) -> list[tuple[str, str]]:
    """(Pfad, Zitat) für alle Felder, die laut L3 Substring der Quelle sein müssen."""
    q: list[tuple[str, str]] = []

    def src(path: str, d: dict | None):
        if d and d.get("source"):
            q.append((path + ".source", d["source"]))

    times = recipe.get("times") or {}
    src("times.active", times.get("active"))
    src("times.total", times.get("total"))
    for sec in sections(recipe, "learnings"):
        q += [(f"learnings.notes[{i}].text", n["text"]) for i, n in enumerate(sec.get("notes", []))]
    for c in iter_courses(recipe):
        q += [(f"{c['id']}/{path}", quote) for path, quote in annotation_quotes(c) if not path.startswith("step:")]
    for i, c in enumerate(recipe.get("constraints", [])):
        if c.get("source"):
            q.append((f"constraints[{i}].source", c["source"]))
    for i, c in enumerate(recipe.get("courses", [])):
        if c.get("source"):
            q.append((f"courses[{i}].source", c["source"]))
    for sec in sections(recipe, "schedule"):
        q += [(f"schedule.entries[{i}].source", e["source"]) for i, e in enumerate(sec["schedule"]["entries"]) if e.get("source") and not e.get("derived")]
    for task in iter_tasks(recipe):
        for prod in task.get("produces", []):
            src(f"product:{prod['id']}.hold", prod.get("hold"))
    for _, step in iter_steps(recipe):
        p = f"step:{step['id']}"
        if step.get("title"):
            q.append((p + ".title", step["title"]))
        if not step.get("actionDerived"):
            q.append((p + ".action", step["action"]))
        src(p + ".duration", step.get("duration"))
        for k in ("cues", "limits"):
            q += [(f"{p}.{k}[{j}]", s) for j, s in enumerate(step.get(k, []))]
        for k in ("why", "rescue"):
            if step.get(k):
                q.append((f"{p}.{k}", step[k]))
        for j, t in enumerate(step.get("timers", [])):
            if t.get("text"):
                q.append((f"{p}.timers[{j}].text", t["text"]))
            src(f"{p}.timers[{j}].duration", t.get("duration"))
        q += [(f"{p}.temps[{j}].text", t["text"]) for j, t in enumerate(step.get("temps", []))]
        for j, ev in enumerate(step.get("events", [])):
            q.append((f"{p}.events[{j}].text", ev["text"]))
            src(f"{p}.events[{j}].at", ev.get("at"))
        if step.get("start"):
            src(p + ".start.offset", step["start"].get("offset"))
        if step.get("endCondition"):
            q.append((p + ".endCondition.text", step["endCondition"]["text"]))
        q += [(f"{p}.ingredients[{j}].amount.text", si["amount"]["text"]) for j, si in enumerate(step.get("ingredients", []))]
    return q


def sentence_prefixes(text: str) -> list[str]:
    """Alle Präfixe aus ganzen Sätzen (Kandidaten für action)."""
    ends = [m.start() + 1 for m in _SENT_END.finditer(text)] + [len(text.rstrip())]
    return [text[:e].strip() for e in ends]
