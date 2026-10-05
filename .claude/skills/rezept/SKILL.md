---
name: rezept
description: Rezept oder Menü nach REZEPTFORMAT.md erstellen oder normalisieren, dann JSON bauen und validieren. Modi "neu <Quelle oder Idee>" (Recherche, Rückfragen, vollständiges Markdown) und "normalisieren <datei.md>" (Bestand auf die Konvention bringen, Inhalt unverändert).
---

# /rezept — Rezept schreiben oder normalisieren

Du arbeitest in `/home/fs/projects/cooking`. Zwei Modi, erkennbar am ersten Argument:

- `neu <URL | Text | Idee>` — ein neues Rezept oder Menü von Grund auf.
- `normalisieren <pfad.md>` — ein vorhandenes Rezept auf die Konvention bringen.

Lies zuerst, in dieser Reihenfolge, und halte dich daran:

1. `REZEPTFORMAT.md` — die Konvention. Alles, was dort steht, ist Pflicht; alles
   andere ist freier Text.
2. `CLAUDE.md` — Haushalt (2 Erwachsene + Kind 3 J., Schwangerschaft mit GDM),
   Vorlieben, Equipment, Einkaufsquellen (Läden-Vokabular), Patterns.
3. `SCHEMA.md`, Abschnitt „Konvertierungs-Anleitung" und „Zeit-Grammatik" — nur
   wenn eine Zeitangabe unklar ist.

## Modus `neu`

1. **Quelle sichern.** URL per WebFetch holen (Serious Eats und Guardian sind
   blockiert, siehe Memory; Alternativen: ATK, Swasthi, FDA). Text oder Idee
   übernehmen. Herkunft kommt später unter `## Quellen & Entscheidungen`.
2. **Rückfragen stellen** (AskUserQuestion, höchstens vier), nur was die Quelle
   nicht klärt: Personenzahl und Anlass; Kind mit? Schwangerschaft/GDM beachten
   (Leitfaden `schwangerschaft/leitfaden.md`); Beschaffung (welcher Laden,
   Bestellbedarf); Equipment-Grenzen (14-l-Topf, kein Gusseisen, Schnellkochtopf);
   Zeitrahmen (Vortag möglich?). Keine Fragen, deren Antwort in CLAUDE.md steht.
3. **Recherchieren**, wo die Quelle dünn ist: Garpunkte, Temperaturen, Haltbarkeiten,
   Technik-Fallstricke. Quellen nennen.
4. **Schreiben** nach dem Gerüst in REZEPTFORMAT.md (Gericht oder Menü). Pflicht:
   - Jeder Schritt `**N. Titel (Dauer)**`, erster Satz = Handlung, Dauer immer
     (Schätzungen als `ca.`), Meta-Zeile mit `nach <Titel>` / `jederzeit` / Anker /
     Ressourcen, wo es den Ablauf betrifft. Titel eindeutig, kurz.
   - Mengen im Schritt als `Zahl Einheit Zutat` mit dem Zutatenwort aus der
     Einkaufsliste. Jede Zutat der Liste kommt in mindestens einem Schritt vor.
   - Komponenten-Zeilen mit Zeitangabe, wenn es mehrere Stränge gibt.
   - Einkaufsliste nach Läden und Warengruppen, Gebinde statt Bedarf, `— Gang N`
     bei Menüs; Kleinmengen unter `### Vorrat prüfen`.
   - `## Kinder-Anpassung`, bei Schwangerschaft `## Schwangerschaft & GDM`,
     `## Beschaffung`, `## Quellen & Entscheidungen`. Bei neuen, ungetesteten
     Rezepten `🚧 ` im Titel und eine `> [!NOTE]`-Statusbox.
   - Zeitplan für alles, was über einen Tag geht.
5. **Datei anlegen** im passenden Ordner (`gerichte/`, `menues/`, `desserts/`,
   `backen/`, `eis/`, `schwangerschaft/`). Dann `task sidebar`.
6. **Pflichtabschluss** (Abschnitt unten).

## Modus `normalisieren`

Regel Nummer eins: **Der Inhalt bleibt.** Mengen, Temperaturen, Zeiten, Reihenfolge,
Erklärungen, Tipps, Learnings — alles bleibt wörtlich. Geändert wird nur die Form:

- Schritte in `**N. Titel (Dauer)**` bringen; fehlt ein Titel, einen kurzen vergeben;
  fehlt die Dauer, aus dem Text übernehmen oder als `ca.` schätzen.
- Schritte, die über mehrere Tage laufen, an der Tagesgrenze teilen (jeder Schritt
  gehört zu einer Phase); Nummerierung nachziehen; Querverweise auf Nummern durch
  Titel ersetzen.
- Meta-Zeilen ergänzen, wo der Text Abhängigkeiten nennt („parallel", „währenddessen",
  „nach dem Anbraten", „≤ 30 Min. vor dem Anrichten").
- Mengen, die nur in der Einkaufsliste stehen, in den Schritt ziehen, der sie
  verwendet („900 g Schweinebauch würfeln").
- Komponenten-Labels mit Zeitangabe nach der Zeit-Grammatik; Kurzansicht-Regel
  (erster Satz = Handlung) prüfen und nur den Satzbau anfassen, nie den Sinn.
- Einkaufsliste nach Läden und Warengruppen; Kleinmengen nach `### Vorrat prüfen`;
  Posten `Menge Name`.
- `~` als `\~`.

Vor dem Überschreiben die alte Fassung sichern (`git show HEAD:<pfad>` reicht, die
Datei ist versioniert). Danach zwingend:

```sh
git show HEAD:<pfad.md> > /tmp/alt.md
python3 -m tools.recipes.cli treue /tmp/alt.md <pfad.md>
```

Ergebnis lesen: Fehlende Token sind ein Fehler (Inhalt verloren). Neue Token müssen
erklärbar sein (Schätz-Dauern, Anker). Die Liste nicht mehr wörtlich vorkommender
Zeilen Zeile für Zeile prüfen: zulässig sind umgebaute Überschriften und
Einkaufsposten, nichts anderes.

## Pflichtabschluss (beide Modi)

```sh
python3 -m tools.recipes.cli lint <pfad.md>      # Hinweise lesen und beheben, was die Konvention verlangt
python3 -m tools.recipes.cli build <pfad.md>     # JSON daneben
python3 -m tools.recipes.cli check <pfad.json> -v
task smoke-kochmodus                              # nur wenn der Kochmodus betroffen ist (Standard-Rezept geändert)
```

Alle FAIL beheben. Hinweise aus `lint` so weit wie sinnvoll beheben: Schritte ohne
Dauer, Zutaten ohne Dosierung, Mengen ohne Zutat in der Liste, Zeitplan-Einträge
ohne Treffer. Dann committen: Markdown und JSON zusammen, Commit-Nachricht nennt
Modus und Quelle. Nicht pushen.

Am Ende berichten: Datei, Zahl der Schritte und Zutaten, offene Lint-Hinweise mit
Begründung, bei `normalisieren` das Ergebnis von `treue`, und alle Stellen, an
denen eine inhaltliche Entscheidung nötig war (Schätzungen, Titelwahl, Teilungen).
