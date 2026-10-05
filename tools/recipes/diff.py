"""Check I: Feld-Diff zweier unabhängiger Konvertierungen derselben Quelle.

Schritte werden über (Task-Index, label) gepaart, Zutaten über id oder Namenswörter.
Ausgabe: Übereinstimmung pro Feld und die konkreten Abweichungen.
"""
from __future__ import annotations

from .util import iter_tasks, quote_key, section, words

Rows = dict[str, list[tuple[str, object, object]]]


def _ing_map(a: dict, b: dict) -> dict[str, str | None]:
    """ingredient-id in a → id in b (gleiche id, sonst größte Wortüberlappung)."""
    bi = {ib["id"]: ib for ib in b.get("ingredients", [])}
    bw = {iid: words(ib["name"]) for iid, ib in bi.items()}
    out = {}
    for ia in a.get("ingredients", []):
        if ia["id"] in bi:
            out[ia["id"]] = ia["id"]
            continue
        wa = words(ia["name"])
        best = max(bw, key=lambda iid: len(bw[iid] & wa), default=None)
        out[ia["id"]] = best if best and bw[best] & wa else None
    return out


def _dur(d: dict | None):
    return (d.get("min"), d.get("max"), d.get("typical")) if d else None


def _keyed(r: dict) -> dict[tuple[int, str], tuple[dict, dict]]:
    return {(ti, st["label"]): (task, st) for ti, task in enumerate(iter_tasks(r)) for st in task["steps"]}


def diff(a: dict, b: dict) -> list[str]:
    rows: Rows = {}

    def add(field: str, where: str, va, vb):
        rows.setdefault(field, []).append((where, va, vb))

    def pair(field: str, where: str, fn, xa, xb):
        add(field, where, fn(xa), fn(xb))

    for f in ("title", "intro", "status", "kind"):
        pair(f"recipe.{f}", "-", lambda r, f=f: r.get(f), a, b)
    pair("recipe.yields.value", "-", lambda r: r.get("yields", {}).get("value"), a, b)
    pair("recipe.times", "-", lambda r: (_dur(r.get("times", {}).get("active")), _dur(r.get("times", {}).get("total"))), a, b)
    pair("recipe.equipment", "-", lambda r: sorted(r.get("equipment", [])), a, b)
    pair("sections.sequence", "-", lambda r: [(s["type"], s.get("title")) for s in r["sections"]], a, b)
    pair("tasks.ids", "-", lambda r: [t["id"] for t in iter_tasks(r)], a, b)

    imap = _ing_map(a, b)
    bi = {i["id"]: i for i in b.get("ingredients", [])}
    pair("ingredients.count", "-", lambda r: len(r.get("ingredients", [])), a, b)
    for ia in a.get("ingredients", []):
        ib = bi.get(imap.get(ia["id"]) or "")
        add("ingredients.matched", ia["id"], True, ib is not None)
        if not ib:
            continue
        add("ingredients.id", ia["id"], ia["id"], ib["id"])
        for f in ("store", "group", "pantry", "optional", "priority", "scale"):
            pair(f"ingredients.{f}", ia["id"], lambda i, f=f: i.get(f), ia, ib)
        pair("ingredients.note", ia["id"], lambda i: quote_key(i.get("note", "")), ia, ib)

    sa, sb = _keyed(a), _keyed(b)
    add("steps.count", "-", len(sa), len(sb))
    for key, (ta, xa) in sa.items():
        w = f"Schritt {ta['id']}/{key[1]}"
        if key not in sb:
            add("steps.matched", w, True, False)
            continue
        xb = sb[key][1]
        for f in ("id", "title", "attention"):
            pair(f"steps.{f}", w, lambda s, f=f: s.get(f), xa, xb)
        for f in ("text", "heading", "action", "why", "rescue"):
            pair(f"steps.{f}", w, lambda s, f=f: quote_key(s.get(f, "")), xa, xb)
        for f in ("actionDerived", "parallel"):
            pair(f"steps.{f}", w, lambda s, f=f: bool(s.get(f)), xa, xb)
        pair("steps.duration", w, lambda s: _dur(s.get("duration")), xa, xb)
        pair("steps.timers", w, lambda s: sorted(str(_dur(t["duration"])) for t in s.get("timers", [])), xa, xb)
        for f in ("cues", "limits"):
            pair(f"steps.{f}", w, lambda s, f=f: sorted(quote_key(x) for x in s.get(f, [])), xa, xb)
        da = {imap.get(si["ref"]) or si["ref"]: si for si in xa["ingredients"]}
        db = {si["ref"]: si for si in xb["ingredients"]}
        add("steps.ingredients.set", w, sorted(da), sorted(db))
        for ref, sia in da.items():
            if sib := db.get(ref):
                ww = f"{w} / {ref}"
                pair("dose.amount.text", ww, lambda s: quote_key(s["amount"]["text"]), sia, sib)
                pair("dose.value+unit", ww, lambda s: (s["amount"].get("value"), s["amount"].get("max"), s["amount"].get("unit")), sia, sib)
                pair("dose.spanForm", ww, lambda s: s.get("spanForm", "exact"), sia, sib)
                pair("dose.reuse", ww, lambda s: bool(s.get("reuse")), sia, sib)
                pair("dose.occurrence", ww, lambda s: s.get("occurrence"), sia, sib)

    la, lb = section(a, "learnings") or {}, section(b, "learnings") or {}
    pair("learnings.cooked", "-", lambda l: l.get("cooked"), la, lb)
    for f in ("summary", "details"):
        pair(f"learnings.{f}", "-", lambda l, f=f: quote_key(l.get(f, "")), la, lb)
    smap = {xa["id"]: sb[k][1]["id"] for k, (_, xa) in sa.items() if k in sb}
    add("learnings.notes.refs", "-", sorted(smap.get(n["ref"].split(":", 1)[1], n["ref"]) for n in la.get("notes", [])),
        sorted(n["ref"].split(":", 1)[1] for n in lb.get("notes", [])))
    pair("learnings.notes.texts", "-", lambda l: sorted(quote_key(n["text"])[:40] for n in l.get("notes", [])), la, lb)
    return _report(rows)


def _report(rows: Rows) -> list[str]:
    lines = []
    for f, rs in rows.items():
        ok = sum(1 for _, va, vb in rs if va == vb)
        lines.append(f"{f:<28} {ok:>3}/{len(rs):<3} {'' if ok == len(rs) else f'← {len(rs) - ok} Abweichung(en)'}")
    lines.append("")
    for f, rs in rows.items():
        lines += [f"  {f} @ {where}:\n      A: {str(va)[:90]}\n      B: {str(vb)[:90]}" for where, va, vb in rs if va != vb]
    return lines
