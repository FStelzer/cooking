"""Markdown nach REZEPTFORMAT.md → Recipe-Dict (Schema v0.2).

Deterministisch: liest nur die Konvention; was nicht erkannt wird, fehlt im JSON
und landet in `Lint`. Nichts wird geraten.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .fmt import APPROX, NUMW, RANGE, SIZE_WORD, parse_num
from .shopping import parse_qty
from . import variants as V
from .util import DEFAULT_RESOURCES, NUM, all_doses, sentence_prefixes, slugify, split_h2, ws_key

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
DOSE_UNITS = ("kg", "g", "ml", "l", "L", "cm", "EL", "TL", "Prisen", "Prise", "Tropfen", "Zweige", "Zweig", "Blatt", "Umdrehung", "Schuss",
              "Stück", "Zehen", "Zehe", "Bund", "Päckchen", "Dose", "Dosen", "Glas", "Scheiben", "Scheibe", "Eigelb", "Eiweiß")
ALIASES = {"eigelb": "eier", "eiweiß": "eier", "eiweiss": "eier", "ei": "eier"}  # Textwort → Zutaten-ID
QTY_WORDS = ("reichlich", "etwas", "einen Schuss", "einem Schuss", "ein Schuss", "eine Prise", "einige", "großzügig")
RESCUE_START = ("Fallback", "Rettung", "Gebrochen", "Falls", "Option", "Notfall", "Noch sicherer")
RESCUE_COND = re.compile(r"^(Ist|Wird|Wenn|Sollte|Falls)\b[^.]*,")
DUR_UNITS = r"(?:Min\.?|Minuten|Sek\.?|Sekunden|Std\.?|Stunden|h\b|Tage?\b)"

DUR_RE = re.compile(rf"(?P<ca>ca\.\s?|\\?~\s?)?(?P<lo>{NUMW})(?:\s?[–-]\s?(?P<hi>{NUMW}))?\s?(?P<u>{DUR_UNITS})")
STEP_RE = re.compile(r"^\*\*(?P<n>\d+[a-z]?)\.\s+(?P<title>.+?)(?:\s+\((?P<paren>[^()]*(?:\([^()]*\)[^()]*)*)\))?\*\*\s*$")
LABEL_RE = re.compile(r"^\*\*(?P<label>[^*]+?):\*\*\s*$")
LABEL_TEXT_RE = re.compile(r"^\*\*(?P<label>[^*]+?):\*\*\s+(?P<text>.+)$")
ITALIC_RE = re.compile(r"^\*(?!\*)(?P<text>.+)\*$")
TEMP_RE = re.compile(rf"(?:[≥>≤<]\s?)?(?P<lo>\d+)(?:\s?[–-]\s?(?P<hi>\d+))?\s?°C")
TASK_ITEM = re.compile(r"^\s*-\s+\[([ x])\]\s+(.*)$")
H3_RE = re.compile(r"^###\s+(.*)$")




def head_noun(name: str) -> str:
    """Erstes Hauptwort: Adjektive (klein geschrieben oder „Schwarzer“ vor Großwort) überspringen."""
    words = [w for w in re.sub(r"[^\wäöüÄÖÜß/-]", " ", re.sub(r"[*_`]", "", name)).split() if w]
    caps = [w for w in words if w[0].isupper()]
    for i, w in enumerate(caps):
        nxt = caps[i + 1] if i + 1 < len(caps) else None
        if nxt and re.search(r"(er|es|e|en)$", w.lower()) and words.index(nxt) == words.index(w) + 1:
            continue
        return max(w.split("/"), key=lambda x: len(x.strip("-"))).strip("-")
    w = (caps or words or [name])[0]
    return max(w.split("/"), key=lambda x: len(x.strip("-"))).strip("-")




def iso(value: float, unit: str) -> str:
    u = unit.lower()
    if u.startswith("tag"):
        return f"P{int(round(value))}D"
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
    lo = parse_num(m["lo"]); hi = parse_num(m["hi"]) if m["hi"] else None
    d = {"min": iso(lo, m["u"]), "max": iso(hi, m["u"])} if hi else {"typical": iso(lo, m["u"])}
    d["source"] = m.group(0).strip()
    if m["ca"]:
        d["estimated"] = True
    return d


@dataclass
class Lint:
    """Hinweise eines Parse-Laufs — und sein Kontext: die Varianten des Rezepts (vor Einkaufsliste und Schritten gesetzt)."""
    msgs: list[str] = field(default_factory=list)
    dims: list[dict] = field(default_factory=list)
    alt: re.Pattern | None = None  # Klammer mit Alternativen, aus dims

    def only(self, text: str, where: str) -> list[str] | None:
        """„Einfrieren, Kombi“ → Wahl-Refs; unbekannte Namen (oder gar keine Varianten) als Hinweis."""
        refs, unknown = V.parse_only(text, self.dims)
        if unknown or not self.dims:
            self.add(where, f"„nur …“: unbekannte Wahl {', '.join(unknown) or text}")
        return refs

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
    out["status"] = "wip" if m["wip"] else "done"
    y = re.search(r"\(([^()]*?)\)\s*$", out["title"])
    if y:
        yt = y.group(1)
        out["yields"] = {"text": yt}
        ym = re.match(rf"\s*(?:ca\.\s?|\\?~)?({NUMW})(?:\s?[–-]\s?{NUMW})?\s+(\w+)", yt)
        if ym:
            out["yields"].update(value=parse_num(ym.group(1)), unit=ym.group(2))
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
            tend = DUR_RE.search(tm.group(2)) or re.search(r"über Nacht", tm.group(2))  # „gesamt über Nacht“ hat keine Zahl
            end = tm.start(2) + (tend.end() if t and tend else 0)
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
def name_core(name: str) -> str:
    """Name ohne Zusatz nach dem Komma und ohne Markdown-Auszeichnung."""
    return re.sub(r"[*_`]", "", name.split(",")[0]).strip()


def ingredient_id(name: str, ings: list[dict], lint: Lint) -> str | None:
    """Kennung = Hauptwort. Teilen sich zwei Posten das Hauptwort („Zucker“, „Brauner Zucker“), behält der
    nackte Name die kurze Kennung, der qualifizierte bekommt den ganzen Kernnamen („brauner-zucker“) —
    egal in welcher Reihenfolge sie stehen. Gleicher Kernname = Dublette."""
    iid, full = slugify(head_noun(name)), slugify(name_core(name))
    taken = {i["id"]: i for i in ings}
    if iid not in taken:
        return iid
    other = taken[iid]
    if full == iid and slugify(name_core(other["name"])) != iid:
        other["id"] = slugify(name_core(other["name"]))  # bisheriger Posten war der qualifizierte
        return iid
    if full != iid and full not in taken:
        return full
    lint.add("Einkaufsliste", f"doppelte Zutat '{iid}' ({name})")
    return None


def parse_shopping(text: str, lint: Lint) -> list[dict]:
    ings: list[dict] = []
    store, group = "Aldi / REWE", None
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
        only = None
        if lint.dims and (om := re.match(r"^nur\s+(.+)$", tail)):
            only = lint.only(om.group(1), "Einkaufsliste")
            tail = tail[: om.start()].strip()
        optional = False
        if re.match(r"(?i)^optional:\s*", core):
            optional, core = True, re.sub(r"(?i)^optional:\s*", "", core)
        for part in re.split(r"\s\+\s", core):
            part = part.strip()
            paren0 = re.search(r"\(([^()]*)\)", part)
            part_np = re.sub(r"\s*\([^()]*\)", "", part).strip()
            pm = re.match(rf"^(?P<qty>(?:ca\.\s?|\\?~)?{RANGE}(?:\s?(?:kg|g|ml|L|l|EL|TL|Stück|St\.|Blatt|Bund|Töpfchen|Päckchen|Glas|Dose|Flasche|Knolle|Zehen))?)\s+(?P<name>.+)$", part_np)
            if pm:
                buy, name = pm["qty"].strip(), pm["name"].strip()
            else:
                nm = re.match(rf"^(?P<name>[^,]+),\s*(?P<qty>.+)$", part_np)
                if nm and not re.search(r"\d|½|¼|¾", nm["qty"]) and all(x.strip()[:1].isupper() for x in part_np.split(",") if x.strip()):
                    # Aufzählung ohne Mengen („Zucker, Salz, Pfeffer“) → mehrere Zutaten
                    names = [x.strip() for x in part_np.split(",") if x.strip()]
                    for nmx in names:
                        iid = ingredient_id(nmx, ings, lint)
                        if iid is None: continue
                        ing = {"id": iid, "name": nmx, "store": store}
                        if group: ing["group"] = group
                        if store == "Vorrat": ing["pantry"] = True
                        if courses: ing["courses"] = sorted(set(courses))
                        if only: ing["only"] = only
                        ings.append(ing)
                    continue
                if nm and not re.search(r"\d|½|¼|¾", nm["qty"]):
                    buy, name = None, part_np  # „Weißer Pfeffer, ganz“: Qualifizierer bleibt im Namen
                else:
                    buy, name = (nm["qty"].strip(), nm["name"].strip()) if nm else (None, part_np)
            extra = paren0.group(1) if paren0 else None
            name = name.strip(" ,")
            iid = ingredient_id(name, ings, lint)
            if iid is None: continue
            ing = {"id": iid, "name": name, "store": store}
            if group: ing["group"] = group
            if buy: ing["buy"] = {"text": buy}
            if courses: ing["courses"] = sorted(set(courses))
            if checked: ing["inStock"] = True
            if optional: ing["optional"] = True
            if store == "Vorrat": ing["pantry"] = True
            if only: ing["only"] = only
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
            out["_after_titles"] = [t.strip() for t in re.split(r",\s*", c[5:]) if t.strip()]
        elif low.startswith("nur "):
            if refs := lint.only(c[4:], where): out["only"] = out.get("only", []) + refs
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
        elif low.startswith("hält") or low.startswith("bis ") or low.startswith("mind."):
            out["_hold"] = (out.get("_hold", "") + ", " + c).strip(", ")
        else:
            lint.add(where, f"Meta-Klausel nicht erkannt: '{c}'")
    if not out["claims"]:
        del out["claims"]
    return out


def annotate_text(step: dict, text: str, ingredients: list[dict], lint: Lint, where: str, seen_doses: set | None = None):
    """Annotationen aus dem Schritttext (alles Zitate)."""
    step["text"] = text
    step["action"] = sentence_prefixes(text)[0]
    # Fett = Grenze
    limits = [m.group(1) for m in re.finditer(r"\*\*([^*]+)\*\*", text)
              if len(m.group(1).split()) >= 2 and not m.group(1).rstrip().endswith(":")]  # „**Weg B — klassisch:**“ ist ein Label
    if limits: step["limits"] = limits
    # Kursiv am Ende = Warum / Rettung
    im = re.search(r"\*(?!\*)\(?([^*]+?)\)?\*\s*$", text)
    if im:
        why, rescue = [], []
        for s in re.split(r"(?<=[.!?])\s+", im.group(1).strip()):
            if s.startswith(("Vorsicht", "Achtung")):
                step.setdefault("limits", []).append(s)
            elif s.startswith(RESCUE_START) or " dann " in s or "→" in s or RESCUE_COND.match(s):
                rescue.append(s)
            else:
                why.append(s)
        if why: step["why"] = " ".join(why)
        if rescue: step["rescue"] = " ".join(rescue)
    # Konditionale Rettung auch außerhalb der Kursivschrift („Ist sie zu salzig, …“)
    if "rescue" not in step:
        cond = [x for x in re.split(r"(?<=[.!?])\s+", text) if RESCUE_COND.match(x.strip("*"))]
        if cond: step["rescue"] = " ".join(x.strip() for x in cond)
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
        elif re.search(r"(hält|haltbar|bis zu|bis|≤|<|mind\.|mindestens|höchstens|max\.|maximal|alle|seit)\s*$", text[max(0, m.start() - 12): m.start()]) \
                or re.match(r"\s*(vor\b|vorher|früher|später|lang haltbar)", text[m.end(): m.end() + 14]):
            continue  # Haltbarkeit, Vorlauf, Obergrenze — keine Garzeit, also kein Timer
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
    # Dosierungen; Inline-Alternativen („80 g Wasser (Dinkel: 40 g)“) werden für die Grund-Dosierung maskiert
    alts, masked = [], text
    if (pat := lint.alt) is not None:
        for m in pat.finditer(text):
            alts.append(m)
            masked = masked[:m.start()] + " " * (m.end() - m.start()) + masked[m.end():]
    step["ingredients"] = find_doses(masked, ingredients, lint, where, seen_doses if seen_doses is not None else set(), original=text)
    if alts:
        step["alts"] = [variant_alt(m, text, step["ingredients"], ingredients, lint, where) for m in alts]


QTY_ONLY = re.compile(rf"{APPROX}(?P<lo>{NUMW})(?:\s?[–-]\s?(?P<hi>{NUMW}))?{SIZE_WORD}\s?(?P<unit>{'|'.join(DOSE_UNITS)})?")
QTY_PREFIX = re.compile(rf"{APPROX}{RANGE}(?:{SIZE_WORD}\s?(?:{'|'.join(DOSE_UNITS)})(?![\wäöüÄÖÜß]))?")


def variant_alt(m: re.Match, text: str, doses: list[dict], ingredients: list[dict], lint: Lint, where: str) -> dict:
    """Klammer mit Alternativen → {text, base?, baseQty?, options[{when, text, qty?}]}. Steht sie direkt hinter einer
    Grund-Dosierung, bekommt diese `byVariant`: reine Mengen („90 g“, `qty`) behalten die Zutat und ersetzen im Text nur
    `baseQty` („80 g“ von „80 g Wasser“); Text mit Zutatenwort wird neu gelesen und ersetzt die ganze Grund-Dosierung."""
    options = [{"when": ref, "text": t} for ref, t in V.split_alt(m["body"], lint.dims)]
    alt = {"text": m.group(0), "options": options}
    before = text[:m.start()].rstrip()
    base = next((d for d in doses if before.endswith(d["amount"]["text"])), None)
    if base is None:
        return alt
    alt["base"] = base["amount"]["text"]
    if bq := QTY_PREFIX.match(alt["base"]):
        alt["baseQty"] = bq.group(0)
    by = {}
    for o in options:
        q = QTY_ONLY.fullmatch(o["text"])
        if q:
            o["qty"] = True
            am = {"text": o["text"], "value": parse_num(q["lo"]), "unit": q["unit"] or base["amount"].get("unit") or "Stück"}
            if q["hi"]: am["max"] = parse_num(q["hi"])
            by[o["when"]] = [{"ref": base["ref"], "amount": am}]
        else:
            ds = find_doses(o["text"], ingredients, lint, where, set())
            if not ds: lint.add(where, f"Alternative „{o['text']}“ ohne erkannte Menge")
            by[o["when"]] = ds
    base["byVariant"] = by
    return alt


def sentence_at(text: str, pos: int) -> str:
    start = max([0] + [m.end() for m in re.finditer(r"[.!?]\s+", text[:pos])])
    end = re.search(r"[.!?](\s|$)", text[pos:])
    return text[start: pos + (end.end() if end else len(text) - pos)].strip()


def ingredient_index(ingredients: list[dict]) -> list[tuple[str, str]]:
    """(wort, id): Hauptwort jeder Zutat (bei „A/B“ beide Teile) und, bei mehrwortigen Kernnamen,
    der Kernname als Phrase mit Leerzeichen („brauner zucker“). Qualifizierer allein zählen nicht."""
    idx = []
    for ing in ingredients:
        core = name_core(ing["name"])
        head = head_noun(core)
        phrase = " ".join(re.findall(r"[\wäöüÄÖÜß/-]+", core)).lower()
        if " " in phrase: idx.append((phrase, ing["id"]))
        if ing["id"] != slugify(head) and ing["id"] == slugify(core):
            continue  # qualifizierte Dublette („Brauner Zucker“): nur die Phrase zählt
        for w in re.split(r"/", head):
            w = w.strip("-").lower()
            if len(w) >= 2: idx.append((w, ing["id"]))  # „Öl“ ist zwei Zeichen lang
    return sorted(set(idx), key=lambda x: (-len(x[0]), x[0], x[1]))


DOSE_RE = re.compile(
    rf"(?P<times>\d+)\s?×\s?|(?P<je>je\s+)?(?P<lo>{NUMW})(?:\s?[–-]\s?(?P<hi>{NUMW}))?{SIZE_WORD}\s?(?P<unit>{'|'.join(DOSE_UNITS)})?(?:\s?\((?:ca\.\s?)?{NUMW}\s?(?:kg|g|ml)\))?\s+(?P<words>(?:[\wäöüÄÖÜß*-]+\s+){{0,3}}?[\wäöüÄÖÜß*/-]+)"
)


UMLAUT_FOLD = str.maketrans("äöü", "aou")
PREP_STOP = {"über", "auf", "in", "im", "mit", "von", "vom", "zu", "zum", "zur", "aus", "für"}  # „(2 kg mit Knochen)“
DOSE_STOP = PREP_STOP | {"die", "der", "den", "das", "dem", "und"}  # Artikel erst ab dem zweiten Wort: „400 g der Tomaten“


def best_match(cand: str, idx: list[tuple[str, str]]):
    """Zutatenwort zu einem Textwort (ohne Phrasen): Alias > exakt > Textwort beginnt mit Zutatenwort („Limettensaft“)
    > Zutatenwort endet auf Textwort („Sellerie“ → Knollensellerie) > Beugung (höchstens 2 Zeichen länger)."""
    cand = ALIASES.get(cand, cand).translate(UMLAUT_FOLD)  # Umlaut-Plural: Apfel ↔ Äpfel
    words = [(w.translate(UMLAUT_FOLD), iid) for w, iid in idx if " " not in w]
    for part in dict.fromkeys([cand] + [p for p in re.split(r"[-/]", cand) if len(p) >= 4]):
        exact = [x for x in words if x[0] == part]
        if exact: return exact[0]
        pre = [x for x in words if part.startswith(x[0]) and len(x[0]) >= 4]
        if pre: return max(pre, key=lambda x: len(x[0]))
        suf = [x for x in words if x[0].endswith(part) and len(part) >= 5]
        if suf: return min(suf, key=lambda x: len(x[0]))
        flex = [x for x in words if x[0].startswith(part) and len(part) >= 5 and len(x[0]) - len(part) <= 2]
        if flex: return min(flex, key=lambda x: len(x[0]))
    return None


def phrase_match(toks: list, i: int, idx: list[tuple[str, str]]):
    """Mehrwortige Zutat („brauner Zucker“) ab Token i: (Treffer, End-Token) oder None."""
    for n in (3, 2):
        if i + n > len(toks): continue
        phrase = " ".join(t.group(0).strip("*").lower() for t in toks[i:i + n])
        hit = next((x for x in idx if x[0] == phrase), None)
        if hit: return hit, toks[i + n - 1]
    return None


def find_doses(text: str, ingredients: list[dict], lint: Lint, where: str, seen_doses: set, original: str | None = None) -> list[dict]:
    idx = ingredient_index(ingredients)
    original = original if original is not None else text
    out = []
    plain = text
    im = re.search(r"\*(?!\*)\(?[^*]+?\)?\*\s*$", plain)  # kursiver Schluss (Warum/Rettung) enthält keine Dosierung
    skip_from = im.start() if im else len(plain)
    for m in DOSE_RE.finditer(plain):
        if m["times"] or m.start() >= skip_from:
            continue
        ahead = re.match(r"(?:[\wäöüÄÖÜß*/-]+,?\s*){1,4}", plain[m.start("words"):])
        if not ahead:
            continue
        toks = list(re.finditer(r"[\wäöüÄÖÜß*/-]+", ahead.group(0)))
        hit, end_tok = None, None
        for i, tok in enumerate(toks):
            if tok.group(0).strip("*").lower() in (DOSE_STOP if i else PREP_STOP):
                break  # „2 EL Lake über die Kresse“, „(2 kg mit Knochen)“: ab hier beginnt etwas anderes
            if i and m["unit"] == "cm" and "," in ahead.group(0)[:tok.start()]:
                break  # „1 cm breite Spalten, 3 Frühlingszwiebeln“: Längenangabe, keine Dosierung
            pm_ = phrase_match(toks, i, idx)
            if pm_:
                hit, end_tok = pm_; break
            cand = tok.group(0).strip("*").lower()
            hit = best_match(cand, idx)
            if hit:
                end_tok = tok; break
        if m["unit"] and m["unit"].lower() in ALIASES:  # „2 Eiweiß steif schlagen, Zucker …“: die Einheit ist die Zutat
            hit = best_match(m["unit"].lower(), idx)
            if not hit: continue
            span_start = m.start("je") if m["je"] else m.start("lo")
            span_end = m.end("unit")
        elif not hit:
            continue
        else:
            span_start = m.start("je") if m["je"] else m.start("lo")
            span_end = m.start("words") + end_tok.end() - (len(end_tok.group(0)) - len(end_tok.group(0).rstrip("*")))
        span = plain[span_start:span_end]
        lo = parse_num(m["lo"]); hi = parse_num(m["hi"]) if m["hi"] else None
        unit = m["unit"] or "Stück"
        if unit == "Prisen": unit = "Prise"
        if unit == "L": unit = "l"
        amount = {"text": span, "value": lo, "unit": unit}
        if hi is not None: amount["max"] = hi
        if m["je"]: amount["per"] = "Pfanne"
        tm = re.search(r"(\d+)\s?×\s?$", plain[:span_start])
        if tm: amount["times"] = int(tm.group(1))
        dose = {"ref": hit[1], "amount": amount}
        if original.count(span) > 1:  # Position im Originaltext (Alternativen-Klammern zählen mit)
            dose["occurrence"] = original.count(span, 0, span_start) + 1
        key = (hit[1], lo, hi)
        article = re.search(r"\b(die|den|das|der|dem)\s+$", plain[:span_start], re.I)
        if key in seen_doses and article:
            dose["reuse"] = True
        seen_doses.add(key)
        out.append(dose)
    # „Lammschulter (2–2,2 kg mit Knochen)“: Menge in der Klammer hinter dem Zutatenwort
    for m in re.finditer(rf"([\wäöüÄÖÜß-]+)\s\((?:ca\.\s?)?(?P<lo>{NUMW})(?:\s?[–-]\s?(?P<hi>{NUMW}))?\s?(?P<unit>{'|'.join(DOSE_UNITS)})\b", plain):
        if m.start() >= skip_from: continue
        bm = best_match(m.group(1).lower(), idx)
        if not bm or any(d["ref"] == bm[1] for d in out): continue
        span = plain[m.start("lo"):m.end("unit")]
        amount = {"text": span, "value": parse_num(m["lo"]), "unit": m["unit"]}
        if m["hi"]: amount["max"] = parse_num(m["hi"])
        dose = {"ref": bm[1], "amount": amount}
        if any(k[0] == bm[1] for k in seen_doses):
            dose["reuse"] = True  # „restlicher Spinat (100 g)“: Aufteilung einer schon dosierten Zutat
        if original.count(span) > 1:
            dose["occurrence"] = original.count(span, 0, m.start("lo")) + 1
        out.append(dose)
    # „insgesamt N Einheit“ → Vervielfacher auf die Dosierung gleicher Einheit
    for m in re.finditer(rf"insgesamt\s+({NUMW})\s?({'|'.join(DOSE_UNITS)})", plain):
        total, unit = parse_num(m.group(1)), m.group(2)
        for d in out:
            a = d["amount"]
            if a.get("unit") == unit and a.get("value") and not a.get("times") and total % a["value"] == 0 and total > a["value"]:
                a["times"] = int(total // a["value"]); break
    # Mengenwörter ohne Zahl
    for qw in QTY_WORDS:
        for m in re.finditer(rf"\b{qw}\s+([\wäöüÄÖÜß-]+)", plain):
            w = m.group(1).lower()
            bm = best_match(w, idx)
            if bm and not any(d["ref"] == bm[1] for d in out):
                out.append({"ref": bm[1], "amount": {"text": m.group(0)}})
    return out


# ------------------------------------------------------------------ Komponenten-Label → Produkt
def product_from_label(name: str, paren: str | None) -> tuple[dict, str | None]:
    prod = {"id": slugify(name), "name": name}
    phase = None
    if paren:
        hold, storage = {}, {}
        low = paren.lower()
        if m := re.search(rf"bis ({NUMW})\s?(Tage|Tag|h|Std\.|Min\.)\s+vorher", paren):
            v, u = parse_num(m.group(1)), m.group(2)
            hold["max"] = f"P{int(v)}D" if u.startswith("Tag") else iso(v, u)
        if "ideal am vortag" in low: hold["ideal"] = "P1D"
        if m := re.search(rf"hält (?:bis )?({NUMW})(?:\s?[–-]\s?({NUMW}))?\s?(h|Std\.|Min\.|Tage)", paren):
            v, u = parse_num(m.group(1)), m.group(3)
            if m.group(2):
                hold["min"] = iso(v, u); hold["max"] = iso(parse_num(m.group(2)), u)
            else:
                hold["max"] = f"P{int(v)}D" if u == "Tage" else iso(v, u)
        if m := re.search(rf"(?:mind\.|mindestens)\s+({NUMW})\s?(h|Std\.|Min\.)", paren):
            hold["min"] = iso(parse_num(m.group(1)), m.group(2))
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
    seen_doses: set = set()

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
        annotate_text(cur_step, txt, ingredients, lint, where, seen_doses)
        if cur_meta:
            cur_step["meta"] = f"*{cur_meta}*"
            meta = parse_meta(cur_meta, lint, where)
            cur_step["_meta"] = meta
            for k in ("parallel", "attention", "claims", "endCondition", "technique", "only"):
                if k in meta: cur_step[k] = meta[k]
            if meta.get("_produces") and cur_task:
                cur_task["produces"] = [product_from_label(meta["_produces"], meta.get("_hold"))[0]]
            elif meta.get("_hold") and cur_task and cur_task.get("produces"):
                prod, _ = product_from_label(cur_task["produces"][0]["name"], meta["_hold"])
                cur_task["produces"][0].update({k: v for k, v in prod.items() if k in ("hold", "storage")})
        if "duration" not in cur_step:
            lint.add(where, "keine Dauer in der Überschrift")
        if "attention" not in cur_step:
            heat = any(c["resource"] in ("hob", "oven", "grill") for c in cur_step.get("claims", []))
            watch = re.search(r"köcheln|kochen|schmoren|reduzieren|einkochen|rösten|backen|ziehen lassen|garen|blanchieren|sprudeln", txt, re.I)
            cur_step["attention"] = "attended" if heat and watch else "active"
        # Überschrift-Dauer als Timer, wenn der Schritt nebenher läuft und der Text keinen Timer nennt
        if cur_step.get("duration") and not cur_step.get("timers") and (cur_step["attention"] != "active" or cur_step.get("parallel")):
            d = {k: v for k, v in cur_step["duration"].items() if k in ("min", "max", "typical")}
            cur_step["timers"] = [{"label": cur_step["title"], "duration": d, "text": cur_step["duration"].get("source", "")}]
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
            local = slugify(sm["title"])
            cur_step = {"id": f"{course_id}-{local}" if course_id else local, "label": sm["n"], "heading": stripped, "title": sm["title"].strip()}
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
            cur_task = new_task(h3.group(1).strip(), stripped, None)
            k = i + 1
            while k < len(lines) and not lines[k].strip(): k += 1
            if k < len(lines) and (om := re.match(r"^\*nur\s+(.+?)\*$", lines[k].strip())):  # Abschnitt gilt nur für diese Wahl
                if refs := lint.only(om.group(1), f"{scope}/{cur_task['name']}"): cur_task["only"] = refs
                cur_task["heading"] += "\n\n" + lines[k].strip()
                i = k
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
    prefix = f"{course_id}-" if course_id else ""
    local = {st["id"].removeprefix(prefix): st["id"] for t in tasks for st in t["steps"]}
    slugs = list(local.values())

    class _ByTitle(dict):
        """Exakter lokaler Slug oder eindeutiger Präfix („nach Karamell“ → karamell-der-entscheidende-schritt)."""
        def get(self, key, default=None):
            k = slugify(key) if key else key
            if k in local:
                return local[k]
            hits = [v for x, v in local.items() if x.startswith(k + "-") or x.startswith(k)]
            return hits[0] if len(hits) == 1 else default

    by_title = _ByTitle()
    ids = set(slugs)
    if len(ids) < sum(len(t["steps"]) for t in tasks):
        lint.add(scope, "doppelte Schritt-Titel (Slugs kollidieren)")
    prod_names = [(p["name"], t) for t in tasks for p in t.get("produces", [])]
    for t in tasks:
        for st in t["steps"]:
            meta = st.pop("_meta", {})
            at = meta.get("_after_titles")
            if at is not None:
                refs, i = [], 0
                while i < len(at):
                    for n in range(len(at) - i, 0, -1):
                        title = ", ".join(at[i:i + n])
                        sid = by_title.get(slugify(title)) or by_title.get(title.lower())
                        if sid: break
                    if sid: refs.append(f"step:{sid}")
                    else: lint.add(f"{scope}/Schritt {st['label']}", f"„nach {at[i]}“: kein Schritt mit diesem Titel")
                    i += n
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
PHASE_RE = [(r"^T-(\d)$", lambda m: {"day": -int(m.group(1))}), (r"^(\d) Tage vorher$", lambda m: {"day": -int(m.group(1))}), (r"^Saison", lambda m: {"day": -60}), (r"^Vortag", lambda m: {"day": -1}), (r"^Vorabend", lambda m: {"day": -1, "part": "evening"}),
            (r"^Vormittag", lambda m: {"day": 0, "part": "morning"}), (r"^Nachmittag", lambda m: {"day": 0, "part": "afternoon"}),
            (r"^(Am )?Abend", lambda m: {"day": 0, "part": "evening"}), (r"^Am Tag", lambda m: {"day": 0}),
            (r"^Gang (\d) \((\+?)(\d+):(\d+)\)$", lambda m: {"day": 0, "part": "service", "at": f"{'+' if m.group(2) else ''}PT{int(m.group(3))}H{int(m.group(4))}M".replace("PT0H", "PT").replace("H0M", "H")})]


_WB = r"(?<![\wäöüÄÖÜß])%s(?![\wäöüÄÖÜß])"
ENTRY_ONLY = re.compile(r"^\*nur\s+([^*]+)\*\s*")
CLOCK_PHASE = re.compile(r"^(?P<label>(?P<h>\d{1,2}):(?P<m>\d{2})\s?Uhr(?:\s*\((?P<off>[^)]*)\))?(?:\s+—\s+(?P<event>[^:]+?))?):\s+(?P<rest>.*)$")


def clock_phase(cm: re.Match, anchor: dict | None, lint: Lint) -> dict | None:
    """„17:30 Uhr (1,5h vorher)“, „19:15 Uhr — Nach dem Amuse“ → Phase am Service-Tag, Lage relativ zum Anker
    (Uhrzeit im Zeitplan-Satz „… um 19:00 Uhr“). Die Klammer ist Kontrolle, keine Quelle."""
    clock = f"{int(cm['h']):02d}:{cm['m']}"
    if anchor is None:
        lint.add("Zeitplan", f"Uhrzeit-Phase '{cm['label']}' ohne Anker („Dinner um 19:00 Uhr“)"); return None
    ah, amin = map(int, anchor["time"].split(":"))
    mins = int(cm["h"]) * 60 + int(cm["m"]) - (ah * 60 + amin)
    if cm["off"]:
        om = re.match(r"^(?:ca\.\s?)?([\d,]+)\s?(h|min)\s+vorher$", cm["off"].strip())
        if om and round(float(om.group(1).replace(",", ".")) * (60 if om.group(2) == "h" else 1)) != -mins:
            lint.add("Zeitplan", f"'{cm['label']}': Klammer passt nicht zu {anchor['time']} Uhr")
        elif not om:
            lint.add("Zeitplan", f"'{cm['label']}': Klammer nicht erkannt")
    sign = "-" if mins < 0 else ("+" if mins > 0 else "")
    spec = {"day": 0, "part": "service", "at": sign + iso(abs(mins), "Min."), "clock": clock}
    if cm["event"]: spec["event"] = cm["event"].strip()
    return spec


def match_entry(e: dict, tasks_all: list[tuple[str | None, dict]], lint: Lint) -> None:
    """Zeitplan-Eintrag → Schritte/Tasks per Namen. Mehrwortige Schritt-Titel zählen als Phrase im Text
    (längste zuerst, Treffer werden ausgeblendet); danach Segmente (an „, “, „ · “, „: “, „ — “, „; “ und „ und “,
    Klammern entfernt): Task-Name = Segment, Ein-Wort-Titel = Segment, letztes Wort des Segments
    („Parfait einfrieren“) oder Segment-Anfang vor einer Zahl („Durchwärmen 12–18 Min.“). Alle Treffer eines
    Eintrags liegen im selben Gang: Gang-Phase gibt ihn vor, sonst der erste Treffer; mehrdeutige Titel
    ohne Gang bleiben Text (Hinweis); eindeutige Namen dürfen aus jedem Gang kommen."""
    phase_course = e["phase"] if e["phase"].startswith("gang-") else None
    course = phase_course
    steps = [(cid, st) for cid, t in tasks_all for st in t["steps"]]
    hits_s: list[str] = []; hits_t: list[str] = []
    masked = ws_key(e["text"]).replace("**", "")

    def take(cands: list[tuple[str | None, str]], kind: str, what: str) -> None:
        nonlocal course
        if len({cid for cid, _ in cands}) > 1:  # Name in mehreren Gängen → nur der Gang des Eintrags
            cands = [(cid, x) for cid, x in cands if cid == course]
            if not cands:
                lint.add("Zeitplan", f"„{what}“ gibt es in mehreren Gängen — Eintrag '{e['text'][:40]}' bleibt Text"); return
        if not cands: return
        course = course or cands[0][0]
        for _, x in cands:
            lst = hits_s if kind == "step" else hits_t
            if x not in lst: lst.append(x)

    for cid, st in sorted(steps, key=lambda x: -len(x[1]["title"])):
        title = st["title"]
        if len(title.split()) < 2: continue
        same = [(c2, s2["id"]) for c2, s2 in steps if s2["title"].lower() == title.lower()]
        m = re.search(_WB % re.escape(title), masked, re.I)
        if m:
            take(same, "step", title)
            masked = masked[:m.start()] + "§" + masked[m.end():]  # Rest-Segment („Consommé §“) trifft keine Komponente
    segs: list[str] = []
    for seg in re.split(r",\s|\s·\s|:\s|\s—\s|;\s|\s→\s", re.sub(r"\s*\([^)]*\)", "", masked)):
        seg = seg.strip(" .")
        if not seg: continue
        segs.append(seg); segs += [x.strip() for x in re.split(r"\sund\s", seg) if x.strip() and x.strip() != seg]
    for seg in segs:
        if "§" in seg: continue
        low = seg.lower()
        take([(cid, t["id"]) for cid, t in tasks_all if t["id"] != "main" and t["name"].lower() == low], "task", seg)
        take([(cid, st["id"]) for cid, st in steps if len(st["title"].split()) == 1 and len(st["title"]) > 3
              and (low == st["title"].lower() or low.endswith(" " + st["title"].lower())
                   or re.match(re.escape(st["title"].lower()) + r"\s\d", low))], "step", seg)
    if hits_s: e["steps"] = sorted(hits_s)
    if hits_t: e["tasks"] = sorted(hits_t)
    if course: e["course"] = course


def parse_schedule(title: str, text: str, tasks_all: list[tuple[str | None, dict]], lint: Lint) -> tuple[dict, str | None]:
    phases, entries, note = [], [], None
    seen = {}
    bullets: list[str] = []
    in_note = False
    sched_only = None
    if om := re.search(r"^\*nur\s+(.+?)\*\s*$", text, re.M):  # ganzer Zeitplan gilt nur für diese Wahl
        sched_only = lint.only(om.group(1), "Zeitplan")
    for line in text.split("\n"):
        if line.startswith("- "): bullets.append(line[2:]); in_note = False
        elif line.startswith("  ") and bullets: bullets[-1] += " " + line.strip()
        elif line.startswith("**") and ":**" in line and len(line) > 20: note = (note + "\n\n" if note else "") + line; in_note = True
        elif in_note and line.strip() and not line.startswith("|"): note += "\n" + line
        elif ITALIC_RE.match(line.strip()) and not line.strip().startswith("*nur ") and not re.search(r"\bum \d{1,2}:\d{2} Uhr", line):
            note = (note + "\n\n" if note else "") + line.strip()  # kursiver Hinweis zum Zeitplan („Variante B: …“)
        elif line.startswith("|"):
            in_note = False
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 2 and re.match(r"^T[−-]", cells[0]):
                tm = re.match(r"^T[−-](\d+)(?::(\d+))?", cells[0])
                mins = int(tm.group(1)) * (60 if tm.group(2) else 1) + int(tm.group(2) or 0)
                pid = "kochtag"
                if pid not in seen:
                    seen[pid] = True; phases.append({"id": pid, "label": "Kochtag", "day": 0, "part": "service"})
                entries.append({"phase": pid, "text": cells[1], "at": {"ref": "anchor", "offset": f"-PT{mins}M"}, "source": cells[0]})
        else:
            in_note = False
    anchor = None
    if am := re.search(r"([\wäöüÄÖÜß-]+) um (\d{1,2}):(\d{2}) Uhr", text):
        anchor = {"label": am.group(1), "time": f"{int(am.group(2)):02d}:{am.group(3)}"}
    for b in bullets:
        if cm := CLOCK_PHASE.match(b):
            label, rest = cm["label"].strip(), cm["rest"]
            spec = clock_phase(cm, anchor, lint)
            if spec is None: continue
            pid = "uhr-" + spec["clock"].replace(":", "-")
            if pid not in seen:
                seen[pid] = True
                phases.append({"id": pid, "label": label, **spec})
            for seg in re.split(r"\s·\s", rest.strip()):
                if seg.strip(): entries.append({"phase": pid, "text": seg.strip()})
            continue
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
    for e in entries:
        if om := ENTRY_ONLY.match(e["text"]):  # „*nur Einfrieren, Kombi* Einfrieren: …“
            if refs := lint.only(om.group(1), "Zeitplan"): e["only"] = refs
            e["text"] = e["text"][om.end():].strip()
        match_entry(e, tasks_all, lint)
        if m := re.search(rf"\(?(?:\\?~)?({RANGE})\s?({DUR_UNITS})\s+vor dem Gang\)?", e["text"]):
            d = duration_range(m.group(1) + " " + m.group(2))
            e["at"] = {"ref": f"course:{e.get('course', 'gang-1')}:serve", "offset": "-" + (d.get("typical") or d["max"])}
            e["source"] = m.group(0).strip("()")
    sched = {"id": slugify(title), "label": title, "phases": phases, "entries": entries}
    if sched_only: sched["only"] = sched_only
    if anchor: sched["_anchor"] = anchor
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
    lint.dims = V.parse_declaration(head)
    lint.alt = V.alt_pattern(lint.dims)
    if lint.dims: recipe["variants"] = lint.dims
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
        anchor = sched.pop("_anchor", None)
        if anchor and not is_menu:
            sched["anchorOverride"] = {"time": anchor["time"]}
        if is_menu and anchor:
            # Uhrzeit-Zeitplan: ein Gang wird in der letzten Uhrzeit-Phase serviert, die Einträge von ihm hat
            clock = {p["id"]: p for p in sched["phases"] if p.get("clock")}
            last = {}
            for e in sched["entries"]:
                if e["phase"] in clock and e.get("course"): last[e["course"]] = clock[e["phase"]]
            names = {c["id"]: c["title"] for s in sections if s.get("type") == "courses" for c in s["courses"]}
            recipe["courses"] = [{"ref": cid, "n": int(cid[5:]), "name": re.sub(r"^\d+\.\s*", "", names[cid]), "serve": last[cid]["at"], "source": last[cid]["label"]}
                                 for cid in names if cid in last]
            recipe["anchor"] = anchor
            recipe["resources"] = [dict(r) for r in DEFAULT_RESOURCES]
        elif is_menu:
            recipe["courses"] = [{"ref": p["id"], "n": int(p["id"][5:]), "name": p["label"].split(" (")[0], "serve": p["at"], "source": p["label"]}
                                 for p in sched["phases"] if p["id"].startswith("gang-")]
            recipe["anchor"] = {"label": "Gang 1 serviert"}
            recipe["resources"] = [dict(r) for r in DEFAULT_RESOURCES]
    if is_menu and not recipe.get("courses"):
        recipe["courses"] = [{"ref": c["id"], "n": int(c["id"][5:]), "name": c["title"], "serve": "PT0M"} for s in sections if s.get("type") == "courses" for c in s["courses"]]
        recipe["anchor"] = {"label": "Service"}
    recipe["sections"] = sections
    # Zutaten ohne Dosierung
    used = {d["ref"] for _, t in tasks_all for st in t["steps"] for si in st["ingredients"] for d in all_doses(si)}
    unused = [i["id"] for i in ingredients if i["id"] not in used]
    if unused: lint.add("Einkaufsliste", "Zutaten ohne Dosierung in Schritten: " + ", ".join(unused))
    return recipe, lint
