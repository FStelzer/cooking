"""Konvertierung menues/menue-november.md → schema/beispiele/menue-november.json.

Verbatim-Teile (Prosa, Schritt-Texte, Zeitplan, To-do) werden aus der Quelle
geschnitten; die Modellierung (Tasks, Produkte, Dosierungen, Annotationen, Kanten,
Zeitplan-Zuordnung) steht hier als Hand-Annotation. Aufruf aus dem Repo-Root:
    python3 tools/convert/menue_november.py && python3 -m tools.recipes.cli derive schema/beispiele/menue-november.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.recipes.util import sentence_prefixes, split_h2  # noqa: E402

SRC = (ROOT / "menues/menue-november.md").read_text(encoding="utf-8")
H2 = dict(split_h2(SRC))


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


def course_blocks() -> dict[int, tuple[str, str]]:
    out = {}
    for g in re.split(r"^(?=### )", H2["Rezepte"], flags=re.M):
        if not g.startswith("### "):
            continue
        lines = g.split("\n")
        body = re.sub(r"\n+---\s*$", "", "\n".join(lines[1:]).strip("\n"))
        out[int(lines[0][4:5])] = (lines[0][4:].strip(), body)
    return out


class Course:
    """Zerlegt einen ###-Block in Absätze, Labels und nummerierte Schritte (verbatim)."""

    def __init__(self, n: int):
        self.title, body = course_blocks()[n]
        self.P = paragraphs(body)
        self.steps: dict[int, str] = {}
        for pp in self.P:
            if not re.match(r"^\d+\. ", pp):
                continue
            cur = None
            for line in pp.split("\n"):
                m = re.match(r"^(\d+)\. (.*)$", line)
                if m:
                    cur = int(m.group(1)); self.steps[cur] = [m.group(2)]
                else:
                    self.steps[cur].append(line.strip())
        self.steps = {k: " ".join(x for x in v if x) for k, v in self.steps.items()}
        assert sorted(self.steps) == list(range(1, len(self.steps) + 1)), (n, sorted(self.steps))

    def find(self, prefix: str) -> str:
        return next(pp for pp in self.P if pp.startswith(prefix))

    def todo(self, prefix: str = "**Offen") -> dict:
        lines = self.find(prefix).split("\n")
        items = []
        for line in lines[1:]:
            m = re.match(r"^- \[([ x])\] (.*)$", line)
            if m:
                items.append({"text": m.group(2), "checked": m.group(1) == "x"})
            else:
                items[-1]["text"] += " " + line.strip()
        return {"intro": lines[0], "items": items}

    def step(self, n: int, id: str, action_n: int = 1, **kw) -> dict:
        text = self.steps[n]
        pre = sentence_prefixes(text)
        st = {"id": id, "label": str(n), "text": text, "action": pre[min(action_n, len(pre)) - 1], "ingredients": []}
        st.update(kw)
        return st

    def md(self, prefix: str, title: str, tags: list[str]) -> dict:
        return {"type": "markdown", "title": title, "level": "bold", "tags": tags, "markdown": self.find(prefix)}

    def anrichten(self, id: str, consumes: list[str], after: list[str], **kw) -> dict:
        p = self.find("**Anrichten:**").replace("**Anrichten:** ", "", 1)
        return {"id": id, "name": "Anrichten", "heading": "**Anrichten:**", "service": True, "consumes": consumes,
                "steps": [{"id": id, "label": "Anrichten", "text": p, "action": sentence_prefixes(p)[0],
                           "attention": "active", "duration": D(typical="PT3M", estimated=True), "after": after, "ingredients": [], **kw}]}


def A(text, value=None, mx=None, unit=None, **kw):
    a = {"text": text}
    if value is not None: a["value"] = value
    if mx is not None: a["max"] = mx
    if unit: a["unit"] = unit
    a.update(kw)
    return a


def SI(ref, amount, **kw):
    return {"ref": ref, "amount": amount, **kw}


def D(**kw):
    return kw


def T(min=None, max=None, typical=None, label="", text=""):
    d = {k: v for k, v in (("min", min), ("max", max), ("typical", typical)) if v}
    return {"label": label, "duration": d, "text": text}


def PROD(id, name, place, hold=None, **storage):
    p = {"id": id, "name": name, "storage": {"place": place, **storage}}
    if hold:
        p["hold"] = hold
    return p


HOB = lambda n=1: {"resource": "hob", "units": n}
OVEN = lambda t, **kw: {"resource": "oven", "temp": t, **kw}

# =============================================================== Gang 1
g1 = Course(1)
tasks1 = [
 {"id": "saison", "name": "Saison-Teil: Tomaten klären", "heading": g1.find("**Saison-Teil"), "phaseHint": "Saison-Teil (Aug/Sep), erledigt 09/2026",
  "produces": [PROD("pueree-block", "Gesalzenes Rohpüree, gefroren (Weg A)", "freezer", {"max": None, "source": "liegen seit 09/2026 im Gefrierfach"}),
               PROD("tomatenwasser-klar", "Klares Tomatenwasser, gefroren (Weg B)", "freezer", {"max": None, "source": "liegen seit 09/2026 im Gefrierfach"})],
  "steps": [
   g1.step(1, "tomaten-salzen", attention="active", duration=D(typical="PT15M", estimated=True), after=[],
           ingredients=[SI("salz", A("7 g Salz", 7, unit="g"))]),
   g1.step(2, "tomaten-mixen", attention="active", limits=["Nur **kurz pulsierend** mixen — grob-pulpig, nicht fein!"],
           why="Zu feines Mixen zermahlt die Kerne (Bitterstoffe) und erzeugt Trübstoffe, die durchs Tuch gehen."),
   g1.step(3, "weg-a-einfrieren", attention="active", why="Eiskristalle schließen die Zellen auf: kristallklarer + höhere Ausbeute"),
   g1.step(4, "weg-b-abtropfen", attention="passive", after=["step:tomaten-mixen"], timers=[T("PT12H", label="Abtropfen", text="über Nacht (12 h)")],
           limits=["**nicht pressen, nicht rühren** (wird trüb)"], cues=["Ausbeute \\~300–400 ml/kg"]),
  ]},
 {"id": "tomatenwasser-auftauen", "name": "Tomatenwasser klären (Drip-Thaw) / auftauen", "heading": g1.find("**Im November"), "phaseHint": "2 Tage vor dem Abend (Weg A) bzw. Vortag (Weg B)",
  "consumes": ["product:pueree-block", "product:tomatenwasser-klar"],
  "produces": [PROD("tomatenwasser", "Klares Tomatenwasser, aufgetaut", "fridge", {"max": None, "source": "im Kühlschrank 24–48 h auftauen lassen"})],
  "steps": [g1.step(5, "klaeren", attention="passive", after=[], duration=D(min="P1D", max="P2D", source="24–48 h"),
                    start={"ref": "course:gang-1:serve", "offset": {"typical": "-P2D", "source": "2 Tage vor dem Abend"}},
                    timers=[T("P1D", "P2D", label="Drip-Thaw", text="24–48 h")], limits=["Nicht drücken.", "**nicht schütteln**"],
                    cues=["es tropft kristallklares Tomatenwasser ab"], rescue="notfalls durch Kaffeefilter nachfiltern")]},
 {"id": "tomatenwasser-wuerzen", "name": "Grundwürzung", "heading": g1.find("**Am Abend:**"), "phaseHint": "1–2 h vor Service", "consumes": ["product:tomatenwasser"],
  "produces": [PROD("tomatenwasser-gewuerzt", "Tomatenwasser gewürzt, kalt ziehend", "fridge", {"min": "PT1H", "max": "PT2H", "source": "Grundwürzung **1–2 h vor Service**"})],
  "steps": [
   g1.step(6, "grundwuerzung", attention="active", duration=D(typical="PT5M", estimated=True),
           start={"ref": "course:gang-1:serve", "offset": {"min": "-PT2H", "max": "-PT1H", "source": "1–2 h vor Service"}},
           ingredients=[SI("tomatenwasser", A("350 ml Tomatenwasser", 350, unit="ml", approx=True)), SI("worcestershire", A("6–8 Tropfen Worcestershire", 6, 8, "Tropfen")),
                        SI("selleriesalz", A("2 Prisen Selleriesalz", 2, unit="Prisen")), SI("pfeffer-weiss", A("1 Umdrehung weißer Pfeffer", 1, unit="Umdrehung"))],
           limits=["**tropfenweise — trübt!**", "**Vorher \\~60 ml für die Kinder-Portion abzweigen**"], why="dabei setzen sich die Worcestershire-Schwebstoffe am Boden ab"),
   g1.step(7, "abschmecken", attention="active", limits=["**Bei Serviertemperatur abschmecken, nie bei Raumtemperatur:**"],
           why="Kälte dämpft Umami und Salz-Wahrnehmung deutlich", cues=["Wirkt es ungewürzt fad/blass: normal, erst würzen, dann urteilen."]),
  ]},
 {"id": "concasse", "name": "Concassé", "phaseHint": "Nachmittag", "produces": [PROD("concasse", "Tomaten-Concassé, ungesalzen", "fridge", {"max": None, "source": "**Erst kurz vor dem Servieren** mit 1 Prise Salz würzen"})],
  "steps": [g1.step(8, "concasse", attention="active", after=[], duration=D(typical="PT15M", estimated=True),
                    ingredients=[SI("cherrytomaten", A("100 g Cherry-/Datteltomaten", 100, unit="g")), SI("salz", A("1 Prise Salz", 1, unit="Prise"))],
                    timers=[T("PT10S", "PT15S", label="Blanchieren", text="10–15 Sek.")], limits=["**Erst kurz vor dem Servieren** mit 1 Prise Salz würzen (zieht sonst Wasser)."], claims=[HOB()])]},
 {"id": "amuse-service", "name": "Tomatenwasser anrichten", "service": True, "consumes": ["product:tomatenwasser-gewuerzt", "product:concasse"],
  "steps": [
   g1.step(9, "limette", attention="active", after=["step:abschmecken"], duration=D(typical="PT2M", estimated=True),
           ingredients=[SI("limetten", A("10 ml Limettensaft", 10, unit="ml"))], limits=["**vorsichtig oben einrühren** (das abgesetzte Sediment am Boden nicht aufwirbeln)"],
           why="Bún-chả-Learning: Säure dominiert schnell — vorsichtig"),
   g1.step(10, "anrichten-1", attention="active", after=["step:limette", "step:concasse"], duration=D(typical="PT5M", estimated=True),
           ingredients=[SI("chilioel", A("2–3 Tropfen mildes Chiliöl", 2, 3, "Tropfen"))], limits=["kein Eis — verwässert", "vom Sediment weg, der letzte Schluck bleibt im Gefäß"],
           cues=["schwimmt als glänzende Perlen — Schärfe kurz und präzise"], technique="technik/mini-projekte.md#kraeuteroel"),
  ]},
]
gang1 = {"id": "gang-1", "kind": "course", "title": g1.title, "intro": g1.find("*Saison-Teil"), "sections": [
    {"type": "tasks", "title": "Zubereitung", "tasks": tasks1},
    g1.md("**Kind (3 J.):**", "Kind (3 J.)", ["kind"]), g1.md("> **Profi-Tipps:**", "Profi-Tipps", ["profi-tipps"]),
    {"type": "todo", "title": "Offen (Testlauf)", **g1.todo()}]}

