# ARCHITEKTUR — Rezeptformat, Parser, Checks, Kochmodus

Rezepte sind Markdown nach `REZEPTFORMAT.md`. Ein deterministischer Parser erzeugt daraus
JSON neben jeder `.md` (validiert gegen `schema/recipe.schema.json`); der Kochmodus
(`kochmodus/`) liest nur dieses JSON. Dieses Dokument hält fest, **warum** das so gebaut
ist (Leitentscheidungen), was die Checks prüfen und was noch offen ist. Wie man ein
Rezept schreibt, steht ausschließlich in `REZEPTFORMAT.md`.

```sh
task build               # alle Rezepte mit JSON neu bauen (+ kochmodus/rezepte.json); einzeln: task build -- gerichte/x.md
task validate            # Gate (Pre-Commit-Hook, `task hooks`): Parser-Tests, Checks, JSON/Sidebar/Learnings/Rezeptliste aktuell
task test-kochmodus      # Node-Tests der reinen Kochmodus-Funktionen (kochmodus/lib.js)
task smoke-kochmodus     # Playwright-Rauchtest im Container (podman)
task serve               # dann http://localhost:3000/kochmodus/
python3 -m tools.recipes.cli lint gerichte/x.md          # Parser-Hinweise (Lücken der Konvention)
python3 -m tools.recipes.cli check gerichte/x.json -v    # alle Checks mit Reports
python3 -m tools.recipes.cli treue alt.md neu.md         # Inhaltstreue einer Normalisierung
python3 -m tools.recipes.cli diff a.json b.json          # Feld-Diff zweier JSONs (z. B. gegen schema/beispiele/)
```

Abhängigkeit: `jsonschema` (`tools/requirements.txt`). Werkzeuge in Python unter
`tools/recipes/`; keine `.md` unter `schema/`, `tools/`, `kochmodus/` (der
Sidebar-Generator liest `*/*.md`).

## Leitentscheidungen

- **L1 Markdown ist die einzige Quelle.** JSON wird per `task build` erzeugt und
  committed, nie von Hand bearbeitet. `REZEPTFORMAT.md` beschreibt alles, was der Parser
  liest; was er nicht erkennt, fehlt im JSON und meldet `cli lint`. Konvention statt
  Heuristik-Sammlung.
- **L2 Verbatim.** Schritte (`text`, `heading`), Prosa-Sektionen, Learnings, Intro und
  Titel tragen den Quelltext wortgleich, inklusive `\~`, Fett, Kursiv.
- **L3 Annotationen sind Zitate.** `why`, `cues[]`, `rescue`, `limits[]`, `title`,
  `amount.text`, `timers[].text`, `temps[].text`, `*.source` müssen (normalisiert)
  Substring der Quelle sein. Check C.
- **L4 Dokument-Reihenfolge ist Daten.** Rezept = Metadaten + geordnete `sections[]`;
  typisiert sind `tasks`, `courses`, `schedule`, `learnings`, `todo`, `shopping`, alles
  andere ist `markdown` mit `tags`.
- **L5 Ermessensfelder nur aus Markierungen.** Warum (kursiver Schlusssatz), Grenzen
  (fett), Erkennungszeichen („bis …“) kommen nur aus der Konvention, unmarkierter Text wird
  nicht geraten. Nachziehen, wenn ein Rezept ohnehin bearbeitet wird. Eine Zeitangabe ist
  kein Timer, wenn sie Haltbarkeit, Vorlauf oder Obergrenze beschreibt.
- **L6 Kurzansicht = Satz-Präfix.** `action` ist der kürzeste Satz-Präfix von `text`, mit
  dem man den Schritt ausführen kann (Intention vor Determinismus). Der Kochmodus zeigt
  „+ N weitere Handgriffe“, wenn der Schritt mehr enthält.
