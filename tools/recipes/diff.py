"""Check I: Feld-Diff zweier unabhängiger Konvertierungen derselben Quelle.

Schritte werden über `label` gepaart, Zutaten über id oder Namenswörter.
Ausgabe: Übereinstimmung pro Feld und die konkreten Abweichungen.
"""
from __future__ import annotations

import re
from collections import OrderedDict

from .util import iter_steps, normalize


def _words(s: str) -> set[str]:
    return set(re.findall(r"[a-zäöüß]{4,}", normalize(s).lower()))


def _ing_map(a: dict, b: dict) -> dict[str, str | None]:
    """ingredient-id in a → id in b."""
    out = {}
    bs = list(b.get("ingredients", []))
    for ia in a.get("ingredients", []):
        hit = next((ib for ib in bs if ib["id"] == ia["id"]), None)
        if hit is None:
            wa = _words(ia["name"])
            hit = max(bs, key=lambda ib: len(wa & _words(ib["name"])), default=None)
            if hit is not None and not (wa & _words(hit["name"])):
                hit = None
        out[ia["id"]] = hit["id"] if hit else None
    return out


class Tally:
    def __init__(self):
        self.fields: "OrderedDict[str, list]" = OrderedDict()

    def add(self, field: str, where: str, va, vb, same=None):
        same = (va == vb) if same is None else same
        self.fields.setdefault(field, []).append((where, same, va, vb))

    def report(self) -> list[str]:
        lines = []
        for f, rows in self.fields.items():
            n = len(rows)
            ok = sum(1 for r in rows if r[1])
            lines.append(f"{f:<28} {ok:>3}/{n:<3} {'' if ok == n else '← ' + str(n - ok) + ' Abweichung(en)'}")
        lines.append("")
        for f, rows in self.fields.items():
            for where, same, va, vb in rows:
                if not same:
                    lines.append(f"  {f} @ {where}:\n      A: {str(va)[:90]}\n      B: {str(vb)[:90]}")
        return lines


def _dur(d):
    if not d:
        return None
    return (d.get("min"), d.get("max"), d.get("typical"))


