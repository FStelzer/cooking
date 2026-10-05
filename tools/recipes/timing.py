"""Checks E (Schritt-Abdeckung), F (Zeitplan-Abdeckung), G (Hold-Konsistenz),
H (Service-Intervalle, warn) und L (Mengen-Check rekonstruierbar)."""
from __future__ import annotations

import re

from .shopping import _match_ingredient, derive, parse_qty, words
from .util import (iter_courses, iter_tasks, iter_tasks_with_course, quote_key, sections, split_h2, ws_key)

_ISO = re.compile(r"^([+-]?)P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")
PART_RANK = {None: 0, "morning": 1, "afternoon": 2, "evening": 3, "service": 4}


def secs(d: str | None) -> int | None:
    if not d:
        return None
    m = _ISO.match(d)
    if not m:
        return None
    s = int(m[2] or 0) * 86400 + int(m[3] or 0) * 3600 + int(m[4] or 0) * 60 + int(m[5] or 0)
    return -s if m[1] == "-" else s


def is_days(d: str | None) -> bool:
    return bool(d) and "T" not in d


def course_blocks(source: str) -> dict[str, str]:
    """{'gang-N': Quelltext des ###-Blocks} aus der ##-Sektion Rezepte."""
    rez = dict(split_h2(source)).get("Rezepte", "")
    out = {}
    for block in re.split(r"^(?=### )", rez, flags=re.M):
        m = re.match(r"^### (\d+)\.", block)
        if m:
            out[f"gang-{m[1]}"] = block
    return out


# ---------------------------------------------------------------- E
def check_e(recipe: dict, source: str) -> tuple[list[str], list[str]]:
    errs, reps = [], []
    blocks = course_blocks(source)
    for course in iter_courses(recipe):
        tasks = [t for sec in sections(course, "tasks") for t in sec["tasks"]]
        if not tasks:
            continue
        want = {m[1] for m in re.finditer(r"^(?:\*\*)?(\d+)\. ", blocks.get(course["id"], ""), re.M)}
        have = {st["label"] for t in tasks for st in t["steps"]}
        missing, extra = sorted(want - have, key=int), sorted(h for h in have - want if h.isdigit())
        if missing:
            errs.append(f"E {course['id']}: nummerierte Quellschritte ohne Step: {', '.join(missing)}")
        if extra:
            errs.append(f"E {course['id']}: Step-Labels ohne Quellschritt: {', '.join(extra)}")
        reps.append(f"E {course['id']}: {len(want)} nummerierte Schritte, {len(have)} Steps (davon {len(have) - len([h for h in have if h.isdigit()])} unnummeriert)")
    return errs, reps


# ---------------------------------------------------------------- F
def schedule_segments(text: str, labels: list[str]) -> list[str]:
    """Bullets (mit Folgezeilen) → Phasen-Präfix ab → ·-Segmente."""
    bullets: list[str] = []
    for line in text.splitlines():
        if line.startswith("- "):
            bullets.append(line[2:])
        elif line.startswith("  ") and bullets:
            bullets[-1] += " " + line.strip()
    segs = []
    for b in bullets:
        for lab in sorted(labels, key=len, reverse=True):
            if b.startswith(lab + ":"):
                b = b[len(lab) + 1:]
                break
        segs += [s.strip() for s in re.split(r"\s·\s", b) if s.strip()]
    return segs


def check_f(recipe: dict, source: str) -> tuple[list[str], list[str]]:
    errs, reps = [], []
    h2 = dict(split_h2(source))
    for sec in sections(recipe, "schedule"):
        sch = sec["schedule"]
        text = h2.get(sec["title"], "")
        if not text:
            errs.append(f"F Zeitplan-Sektion '## {sec['title']}' nicht in der Quelle")
            continue
        want = [quote_key(s) for s in schedule_segments(text, [p["label"] for p in sch["phases"]])]
        have = [quote_key(e["text"]) for e in sch["entries"] if not e.get("derived")]
        derived = [e["text"] for e in sch["entries"] if e.get("derived")]
        for w in want:
            if w not in have:
                errs.append(f"F Zeitplan-Eintrag nicht im JSON: '{w[:70]}'")
        for h in have:
            if h not in want:
                errs.append(f"F JSON-Eintrag nicht im Original-Zeitplan (derived fehlt?): '{h[:70]}'")
        linked = sum(1 for e in sch["entries"] if e.get("tasks"))
        reps.append(f"F {sec['title'][:30]}: {len(want)} Original-Segmente, {len(have)} verbatim-Einträge, {linked} mit Task, {len(derived)} abgeleitet"
                    + (": " + "; ".join(derived) if derived else ""))
    return errs, reps


