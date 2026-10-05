# REZEPTFORMAT — Spezifikation für Rezepte und Menüs

Jedes Rezept ist eine Markdown-Datei in diesem Format. Daraus erzeugt `task build`
deterministisch eine JSON-Datei für Validator, Einkaufsliste und Kochmodus. Der
Parser liest **nur**, was hier beschrieben ist; alles andere ist freier Text, der
unverändert erhalten bleibt, aber keine Daten liefert. Was fehlt, meldet `cli lint`.

Dieses Dokument ist die Vorlage für neue Rezepte: Gerüst kopieren, ausfüllen,
`task build`, `task validate`.

## 1. Gerüst eines Gerichts

```markdown
# Thịt kho trứng — vietnamesisches Karamell-Schweinefleisch (4 Portionen)

*Aktive Zeit 30 Min., gesamt 2–2,5 Std. Equipment: schwerer Topf mit Deckel, kleiner Topf.*

## Beschaffung

- **Schweinebauch:** am Stück, gern mit Schwarte; REWE Center.

## Einkaufsliste

### REWE Center
**Fleisch & Fisch:**
- [ ] 900 g Schweinebauch am Stück

### Asialaden
- [ ] 4–5 EL Fischsauce *(z. B. Red Boat)*
- [ ] 500–600 ml Kokoswasser (ungesüßt)

### Vorrat prüfen
- [ ] Zucker, Salz, Pfeffer — Kleinmengen

## Zubereitung

**1. Blanchieren (10 Min.)**
*jederzeit · Herd*
Schweinebauch in 4 cm große Würfel schneiden. In kaltem Wasser aufsetzen, aufkochen,
2–3 Min. sprudeln lassen, abgießen. *Entfernt Trübstoffe, die Sauce bleibt klar.*

**2. Karamell (5 Min.)**
*jederzeit · Herd*
3 EL Zucker mit 1 EL Wasser bei mittlerer Hitze schmelzen, **nicht rühren**, nur den
Topf schwenken, bis das Karamell tief bernsteinfarben ist. *Zu schwarz = bitter, dann
lieber neu starten.*

**3. Schmoren (90–120 Min.)**
*nach Blanchieren, Karamell · Herd*
Mit 500–600 ml Kokoswasser auffüllen, bis das Fleisch knapp bedeckt ist. 2–3 EL
Fischsauce dazu, bei kleinster Hitze schmoren. Nach 60 Min. einmal wenden.

**4. Reduzieren (20–30 Min.)**
*letzte 20–30 Min. von Schmoren*
Deckel abnehmen und die Sauce sirupartig einkochen, bis sie das Fleisch glänzend überzieht.

**5. Servieren (ca. 5 Min.)**
*nach Reduzieren*
Fleisch mit viel Sauce auf Reis.

## Kinder-Anpassung

- Chilis bleiben ganz, Kinderportion ist automatisch mild.

## Zeitplan

| T−2:30 | Blanchieren, Karamell, Schmoren starten |
| T−0:30 | Deckel ab, reduzieren |

## Learnings

**Gekocht 07/2026.** Kurzfassung …

### Details
- …

## Notizen

- …
```

## 2. Gerüst eines Menüs

