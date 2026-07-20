# CLAUDE.md — Kontext für Rezept-Repo

Dieses Repo enthält Rezepte und Koch-Notizen. Beim Erstellen neuer Rezepte oder
Anpassen bestehender bitte folgenden Kontext berücksichtigen.

## Haushalt

- **Personen:** 2 Erwachsene + 1 Kind (Stand: 3 Jahre, Stand April 2026)
- **Kind isst:** Gerne ausgefallene Dinge — Sushi, Sojasauce, Eier, Oliven
- **Kind nicht:** Scharf
- **Erfahrungslevel:** Erfahren in der Küche, scheut keinen Aufwand
- **Geschmacksvorlieben:**
  - Mag: Reichhaltig/kräftig, komplexe Umami-Profile, klare elegante Brühen
  - Mag weniger: Sehr intensive Pilznoten (kein großer Pilz-Fan)
  - Enoki-Pilze: Textur nicht beliebt → Shimeji/Champignons bevorzugen
- **Toleranz für lange Zubereitung:** Hoch (6-7h für Brühe ist okay)

## Equipment

### Vorhanden
- **Größter Topf: 14L** (seit Juli 2026 — Paitan/Tonkotsu-Style und große Brühen-Mengen jetzt möglich)
- Zweitgrößter Topf: 6L
- Bräter/Schmortopf (für Osso Buco-Style Gerichte)
- Stabmixer
- Fleischthermometer
- Mandoline / Gemüsehobel
- Kastenformen (ca. 20cm, 2 Stück)
- Feines Sieb + Passiertuch
- Standard Pfannen, Kleinkram

### Fehlt / Wäre gut zu haben
- Bunsenbrenner (für Aburi-Effekte)

## Einkaufsquellen

### Aldi / REWE (nah, Standardeinkauf)
- Grundzutaten: Gemüse, Obst, Milchprodukte, Eier, Butter, Sahne
- Standard-Gewürze, Zucker, Mehl
- Eingeschränkte Auswahl bei Spezialitäten

### REWE Center (groß, gute Auswahl, weiter weg)
**Zuverlässig zu bekommen:**
- Fleisch generell, Schweinebauch, Hähnchenflügel
- Suppenhuhn
- Frisches Gemüse
- Einigermaßen gute Auswahl an Asia Zutaten
- Eier, Milchprodukte

**Gibt es NICHT (auch nicht im Center) — wird nichts vor Ort zerlegt:**
- Karkassen (Hähnchen, etc.)
- Schweinefüße, Gelenke, Markknochen
- Sonstige Schlachtnebenprodukte
- → Für sowas immer Selgros!

**Eher nicht zu erwarten:**
- Frische asiatische Spezialitäten (frische Ramen, Mochi etc.)
- Große Auswahl japanischer Würzmittel
- Spezielle asiatische Pilze (Shimeji, Enoki gibt es frisch)

### Asialaden (lokal, klein-mittelgroß)
**Zuverlässig:**
- Trocken-Ramen mit Kansui (z.B. Hakubaku organic — sehr gute Qualität)
- Mirin, Sake (Kochsake/Ryorishu), Sojasauce
- Kombu, Katsuobushi, getrocknete Shiitake
- Nori, getrocknete Pilze allgemein
- Frische Frühlingszwiebeln (oft besser als REWE)
- Menma in der Dose
- TK Hühnerfüße

**Unsicher / vorher anrufen:**
- Frische Ramen-Nudeln (nicht immer da)
- Frische Spezialpilze
- Narutomaki/Kamaboko (TK)

**Eher nicht erhältlich:**
- Großes Sortiment japanischer Spezialitäten (kein japanischer Großhandel)
- Spezielle Sake-Sorten (nur eine einzige eher zum Trinken gedacht)

### Buhara Seafood (Dietzenbach, nah)
- Gut sortierter Fischhändler
- **Erste Anlaufstelle für Fisch & Meeresfrüchte** (Hummer, Garnelen mit Schale etc.)
- Bei Spezialwünschen vorher anfragen; Fallback: Selgros (TK)