# ---------------------------------------------------------------- Zeitgerüst
def _phase_rank(ph: dict) -> tuple:
    return (ph["day"], PART_RANK.get(ph.get("part")), secs(ph.get("at")) or 0)


def placements(recipe: dict) -> dict[str, list[tuple[dict, dict]]]:
    """task-id → [(phase, entry)] über alle Schedules (Einträge mit tasks oder steps)."""
    out: dict[str, list] = {}
    step_task = {st["id"]: t["id"] for t in iter_tasks(recipe) for st in t["steps"]}
    for sec in sections(recipe, "schedule"):
        phases = {p["id"]: p for p in sec["schedule"]["phases"]}
        for e in sec["schedule"]["entries"]:
            tids = set(e.get("tasks", [])) | {step_task[s] for s in e.get("steps", []) if s in step_task}
            for t in tids:
                out.setdefault(t, []).append((phases[e["phase"]], e))
    return out


def _dur(step: dict) -> int:
    d = step.get("duration") or {}
    return secs(d.get("typical")) or secs(d.get("min")) or secs(d.get("max")) or 0


def task_span(task: dict) -> int:
    return sum(_dur(s) for s in task["steps"])


def service_times(recipe: dict) -> dict[str, tuple[int, int, dict]]:
    """task-id → (start, end, entry) in Sekunden relativ zum Anker, nur verzeitete Einträge."""
    serve = {c["ref"]: secs(c["serve"]) or 0 for c in recipe.get("courses", [])}
    tasks = {t["id"]: t for t in iter_tasks(recipe)}
    out = {}
    step_task = {st["id"]: t["id"] for t in tasks.values() for st in t["steps"]}
    for sec in sections(recipe, "schedule"):
        phases = {p["id"]: p for p in sec["schedule"]["phases"]}
        phase_cursor: dict[str, int] = {}
        for e in sec["schedule"]["entries"]:
            ph = phases[e["phase"]]
            if e.get("at"):
                ref, off = e["at"]["ref"], secs(e["at"]["offset"]) or 0
                base = serve.get(ref.split(":")[1], 0) if ref.startswith("course:") else 0
                t0 = base + off
            elif ph.get("at") is not None and ph.get("part") == "service":
                t0 = max(secs(ph["at"]) or 0, phase_cursor.get(e["phase"], -10**9))  # ohne eigene Zeit: nach dem vorigen Eintrag der Phase
            else:
                continue
            cur = t0
            units = [(tid, task_span(tasks[tid])) for tid in e.get("tasks", [])]
            units += [(step_task[s], sum(_dur(x) for x in tasks[step_task[s]]["steps"] if x["id"] == s)) for s in e.get("steps", []) if s in step_task]
            for tid, span in units:
                start = min(out[tid][0], cur) if tid in out else cur
                out[tid] = (start, max(out[tid][1] if tid in out else 0, cur + span), e)
                cur += span
            phase_cursor[e["phase"]] = cur
    return out


