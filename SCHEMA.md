# SCHEMA.md — Strukturiertes Rezeptformat (Phase 2)

Kanonisches Zwischenformat für Rezepte und Menüs: JSON mit JSON Schema
(`schema/recipe.schema.json`), handkonvertierte Beispiele unter `schema/beispiele/`,
Validator unter `tools/recipes/`. **Die Markdown-Dateien bleiben die einzige Quelle**;
in Phase 2 wird keine `.md` verändert. Dieses Dokument hält Leitentscheidungen,
Konvertierungs-Anleitung, Checks und Messwerte fest.

Aufruf:

```sh
python3 -m tools.recipes.cli check schema/beispiele/*.json      # Checks A–D
python3 -m tools.recipes.cli check schema/beispiele/x.json -v   # mit Reports
python3 -m tools.recipes.cli derive schema/beispiele/x.json      # derived-Block (Einkaufsliste, Mengen) schreiben
python3 -m tools.recipes.cli shopping schema/beispiele/x.json    # Einkaufsliste als Markdown
python3 -m tools.recipes.cli diff a.json b.json                 # Feld-Diff zweier Konvertierungen (Check I / M)
python3 -m tools.recipes.cli build gerichte/x.md                # Markdown (REZEPTFORMAT.md) → gerichte/x.json
python3 -m tools.recipes.cli lint gerichte/x.md                 # Parser-Hinweise
task build               # alle Rezepte mit JSON neu bauen
task validate            # Checks über alle gebauten JSONs + Aktualität (build --check)
task test-kochmodus      # Node-Tests der Kochmodus-Funktionen (kochmodus/lib.js)
task smoke-kochmodus     # Playwright-Rauchtest im Container (podman)
task serve               # dann http://localhost:3000/kochmodus/?r=schema/beispiele/thit-kho-trung.json
```

Einzige Abhängigkeit: `jsonschema` (siehe `tools/requirements.txt`).

## Status

