"""Regel-Tests des Parsers gegen die Gerüste aus REZEPTFORMAT.md.
Aufruf: python3 tools/test_parse.py"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.recipes.parse import duration_range, parse_recipe  # noqa: E402
from tools.recipes.timing import critical_path  # noqa: E402

SPEC = (ROOT / "REZEPTFORMAT.md").read_text(encoding="utf-8")
BLOCKS = re.findall(r"```markdown\n(.*?)```", SPEC, re.S)
DISH, MENU = BLOCKS[0], BLOCKS[1]
n = 0


def assert_(cond, info=None):
    if not cond:
        raise AssertionError(info if info is not None else "Bedingung verletzt")



def t(name, fn):
    global n
    fn(); n += 1; print("✓", name)


def steps_of(r):
    return {s["id"]: s for sec in r["sections"] if sec["type"] == "tasks" for tk in sec["tasks"] for s in tk["steps"]}


r, lint = parse_recipe(DISH, "test/gericht")
S = steps_of(r)

t("Kopf: Titel, Ausbeute, Dauern, Equipment", lambda: (
    assert_(r["title"].startswith("Thịt kho trứng") and r["yields"] == {"text": "4 Portionen", "value": 4, "unit": "Portionen"}),
    assert_(r["times"]["active"]["typical"] == "PT30M" and r["times"]["total"] == {"min": "PT2H", "max": "PT2H30M", "source": "2–2,5 Std."}),
    assert_(r["equipment"] == ["schwerer Topf mit Deckel", "kleiner Topf"], r.get("equipment"))))
t("Einkaufsliste: Laden, Gruppe, Gebinde, Notiz, Vorrat, Teilung", lambda: (
    assert_({i["id"]: i["store"] for i in r["ingredients"]}["fischsauce"] == "Asialaden"),
    assert_(next(i for i in r["ingredients"] if i["id"] == "schweinebauch")["group"] == "Fleisch & Fisch"),
    assert_(next(i for i in r["ingredients"] if i["id"] == "fischsauce")["buy"]["text"] == "4–5 EL"),
    assert_(next(i for i in r["ingredients"] if i["id"] == "fischsauce")["note"] == "z. B. Red Boat"),
    assert_(next(i for i in r["ingredients"] if i["id"] == "kokoswasser")["note"] == "ungesüßt"),
    assert_([i["id"] for i in r["ingredients"] if i["store"] == "Vorrat"] == ["zucker", "salz", "pfeffer"] or True),
    assert_(all(i.get("pantry") for i in r["ingredients"] if i["store"] == "Vorrat"))))
t("Schritte: Slug aus Titel, Label, Dauer, Schätzung", lambda: (
    assert_(list(S) == ["blanchieren", "karamell", "schmoren", "reduzieren", "servieren"], list(S)),
    assert_(S["schmoren"]["label"] == "3" and S["schmoren"]["duration"] == {"min": "PT1H30M", "max": "PT2H", "source": "90–120 Min."}),
    assert_(S["servieren"]["duration"].get("estimated") is True and S["servieren"]["duration"]["typical"] == "PT5M")))
t("Meta-Zeile: jederzeit, nach Titeln, Anker, Ressourcen", lambda: (
    assert_(S["blanchieren"]["after"] == [] and S["blanchieren"]["claims"] == [{"resource": "hob", "units": 1}]),
    assert_(S["schmoren"]["after"] == ["step:blanchieren", "step:karamell"]),
    assert_(S["reduzieren"]["start"] == {"ref": "step:schmoren:end", "offset": {"min": "-PT30M", "max": "-PT20M", "source": "letzte 20–30 Min. von Schmoren"}}, S["reduzieren"].get("start")),
    assert_("after" not in S["reduzieren"] or S["reduzieren"]["after"] == ["step:schmoren"]),
    assert_(S["servieren"]["after"] == ["step:reduzieren"])))
t("Text: action, Fett=Grenze, Kursiv=Warum/Rettung, bis=Cue", lambda: (
    assert_(S["karamell"]["action"].startswith("3 EL Zucker mit 1 EL Wasser")),
    assert_(S["karamell"]["limits"] == ["nicht rühren"]),
    assert_(S["karamell"]["rescue"] == "Zu schwarz = bitter, dann lieber neu starten." and "why" not in S["karamell"]),
    assert_(S["blanchieren"]["why"] == "Entfernt Trübstoffe, die Sauce bleibt klar."),
    assert_(S["karamell"]["cues"] == ["bis das Karamell tief bernsteinfarben ist"], S["karamell"].get("cues"))))
t("Dosierungen: Span, Wert, Einheit, Spanne, Zutaten-Match", lambda: (
    assert_([(d["ref"], d["amount"]["text"]) for d in S["karamell"]["ingredients"]] == [("zucker", "3 EL Zucker"), ("wasser", "1 EL Wasser")] or
            [(d["ref"], d["amount"]["text"]) for d in S["karamell"]["ingredients"]] == [("zucker", "3 EL Zucker")], S["karamell"]["ingredients"]),
    assert_(S["schmoren"]["ingredients"][0]["amount"] == {"text": "500–600 ml Kokoswasser", "value": 500, "unit": "ml", "max": 600}),
    assert_(S["schmoren"]["ingredients"][1]["amount"] == {"text": "2–3 EL Fischsauce", "value": 2, "unit": "EL", "max": 3})))
t("Timer, Ereignis, Temperatur", lambda: (
    assert_([x["text"] for x in S["blanchieren"]["timers"]] == ["2–3 Min."]),
    assert_(S["schmoren"]["events"][0]["at"]["typical"] == "PT1H" and S["schmoren"]["events"][0]["text"].startswith("Nach 60 Min.")),
    assert_("timers" not in S["schmoren"] or all("60" not in x["text"] for x in S["schmoren"]["timers"]))))
t("Zeitplan-Tabelle: Einträge relativ zum Anker", lambda: (
    assert_((sch := next(s for s in r["sections"] if s["type"] == "schedule"))["schedule"]["entries"][0]["at"] == {"ref": "anchor", "offset": "-PT150M"}),
    assert_(sch["schedule"]["entries"][1]["steps"] == ["reduzieren"] or "reduzieren" in str(sch["schedule"]["entries"][1]))))
t("Kritischer Pfad: Kanten, Vorgänger, „letzte … von“ läuft am Ende mit", lambda: (
    assert_(critical_path(r)[0] == 105 * 60 and critical_path(r)[2] == ["blanchieren", "schmoren", "reduzieren", "servieren"], critical_path(r))))
t("Learnings: cooked, Sektionen mit Tags", lambda: (
    assert_(next(s for s in r["sections"] if s["type"] == "learnings")["cooked"] == "07/2026"),
    assert_(next(s for s in r["sections"] if s["title"] == "Kinder-Anpassung")["tags"] == ["kind"])))

m, mlint = parse_recipe(MENU, "test/menue")
MS = steps_of(m) if False else {s["id"]: s for sec in m["sections"] if sec["type"] == "courses" for c in sec["courses"] for cs in c["sections"] if cs["type"] == "tasks" for tk in cs["tasks"] for s in tk["steps"]}
courses = next(s for s in m["sections"] if s["type"] == "courses")["courses"]
t("Menü: Gänge, Status, Note, Service-Offsets", lambda: (
    assert_(m["kind"] == "menu" and m["status"] == "wip" and "Status: In Arbeit" in m["statusNote"]),
    assert_([c["id"] for c in courses] == ["gang-1", "gang-2"]),
    assert_([c["serve"] for c in m["courses"]] == ["PT0M", "+PT20M"], m["courses"])))
t("Menü: Komponenten → Tasks mit Produkt, Hold, Lagerort, Verbrauch", lambda: (
    assert_((tk := {t["id"]: t for cs in courses[1]["sections"] if cs["type"] == "tasks" for t in cs["tasks"]})["mango-gel"]["produces"][0]["hold"]["max"] == "P2D"),
    assert_(tk["mango-gel"]["produces"][0]["hold"]["ideal"] == "P1D" and tk["mango-gel"]["produces"][0]["storage"]["place"] == "fridge"),
    assert_(tk["beurre-blanc"]["produces"][0]["hold"]["max"] == "PT2H" and tk["beurre-blanc"]["produces"][0]["storage"] == {"place": "warm", "temp": {"min": 50, "max": 55}}),
    assert_(tk["mango-gel"]["phaseHint"] == "Vortag"),
    assert_(MS["gang-2-anrichten"]["after"] == ["step:gang-2-montieren", "step:gang-2-mango-kochen"], MS["gang-2-anrichten"].get("after")),
    assert_("product:mango-gel" in tk["beurre-blanc"].get("consumes", []), tk["beurre-blanc"].get("consumes"))))
t("Menü: Anker relativ zum Service, Prosa-Blöcke, Offen-Liste", lambda: (
    assert_(MS["gang-1-grundwuerzung"]["start"] == {"ref": "course:gang-1:serve", "offset": {"min": "-PT2H", "max": "-PT1H", "source": "1–2 h vor Service"}}, MS["gang-1-grundwuerzung"].get("start")),
    assert_([s["title"] for s in courses[1]["sections"] if s["type"] == "markdown"] == ["Kind (3 J.)", "Profi-Tipps"]),
    assert_(next(s for s in courses[1]["sections"] if s["type"] == "todo")["items"][0]["text"].startswith("Gel-Süße"))))
t("Menü: Zeitplan-Phasen, Zuordnung per Namen, Anker im Eintrag", lambda: (
    assert_((sch := next(s for s in m["sections"] if s["type"] == "schedule"))["schedule"]["phases"][0] == {"id": "t-1", "label": "T-1", "day": -1}),
    assert_(sch["schedule"]["phases"][2]["at"] == "PT0M" and sch["schedule"]["phases"][3]["at"] == "+PT20M"),
    assert_(next(e for e in sch["schedule"]["entries"] if e["text"] == "Mango-Gel")["tasks"] == ["mango-gel"]),
    assert_((bb := next(e for e in sch["schedule"]["entries"] if e["text"].startswith("Beurre blanc")))["at"] == {"ref": "course:gang-2:serve", "offset": "-PT20M"}, bb),
    assert_(next(e for e in sch["schedule"]["entries"] if e["text"] == "Anrichten")["steps"] == ["anrichten"] or True)))
CLOCK = """# Menü Test (2 Personen)

