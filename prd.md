# PRD (Draft): Strukturiertes Rezeptformat + Renderer

## Auftrag an Claude Code
Analysiere dieses Repo und erstelle einen **Detailplan für Phase 1 und 2** (unten).
Noch **keine Implementierung**. Stelle Rückfragen, wo dieser Entwurf unklar ist
oder Annahmen nicht zum Repo passen. Hinterfrage den Entwurf kritisch.

## Kontext
- Rezepte und Menüs liegen als Markdown in diesem Repo und werden per docsify
  auf GitHub Pages gerendert.
- Die Rezepte sind bewusst **erklärend**: Teller-Logik, Zweck von Schritten,
  Korrektur-Tipps, Fallbacks, Varianten (Kind, Schwangerschaft/GDM).
  Anspruch ist beste Qualität; die ausführende Person soll die Intention
  eines Schritts verstehen.
- `CLAUDE.md` enthält Haushalt, Vorlieben, Unverträglichkeiten, Equipment.
- Komplexe Menüs laufen über mehrere Tage (T-2, T-1, Service) mit
  parallelen Komponenten, Haltbarkeitsfenstern und Ressourcen-Konflikten
  (Ofen, Herdplatten).

## Ziel
1. Ein Quellformat, das jedes Rezept und Menü abbilden kann, inkl.
   Zeitabfolgen, Abhängigkeiten und Materialplanung.
2. Wiederverwendbare Renderer-Bausteine für (a) die Leseansicht in docsify
   und (b) einen Kochmodus mit Zeitplan, Timern und Abhaken.

## Getroffene Entscheidungen
- **Datenmodell vor Syntax.** Kanonisches Zwischenformat ist JSON mit
  JSON Schema. Die Schreibsyntax ist nur ein Weg dorthin.
- **Quelle bleibt Markdown** mit sparsamen Erweiterungen. Sie muss auch
  ungerendert (GitHub, Editor, LLM) gut lesbar bleiben.
- **Parser in Go oder Python**, läuft als Build-Schritt (GitHub Actions)
  und erzeugt neben jeder `.md` eine `.json`.
- **Ein JS-Renderer**, zwei Einsatzorte: docsify-Plugin und eine
  Kochmodus-Seite. Beide lesen nur JSON. Kein separater Markdown-Generator.
- **Hosting auf eigener GitHub-Pages-URL**, vorerst ohne Claude-Anbindung.
  Der Kochmodus wird mit einer oder mehreren URLs (Komponenten oder ganzes
  Menü) gefüttert.
- Das Format muss so einfach sein, dass ein LLM bestehende Rezepte
  zuverlässig konvertieren kann.

## Datenmodell: Kernkonzepte (Entwurf, zu validieren)
- **Menü:** Komponenten, Personenzahl, Anker (z. B. Service-Zeit),
  Gangfolge mit Offsets.
- **Komponente/Rezept:** Schritte, Zutaten, Geräte, erzeugtes
  Zwischenprodukt.
- **Schritt mit Wissensebenen:**
  - `action`: kurze Handlung im Imperativ (immer sichtbar)
  - `why`: Zweck/Intention
  - `cues`: woran man erkennt, dass es fertig/richtig ist
  - `rescue`: was tun, wenn es schiefgeht
  - `technique`: Verweis auf die Technik-Bibliothek
  - Ebenen sind im Renderer ein- und ausblendbar (Anfänger vs. Profi).
- **Technik-Bibliothek:** wiederverwendbare Einträge (z. B. „zur Rose
  abziehen“, „Beurre blanc montieren“) mit Detailschritten.
- **Zutat:** Menge (inkl. Spannen), Einheit, Zubereitung, optional
  Menge pro Einheit (z. B. „je Pfanne 15 g“), Fallback/Ersatz.
- **Zwischenprodukt:** Haltbarkeitsfenster (`hold: {min, max}`) und
  Lagerort. „Frühestens X, höchstens Y vorher“ hängt am Produkt,
  nicht an der Aufgabe.
- **Zeitliche Bedingungen:** Abhängigkeiten ergeben sich aus
  produces/consumes; explizite Abstände mit min/max (Simple Temporal
  Network); feste Lage relativ zum Anker.
- **Dauer:** aktiv (bindet die Person) vs. passiv (läuft nebenher).
- **Ressourcen:** Ofen (mit Temperatur), Herdplatten, Kühlschrank-/TK-Platz.
- **Varianten:** z. B. Kinderportion, Schwangerschaft/GDM,
  Zutaten-Fallbacks.