# =============================================================== Gang 2
g2 = Course(2)
tasks2 = [
 {"id": "mango-gel", "name": "Mango-Gel", "heading": g2.find("**Mango-Gel"), "phaseHint": "bis 2 Tage vorher, ideal am Vortag",
  "produces": [PROD("mango-gel", "Mango-Gel in der Spritzflasche", "fridge", {"max": "P2D", "ideal": "P1D", "source": "bis 2 Tage vorher, ideal am Vortag — Agar nässt ab Tag 3"}, note="Spritzflasche; vor dem Anrichten kurz durchschütteln")],
  "steps": [
   g2.step(1, "mango-kochen", attention="attended", duration=D(min="PT5M", max="PT10M", source="5–10 Min."), timers=[T("PT5M", "PT10M", label="Mango weich kochen", text="5–10 Min.")],
           ingredients=[SI("mango", A("1 reifer Mango", 1, unit="Stück")), SI("zucker", A("1–2 EL Zucker", 1, 2, "EL")), SI("ingwer", A("5 g fein geriebenem Ingwer", 5, unit="g")), SI("wasser", A("2 EL Wasser", 2, unit="EL"))],
           cues=["durch das feine Sieb streichen → \\~250 ml Masse"], limits=["**Kein Chili** — der Gel-Rest wird Kinder-Dessert (s. unten)."], claims=[HOB()]),
   g2.step(2, "agar-einmixen", attention="active", duration=D(min="PT4M", max="PT6M", estimated=True), timers=[T("PT2M", "PT3M", label="Sprudelnd kochen", text="2–3 Min.")],
           ingredients=[SI("agar", A("2 g Agar-Agar", 2, unit="g"))], equipment=["Feinwaage", "Stabmixer"], limits=["±0,5 g verändert die Textur deutlich!", "in die **kalte** Masse einmixen"], why="volle Hydratation", claims=[HOB()]),
   g2.step(3, "saeure-einruehren", attention="active", ingredients=[SI("limetten", A("½ Limette", 0.5, unit="Stück")), SI("salz", A("1 Prise Salz", 1, unit="Prise"))],
           limits=["**Säure erst nach dem Kochen**"], why="mitgekocht schwächt sie das Agar-Gel", cues=["Das Gel soll solo süß-sauer-hell schmecken, nicht bonbonsüß."]),
   g2.step(4, "gel-fest-und-mixen", attention="passive", duration=D(min="PT1H", max="PT2H", source="1–2 h"), timers=[T("PT1H", "PT2H", label="Gel fest werden", text="1–2 h"), T("PT1M", "PT3M", label="Glatt mixen", text="1–3 Min.")],
           rescue="Fallback ohne Agar: Masse dick einkochen und glatt mixen — Chutney-Nocken statt präziser Punkte.", equipment=["Spritzflasche"]),
  ]},
 {"id": "walnuss-crumble", "name": "Walnusscrumble", "heading": g2.find("**Walnusscrumble"), "phaseHint": "Vortag",
  "produces": [PROD("walnuss-crumble", "Walnusscrumble", "room", {"min": "PT30M", "max": None, "source": "Komplett auskühlen lassen"}, covered=True, note="luftdicht bei Raumtemperatur — nicht im Kühlschrank (Kondensfeuchte)")],
  "steps": [g2.step(5, "crumble-roesten", attention="attended", duration=D(min="PT10M", max="PT15M", estimated=True), after=[],
                    ingredients=[SI("walnuesse", A("50 g Walnüsse", 50, unit="g")), SI("butter", A("20 g Butter", 20, unit="g")), SI("panko", A("20 g Panko", 20, unit="g")), SI("honig", A("½ TL Honig", 0.5, unit="TL")), SI("salz", A("1 Prise Salz", 1, unit="Prise"))],
                    temps=[{"kind": "ofen", "value": 160, "text": "160 °C"}], claims=[OVEN(160, alt=[HOB()])], cues=["goldbraun und **vollständig trocken**"], limits=["nicht im Kühlschrank (Kondensfeuchte)"])]},
 {"id": "pralinen-formen", "name": "Ziegenkäse-Pralinen formen", "heading": g2.find("**Ziegenkäse-Pralinen"), "phaseHint": "Vortag formen, Wälzen erst am Abend",
  "produces": [PROD("pralinen-roh", "Pralinen, ungewälzt", "fridge", {"min": "PT10M", "max": "P1D", "source": "10–15 Min. anfrieren macht das Rollen sauber. Kalt lagern."}),
               PROD("waelzmischung", "Wälzmischung (Walnuss + Kräuter)", "fridge", {"max": "P1D", "source": "Wälzmischung bereitstellen"}, covered=True)],
  "steps": [
   g2.step(6, "pralinen-kneten", attention="active", duration=D(typical="PT10M", estimated=True), after=[], timers=[T("PT10M", "PT15M", label="Pralinen anfrieren", text="10–15 Min.")],
           ingredients=[SI("ziegenfrischkaese", A("120 g", 120, unit="g")), SI("honig", A("1 TL Honig", 1, unit="TL")), SI("pfeffer-weiss", A("Pfeffer"))],
           limits=["nicht mehr — Masse wird klebrig, Süße kommt am Teller vom Gel"], why="10–15 Min. anfrieren macht das Rollen sauber."),
   g2.step(7, "waelzmischung", attention="active", duration=D(typical="PT5M", estimated=True), ingredients=[SI("walnuesse", A("30 g Walnüsse", 30, unit="g")), SI("kraeuter", A("2 EL fein gehackte Kräuter", 2, unit="EL"))]),
  ]},
 {"id": "pralinen-waelzen", "name": "Pralinen wälzen", "phaseHint": "am Abend", "consumes": ["product:pralinen-roh", "product:waelzmischung"],
  "produces": [PROD("pralinen-gewaelzt", "Pralinen gewälzt, temperiert", "room", {"max": "PT30M", "source": "Erst ≤30 Min. vor dem Anrichten"})],
  "steps": [g2.step(8, "waelzen", attention="active", duration=D(typical="PT5M", estimated=True), after=[],
                    start={"ref": "task:anrichten-2:start", "offset": {"min": "-PT30M", "max": "PT0M", "source": "Erst ≤30 Min. vor dem Anrichten"}},
                    why="Panade zieht sonst Feuchtigkeit", rescue="Noch sicherer: gar nicht wälzen, Praline aufs Crumble-Bett setzen und Wälzmischung darüber streuen.")]},
 {"id": "kaisergranat-vorbereiten", "name": "Kaisergranat vorbereiten", "heading": g2.find("**Kaisergranat vorbereiten"), "phaseHint": "Vortag auftauen, am Tag auslösen",
  "produces": [PROD("kaisergranat-angetrocknet", "Schwänze ausgelöst, angetrocknet", "fridge", {"min": "PT1H", "max": "PT2H", "source": "1–2 h offen auf Gitter/Küchenpapier im Kühlschrank antrocknen"}, covered=False)],
  "steps": [
   g2.step(9, "auftauen", attention="passive", after=[], duration=D(min="PT8H", max="PT14H", source="über Nacht"), timers=[T("PT8H", "PT14H", label="Auftauen", text="über Nacht")],
           ingredients=[SI("kaisergranat", A("12 Kaisergranat", 12, unit="Stück"))], limits=["nie warm, nie im Wasser — laugt aus"]),
   g2.step(10, "ausloesen", 2, attention="active", duration=D(typical="PT20M", source="\\~20 Min. Schwänze auslösen"), equipment=["Küchenschere"], why="beste Basis für eine Bisque"),
   g2.step(11, "trockentupfen", attention="active", duration=D(typical="PT5M", estimated=True), why="Feuchtigkeit ist der Feind der Kruste, TK-Ware zieht besonders Wasser"),
  ]},
 {"id": "beurre-blanc", "name": "Verjus-Limetten-Beurre-blanc", "heading": g2.find("**Verjus-Limetten-Beurre-blanc"), "phaseHint": "\\~20 Min. vor dem Gang",
  "produces": [PROD("beurre-blanc", "Beurre blanc (ohne Limette), warm", "warm", {"max": "PT2H", "source": "hält bis 2 h"}, temp={"min": 50, "max": 55}, note="Wasserbad oder vorgewärmte Thermoskanne")],
  "steps": [
   g2.step(12, "reduktion", attention="attended", duration=D(min="PT6M", max="PT8M", estimated=True), after=[],
           ingredients=[SI("schalotten", A("2 Schalotten", 2, unit="Stück")), SI("verjus", A("110 ml Verjus", 110, unit="ml")), SI("weissweinessig", A("25 ml Weißweinessig", 25, unit="ml"))],
           cues=["auf \\~3 EL sirupös einreduzieren"], why="Verjus ersetzt Weißwein + Noilly Prat 1:1 — gleiche Säure- und Fruchtrolle, kein Alkohol.",
           rescue="Fallback ohne Verjus: 60 ml Weißweinessig + 60 ml Wasser + 1 TL Zucker.", claims=[HOB()]),
   g2.step(13, "sahne", attention="attended", duration=D(typical="PT1M", estimated=True), ingredients=[SI("sahne", A("2 EL Sahne", 2, unit="EL"))], why="stabilisiert die Emulsion spürbar", technique="technik/mini-projekte.md#beurre-blanc", claims=[HOB()]),
   g2.step(14, "montieren", attention="active", duration=D(min="PT5M", max="PT7M", estimated=True), ingredients=[SI("butter", A("170 g eiskalte Butter", 170, unit="g"))],
           temps=[{"kind": "max", "value": 58, "text": "Nie über \\~58 °C"}], limits=["**Nie über \\~58 °C, nie kochen**"], cues=["nächstes Stück erst, wenn das vorige emulgiert ist"], claims=[HOB()], equipment=["Thermometer", "feines Sieb"]),
   g2.step(15, "warmhalten-limette", attention="attended", ingredients=[SI("limetten", A("1 Limette", 1, unit="Stück"))], temps=[{"kind": "halten", "min": 50, "max": 55, "text": "50–55 °C"}],
           limits=["**Erst unmittelbar vor dem Anrichten**"], why="Zitrus-Öle sind hitzeflüchtig, und Limette ist aggressiver als Zitrone", rescue="Gebrochen? → Emulsions-Notfall in `technik/abschmecken.md`.", technique="technik/abschmecken.md#emulsions-notfall"),
  ]},
 {"id": "braten", "name": "Kaisergranat braten", "heading": g2.find("**Kaisergranat braten"), "phaseHint": "à la minute", "consumes": ["product:kaisergranat-angetrocknet"],
  "steps": [
   g2.step(16, "salzen", attention="active", duration=D(typical="PT2M", estimated=True), after=["step:trockentupfen"], limits=["nicht heiß — Praline!"]),
   g2.step(17, "pfannen", attention="active", duration=D(typical="PT3M", estimated=True), ingredients=[SI("butterschmalz", A("je 1 EL Butterschmalz", 1, unit="EL", per="Pfanne", times=2))],
           cues=["leicht rauchend"], why="zwei Pfannen parallel schlagen zwei Chargen, Kaisergranat verzeiht kein Warten", claims=[HOB(2)]),
   g2.step(18, "braten-arrosieren", attention="active", duration=D(min="PT2M", max="PT3M", estimated=True), ingredients=[SI("butter", A("je 15 g Butter", 15, unit="g", per="Pfanne", times=2))],
           timers=[T("PT45S", "PT60S", label="Seite 1", text="45–60 Sek."), T("PT45S", "PT60S", label="Arrosieren", text="45–60 Sek.")],
           temps=[{"kind": "kern", "min": 60, "max": 62, "text": "Bei 60–62 °C Kern raus"}, {"kind": "max", "value": 70, "text": "Über \\~70 °C wird er gummiartig"}],
           endCondition={"type": "temperature", "value": 61, "text": "Bei 60–62 °C Kern raus"}, cues=["durchgehend opak, fest-saftig"], limits=["Über \\~70 °C wird er gummiartig, also Thermometer statt Uhr."],
           why="das ist „durchgegart“ im Sinne der Schwangerschafts-Regel und zugleich der Punkt, an dem Kaisergranat am besten ist", claims=[HOB(2)]),
  ]},
 g2.anrichten("anrichten-2", ["product:mango-gel", "product:walnuss-crumble", "product:pralinen-gewaelzt", "product:beurre-blanc"],
              ["step:braten-arrosieren", "step:warmhalten-limette", "step:waelzen"], why="im Saucenspiegel verlaufen sie"),
]
gang2 = {"id": "gang-2", "kind": "course", "title": g2.title, "intro": g2.find("*Vortag:"), "sections": [
    g2.md("**Teller-Logik:**", "Teller-Logik", ["teller-logik"]), g2.md("**Beschaffung, ehrlich:**", "Beschaffung, ehrlich", ["beschaffung"]),
    {"type": "tasks", "title": "Zubereitung", "tasks": tasks2},
    g2.md("**Kind (3 J.):**", "Kind (3 J.)", ["kind"]), g2.md("> **Profi-Tipps:**", "Profi-Tipps", ["profi-tipps"]),
    {"type": "todo", "title": "Offen (Testlauf)", **g2.todo()}]}