- **L7 Dauern als ISO 8601.** `PnD` = Kalendertage, `PTnH` = Uhrzeit-Stunden.
- **L8 Graph ↔ Platzierung getrennt.** Tasks/Produkte/Hold/Claims sagen *was* und *wie
  lange*; Kanten (`after`, `start`) sagen *wovon abhängig*; Zeitpläne sagen, *wann der
  Autor es tun will*. Kein Planer, nur Konfliktprüfung (Checks G, H, P).
- **L9 Abgeleitetes rechnet Python.** Einkaufsliste und Mengen (`derived`) entstehen in
  `tools/recipes/shopping.py` aus `ingredients[]` und `step.ingredients[]` — pro
  Varianten-Kombination vorgerechnet. Der Browser zeigt an, wählt aus und skaliert, ohne
  zweite Aggregationslogik. Auch Entscheidungen über den Text (welche Alternative nur eine
  Menge ist: `qty`, `baseQty`) trifft der Parser.
- **L10 Mengen als Text-Spans.** `amount.text` ist der Span im Schritttext; der Renderer
  ersetzt beim Skalieren den Zahlenteil. Mehrfach vorkommende Spans tragen `occurrence`.
  `reuse: true` = schon dosiert (skalieren ja, summieren nein).
- **L11 Stabile Slugs.** IDs kommen aus Titeln, nie aus Nummern, und werden nach dem ersten
  Kochen nicht umbenannt (Abhak-Zustand, Notizen, Verweise hängen daran). Abhängigkeiten
  über Titel, nie über Nummern.
- **L12 Varianten nur über `only`.** Dimensionen mit Default im Kopf; Schritte, Abschnitte,
  Posten, Zeitpläne und Einträge tragen `only`; Inline-Alternativen tauschen Mengen. Kein
  `replaces`.
- **L13 Feedback ohne Backend.** Eine allgemeine Notiz pro Rezept/Menü im Kochmodus,
  exportiert als Markdown-Block unter `## Learnings` (`learnings.notes[]`).
- **L14 Kochmodus-Zustand im Browser.** `km:<rezept-id>` (Haken, Einkauf, Notiz, Faktor,
  Wahl), `km:timers` rezeptübergreifend mit absoluter Endzeit (überlebt Reload), `km:last`.
  Statische Seite, installierbar, offline über den Service Worker: App-Hülle als ein
  Cache pro Version (Hash der Hülle, von `task build` gesetzt, atomar installiert), Rezepte
  in einem eigenen Cache, Netz zuerst. Beim Entwickeln mit `task serve`: nach Änderungen
  an der App `task build` und zweimal neu laden (oder in den DevTools „Update on reload“). Kein Alarm bei gesperrtem Bildschirm (ohne Push-Server
  nicht verlässlich), dafür „Bildschirm wach halten“.
- **L15 Gates lokal.** `task validate` als Pre-Commit-Hook, kein CI.

## Löffel und Milliliter (Anzeige-Regel)

Rohwerte bleiben wie in der Quelle. Für die Anzeige (`tools/recipes/spoons.py`, ab Phase 5
im Renderer):

- TL/EL bleiben Löffel; mit `unitHint` (z. B. EL → g) steht der metrische Wert in
  Klammern: „5 EL (≈ 60 g)“.
- Metrische Werte aus US-Umrechnungen (14,79 ml = 1 EL, 4,93 ml = 1 TL, ±1 %) erscheinen
  als Löffel mit Rohwert: „14,7 ml“ → „1 EL (14,7 ml)“.
- `amount.display` setzt die Anzeige explizit. Beim Skalieren wird der Rohwert skaliert,
  die Anzeige neu abgeleitet.

## Checks

`cli check` (in `task validate` über alle gebauten JSONs). **fail** bricht das Gate,
**warn/info** erscheint mit `-v`.

