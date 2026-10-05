"""Markdown nach REZEPTFORMAT.md → Recipe-Dict (Schema v0.2).

Deterministisch: liest nur die Konvention; was nicht erkannt wird, fehlt im JSON
und landet in `Lint`. Nichts wird geraten.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .shopping import parse_qty
from .util import NUM, sentence_prefixes, split_h2, ws_key

# ------------------------------------------------------------------ Vokabular
STORES = [("asialaden", "Asialaden"), ("rewe center", "REWE Center"), ("rewe / aldi", "Aldi / REWE"), ("aldi / rewe", "Aldi / REWE"),
          ("aldi", "Aldi / REWE"), ("rewe", "REWE Center"), ("selgros", "Selgros"), ("buhara", "Buhara Seafood"),
          ("online", "Online"), ("vorrat", "Vorrat"), ("drogerie", "Drogerie"), ("metzger", "Metzger")]
GROUP_WORDS = [("obst", "Obst & Gemüse"), ("gemüse", "Obst & Gemüse"), ("fleisch", "Fleisch & Fisch"), ("fisch", "Fleisch & Fisch"),
               ("kühltheke", "Milchprodukte & Eier"), ("milch", "Milchprodukte & Eier"), ("eier", "Milchprodukte & Eier"),
               ("trocken", "Trockenwaren"), ("gewürz", "Würzmittel & Gewürze"), ("würz", "Würzmittel & Gewürze"),
               ("getränk", "Getränke"), ("spirituos", "Getränke"), ("tiefkühl", "Tiefkühl"), ("tk", "Tiefkühl")]
SECTION_TAGS = [("kind", "kind"), ("schwangerschaft", "schwangerschaft"), ("beschaffung", "beschaffung"), ("quellen", "quellen"),
                ("notizen", "notizen"), ("stil-entscheidung", "stil"), ("teller-logik", "teller-logik"), ("konzept", "teller-logik"),
                ("profi-tipps", "profi-tipps"), ("fehlerbild", "fehlerbild")]
DOSE_UNITS = ("kg", "g", "ml", "l", "EL", "TL", "Prisen", "Prise", "Tropfen", "Zweige", "Zweig", "Blatt", "Umdrehung", "Schuss",
              "Stück", "Zehen", "Zehe", "Bund", "Päckchen", "Dose", "Dosen", "Glas", "Scheiben", "Scheibe", "Eigelb", "Eiweiß")
QTY_WORDS = ("reichlich", "etwas", "einen Schuss", "ein Schuss", "eine Prise", "einige")
RESCUE_START = ("Fallback", "Rettung", "Gebrochen", "Zu ", "Falls", "Option,", "Notfall")
DUR_UNITS = r"(?:Min\.?|Minuten|Sek\.?|Sekunden|Std\.?|Stunden|h\b)"

NUMW = r"(?:\d+(?:[,.]\d+)?|½|¼|¾|⅓)"
RANGE = rf"{NUMW}(?:\s?[–-]\s?{NUMW})?"
DUR_RE = re.compile(rf"(?P<ca>ca\.\s?|\\?~\s?)?(?P<lo>{NUMW})(?:\s?[–-]\s?(?P<hi>{NUMW}))?\s?(?P<u>{DUR_UNITS})")
STEP_RE = re.compile(r"^\*\*(?P<n>\d+[a-z]?)\.\s+(?P<title>.+?)(?:\s+\((?P<paren>[^()]*(?:\([^()]*\)[^()]*)*)\))?\*\*\s*$")
LABEL_RE = re.compile(r"^\*\*(?P<label>[^*]+?):\*\*\s*$")
LABEL_TEXT_RE = re.compile(r"^\*\*(?P<label>[^*]+?):\*\*\s+(?P<text>.+)$")
ITALIC_RE = re.compile(r"^\*(?!\*)(?P<text>.+)\*$")
TEMP_RE = re.compile(rf"(?:[≥>≤<]\s?)?(?P<lo>\d+)(?:\s?[–-]\s?(?P<hi>\d+))?\s?°C")
TASK_ITEM = re.compile(r"^\s*-\s+\[([ x])\]\s+(.*)$")
H3_RE = re.compile(r"^###\s+(.*)$")


def slugify(s: str) -> str:
    s = re.sub(r"[*_`]", "", s).lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("é", "e"), ("è", "e"), ("à", "a"), ("ị", "i"), ("ứ", "u")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "x"


def num(s: str) -> float:
    return {"½": .5, "¼": .25, "¾": .75, "⅓": .33}.get(s) or float(s.replace(",", "."))


def iso(value: float, unit: str) -> str:
    u = unit.lower()
    if u.startswith("sek"):
        return f"PT{int(round(value))}S"
    if u.startswith("std") or u == "h":
        h = int(value); m = int(round((value - h) * 60))
        return f"PT{h}H{m}M" if m else f"PT{h}H"
    m = int(round(value))
    return f"PT{m // 60}H{m % 60}M" if m >= 60 and m % 60 else (f"PT{m // 60}H" if m >= 60 else f"PT{m}M")


def duration_range(text: str) -> dict | None:
    """„5 Min.“, „90–120 Min.“, „ca. 8 Min.“, „über Nacht“ → DurationRange."""
    if re.search(r"über Nacht", text):
        return {"min": "PT8H", "max": "PT14H", "source": "über Nacht"}
    m = DUR_RE.search(text)
    if not m:
        return None
    lo = num(m["lo"]); hi = num(m["hi"]) if m["hi"] else None
    d = {"min": iso(lo, m["u"]), "max": iso(hi, m["u"])} if hi else {"typical": iso(lo, m["u"])}
    d["source"] = m.group(0).strip()
    if m["ca"]:
        d["estimated"] = True
    return d


@dataclass
class Lint:
    msgs: list[str] = field(default_factory=list)

    def add(self, where: str, msg: str):
        self.msgs.append(f"{where}: {msg}")


# ------------------------------------------------------------------ Kopf
def parse_head(head: str, lint: Lint) -> dict:
    out = {}
    paras = paragraphs(head)
    m = re.search(r"^#\s+(?:(?P<wip>🚧)\s+)?(?P<title>.+)$", head, re.M)
    if not m:
        lint.add("Kopf", "keine H1 gefunden")
        return {"title": "?"}
    out["title"] = m["title"].strip()
    if m["wip"]:
        out["status"] = "wip"
    y = re.search(r"\(([^()]*?)\)\s*$", out["title"])
    if y:
        yt = y.group(1)
        out["yields"] = {"text": yt}
        ym = re.match(rf"\s*(?:ca\.\s?|\\?~)?({NUMW})(?:\s?[–-]\s?{NUMW})?\s+(\w+)", yt)
        if ym:
            out["yields"].update(value=num(ym.group(1)), unit=ym.group(2))
    notes = [p for p in paras if p.startswith("> [!NOTE]")]
    if notes:
        out["statusNote"] = "\n\n".join(notes)
    intro = [p for p in paras if not p.startswith("#") and not p.startswith("> [!NOTE]")]
    if intro:
        out["intro"] = "\n\n".join(intro)
        first = ws_key(intro[0])
        tm = re.search(r"Aktive Zeit\s*(?:\\?~)?(.+?),\s*gesamt\s*(?:\\?~)?(.*)$", first)
        if tm:
            a, t = duration_range(tm.group(1)), duration_range(tm.group(2))
            end = tm.start(2) + (DUR_RE.search(tm.group(2)).end() if t else 0)
            out["times"] = {"text": first[tm.start(): end].strip(" *")}
            if a: out["times"]["active"] = a
            if t: out["times"]["total"] = t
        em = re.search(r"Equipment:\s*(.+?)(?:\.\*|\.$|\*$|$)", first)
        if em:
            out["equipment"] = [e.strip(" .*") for e in re.split(r",\s*", em.group(1)) if e.strip(" .*")]
    return out


def paragraphs(block: str) -> list[str]:
    out, buf = [], []
    for line in block.split("\n"):
        if line.strip() == "":
            if buf:
                out.append("\n".join(buf)); buf = []
        else:
            buf.append(line)
    if buf:
        out.append("\n".join(buf))
    return out


# ------------------------------------------------------------------ Einkaufsliste
def parse_shopping(text: str, lint: Lint) -> list[dict]:
    ings: list[dict] = []
    store, group, seen = "Aldi / REWE", None, set()
    for line in text.split("\n"):
        h3 = H3_RE.match(line)
        if h3:
            lab = h3.group(1).lower()
            store = next((s for key, s in STORES if key in lab), None) or h3.group(1).split("(")[0].strip()
            group = None
            continue
        lm = LABEL_RE.match(line.strip())
        if lm:
            lab = lm["label"].lower()
            group = next((g for key, g in GROUP_WORDS if key in lab), None) or lm["label"].strip()
            continue
        im = TASK_ITEM.match(line)
        if not im:
            continue
        checked, item = im.group(1) == "x", im.group(2).strip()
        note_m = re.search(r"\*\((.*?)\)\*\s*$", item) or re.search(r"\*([^*]+)\*\s*$", item)
        note = note_m.group(1).strip() if note_m else None
        core = item[: note_m.start()].strip() if note_m else item
        core, _, tail = core.partition(" — ")
        courses = [f"gang-{n}" for n in re.findall(r"Gang (\d)", tail + " " + (note or ""))]
        optional = False
        if re.match(r"(?i)^optional:\s*", core):
            optional, core = True, re.sub(r"(?i)^optional:\s*", "", core)
        for part in re.split(r"\s\+\s", core):
            part = part.strip()
            pm = re.match(rf"^(?P<qty>(?:ca\.\s?|\\?~)?{RANGE}(?:\s?(?:kg|g|ml|L|l|EL|TL|Stück|St\.|Blatt|Bund|Töpfchen|Päckchen|Glas|Dose|Flasche|Knolle|Zehen))?)\s+(?P<name>.+)$", part)
            if pm:
                buy, name = pm["qty"].strip(), pm["name"].strip()
            else:
                nm = re.match(rf"^(?P<name>[^,]+),\s*(?P<qty>.+)$", part)
                if nm and not re.search(r"\d|½|¼|¾", nm["qty"]):
                    # Aufzählung ohne Mengen („Zucker, Salz, Pfeffer“) → mehrere Zutaten
                    names = [x.strip() for x in part.split(",") if x.strip()]
                    for nmx in names:
                        iid = slugify(nmx.split()[0])
                        if iid in seen: continue
                        seen.add(iid)
                        ing = {"id": iid, "name": nmx, "store": store}
                        if group: ing["group"] = group
                        if store == "Vorrat": ing["pantry"] = True
                        if courses: ing["courses"] = sorted(set(courses))
                        ings.append(ing)
                    continue
                buy, name = (nm["qty"].strip(), nm["name"].strip()) if nm else (None, part)
            paren = re.search(r"\(([^()]*)\)", name)
            extra = paren.group(1) if paren else None
            name = re.sub(r"\s*\([^()]*\)", "", name).strip(" ,")
            first = re.sub(r"[^\wäöüÄÖÜß-]", " ", name).split()
            iid = slugify(next((w for w in first if w[0].isupper()), first[0] if first else name))
            if iid in seen:
                lint.add("Einkaufsliste", f"doppelte Zutat '{iid}' ({name})")
                continue
            seen.add(iid)
            ing = {"id": iid, "name": name, "store": store}
            if group: ing["group"] = group
            if buy: ing["buy"] = {"text": buy}
            if courses: ing["courses"] = sorted(set(courses))
            if checked: ing["inStock"] = True
            if optional: ing["optional"] = True
            if store == "Vorrat": ing["pantry"] = True
            notes = [x for x in (extra, note, tail if tail and not re.fullmatch(r"(Gang \d.*)", tail) else None) if x]
            if notes: ing["note"] = "; ".join(notes)
            ings.append(ing)
    return ings


# ------------------------------------------------------------------ Schritte
def parse_paren(paren: str | None) -> dict:
    out: dict = {}
    if not paren:
        return out
    d = duration_range(paren)
    if d:
        out["duration"] = d
    low = paren.lower()
    if "parallel" in low: out["parallel"] = True
    if "passiv" in low: out["attention"] = "passive"
    if "jederzeit" in low: out["after"] = []
    return out


def parse_meta(meta: str, lint: Lint, where: str) -> dict:
    """Kursive Meta-Zeile: Klauseln mit „·“."""
    out: dict = {"claims": [], "_after_titles": None, "_anchor": None}
    for raw in re.split(r"\s·\s", meta):
        c = raw.strip()
        low = c.lower()
        if low == "jederzeit":
            out["_after_titles"] = []
        elif low.startswith("nach "):
            out["_after_titles"] = [t.strip() for t in re.split(r",\s*|\s+und\s+", c[5:]) if t.strip()]
        elif low == "parallel":
            out["parallel"] = True
        elif low == "passiv":
            out["attention"] = "passive"
        elif m := re.match(rf"^(?:≤|<=|bis)\s?({RANGE})\s?({DUR_UNITS})\s+vor dem (.+)$", c):
            out["_anchor"] = ("before-step", m.group(3), duration_range(m.group(1) + " " + m.group(2)), c)
        elif m := re.match(rf"^(?:letzte|in den letzten)\s+({RANGE})\s?({DUR_UNITS})\s+(?:von|des)\s+(.+)$", c):
            out["_anchor"] = ("end-of-step", m.group(3), duration_range(m.group(1) + " " + m.group(2)), c)
        elif m := re.match(rf"^(?:\\?~)?({RANGE})\s?({DUR_UNITS})\s+vor (?:Gang (\d)|dem Gang|Service|dem Service)$", c):
            out["_anchor"] = ("before-serve", m.group(3), duration_range(m.group(1) + " " + m.group(2)), c)
        elif m := re.match(r"^Ofen\s+(\d+)\s?°C$", c):
            out["claims"].append({"resource": "oven", "temp": int(m.group(1))})
        elif low == "herd":
            out["claims"].append({"resource": "hob", "units": 1})
        elif m := re.match(r"^(\d+)\s+Pfannen$", c):
            out["claims"].append({"resource": "hob", "units": int(m.group(1))})
        elif low == "grill":
            out["claims"].append({"resource": "grill", "units": 1})
        elif low.startswith("fertig "):
            text = c[7:].strip()
            tm = TEMP_RE.search(text)
            out["endCondition"] = {"type": "temperature" if tm else "visual", "text": text}
            if tm: out["endCondition"]["value"] = int(tm["lo"])
        elif low.startswith("technik:"):
            out["technique"] = c.split(":", 1)[1].strip()
        elif low.startswith("ergibt "):
            out["_produces"] = c[7:].strip()
        elif low.startswith("hält") or low.startswith("bis "):
            out["_hold"] = c
        else:
            lint.add(where, f"Meta-Klausel nicht erkannt: '{c}'")
    if not out["claims"]:
        del out["claims"]
    return out


def annotate_text(step: dict, text: str, ingredients: list[dict], lint: Lint, where: str):
    """Annotationen aus dem Schritttext (alles Zitate)."""
    step["text"] = text
    step["action"] = sentence_prefixes(text)[0]
    # Fett = Grenze
    limits = [m.group(1) for m in re.finditer(r"\*\*([^*]+)\*\*", text)]
    if limits: step["limits"] = limits
    # Kursiv am Ende = Warum / Rettung
    im = re.search(r"\*(?!\*)\(?([^*]+?)\)?\*\s*$", text)
    if im:
        why, rescue = [], []
        for s in re.split(r"(?<=[.!?])\s+", im.group(1).strip()):
            (rescue if s.startswith(RESCUE_START) else why).append(s)
        if why: step["why"] = " ".join(why)
        if rescue: step["rescue"] = " ".join(rescue)
    # „bis …“ = Erkennungszeichen
    cues = [m.group(0).strip() for m in re.finditer(r"\bbis (?:das|der|die|die|es|sie|er|alle|zum|zur|sich|auf)\b[^.;,*)—]+", text)]
    if cues: step["cues"] = cues
    # Timer, Ereignisse, Temperaturen
    timers, events = [], []
    for m in DUR_RE.finditer(text):
        before = text[max(0, m.start() - 6): m.start()]
        d = duration_range(m.group(0))
        if re.search(r"[Nn]ach\s*$", before):
            events.append({"at": d, "text": sentence_at(text, m.start())})
        else:
            timers.append({"label": step.get("title", "Timer"), "duration": {k: v for k, v in d.items() if k != "source"}, "text": m.group(0).strip()})
    if timers: step["timers"] = timers
    if events: step["events"] = events
    temps = []
    for m in TEMP_RE.finditer(text):
        ctx = text[max(0, m.start() - 25): m.start()].lower()
        kind = "kern" if "kern" in text[m.start() - 25: m.end() + 15].lower() else "ofen" if "ofen" in ctx else "halten" if "halten" in ctx or "warm" in ctx else "max" if "über" in ctx or "nie" in ctx else "ziel"
        t = {"kind": kind, "text": m.group(0)}
        if m["hi"]: t.update(min=int(m["lo"]), max=int(m["hi"]))
        else: t["value"] = int(m["lo"])
        temps.append(t)
    if temps: step["temps"] = temps
    # Dosierungen
    step["ingredients"] = find_doses(text, ingredients, lint, where)


def sentence_at(text: str, pos: int) -> str:
    start = max([0] + [m.end() for m in re.finditer(r"[.!?]\s+", text[:pos])])
    end = re.search(r"[.!?](\s|$)", text[pos:])
    return text[start: pos + (end.end() if end else len(text) - pos)].strip()


def ingredient_index(ingredients: list[dict]) -> list[tuple[str, str]]:
    """(wort, id) für alle Namenswörter ≥ 4 Zeichen, längere zuerst."""
    idx = []
    for ing in ingredients:
        for w in re.findall(r"[\wäöüÄÖÜß-]{4,}", ing["name"]):
            idx.append((w.lower(), ing["id"]))
    return sorted(set(idx), key=lambda x: -len(x[0]))


DOSE_RE = re.compile(
    rf"(?P<times>\d+)\s?×\s?|(?P<je>je\s+)?(?P<lo>{NUMW})(?:\s?[–-]\s?(?P<hi>{NUMW}))?\s?(?P<unit>{'|'.join(DOSE_UNITS)})?\s+(?P<words>(?:[\wäöüÄÖÜß*-]+\s+){{0,3}}?[\wäöüÄÖÜß*/-]+)"
)


def find_doses(text: str, ingredients: list[dict], lint: Lint, where: str) -> list[dict]:
    idx = ingredient_index(ingredients)
    out, seen_counts = [], {}
    plain = text
    for m in DOSE_RE.finditer(plain):
        if m["times"]:
            continue
        words = m["words"]
        wl = [w.strip("*").lower() for w in words.split()]
        hit = next(((w, iid) for w, iid in idx for cand in wl if cand.startswith(w) or w.startswith(cand) and len(cand) >= 5), None)
        if not hit:
            continue
        # Span = Zahl … bis einschließlich des Zutatenworts
        end_word = next(w for w in words.split() if w.strip("*").lower().startswith(hit[0]) or hit[0].startswith(w.strip("*").lower()))
        span = plain[m.start(): m.start(words, ) + words.index(end_word) + len(end_word)] if False else None
        span_start = m.start("je") if m["je"] else m.start("lo")
        span_end = m.start("words") + words.index(end_word) + len(end_word)
        span = plain[span_start:span_end]
        lo = num(m["lo"]); hi = num(m["hi"]) if m["hi"] else None
        unit = m["unit"] or "Stück"
        if unit in ("Prisen",): unit = "Prise"
        amount = {"text": span, "value": lo, "unit": unit}
        if hi is not None: amount["max"] = hi
        if m["je"]: amount["per"] = "Pfanne"
        tm = re.search(r"(\d+)\s?×\s?$", plain[:span_start])
        if tm: amount["times"] = int(tm.group(1))
        n = plain.count(span)
        dose = {"ref": hit[1], "amount": amount}
        if n > 1:
            seen_counts[span] = seen_counts.get(span, 0) + 1
            dose["occurrence"] = seen_counts[span]
        prev = next((d for d in out if d["ref"] == hit[1] and d["amount"].get("value") == lo), None)
        if prev or any(d["ref"] == hit[1] and d["amount"].get("value") == lo for d in getattr(find_doses, "_earlier", [])):
            dose["reuse"] = True
        out.append(dose)
    # Mengenwörter ohne Zahl
    for qw in QTY_WORDS:
        for m in re.finditer(rf"\b{qw}\s+([\wäöüÄÖÜß-]+)", plain):
            w = m.group(1).lower()
            hit = next((iid for ww, iid in idx if w.startswith(ww) or ww.startswith(w) and len(w) >= 5), None)
            if hit and not any(d["ref"] == hit for d in out):
                out.append({"ref": hit, "amount": {"text": m.group(0)}})
    return out


# ------------------------------------------------------------------ Komponenten-Label → Produkt
def product_from_label(name: str, paren: str | None) -> tuple[dict, str | None]:
    prod = {"id": slugify(name), "name": name}
    phase = None
    if paren:
        hold, storage = {}, {}
        low = paren.lower()
        if m := re.search(rf"bis ({NUMW})\s?(Tage|Tag|h|Std\.|Min\.)\s+vorher", paren):
            v, u = num(m.group(1)), m.group(2)
            hold["max"] = f"P{int(v)}D" if u.startswith("Tag") else iso(v, u)
        if "ideal am vortag" in low: hold["ideal"] = "P1D"
        if m := re.search(rf"hält (?:bis )?({NUMW})\s?(h|Std\.|Min\.|Tage)", paren):
            v, u = num(m.group(1)), m.group(2)
            hold["max"] = f"P{int(v)}D" if u == "Tage" else iso(v, u)
        if m := re.search(rf"(?:mind\.|mindestens)\s+({NUMW})\s?(h|Std\.|Min\.)", paren):
            hold["min"] = iso(num(m.group(1)), m.group(2))
        if hold:
            hold["source"] = paren; prod["hold"] = hold
        if "kühlschrank" in low or "kalt" in low: storage["place"] = "fridge"
        elif "gefrier" in low or "tk" in low: storage["place"] = "freezer"
        elif "warm" in low:
            storage["place"] = "warm"
            if m := TEMP_RE.search(paren): storage["temp"] = {"min": int(m["lo"]), "max": int(m["hi"] or m["lo"])}
        elif "raumtemperatur" in low: storage["place"] = "room"
        if storage: prod["storage"] = storage
        pm = re.search(r"(Vortag|Vortage|am Abend|Abend|Nachmittag|Vormittag|am Tag|T-\d|à la minute|Saison[^,]*)", paren)
        if pm: phase = pm.group(1)
    return prod, phase


# ------------------------------------------------------------------ Body (Zubereitung / Gang)
def parse_body(text: str, scope: str, ingredients: list[dict], lint: Lint, course_id: str | None = None) -> tuple[list[dict], list[dict], str | None]:
    """→ (sections, tasks, intro). Schritte werden Tasks (Komponenten) zugeordnet."""
    sections: list[dict] = []
    tasks: list[dict] = []
    intro = None
    cur_task: dict | None = None
    cur_step: dict | None = None
    cur_text: list[str] = []
    cur_meta: str | None = None
    first_block = True
    tasks_pos: list[int] = []

    def new_task(name: str, heading: str | None, paren: str | None):
        prod, phase = product_from_label(name, paren)
        t = {"id": slugify(name), "name": name, "steps": []}
        if heading: t["heading"] = heading
        if phase: t["phaseHint"] = phase
        t["produces"] = [prod]
        tasks.append(t)
        return t

    def flush_step():
        nonlocal cur_step, cur_text, cur_meta, cur_task
        if cur_step is None:
            return
        if cur_task is None:
            cur_task = {"id": course_id or "main", "name": scope, "steps": []}
            tasks.append(cur_task)
        txt = "\n".join(cur_text).strip()
        txt = re.sub(r"(?<![\n])\n(?![\n\-*>|])", " ", txt)  # umbrochene Zeilen zusammenziehen, Listen behalten
        where = f"{scope}/Schritt {cur_step['label']}"
        annotate_text(cur_step, txt, ingredients, lint, where)
        if cur_meta:
            meta = parse_meta(cur_meta, lint, where)
            cur_step["_meta"] = meta
            for k in ("parallel", "attention", "claims", "endCondition", "technique"):
                if k in meta: cur_step[k] = meta[k]
            if meta.get("_produces") and cur_task:
                cur_task["produces"] = [product_from_label(meta["_produces"], meta.get("_hold"))[0]]
        if "duration" not in cur_step:
            lint.add(where, "keine Dauer in der Überschrift")
        cur_task["steps"].append(cur_step)
        cur_step, cur_text, cur_meta = None, [], None

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped == "" or stripped == "---":
            i += 1; continue
        sm = STEP_RE.match(stripped)
        if sm:
            if not tasks_pos: tasks_pos.append(len(sections))
            flush_step()
            cur_step = {"id": slugify(sm["title"]), "label": sm["n"], "heading": stripped, "title": sm["title"].strip()}
            cur_step.update(parse_paren(sm["paren"]))
            first_block = False
            # Meta-Zeile?
            if i + 1 < len(lines) and (mm := ITALIC_RE.match(lines[i + 1].strip())) and not LABEL_RE.match(lines[i + 1].strip()):
                cur_meta = mm["text"].strip(); i += 2
            else:
                i += 1
            continue
        lm = LABEL_RE.match(stripped)
        if lm and cur_step is None or (lm and stripped.startswith("**") and cur_step is not None and (i == 0 or lines[i - 1].strip() == "")):
            flush_step()
            label = lm["label"].strip()
            if label.lower().startswith("offen"):
                items, j = [], i + 1
                while j < len(lines) and (TASK_ITEM.match(lines[j]) or (lines[j].startswith("  ") and items)):
                    if tm := TASK_ITEM.match(lines[j]): items.append({"text": tm.group(2).strip(), "checked": tm.group(1) == "x"})
                    else: items[-1]["text"] += " " + lines[j].strip()
                    j += 1
                sections.append({"type": "todo", "title": label, "intro": stripped, "items": items})
                i = j; continue
            pm = re.match(r"^(?P<name>.+?)\s*\((?P<paren>.*)\)$", label)
            name, paren = (pm["name"], pm["paren"]) if pm else (label, None)
            if not tasks_pos: tasks_pos.append(len(sections))
            cur_task = new_task(name, stripped, paren)
            if not paren: lint.add(f"{scope}/{name}", "Komponente ohne Zeitangabe in der Klammer")
            first_block = False
            i += 1; continue
        h3 = H3_RE.match(stripped)
        if h3 and course_id is None:
            flush_step()
            cur_task = new_task(h3.group(1).strip(), None, None)
            i += 1; continue
        if cur_step is not None and not stripped.startswith("> ") and not (LABEL_TEXT_RE.match(stripped) and lines[i - 1].strip() == ""):
            cur_text.append(line); i += 1; continue
        flush_step()
        # Prosa-Block: bis zur Leerzeile
        j = i
        while j < len(lines) and lines[j].strip() != "":
            j += 1
        block = "\n".join(lines[i:j]).strip()
        if first_block and ITALIC_RE.match(block.replace("\n", " ")) and intro is None:
            intro = block
        else:
            lt = LABEL_TEXT_RE.match(block.split("\n")[0])
            title = lt["label"].strip() if lt else ("Profi-Tipps" if block.startswith("> **Profi-Tipps") else block.split("\n")[0][:40])
            tag = next((t for key, t in SECTION_TAGS if key in title.lower()), None)
            sec = {"type": "markdown", "title": title, "level": "bold", "markdown": block}
            if tag: sec["tags"] = [tag]
            sections.append(sec)
        first_block = False
        i = j
    flush_step()
    # Produkte: Komponenten ohne Zeitangabe erzeugen trotzdem ein Produkt; Einzeltask nicht
    resolve_refs(tasks, lint, scope, course_id)
    if tasks:
        sections.insert(tasks_pos[0] if tasks_pos else 0, {"type": "tasks", "title": "Zubereitung", "tasks": tasks})
    return sections, tasks, intro


def resolve_refs(tasks: list[dict], lint: Lint, scope: str, course_id: str | None):
    by_title = {}
    for t in tasks:
        for st in t["steps"]:
            by_title[slugify(st["title"])] = st["id"]
            by_title[st["title"].lower()] = st["id"]
    ids = set(by_title.values())
    if len(ids) < sum(len(t["steps"]) for t in tasks):
        lint.add(scope, "doppelte Schritt-Titel (Slugs kollidieren)")
    prod_names = [(p["name"], t) for t in tasks for p in t.get("produces", [])]
    for t in tasks:
        for st in t["steps"]:
            meta = st.pop("_meta", {})
            at = meta.get("_after_titles")
            if at is not None:
                refs = []
                for title in at:
                    sid = by_title.get(slugify(title)) or by_title.get(title.lower())
                    if sid: refs.append(f"step:{sid}")
                    else: lint.add(f"{scope}/Schritt {st['label']}", f"„nach {title}“: kein Schritt mit diesem Titel")
                st["after"] = refs
            if anc := meta.get("_anchor"):
                kind, target, dur, src = anc
                lo = dur.get("min") or dur.get("typical"); hi = dur.get("max") or dur.get("typical")
                if kind == "before-step":
                    sid = by_title.get(slugify(target))
                    if sid: st["start"] = {"ref": f"step:{sid}:start", "offset": {"min": "-" + hi, "max": "PT0M", "source": src}}
                    else: lint.add(f"{scope}/Schritt {st['label']}", f"Anker „vor dem {target}“: kein Schritt mit diesem Titel")
                elif kind == "end-of-step":
                    sid = by_title.get(slugify(target))
                    if sid: st["start"] = {"ref": f"step:{sid}:end", "offset": {"min": "-" + hi, "max": "-" + lo, "source": src}}
                    else: lint.add(f"{scope}/Schritt {st['label']}", f"Anker „letzte … von {target}“: kein Schritt mit diesem Titel")
                else:
                    ref = f"course:gang-{target}:serve" if target else (f"course:{course_id}:serve" if course_id else "anchor")
                    st["start"] = {"ref": ref, "offset": ({"min": "-" + hi, "max": "-" + lo} if lo != hi else {"typical": "-" + lo}) | {"source": src}}
        # Verbrauch: Produktnamen anderer Tasks im Text
        cons = []
        for name, pt in prod_names:
            if pt is t: continue
            if any(re.search(r"(?i)(?<![\wäöü])" + re.escape(name) + r"(?![\wäöü])", st["text"]) for st in t["steps"]):
                cons.append("product:" + slugify(name))
        if cons: t["consumes"] = sorted(set(cons))


# ------------------------------------------------------------------ Zeitplan
PHASE_RE = [(r"^T-(\d)$", lambda m: {"day": -int(m.group(1))}), (r"^Vortag", lambda m: {"day": -1}), (r"^Vorabend", lambda m: {"day": -1, "part": "evening"}),
            (r"^Vormittag", lambda m: {"day": 0, "part": "morning"}), (r"^Nachmittag", lambda m: {"day": 0, "part": "afternoon"}),
            (r"^(Am )?Abend", lambda m: {"day": 0, "part": "evening"}), (r"^Am Tag", lambda m: {"day": 0}),
            (r"^Gang (\d) \((\+?)(\d+):(\d+)\)$", lambda m: {"day": 0, "part": "service", "at": f"{'+' if m.group(2) else ''}PT{int(m.group(3))}H{int(m.group(4))}M".replace("PT0H", "PT").replace("H0M", "H").replace("PT0M", "PT0M")})]


def parse_schedule(title: str, text: str, tasks_all: list[tuple[str | None, dict]], lint: Lint) -> tuple[dict, str | None]:
    phases, entries, note = [], [], None
    seen = {}
    bullets: list[str] = []
    for line in text.split("\n"):
        if line.startswith("- "): bullets.append(line[2:])
        elif line.startswith("  ") and bullets: bullets[-1] += " " + line.strip()
        elif line.startswith("**") and ":**" in line and not line.startswith("**Vortage") and len(line) > 20: note = (note + "\n\n" if note else "") + line
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 2 and re.match(r"^T[−-]", cells[0]):
                tm = re.match(r"^T[−-](\d+)(?::(\d+))?", cells[0])
                mins = int(tm.group(1)) * (60 if tm.group(2) else 1) + int(tm.group(2) or 0)
                pid = "kochtag"
                if pid not in seen:
                    seen[pid] = True; phases.append({"id": pid, "label": "Kochtag", "day": 0, "part": "service"})
                entries.append({"phase": pid, "text": cells[1], "at": {"ref": "anchor", "offset": f"-PT{mins}M"}, "source": cells[0]})
    for b in bullets:
        lm = re.match(r"^(?P<label>[^:(]*(?:\([^)]*\))?):\s*(?P<rest>.*)$", b)
        if not lm:
            lint.add("Zeitplan", f"Bullet ohne Phasen-Präfix: '{b[:40]}'"); continue
        label, rest = lm["label"].strip(), lm["rest"]
        spec = next((fn(m) for pat, fn in PHASE_RE if (m := re.match(pat, label))), None)
        if spec is None:
            lint.add(f"Zeitplan", f"Phase nicht erkannt: '{label}'"); continue
        gm = re.match(r"^Gang (\d)", label)
        pid = f"gang-{gm.group(1)}" if gm else slugify(label)
        if pid not in seen:
            seen[pid] = True
            phases.append({"id": pid, "label": label, **spec})
        for seg in re.split(r"\s·\s", rest.strip()):
            seg = seg.strip()
            if seg: entries.append({"phase": pid, "text": seg})
    # Zuordnung per Namen
    for e in entries:
        low = ws_key(e["text"]).lower()
        hits_t, hits_s, course = [], [], None
        for cid, t in tasks_all:
            if t["id"] != "main" and t["name"].lower() in low or any(p["name"].lower() in low for p in t.get("produces", [])):
                hits_t.append(t["id"]); course = course or cid
            for st in t["steps"]:
                if st["title"].lower() in low and len(st["title"]) > 3:
                    hits_s.append(st["id"]); course = course or cid
        if hits_t: e["tasks"] = sorted(set(hits_t))
        elif hits_s: e["steps"] = sorted(set(hits_s))
        if course: e["course"] = course
        if e["phase"].startswith("gang-"): e["course"] = e["phase"]
        if m := re.search(rf"\(?(?:\\?~)?({RANGE})\s?({DUR_UNITS})\s+vor dem Gang\)?", e["text"]):
            d = duration_range(m.group(1) + " " + m.group(2))
            e["at"] = {"ref": f"course:{e.get('course', 'gang-1')}:serve", "offset": "-" + (d.get("typical") or d["max"])}
            e["source"] = m.group(0).strip("()")
    sched = {"id": slugify(title), "label": title, "phases": phases, "entries": entries}
    return sched, note


# ------------------------------------------------------------------ Learnings / To-do
def parse_learnings(text: str) -> dict:
    paras = paragraphs(text)
    summary = paras[0] if paras else ""
    cm = re.search(r"\*\*(?:Gekocht|Gebacken|Gemacht)[^*]*?(\d{2}/\d{4})", summary)
    sec = {"type": "learnings", "title": "Learnings", "cooked": cm.group(1) if cm else None, "summary": summary}
    rest = "\n\n".join(paras[1:])
    if rest: sec["details"] = rest
    notes = re.search(r"^### Notizen aus dem Kochmodus[^\n]*\n+(.*?)(?=^###|\Z)", rest, re.S | re.M)
    if notes and notes.group(1).strip():
        sec["notes"] = [{"text": notes.group(1).strip(), "status": "open"}]
    return sec


def parse_todo(title: str, text: str) -> dict:
    items = []
    for line in text.split("\n"):
        if m := TASK_ITEM.match(line): items.append({"text": m.group(2).strip(), "checked": m.group(1) == "x"})
        elif line.startswith("  ") and items: items[-1]["text"] += " " + line.strip()
    return {"type": "todo", "title": title, "items": items}


# ------------------------------------------------------------------ Rezept
def parse_recipe(md: str, recipe_id: str) -> tuple[dict, Lint]:
    lint = Lint()
    parts = split_h2(md)
    head, secs = parts[0][1], parts[1:]
    recipe = {"$schema": "../schema/recipe.schema.json", "schemaVersion": "0.1", "id": recipe_id, "kind": "dish"}
    recipe.update(parse_head(head, lint))
    recipe.setdefault("yields", {"text": "?"})
    titles = {t: x for t, x in secs}
    shop = next((x for t, x in secs if t.startswith("Einkaufsliste")), "")
    ingredients = parse_shopping(shop, lint) if shop else []
    for extra in ("salz", "wasser", "pfeffer"):
        pass
    if not any(i["id"] == "wasser" for i in ingredients):
        ingredients.append({"id": "wasser", "name": "Wasser", "store": "Vorrat", "pantry": True})
    recipe["ingredients"] = ingredients
    is_menu = any(t == "Rezepte" and re.search(r"^### \d+\.", x, re.M) for t, x in secs)
    recipe["kind"] = "menu" if is_menu else "dish"
    sections: list[dict] = []
    tasks_all: list[tuple[str | None, dict]] = []
    schedule_secs = []
    for title, text in secs:
        if title.startswith("Einkaufsliste"):
            sections.append({"type": "shopping", "title": title}); continue
        if title.startswith("Mengen-Check"):
            continue
        if title in ("Zubereitung", "Rezept") and not is_menu:
            body_secs, tasks, intro = parse_body(text, recipe["title"], ingredients, lint)
            if intro: recipe["intro"] = (recipe.get("intro", "") + "\n\n" + intro).strip()
            sections += body_secs
            tasks_all += [(None, t) for t in tasks]
            continue
        if title == "Rezepte" and is_menu:
            courses = []
            for block in re.split(r"^(?=### )", text, flags=re.M):
                if not block.startswith("### "): continue
                lines = block.split("\n")
                ctitle = lines[0][4:].strip()
                cid = f"gang-{re.match(r'(\d+)', ctitle).group(1)}"
                body = re.sub(r"\n+---\s*$", "", "\n".join(lines[1:]).strip("\n"))
                csecs, ctasks, cintro = parse_body(body, ctitle, ingredients, lint, course_id=cid)
                course = {"id": cid, "kind": "course", "title": ctitle, "sections": csecs}
                if cintro: course["intro"] = cintro
                courses.append(course)
                tasks_all += [(cid, t) for t in ctasks]
            sections.append({"type": "courses", "title": title, "courses": courses}); continue
        if title.startswith("Zeitplan"):
            schedule_secs.append((title, text)); sections.append({"type": "schedule", "title": title}); continue
        if title == "Learnings":
            sections.append(parse_learnings(text)); continue
        if title.startswith("To-do") or title.startswith("Offen"):
            sections.append(parse_todo(title, text)); continue
        tag = next((t for key, t in SECTION_TAGS if key in title.lower()), None)
        sec = {"type": "markdown", "title": title, "level": 2, "markdown": text.strip("\n")}
        if tag: sec["tags"] = [tag]
        sections.append(sec)
    # Zeitpläne (brauchen alle Tasks)
    for title, text in schedule_secs:
        sched, note = parse_schedule(title, text, tasks_all, lint)
        sec = next(s for s in sections if s.get("type") == "schedule" and s["title"] == title)
        sec["schedule"] = sched
        if note: sec["note"] = note
        if is_menu:
            recipe["courses"] = [{"ref": p["id"], "n": int(p["id"][5:]), "name": p["label"].split(" (")[0], "serve": p["at"], "source": p["label"]}
                                 for p in sched["phases"] if p["id"].startswith("gang-")]
            recipe["anchor"] = {"label": "Gang 1 serviert"}
            recipe["resources"] = [{"id": "oven", "count": 1}, {"id": "hob", "count": 4}, {"id": "cook", "count": 1}]
    if is_menu and "courses" not in recipe:
        recipe["courses"] = [{"ref": c["id"], "n": int(c["id"][5:]), "name": c["title"], "serve": "PT0M"} for s in sections if s.get("type") == "courses" for c in s["courses"]]
        recipe["anchor"] = {"label": "Service"}
    recipe["sections"] = sections
    # Zutaten ohne Dosierung
    used = {si["ref"] for _, t in tasks_all for st in t["steps"] for si in st["ingredients"]}
    unused = [i["id"] for i in ingredients if i["id"] not in used]
    if unused: lint.add("Einkaufsliste", "Zutaten ohne Dosierung in Schritten: " + ", ".join(unused))
    return recipe, lint