# =============================================================== Gang 3
g3 = Course(3)
tasks3 = [
 {"id": "knochen-roesten", "name": "Lammknochen rösten", "heading": g3.find("**Schmoren + Jus"), "phaseHint": "T-1 (oder schon T-2)",
  "steps": [g3.step(1, "knochen-roesten", attention="attended", after=[], duration=D(min="PT20M", max="PT30M", source="20–30 Min."), timers=[T("PT20M", "PT30M", label="Knochen rösten", text="20–30 Min.")],
                    ingredients=[SI("lammknochen", A("500 g Lammknochen", 500, unit="g"))], temps=[{"kind": "ofen", "value": 220, "text": "220 °C"}], claims=[OVEN(220)],
                    cues=["**goldbraun** rösten — nicht tiefdunkel!"], why="Lammknochen werden dunkel geröstet **bitter**")]},
 {"id": "schulter-anbraten", "name": "Lammschulter salzen und anbraten", "phaseHint": "T-1 (Dry-Brine optional T-2)",
  "steps": [g3.step(2, "schulter-anbraten", attention="active", after=[], duration=D(typical="PT15M", estimated=True), timers=[T("PT10M", label="Anbraten", text="\\~10 Min.")],
                    ingredients=[SI("lammschulter", A("2–2,2 kg", 2, 2.2, "kg")), SI("salz", A("2,5–3 TL Salz", 2.5, 3, "TL")), SI("oel", A("1 EL Öl", 1, unit="EL"))],
                    cues=["rundum tief braun anbraten"], claims=[HOB()])]},
 {"id": "ansatz", "name": "Röstansatz und Rotwein-Reduktion",
  "steps": [
   g3.step(3, "roestgemuese", attention="attended", duration=D(typical="PT10M", estimated=True),
           ingredients=[SI("zwiebel", A("150 g Zwiebel", 150, unit="g")), SI("karotte", A("100 g Karotte", 100, unit="g")), SI("knollensellerie", A("100 g Sellerie", 100, unit="g")), SI("tomatenmark", A("1 EL (15 g) Tomatenmark", 1, unit="EL"))],
           cues=["tief braun anrösten"], limits=["**ständig rühren** (verbrannt = bitter)"], claims=[HOB()]),
   g3.step(4, "rotwein-reduktion", attention="attended", duration=D(typical="PT15M", estimated=True), ingredients=[SI("rotwein", A("100 ml Rotwein", 100, unit="ml", times=3))],
           cues=["**fast trocken** einkochen"], why="in Etappen reduziert dominiert die Wein-Säure nicht, und der Alkohol ist praktisch komplett verkocht, bevor Flüssigkeit dazukommt",
           rescue="Null-Risiko-Option: 150 ml Verjus + 150 ml Wasser statt Wein, gleich reduziert — Jus wird etwas flacher.", claims=[HOB()]),
  ]},
 {"id": "schmoren", "name": "Schmoren", "consumes": [],
  "produces": [PROD("schulter-geschmort", "Geschmorte Schulter + Schmorflüssigkeit", "room", {"max": "PT30M", "source": "10 Min. abkühlen lassen, dann **warm** zupfen"})],
  "steps": [g3.step(5, "schmoren", attention="passive", after=["step:knochen-roesten", "step:rotwein-reduktion"], duration=D(min="PT3H", max="PT3H30M", source="3–3,5 Std."),
                    timers=[T("PT3H", "PT3H30M", label="Schmoren", text="3–3,5 Std.")], events=[{"at": {"typical": "PT1H45M", "source": "Nach der Hälfte"}, "text": "Nach der Hälfte einmal wenden."}],
                    ingredients=[SI("wasser", A("1–1,5 L", 1, 1.5, "l", approx=True)), SI("lorbeer", A("1 Lorbeerblatt", 1, unit="Stück")), SI("kraeuter", A("2 Zweige Thymian", 2, unit="Zweige")), SI("knoblauch", A("4 angedrückte Knoblauchzehen", 4, unit="Stück"))],
                    temps=[{"kind": "ofen", "value": 150, "text": "150 °C"}], claims=[OVEN(150)], endCondition={"type": "visual", "text": "Gabel dreht sich ohne Widerstand"}, cues=["bis das Fleisch vom Knochen fällt"])]},
 {"id": "zupfen-pressen", "name": "Zupfen, würzen, pressen", "consumes": ["product:schulter-geschmort"],
  "produces": [PROD("lammblock", "Gepresster Lammblock", "fridge", {"min": "PT8H", "max": "P1D", "source": "über Nacht kalt stellen"}, note="Kastenform mit Gewicht")],
  "steps": [
   g3.step(6, "zupfen", attention="active", duration=D(typical="PT25M", estimated=True), timers=[T("PT10M", label="Abkühlen", text="10 Min.")],
           ingredients=[SI("zitronen", A("½ Zitrone", 0.5, unit="Stück")), SI("kraeuter", A("1 EL gehackter Petersilie", 1, unit="EL")), SI("kraeuter", A("½ TL fein gehacktem Rosmarin", 0.5, unit="TL"))],
           limits=["nicht zu fein — Struktur bleibt"], cues=["**kräftig**"], why="der Block wird kalt gegessen probiert, aber warm serviert, und die Jus kommt dazu"),
   g3.step(7, "pressen", attention="active", duration=D(typical="PT10M", estimated=True), ingredients=[SI("gelatine", A("1 Blatt Gelatine", 1, unit="Blatt"), note="nur als Option")],
           why="Die Gelatine der Schmorflüssigkeit bindet den Block.", rescue="Option, falls der Block beim ersten Mal zerfällt: 1 Blatt Gelatine in den 4–5 EL Fond auflösen — notieren, nicht vorsorglich."),
  ]},
 {"id": "jus-vorbereiten", "name": "Schmorflüssigkeit passieren, entfetten", "consumes": ["product:schulter-geschmort"],
  "produces": [PROD("schmorfluessigkeit", "Schmorflüssigkeit passiert, entfettet", "fridge", {"min": "PT8H", "source": "über Nacht kalt stellen"})],
  "steps": [g3.step(8, "passieren", attention="active", after=["step:zupfen"], duration=D(typical="PT10M", estimated=True), equipment=["feines Sieb", "Passiertuch"],
                    why="Schulter gibt viel Fett ab — der Deckel ist das wichtigste Werkzeug gegen ein schweres Menü")]},
 {"id": "jus-reduzieren", "name": "Jus reduzieren", "phaseHint": "am Tag", "consumes": ["product:schmorfluessigkeit"],
  "produces": [PROD("jus", "Lammjus, reduziert, ungesalzen", "fridge", {"max": None, "source": "Jus erwärmen, salzen"})],
  "steps": [g3.step(9, "jus-reduzieren", attention="attended", duration=D(typical="PT30M", estimated=True), cues=["auf \\~250–300 ml **sanft** reduzieren"],
                    limits=["**Kein Salz bis zum Schluss** (Konzentration!)"], why="zu heftiges Reduzieren macht bitter und trüb", claims=[HOB()])]},
 {"id": "pueree", "name": "Selleriepüree", "heading": g3.find("**Selleriepüree"), "phaseHint": "am Nachmittag, hält warm",
  "produces": [PROD("selleriepueree", "Selleriepüree, warm", "warm", {"max": None, "source": "Abgedeckt warmhalten, vor dem Anrichten ggf. kurz remixen"})],
  "steps": [
   g3.step(10, "sellerie-kochen", attention="attended", after=[], duration=D(min="PT20M", max="PT25M", source="20–25 Min."), timers=[T("PT20M", "PT25M", label="Sellerie köcheln", text="20–25 Min.")],
           ingredients=[SI("knollensellerie", A("600 g Knollensellerie", 600, unit="g")), SI("vollmilch", A("500 ml Vollmilch", 500, unit="ml")), SI("salz", A("½ TL Salz", 0.5, unit="TL"))],
           cues=["bis sehr weich"], limits=["Milch brennt gern an"], why="Außenschicht und grünliche Stellen sind die Bitter-Quelle", claims=[HOB()]),
   g3.step(11, "pueree-mixen", attention="active", duration=D(typical="PT8M", estimated=True), timers=[T("PT2M", label="Ausdampfen", text="2 Min.")],
           ingredients=[SI("butter", A("45 g Butter", 45, unit="g"))], why="gegen Wässrigkeit", equipment=["Stabmixer"]),
   g3.step(12, "pueree-passieren", attention="active", duration=D(typical="PT8M", estimated=True), ingredients=[SI("muskat", A("1 kleinen Prise Muskat", 1, unit="Prise")), SI("zitronen", A("1 TL Zitronensaft", 1, unit="TL"))],
           why="**der** Schritt für seidige Sterne-Textur", equipment=["feines Sieb"]),
  ]},
 {"id": "rosenkohl", "name": "Rosenkohlblätter lösen und blanchieren", "heading": g3.find("**Rosenkohl zweierlei"), "phaseHint": "Nachmittag",
  "produces": [PROD("rosenkohl-blanchiert", "Blanchierte Rosenkohlblätter", "fridge", {"max": None, "source": "kann Stunden vorher passieren"}),
               PROD("rosenkohl-roh", "Rohe Rosenkohlblätter für die Chips", "room")],
  "steps": [
   g3.step(13, "blaetter-loesen", attention="active", after=[], duration=D(typical="PT30M", source="\\~30 Min. einplanen"), ingredients=[SI("rosenkohl", A("700 g Rosenkohl", 700, unit="g"))]),
   g3.step(14, "blanchieren", attention="active", duration=D(typical="PT10M", estimated=True), timers=[T("PT30S", "PT60S", label="Blanchieren", text="30–60 Sek.")], why="fixiert das Knallgrün", claims=[HOB()]),
  ]},
 {"id": "chips", "name": "Sellerie- und Rosenkohl-Chips frittieren", "phaseHint": "1–2 Std. vor Service", "consumes": ["product:rosenkohl-roh"],
  "produces": [PROD("chips", "Sellerie- und Rosenkohl-Chips, ungesalzen", "room", {"max": "PT2H", "source": "Halten 1–2 Std."}, covered=False, note="offen, warm und trocken (z. B. ausgeschalteter Ofen, Tür einen Spalt auf)")],
  "steps": [
   g3.step(15, "frittieren", attention="active", after=["step:blaetter-loesen"], duration=D(typical="PT25M", estimated=True),
           start={"ref": "course:gang-3:serve", "offset": {"min": "-PT2H", "max": "-PT1H", "source": "1–2 Std. vor Service"}},
           ingredients=[SI("frittieroel", A("1 L Öl", 1, unit="l", approx=True)), SI("knollensellerie", A("150 g Sellerie-Scheiben", 150, unit="g"))],
           temps=[{"kind": "ofen", "min": 170, "max": 180, "text": "170–180 °C"}], timers=[T("PT2M", "PT3M", label="Sellerie-Chips", text="2–3 Min."), T("PT30S", label="Rosenkohl-Charge", text="\\~30 Sek.")],
           cues=["**hellgold**", "dunkelgrün und knusprig, nicht braun"], limits=["**knochentrocken**, sonst spritzt es"], equipment=["Mandoline", "Thermometer"], claims=[HOB()]),
   g3.step(16, "chips-lagern", attention="active", duration=D(typical="PT3M", estimated=True), limits=["niemals abdecken (Dampf = zäh)", "**Salzen erst kurz vor dem Servieren.**"],
           rescue="Ofen-Fallback für beide: 150–160 °C, 15–25 Min., einlagig — einfacher, aber weniger kross."),
  ]},
 {"id": "lamm-service", "name": "Lammblöcke", "heading": g3.find("**Lammblöcke & Service:**"), "phaseHint": "Abend", "consumes": ["product:lammblock", "product:rosenkohl-blanchiert", "product:jus", "product:chips"],
  "steps": [
   g3.step(17, "block-temperieren", attention="active", after=[], duration=D(typical="PT10M", estimated=True), start={"ref": "course:gang-3:serve", "offset": {"typical": "-PT1H", "source": "1 Std. vor Gang 3"}},
           why="temperiert wärmt schneller durch", cues=["Kanten glatt — das ist der Look"]),
   g3.step(18, "bloecke-anbraten", attention="active", duration=D(typical="PT8M", estimated=True), ingredients=[SI("butterschmalz", A("1 EL Butterschmalz", 1, unit="EL"))],
           timers=[T("PT1M", "PT2M", label="Charge anbraten", text="je 1–2 Min.")], temps=[{"kind": "ofen", "value": 140, "text": "140 °C"}], claims=[OVEN(140, until="step:durchwaermen:end"), HOB()],
           limits=["Edelstahl: nicht überladen"], why="die Schnittflächen zuerst, sie halten den Block zusammen"),
   g3.step(19, "durchwaermen", attention="attended", duration=D(min="PT12M", max="PT18M", source="12–18 Min."), timers=[T("PT12M", "PT18M", label="Lamm im Ofen", text="12–18 Min.")],
           temps=[{"kind": "kern", "min": 70, "text": "≥ 70 °C Kern"}], endCondition={"type": "temperature", "value": 70, "text": "**≥ 70 °C Kern** — nach Thermometer, nicht nach Uhr"}, claims=[OVEN(140)],
           why="Das ist die Schwangerschafts-Grenze (Listerien nach Lagerung) und zugleich der Punkt, an dem der Block innen wieder saftig-warm ist."),
   g3.step(20, "parallel-finish", attention="active", after=["step:bloecke-anbraten"], duration=D(typical="PT8M", estimated=True),
           ingredients=[SI("butter", A("20 g aufschäumender Butter", 20, unit="g")), SI("salz", A("1 Prise Salz", 1, unit="Prise")), SI("butter", A("25 g eiskalte Butter", 25, unit="g"))],
           timers=[T("PT1M", "PT2M", label="Blätter schwenken", text="1–2 Min.")], limits=["danach nicht mehr kochen"], claims=[HOB(2)]),
  ]},
 g3.anrichten("anrichten-3", ["product:selleriepueree"], ["step:durchwaermen", "step:parallel-finish"], limits=["nicht über die Chips — weichen auf"]),
]
gang3 = {"id": "gang-3", "kind": "course", "title": g3.title, "intro": g3.find("*T-1:"), "sections": [
    g3.md("**Teller-Logik:**", "Teller-Logik", ["teller-logik"]),
    {"type": "tasks", "title": "Zubereitung", "tasks": tasks3},
    g3.md("**Kind (3 J.):**", "Kind (3 J.)", ["kind"]), g3.md("> **Profi-Tipps:**", "Profi-Tipps", ["profi-tipps"]),
    {"type": "todo", "title": "Offen (Testlauf / Beschaffung)", **g3.todo()}]}