| # | Prüft | Art |
|---|---|---|
| A | JSON Schema | fail |
| B | Jede `##`-Sektion der Quelle hat eine Section; alle Zahl+Einheit-Token der Quelle stehen in verbatim-Feldern; jede Quellzeile ≥ 20 Zeichen steht verbatim im JSON | fail |
| C | Zitat-Treue der Annotationen; `action` ist Präfix von `text`; Spans eindeutig oder mit `occurrence` | fail |
| D | Slugs gültig und eindeutig; alle Refs lösen auf (Zutaten inkl. `byVariant`, Produkte, Kanten, Anker, Varianten-Wahlen); Schritt-Graph ohne Zyklen; Report: Zutaten ohne Dosierung | fail |
| E | Pro Gang: nummerierte Schritte der Quelle = Steps | fail |
| F | Zeitplan: jedes Segment der Quelle (Bullets, `T−`-Tabelle) ist ein verbatim-Eintrag; Report: Einträge mit Treffer | fail |
| G | Erzeuger vor Verbraucher über die Phasen, Haltbarkeit (`hold`) eingehalten | fail |
| H | Service-Zeitplan: Koch doppelt belegt (pro Schritt, passive zählen nicht), Ofen-Temperaturen, Herd-Kapazität (5 Felder), Aufgaben nach Servierzeit, Constraints | warn |
| K | `derived` aktuell (Hash); jeder Original-Posten der Einkaufsliste findet eine Zutat; Menge gegen die Ableitung (Gebinde zählt als passend) | fail/info |
| L | `## Mengen-Check`-Tabelle gegen die Ableitung | info |
| P | Kritischer Pfad über die Schritt-Kanten gegen „gesamt …“ im Kopf, sonst Vorschlag | warn |

Daneben: `tools/test_parse.py` (Regeln gegen die Gerüste in REZEPTFORMAT.md),
`tools/test_kochmodus.mjs`, `tools/smoke_kochmodus.mjs`. `schema/beispiele/*.json` sind
eingefrorene Hand-Annotationen als Paritäts-Soll für `cli diff`, keine Quelle.

## Offen

- **Phase 5 — Docsify aus dem JSON:** Einkaufsliste und Mengen-Check aus `derived` in der
  Docsify-Seite (Skalieren, Löffel-Regel, Variantenwahl), Apple-Export aus der generierten
  Liste; danach entfallen beide Sektionen im Markdown. Dabei TL↔EL beim Summieren
  umrechnen (Dal: Ghee „1 TL (+ EL ungemischt)“) und Mengen pro Teller (`1 halbiertes
  Ei`) nicht zum Einkauf zählen.
- **Kochmodus:** November-Menü (Gang 2) als Testlauf kochen, Dauern messen und
  `estimated` ablösen; „Claude zum Schritt fragen“ (zurückgestellt, bessere Integration
  später); Personen-Multiplikator, sobald mehr Rezepte Mengen pro Person haben.
- **Rezepte:** Seit 10/2026 haben alle Rezepte ein JSON, auch die drei Komponenten-Rezepte
  unter `technik/` (Pfannkuchen, Teriyaki, Bratensauce). Ohne JSON bleiben nur die
  Spickzettel und `schwangerschaft/leitfaden.md`. Offen: Gesamtzeit-Kopfzeilen nach Check P
  nachtragen (Bò lúc lắc \~2:25, Dal \~0:45, Brötchen); Ermessensfelder (L5) beim
  Bearbeiten markieren.
- **Technik:** Check P vergleicht bei mehrtägigen Rezepten (Mezze „gesamt 3 Tage“,
  Bratensauce „\~2 Tage“) den Pfad über die Schritt-Kanten mit der Kalenderdauer und warnt
  dann immer; die Tagesgrenzen aus dem Zeitplan fehlen im Pfad.
- **Technik:** Check H modelliert bei Uhrzeit-Menüs das Ende der Servier-Phase nicht
  (Aufgaben, die in die nächste Phase laufen, bleiben unbemerkt); Check D und P teilen
  sich die Vorgänger-Regel nicht; Zeitplan-Grammatik steht in Parser und Check F doppelt.
- **Später (aus dem ursprünglichen PRD):** Ebenen-Schalter (Warum/Rettung ein- und
  ausblenden), Technik-Bibliothek mit Detailschritten, mehrere Rezepte zu einem Plan im
  Kochmodus, Kühlschrank-/TK-Platz als Ressource.
