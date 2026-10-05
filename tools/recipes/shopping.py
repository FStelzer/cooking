"""Abgeleitete Sichten (L10): Mengen-Summen und Einkaufsliste.

`derive()` berechnet aus ingredients[] und step.ingredients[] den Block `derived`
und schreibt ihn ins JSON; `render_shopping()` macht daraus Markdown im heutigen
Format; `check_k()` vergleicht mit der Original-Einkaufsliste der Quelle.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from datetime import datetime, timezone

from .spoons import display_text
from .util import iter_tasks, normalize, split_h2

# Besuchs-Reihenfolge laut CLAUDE.md (Asialaden zuerst, dann REWE); Vorrat zuletzt.
STORE_ORDER = ["Online", "Buhara Seafood", "Asialaden", "Selgros", "REWE Center", "Aldi / REWE", "Vorrat"]
# Warengruppen in Laufreihenfolge im Laden (CLAUDE.md „Format: Einkaufslisten“)
GROUP_ORDER = ["Obst & Gemüse", "Fleisch & Fisch", "Milchprodukte & Eier", "Trockenwaren",
               "Würzmittel & Gewürze", "Getränke", "Tiefkühl", "Sonstiges"]
_UNSET = object()
STOPWORDS = {"frische", "frischer", "frisches", "rote", "roter", "rotes", "große", "großer", "kleine", "kleiner",
             "ganze", "ganzer", "stück", "optional", "oder", "zum", "etwas", "gehackt", "gemahlen", "fein"}
TO_BASE = {"kg": ("g", 1000), "l": ("ml", 1000)}
FRACTIONS = {0.5: "½", 0.25: "¼", 0.75: "¾", 0.33: "⅓"}


def source_hash(recipe: dict) -> str:
    body = {k: v for k, v in recipe.items() if k != "derived"}
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def fmt_num(x: float) -> str:
    if x in FRACTIONS:
        return FRACTIONS[x]
    if float(x).is_integer():
        return str(int(x))
    return f"{x:g}".replace(".", ",")


def fmt_amount(value, mx, unit, approx=False) -> str:
    if value is None:
        return ""
    s = fmt_num(value) if mx in (None, value) else f"{fmt_num(value)}–{fmt_num(mx)}"
    if unit and unit != "Stück":
        s += f" {unit}"
    return ("~" if approx else "") + s


def _base(value, unit, hint):
    """Einheit auf Basis bringen: kg→g, l→ml, unitHint from→to."""
    if value is None:
        return value, unit
    if hint and unit == hint["from"]:
        value, unit = value * hint["factor"], hint["to"]
    if unit in TO_BASE:
        u, f = TO_BASE[unit]
        value, unit = value * f, u
    return value, unit


def derive(recipe: dict) -> dict:
    ings = OrderedDict((i["id"], i) for i in recipe.get("ingredients", []))
    acc = {i: {"value": None, "max": None, "unit": _UNSET, "approx": False, "mixed": set(), "unitless": [], "perTask": OrderedDict()} for i in ings}
    for task in iter_tasks(recipe):
        for step in task["steps"]:
            for si in step["ingredients"]:
                if si.get("reuse") or si["ref"] not in acc:  # unbekannte Refs meldet Check D
                    continue
                a = acc[si["ref"]]
                am = si["amount"]
                v, mx, u = am.get("value"), am.get("max", am.get("value")), am.get("unit")
                if v is None:
                    a["unitless"].append(am["text"])
                    continue
                hint = ings[si["ref"]].get("unitHint")
                v, u2 = _base(v, u, hint)
                mx, _ = _base(mx, u, hint)
                if a["unit"] is _UNSET:
                    a["unit"] = u2
                elif a["unit"] != u2:
                    a["mixed"].add(u2 or "ohne Einheit")
                    continue
                a["value"] = (a["value"] or 0) + v
                a["max"] = (a["max"] or 0) + mx
                a["approx"] = a["approx"] or bool(am.get("approx"))
                pt = a["perTask"].setdefault(task["id"], [])
                pt.append(am["text"])
    quantities = []
    for iid, a in acc.items():
        unit = None if a["unit"] is _UNSET else a["unit"]
        q = {"ingredient": iid, "total": {"text": fmt_amount(a["value"], a["max"], unit, a["approx"])}}
        if a["value"] is not None:
            q["total"].update({"value": a["value"], "max": a["max"], "approx": a["approx"]})
            if unit:
                q["total"]["unit"] = unit
        if a["unitless"]:
            q["unitless"] = a["unitless"]
        if a["mixed"]:
            q["unitMixed"] = True
            q["total"]["text"] += " (+ " + ", ".join(sorted(a["mixed"])) + " ungemischt)"
        q["perTask"] = {t: " + ".join(xs) for t, xs in a["perTask"].items()}
        quantities.append(q)
    qmap = {q["ingredient"]: q for q in quantities}

    groups: "OrderedDict[tuple, list]" = OrderedDict()
    for iid, ing in ings.items():
        q = qmap[iid]
        need = q["total"]
        text = display_text(need, ing) if need.get("value") is not None else need["text"]
        text = text.replace("~", "\\~")  # Docsify: einzelne Tilde = Durchstreichung (CLAUDE.md)
        name = ing["name"] + (f", {ing['prep']}" if ing.get("prep") else "")
        line = f"{text} {name}".strip() if text else name
        if ing.get("buy"):
            line = f"{ing['buy']['text']} {name} (Bedarf {text})" if text else f"{ing['buy']['text']} {name}"
        if ing.get("optional"):
            line = "Optional: " + line
        if ing.get("note"):
            n = ing["note"]
            line += " " + (n if n.startswith("*") else f"*({n})*")
        item = {"ingredient": iid, "name": ing["name"], "text": line, "need": need,
                "checked": bool(ing.get("inStock"))}
        for k in ("buy", "priority", "optional", "pantry"):
            if ing.get(k) is not None:
                item[k] = ing[k]
        groups.setdefault((ing["store"], ing.get("group")), []).append(item)

    def store_key(k):
        s, g = k
        return (STORE_ORDER.index(s) if s in STORE_ORDER else len(STORE_ORDER), s,
                GROUP_ORDER.index(g) if g in GROUP_ORDER else len(GROUP_ORDER), g or "")

    shopping = [{"store": s, "group": g, "items": items} for (s, g), items in sorted(groups.items(), key=lambda kv: store_key(kv[0]))]
    return {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sourceHash": source_hash(recipe),
        "quantities": quantities,
        "shopping": shopping,
    }


def render_shopping(recipe: dict) -> str:
    d = recipe.get("derived")
    if not d or d.get("sourceHash") != source_hash(recipe):
        import sys
        print("Hinweis: derived-Block fehlt oder ist veraltet — Einkaufsliste wird aus dem JSON neu berechnet", file=sys.stderr)
        d = derive(recipe)
    out = ["## Einkaufsliste", ""]
    cur = None
    for grp in d["shopping"]:
        if grp["store"] != cur:
            cur = grp["store"]
            out += [f"### {cur}", ""]
        if grp.get("group"):
            out += [f"**{grp['group']}:**", ""]
        for it in grp["items"]:
            out.append(f"- [{'x' if it['checked'] else ' '}] {it['text']}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- Check K

_QTY = re.compile(
    r"^\s*(?:optional:\s*)?(?P<lo>\d+(?:[,.]\d+)?|½|¼|¾)\s*(?P<u1>(?:kg|g|ml|l|EL|TL|Prise)(?![\wäöüßÄÖÜ]))?"
    r"(?:\s*[–-]\s*(?P<hi>\d+(?:[,.]\d+)?)\s*(?P<u2>(?:kg|g|ml|l|EL|TL|Prise)(?![\wäöüßÄÖÜ]))?)?",
)
_FRAC = {"½": 0.5, "¼": 0.25, "¾": 0.75}


def _num(s):
    return _FRAC.get(s) or float(s.replace(",", "."))


def parse_qty(part: str):
    """'900 g – 1 kg' → (900, 1000, 'g'); '4–5 EL' → (4, 5, 'EL'); '6 Eier' → (6, 6, None)."""
    m = _QTY.match(part)
    if not m or not m.group("lo"):
        return None
    lo, hi = _num(m.group("lo")), _num(m.group("hi")) if m.group("hi") else None
    u1, u2 = m.group("u1"), m.group("u2")
    u1 = None if u1 is None else u1 if u1 in ("EL", "TL") else u1.lower()
    u2 = None if u2 is None else u2 if u2 in ("EL", "TL") else u2.lower()
    unit = u2 or u1
    if u1 and u2 and u1 != u2:  # 900 g – 1 kg
        lo, _ = _base(lo, u1, None)
        hi, unit = _base(hi, u2, None)
    else:
        lo, unit_b = _base(lo, unit, None)
        hi, _ = _base(hi, unit, None) if hi is not None else (None, None)
        unit = unit_b
    return lo, (hi if hi is not None else lo), unit


def original_items(source: str) -> list[str]:
    for title, text in split_h2(source):
        if title.startswith("Einkaufsliste"):
            return [re.sub(r"^\s*- \[[ x]\]\s+", "", l) for l in text.splitlines() if re.match(r"^\s*- \[[ x]\]", l)]
    return []


def _words(s: str) -> set[str]:
    s = normalize(s).lower()
    return {w for w in re.findall(r"[a-zäöüß]{4,}", s)} - STOPWORDS


def _match_ingredient(part: str, ings: dict) -> str | None:
    """Zutat zu einem Posten-Teil: exakter Name > größte Wortüberlappung > Teilwort."""
    np_ = normalize(part).lower()
    for iid, ing in ings.items():
        if normalize(ing["name"]).lower() in np_:
            return iid
    pw = _words(part)
    best, score = None, 0
    for iid, ing in ings.items():
        n = len(_words(ing["name"]) & pw)
        if n > score:
            best, score = iid, n
    if best:
        return best
    for iid, ing in ings.items():
        if any(w in np_ for w in _words(ing["name"])):
            return iid
    return None


def check_k(recipe: dict, source: str) -> tuple[list[str], list[str]]:
    errs, reps = [], []
    items = original_items(source)
    if not items:
        return errs, ["K keine Einkaufsliste in der Quelle"]
    d = recipe.get("derived")
    if not d:
        return ["K derived-Block fehlt — `cli derive` ausführen"], []
    if d.get("sourceHash") != source_hash(recipe):
        return ["K derived-Block veraltet (sourceHash) — `cli derive` ausführen"], []
    ings = {i["id"]: i for i in recipe["ingredients"]}
    qty = {q["ingredient"]: q for q in d["quantities"]}
    covered: set[str] = set()
    reported: set[str] = set()
    ok = dev = 0
    for item in items:
        parts = [p.strip() for p in re.split(r"\s\+\s", normalize(re.sub(r"\*\(.*?\)\*", "", item)))]
        last = None
        wants: "OrderedDict[str, list]" = OrderedDict()
        for part in parts:
            target = _match_ingredient(part, ings) or last
            if target is None:
                continue
            wants.setdefault(target, []).append(parse_qty(part))
            last = target
        if not wants:
            errs.append(f"K Original-Posten ohne Zutat im JSON: '{item[:60]}'")
            continue
        for iid, qs in wants.items():
            covered.add(iid)
            tot = qty[iid]["total"]
            qs = [q for q in qs if q]
            if not qs:
                ok += 1
                continue
            lo = sum(q[0] for q in qs)
            hi = sum(q[1] for q in qs)
            unit = qs[0][2]
            g_lo, g_hi, g_unit = tot.get("value"), tot.get("max"), tot.get("unit")
            if g_unit == "Stück":
                g_unit = None
            if g_lo is None:
                dev += 1
                reps.append(f"K Abweichung {iid}: Original '{item[:50]}' hat Menge, JSON nur Freitext {qty[iid].get('unitless')}")
            elif (lo, hi, unit) == (g_lo, g_hi, g_unit):
                ok += 1
            elif ings[iid].get("buy"):
                ok += 1
                reps.append(f"K {iid}: Gebinde '{ings[iid]['buy']['text']}' statt Bedarf {tot['text']}")
            else:
                dev += 1
                if iid not in reported:
                    reported.add(iid)
                    reps.append(f"K Abweichung {iid}: Original {fmt_amount(lo, hi, unit)} (Posten '{item[:40]}') ↔ generiert "
                                f"{tot['text']} (Schritte: {'; '.join(f'{t}: {x}' for t, x in qty[iid]['perTask'].items())})")
    extra = [iid for iid in ings if iid not in covered]
    reps.insert(0, f"K {len(items)} Original-Posten → {ok + dev} Zutat-Zuordnungen: {ok} passend, {dev} abweichend; "
                   f"{len(extra)} Zutat(en) nur im JSON: {', '.join(extra) or '—'}")
    return errs, reps
