"""Abgeleitete Sichten (L10): Mengen-Summen und Einkaufsliste.

`derive()` berechnet aus ingredients[] und step.ingredients[] den Block `derived`
(reine Daten, kein Markdown); `render_shopping()` baut daraus Markdown im heutigen
Format; `check_k()` vergleicht mit der Original-Einkaufsliste der Quelle.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from .fmt import COUNT_UNIT, FRACTION_VALUES, fmt_amount
from .spoons import display_text
from .util import (NUM, SHOPPING_SECTION, TASK_ITEM, UNITS_MASS_VOL, iter_tasks_with_course, quote_key,
                   split_h2, unit_alt, words)

# Besuchs-Reihenfolge laut CLAUDE.md (Asialaden zuerst, dann REWE); Vorrat zuletzt.
STORE_ORDER = ["Online", "Buhara Seafood", "Asialaden", "Selgros", "REWE Center", "Aldi / REWE", "Vorrat"]
# Warengruppen in Laufreihenfolge im Laden (CLAUDE.md „Format: Einkaufslisten“).
GROUP_ORDER = ["Obst & Gemüse", "Fleisch & Fisch", "Milchprodukte & Eier", "Trockenwaren",
               "Würzmittel & Gewürze", "Getränke", "Tiefkühl", "Sonstiges"]
STORE_RANK = {s: i for i, s in enumerate(STORE_ORDER)}
GROUP_RANK = {g: i for i, g in enumerate(GROUP_ORDER)}
TO_BASE = {"kg": ("g", 1000), "l": ("ml", 1000)}


def _base(value: float | None, unit: str | None, hint: dict | None = None) -> tuple[float | None, str]:
    """Einheit kanonisieren: None → Stück, unitHint from→to, kg→g, l→ml."""
    unit = unit or COUNT_UNIT
    if value is None:
        return None, unit
    if hint and unit == hint["from"]:
        value, unit = value * hint["factor"], hint["to"]
    if unit in TO_BASE:
        u, f = TO_BASE[unit]
        value, unit = value * f, u
    return value, unit


def source_hash(recipe: dict) -> str:
    body = {k: v for k, v in recipe.items() if k != "derived"}
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def derived_status(recipe: dict) -> str:
    """'missing' | 'stale' | 'ok' — einzige Stelle, die den gespeicherten Block bewertet."""
    d = recipe.get("derived")
    if not d:
        return "missing"
    return "ok" if d.get("sourceHash") == source_hash(recipe) else "stale"


def _group_key(key: tuple[str, str | None]) -> tuple:
    store, group = key
    return (STORE_RANK.get(store, len(STORE_RANK)), store, GROUP_RANK.get(group, len(GROUP_RANK)), group or "")


def derive(recipe: dict) -> dict:
    """Vorbedingung: Check D ist grün (alle step.ingredients[].ref bekannt). Mit Varianten gelten quantities/shopping
    für die Default-Wahl; `variants[]` hat dieselben Sichten für jede andere Kombination (Python rechnet, der Browser wählt)."""
    from . import variants as V
    head = {"generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "sourceHash": source_hash(recipe)}
    dims = recipe.get("variants") or []
    if not dims:
        return head | _derive(recipe)
    sels = V.selections(dims)
    out = head | {"select": sels[0]} | _derive(V.view(recipe, sels[0]))
    out["variants"] = [{"key": V.selection_key(sel), "select": sel} | _derive(V.view(recipe, sel)) for sel in sels[1:]]
    return out


def _derive(recipe: dict) -> dict:
    ings = {i["id"]: i for i in recipe.get("ingredients", [])}
    acc = {i: {"value": None, "max": None, "unit": None, "approx": False, "mixed": set(), "unitless": [], "perTask": {}, "perCourse": {}}
           for i in ings}
    for course, task in iter_tasks_with_course(recipe):
      for step in task["steps"]:
        for si in step["ingredients"]:
            if si.get("reuse"):
                continue
            if si["ref"] not in acc:
                raise ValueError(f"step:{step['id']}: unbekannte Zutat '{si['ref']}' (Check D zuerst)")
            a, am = acc[si["ref"]], si["amount"]
            if am.get("value") is None:
                a["unitless"].append(am["text"])
                continue
            hint, n = ings[si["ref"]].get("unitHint"), am.get("times", 1)
            v, u = _base(am["value"] * n, am.get("unit"), hint)
            mx, _ = _base(am.get("max", am["value"]) * n, am.get("unit"), hint)
            if a["value"] is None:
                a["unit"] = u
            elif a["unit"] != u:
                a["mixed"].add(u)
                continue
            a["value"] = (a["value"] or 0) + v
            a["max"] = (a["max"] or 0) + mx
            a["approx"] = a["approx"] or bool(am.get("approx"))
            a["perTask"].setdefault(task["id"], []).append(am["text"] + (f" ×{n}" if n > 1 else ""))
            if course:
                pc = a["perCourse"].setdefault(course, [0, 0])
                pc[0] += v; pc[1] += mx

    quantities, groups = {}, {}
    for iid, a in acc.items():
        total = {"text": fmt_amount(a["value"], a["max"], a["unit"], a["approx"])}
        if a["value"] is not None:
            total.update(value=a["value"], max=a["max"], unit=a["unit"], approx=a["approx"])
        q = {"ingredient": iid, "total": total, "perTask": {t: " + ".join(xs) for t, xs in a["perTask"].items()}}
        if a["perCourse"]:
            q["perCourse"] = {c: {"text": fmt_amount(lo, hi, a["unit"]), "value": lo, "max": hi, "unit": a["unit"]} for c, (lo, hi) in a["perCourse"].items()}
        if a["unitless"]:
            q["unitless"] = a["unitless"]
        if a["mixed"]:
            q["unitMixed"] = True
            total["text"] += " (+ " + ", ".join(sorted(a["mixed"])) + " ungemischt)"
        quantities[iid] = q
        ing = ings[iid]
        item = {"ingredient": iid, "name": ing["name"], "need": total,
                "display": display_text(total, ing), "inStock": bool(ing.get("inStock"))}
        for k in ("buy", "priority", "optional", "pantry", "note"):
            if ing.get(k) is not None:
                item[k] = ing[k]
        groups.setdefault((ing["store"], ing.get("group")), []).append(item)

    return {
        "quantities": list(quantities.values()),
        "shopping": [{"store": s, "group": g, "items": groups[(s, g)]} for s, g in sorted(groups, key=_group_key)],
    }


def _item_line(it: dict) -> str:
    """Einzige Stelle, die Markdown für einen Posten baut (inkl. Docsify-Tilde-Escape)."""
    amount = it["display"].replace("~", "\\~")
    line = f"{it['buy']['text']} {it['name']}" + (f" (Bedarf {amount})" if amount else "") if it.get("buy") \
        else f"{amount} {it['name']}".strip()
    if it.get("optional"):
        line = "Optional: " + line
    if n := it.get("note"):
        line += " " + (n if n.startswith("*") else f"*({n})*")
    return f"- [{'x' if it['inStock'] else ' '}] {line}"


def render_shopping(recipe: dict) -> str:
    out = [f"## {SHOPPING_SECTION}", ""]
    cur = None
    for grp in derive(recipe)["shopping"]:
        if grp["store"] != cur:
            cur = grp["store"]
            out += [f"### {cur}", ""]
        if grp.get("group"):
            out += [f"**{grp['group']}:**", ""]
        out += [_item_line(it) for it in grp["items"]] + [""]
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- Check K

_FRAC_ALT = "|".join(FRACTION_VALUES)
_U = unit_alt(UNITS_MASS_VOL)
_QTY = re.compile(rf"^\s*(?:(?i:optional):\s*)?(?P<lo>{NUM}|{_FRAC_ALT})\s*(?P<u1>{_U})?"
                  rf"(?:\s*[–-]\s*(?P<hi>{NUM})\s*(?P<u2>{_U})?)?")
_NOTE = re.compile(r"\*\(.*?\)\*")


def _num(s: str) -> float:
    return FRACTION_VALUES.get(s) or float(s.replace(",", "."))


def parse_qty(part: str) -> tuple[float, float, str] | None:
    """'900 g – 1 kg' → (900, 1000, 'g'); '4–5 EL' → (4, 5, 'EL'); '6 Eier' → (6, 6, 'Stück')."""
    m = _QTY.match(part)
    if not m or not m.group("lo"):
        return None
    hi = _num(m.group("hi")) if m.group("hi") else None
    lo, unit = _base(_num(m.group("lo")), m.group("u1") or m.group("u2"))
    hi, _ = _base(hi, m.group("u2") or m.group("u1"))
    return lo, hi if hi is not None else lo, unit


def original_items(source: str) -> list[str]:
    for title, text in split_h2(source):
        if title.startswith(SHOPPING_SECTION):
            return [m.group(2) for line in text.splitlines() if (m := TASK_ITEM.match(line))]
    return []


def _match_ingredient(part: str, names: dict[str, str], weighted: dict[str, set[str]]) -> str | None:
    """Zutat zu einem Posten-Teil: exakter Name im Text, sonst größte Überlappung
    unterscheidender Wörter (Wörter, die in mehreren Zutatennamen vorkommen, zählen nicht)."""
    key = quote_key(part).lower()
    for iid, name in names.items():
        if name in key:
            return iid
    pw = words(part)
    best = max(weighted, key=lambda iid: len(weighted[iid] & pw), default=None)
    return best if best and weighted[best] & pw else None


def check_k(recipe: dict, source: str) -> tuple[list[str], list[str]]:
    errs, reps = [], []
    items = original_items(source)
    if not items:
        return errs, ["K keine Einkaufsliste in der Quelle"]
    status = derived_status(recipe)
    if status == "stale":
        errs.append("K derived-Block veraltet (sourceHash) — `cli derive` ausführen")
    elif status == "missing":
        reps.append("K derived-Block fehlt — `cli derive` schreibt ihn; Vergleich läuft gegen eine frische Ableitung")
    ings = {i["id"]: i for i in recipe["ingredients"]}
    qty = {q["ingredient"]: q for q in _derive(recipe)["quantities"]}  # alle Varianten zugleich, wie die Markdown-Liste
    names = {iid: quote_key(i["name"]).lower() for iid, i in ings.items()}
    all_words = [words(i["name"]) for i in ings.values()]
    common = {w for ws in all_words for w in ws if sum(w in x for x in all_words) > 1}
    weighted = {iid: words(i["name"]) - common for iid, i in ings.items()}
    covered, reported = set(), set()
    ok = dev = 0
    for item in items:
        wants: dict[str, list] = {}
        last = None
        core = re.split(r"\s—\s", quote_key(_NOTE.sub("", item)), maxsplit=1)[0]  # „— Gang-Zuordnung“ abtrennen
        for part in re.split(r"\s\+\s", core):
            target = _match_ingredient(part, names, weighted) or last
            if target:
                wants.setdefault(target, []).append(parse_qty(part))
                last = target
        if not wants:
            errs.append(f"K Original-Posten ohne Zutat im JSON: '{item[:60]}'")
            continue
        for iid, qs in wants.items():
            covered.add(iid)
            qs = [q for q in qs if q]
            if not qs:
                ok += 1
                continue
            lo, hi, unit = sum(q[0] for q in qs), sum(q[1] for q in qs), qs[0][2]
            tot = qty[iid]["total"]
            if (lo, hi, unit) == (tot.get("value"), tot.get("max"), tot.get("unit")):
                ok += 1
            elif ings[iid].get("buy"):
                ok += 1
                if tot.get("value") is not None:
                    reps.append(f"K {iid}: Gebinde '{ings[iid]['buy']['text']}' statt Bedarf {tot['text']}")
            elif tot.get("value") is None:
                dev += 1
                reps.append(f"K Abweichung {iid}: Original '{item[:50]}' hat Menge, JSON nur Freitext {qty[iid].get('unitless')}")
            else:
                dev += 1
                if iid not in reported:
                    reported.add(iid)
                    per = "; ".join(f"{t}: {x}" for t, x in qty[iid]["perTask"].items())
                    reps.append(f"K Abweichung {iid}: Original {fmt_amount(lo, hi, unit)} (Posten '{item[:40]}') "
                                f"↔ generiert {tot['text']} (Schritte: {per})")
    extra = [iid for iid in ings if iid not in covered]
    reps.insert(0, f"K {len(items)} Original-Posten → {ok + dev} Zutat-Zuordnungen: {ok} passend, {dev} abweichend; "
                   f"{len(extra)} Zutat(en) nur im JSON: {', '.join(extra) or '—'}")
    return errs, reps
