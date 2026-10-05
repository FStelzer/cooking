"""Checks B (Vollständigkeit), C (Zitat-Treue, Spans), D (IDs und Referenzen)."""
from __future__ import annotations

import re
from collections import Counter

from .util import (UNIT_TOKEN, annotation_quotes, is_generated, iter_steps, iter_tasks, quote_key,
                   sections, sentence_prefixes, source_without_generated, split_h2, unit_tokens,
                   verbatim_strings, ws_key)

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_LIST_PREFIX = re.compile(r"^\s*(?:[-*]\s+\[[ x]\]\s+|[-*]\s+|\d+\.\s+|#+\s+|>\s*)")


def check_b(recipe: dict, source: str) -> tuple[list[str], list[str]]:
    """B1 Sektionen vollständig, B2 Zahl+Einheit-Token identisch, B3 jede Quellzeile verbatim enthalten."""
    errs, reps = [], []
    have_titles = [sec.get("title", "") for sec in recipe.get("sections", [])]
    for t in (t for t, _ in split_h2(source) if t):
        if is_generated(t):
            if not any(is_generated(h) for h in have_titles):
                reps.append(f"B Sektion '{t}' wird generiert, kein Platzhalter im JSON")
        elif t not in have_titles:
            errs.append(f"B Sektion '## {t}' fehlt im JSON")
    src = source_without_generated(source)
    verb = verbatim_strings(recipe)
    want, have = unit_tokens(src), sum(map(unit_tokens, verb), Counter())
    errs += [f"B Token fehlt im JSON (verbatim-Felder): '{tok}' ×{n}" for tok, n in sorted((want - have).items())]
    errs += [f"B Token im JSON, aber nicht in der Quelle: '{tok}' ×{n}" for tok, n in sorted((have - want).items())]
    reps.append(f"B {want.total()} Zahl+Einheit-Token in der Quelle, {have.total()} in verbatim-Feldern")
    blob = ws_key(" ".join(verb))
    for line in src.splitlines():
        ln = ws_key(_LIST_PREFIX.sub("", line))
        if len(ln) >= 20 and ln not in blob:
            errs.append(f"B Quellzeile nicht verbatim im JSON: '{ln[:70]}'")
    return errs, reps


def check_c(recipe: dict, source: str) -> tuple[list[str], list[str]]:
    errs, reps = [], []
    qsrc = quote_key(source)
    errs += [f"C Zitat nicht in der Quelle: {path} = '{quote[:60]}'"
             for path, quote in annotation_quotes(recipe) if quote_key(quote) not in qsrc]
    exact = derived = 0
    for _, step in iter_steps(recipe):
        p, text = f"step:{step['id']}", step["text"]
        if step.get("actionDerived"):
            toks = UNIT_TOKEN.findall(step["action"])
            if toks and not any(si.get("actionOccurrence") for si in step["ingredients"]):
                errs.append(f"C {p}.action (derived) enthält Mengen {toks} ohne actionOccurrence")
        else:
            na = quote_key(step["action"])
            if not any(na == quote_key(pre) for pre in sentence_prefixes(text)):
                errs.append(f"C {p}.action ist kein verbatim-Präfix aus ganzen Sätzen von text")
            elif len(na) > 0.7 * len(quote_key(text)) and any(step.get(k) for k in ("cues", "why", "rescue", "limits")):
                reps.append(f"C {p}.action umfasst {100 * len(na) // len(quote_key(text))} % des Textes — mengenfreie Kurzfassung (actionDerived) erwägen")
        if step.get("title") and step.get("heading") and quote_key(step["title"]) not in quote_key(step["heading"]):
            errs.append(f"C {p}.title nicht in heading")
        for j, si in enumerate(step["ingredients"]):
            span = si["amount"]["text"]
            if si.get("spanForm", "exact") == "derived":
                derived += 1
                continue
            exact += 1
            n = text.count(span)  # roh, wie der Renderer den Span sucht (L11)
            if n == 0:
                errs.append(f"C {p}.ingredients[{j}] spanForm=exact, aber '{span}' nicht wörtlich in text")
            elif n > 1 and not si.get("occurrence"):
                errs.append(f"C {p}.ingredients[{j}] '{span}' kommt {n}× vor, occurrence fehlt")
            elif si.get("occurrence", 1) > n:
                errs.append(f"C {p}.ingredients[{j}] occurrence {si['occurrence']} > {n} Vorkommen")
    reps.append(f"C Dosierungen: {exact} spanForm=exact, {derived} derived")
    return errs, reps