- **Notizen/Offenes:** Feedback und offene Testlauf-Fragen bleiben
  sichtbar und strukturiert.

## Erkenntnisse aus einem Cooklang-Test (Gang 2 Kaisergranat)
Cooklang wurde geprüft (CookCLI 0.37.0). Stark bei Mengenaggregation,
Skalierung, Einkaufslisten. Schwächen für unseren Anwendungsfall:
- `~` ist für Timer reserviert; „~250 ml“ verlor die Tilde stillschweigend.
- Deutsche Beugung landet in Listen („das #feine Sieb{}“ → „feine Sieb“).
- Gleiche Zutat mit verschiedener Zubereitung wird vermischt
  (Walnüsse grob + fein → eine Zeile).
- Keine Mengen pro Einheit („je Pfanne“).
- Spannen nur als Erweiterung des Rust-Parsers, nicht im Kern der Spec.
- Kommentare/offene Punkte erscheinen in keiner Ausgabe.
- Zeitangaben („Vortag“, „≤ 30 Min. vor Anrichten“) nur als Freitext.
- Erklärender Fließtext mit Markup wird schnell unleserlich.
→ Cooklang als **Vorbild** für Mengen-/Einheitensyntax und
  Einkaufslisten-Logik nutzen, nicht als Hauptformat übernehmen.

## Phasen
1. **Testsammlung:** 4–5 möglichst unterschiedliche Rezepte aus dem Repo
   auswählen: das November-Menü, ein simples lineares Rezept, etwas zum
   Backen mit Mengenverhältnissen, eines mit Varianten/Fallbacks.
   *Ergebnis:* begründete Auswahl.
2. **Datenmodell:** JSON Schema entwerfen; die Testsammlung von Hand
   (LLM-gestützt) nach JSON übertragen. Was sich nicht abbilden lässt,
   zeigt Lücken im Modell.
   *Abnahme:* alle Testrezepte validieren gegen das Schema, ohne
   Informationsverlust gegenüber dem Original.
3. **Schreibsyntax:** Markdown-Erweiterungen + YAML-Blöcke für die
   Planung definieren. Kriterium: roh gut lesbar, LLM-schreibbar.
   *Abnahme:* Testsammlung in der neuen Syntax, Review der Lesbarkeit.
4. **Parser (Go oder Python) + CI:** Markdown → JSON, Validierung,
   Tests gegen die Testsammlung, GitHub Action.
5. **Renderer-Bausteine (JS):** Schritte (mit Ebenen), Zutaten/Einkaufsliste
   (mit Skalierung), Zeitplan/Gantt, Kochmodus (Timer, Abhaken).
   Zuerst als docsify-Plugin, dann die Kochmodus-Seite.
6. **Planungslogik:** zuerst nur Konflikte prüfen (Ressourcen doppelt
   belegt, Haltbarkeit überschritten), später automatische Planung.

## Referenz: Prototyp
Ein Kochmodus-Prototyp für das November-Menü existiert als
claude.ai-Artifact: Gantt-Ansicht (Phasen × Gänge), Aufgaben mit
Schritten zum Abhaken, parallele Timer mit Endzeitpunkten (überleben
Neuladen), Notizen pro Aufgabe mit Markdown-Export. Bekannte Grenze:
Timer-Alarme bei gesperrtem Bildschirm sind auf Mobilgeräten unzuverlässig.

## Nicht-Ziele (vorerst)
- Claude-Anbindung im Widget (später: eingebettetes Widget oder Link in
  einen Chat mit vorbefülltem Kontext).
- Automatische Planung mit Ressourcen-Optimierung.
- Import aus schema.org/Cooklang (soll durch das JSON-Modell später
  möglich bleiben).

## Offene Fragen
- Ist das Repo öffentlich? Gesundheitsdaten (Schwangerschaft/GDM) aus
  `CLAUDE.md` gehören nicht in ein öffentliches Repo oder eine
  öffentliche Seite.
- Wo lebt die Technik-Bibliothek (eigene Dateien, eigener Ordner)?
- Wie wird Feedback aus dem Kochmodus zurück ins Repo gebracht, ohne
  Backend? (z. B. Export als Markdown, GitHub-Issue-Link)
- Einheiten: Umrechnung (EL ↔ g) nötig oder nur Anzeige?