```markdown
# 🚧 Menü November — Tomatenwasser / Kaisergranat (4–5 Personen)

> [!NOTE]
> **Status: In Arbeit** — Testläufe stehen aus.

## Menüfolge & Dramaturgie

| # | Gang | Charakter |
|---|---|---|
| 1 | Klares Tomatenwasser | kalt, klar |

## Einkaufsliste

### Buhara Seafood
- [ ] 12 Stück Kaisergranat, TK roh — Gang 2

## Rezepte

### 1. Klares Tomatenwasser

*Am Abend 15 Min. Pro Portion 60–70 ml. Equipment: feines Sieb.*

**Teller-Logik:** Warum dieser Gang so gebaut ist.

**1. Grundwürzung (5 Min.)**
*1–2 h vor Service*
350 ml Tomatenwasser mit 6–8 Tropfen Worcestershire würzen, kalt ziehen lassen.

**2. Anrichten (ca. 5 Min.)**
*nach Grundwürzung*
Vorgekühlte Gläser, je 60–70 ml angießen.

### 2. Kaisergranat mit Beurre blanc

*Vortag 45 Min. Am Abend 25 Min. Equipment: 2 Pfannen, Thermometer.*

**Mango-Gel (bis 2 Tage vorher, ideal am Vortag, Kühlschrank):**

**1. Mango kochen (5–10 Min.)**
*jederzeit · Herd*
1 reife Mango mit 1–2 EL Zucker 5–10 Min. weich kochen, mixen, passieren.

**Beurre blanc (20 Min. vor dem Gang, hält bis 2 h warm bei 50–55 °C):**

**2. Reduktion (ca. 8 Min.)**
*jederzeit · Herd*
2 Schalotten mit 110 ml Verjus sirupös einreduzieren.

**3. Montieren (ca. 6 Min.)**
*Herd*
170 g eiskalte Butter würfelweise einschlagen, **nie über 58 °C**.

**4. Anrichten (ca. 3 Min.)**
*nach Montieren, Mango kochen*
Spiegel Beurre blanc, Mango-Gel-Punkte am Rand.

**Kind (3 J.):** 1 Schwanz, Mango-Gel ohne Chili.

> **Profi-Tipps:**
> - Agar-Punkte verlaufen nicht, auch neben heißem Kaisergranat.

**Offen (Testlauf):**
- [ ] Gel-Süße gegen Kaisergranat auf dem ganzen Teller prüfen

## Zeitplan

- T-1: Mango-Gel · Kaisergranat auftauen
- Nachmittags: Kaisergranat auslösen
- Gang 1 (0:00): Tomatenwasser anrichten
- Gang 2 (+0:20): Beurre blanc (20 Min. vor dem Gang) · Kaisergranat braten · Anrichten

## To-do gesamt

- [ ] Verjus bestellen
```

## 3. Kopf

- `# Titel (Ausbeute)`. Die Klammer am Ende nennt die Ausbeute: `4 Portionen`,
  `12 Stück`, `4–5 Personen`. `🚧 ` vor dem Titel markiert „in Arbeit".
- Danach optional `> [!NOTE]`-Boxen (Status, Hinweise).
- Eine kursive Meta-Zeile: `*Aktive Zeit X, gesamt Y. Equipment: a, b, c.*` Die
  Dauern werden gelesen, die Geräteliste kommagetrennt bis zum Punkt.

## 4. Sektionen

| `##`-Sektion | Pflicht | Inhalt |
|---|---|---|
| `Einkaufsliste` | ja | Abschnitt 7 |
| `Zubereitung` | ja (Gericht) | Schritte, Abschnitt 5–6 |
| `Rezepte` mit `### N. Gang` | ja (Menü) | pro Gang ein Block wie eine Zubereitung |
| `Zeitplan` | empfohlen | Abschnitt 8 |
| `Learnings` | nach dem Kochen | Abschnitt 9 |
| `To-do …` | optional | Aufgaben `- [ ]` |
| `Beschaffung`, `Kinder-Anpassung`, `Schwangerschaft & GDM`, `Quellen & Entscheidungen`, `Notizen`, `Stil-Entscheidung` | optional | freier Text; der Name bestimmt das Tag |
| `Mengen-Check` | nein | wird generiert, nicht schreiben |

## 5. Komponenten und Schritte

**Komponenten** gibt es, wenn ein Rezept mehrere Stränge hat (Gel, Crumble, Sauce).
Eine Komponente beginnt mit einer fetten Zeile, die allein steht und mit `:**`
endet. Die Klammer nennt, wann sie gemacht wird und wie lange sie hält:

```markdown
**Mango-Gel (bis 2 Tage vorher, ideal am Vortag, Kühlschrank):**
**Beurre blanc (20 Min. vor dem Gang, hält bis 2 h warm bei 50–55 °C):**
**Walnusscrumble (Vortag, Raumtemperatur):**
```

Jede Komponente erzeugt ein Produkt mit ihrem Namen. Nennt ein Schritt einer anderen
Komponente diesen Namen, gilt das als Verbrauch. Ein Rezept ohne solche Zeilen ist
eine einzige Komponente. Fette Zeilen **mit Text dahinter** (`**Teller-Logik:** …`,
`**Kind (3 J.):** …`) sind Prosa-Blöcke, keine Komponenten.