# =============================================================== Gang 4
g4 = Course(4)
tasks4 = [
 {"id": "kaffee-crumble", "name": "Kaffee-Crumble", "heading": g4.find("**Kaffee-Crumble"), "phaseHint": "Vortag",
  "produces": [PROD("kaffee-crumble", "Kaffee-Crumble", "room", {"max": None, "source": "luftdicht bei Raumtemperatur"}, covered=True, note="**Nie einfrieren oder kühlen**")],
  "steps": [g4.step(1, "kaffee-crumble", attention="attended", after=[], duration=D(min="PT20M", max="PT25M", estimated=True), timers=[T("PT12M", "PT15M", label="Crumble backen", text="12–15 Min.")],
                    ingredients=[SI("panko", A("40 g Mehl", 40, unit="g")), SI("butter", A("30 g weiche Butter", 30, unit="g")), SI("brauner-zucker", A("25 g brauner Zucker", 25, unit="g")),
                                 SI("espressobohnen", A("1 TL fein gemahlener Decaf-Espresso", 1, unit="TL")), SI("kakaonibs", A("20 g Kakaonibs", 20, unit="g")), SI("salz", A("1 Prise Salz", 1, unit="Prise"))],
                    temps=[{"kind": "ofen", "value": 160, "text": "160 °C"}], claims=[OVEN(160)], limits=["**Nie einfrieren oder kühlen** — zieht Feuchtigkeit."], why="sie sind schon geröstet und leiden nicht")]},
 {"id": "parfait", "name": "Parfait", "heading": g4.find("**Parfait (1–2 Tage vorher):**"), "phaseHint": "1–2 Tage vorher",
  "produces": [PROD("parfait", "Espresso-Parfait, gefroren", "freezer", {"min": "PT8H", "max": "P2D", "source": "**Mind. über Nacht** bei voller Gefrierleistung"})],
  "steps": [
   g4.step(2, "pate-a-bombe", attention="active", after=[], duration=D(typical="PT12M", estimated=True),
           ingredients=[SI("eier", A("4 Eigelb", 4, unit="Stück")), SI("zucker", A("70 g Zucker", 70, unit="g")), SI("dextrose", A("25 g Dextrose", 25, unit="g")),
                        SI("decaf-espresso", A("90 ml ausgekühlten doppelt starken Decaf-Espresso", 90, unit="ml")), SI("instant-espresso", A("2 TL entkoffeiniertes Instant-Espressopulver", 2, unit="TL")), SI("salz", A("2 g Salz", 2, unit="g"))],
           temps=[{"kind": "ziel", "min": 75, "max": 82, "text": "**75–82 °C**"}], endCondition={"type": "temperature", "value": 78, "text": "**75–82 °C** (Thermometer — ab 70 °C pasteurisiert, über 84 °C gerinnt es)"},
           limits=["über 84 °C gerinnt es"], why="so bindet er ein, statt später Volumen zu kosten", equipment=["Küchenthermometer", "Handrührer"], claims=[HOB()]),
   g4.step(3, "kaltschlagen", attention="active", duration=D(min="PT5M", max="PT8M", source="5–8 Min."), timers=[T("PT5M", "PT8M", label="Kaltschlagen", text="5–8 Min.")],
           cues=["bis die Masse unter \\~30 °C ist"], why="warme Masse schmilzt gleich die Sahne"),
   g4.step(4, "sahne-schlagen", attention="active", after=[], duration=D(typical="PT4M", estimated=True), ingredients=[SI("sahne", A("300 ml Sahne", 300, unit="ml"))],
           cues=["zu **weichen Spitzen** schlagen"], limits=["ausdrücklich nicht steif"], why="beim Falten kommt Scherung dazu, übersteift wird’s buttrig-körnig"),
   g4.step(5, "unterheben", attention="active", after=["step:kaltschlagen", "step:sahne-schlagen"], duration=D(typical="PT3M", estimated=True), why="Konsistenzen angleichen", limits=["zügig, nicht rühren"]),
   g4.step(6, "einfrieren", attention="passive", duration=D(min="PT8H", source="**Mind. über Nacht**"), timers=[T("PT8H", label="Gefrieren", text="über Nacht")], why="Kälte dämpft beides"),
  ]},
 {"id": "dessert-service", "name": "Dessert anrichten und Schuss shaken", "heading": g4.find("**Service (à la minute):**"), "service": True, "consumes": ["product:parfait", "product:kaffee-crumble"],
  "steps": [
   g4.step(7, "temperieren", attention="attended", after=[], duration=D(typical="PT15M", source="10–15 Min. vor dem Dessert"), start={"ref": "course:gang-4:serve", "offset": {"min": "-PT15M", "max": "-PT10M", "source": "10–15 Min. vor dem Dessert"}},
           timers=[T("PT10M", "PT15M", label="Parfait temperieren", text="10–15 Min."), T("PT15M", label="Teller frosten", text="15 Min.")],
           ingredients=[SI("decaf-espresso", A("30 ml pro Person", 30, unit="ml", per="Person", approx=True))], limits=["**erst jetzt** brühen"],
           why="die Crema ist das Schaummittel, abgestandener Espresso schäumt nicht", rescue="auf komplett flachem Teller läuft der Schuss sofort an den Rand"),
   g4.step(8, "schneiden", attention="active", duration=D(typical="PT5M", estimated=True), cues=["nach jedem Schnitt Messer neu erwärmen"]),
   g4.step(9, "shaken", attention="active", duration=D(typical="PT5M", estimated=True), timers=[T("PT15S", "PT20S", label="Shaken", text="15–20 Sek.")],
           ingredients=[SI("decaf-espresso", A("30 ml frischer Decaf-Espresso", 30, unit="ml", per="Person")), SI("zuckersirup", A("10 ml Zuckersirup", 10, unit="ml", per="Person")),
                        SI("wodka", A("15 ml Wodka", 15, unit="ml", per="Trinker")), SI("kahlua", A("10 ml Kahlúa", 10, unit="ml", per="Trinker")), SI("decaf-espresso", A("15 ml frischer Decaf-Espresso", 15, unit="ml", per="Trinker"))],
           cues=["bis der Shaker beschlägt", "dichter, heller Schaum"], equipment=["Shaker", "feines Sieb"]),
   g4.step(10, "am-tisch", attention="active", duration=D(typical="PT2M", estimated=True), why="das fördert den Schaum obendrauf („Crema“)", limits=["Sofort essen"]),
  ]},
]
gang4 = {"id": "gang-4", "kind": "course", "title": g4.title, "intro": g4.find("*Parfait:"), "sections": [
    g4.md("**Konzept:**", "Konzept", ["teller-logik"]), g4.md("**Decaf für alle:**", "Decaf für alle", ["schwangerschaft"]),
    g4.md("**Ei-Check:**", "Ei-Check", ["schwangerschaft"]), g4.md("**Textur-Check", "Textur-Check", ["notizen"]),
    {"type": "tasks", "title": "Zubereitung", "tasks": tasks4},
    g4.md("**Kind (3 J.):**", "Kind (3 J.)", ["kind"]), g4.md("> **Profi-Tipps:**", "Profi-Tipps", ["profi-tipps"]),
    {"type": "todo", "title": "Offen (Testlauf)", **g4.todo()}]}