| Datum | Stand |
|---|---|
| 2026-10-05 | Plan freigegeben. AP0 (Festlegungen, Werkzeug-Skelett) und AP1 (Schema v0.1, thit-kho Minimum + Anreicherung) umgesetzt. Checks A–D grün, Mutationstest 11/11 erkannt. |
| 2026-10-05 | AP2 umgesetzt: `tools/recipes/shopping.py` berechnet `derived.quantities` und `derived.shopping`, `cli derive` schreibt sie ins JSON (reproduzierbar bis auf `generatedAt`, Hash-Prüfung gegen veraltete Blöcke), `cli shopping` rendert Markdown im heutigen Format, Check K vergleicht mit der Original-Einkaufsliste. |
| 2026-10-05 | **Phase 3/4 begonnen: Konvention + Parser.** `REZEPTFORMAT.md` (eigenständige Spezifikation mit Gerüsten), `tools/recipes/parse.py` (deterministisch, 13 Regel-Tests gegen die Gerüste), `cli build/lint`, `task build/validate` auf die gebauten JSONs neben den `.md`. **AP-C:** `gerichte/thit-kho-trung.md` auf die Konvention normalisiert (Inhalt unverändert: Token-Multiset identisch, nur Einkaufsliste nach Läden gruppiert, Meta-Zeilen, zwei Schätz-Dauern); `gerichte/thit-kho-trung.json` wird gebaut, Checks A–L grün, K 16/16. Parität gegen die Hand-Annotation: 86 % gesamt, **96 % auf Inhaltsfeldern** (Dosierungen 23/23, Rettung, Grenzen 8/9, Warum 8/9); beabsichtigte Unterschiede: Slugs aus Titeln, umgebaute Überschriften, Laden-Zuordnung, Schätz-Dauern, Kurzansicht = erster Satz. Nicht ableitbar und akzeptiert: Erkennungszeichen jenseits von „bis …", `attended` nur per Heuristik. |
| 2026-10-05 | **November-Menü vollständig modelliert** (User: „damit man es ehrlich testen kann"). Alle vier Gänge als Tasks/Produkte/Schritte: 60 Schritte (58 nummeriert + 2 Anrichten), 84 Dosierungen, 22 Produkte, 23 Erzeuger→Verbraucher-Paare, 28 Zeitplan-Einträge (5 abgeleitet), 53 Zutaten. Konvertierung als versioniertes Skript `tools/convert/menue_november.py` (Verbatim-Schnitt + Hand-Annotation). Zwei Format-Anpassungen am Markdown (Schritte, die über mehrere Tage liefen, aufgetrennt; Inhalt unverändert, eigener Commit). Kochen-Ansicht ordnet nach Ablauf, optional nach Gang. |
| 2026-10-05 | **AP-E: November-Menü normalisiert und per Parser gebaut.** `menues/menue-november.md` auf die Konvention (60 Schritte als `**N. Titel (Dauer)**` mit Meta-Zeilen, Komponenten-Labels mit Zeit-Grammatik, Einkaufsposten `Menge Name`, Zeitplan-Einträge nennen Schritt-/Komponentennamen; Saison-Phase, drei `[x]`-Vorratsposten und vier Schätz-Dauern ergänzt). Inhaltstreue: alle Zahl+Einheit-Token der alten Fassung erhalten, 50 Zeilen nur umformatiert. `menues/menue-november.json` gebaut: Checks A–L grün, K 44/44, alle 60 Schritte im Zeitplan platziert, Rauchtest grün (Plan 9×5, 32 Einträge, 55 Posten). Parität gegen `schema/beispiele/menue-november.json`: Schritttexte 58/58, Kurzansicht 57/58, Dosierungen 58/60 (Text) bzw. 57/60 (Wert), Rettung 53/58, Dauern 51/58, Zutaten pro Schritt 45/58 — zusammen 87 % auf Inhaltsfeldern (1294/1491). **Unter 90 % liegen nur Ermessensfelder:** Warum 19/58, Grenzen 21/58, Erkennungszeichen 33/58, Timer 36/58 — die Hand-Annotation hatte Klammern, Gedankenstriche und Teilsätze zitiert, die Konvention kennt nur Kursiv am Ende, Fett und „bis …“. Entscheidung offen: akzeptieren (Anzeige-Annotationen) oder Markdown dafür umbauen. Parser-Lücken aus dem Lauf geschlossen (Zutaten-Phrasen und Komposita, ID-Kollision, Mengen in Klammern, Komma-Titel in `nach …`, Zeitplan-Zuordnung über Phrasen/Segmente/Gang). `tools/convert/menue_november.py` gelöscht (L16). |
| 2026-10-05 | **Entscheidung zu den Ermessensfeldern (L18):** Parität von Warum/Grenzen/Cues akzeptiert, Nachziehen bei Gelegenheit. Timer-Übergenerierung behoben (Haltbarkeit, Vorlauf, Obergrenze sind keine Timer): November 36 → 40/58, Rest sind Garzeiten, die die Hand-Annotation ausgelassen hatte. |
| 2026-10-05 | **AP5: Hochzeitstag normalisiert und per Parser gebaut.** Neu in Konvention und Parser: Zeitplan nach Uhrzeit (`17:30 Uhr (1,5h vorher)`, `19:15 Uhr — Nach dem Amuse`) mit Anker aus „… Dinner um 19:00 Uhr“, Phase `N Tage vorher`, Servierzeit eines Gangs = letzte Uhrzeit-Phase mit seinen Einträgen, gangübergreifende Einträge (Ente startet während des Amuse). Dazu Parser-Lücken geschlossen: Rest-Segment neben einem getroffenen Titel trifft keine Komponente mehr, `→` trennt Segmente, `Eigelb` als Einheit dosiert die Eier, Umlaut-Plural (Apfel/Äpfel). Check H rechnet die Koch-Belegung pro Schritt statt pro Task (verteilte Tasks belegten sonst den ganzen Nachmittag). Siehe Messwerte AP5. |
| 2026-10-05 | **Phase 2b, AP4 umgesetzt** (Entscheidungspunkt auf User-Entscheidung übersprungen: erst ein großes Menü ist der echte Test, bei bekannten Rezepten entsteht kaum Feedback). Schema v0.2: Menü/Gänge/Zeitplan/Ressourcen/Constraints. `menue-november.json`: Rahmen, Gang 2 vollständig (8 Tasks, 7 Produkte, 18 Steps), Stubs für 1/3/4, 50 Zutaten, 8 Phasen + 24 Einträge. `timing.py` mit Checks E–H, L. Kochmodus menüfähig mit Plan-Raster. Siehe Messwerte AP4. |
| 2026-10-05 | **Durchstich** gebaut: `kochmodus/` (statische Seite, vanilla JS, `marked` vom CDN wie Docsify). Ansichten Kochen (Kurzansicht + Details mit Hervorhebung, Abhaken, Timer mit Endzeit im localStorage, Ereignisse, Notiz pro Schritt, Export im `learnings.notes[]`-Format, Voraussetzungen aus `after`), Einkauf (aus `derived.shopping`, abhakbar, skaliert) und Lesen (Sektionen in Dokumentreihenfolge). Skalieren ersetzt Spans inline (L11) mit Rundung nach Einheit (`kochmodus/lib.js`). 10 Node-Tests, Playwright-Rauchtest im Container grün. **Nächster Schritt: Thịt kho damit kochen, dann Entscheidungspunkt vor Phase 2b.** |
| 2026-10-05 | AP3 umgesetzt: zweite unabhängige Konvertierung von thit-kho durch einen frischen Agenten (nur SCHEMA.md + Schema + Quelle), `cli diff` misst Übereinstimmung pro Feld. Ergebnis: alle verbatim-nahen Felder 100 %, Ermessensfelder streuen (siehe Messwerte). Daraus Anleitung v2 mit regelbasiertem `action` (= erster Satz, Check C erzwingt das), festem Warengruppen-Vokabular, klaren Regeln für `priority`/`optional`/`note`/`scale`. Phase 2a damit abgeschlossen; nächster Schritt: Durchstich (Kochmodus-Seite mit thit-kho). |

## Phase 1: Testsammlung und harte Stellen

| # | Datei | Umfang | Phase | Harte Stellen (Zeile) |
|---|---|---|---|---|
| 1 | `gerichte/thit-kho-trung.md` | vollständig | 2a | Z. 3 Meta-Zeile mit nacktem `~` · Z. 12 Schweinebauch-Menge nur in der Einkaufsliste, nicht im Schritt · Z. 14 + 23 Zucker auf zwei Posten verteilt · Z. 21 Querverweis auf anderes Rezept in kursiver Notiz · Z. 22 zwei Zutaten in einem Posten · Z. 33 „jeweils die Hälfte" · Z. 39 „3 EL Zucker" zweimal im Schritt · Z. 45 Eier erneut genannt (reuse) · Z. 48 „Schuss Kokoswasser" ohne Zahl · Z. 64/70 Learnings widersprechen Schritt 6 |
| 2 | `menues/menue-november.md` | Rahmen + Gang 2 vollständig, Gänge 1/3/4 als Stubs | 2b | Z. 53–122 Einkaufsliste mit Gang-Zuordnung, `[x]`, Sammelposten · Z. 126–201 Gang 1 mit Weg A/B · Z. 205–209 Meta-Block mit `\|` · Z. 227 Hold-Fenster im Fett-Label · Z. 229–305 Nummerierung 1–17 über Komponentenblöcke · Z. 242 Fallback in Klammern · Z. 252–262 zwei Produktzustände (Praline roh/gewälzt), „≤30 Min. vor dem Anrichten" · Z. 266 „über Nacht" · Z. 271 „1–2 h antrocknen" = hold.min · Z. 277–280 Fallback-Rezeptur · Z. 287 „hält bis 2 h" · Z. 291 Technik-Verweis · Z. 297–305 zwei Pfannen, Kerntemperatur-Cue · Z. 315–324 Profi-Tipps-Blockquote · Z. 326–337 Offen-Liste · Z. 614–645 Zeitplan-Skelett mit `·` und Gang-Offsets · Z. 642 Ofen-Plan als Prosa · Z. 710 ff. Mengen-Check gangübergreifend |
| 3 | `menues/menue-hochzeitstag.md` | Menükarte, Gang-Stubs, Zeitplan (Z. 318–388), Learnings | 2b | Z. 320 Anker „Dinner um 19:00" nur in Prosa · Z. 322–335 Tage-Phasen ohne Uhrzeit · Z. 337–361 absolute Uhrzeiten mit Offset in Klammern · Z. 350 Logistik „Tisch decken" · Z. 363–366 Ereignis-Phase, Ente startet während Amuse (gangübergreifend) · Z. 374 „ruhen lassen, während Gäste essen" · Z. 377 Kinder-Split der Sauce · Z. 345/353 Ofen 80 °C Warmhalten |
| 4 | `schwangerschaft/dal-baukasten.md` | vollständig | 2b | Z. 3 Anker-Link im Intro · Z. 29–50 Schnellkochtopf-Fassung mit Ersetzungen pro Variante (Z. 43) · Z. 53–105 Einkaufsliste mit Pflichtblock + „Nur Variante A–D" · Z. 57 Knoblauch nach Verwendung aufgeschlüsselt · Z. 67 „entfällt bei Kachumber" · Z. 110–134 Schritte als `###` · Z. 122–130 Teilen + parallele Tadka Erwachsene/Kind · Z. 148–181 Delta-Varianten („Schritt 1–4 unverändert", „Ersetzt Schritt 1 komplett", „Ersetzt das Grundrezept komplett") · Z. 201–206 Countdown-Zeitplan `–0:50` … `0:00` |
| 5 | `backen/vollkornbroetchen.md` | vollständig | 2b | Z. 3 drei Zeitphasen im Intro · Z. 38–56 Gebinde ≠ Bedarf („1 kg … Bedarf 600 g") · Z. 64–84 Matrix-Tabelle Mehl × Weg mit Prozess-Parametern · Z. 88 Skalierungsregel mit Ausnahme (Hefe 0,1 g) · Z. 109 inline Varianten „(Weg A; 6 g für Weg B, 9 g für Weg C)" · Z. 111 bedingte Logik Teigtemperatur · Z. 114 Fenstertest, Reservewasser · Z. 132–139 Weg A/B/C mit „Weiter bei Schritt 9/10" · Z. 146 Fingertest-Entscheidungsbaum · Z. 168–177 absoluter Zeitplan, zweite Session „Backen aus dem Frost" · Z. 186–190 Fehlerbild-Tabelle |

## Leitentscheidungen

- **L1 Markdown bleibt einzige Quelle.** JSON entsteht parallel (von Hand/LLM), ändert
  keine `.md`; `task sidebar` / `task learnings` und die Docsify-Plugins bleiben unberührt.
- **L2 Verbatim-Prinzip.** Schritte (`text`, `heading`), Prosa-Sektionen (`markdown`),
  Learnings (`summary`, `details`), Intro und Titel tragen den Quelltext wortgleich,
  inklusive `\~`, Fett, Kursiv, Docsify-Dialekt.
- **L3 Annotationen sind Zitate.** `why`, `cues[]`, `rescue`, `limits[]`, `title`,
  `amount.text`, `timers[].text`, `temps[].text`, `*.source`, `notes[].text` müssen nach
  Normalisierung (Tilde-Escape auflösen, `*` entfernen, Whitespace zusammenziehen)
  Substring der Quelle sein. Check C.
- **L4 Dokument-Reihenfolge ist Daten.** Rezept = Metadaten + geordnete `sections[]`.
  Typisiert: `tasks`, `learnings`, `todo`, `shopping` (nur Platzhalter), ab Phase 2b
  `courses`, `schedule`. Alles andere ist `markdown` mit `tags`.
- **L5 Zwei Pflicht-Ebenen.** *Minimum* = Schema-`required`. *Anreicherung* = alles
  Optionale, nur wo der Text es hergibt. Siehe Tabelle unten.
- **L6 Abgeleitetes ist erlaubt, aber markiert.** Was nicht wörtlich in der Quelle
  steht (außer IDs, normalisierten Zahlen/Dauern) trägt `actionDerived: true`,
  `spanForm: "derived"` oder `derived: true`. Check D zählt sie. Ziel für neue Rezepte
  nach Schreibkonvention: null.
- **L7 Schreibkonvention für Schritte.** Erster Satz (oder führender Satzblock) = reine
  Handlung mit Mengen; danach Cues und Grenzwerte; kursiver Schluss = Warum/Rettung.
  `action` ist dann ein verbatim-Präfix von `text`. Wo das keine brauchbare
  Kurzansicht ergibt, eine **mengenfreie** Kurzfassung mit `actionDerived: true`.
  Zahl+Einheit in einer abgeleiteten `action` ist ein Fehler, außer ein
  `StepIngredient` trägt `actionOccurrence`.
- **L8 Dauern als ISO 8601.** `PT20M`, `PT3H30M`, `P2D`. Konvention: `PnD` =
  Kalendertage, `PTnH` = Uhrzeit-Stunden; `P1D ≠ PT24H`.
- **L9 Graph ↔ Platzierung getrennt** (Phase 2b). Tasks/Produkte/Hold/Claims sagen
  *was* und *wie lange*; `schedules[]` sagt, *wann der Autor es tun will*.
- **L10 Einkaufsliste und Mengen-Check sind abgeleitet, in Python.** Quelle sind
  `ingredients[]` (Laden, Gebinde, Vorrat, Priorität) und `step.ingredients[]`
  (Dosierung pro Verwendung). `cli derive` schreibt `derived.shopping` und
  `derived.quantities` ins JSON; der Browser zeigt nur an und skaliert. Keine zweite
  Aggregationslogik in JS. Die Markdown-Abschnitte sind nur Soll-Vergleich (Check K/L).
  `step.ingredients[]` ist deshalb Minimum. `reuse: true` markiert eine Zutat, die
  schon dosiert wurde (wird skaliert, nicht summiert).
- **L11 Mengen als Text-Spans.** `amount.text` ist der Span, wie er in `step.text`
  steht (Zahl + Einheit, bei Mehrdeutigkeit plus Nomen: „2 fein gehackten Schalotten").
  Der Renderer ersetzt den führenden Zahlenteil beim Skalieren. Kommt der Span
  mehrfach vor, ist `occurrence` Pflicht. Steht die Menge nicht im Schritt, dann
  `spanForm: "derived"` und der Text muss anderswo in der Quelle stehen.
- **L12 Stabile Slugs.** `step.id`, `task.id`, `ingredient.id`, `product.id` sind
  Slugs aus Titel oder Verb+Objekt (`karamell`, `pickle-und-reis`), rezeptweit
  eindeutig, nie numerisch, nie aus der Nummer. Die Nummer ist nur `label`. Slugs
  werden einmal vergeben und nie umbenannt (Abhak-Zustand, Notizen, Verweise).
- **L13 Feedback-Ziel.** `learnings.notes[]` mit optionalem `ref: step:<slug>|task:<id>|
  product:<id>`, `date`, `status: open|applied`. Ohne `ref` gilt die Notiz dem ganzen
  Rezept. Der Kochmodus erfasst **eine allgemeine Notiz** pro Rezept/Menü (User-
  Entscheidung 10/2026: Notizen pro Schritt lohnen nicht, das Einarbeiten ist ohnehin
  Rezeptarbeit) und exportiert sie als Markdown-Block unter `## Learnings`.
- **L18 Ermessensfelder werden nur aus Markierungen gelesen.** Warum (kursiver
  Schlusssatz), Grenzen (fett) und Erkennungszeichen („bis …") kommen ausschließlich aus
  der Konvention; unmarkierte Begründungen in Klammern oder Nebensätzen bleiben Text
  und werden nicht geraten (Entscheidung User, 10/2026, nach der Parität des
  November-Menüs). Sie werden nachgezogen, wenn ein Rezept ohnehin bearbeitet wird.
  Timer dagegen sind keine Ermessensfrage: eine Zeitangabe ist kein Timer, wenn sie
  Haltbarkeit („hält bis 2 h"), Vorlauf („1–2 h vor Service") oder Obergrenze
  („≤ 30 Min.") beschreibt.
- **L17 Konvention ist die Schreibsyntax.** `REZEPTFORMAT.md` beschreibt alles, was der
  Parser liest; Abhängigkeiten über Titel, nie über Nummern; Slugs aus Titeln; JSON
  neben der `.md`, per `task build` erzeugt und committed. Die handannotierten
  `schema/beispiele/*.json` bleiben eingefrorenes Soll für die Parität (`cli diff`),
  werden aber nicht mehr gegen die Quelle validiert.
- **L16 Keine Konvertierungsskripte mehr.** Bis AP-E lag die Modellierung des
  November-Menüs in `tools/convert/menue_november.py` (verbatim-Schnitt plus Hand-
  Annotation). Seit die Konvention (L17) steht, ist das Markdown selbst die Quelle der
  Modellierung; das Skript ist gelöscht, `cli build` ersetzt es.
- **L15 Stub-Gänge.** Ein Gang, der noch nicht modelliert ist, ist ein `Recipe{kind:
  course}` mit genau einer verbatim-`markdown`-Sektion. Seine Zutaten tragen `buy`
  (Kaufmenge aus der Liste) statt Dosierungen; Check K wertet das als passend,
  Check E/L prüfen nur modellierte Gänge. So wächst ein Menü gangweise.
- **L14 Ablage.** `schema/recipe.schema.json`, `schema/beispiele/*.json`,
  `tools/recipes/*.py`, `tools/requirements.txt`, dieses `SCHEMA.md` im Root.
  Keine `.md` unter `schema/` oder `tools/` (der Sidebar-Generator iteriert `*/*.md`).

## Löffel und Milliliter (Anzeige-Regel)

Rohwerte bleiben wie in der Quelle (`value`/`unit`). Für die Anzeige gilt, umgesetzt
in `tools/recipes/spoons.py` und ab Phase 5 im Renderer:

- Löffelangaben (TL/EL) bleiben Löffel. Hat die Zutat einen `unitHint` (z. B.
  EL → g, Faktor 12), steht der metrische Wert in Klammern: „5 EL (≈ 60 g)".
- Metrische Werte aus US-Umrechnungen (14,79 ml = 1 EL, 4,93 ml = 1 TL, Vielfache
  in halben Schritten, ±1 %) werden als Löffel gezeigt, der Rohwert in Klammern:
  „14,7 ml" → „1 EL (14,7 ml)". In der Einkaufsliste nur diese Fälle; in der
  Kochansicht optional auch glatte 15/5-ml-Vielfache („45 ml" → „3 EL (45 ml)").
- `amount.display: {value, unit}` setzt die Anzeige explizit und hat Vorrang.
- Beim Skalieren wird der Rohwert skaliert, die Anzeige neu abgeleitet.

Stand im Repo (10/2026): keine 4,9-/14,7-ml-Angaben vorhanden; bestehende Rezepte
schreiben „1 EL (15 ml)" oder „15 g (1 EL)". Die Regel ist für Importe aus
US-Quellen vorgesehen.

## Minimum vs. Anreicherung

| Ebene | Felder |
|---|---|
| **Minimum** (Schema `required`) | Recipe: `id`, `kind`, `title`, `yields`, `ingredients`, `sections` · Ingredient: `id`, `name`, `store` · Task: `id`, `name`, `steps` · Step: `id`, `label`, `text`, `action`, `ingredients` · StepIngredient: `ref`, `amount.text` · learnings: `cooked`, `summary` |
| **Anreicherung** | `intro`, `times`, `equipment`, `status`; Step: `heading`, `title`, `attention`, `duration`, `timers`, `temps`, `endCondition`, `cues`, `why`, `rescue`, `limits`, `technique`, `parallel`, `equipment`; Amount: `value`, `max`, `approx`, `unit`, `per`; Ingredient: `group`, `buy`, `inStock`, `pantry`, `priority`, `optional`, `fallback`, `unitHint`, `scale`; Task: `intro`, `phaseHint`, `duration`, `produces`, `consumes`; learnings: `details`, `notes` |

## Konvertierungs-Anleitung (v2, nach AP3)

Regeln, die der Validator erzwingt, sind mit **[C]**/**[D]** markiert. Alles andere ist
Konvention; wo zwei Konverter in AP3 abgewichen sind, steht jetzt eine feste Regel.

1. **Kopf.** `id` = Pfad ohne `.md`. `title` = H1 ohne `🚧`; `status: wip` bei `🚧`.
   `intro` = alles zwischen H1 und erster `##`, verbatim. `yields` aus dem Titel.
   `times`/`equipment` aus der kursiven Meta-Zeile, soweit vorhanden.
2. **Sektionen in Dokumentreihenfolge** **[B]**. `## Einkaufsliste` → `{type: shopping}`
   (Platzhalter). `## Zubereitung`/`## Rezept` → `tasks`. `## Learnings` → `learnings`
   (`summary` = Fließtext bis zur ersten `###`, `details` = Rest ab `###`, verbatim).
   `## To-do`/„Offen"-Listen → `todo`. `## Mengen-Check` entfällt. Alles andere →
   `markdown` verbatim mit `tags`.
3. **Task.** Einfaches Rezept = genau ein Task mit `id: "main"`, `name` = Gerichtname.
4. **Schritte.** Ein Markdown-Schritt = ein Step, nie splitten. `heading` = Überschrift-
   zeile verbatim inklusive `**`. `label` = Nummer. `title` = Zitat aus `heading` ohne Nummer und
   Dauer **[C]**. `text` = ganzer Absatz verbatim. `duration` **nur** aus der
   Überschrift (`source` = die Klammerangabe); Dauern im Text werden `timers`, nie
   `duration`. `parallel: true` bei „parallel" in der Überschrift.
5. **`action` — die Kurzansicht.** Intention: Wer nur `heading` + `action` liest,
   kann den Schritt korrekt ausführen, wenn er das Rezept kennt. Also: Handlung,
   Zutat, Menge, Gerät, Hitze. **Nicht** hinein gehören Erklärung (Warum),
   Erkennungszeichen (Cues), Grenzwerte und Rettung; die stehen in der Vollansicht
   und werden dort hervorgehoben. Praktisch: der kürzeste Präfix aus **ganzen
   Sätzen** **[C]**, der die Kernhandlung enthält. Meist ist das der erste Satz
   (Schritt 4: „Zucker … schmelzen lassen, nicht rühren"), manchmal zwei (Schritt 1:
   würfeln **und** blanchieren, die Überschrift heißt so), bei einem Schritt ohne
   Annotationen auch der ganze Text (Schritt 8: Pickle, Gurke, Reis). Wäre der nötige
   Präfix fast der ganze Text, obwohl er Annotationen enthält (Schritt 6: Schmoren
   steht erst im fünften Satz), dann eine **mengenfreie** Kurzfassung mit
   `actionDerived: true`. Der Validator meldet als Hinweis, wenn ein verbatim-Präfix
   über 70 % eines annotierten Textes umfasst.
6. **Slugs** **[D]**: Step aus `title` (ohne Füllwörter, `&` → `und`, Umlaute
   ae/oe/ue/ss): „Schnell-Pickle & Reis" → `pickle-und-reis`. Zutat = erstes
   Hauptnomen des Einkaufspostens in der Schreibweise der Liste: „2–3 frische rote
   Chilis" → `chilis`, „Frühlingszwiebeln oder Koriander" → `fruehlingszwiebeln`.
7. **Dosierungen (StepIngredient)** **[C]**. Genau dann ein Eintrag, wenn im Schritt
   ein Mengen-Span steht: Zahl + Einheit/Nomen („3 EL Zucker", „6 Eier", „½ Salat-
   gurke") oder Mengenwort („reichlich Pfeffer", „Prise Salz", „Schuss Kokoswasser";
   dann `unit` = Mengenwort, kein `value`). Reine Nennungen ohne Menge („das
   marinierte Fleisch", „Fleisch mit …") werden **nicht** erfasst. Wiederholt ein
   Schritt eine schon dosierte Zahl („Die 6 Eier") → `reuse: true`. Span bei
   Mehrdeutigkeit um das Nomen verlängern; kommt er trotzdem mehrfach vor →
   `occurrence`. Markdown im Span bleibt drin („2–3 **ganze** Chilis"). Menge nur in
   der Einkaufsliste → am ersten verwendenden Schritt mit `spanForm: "derived"`.
   `unit: "Stück"` für Stückzahlen (auch Zehen, Eier); ein `value` ohne `unit` lehnt das
   Schema ab. Der Span wird roh in `step.text` gesucht (inkl. Markdown-Marker).
8. **Zutaten (Rezept-Ebene).** Ein `Ingredient` pro Zutat; Sammel- und „A + B"-Posten
   aufteilen; „A oder B" bleibt **eine** Zutat. `name` = Posten ohne Mengen- und
   Klammer-/Kursivteil. `note` = Klammer- oder Kursivzusatz des Postens verbatim.
   `storeNote` = Beschaffungs-Prosa aus `## Beschaffung`. `prep` **nicht** setzen
   (Vorbereitung steht im Schritt). `store` aus `## Beschaffung`, sonst CLAUDE.md-
   Einkaufsquellen; Default „Aldi / REWE". `group` aus dem festen Vokabular:
   *Obst & Gemüse · Fleisch & Fisch · Milchprodukte & Eier · Trockenwaren ·
   Würzmittel & Gewürze · Getränke · Tiefkühl · Sonstiges*; bei `store: Vorrat`
   keine Gruppe. `pantry: true` für Salz, Pfeffer, Wasser, Öl zum Braten.
   `optional: true` bei „Optional:"/„optional"; `priority` **nur**, wenn die Liste ein
   Label trägt (Pflicht/Empfehlenswert/Optional/„empfohlen"), sonst weglassen.
   `scale` **nur** für Ausnahmen (`fixed` Bratfett, `note` mit `scaleNote`);
   Default-Verhalten (Stück → runden, Mengenwort → nicht skalieren) leitet der
   Generator ab. `fallback` aus Learnings/Notizen, kurz.
9. **Annotationen** nur als Zitate (L3) **[C]**: `cues` = Erkennungszeichen („bis …",
   „tief bernsteinfarben"), `limits` = Grenzen/Warnungen (mit „Vorsicht:"-Präfix,
   falls vorhanden), `why` = Begründung (kursiver Schlusssatz, ganz, mit Punkt),
   `rescue` = „wenn schiefgeht". Satzgrenzen ganz übernehmen, nicht in Teilphrasen
   splitten. `step.equipment` nicht erfassen (steht im Text, Rezept-Ebene reicht).
10. **`attention`.** `active` = Hände dauernd am Werk (schneiden, kneten, anrichten);
    `attended` = auf dem Herd, Blick nötig, Hände zwischendurch frei (Karamell,
    Anbraten, Reduzieren, Eier kochen); `passive` = man kann weggehen (Schmoren,
    Marinieren, Ziehen lassen, Auftauen). Im Zweifel `attended`.
11. **Learnings-Notizen** **[D]**: jeder Bullet der `### Details` wird eine Note;
    `text` = Bullet ohne das fette Label, verbatim; `ref` auf den Schritt, den der
    Bullet ändert (Topfwahl → Schritt mit dem Topf); `date` = „Gekocht MM/JJJJ";
    `status: open`, solange der Rezepttext die Erkenntnis nicht umsetzt.
12. **Abhängigkeiten und Zeitanker** **[D]**. `after: ["step:…"]` nennt die Schritte,
    die abgeschlossen sein müssen. Fehlt das Feld, gilt der vorhergehende Schritt des
    Tasks; `[]` heißt „keine Voraussetzung" (Eier kochen, Pickle). Daraus leitet die
    Planung Parallelität ab; `parallel` bleibt nur verbatim-Marker der Überschrift.
    `start: {ref: "step:x:end", offset: {min, max}}` verankert einen Schritt relativ
    zu Start/Ende eines anderen („letzte 20–30 Min." des Schmorens → `-PT30M`/`-PT20M`
    vor `step:schmoren:end`). `events[]` sind Zeitpunkte *innerhalb* eines Schritts
    („nach ~60 Min. Eier wenden"), keine Timer. Fehlt eine Dauer in der Quelle und wird
    sie für die Planung gebraucht („Reis wie gewohnt kochen"), darf sie geschätzt
    werden, dann `estimated: true` (L6).
13. **Zeitangaben** nach dieser Grammatik:

| Quellphrase | Ziel | Regel |
|---|---|---|
| `45 Min.`, `\~45 Min.` | `duration.typical: PT45M` | Zirka/Escape ignorieren |
| `3–3,5 Std.`, `90–120 Min.` | `{min, max}` | U+2013, Dezimalkomma |
| `30 Sek.` | `PT30S` | |
| `über Nacht` | `{min: PT8H, max: PT14H}` + `source` | feste Konvention |
| `Vortag`, `T-1`, `Vormittags` | `task.phaseHint` / `phase` | **nie** Hold oder Dauer |
| `bis 2 Tage vorher`, `hält bis 2 h`, `≤ 30 Min. vor dem Anrichten` | `product.hold.max` | Haltbarkeit, nicht Dauer |
| `hält ewig` | `hold.max: null` + `note` | nie Zahl erfinden |
| `1–2 h offen antrocknen`, `2–3 h marinieren` | `hold {min, max}` | Ruhen = Hold-Min |
| `\~20 Min. vor dem Gang` | `entry.at {ref: course:…:serve, offset: -PT20M}` | Offset, nicht Dauer (2b) |
| `T−3:30`, `T−27`, `–0:50`, `+0:20` | `-PT3H30M`, `-PT27M`, `-PT50M`, `serve: +PT20M` | alle Minus-Zeichen gleich (2b) |
| `(25 Min., passiv)`, `dabeibleiben!` | `attention: passive` / `attended` | |
| `bei 60–62 °C raus`, „nach Thermometer" | `endCondition {temperature}`, Dauer nur Schätzung | Timer ist Richtwert |

## Checks

| # | Prüft | Art | Ab |
|---|---|---|---|
| A | JSON Schema (Pflichtfelder, Enums, ISO-Dauern, Slug-Muster) | fail | AP0 |
| B | B1 jede `##`-Sektion der Quelle (außer generierte) hat eine Section gleichen Titels · B2 Multiset aller Zahl+Einheit-Token der Quelle (ohne Einkaufsliste/Mengen-Check) = Multiset der verbatim-Felder · B3 jede Quellzeile ≥ 20 Zeichen ist verbatim im JSON | fail | AP1 |
| C | Zitat-Treue aller Annotationen (L3); nicht-derived `action` ist Präfix von `text`; `title` in `heading`; exakte Spans eindeutig oder mit `occurrence`; abgeleitete `action` mengenfrei | fail | AP1 |
| D | Slugs gültig und rezeptweit eindeutig; `ref`, `consumes` (`product:`-Präfix), `notes[].ref`, `todo[].ref`, `after`, `start.ref` lösen auf; Schritt-Graph (inkl. Vorgänger-Default) ohne Selbstbezug und Zyklen; Report der derived-Felder und der Zutaten ohne Dosierung | fail | AP1 |
| K | Status des gespeicherten `derived`-Blocks (fehlt → Hinweis, veraltet → Fehler); Vergleich immer gegen eine frische Ableitung; jeder Original-Posten der `## Einkaufsliste` (Teile an ` + ` getrennt) findet eine Zutat per Namenswort; Menge des Postens (inkl. `900 g – 1 kg`, `4–5 EL`, `½`) gegen `derived.quantities.total`; Gebinde (`buy`) zählt als passend; Zutaten nur im JSON als Info | fail bei Posten ohne Zutat oder veraltetem Block, Abweichungen als Report | AP2 |
| E–H, L | Schritt-/Zeitplan-Abdeckung, Hold-Konsistenz, Service-Intervalle, Mengen-Check | | AP4 |

**Mutationstest (2026-10-05):** 11 absichtlich fehlerhafte Kopien von thit-kho
(erfundenes Zitat, falscher `action`-Präfix, Menge in abgeleiteter `action`, fehlende
`occurrence`, geänderte Menge im Text, doppelte ID, numerischer Slug, unbekannte
Zutat, kaputte Notiz-Referenz, falsches Dauer-Format, gelöschte Sektion) werden alle
erkannt. Vor der Verschärfung von B rutschte die gelöschte Sektion durch; deshalb
sind B1 und B3 jetzt Fehler, nicht Report.

## Messwerte

### thit-kho-trung (AP1, 2026-10-05)

| Kennzahl | Wert | Bemerkung |
|---|---|---|
| Schritte | 9 | ein Task `main` |
| `action` verbatim-Präfix / abgeleitet | 8 / 1 | Schritt 6 (Schmoren): der Handlungsblock wäre 85 % des Textes, daher mengenfreie Kurzfassung |
| Dosierungen `spanForm: exact` / `derived` | 24 / 1 | derived: Schweinebauch, Menge steht nur in der Einkaufsliste |
| davon ohne `value` (nicht skalierbar) | 4 | „reichlich Pfeffer", „das marinierte Fleisch", „einem Schuss Kokoswasser", „Frühlingszwiebeln/Koriander" |
| `reuse: true` | 2 | Fleisch in Schritt 5, Eier in Schritt 6 |
| `occurrence` nötig | 1 | „3 EL Zucker" steht in Schritt 4 auch in der Rettung |
| Zahl+Einheit-Token Quelle / JSON | 33 / 33 | |
| Zutaten | 17 | aus 14 Einkaufsposten (zwei geteilt, Wasser und Salz ergänzt) |
| Zutaten ohne Dosierung in Schritten | 0 | |

**Befunde für Phase 3 (Syntax):** (1) Mengen müssen im Markdown als Span markierbar
sein, inkl. Nomen zur Eindeutigkeit und einem Mehrdeutigkeits-Zähler oder einer
expliziten Markierung der Dosierungsstelle. (2) „reuse" braucht eine Markierung
(dieselbe Zutat, nicht summieren). (3) Mengen, die nur in der Einkaufsliste stehen,
müssen in den Schritt wandern, sonst bleibt `spanForm: derived`. (4) Der Slug muss
an der Schrittüberschrift hängen können. (5) Für die Kurzansicht genügt in 8 von 9
Fällen die bestehende Schreibweise; Schritt 6 zeigt die Grenze (viele Handlungen in
einem Schritt).

### thit-kho-trung, Ableitung (AP2, 2026-10-05)

| Kennzahl | Wert | Bemerkung |
|---|---|---|
| Original-Posten → Zutat-Zuordnungen | 14 → 17 | zwei Posten enthalten je mehrere Zutaten |
| passend / abweichend | 15 / 2 | beide Abweichungen = Zucker: Original 4 EL + 1 EL in zwei Posten, generiert 5 EL in einem |
| Zutaten nur im JSON | 1 | Wasser (1 EL fürs Karamell, `pantry`) |
| Zutaten ohne summierbare Menge | 3 | Pfeffer „reichlich", Frühlingszwiebeln, Kokoswasser-„Schuss" zusätzlich zur Hauptmenge |
| Reproduzierbar | ja | zweimal `derive` identisch bis auf `generatedAt` |

**Härtefälle, Stand nach AP2:** Sammelposten (aufgeteilt in Zutaten) ✓ · Dosierung ohne Zahl (`unitless`, erscheint ohne Menge) ✓ · Spannen-Summen (`4–5 EL`) ✓ · `kg`/`l` werden auf `g`/`ml` normiert, Anzeige dann `900–1000 g` statt `900 g – 1 kg` (kosmetisch, offen) · gemischte Einheiten pro Zutat (`unitHint`, `unitMixed`) implementiert, in thit-kho nicht vorgekommen · Gebinde ≠ Bedarf (`buy`) implementiert, erst in vollkornbrötchen testbar · Varianten-abhängige Posten erst in AP6.

**Rendering-Entscheidungen** (`cli shopping`): `###` pro Laden in Besuchsreihenfolge (Online, Buhara, Asialaden, Selgros, REWE Center, Aldi/REWE, Vorrat), darunter `**Warengruppe:**`, Einträge `- [ ] Menge Name, prep *(note)*`, `Optional:`-Präfix, `[x]` bei `inStock`. Das 📲-Export-Plugin würde auf dieser Ausgabe unverändert funktionieren.

### menue-november, vollständig (AP4, 2026-10-05)

| Kennzahl | Wert | Bemerkung |
|---|---|---|
| Schritte | 60 (10 + 19 + 21 + 10) | je Gang 1–N nummeriert plus Anrichten bei Gang 2 und 3 |
| Tasks / Produkte / Kanten | 25 / 22 / 23 Erzeuger→Verbraucher | alle über Phasen konsistent (Check G) |
| Dosierungen exact / derived | 84 / 0 | `times` für Rotwein in 3 Schüben und je-Pfanne-Angaben |
| Zutaten | 53 aus 42 Posten | 12 nur im JSON (Vorrat: Salz, Wasser, Öl, gebrühter Espresso, Sirup …) |
| Check K | 43 / 43 passend | |
| Check F | 23 / 23 Segmente, 13 mit Task, 5 abgeleitet | Saison-Teil, Concassé, Grundwürzung, Pralinen wälzen, Anrichten Gang 3 |
| Check L | 13 / 20 Zellen passend, 7 Hinweise | alle Hinweise = gemischte Einheiten (Limette Stück vs. ml Saft, EL vs. g), Pro-Person-Angaben oder Sammelzeile „Zucker / Dextrose" |
| Check H | 3 Warnungen | Anrichten Gang 2 +0:22 vs. +0:20; Dessert +1:57 vs. +1:45 (Temperieren beginnt erst bei −15); Limette 7 statt ≤ 5 Min. |
| Token Quelle / JSON | 249 / 249 | |

**Markdown-Anpassungen (Format, Inhalt unverändert):** Gang 2 Schritt 9 (auftauen am
Vortag) und 10 (auslösen am Tag) getrennt; Gang 3 Schritt 8 (passieren, Fettdeckel) und
9 (am Tag reduzieren) getrennt, der Montier-Satz in den Abend-Schritt 20 verschoben, der
vorher nur „Jus montieren (Schritt 8)" sagte. Regel daraus: **ein Schritt gehört zu
einer Phase**; läuft ein Schritt über Tage, wird er in der Quelle geteilt.

**Was die Vollmodellierung gezeigt hat:** (1) Der Zeitplan-Skelett-Text deckt nur die
Hälfte der Tasks ab; fünf Platzierungen mussten aus den Rezeptschritten abgeleitet
werden (`derived`). (2) Mengen-Check-Zellen mischen Einheiten; Check L kann sie nur
als Hinweis vergleichen. (3) Mehrfach-Dosierungen derselben Zutat mit verschiedenen
Einheiten (Limette als Stück und als Saft in ml, Kräuter als EL, Zweige, TL) sind
häufig; `unitMixed` macht das sichtbar statt zu erfinden. (4) Pro-Person-Angaben
(Shakes) brauchen in der Ableitung einen Personen-Multiplikator — offen.

### menue-november, Gang 2 (AP4, 2026-10-05)

| Kennzahl | Wert | Bemerkung |
|---|---|---|
| Zahl+Einheit-Token Quelle / JSON | 249 / 249 | Stubs und Prosa verbatim per Skript geschnitten |
| Schritte Gang 2 | 17 nummeriert + 1 (Anrichten) | Nummerierung 1–17 über 6 Komponentenblöcke, als `label` erhalten |
| Tasks / Produkte / Kanten | 8 / 7 / 5 explizite `after` + 1 `start`-Anker | Praline roh/gewälzt als zwei Produkte |
| Dosierungen exact / derived | 26 / 0 | `times: 2` für „2 Pfannen mit je 1 EL“ |
| `action` verbatim / abgeleitet | 18 / 0 | 4 Hinweise „> 70 %“ bei kurzen Schritten ohne Annotationen-Mehrwert |
| Zutaten | 50 aus 42 Posten | Gang-Zuordnung an jeder Zutat |
| Check K | 43 / 43 passend | Stub-Gänge über `buy` (Gebinde) |
| Check F (Zeitplan) | 23 / 23 Segmente, 8 mit Task, 1 abgeleitet | „Pralinen wälzen“ steht nicht im Skelett |
| Check G | 7 Erzeuger→Verbraucher-Paare konsistent | Tagesgranularität über Phasen |
| Check L (Gang 2) | 7 / 8 Zellen | Limetten: Tabelle zählt 1 Reserve mit |
| Check H | 2 Warnungen | Anrichten endet +0:22 bei Service +0:20 (Beurre blanc ab −20 Min. + Braten + Anrichten = 22 Min.); Limette 7 statt ≤5 Min. vor dem Anrichten |

**Was AP4 gezeigt hat:** (1) Das Zeitmodell trägt: Phasen mit verbatim-Einträgen
decken das Skelett vollständig ab, Hold-Fenster und Kanten lassen sich ohne
Erfindung aus dem Text holen. (2) Check H findet mit geschätzten Step-Dauern den
Zeitfenster-Konflikt, der bei der ersten Analyse von Hand auffiel. Alle Dauern der
Gang-2-Schritte außer drei sind `estimated: true` — das Menü nennt nur Summen pro
Phase („Am Abend: \~25 Min., davon \~8 à la minute“). (3) Stub-Gänge kosten nichts:
verbatim-Markdown plus `buy` an den Zutaten reicht für Einkaufsliste und Checks.
(4) Die Kochmodus-Plan-Ansicht braucht an Zeitplan-Einträgen eine Gang-Zuordnung
auch außerhalb des Service (per Schlüsselwort gesetzt, `course` am Eintrag).
(5) Offen für AP5/AP6: absolute Uhrzeiten (Hochzeitstag), Varianten.

### menue-hochzeitstag (AP5, 2026-10-05)

| Kennzahl | Wert | Bemerkung |
|---|---|---|
| Schritte | 47 (7 + 9 + 19 + 12) | aus 101 Unterpunkten zusammengefasst, Anrichten-Absätze als Schritte pro Gang |
| Tasks / Dosierungen | 19 / 41 exact, 0 derived | |
| Zutaten | 34 aus 33 Posten | 12 ohne Dosierung: Kräuter, Gewürze, Fette ohne Mengenangabe in der Quelle, Vollmilch (wird in keinem Schritt verwendet) |
| Token Quelle / JSON | 142 / 142 | Treue alt → neu: alle Token erhalten, `1/2` → `½` |
| Check K | 33 / 33 passend | |
| Check F | 42 / 42 Segmente, alle 47 Schritte platziert | 9 Logistik-Einträge bleiben Text (Tisch decken, Aperitif …) |
| Check H | 3 Warnungen | Jakobsmuscheln tupfen und Karotten glasieren überlappen um 17:30/18:15 (Schätzdauer); Entenbrust salzen läuft in den Amuse; Ente ruht bis +0:40, Hauptgang-Phase beginnt +0:35 |
| Schätz-Dauern | 33 / 47 | die Quelle nennt fast nur Teilzeiten im Text |

**Markdown-Anpassungen (Form):** Stores zugeordnet (Buhara Seafood für Jakobsmuscheln,
Rest REWE Center, Gewürze und Öle unter Vorrat). „Für das …“-Überschriften zu Komponenten
mit Zeitangabe. Die Kirsch-Jus wurde nach dem Zeitplan in Sauce-Basis (2 Tage vorher) und
Kirsch-Jus (à la minute) geteilt, ebenso Kartoffelbaumkuchen und die Scheiben am Tag.
Schritt-Titel wurden so gewählt, wie der Zeitplan sie nennt. Drei Zeitplan-Einträge haben
ihren Zusatz in Klammern bekommen, damit der Komponentenname allein steht
(„Parfait (komplett zubereiten …)“).

**Widersprüche in der Quelle (nicht aufgelöst, beim nächsten Kochen klären):** Der Zeitplan
holt das Parfait um 18:45 aus dem Gefrierfach, das Rezept sagt 10–15 Min. vor dem Servieren.
Die Kinder-Sauce wird im Zeitplan mit Butter montiert, im Rezept nur abgeschmeckt. Die
Baumkuchen-Scheiben sollen um 16:00 bei 80 °C warmgehalten werden, der Ofen wird aber
erst um 18:15 vorgeheizt.

### thit-kho-trung, Determinismus (AP3, 2026-10-05)

Zweitkonvertierung durch einen frischen Agenten mit SCHEMA.md (Anleitung v1), Schema
und Quelle. Einschränkung: Der Agent hat zusätzlich den Validator-Code gelesen und
`main` stand in den Messwerten, die Unabhängigkeit ist also nicht perfekt.
`cli diff` gegen die Erstkonvertierung (Stand v1):

| Feld | Übereinstimmung | Befund → Regel in v2 |
|---|---|---|
| Verbatim-Felder (title, intro, text, heading, title, summary, details), Sektionsfolge, Zutatenanzahl, Timer, rescue, parallel | 100 % | stabil, keine Änderung |
| Step-Slugs | 9/9 | Slug-Regel funktioniert |
| Dosierungen (`amount.text`, spanForm, reuse, occurrence) | 25/25 | Span-Regel funktioniert; B erfasste zusätzlich „Fleisch" in Schritt 2 → Regel 7: nur Spans mit Menge |
| Learnings-Refs | 5/5 | stabil; Texte differierten (Teilsatz vs. ganzer Bullet) → Regel 11 |
| `action` | 4/9 | Ermessen („ganze Sätze", „reine Handlung") → Regel 5 formuliert die Intention aus (Kurzansicht muss zum Ausführen reichen); Check C prüft Satzgrenzen, erzwingt keine Länge |
| `attention` | 5/9 | keine Regel → Regel 10 |
| `cues`, `limits`, `why` | 7/9 | Phrasengrenzen („Vorsicht:"-Präfix, Satz geteilt) → Regel 9: ganze Sätze |
| `step.equipment` | 7/9 | Mehrwert gering → nicht erfassen |
| `duration` | 8/9 | B nahm Dauer aus dem Text → Regel 4: nur Überschrift |
| Zutaten `group` | 6/17 | freie Benennung → festes Vokabular (Regel 8) |
| Zutaten `priority` | 3/17 | B setzte überall `pflicht` → nur bei Label in der Quelle |
| Zutaten `scale` | 11/17 | keine Regel → nur Ausnahmen, Default im Generator |
| Zutaten `prep`/`note` | 13/17, 11/17 | Abgrenzung unklar → `prep` entfällt, `note` = Klammer-/Kursivtext |
| Zutaten `id`, `store` | 15/17, 16/17 | Singular/Plural (chili/chilis), Jasminreis Asialaden vs. REWE → Slug-Regel; Store bleibt Ermessen |

Nach Umstellung auf v2 hat thit-kho 1 abgeleitete `action` (Schritt 6) und 23 exakte
Spans (vorher 24, „das marinierte Fleisch" entfällt). Eine Wiederholung der Messung
mit v2 ist sinnvoll, sobald die nächste Datei konvertiert wird (Phase 2b), nicht
vorher.

## Entscheidungen

| Datum | Entscheidung |
|---|---|
| 2026-10-05 | `heading` als eigenes verbatim-Feld eingeführt, damit Check B die Dauer in der Schrittüberschrift ohne Doppelzählung über `duration.source` prüfen kann. |
| 2026-10-05 | `action` darf ein Präfix aus mehreren Sätzen sein (nicht nur der erste Satz), solange es reine Handlung ist. Grenze nach Augenmaß: wird der Block fast so lang wie der Text, lieber abgeleitet und mengenfrei. |
| 2026-10-05 | `reuse: true` an `StepIngredient` ergänzt (Eier, mariniertes Fleisch): skalieren ja, summieren nein. |
| 2026-10-05 | Check B verschärft: fehlende Sektionen und nicht abgedeckte Zeilen sind Fehler, nicht nur Report. |
| 2026-10-05 | Löffel-Anzeigeregel (User-Anforderung): Rohwerte in ml bleiben, Kochansicht zeigt TL/EL mit Rohwert in Klammern; `amount.display` als expliziter Hinweis. |
| 2026-10-05 | `action`: Nach der AP3-Streuung (4/9) kurz als „exakt erster Satz" festgelegt, auf User-Einwand zurückgenommen: zu hart, trifft nicht immer die Handlung. Jetzt Intentions-Regel (Anleitung 5): kürzester Satz-Präfix, mit dem man den Schritt ausführen kann; Check C prüft nur Satzgrenzen und gibt bei > 70 % eines annotierten Textes einen Hinweis. Streuung wird in Kauf genommen, Intention schlägt Determinismus. |
| 2026-10-05 | `step.equipment` und `Ingredient.prep` werden nicht mehr erfasst (bleiben im Schema, Anleitung setzt sie nicht). `Ingredient.scale` nur für Ausnahmen. |
| 2026-10-05 | Code-Review (10 Befunde) eingearbeitet: Einheiten-Regex mit Wortgrenze, Sentinel für „Einheit noch nicht gesetzt" (Stück + g wird jetzt als gemischt gemeldet statt summiert), `~` bei Zirka-Mengen in der Liste als `\~`, Diff paart Schritte über (Task, Label), `__pycache__` aus dem Index und `.gitignore`, `cli shopping` prüft den Hash, fehlender `derived`-Block ist kein Fehler mehr, Zutaten-Zuordnung mit Stoppwörtern und exaktem Namen zuerst, „20 Min." vor Großbuchstabe ist ein Satzende, Warengruppen in Laden-Laufreihenfolge. |
| 2026-10-05 | `/simplify` (4 Reviews, ~50 Funde) eingearbeitet: ein Formatierer (`fmt.py`), `Stück` als kanonische Zähleinheit (kein Sentinel, `value` verlangt `unit`), zwei Normalisierungsschlüssel `ws_key` (L2) / `quote_key` (L3), Spans roh gezählt, `derived` enthält nur Daten (`display` statt Markdown-Zeile), eine Stelle für den Block-Status, `derive` verlangt Check D (Fehler statt Schweigen), Schema-Sektionen per `if/then` ohne Python-Nachfilter, Abkürzungs-Heuristik für Satzgrenzen gestrichen (Check C ist Präfix-tolerant), Stoppwortliste durch datengeleitete Gewichte ersetzt, `heading` verbatim inkl. `**`. |
| 2026-10-05 | Externes Schema-Feedback bewertet. **Übernommen (Phase 2a):** Schritt-Kanten `after` (Default: Vorgänger, `[]` = frei), relative Anker `start`, `events[]` getrennt von Timern, `duration.estimated`, `consumes` mit `product:`-Präfix, `derived.inStock` statt `checked` (Abhak-Zustand ist Renderer-State), `hold` dokumentiert relativ zu `product:ready`, Einheit „Zehen" aus den Beispielen gestrichen. **Verschoben auf AP4:** Ressourcen mit ID/Kapazität und Ofen-Temperatur-Bindung (war dort geplant), Summen-/Kritischer-Pfad-Linter gegen `times.total` (braucht den Graph, jetzt vorhanden). **Nicht übernommen:** Schritte splitten (verletzt L2 „ein Markdown-Schritt = ein Step"; stattdessen Schreibkonvention: unabhängige Stränge in der Quelle als eigene Schritte schreiben, Bestand bleibt wie er ist). |
| 2026-10-05 | `derived.sourceHash` = SHA-256 (gekürzt) des JSON ohne `derived`; `cli check` verlangt einen aktuellen Block, sobald die Quelle eine Einkaufsliste hat. Mengen werden intern auf g/ml normiert; `Stück` wird in der Anzeige weggelassen. |

## Kochmodus (Durchstich)

`kochmodus/index.html` + `app.js` + `lib.js` + `style.css`, kein Build. Lädt ein
Rezept-JSON per `?r=<pfad>` (Default thit-kho). Optik und Interaktion folgen dem
Artifact-Prototyp `claude-cook.html` (Repo-Root, vom User mit Claude im Web gebaut):
Schritt-Zeilen mit Checkbox, Antippen öffnet ein Bottom-Sheet mit dem **vollständigen
Schritt-Text** (Kurzansicht als fetter Anfang, Cues/Grenzen/Warum/Rettung markiert),
darunter eine Details-Liste (Dauer, Voraussetzung, Zeitpunkt, Temperatur, Fertig-wenn,
Gerät, Technik, erzeugtes Produkt mit Haltbarkeit, benötigte Produkte), Timer-Start und
Abhaken; eine allgemeine Notiz pro Rezept/Menü in der Notizen-Ansicht; Timer laufen in einem Dock am unteren Rand
über alle Ansichten (+1 Min., Pause, Stopp); Ansichten Kochen / Einkauf / Lesen /
Notizen (mit Markdown-Export); Wach-halten-Knopf. Nicht übernommen: Gantt (braucht
Phasen × Gänge aus Phase 2b) und die claude.ai-Anbindung (Rückfragen, DB-Sync). Zustand (Abhaken, Timer-Endzeiten,
Notizen, Einkaufs-Häkchen, Faktor) liegt im localStorage unter `km:<recipe.id>`,
Schlüssel sind die Step-/Zutaten-Slugs (L12). Timer-Alarm: Ton + Vibration + Titel;
bekannte Grenze (Prototyp): bei gesperrtem Bildschirm unzuverlässig. Wake Lock wird
angefragt, wo erlaubt. Mengen: Spans werden roh im Text ersetzt, nur `spanForm:
exact` mit `value`; Rundung: Stück auf halbe, EL/TL auf Viertel, g/ml ab 100 auf 5er.
Einkaufsliste bei Faktor 1 zeigt `display` (Löffel-Regel), sonst den skalierten
Rohwert. Notizen-Export: Markdown-Block mit `step:<slug>`-Bezug, zum Einfügen unter
`## Learnings`; Parser (Phase 4) liest ihn in `learnings.notes[]` zurück.

Was beim Kochen beobachtet werden soll (Input für den Entscheidungspunkt): Reicht
Kurzansicht + Überschrift zum Ausführen? Werden Details aufgeklappt, und wofür?
Timer benutzt oder Uhr? Stört die Sticky-Kopfzeile auf dem Handy (ca. 210 px)?
Fehlt `after` irgendwo? Welche Notizen entstehen, und passen sie ins Format?

## Nächste Schritte

- **AP6:** Varianten (dal-baukasten, vollkornbrötchen): `variants[]`, `only`,
  `replaces`, `byVariant`, `next`; zwei Schedules (Backtag, aus dem Frost).
  Vorschlag (10/2026, noch nicht entschieden):
  - Zwei Muster. Brötchen hat orthogonale Dimensionen (Mehl: Weizen | Weizen-Roggen |
    Dinkel; Weg: Einfrieren | Direkt backen | Beides), die Unterschiede stehen meist im
    Schritt selbst. Dal ist ein Grundrezept plus Alternativen A–D, die eigene Schritte und
    eigene Einkaufsblöcke haben.
  - Ein Rezept deklariert seine Dimensionen mit Wahlmöglichkeiten, jede mit Default.
    Schreibweise: `*Varianten: Mehl = Weizen | Weizen-Roggen | Dinkel · Weg = …*`.
  - Ganze Schritte, Zeitplan-Einträge und Einkaufsposten tragen `only` (Zeile
    `*nur Einfrieren, Beides*` unter dem Schritt-Titel) oder `replaces` (über den
    Titel, nie über die Nummer).
  - Unterschiede innerhalb eines Satzes laufen als Spans mit derselben Mechanik wie beim
    Skalieren: „80 g Wasser (Weizen-Roggen: 90 g, Dinkel: 40 g)“. Die bestehenden
    Schreibweisen der Brötchen-Datei vereinheitlichen.
  - Einkaufsliste und Mengen-Check rechnet Python vor, pro Kombination unter einem
    Schlüssel (Brötchen 3×3, Dal 5). Der Browser wählt nur aus und hat keine eigene
    Aggregation.
  - Kochmodus: eine Auswahlleiste oben mit einem Segment pro Dimension. Die Wahl wird pro
    Rezept im localStorage gemerkt und gilt für Kochen, Plan, Timer und Einkauf. Nicht
    gewählte Schritte verschwinden ganz. „Beides“ muss die Dimension ausdrücklich
    erlauben. Lesen zeigt weiterhin den vollen Text.
  - Am Text zu klären: Ersetzt eine Dal-Variante Grundschritte oder hängt sie Schritte an?
    Gibt es einen Zeitplan pro Weg oder einen Zeitplan mit `only`-Einträgen?
- **AP7:** Abnahme über alle fünf Dateien, Review-Checkliste, PRD-Delta.
- Kochmodus alltagstauglich (nach AP7, vor dem November-Menü und vor Phase 5):
  Wake-Lock, Alarm, Offline, Personen-Multiplikator für `per`-Mengen in der Ableitung,
  Kritischer-Pfad-Linter gegen `times.total`. Generische Schnell-Timer (Quick-Set ohne
  Schrittbezug). „Claude zum Schritt fragen“ mit dem Rezept als Kontext. Danach den
  November-Menü-Testlauf (Gang 2) machen, die Dauern dabei messen und die
  `estimated`-Flags ablösen. Klären, was mit `claude-cook.html` passiert.
- **Phase 5:** Einkaufsliste und Mengen-Check aus dem JSON in Docsify (Skalieren,
  Löffel-Regel, Variantenwahl). Der Apple-Export kommt dann aus der generierten Liste,
  danach entfallen beide Sektionen im Markdown. Erst nach AP6, weil die Varianten die
  Struktur der Liste ändern.