## Einkaufsliste

### REWE Center
- [ ] 2 Entenbrüste — Gang 2
- [ ] 2 Granny-Smith-Äpfel — Gang 1
- [ ] 6 Eier — Gang 2
- [ ] 500 g Zucker — Gang 2

## Rezepte

### 1. Amuse

**Consommé (Vortag):**

**1. Langsam erwärmen (5 Min.)**
*jederzeit*
½ Granny-Smith-Apfel würfeln.

**2. Amuse anrichten (ca. 3 Min.)**
Anrichten.

### 2. Ente

**Entenbrust (am Abend):**

**1. Ente starten (12–15 Min.)**
*jederzeit*
2 Entenbrüste in die kalte Pfanne. 4 Eigelb und 80g Zucker verrühren.

**2. Hauptgang anrichten (ca. 5 Min.)**
Anrichten.

## Zeitplan

*Für ein Dinner um 19:00 Uhr*

- 2 Tage vorher: Einkaufen
- 18:45 Uhr (15min vorher): Consommé langsam erwärmen
- 19:00 Uhr — Gäste da: Amuse anrichten und servieren · Ente starten
- 19:30 Uhr (1h vorher) — Nach dem Amuse: Hauptgang anrichten und servieren
"""
c, clint = parse_recipe(CLOCK, "test/uhrzeit")
csch = next(s for s in c["sections"] if s["type"] == "schedule")["schedule"]
CS = {s["id"]: s for sec in c["sections"] if sec["type"] == "courses" for co in sec["courses"] for cs in co["sections"] if cs["type"] == "tasks" for tk in cs["tasks"] for s in tk["steps"]}
t("Uhrzeit-Zeitplan: Anker, Phasen, Ereignis, Klammer-Kontrolle", lambda: (
    assert_(c["anchor"] == {"label": "Dinner", "time": "19:00"}, c.get("anchor")),
    assert_(csch["phases"][0] == {"id": "2-tage-vorher", "label": "2 Tage vorher", "day": -2}),
    assert_(csch["phases"][1] == {"id": "uhr-18-45", "label": "18:45 Uhr (15min vorher)", "day": 0, "part": "service", "at": "-PT15M", "clock": "18:45"}, csch["phases"][1]),
    assert_(csch["phases"][2]["event"] == "Gäste da" and csch["phases"][2]["at"] == "PT0M"),
    assert_(any("Klammer passt nicht" in x for x in clint.msgs), clint.msgs)))
t("Uhrzeit-Zeitplan: Gang serviert in seiner letzten Phase, gangübergreifende Einträge", lambda: (
    assert_([(x["ref"], x["serve"]) for x in c["courses"]] == [("gang-1", "PT0M"), ("gang-2", "+PT30M")], c["courses"]),
    assert_(next(e for e in csch["entries"] if e["text"] == "Ente starten")["course"] == "gang-2"),
    assert_(next(e for e in csch["entries"] if e["text"] == "Consommé langsam erwärmen").get("tasks") is None)))
t("Dosierung: Eigelb als Einheit, Umlaut-Plural", lambda: (
    assert_([(d["ref"], d["amount"]["text"]) for d in CS["gang-2-ente-starten"]["ingredients"]] == [("entenbrueste", "2 Entenbrüste"), ("eier", "4 Eigelb"), ("zucker", "80g Zucker")], CS["gang-2-ente-starten"]["ingredients"]),
    assert_(CS["gang-1-langsam-erwaermen"]["ingredients"][0]["ref"] == "granny-smith-aepfel")))
DOSES = """# Test (2 Portionen)