def check_d(recipe: dict) -> tuple[list[str], list[str]]:
    errs, reps = [], []
    ids: set[str] = set()

    def reg(kind: str, slug: str):
        if not SLUG.match(slug) or slug.isdigit():
            errs.append(f"D ungültiger Slug {kind}:{slug}")
        key = f"{kind}:{slug}"
        if key in ids:
            errs.append(f"D doppelte ID {key}")
        ids.add(key)

    for ing in recipe.get("ingredients", []):
        reg("ingredient", ing["id"])
    for task in iter_tasks(recipe):
        reg("task", task["id"])
        for prod in task.get("produces", []):
            reg("product", prod["id"])
        for step in task["steps"]:
            reg("step", step["id"])
    used: set[str] = set()
    derived: list[str] = []
    for task in iter_tasks(recipe):
        errs += [f"D task:{task['id']} consumes unbekanntes Produkt '{c}'" for c in task.get("consumes", []) if f"product:{c}" not in ids]
        for step in task["steps"]:
            if step.get("actionDerived"):
                derived.append(f"step:{step['id']}.action")
            for j, si in enumerate(step["ingredients"]):
                used.add(si["ref"])
                if f"ingredient:{si['ref']}" not in ids:
                    errs.append(f"D step:{step['id']}.ingredients[{j}] ref '{si['ref']}' unbekannt")
                if si.get("spanForm") == "derived":
                    derived.append(f"step:{step['id']}.ingredients[{j}]")
    # Schritt-Graph: after/start lösen auf, kein Selbstbezug, keine Zyklen (Vorgänger-Default eingeschlossen)
    preds: dict[str, list[str]] = {}
    for task in iter_tasks(recipe):
        prev = None
        for step in task["steps"]:
            me = f"step:{step['id']}"
            after = step.get("after")
            preds[me] = list(after) if after is not None else ([prev] if prev else [])
            for ref in preds[me] + ([step["start"]["ref"].rsplit(":", 1)[0]] if step.get("start") else []):
                if ref not in ids:
                    errs.append(f"D {me}: Referenz '{ref}' löst nicht auf")
                elif ref == me:
                    errs.append(f"D {me}: bezieht sich auf sich selbst")
            prev = me
    state: dict[str, int] = {}

    def cyclic(n: str) -> bool:
        if state.get(n) == 1:
            return True
        if state.get(n) == 2:
            return False
        state[n] = 1
        if any(cyclic(m) for m in preds.get(n, []) if m in preds):
            return True
        state[n] = 2
        return False

    errs += [f"D Zyklus im Schritt-Graph bei {n}" for n in preds if cyclic(n)][:1]
    for sec in sections(recipe, "learnings"):
        errs += [f"D learnings.notes[{i}].ref '{n['ref']}' löst nicht auf" for i, n in enumerate(sec.get("notes", [])) if n["ref"] not in ids]
    for sec in sections(recipe, "todo"):
        errs += [f"D todo.items[{i}].ref '{it['ref']}' löst nicht auf" for i, it in enumerate(sec["items"]) if it.get("ref") and it["ref"] not in ids]
    if unused := [i["id"] for i in recipe.get("ingredients", []) if i["id"] not in used]:
        reps.append(f"D Zutaten ohne Dosierung in Schritten: {', '.join(unused)}")
    reps.append(f"D {len(derived)} derived-Feld(er)" + (": " + ", ".join(derived) if derived else ""))
    return errs, reps