# =============================================================== Zutaten
def I(id, name, store, group=None, buy=None, courses=None, **kw):
    d = {"id": id, "name": name, "store": store}
    if group: d["group"] = group
    if buy: d["buy"] = {"text": buy}
    if courses: d["courses"] = courses
    d.update(kw)
    return d


RC, OG, MI, TR, GT, GW, V = "REWE Center", "Obst & Gemüse", "Milchprodukte & Eier", "Trockenwaren", "Getränke", "Würzmittel & Gewürze", "Vorrat"
ingredients = [
 I("verjus", "Verjus", "Online", buy="500 ml", courses=["gang-2", "gang-3"], note="Weinhandel oder online, \\~8–12 €; vielseitig: Vinaigretten, Poulet au vinaigre"),
 I("espressobohnen", "Espressobohnen **entkoffeiniert**", "Online", buy="250 g", courses=["gang-4"], note="Specialty-Röster (Swiss-Water- oder CO2-Verfahren, dunklere Röstung); billiger Decaf schmeckt flach/sauer"),
 I("instant-espresso", "Instant-Espressopulver **entkoffeiniert**", "Online", buy="klein", courses=["gang-4"], note="Nescafé Gold/Lavazza Dek; Fallback: 1 TL sehr fein gemahlener Decaf"),
 I("kaisergranat", "Kaisergranat", "Buhara Seafood", group="Fleisch & Fisch", buy="12 Stück", courses=["gang-2"], storeNote="vorher anfragen!",
   note="**TK roh, ganz**, \\~1 kg, Größe 10–15 St./kg; Etikett: Nephrops norvegicus; nicht vorgekocht, keine argentinischen Rotgarnelen", fallback="Selgros TK"),
 I("lammschulter", "Lammschulter **mit Knochen**", "Selgros", group="Fleisch & Fisch", buy="2–2,2 kg", courses=["gang-3"], note="Alternative: türkischer Metzger, s. Offen"),
 I("lammknochen", "Lammknochen, gesägt", "Selgros", group="Fleisch & Fisch", buy="500 g", courses=["gang-3"]),
 I("kaisergranat-fallback", "Kaisergranat TK (Selgros)", "Selgros", group="Fleisch & Fisch", courses=["gang-2"], optional=True, priority="optional", note="nur als Fallback, falls Buhara nicht liefert"),
 I("cherrytomaten", "Cherry-/Datteltomaten", RC, OG, "150 g", ["gang-1"]),
 I("limetten", "Limetten", RC, OG, "4 Stück", ["gang-1", "gang-2"]),
 I("zitronen", "Zitronen", RC, OG, "2 Stück", ["gang-3"]),
 I("mango", "Mango, reif", RC, OG, "1 Stück", ["gang-2"]),
 I("ingwer", "Ingwer", RC, OG, "kleines Stück", ["gang-2"]),
 I("schalotten", "Schalotten", RC, OG, "3 Stück", ["gang-2"]),
 I("zwiebel", "Zwiebel", RC, OG, "150 g", ["gang-3"]),
 I("karotte", "Karotte", RC, OG, "1 Stück", ["gang-3"]),
 I("knollensellerie", "Knollensellerie", RC, OG, "1 große Knolle (\\~1,2 kg)", ["gang-3"]),
 I("rosenkohl", "Rosenkohl", RC, OG, "700 g", ["gang-3"]),
 I("knoblauch", "Knoblauch", RC, OG, "1 Knolle", ["gang-3"]),
 I("kraeuter", "Petersilie, Schnittlauch, Thymian, Rosmarin", RC, OG, "je 1 Bund/Töpfchen", ["gang-2", "gang-3"]),
 I("basilikum", "Basilikum", RC, OG, "1 Töpfchen", ["gang-1"]),
 I("butter", "Butter", RC, MI, "500 g (2 × 250 g)", ["gang-2", "gang-3", "gang-4"]),
 I("ziegenfrischkaese", "Ziegenfrischkäse, **mild, pasteurisiert**", RC, MI, "150 g", ["gang-2"], note="z. B. Chavroux; Petit Billy falls da — kräftig-rustikale Sorten (Caprinsäure) dominieren den feinen Kaisergranat; Etikett auf pasteurisierte Milch prüfen"),
 I("sahne", "Sahne", RC, MI, "500 ml", ["gang-2", "gang-4"], unitHint={"from": "EL", "to": "ml", "factor": 15}),
 I("vollmilch", "Vollmilch", RC, MI, "1 L", ["gang-3"]),
 I("eier", "Eier", RC, MI, "6 Stück", ["gang-4"], note="4 Eigelb; Eiweiß-Verwertung einplanen"),
 I("walnuesse", "Walnüsse", RC, TR, "100 g", ["gang-2"]),
 I("agar", "Agar-Agar", RC, TR, "1 Päckchen", ["gang-2"], note="Bio-/Backregal; Fallback: Chutney-Variante ohne Agar"),
 I("kakaonibs", "Kakaonibs", RC, TR, "klein", ["gang-4"], note="Bio-Regal; Fallback: Zartbitter 70 %+ gehackt"),
 I("dextrose", "Dextrose (Traubenzucker)", RC, TR, "25 g", ["gang-4"], note="Vorrat aus `eis/` prüfen"),
 I("brauner-zucker", "Brauner Zucker", RC, TR, "500 g", ["gang-4"], note="falls kein Vorrat"),
 I("rotwein", "Rotwein, kräftig", RC, GT, "1 Flasche", ["gang-3"], note="300 ml, wird in Schüben trocken reduziert; alkoholfreie Option: 150 ml Verjus + 150 ml Wasser"),
 I("wodka", "Wodka", RC, GT, "kleine Flasche", ["gang-4"], optional=True, note="**nur Espresso-Martini-Schuss**, \\~15 ml pro Trinker; neutraler 40%er reicht"),
 I("kahlua", "Kahlúa o. ä. Kaffeelikör", RC, GT, "klein", ["gang-4"], optional=True, note="**nur Schuss**, \\~10 ml pro Trinker"),
 I("frittieroel", "Frittieröl", RC, GT, "1–2 L", ["gang-3"]),
 I("selleriesalz", "Selleriesalz", RC, GW, "1 Glas", ["gang-1"]),
 I("pfeffer-weiss", "Weißer Pfeffer, ganz", RC, GW, courses=["gang-1", "gang-2"], note="falls kein Vorrat — kein schwarzer: sichtbare Punkte"),
 I("tomatenwasser", "Tomatenwasser", V, courses=["gang-1"], inStock=True, note="**beide Klärwege (Püree-Block + klares Wasser) liegen seit 09/2026 im Gefrierfach**"),
 I("worcestershire", "Worcestershire-Sauce", V, courses=["gang-1"], pantry=True),
 I("chilioel", "Mildes Chiliöl", V, courses=["gang-1"], pantry=True, note="oder selbst ansetzen → Chili-Öl-Drill in `technik/mini-projekte.md`"),
 I("weissweinessig", "Weißweinessig", V, courses=["gang-2"], pantry=True),
 I("butterschmalz", "Butterschmalz", V, courses=["gang-2", "gang-3"], pantry=True),
 I("gelatine", "Gelatine", V, buy="1 Blatt", courses=["gang-3"], optional=True, note="nur als Option für die Block-Bindung"),
 I("zucker", "Zucker", V, courses=["gang-2", "gang-4"], pantry=True, note="auch für 1:1-Zuckersirup, Shakerato", unitHint={"from": "EL", "to": "g", "factor": 12}),
 I("panko", "Panko oder Mehl", V, courses=["gang-2", "gang-4"], pantry=True),
 I("honig", "Honig", V, courses=["gang-2"], pantry=True),
 I("muskat", "Muskat", V, courses=["gang-3"], pantry=True),
 I("tomatenmark", "Tomatenmark", V, courses=["gang-3"], pantry=True, unitHint={"from": "EL", "to": "g", "factor": 15}),
 I("lorbeer", "Lorbeer", V, courses=["gang-3"], pantry=True),
 I("salz", "Salz", V, pantry=True),
 I("wasser", "Wasser", V, pantry=True),
 I("oel", "Öl (neutral)", V, pantry=True, courses=["gang-3"]),
 I("decaf-espresso", "Decaf-Espresso (gebrüht)", V, courses=["gang-4"], pantry=True, note="aus den Espressobohnen; 2–3 Brühgänge"),
 I("zuckersirup", "Zuckersirup 1:1", V, courses=["gang-4"], pantry=True, note="Zucker in gleich viel heißem Wasser gelöst, abgekühlt"),
]