**Schritte** haben immer diese Form:

```markdown
**N. Titel (Dauer)**
*Meta-Zeile (optional)*
Text des Schritts, beliebig lang, Zeilenumbrüche egal.
```

- `N` läuft pro Rezept bzw. pro Gang durch, auch über Komponenten hinweg.
- Der **Titel ist die Kennung** des Schritts (Slug). Er ist innerhalb des Rezepts
  eindeutig und wird nach dem ersten Kochen nicht mehr umbenannt. Zwei bis vier
  Wörter: „Karamell", „Blöcke anbraten", „Pralinen wälzen".
- **Dauer** in der Klammer: `5 Min.`, `90–120 Min.`, `3–3,5 Std.`, `30 Sek.`,
  `über Nacht`. Geschätzt: `ca. 8 Min.`. Zusätze in derselben Klammer: `parallel`
  (läuft nebenher weiter), `passiv` (braucht niemanden am Herd), `jederzeit` (keine
  Voraussetzung). Jeder Schritt soll eine Dauer haben; sonst kann kein Zeitplan
  gerechnet werden.
- **Meta-Zeile** direkt unter der Überschrift, kursiv, Klauseln mit ` · `:

| Klausel | Bedeutung |
|---|---|
| `nach Karamell, Marinieren` | Voraussetzungen, über **Titel** anderer Schritte, nie über Nummern |
| `jederzeit` | keine Voraussetzung |
| `≤ 30 Min. vor dem Anrichten` | muss innerhalb dieser Spanne vor dem Schritt „Anrichten" liegen |
| `letzte 20–30 Min. von Schmoren` | läuft am Ende des Schritts „Schmoren" mit |
| `1 Std. vor Gang 3`, `1–2 h vor Service`, `20 Min. vor dem Gang` | Zeitanker relativ zum Service |
| `Ofen 160 °C`, `Herd`, `2 Pfannen`, `Grill` | belegte Ressourcen |
| `fertig bei ≥ 70 °C Kern`, `fertig wenn die Gabel sich ohne Widerstand dreht` | Abbruchkriterium statt Uhr |
| `ergibt Beurre blanc`, `hält bis 2 h` | Produkt und Haltbarkeit, wenn es keine Komponenten-Zeile gibt |
| `Technik: technik/mini-projekte.md#beurre-blanc` | Verweis in die Technik-Sammlung |

Fehlt die Meta-Zeile, ist der vorhergehende Schritt die Voraussetzung.

## 6. Schritttext

Der Text ist frei, aber vier Formen tragen Bedeutung:

- **Erster Satz = die Handlung.** Er ist die Kurzansicht im Kochmodus. Was man tut,
  womit, in welcher Menge, bei welcher Hitze. Erklärungen kommen danach.
- **Fett** = Grenze oder Warnung: `**nie über 58 °C**`, `**nicht rühren**`.
- **Kursiver Satz am Ende** = das Warum. Beginnt er mit „Fallback", „Rettung",
  „Gebrochen?" oder „Zu …", ist es eine Rettung.
- „bis …"-Nebensätze = Erkennungszeichen: `bis das Fleisch vom Knochen fällt`.

Mengen und Zeiten im Text werden erkannt, wenn sie so geschrieben sind:

| Form | Beispiel | Bedeutung |
|---|---|---|
| Zahl Einheit Zutat | `3 EL Zucker`, `500–600 ml Kokoswasser`, `½ Limette`, `1 Prise Salz`, `6 Eier` | Dosierung; das Zutatenwort muss in der Einkaufsliste vorkommen |
| Mengenwort Zutat | `reichlich Pfeffer`, `ein Schuss Kokoswasser` | Dosierung ohne Zahl |
| `je 15 g Butter` | | Menge pro Pfanne/Person |
| `2 × 15 g Butter` | | Vervielfacher |
| dieselbe Zahl derselben Zutat erneut | `Die 6 Eier hineinlegen` | keine neue Menge |
| Zahl + Min./Sek./Std. | `9–10 Min.`, `30 Sek.` | Timer |
| `Nach 60 Min. …` | | Ereignis innerhalb des Schritts |
| Zahl + °C | `60–62 °C Kern`, `Ofen 160 °C`, `nie über 58 °C` | Temperatur (Art nach dem Wort davor) |

