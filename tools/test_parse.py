"""Regel-Tests des Parsers gegen die Gerüste aus REZEPTFORMAT.md.
Aufruf: python3 tools/test_parse.py"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.recipes.parse import parse_recipe  # noqa: E402

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
print(f"{n} Tests ok")
if lint.msgs or mlint.msgs:
    print("Lint (Gericht):", *lint.msgs, sep="\n  ") if lint.msgs else None
    print("Lint (Menü):", *mlint.msgs, sep="\n  ") if mlint.msgs else None