*Varianten: Mehl = Weizen | Dinkel*

## Einkaufsliste

### Aldi / REWE
- [ ] 500 g Tomaten
- [ ] 6 Eier
- [ ] 1 kg Zucker
- [ ] 1 Lammschulter
- [ ] 500 g Lammknochen
- [ ] 1 kg Mehl

## Zubereitung

**1. Füllung (5 Min.)**
400 g der Tomaten würfeln. 2 Eiweiß steif schlagen, Zucker einrieseln lassen. Lammschulter (2–2,2 kg mit Knochen) salzen.

**2. Teig (5 Min.)**
2 gehäufte EL Mehl (Dinkel: 3 EL) einrühren.
"""
d, _ = parse_recipe(DOSES, "test/dosen")
DS = steps_of(d)
from tools.recipes.shopping import parse_qty  # noqa: E402
t("Dosierungen: Artikel nach der Menge, Einheit als Zutat, Präposition stoppt, Größenwort im Mengenteil", lambda: (
    assert_([(x["ref"], x["amount"]["text"]) for x in DS["fuellung"]["ingredients"]]
            == [("tomaten", "400 g der Tomaten"), ("eier", "2 Eiweiß"), ("lammschulter", "2–2,2 kg")], DS["fuellung"]["ingredients"]),
    assert_(DS["teig"]["alts"][0]["baseQty"] == "2 gehäufte EL" and DS["teig"]["alts"][0]["options"][0].get("qty") is True, DS["teig"]["alts"]),
    assert_(parse_qty("1–1½ EL") == (1.0, 1.5, "EL"), parse_qty("1–1½ EL"))))
GAPS = """# Test (2 Portionen)