Zirka immer als `ca.` oder `\~` (Backslash-Tilde, sonst streicht Docsify durch).

## 7. Einkaufsliste

```markdown
## Einkaufsliste

### Asialaden
- [ ] 4–5 EL Fischsauce *(z. B. Red Boat)*

### REWE Center
**Obst & Gemüse:**
- [ ] 4 Schalotten — Gang 2
- [ ] 2 Karotten + 1 kleiner Rettich *(fürs Pickle, optional)*
- [x] Tomatenwasser — liegt im Gefrierfach

### Vorrat prüfen
- [ ] Salz, Pfeffer, Zucker — Kleinmengen
```

- `###` = Laden: `Asialaden`, `REWE Center`, `Aldi / REWE`, `Selgros`,
  `Buhara Seafood`, `Online`, `Drogerie`, `Vorrat prüfen`. Reihenfolge = Besuchsreihenfolge.
- `**…:**` = Warengruppe: `Obst & Gemüse`, `Fleisch & Fisch`, `Milchprodukte & Eier`,
  `Trockenwaren`, `Würzmittel & Gewürze`, `Getränke`, `Tiefkühl`, `Sonstiges`.
- Posten: `- [ ] Menge Name[, Zusatz] [(Klammer)] [— Gang N] [*(Notiz)*]`. Die Menge
  ist das Gebinde (was man kauft); der Bedarf wird aus den Schritten gerechnet.
  `[x]` = vorhanden. `Optional:` am Anfang = optional. `A + B` sind zwei Zutaten,
  `A oder B` eine. Das erste Hauptwort des Namens ist die Kennung; es muss in den
  Schritten wiederkehren (`Schalotten` ↔ `2 Schalotten`).

## 8. Zeitplan

Für Menüs und Vorbereitungen über mehrere Tage:

```markdown
## Zeitplan
- T-1: Mango-Gel · Walnusscrumble · Kaisergranat auftauen
- Nachmittags: Selleriepüree · Chips frittieren
- Gang 1 (0:00): Tomatenwasser anrichten
- Gang 2 (+0:20): Beurre blanc (20 Min. vor dem Gang) · Kaisergranat braten · Anrichten
```

Phasen: `T-2`, `T-1`, `Vortag`, `Vorabend`, `Vormittags`, `Nachmittags`, `Am Abend`,
`Am Tag`, `Gang N (+h:mm)`. Einträge mit ` · ` getrennt. Ein Eintrag wird einem
Schritt oder einer Komponente zugeordnet, wenn er deren **Titel bzw. Namen** nennt;
Einträge ohne Treffer bleiben Text (Tisch decken, Gäste da).

Für ein einzelnes Gericht reicht eine Tabelle relativ zum Essen:

```markdown
| T−1:30 | Marinade mixen, Fleisch anfrieren |
| T−0:20 | Reis aufsetzen |
```

## 9. Learnings und Notizen

```markdown
## Learnings

**Gekocht 07/2026.** Kurzfassung in zwei bis vier Sätzen: Ergebnis, größter Hebel fürs nächste Mal.

### Details
- **Thema:** …

### Notizen aus dem Kochmodus (10/2026)
Freitext, so wie der Kochmodus ihn exportiert.
```

`Gekocht`, `Gebacken` oder `Gemacht` plus `MM/JJJJ` markieren das Rezept als gekocht.

## 10. Was `cli lint` meldet

Schritte ohne Dauer · doppelte Schritt-Titel · `nach …` oder Anker mit unbekanntem
Titel · Mengen im Text ohne passende Zutat in der Einkaufsliste · Zutaten ohne
Dosierung in Schritten · Komponenten ohne Zeitangabe · Zeitplan-Einträge ohne Treffer
· unbekannte Phasen oder Meta-Klauseln. Hinweise sind keine Fehler; sie zeigen, wo
das JSON Lücken hat.