# =============================================================== Zeitplan
zp_title = next(t for t in H2 if t.startswith("Zeitplan-Skelett"))
zp = H2[zp_title]
note = next(pp for pp in paragraphs(zp) if pp.startswith("**Ofen-Plan"))
bullets: list[str] = []
for line in zp.split("\n"):
    if line.startswith("- "):
        bullets.append(line[2:])
    elif line.startswith("  ") and bullets:
        bullets[-1] += " " + line.strip()
PHASES = [("saison", "Saison-Teil (erledigt 09/2026)", -60, None, None),
          ("t-2", "T-2", -2, None, None), ("t-1", "T-1", -1, None, None), ("vormittags", "Vormittags", 0, "morning", None),
          ("nachmittags", "Nachmittags", 0, "afternoon", None), ("gang-1", "Gang 1 (0:00)", 0, "service", "PT0M"),
          ("gang-2", "Gang 2 (+0:20)", 0, "service", "+PT20M"), ("gang-3", "Gang 3 (+0:55)", 0, "service", "+PT55M"), ("gang-4", "Gang 4 (+1:45)", 0, "service", "+PT1H45M")]
entries = []
for b in bullets:
    ph = next(p for p in PHASES if b.startswith(p[1] + ":"))
    for seg in re.split(r"\s·\s", b[len(ph[1]) + 1:].strip()):
        entries.append({"phase": ph[0], "text": seg.strip()})