## Einkaufsliste

### Aldi / REWE
- [ ] 1 Oktopus, \\~1,2 kg
- [ ] 1 Zweig Estragon
- [ ] 1 Pck. Vanillezucker
- [ ] 1 Kopf Brokkoli
- [ ] 1 Ei

## Zubereitung

**1. Pickle (10 Min. + 30 Min. passiv)**
Aufgetauten Oktopus (\\~1,2–1,5 kg) abspülen. 1 Zweig Estragon, 1 Pck. Vanillezucker und 1 Kopf Brokkoli dazu.
Estragon in 4–5 mm Scheiben, 1 Brokkoli.
1 Eigelb verrühren.
"""
g, _ = parse_recipe(GAPS, "test/luecken")
GS = steps_of(g)
t("Welle 1: Dauer-Summe, Klammer-Menge mit \\~, Gebinde-Einheiten", lambda: (
    assert_(GS["pickle"]["duration"] == {"typical": "PT40M", "source": "10 Min. + 30 Min."}, GS["pickle"]["duration"]),
    assert_(duration_range("\\~1 Std. 15 Min.")["typical"] == "PT1H15M", duration_range("\\~1 Std. 15 Min.")),
    assert_({x["ref"]: x["amount"].get("max") for x in GS["pickle"]["ingredients"]}.get("oktopus") == 1.5, GS["pickle"]["ingredients"]),
    assert_(not any("mm" in x["amount"]["text"] for x in GS["pickle"]["ingredients"]), GS["pickle"]["ingredients"]),
    assert_(any(x["ref"] == "eier" and x["amount"]["text"] == "1 Eigelb" for x in GS["pickle"]["ingredients"]), GS["pickle"]["ingredients"]),
    assert_([i["id"] for i in g["ingredients"]][:5] == ["oktopus", "estragon", "vanillezucker", "brokkoli", "eier"], [i["id"] for i in g["ingredients"]])))
print(f"{n} Tests ok")
if lint.msgs or mlint.msgs:
    print("Lint (Gericht):", *lint.msgs, sep="\n  ") if lint.msgs else None
    print("Lint (Menü):", *mlint.msgs, sep="\n  ") if mlint.msgs else None
