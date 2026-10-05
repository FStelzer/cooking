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
```

Einzige Abhängigkeit: `jsonschema` (siehe `tools/requirements.txt`).

## Status

| Datum | Stand |
|---|---|
| 2026-10-05 | Plan freigegeben. AP0 (Festlegungen, Werkzeug-Skelett) und AP1 (Schema v0.1, thit-kho Minimum + Anreicherung) umgesetzt. Checks A–D grün, Mutationstest 11/11 erkannt. |
| 2026-10-05 | AP2 umgesetzt: `tools/recipes/shopping.py` berechnet `derived.quantities` und `derived.shopping`, `cli derive` schreibt sie ins JSON (reproduzierbar bis auf `generatedAt`, Hash-Prüfung gegen veraltete Blöcke), `cli shopping` rendert Markdown im heutigen Format, Check K vergleicht mit der Original-Einkaufsliste. Nächster Schritt: AP3 (zweite unabhängige Konvertierung, Feld-Diff). |

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
- **L13 Feedback-Ziel.** `learnings.notes[]` mit `ref: step:<slug>|task:<id>|product:<id>`,
  `date`, `status: open|applied`. Der Kochmodus exportiert genau diese Struktur.
- **L14 Ablage.** `schema/recipe.schema.json`, `schema/beispiele/*.json`,
  `tools/recipes/*.py`, `tools/requirements.txt`, dieses `SCHEMA.md` im Root.
  Keine `.md` unter `schema/` oder `tools/` (der Sidebar-Generator iteriert `*/*.md`).

## Minimum vs. Anreicherung

| Ebene | Felder |
|---|---|
| **Minimum** (Schema `required`) | Recipe: `id`, `kind`, `title`, `yields`, `ingredients`, `sections` · Ingredient: `id`, `name`, `store` · Task: `id`, `name`, `steps` · Step: `id`, `label`, `text`, `action`, `ingredients` · StepIngredient: `ref`, `amount.text` · learnings: `cooked`, `summary` |
| **Anreicherung** | `intro`, `times`, `equipment`, `status`; Step: `heading`, `title`, `attention`, `duration`, `timers`, `temps`, `endCondition`, `cues`, `why`, `rescue`, `limits`, `technique`, `parallel`, `equipment`; Amount: `value`, `max`, `approx`, `unit`, `per`; Ingredient: `group`, `buy`, `inStock`, `pantry`, `priority`, `optional`, `fallback`, `unitHint`, `scale`; Task: `intro`, `phaseHint`, `duration`, `produces`, `consumes`; learnings: `details`, `notes` |

## Konvertierungs-Anleitung (v1, nach AP1)

1. **Kopf.** `id` = Pfad ohne `.md`. `title` = H1 ohne `🚧`; `status: wip` bei `🚧`.
   `intro` = alles zwischen H1 und erster `##`, verbatim. `yields` aus dem Titel.
2. **Sektionen in Dokumentreihenfolge.** `## Einkaufsliste` → `{type: shopping}`
   (nur Platzhalter). `## Zubereitung`/`## Rezept` → `tasks`. `## Learnings` →
   `learnings` (`summary` = Fließtext bis zur ersten `###`, `details` = Rest ab `###`,
   beides verbatim). `## To-do`/„Offen"-Listen → `todo`. `## Mengen-Check` entfällt.
   Alles andere → `markdown` (verbatim, `tags` nach Inhalt).
3. **Schritte.** Ein Markdown-Schritt = ein Step, nie splitten. `heading` = die
   Überschriftzeile ohne `**`. `label` = Nummer. `title` = Zitat aus `heading` ohne
   Nummer und Dauer. `text` = ganzer Absatz verbatim. `action` nach L7.
   Slug nach L12. `duration.source` = Dauer-Angabe aus der Überschrift.
4. **Dosierungen.** Jede Mengenangabe im Schritt wird ein `StepIngredient` mit
   `amount.text` als Span (L11). Zutat ohne Zahl („reichlich Pfeffer", „Schuss
   Kokoswasser") bekommt nur `text`, kein `value`. Zweite Nennung derselben Menge
   („Die 6 Eier") → `reuse: true`. Menge nur in der Einkaufsliste → am ersten
   verwendenden Schritt mit `spanForm: "derived"`.
5. **Zutaten (Rezept-Ebene).** Ein `Ingredient` pro Zutat (nicht pro Einkaufsposten):
   Sammelposten und „A + B"-Posten werden aufgeteilt. `store` aus `## Beschaffung`
   bzw. CLAUDE.md-Einkaufsquellen; `pantry: true` für Salz, Pfeffer, Wasser; `note` =
   kursive Anmerkung des Postens verbatim.
6. **Annotationen** nur als Zitate (L3): `cues` = Erkennungszeichen („bis …",
   „tief bernsteinfarben"), `limits` = Grenzen/Warnungen, `why` = Begründung (meist
   kursiv am Ende), `rescue` = „wenn schiefgeht". Nicht erfinden, nicht umformulieren.
7. **Zeitangaben** nach dieser Grammatik:

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
| D | Slugs gültig und rezeptweit eindeutig; `ref`, `consumes`, `notes[].ref`, `todo[].ref` lösen auf; Report der derived-Felder und der Zutaten ohne Dosierung | fail | AP1 |
| K | `derived` vorhanden und aktuell (`sourceHash`); jeder Original-Posten der `## Einkaufsliste` (Teile an ` + ` getrennt) findet eine Zutat per Namenswort; Menge des Postens (inkl. `900 g – 1 kg`, `4–5 EL`, `½`) gegen `derived.quantities.total`; Gebinde (`buy`) zählt als passend; Zutaten nur im JSON als Info | fail bei Posten ohne Zutat oder veraltetem Block, Abweichungen als Report | AP2 |
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

## Entscheidungen

| Datum | Entscheidung |
|---|---|
| 2026-10-05 | `heading` als eigenes verbatim-Feld eingeführt, damit Check B die Dauer in der Schrittüberschrift ohne Doppelzählung über `duration.source` prüfen kann. |
| 2026-10-05 | `action` darf ein Präfix aus mehreren Sätzen sein (nicht nur der erste Satz), solange es reine Handlung ist. Grenze nach Augenmaß: wird der Block fast so lang wie der Text, lieber abgeleitet und mengenfrei. |
| 2026-10-05 | `reuse: true` an `StepIngredient` ergänzt (Eier, mariniertes Fleisch): skalieren ja, summieren nein. |
| 2026-10-05 | Check B verschärft: fehlende Sektionen und nicht abgedeckte Zeilen sind Fehler, nicht nur Report. |
| 2026-10-05 | `derived.sourceHash` = SHA-256 (gekürzt) des JSON ohne `derived`; `cli check` verlangt einen aktuellen Block, sobald die Quelle eine Einkaufsliste hat. Mengen werden intern auf g/ml normiert; `Stück` wird in der Anzeige weggelassen. |

## Nächste Schritte

- **AP3:** zweite unabhängige Konvertierung von thit-kho, Feld-Diff; Anleitung v2.
- Danach Durchstich (Kochmodus-Seite mit thit-kho), dann Entscheidungspunkt vor 2b.