MAP = {
 "**Tomaten-Püree-Block (Weg A) aus dem Gefrierfach ins Passiertuch (Drip-Thaw braucht 24–48 h!)**": {"steps": ["klaeren"], "course": "gang-1"},
 "Parfait einfrieren": {"tasks": ["parfait"], "course": "gang-4"},
 "Lammschulter salzen (Dry-Brine, optional)": {"steps": ["schulter-anbraten"], "course": "gang-3"},
 "Lammknochen ggf. schon rösten": {"steps": ["knochen-roesten"], "course": "gang-3"},
 "**Lammschulter schmoren (3–3,5 h), zupfen, pressen; Schmorflüssigkeit passieren und kalt stellen**": {"tasks": ["knochen-roesten", "schulter-anbraten", "ansatz", "schmoren", "zupfen-pressen", "jus-vorbereiten"], "course": "gang-3"},
 "Mango-Gel": {"tasks": ["mango-gel"], "course": "gang-2"},
 "beide Crumbles": {"tasks": ["walnuss-crumble", "kaffee-crumble"], "course": "gang-2"},
 "Ziegenkäse- Pralinen formen (ungewälzt)": {"tasks": ["pralinen-formen"], "course": "gang-2"},
 "Kaisergranat im Kühlschrank auftauen": {"steps": ["auftauen"], "course": "gang-2"},
 "Weg B: Tomatenwasser in den Kühlschrank zum Auftauen": {"steps": ["klaeren"], "course": "gang-1"},
 "Fettdeckel von der Schmorflüssigkeit, Jus auf 250–300 ml reduzieren": {"steps": ["jus-reduzieren"], "course": "gang-3"},
 "Kaisergranat auslösen, Schalen einfrieren": {"steps": ["ausloesen"], "course": "gang-2"},
 "Rosenkohlblätter lösen, Hälfte blanchieren": {"tasks": ["rosenkohl"], "course": "gang-3"},
 "Selleriepüree": {"tasks": ["pueree"], "course": "gang-3"},
 "Chips frittieren (Sellerie, dann Rosenkohl — halten 1–2 h)": {"tasks": ["chips"], "course": "gang-3"},
 "Kaisergranat offen antrocknen": {"steps": ["trockentupfen"], "course": "gang-2"},
 "Lammblock 1 h vor Gang 3 aus dem Kühlschrank, schneiden": {"steps": ["block-temperieren"], "course": "gang-3", "at": {"ref": "course:gang-3:serve", "offset": "-PT1H"}, "source": "1 Std. vor Gang 3"},
 "Ofen 80 °C für Teller": {},
 "Tomatenwasser abschmecken, anrichten — kein Herd nötig (Grundwürzung schon 1–2 h vorher)": {"steps": ["abschmecken", "limette", "anrichten-1"], "at": {"ref": "course:gang-1:serve", "offset": "-PT10M"}, "source": "kein Herd nötig"},
 "Beurre blanc montieren, Kaisergranat à la minute (\\~8 Min. aktiv)": {"tasks": ["beurre-blanc", "braten", "anrichten-2"], "at": {"ref": "course:gang-2:serve", "offset": "-PT20M"}, "source": "\\~20 Min. vor dem Gang"},
 "Ofen auf 140 °C, Blöcke anbraten, 12–18 Min. Ofen bis ≥ 70 °C Kern (Thermometer-Alarm)": {"steps": ["bloecke-anbraten", "durchwaermen"], "at": {"ref": "course:gang-3:serve", "offset": "-PT30M"}, "source": "Nach Gang 2"},
 "parallel Rosenkohl schwenken, Jus montieren, Chips salzen": {"steps": ["parallel-finish"], "at": {"ref": "course:gang-3:serve", "offset": "-PT12M"}, "source": "parallel"},
 "Parfait 10–15 Min. vorher in den Kühlschrank, Scheiben schneiden, Espresso brühen, Shakerato und Martini am Tisch shaken": {"tasks": ["dessert-service"], "at": {"ref": "course:gang-4:serve", "offset": "-PT15M"}, "source": "10–15 Min. vorher"},
}
for e in entries:
    m = MAP.get(e["text"])
    assert m is not None, e["text"]
    e.update(m)
    if e["phase"].startswith("gang-"):
        e["course"] = e["phase"]