### Selgros (Großhandel, weiter weg)
- Großhandel-Charakter, große Gebinde
- Bei einem Trip kann nicht der Asialaden besucht werden → Trade-off
- **Die Quelle für Knochen/Karkassen/Schweinefüße/Gelenke** (gibt es bei REWE nicht)
- Potenziell gut für: größere Mengen Sahne/Butter, Jakobsmuscheln (TK), Entenbrust
- Japanische Spezialitäten vermutlich eingeschränkt

## Generelle Patterns für Rezept-Empfehlungen

1. **Topfgröße immer mitdenken:** 14L ist die harte Grenze (großer Topf), daneben
   6L für kleinere Brühen. Rezepte für mehr Volumen → explizit anmerken oder
   anpassen (z.B. Wassermenge reduzieren).

2. **Mengen-Mathematik prüfen:** Wenn mehrere Komponenten dieselbe Zutat brauchen
   (z.B. Sojasauce für Tare + Chashu + Eier-Marinade), die Gesamtmenge auf der
   Einkaufsliste richtig summieren. Frühere Fehler: Mirin/Sojasauce zu knapp
   bemessen.

3. **Einkaufslogik:** Asialaden zuerst (japanische Spezialzutaten), dann REWE
   (Fleisch, Gemüse, Backup). Vor Asialaden anrufen für Engpass-Artikel.

4. **Beim Kind mitdenken:** Eigene mildere Version (weniger Tare, kein scharfes
   Öl) parallel mit anrichten.

5. **Bei Vorschlägen kritisch sein:** User schätzt es wenn Annahmen hinterfragt
   werden und Alternativen abgewogen werden. Keine Über-Optimistik bei
   Beschaffbarkeit von Zutaten.

6. **Quellen/Referenzen nennen** wenn möglich, statt nur aus dem Bauch heraus.

7. **Zutaten** User ist durchaus bereit Spezialzutaten oder nötiges Equipment zu besorgen
   wenn gut beschaffbar (im Zweifel auch amazone / online) und nicht allzu teuer oder zumindest
   für viele andere Dinge nützlich und nicht nur für ein einziges Rezept

## Repo-Struktur & Rezept-Status

- **Ordner:** Alle Einzelrezepte liegen in `gerichte/` (keine Unterteilung nach
  Küche/Region). Speziell bleiben: `menues/` (Mehrgänger), `schwangerschaft/`,
  `einkaufslisten/` (kombinierte Listen über mehrere Rezepte).
- **Rezepte in Arbeit (TODO):** H1-Titel beginnt mit `🚧 ` und direkt unter dem
  Titel steht eine Status-Alertbox (`> [!NOTE]` … "Status: In Arbeit"). Solche
  Stubs enthalten Idee, grobe Richtung, Beschaffungs-Einschätzung und offene
  Fragen — noch keine Einkaufsliste/Zubereitung.
- **Sidebar wird generiert:** `_sidebar.md` NIE von Hand editieren, sondern
  `task sidebar` laufen lassen. Der Generator gruppiert 🚧-Rezepte automatisch
  in die Sektion „🚧 in arbeit" und hängt den Link auf `ideen.md` an.
- **Fertigstellung eines Rezepts:** `🚧 ` aus dem Titel entfernen, Statusbox
  raus, `task sidebar` ausführen — fertig, keine Datei-Moves nötig.
- **Ideen-Backlog:** Unkonkrete Ideen leben in `ideen.md`. Wird eine konkret →
  🚧-Stub in `gerichte/` anlegen und aus dem Backlog streichen.

## Format: Einkaufslisten (immer so!)

- **Abhakbar:** Einkaufslisten-Einträge immer als GFM-Task-Liste schreiben
  (`- [ ] Zutat, Menge`), NICHT als normale Bullets. Die Docsify-Seite nutzt das
  Plugin `docsify-interactive-checkboxes` (eingebunden in `index.html`), das die
  Checkboxen im Browser anklickbar macht und den Zustand im localStorage speichert.
- Gilt NUR für Einkaufslisten — Zubereitungsschritte, Zeitpläne etc. bleiben
  normale Listen/Absätze.
