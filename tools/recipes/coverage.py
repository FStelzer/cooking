"""Checks B (Zahlen-Vollständigkeit), C (Zitat-Treue), D (Referenzen und IDs)."""
from __future__ import annotations

import re
from collections import Counter

from .util import (GENERATED_SECTIONS, UNIT_TOKEN, annotation_quotes, iter_steps, iter_tasks,
                   normalize, sentence_prefixes, source_without_generated, split_h2, unit_tokens, verbatim_strings)

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def check_b(recipe: dict, source: str) -> tuple[list[str], list[str]]:
    """B1 Sektionen vollständig, B2 Zahl+Einheit-Token identisch, B3 jede Quellzeile verbatim enthalten."""
    errs, reps = [], []
    # B1: jede ##-Sektion der Quelle (außer generierte) hat eine Section mit gleichem Titel
    want_titles = [t for t, _ in split_h2(source) if t]
    have_titles = [sec.get("title", "") for sec in recipe.get("sections", [])]
    for t in want_titles:
        if any(t.startswith(g) for g in GENERATED_SECTIONS):
            if t not in have_titles and not any(h.startswith(g) for h in have_titles for g in GENERATED_SECTIONS):
                reps.append(f"B Sektion '{t}' wird generiert, kein Platzhalter im JSON")
            continue
        if t not in have_titles:
            errs.append(f"B Sektion '## {t}' fehlt im JSON")
    # B2: Token-Multiset
    src = source_without_generated(source)
    want = unit_tokens(src)
    have = Counter()
    verb = verbatim_strings(recipe)
    for s in verb:
        have += unit_tokens(s)
    for tok, n in sorted((want - have).items()):
        errs.append(f"B Token fehlt im JSON (verbatim-Felder): '{tok}' ×{n}")
    for tok, n in sorted((have - want).items()):
        errs.append(f"B Token im JSON, aber nicht in der Quelle: '{tok}' ×{n}")
    reps.append(f"B {sum(want.values())} Zahl+Einheit-Token in der Quelle, {sum(have.values())} in verbatim-Feldern")
    # B3: Zeilen-Abdeckung (verbatim-Prinzip L2)
    blob = normalize(" ".join(verb))
    for line in src.splitlines():
        ln = normalize(re.sub(r"^\s*(?:[-*]\s+\[[ x]\]\s+|[-*]\s+|\d+\.\s+|#+\s+|>\s*)", "", line))
        if len(ln) >= 20 and ln not in blob:
            errs.append(f"B Quellzeile nicht verbatim im JSON: '{ln[:70]}'")
    return errs, reps


def _count(hay: str, needle: str) -> int:
    return len(re.findall(re.escape(needle), hay))


def check_c(recipe: dict, source: str) -> tuple[list[str], list[str]]:
    errs, reps = [], []
    nsrc = normalize(source)
    for path, quote in annotation_quotes(recipe):
        if normalize(quote) not in nsrc:
            errs.append(f"C Zitat nicht in der Quelle: {path} = '{quote[:60]}'")
    exact = derived = 0
    for task, step in iter_steps(recipe):
        p = f"step:{step['id']}"
        ntext = normalize(step["text"])
        if not step.get("actionDerived"):
            na = normalize(step["action"])
            prefixes = [normalize(x) for x in sentence_prefixes(step["text"])]
            if na not in prefixes:
                errs.append(f"C {p}.action ist kein verbatim-Präfix aus ganzen Sätzen von text")
            elif len(na) > 0.7 * len(ntext) and any(step.get(k) for k in ("cues", "why", "rescue", "limits")):
                reps.append(f"C {p}.action umfasst {100 * len(na) // len(ntext)} % des Textes — mengenfreie Kurzfassung (actionDerived) erwägen")
        else:
            toks = UNIT_TOKEN.findall(step["action"])
            if toks and not any(si.get("actionOccurrence") for si in step.get("ingredients", [])):
                errs.append(f"C {p}.action (derived) enthält Mengen {toks} ohne actionOccurrence")
        if step.get("title") and step.get("heading") and normalize(step["title"]) not in normalize(step["heading"]):
            errs.append(f"C {p}.title nicht in heading")
        for j, si in enumerate(step.get("ingredients", [])):
            form = si.get("spanForm", "exact")
            a = normalize(si["amount"]["text"])
            if form == "exact":
                exact += 1
                n = _count(ntext, a)
                if n == 0:
                    errs.append(f"C {p}.ingredients[{j}] spanForm=exact, aber '{a}' nicht in text")
                elif n > 1 and not si.get("occurrence"):
                    errs.append(f"C {p}.ingredients[{j}] '{a}' kommt {n}× vor, occurrence fehlt")
                elif si.get("occurrence", 1) > n:
                    errs.append(f"C {p}.ingredients[{j}] occurrence {si['occurrence']} > {n} Vorkommen")
            else:
                derived += 1
    reps.append(f"C Dosierungen: {exact} spanForm=exact, {derived} derived")
    return errs, reps


def check_d(recipe: dict) -> tuple[list[str], list[str]]:
    errs, reps = [], []
    ids: dict[str, str] = {}

    def reg(kind: str, slug: str):
        if not SLUG.match(slug) or slug.isdigit():
            errs.append(f"D ungültiger Slug {kind}:{slug}")
        key = f"{kind}:{slug}"
        if key in ids:
            errs.append(f"D doppelte ID {key}")
        ids[key] = key

    for ing in recipe.get("ingredients", []):
        reg("ingredient", ing["id"])
    for task in iter_tasks(recipe):
        reg("task", task["id"])
        for prod in task.get("produces", []):
            reg("product", prod["id"])
        for step in task["steps"]:
            reg("step", step["id"])
    for task in iter_tasks(recipe):
        for c in task.get("consumes", []):
            if f"product:{c}" not in ids:
                errs.append(f"D task:{task['id']} consumes unbekanntes Produkt '{c}'")
        for step in task["steps"]:
            for j, si in enumerate(step["ingredients"]):
                if f"ingredient:{si['ref']}" not in ids:
                    errs.append(f"D step:{step['id']}.ingredients[{j}] ref '{si['ref']}' unbekannt")
    used = {si["ref"] for _, s in iter_steps(recipe) for si in s["ingredients"]}
    unused = [i["id"] for i in recipe.get("ingredients", []) if i["id"] not in used]
    if unused:
        reps.append(f"D Zutaten ohne Dosierung in Schritten: {', '.join(unused)}")
    for sec in recipe.get("sections", []):
        if sec.get("type") == "learnings":
            for i, n in enumerate(sec.get("notes", [])):
                if n["ref"] not in ids:
                    errs.append(f"D learnings.notes[{i}].ref '{n['ref']}' löst nicht auf")
        if sec.get("type") == "todo":
            for i, it in enumerate(sec["items"]):
                if it.get("ref") and it["ref"] not in ids:
                    errs.append(f"D todo.items[{i}].ref '{it['ref']}' löst nicht auf")
    derived = [f"step:{s['id']}.action" for _, s in iter_steps(recipe) if s.get("actionDerived")]
    derived += [f"step:{s['id']}.ingredients[{j}]" for _, s in iter_steps(recipe)
                for j, si in enumerate(s["ingredients"]) if si.get("spanForm") == "derived"]
    reps.append(f"D {len(derived)} derived-Feld(er)" + (": " + ", ".join(derived) if derived else ""))
    return errs, reps