entries += [
 {"phase": "saison", "text": "Saison-Teil: Tomaten salzen, mixen, einfrieren bzw. abtropfen (erledigt 09/2026)", "tasks": ["saison"], "course": "gang-1", "derived": True},
 {"phase": "nachmittags", "text": "Concassé schneiden (ungesalzen)", "steps": ["concasse"], "course": "gang-1", "derived": True},
 {"phase": "gang-1", "text": "Tomatenwasser Grundwürzung, kalt ziehen lassen", "steps": ["grundwuerzung"], "course": "gang-1", "derived": True,
  "at": {"ref": "course:gang-1:serve", "offset": "-PT1H30M"}, "source": "Grundwürzung **1–2 h vor Service**"},
 {"phase": "gang-2", "text": "Pralinen wälzen", "tasks": ["pralinen-waelzen"], "course": "gang-2", "derived": True, "at": {"ref": "course:gang-2:serve", "offset": "-PT30M"}, "source": "Erst ≤30 Min. vor dem Anrichten"},
 {"phase": "gang-3", "text": "Anrichten: Püree, Block, Blätter, Chips, Jus", "tasks": ["anrichten-3"], "course": "gang-3", "derived": True, "at": {"ref": "course:gang-3:serve", "offset": "-PT4M"}},
]
schedule = {"id": "abend", "label": zp_title,
            "phases": [{"id": i, "label": l, "day": d, **({"part": pt} if pt else {}), **({"at": at} if at else {})} for i, l, d, pt, at in PHASES],
            "entries": entries}

todo_items = []
for line in H2["To-do gesamt"].split("\n"):
    m = re.match(r"^- \[([ x])\] (.*)$", line)
    if m:
        todo_items.append({"text": m.group(2), "checked": m.group(1) == "x"})
    elif line.startswith("  ") and todo_items:
        todo_items[-1]["text"] += " " + line.strip()

head = H2[""]
recipe = {
 "$schema": "../recipe.schema.json", "schemaVersion": "0.1",
 "id": "menues/menue-november", "kind": "menu", "title": re.search(r"^# 🚧 (.*)$", head, re.M).group(1), "status": "wip",
 "statusNote": "\n\n".join(pp for pp in paragraphs(head) if pp.startswith("> [!NOTE]")),
 "yields": {"text": "4–5 Personen", "value": 5, "unit": "Personen"},
 "persons": {"text": "4–5 Personen (2 Erw. + Gäste + Kind 3 J.)", "adults": 2, "kids": 1},
 "anchor": {"label": "Gang 1 serviert"},
 "courses": [{"ref": "gang-1", "n": 1, "name": "Tomatenwasser", "serve": "PT0M", "source": "Gang 1 (0:00)"},
             {"ref": "gang-2", "n": 2, "name": "Kaisergranat", "serve": "+PT20M", "source": "Gang 2 (+0:20)"},
             {"ref": "gang-3", "n": 3, "name": "Lammschulter", "serve": "+PT55M", "source": "Gang 3 (+0:55)"},
             {"ref": "gang-4", "n": 4, "name": "Espresso-Parfait", "serve": "+PT1H45M", "source": "Gang 4 (+1:45)"}],
 "resources": [{"id": "oven", "count": 1}, {"id": "hob", "count": 4}, {"id": "cook", "count": 1}],
 "constraints": [
   {"type": "max-gap", "from": "step:warmhalten-limette:end", "to": "task:anrichten-2:start", "value": "PT5M", "source": "Erst unmittelbar vor dem Anrichten"},
   {"type": "max-gap", "from": "step:salzen:end", "to": "step:pfannen:start", "value": "PT2M", "source": "erst direkt vor dem Braten"},
   {"type": "max-gap", "from": "step:limette:end", "to": "step:anrichten-1:start", "value": "PT3M", "source": "Kurz vor dem Ausgießen"}],
 "ingredients": ingredients,
 "sections": [
   {"type": "markdown", "title": "Menüfolge & Dramaturgie", "level": 2, "markdown": H2["Menüfolge & Dramaturgie"].strip("\n")},
   {"type": "shopping", "title": "Einkaufsliste"},
   {"type": "courses", "title": "Rezepte", "courses": [gang1, gang2, gang3, gang4]},
   {"type": "schedule", "title": zp_title, "note": note, "schedule": schedule},
   {"type": "todo", "title": "To-do gesamt", "items": todo_items},
   {"type": "markdown", "title": "Quellen & Entscheidungen", "level": 2, "tags": ["quellen"], "markdown": H2["Quellen & Entscheidungen"].strip("\n")},
 ]}
out = ROOT / "schema/beispiele/menue-november.json"
out.write_text(json.dumps(recipe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
n_steps = sum(len(t["steps"]) for g in (tasks1, tasks2, tasks3, tasks4) for t in g)
print(f"geschrieben: {out.relative_to(ROOT)} | Schritte {n_steps} | Zutaten {len(ingredients)} | Zeitplan-Einträge {len(entries)}")