# ---------------------------------------------------------------- G
def check_g(recipe: dict) -> tuple[list[str], list[str]]:
    errs, reps = [], []
    producer = {}
    for t in iter_tasks(recipe):
        for p in t.get("produces", []):
            producer[f"product:{p['id']}"] = (t, p)
            h = p.get("hold") or {}
            lo, hi, ideal = secs(h.get("min")), secs(h.get("max")), secs(h.get("ideal"))
            if lo is not None and hi is not None and lo > hi:
                errs.append(f"G product:{p['id']}: hold.min > hold.max")
            if ideal is not None and ((lo is not None and ideal < lo) or (hi is not None and ideal > hi)):
                errs.append(f"G product:{p['id']}: hold.ideal außerhalb von min/max")
    pl = placements(recipe)
    checked = 0
    for t in iter_tasks(recipe):
        for c in t.get("consumes", []):
            if c not in producer:
                continue
            pt, prod = producer[c]
            pp, cp = pl.get(pt["id"]), pl.get(t["id"])
            if not pp or not cp:
                continue
            p_rank = min(_phase_rank(ph) for ph, _ in pp)
            c_rank = max(_phase_rank(ph) for ph, _ in cp)
            checked += 1
            if c_rank < p_rank:
                errs.append(f"G task:{t['id']} verbraucht {c}, ist aber vor dem Erzeuger task:{pt['id']} platziert")
            hmax = (prod.get("hold") or {}).get("max")
            if hmax and is_days(hmax):
                gap = c_rank[0] - p_rank[0]
                if gap > secs(hmax) // 86400:
                    errs.append(f"G {c}: Erzeuger {pt['id']} liegt {gap} Tage vor Verbraucher {t['id']}, hold.max ist {hmax}")
    reps.append(f"G {len(producer)} Produkte, {checked} Erzeuger→Verbraucher-Paare über Phasen geprüft")
    return errs, reps


# ---------------------------------------------------------------- H (warn)
def check_h(recipe: dict) -> tuple[list[str], list[str]]:
    reps = []
    st = service_times(recipe)
    tasks = {t["id"]: t for t in iter_tasks(recipe)}
    cook = {r["id"]: r["count"] for r in recipe.get("resources", [])}
    if not st:
        return [], ["H keine verzeiteten Service-Einträge"]
    ids = sorted(st, key=lambda k: st[k][0])
    fmt = lambda s: f"{'+' if s >= 0 else '−'}{abs(s) // 3600}:{abs(s) % 3600 // 60:02d}"
    reps.append("H Service-Intervalle (relativ zu Gang 1): " + "; ".join(f"{k} {fmt(st[k][0])}–{fmt(st[k][1])}" for k in ids))
    # Koch: zwei aktive Tasks gleichzeitig
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if st[a][2] is st[b][2]:
                continue  # sequenziell im selben Eintrag
            if st[a][0] < st[b][1] and st[b][0] < st[a][1] and cook.get("cook", 1) == 1:
                reps.append(f"H ⚠ Koch doppelt belegt: {a} ({fmt(st[a][0])}–{fmt(st[a][1])}) und {b} ({fmt(st[b][0])}–{fmt(st[b][1])})")
    # Ofen: überlappende Claims mit verschiedener Temperatur; Herd: Einheiten > Kapazität
    claims = []
    for tid, (t0, t1, _) in st.items():
        cur = t0
        for s in tasks[tid]["steps"]:
            d = _dur(s)
            for cl in s.get("claims", []):
                claims.append((cl["resource"], cl.get("temp"), cl.get("units", 1), cur, cur + d, s["id"]))
            cur += d
    for i, a in enumerate(claims):
        for b in claims[i + 1:]:
            if a[0] == b[0] and a[3] < b[4] and b[3] < a[4]:
                if a[0] == "oven" and a[1] != b[1]:
                    reps.append(f"H ⚠ Ofen: {a[5]} bei {a[1]} °C und {b[5]} bei {b[1]} °C überlappen")
                if a[0] == "hob" and a[2] + b[2] > cook.get("hob", 4):
                    reps.append(f"H ⚠ Herd: {a[5]} + {b[5]} brauchen {a[2] + b[2]} Platten")
    # Gang-Abstände vs. Task-Spannen
    serve = {c["ref"]: secs(c["serve"]) or 0 for c in recipe.get("courses", [])}
    for tid, (t0, t1, e) in st.items():
        c = e.get("course")
        if c in serve and t1 > serve[c]:
            reps.append(f"H ⚠ {tid} endet {fmt(t1)}, Gang {c} wird {fmt(serve[c])} serviert")
    # explizite Constraints (nur wenn beide Ereignisse verzeitet)
    ev = {}
    for tid, (t0, t1, _) in st.items():
        ev[f"task:{tid}:start"], ev[f"task:{tid}:end"] = t0, t1
        cur = t0
        for s in tasks[tid]["steps"]:
            ev[f"step:{s['id']}:start"] = cur
            cur += _dur(s)
            ev[f"step:{s['id']}:end"] = cur
    for c in recipe.get("constraints", []):
        if c["from"] in ev and c["to"] in ev:
            gap, val = ev[c["to"]] - ev[c["from"]], secs(c["value"]) or 0
            ok = gap >= val if c["type"] == "min-gap" else gap <= val
            reps.append(f"H {'✓' if ok else '⚠'} {c['type']} {c['from']} → {c['to']}: {gap // 60} Min. (Grenze {val // 60})")
    return [], reps