- **Sortierung:** Immer nach Laden gruppieren (`###`-Überschrift pro Laden, in
  sinnvoller Besuchs-Reihenfolge, siehe Einkaufslogik oben) und/oder innerhalb
  nach Warengruppen, wie man sie im Laden beieinander findet: Obst/Gemüse,
  Kühltheke (Fisch/Fleisch), Milchprodukte/Eier, Trockenwaren, Gewürze, …
- **Achtung beim Editieren:** Die Checkbox-IDs hängen am Eintragstext — wer eine
  Zeile umformuliert, setzt deren Haken zurück. Unkritisch, aber bei Anpassungen
  kurz erwähnen wenn eine Liste vermutlich gerade "in Benutzung" ist.

## Bisherige Projekte

- ✅ **Shoyu-Ramen mit Chintan-Brühe** (siehe `gerichte/ramen-shoyu-chintan.md`)
  - Erfolgreich umgesetzt
  - Learnings: Pilznote reduzieren, Enoki meiden, Suppenhuhn+Flügel funktioniert
    gut als Karkassen-Ersatz

- ✅ **Degustationsmenü Hochzeitstag** (siehe `menues/menue-hochzeitstag.md`)
  - 4 Gänge erfolgreich umgesetzt, Zeitplan hat funktioniert
  - Highlights: Jakobsmuscheln (Vorspeise) und Karamell-Pekannuss-Parfait (Dessert)
  - Glasierte Karotten trotz Einfachheit sehr gelobt
  - Learning: Kartoffelbaumkuchen — Aufwand/Wow-Verhältnis schlecht, nächstes Mal
    einfachere Kartoffelbeilage. Entenbrust solide aber kein Highlight.
  - Learning: Aufwand ≠ Wow. Perfekte Ausführung simpler Techniken oft wirkungsvoller.

- ✅ **Thịt kho trứng** (siehe `gerichte/thit-kho-trung.md`) — 07/2026
  - Klarer Favorit: minimaler Aufwand, herausragendes Preis/Leistungs-Verhältnis,
    zweimal mit Genuss gegessen. Bestätigt Learning "Aufwand ≠ Wow".
  - Learnings: ganze Chilis früher entnehmen (geben auch unverletzt Schärfe ab),
    Säure-Balance kommt vom Pickle, Radieschen als Daikon-Ersatz okay.
    Mitgeschmorte Eier überzeugten nicht (fest, fad) — weglassen oder erst
    in den letzten 20–30 Min. einlegen.

- ✅ **Geschmorter Oktopus, griechische Art** (siehe `gerichte/oktopus-geschmort.md`) — 07/2026
  - Gut, aber Aufwand/Reward schwächer als Thịt kho → besondere Anlässe.
  - Beschaffung: Selgros-Frischetheke "Pulpo Blume Marokko" (*Octopus vulgaris*) ✓;
    TK-Ware "Tintenfisch Tentakel" (*Dosidicus gigas*) ist KEIN Ersatz — Etikett
    immer auf lateinischen Namen prüfen.
  - Cantaloupe-Sorbet als Dessert dazu: sehr stimmig.

## Ideen für nächste Projekte

→ Siehe `ideen.md` (Ideen-Backlog). Aktuell in Arbeit (🚧-Stubs in `gerichte/`):
Cá kho tộ, Cochinita Pibil, Lamm-Kleftiko, Tafelspitz.

## Workflow: Neues Rezept erarbeiten

Vorgehensweise für neue Rezepte in diesem Repo:

1. **Idee & Kontext:** Grobe Idee beschreiben (z.B. "Pho für 2+1, winterlich").
   Claude prüft gegen Equipment, Einkaufsquellen, Vorlieben und bisherige Learnings.
2. **Recherche & Abwägung:** Varianten diskutieren, Quellen nennen,
   realistische Einschätzung der Beschaffbarkeit und des Aufwands.
3. **Rezept-Entwurf:** Vollständiges Rezept mit Einkaufsliste, Zeitplan,
   Mengen-Check (Gesamtverbrauch pro Zutat!) und Kinder-Anpassungen.
4. **Review & Feinschliff:** Kritische Prüfung, ggf. Vereinfachungen.
5. **Nach dem Kochen:** Feedback & Learnings ergänzen, CLAUDE.md updaten.
