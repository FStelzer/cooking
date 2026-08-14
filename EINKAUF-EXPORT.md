# Einkaufslisten-Export → Apple Erinnerungen

Die Docsify-Seite zeigt an jeder `## Einkaufsliste` und an jeder `###`-Laden-Gruppe
einen **📲-Export-Button**. Der Button sammelt alle **nicht abgehakten** Items ein
(abgehakt = schon vorhanden/gekauft, Zustand kommt von den anklickbaren Checkboxen)
und kürzt lange kursive Anmerkungen weg. Am iPhone öffnet sich das Share-Sheet,
am Desktop landet der Text zeilenweise in der Zwischenablage.

Der Laden-Button exportiert nur seine Gruppe — praktisch, wenn Asialaden und REWE
getrennte Erinnerungen-Listen bekommen sollen.

## Einmalige Einrichtung am iPhone

### 1. Erinnerungen-Liste anlegen

In **Erinnerungen** eine neue Liste erstellen, als **Listentyp „Einkaufsliste"**
(sortiert Einträge automatisch in Supermarkt-Kategorien wie Obst & Gemüse,
Milchprodukte, …) und über „Personen hinzufügen" teilen.

### 2. Kurzbefehl anlegen

In der **Kurzbefehle**-App einen neuen Kurzbefehl erstellen, Name z. B.
**„Zur Einkaufsliste"**:

1. Oben auf das ⓘ-Symbol → **„Im Share-Sheet anzeigen"** aktivieren.
   Bei den akzeptierten Eingabetypen nur **Text** anhaken; „Wenn es keine
   Eingabe gibt" auf **„Fortfahren"**.
2. Aktionen hinzufügen (die erste Aktion „Empfange **Text** aus Share-Sheet"
   entsteht durch Schritt 1 automatisch):
   - **„Text trennen"** — Trennen mit: **Zeilenumbrüche**.
     ⚠️ Auf die Eingabe-Variable der Aktion tippen und explizit
     **„Kurzbefehl-Eingabe"** auswählen — Shortcuts verdrahtet das nicht
     zuverlässig automatisch; bleibt sie leer, passiert beim Teilen einfach nichts.
   - **„Mit jedem Element wiederholen"** — und *innerhalb* der Wiederholung
     (eingerückt zwischen „Wiederholen" und „Ende Wiederholung"):
     - **„Neue Erinnerung erstellen"** — als Erinnerungs-Text die Variable
       **„Wiederholungselement"** einsetzen (⚠️ nicht „Text"/„Kurzbefehl-Eingabe" —
       sonst landet in jeder Erinnerung die komplette Liste),
       Liste: **„Bei jeder Ausführung fragen"** (oder fest die Einkaufsliste aus Schritt 1)

### 3. Benutzung

Rezept auf der Seite öffnen → ggf. vorher abhaken, was schon da ist →
📲-Button → im Share-Sheet **„Zur Einkaufsliste"** wählen → Ziel-Liste bestätigen.
Jede Zeile wird eine eigene Erinnerung.

## Fallback ohne Kurzbefehl

Text exportieren/kopieren und in Erinnerungen in ein neues Element **einfügen** —
iOS macht aus mehrzeilig eingefügtem Text automatisch einzelne Erinnerungen.

## Grenzen

- Erinnerungen ist von außen nicht ansteuerbar (kein CalDAV mehr seit iOS 13),
  deshalb läuft der Import immer über das iPhone selbst.
- Die Laden-Zuordnung steckt nur in der Wahl der Ziel-Liste; innerhalb einer
  Liste sortiert Erinnerungen selbst nach Warengruppen.