def diff(a: dict, b: dict) -> list[str]:
    t = Tally()
    for f in ("title", "intro", "status", "kind"):
        t.add(f"recipe.{f}", "-", a.get(f), b.get(f))
    t.add("recipe.yields.value", "-", a.get("yields", {}).get("value"), b.get("yields", {}).get("value"))
    t.add("recipe.times", "-", (_dur(a.get("times", {}).get("active")), _dur(a.get("times", {}).get("total"))),
          (_dur(b.get("times", {}).get("active")), _dur(b.get("times", {}).get("total"))))
    t.add("recipe.equipment", "-", sorted(a.get("equipment", [])), sorted(b.get("equipment", [])))
    t.add("sections.sequence", "-", [(s["type"], s.get("title")) for s in a["sections"]],
          [(s["type"], s.get("title")) for s in b["sections"]])

    imap = _ing_map(a, b)
    bi = {i["id"]: i for i in b.get("ingredients", [])}
    t.add("ingredients.count", "-", len(a.get("ingredients", [])), len(b.get("ingredients", [])))
    for ia in a.get("ingredients", []):
        ib = bi.get(imap.get(ia["id"]) or "")
        t.add("ingredients.matched", ia["id"], True, ib is not None, same=ib is not None)
        if not ib:
            continue
        t.add("ingredients.id", ia["id"], ia["id"], ib["id"])
        for f in ("store", "group", "pantry", "optional", "priority", "scale", "prep"):
            t.add(f"ingredients.{f}", ia["id"], ia.get(f), ib.get(f))
        t.add("ingredients.note", ia["id"], normalize(ia.get("note", "")), normalize(ib.get("note", "")))

    sa = {s["label"]: (task, s) for task, s in iter_steps(a)}
    sb = {s["label"]: (task, s) for task, s in iter_steps(b)}
    t.add("steps.count", "-", len(sa), len(sb))
    t.add("tasks.ids", "-", [tk["id"] for tk, _ in iter_steps(a)][:1], [tk["id"] for tk, _ in iter_steps(b)][:1])
    for label, (ta, xa) in sa.items():
        if label not in sb:
            t.add("steps.matched", label, True, False, same=False)
            continue
        tb, xb = sb[label]
        w = f"Schritt {label}"
        t.add("steps.id", w, xa["id"], xb["id"])
        t.add("steps.text", w, normalize(xa["text"]), normalize(xb["text"]))
        t.add("steps.heading", w, normalize(xa.get("heading", "")), normalize(xb.get("heading", "")))
        t.add("steps.title", w, xa.get("title"), xb.get("title"))
        t.add("steps.action", w, normalize(xa["action"]), normalize(xb["action"]))
        t.add("steps.actionDerived", w, bool(xa.get("actionDerived")), bool(xb.get("actionDerived")))
        t.add("steps.attention", w, xa.get("attention"), xb.get("attention"))
        t.add("steps.parallel", w, bool(xa.get("parallel")), bool(xb.get("parallel")))
        t.add("steps.duration", w, _dur(xa.get("duration")), _dur(xb.get("duration")))
        t.add("steps.timers", w, sorted(str(_dur(x["duration"])) for x in xa.get("timers", [])),
              sorted(str(_dur(x["duration"])) for x in xb.get("timers", [])))
        for f in ("why", "rescue"):
            t.add(f"steps.{f}", w, normalize(xa.get(f, "")), normalize(xb.get(f, "")))
        for f in ("cues", "limits"):
            ca, cb = {normalize(x) for x in xa.get(f, [])}, {normalize(x) for x in xb.get(f, [])}
            t.add(f"steps.{f}", w, sorted(ca), sorted(cb), same=(ca == cb))
        t.add("steps.equipment", w, sorted(xa.get("equipment", [])), sorted(xb.get("equipment", [])))
        # Dosierungen: über Zutaten-Mapping paaren
        da = {imap.get(si["ref"]) or si["ref"]: si for si in xa["ingredients"]}
        db = {si["ref"]: si for si in xb["ingredients"]}
        t.add("steps.ingredients.set", w, sorted(da), sorted(db))
        for ref, sia in da.items():
            sib = db.get(ref)
            if not sib:
                continue
            ww = f"{w} / {ref}"
            t.add("dose.amount.text", ww, normalize(sia["amount"]["text"]), normalize(sib["amount"]["text"]))
            t.add("dose.value+unit", ww, (sia["amount"].get("value"), sia["amount"].get("max"), sia["amount"].get("unit")),
                  (sib["amount"].get("value"), sib["amount"].get("max"), sib["amount"].get("unit")))
            t.add("dose.spanForm", ww, sia.get("spanForm", "exact"), sib.get("spanForm", "exact"))
            t.add("dose.reuse", ww, bool(sia.get("reuse")), bool(sib.get("reuse")))
            t.add("dose.occurrence", ww, sia.get("occurrence"), sib.get("occurrence"))

    la = next((s for s in a["sections"] if s["type"] == "learnings"), {})
    lb = next((s for s in b["sections"] if s["type"] == "learnings"), {})
    t.add("learnings.cooked", "-", la.get("cooked"), lb.get("cooked"))
    t.add("learnings.summary", "-", normalize(la.get("summary", "")), normalize(lb.get("summary", "")))
    t.add("learnings.details", "-", normalize(la.get("details", "")), normalize(lb.get("details", "")))
    smap = {xa["id"]: sb[l][1]["id"] for l, (_, xa) in sa.items() if l in sb}
    na = sorted((smap.get(n["ref"].split(":", 1)[1], n["ref"]), normalize(n["text"])[:40]) for n in la.get("notes", []))
    nb = sorted((n["ref"].split(":", 1)[1], normalize(n["text"])[:40]) for n in lb.get("notes", []))
    t.add("learnings.notes.refs", "-", sorted(x[0] for x in na), sorted(x[0] for x in nb))
    t.add("learnings.notes.texts", "-", sorted(x[1] for x in na), sorted(x[1] for x in nb))
    return t.report()