# ---------------------------------------------------------------- L
def _cell_qty(cell: str):
    cell = quote_key(cell).strip()
    if cell in ("", "—", "-"):
        return None
    total = [0.0, 0.0, None]
    for part in re.split(r"\s\+\s", cell):
        part = part.lstrip("~≈ ").strip()
        q = parse_qty(part)
        if not q:
            continue
        total[0] += q[0]; total[1] += q[1]; total[2] = total[2] or q[2]
    return None if total[2] is None else tuple(total)


def check_l(recipe: dict, source: str) -> tuple[list[str], list[str]]:
    errs, reps = [], []
    sec = next(((t, x) for t, x in split_h2(source) if t.startswith("Mengen-Check")), None)
    if not sec:
        return errs, ["L kein Mengen-Check in der Quelle"]
    rows = [l for l in sec[1].splitlines() if l.startswith("|")]
    if len(rows) < 3:
        return errs, ["L Mengen-Check-Tabelle nicht lesbar"]
    header = [h.strip() for h in rows[0].strip("|").split("|")]
    converted = {c["id"] for c in iter_courses(recipe) if any(sections(c, "tasks"))}
    col = {f"gang-{m[1]}": i for i, h in enumerate(header) if (m := re.match(r"Gang (\d+)", h))}
    ings = {i["id"]: i for i in recipe["ingredients"]}
    names = {iid: quote_key(i["name"]).lower() for iid, i in ings.items()}
    allw = [words(i["name"]) for i in ings.values()]
    common = {w for ws in allw for w in ws if sum(w in x for x in allw) > 1}
    weighted = {iid: words(i["name"]) - common for iid, i in ings.items()}
    qty = {q["ingredient"]: q for q in derive(recipe)["quantities"]}
    ok = dev = skipped = 0
    for row in rows[2:]:
        cells = [c.strip() for c in row.strip("|").split("|")]
        iid = _match_ingredient(cells[0], names, weighted)
        if not iid:
            skipped += 1
            continue
        for cid in converted & set(col):
            want = _cell_qty(cells[col[cid]])
            have = (qty.get(iid, {}).get("perCourse") or {}).get(cid)
            if want is None and have is None:
                continue
            if want is None or have is None:
                dev += 1
                reps.append(f"L {cells[0]} / {cid}: Tabelle '{cells[col[cid]][:30]}' ↔ JSON {have and (have['value'], have['unit'])}")
                continue
            hv, hm = have["value"], have["max"]
            if (abs(hv - want[0]) <= 0.26 * max(want[0], 1e-9)) and have["unit"] == want[2]:
                ok += 1
            else:
                dev += 1
                msg = f"L {cells[0]} / {cid}: Tabelle {want[0]:g}{'–' + format(want[1], 'g') if want[1] != want[0] else ''} {want[2]} ↔ JSON {hv:g}{'–' + format(hm, 'g') if hm != hv else ''} {have['unit']} ('{cells[col[cid]][:40]}')"
                # Nur ein sauberer Fall ist ein Fehler: gleiche Einheit, keine Pro-/Reserve-/Sammelangaben
                soft = have["unit"] != want[2] or re.search(r"pro |je |Reserve|Test|≈|/", cells[col[cid]] + cells[0])
                (reps if soft else errs).append(msg)
    reps.insert(0, f"L Mengen-Check: {ok} Zellen passend, {dev} abweichend, {skipped} Zeilen ohne Zutat; geprüfte Gänge: {', '.join(sorted(converted & set(col))) or '—'}")
    return errs, reps
