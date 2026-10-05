"""Gemeinsame Helfer: Laden, Normalisieren, Tokenisieren, Verbatim-Felder sammeln."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schema" / "recipe.schema.json"

# Sektionen, die nicht verbatim im JSON stehen müssen (werden generiert, Check K/L).
GENERATED_SECTIONS = ("Einkaufsliste", "Mengen-Check")

# Zahl + Einheit, inkl. Spannen (2–3 EL, 90–120 Min.) und Dezimalkomma (2,5 Std.).
UNIT_TOKEN = re.compile(
    r"\d+(?:[,.]\d+)?(?:\s?[–-]\s?\d+(?:[,.]\d+)?)?\s?"
    r"(?:kg|g|ml|l|EL|TL|Min\.?|Std\.?|Sek\.?|h|°C|%|cm)(?![\wäöüßÄÖÜ])"
)


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def source_path(recipe: dict) -> Path:
    return ROOT / (recipe["id"] + ".md")


def read_source(recipe: dict) -> str:
    return source_path(recipe).read_text(encoding="utf-8")


def normalize(s: str) -> str:
    """Für Substring-Vergleiche: Tilde-Escape auflösen, Markdown-Betonung
    entfernen, Whitespace (auch Zeilenumbrüche) zusammenziehen."""
    s = s.replace("\\~", "~").replace("*", "")
    return re.sub(r"\s+", " ", s).strip()


def unit_tokens(s: str) -> Counter:
    return Counter(normalize(m.group(0)) for m in UNIT_TOKEN.finditer(s))


def split_h2(md: str) -> list[tuple[str, str]]:
    """Liefert [(titel, text)] für die ##-Sektionen; der Kopf vor der ersten ##
    bekommt den Titel ''."""
    parts: list[tuple[str, str]] = []
    title, buf = "", []
    for line in md.splitlines():
        m = re.match(r"^## +(.*)$", line)
        if m:
            parts.append((title, "\n".join(buf)))
            title, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    parts.append((title, "\n".join(buf)))
    return parts


def source_without_generated(md: str) -> str:
    keep = []
    for title, text in split_h2(md):
        if any(title.startswith(g) for g in GENERATED_SECTIONS):
            continue
        keep.append(text)
    return "\n".join(keep)


def iter_tasks(recipe: dict):
    for sec in recipe.get("sections", []):
        if sec.get("type") == "tasks":
            for task in sec["tasks"]:
                yield task


def iter_steps(recipe: dict):
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
                out.append(task.get("intro", ""))
                for step in task["steps"]:
                    out.append(step.get("heading", ""))
                    out.append(step["text"])
        elif t == "learnings":
            out += [sec["summary"], sec.get("details", "")]
        elif t == "todo":
            out += [i["text"] for i in sec["items"]]
    return [s for s in out if s]


def annotation_quotes(recipe: dict) -> list[tuple[str, str]]:
    """(Pfad, Zitat) für alle Felder, die laut L3 Substring der Quelle sein müssen."""
    q: list[tuple[str, str]] = []

    def dr(path: str, d: dict | None):
        if d and d.get("source"):
            q.append((path + ".source", d["source"]))

    if recipe.get("times"):
        dr("times.active", recipe["times"].get("active"))
        dr("times.total", recipe["times"].get("total"))
    for sec in recipe.get("sections", []):
        if sec.get("type") == "learnings":
            for i, n in enumerate(sec.get("notes", [])):
                q.append((f"learnings.notes[{i}].text", n["text"]))
    for task, step in iter_steps(recipe):
        p = f"step:{step['id']}"
        if step.get("title"):
            q.append((p + ".title", step["title"]))
        if not step.get("actionDerived"):
            q.append((p + ".action", step["action"]))
        dr(p + ".duration", step.get("duration"))
        for k in ("cues", "limits"):
            for j, s in enumerate(step.get(k, [])):
                q.append((f"{p}.{k}[{j}]", s))
        for k in ("why", "rescue"):
            if step.get(k):
                q.append((f"{p}.{k}", step[k]))
        for j, t in enumerate(step.get("timers", [])):
            if t.get("text"):
                q.append((f"{p}.timers[{j}].text", t["text"]))
            dr(f"{p}.timers[{j}].duration", t.get("duration"))
        for j, t in enumerate(step.get("temps", [])):
            q.append((f"{p}.temps[{j}].text", t["text"]))
        if step.get("endCondition"):
            q.append((p + ".endCondition.text", step["endCondition"]["text"]))
        for j, si in enumerate(step.get("ingredients", [])):
            q.append((f"{p}.ingredients[{j}].amount.text", si["amount"]["text"]))
        for prod in task.get("produces", []) if task else []:
            hold = prod.get("hold") or {}
            if hold.get("source"):
                q.append((f"product:{prod['id']}.hold.source", hold["source"]))
    return q


_ABBREV = {"z", "b", "ca", "bzw", "ggf", "evtl", "nr", "st", "inkl", "max", "vgl", "u", "a", "s", "o"}
_TIME_ABBREV = {"min", "std", "sek"}  # Satzende, wenn danach ein Großbuchstabe folgt („… 20 Min. Danach …“)
_SENT_END = re.compile(r"[.!?]\s+(?=[A-ZÄÖÜ0-9„\"*(½¼¾])")


def sentence_ends(text: str) -> list[int]:
    """Indizes (exklusiv) aller Satzenden; Abkürzungen wie „Min.“, „z. B.“ zählen
    nicht als Satzende. Der Textschluss ist immer ein Satzende."""
    ends = []
    for m in _SENT_END.finditer(text):
        before = text[:m.start()]
        word = re.findall(r"[\wäöüÄÖÜß]+$", before.rstrip("*)"))
        if word and word[-1].lower() in _ABBREV:
            continue
        if word and word[-1].lower() in _TIME_ABBREV and not text[m.end()].isupper():
            continue
        ends.append(m.start() + 1)
    ends.append(len(text.rstrip()))
    return ends


def first_sentence(text: str) -> str:
    return text[: sentence_ends(text)[0]]


def sentence_prefixes(text: str) -> list[str]:
    """Alle Präfixe aus ganzen Sätzen (Kandidaten für action)."""
    return [text[:e].strip() for e in sentence_ends(text)]
