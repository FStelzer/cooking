// Playwright-Rauchtest der Kochmodus-Seite gegen das thit-kho-Beispiel.
// Läuft im Playwright-Container (siehe Taskfile `smoke-kochmodus`); das Paket
// kommt per `npx -p playwright`, PLAYWRIGHT_DIR zeigt auf dessen node_modules.
// Aufruf: node tools/smoke_kochmodus.mjs [screenshot.png]
import { createRequire } from "node:module";
import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";

const req = createRequire(process.env.PLAYWRIGHT_DIR || import.meta.url);
const { chromium } = req("playwright");
const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const PORT = 3456;
const SHOT = process.argv[2];
const MIME = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".webmanifest": "application/manifest+json", ".png": "image/png" };

const server = http.createServer(async (rq, res) => {
  let p = decodeURIComponent(new URL(rq.url, "http://x").pathname);
  if (p.endsWith("/")) p += "index.html";
  try {
    const data = await readFile(path.join(ROOT, p));
    res.writeHead(200, { "content-type": MIME[path.extname(p)] || "application/octet-stream" }).end(data);
  } catch { res.writeHead(404).end(); }
});
await new Promise((r) => server.listen(PORT, "127.0.0.1", r));

const errors = [];
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } }); // Smartphone
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  // Alter Zustand mit Timer-Feld (frühere Fassung) — darf nicht crashen, Timer werden verworfen
  await page.addInitScript(() => { if (!localStorage.getItem("km:gerichte/thit-kho-trung"))
    localStorage.setItem("km:gerichte/thit-kho-trung", JSON.stringify({ timers: { "schmoren#0.0": Date.now() + 60000 } })); });
  await page.goto(`http://127.0.0.1:${PORT}/kochmodus/?r=../gerichte/thit-kho-trung.json`);
  await page.waitForSelector(".row[data-step]");
  assert.equal(await page.locator(".row[data-step]").count(), 9, "9 Schritte erwartet");
  assert.equal(await page.locator(".dock .tm").count(), 0, "alte Timer werden nicht übernommen");
  assert.match(await page.locator("#title").innerText(), /Thịt kho/);
  const k4 = page.locator('.row[data-step="karamell-der-entscheidende-schritt"]');
  assert.match(await k4.innerText(), /3 EL Zucker/);
  assert.equal(await k4.locator("textarea").count(), 0, "Notiz darf in der Zeile nicht sichtbar sein");
  // Sheet: Volltext einmal, Kurzansicht fett, Hervorhebung, Details, keine Notiz
  await k4.locator("[data-open]").click();
  await page.waitForSelector("#sheet.open");
  const sheetText = await page.locator("#sheet").innerText();
  assert.equal((sheetText.match(/3 EL Zucker mit 1 EL Wasser/g) || []).length, 1, "Kurzansicht wird im Sheet wiederholt");
  assert.ok(sheetText.includes("kostet 3 EL Zucker und 5 Minuten"), "Volltext unvollständig");
  assert.equal(await page.locator("#sheet .action-span").count(), 1);
  assert.ok((await page.locator("#sheet mark.cue").count()) >= 1, "Cue-Hervorhebung fehlt");
  assert.equal(await page.locator("#sheet textarea").count(), 0, "keine Notiz pro Schritt");
  assert.match(await page.locator("#sheet .details").innerText(), /Dauer/);
  await page.click("#sheet .close");
  // Allgemeine Notiz in der Notizen-Ansicht
  await page.click('button[data-view="notizen"]');
  await page.fill("#noteBox", "dunkler als gedacht ging gut");
  await page.waitForTimeout(500);
  await page.click('button[data-view="kochen"]');
  // Skalieren ×2 ersetzt inline
  await page.click('button[data-factor="2"]');
  assert.match(await page.locator('.row[data-step="karamell-der-entscheidende-schritt"]').innerText(), /6 EL Zucker mit 2 EL Wasser/);
  assert.match(await page.locator("#meta").innerText(), /8 Portionen/);
  await page.click('button[data-factor="1"]');
  // Timer aus dem Sheet starten, Dock zeigt ihn, überlebt Reload
  await page.locator('.row[data-step="schmoren"] [data-open]').click();
  await page.click('#sheet [data-start="0"]');
  assert.equal(await page.locator(".dock .tm").count(), 1);
  await page.click("#sheet .close");
  // Schritt mit mehr Inhalt: Haken in der Liste öffnet die Details, abgehakt wird im Sheet
  await page.click('.row[data-step="fleisch-vorbereiten-blanchieren"] input[data-done]');
  await page.waitForSelector("#sheet.open");
  assert.ok(!(await page.locator('.row[data-step="fleisch-vorbereiten-blanchieren"] input[data-done]').isChecked()), "Liste hakt nicht direkt ab");
  assert.match(await page.locator('.row[data-step="fleisch-vorbereiten-blanchieren"] .more').innerText(), /weitere/);
  await page.check("#sheet .donebar input");
  // Blättern im Sheet (Knopf und Pfeiltaste)
  assert.match(await page.locator("#sheet .nav small").innerText(), /^1\/9$/);
  await page.click('#sheet [data-nav="1"]');
  assert.match(await page.locator("#sheet .nav small").innerText(), /^2\/9$/);
  await page.keyboard.press("ArrowLeft");
  assert.match(await page.locator("#sheet .nav small").innerText(), /^1\/9$/);
  await page.click("#sheet .close");
  await page.reload();
  await page.waitForSelector(".row[data-step]");
  assert.equal(await page.locator(".dock .tm").count(), 1, "Timer überlebt Reload nicht");
  assert.ok(await page.locator('.row[data-step="fleisch-vorbereiten-blanchieren"] input[data-done]').isChecked());
  assert.match(await page.locator("#progress").innerText(), /1 von 9/);
  // Neu kochen: nach Bestätigung sind Haken und Timer weg
  page.once("dialog", (d) => d.dismiss());
  await page.click("#reset");
  assert.match(await page.locator("#progress").innerText(), /1 von 9/, "Abbrechen lässt alles stehen");
  page.once("dialog", (d) => d.accept());
  await page.click("#reset");
  assert.match(await page.locator("#progress").innerText(), /0 von 9/);
  assert.equal(await page.locator(".dock .tm").count(), 0, "Timer zurückgesetzt");
  // Notizen-Ansicht + Export (nach Reload)
  await page.click('button[data-view="notizen"]');
  const out = await page.locator("#mdOut").inputValue();
  assert.ok(out.includes("Notizen aus dem Kochmodus") && out.includes("dunkler als gedacht"), out);
  // Einkauf
  await page.click('button[data-view="einkauf"]');
  assert.equal(await page.locator("ul.shop li").count(), 17);
  assert.match(await page.locator("#main").innerText(), /4–5 EL Fischsauce/);
  await page.click('button[data-factor="2"]');
  assert.match(await page.locator("#main").innerText(), /4–5 EL Fischsauce · braucht 8–10 EL/);
  await page.click('button[data-factor="1"]');
  // Lesen: Sektionen in Dokumentreihenfolge
  await page.click('button[data-view="lesen"]');
  const h2 = await page.locator("#main h2").allInnerTexts();
  assert.deepEqual(h2.slice(0, 3), ["Beschaffung", "Einkaufsliste", "Zubereitung"], h2.join(", "));
  assert.ok(h2.includes("Learnings") && h2.includes("Notizen"));
  // Menü: Plan-Ansicht (Phasen × Gänge), Gang-Gruppierung, Stub-Hinweis
  await page.goto(`http://127.0.0.1:${PORT}/kochmodus/?r=../menues/menue-november.json`);
  await page.waitForSelector(".gantt");
  assert.equal(await page.locator(".gantt .ph:not(.corner)").count(), 9, "9 Phasen erwartet (inkl. Saison)");
  assert.equal(await page.locator(".gantt .lane").count(), 5, "Menü + 4 Gänge");
  assert.equal(await page.locator(".chip").count(), 32, "32 Zeitplan-Einträge");
  assert.equal(await page.locator(".chip.derived").count(), 0, "gebautes JSON: alle Einträge stehen im Markdown");
  await page.locator('.chip[data-open="gang-2-reduktion"]').click();
  await page.waitForSelector("#sheet.open");
  assert.match(await page.locator("#sheet .lbl").innerText(), /Gang 2.*Beurre-blanc.*Schritt 12/);
  await page.click("#sheet .close");
  await page.click('button[data-view="kochen"]');
  assert.equal(await page.locator(".phase").count(), 9, "9 Phasen in der Kochen-Ansicht");
  assert.equal(await page.locator(".row[data-step]").count(), 63, "60 Schritte, drei davon in zwei Phasen (Knochen rösten, Jus reduzieren, Kaffee-Crumble)");
  assert.equal(await page.locator(".row.plain").count(), 3, "3 reine Text-Einträge (Dry-Brine, Weg B in den Kühlschrank, Ofen für Teller)");
  assert.equal(await page.locator('.phase:has(h2:text("Ohne Platz"))').count(), 0, "alle Schritte im Zeitplan platziert");
  const order = await page.locator(".phase h2").allInnerTexts();
  assert.deepEqual(order.slice(0, 4), ["Saison-Teil (erledigt 09/2026)", "T-2", "T-1", "Vormittags"], order.join(", "));
  assert.match(await page.locator('.phase:has(h2:text("Gang 2 (+0:20)")) .row[data-step]').first().innerText(), /^8\. Pralinen wälzen/, "Service-Phase Gang 2 beginnt mit Pralinen wälzen (Schritt 8)");
  await page.click('button[data-order="gang"]');
  assert.equal(await page.locator(".course").count(), 4, "4 Gänge im Gang-Modus");
  assert.equal(await page.locator(".course .empty").count(), 0, "keine Stub-Gänge mehr");
  await page.reload(); await page.waitForSelector(".gantt"); await page.click('button[data-view="kochen"]');
  assert.equal(await page.locator(".course").count(), 4, "Reihenfolge-Wahl überlebt Reload");
  await page.click('button[data-order="ablauf"]');
  await page.click('button[data-view="einkauf"]');
  assert.equal(await page.locator("ul.shop li").count(), 55, "55 Zutaten in der generierten Einkaufsliste");
  await page.click('button[data-view="lesen"]');
  assert.ok((await page.locator("#main h2").allInnerTexts()).includes("Rezepte"));
  // Varianten: Auswahl blendet Schritte ein/aus, tauscht Mengen, wechselt Einkauf und Zeitpläne, überlebt Reload
  await page.goto(`http://127.0.0.1:${PORT}/kochmodus/?r=../backen/vollkornbroetchen.json`);
  await page.waitForSelector(".row[data-step]");
  assert.equal(await page.locator("select[data-variant]").count(), 2, "zwei Dimensionen: Mehl, Weg");
  assert.equal(await page.locator('.row[data-step="einfrieren"]').count(), 1);
  assert.equal(await page.locator('.row[data-step="stueckgare"]').count(), 0, "Weg B ausgeblendet");
  await page.selectOption('select[data-variant="mehl"]', "dinkel");
  await page.selectOption('select[data-variant="weg"]', "direkt-backen");
  assert.equal(await page.locator('.row[data-step="einfrieren"]').count(), 0, "Weg A ausgeblendet");
  assert.equal(await page.locator('.row[data-step="stueckgare"]').count(), 1);
  assert.match(await page.locator('.row[data-step="autolyse"]').innerText(), /390 g Dinkelvollkornmehl, 40 g Wasser/);
  await page.click('button[data-view="einkauf"]');
  const shop = await page.locator("#main").innerText();
  assert.ok(shop.includes("Dinkelvollkornmehl") && !shop.includes("Weizenvollkornmehl"), "Einkauf der Dinkel-Variante");
  await page.reload(); await page.waitForSelector("select[data-variant]");
  assert.equal(await page.locator('select[data-variant="mehl"]').inputValue(), "dinkel", "Wahl überlebt Reload");
  await page.selectOption('select[data-variant="weg"]', "kombi");
  await page.click('button[data-view="plan"]');
  assert.deepEqual(await page.locator("#main > h2").allInnerTexts(), ["Zeitplan Backtag", "Zeitplan aus dem Frost"]);
  await page.click('button[data-view="lesen"]');
  assert.ok((await page.locator("#main").innerText()).includes("(Weizen-Roggen: 90 g, Dinkel: 40 g)"), "Lesen zeigt alle Varianten");
  // App: ohne ?r= das zuletzt geöffnete Rezept (eben: Brötchen), ?liste=1 = Rezeptliste
  await page.goto(`http://127.0.0.1:${PORT}/kochmodus/`);
  await page.waitForSelector(".row[data-step]");
  assert.match(await page.locator("#title").innerText(), /Vollkornbrötchen/, "zuletzt geöffnetes Rezept");
  await page.goto(`http://127.0.0.1:${PORT}/kochmodus/?liste=1`);
  await page.waitForSelector("a.pick");
  const n = JSON.parse(await (await fetch(`http://127.0.0.1:${PORT}/kochmodus/rezepte.json`)).text()).length;
  assert.equal(await page.locator("a.pick").count(), n, "Rezeptliste = rezepte.json");
  await page.locator('a.pick:has-text("Bò lúc lắc")').click();
  await page.waitForSelector(".row[data-step]");
  // Schnell-Timer ohne Schrittbezug
  await page.click("#addTimer");
  await page.fill("#qlabel", "Nudeln");
  await page.click('#quick [data-quick="300"]');
  assert.match(await page.locator(".dock .tm").innerText(), /Nudeln/);
  assert.equal(await page.locator(".dock .tm.foreign").count(), 0, "eigener Timer ohne Herkunft");
  // Timer sind rezeptübergreifend: Liste zeigt ihn, anderes Rezept nennt die Herkunft, Link führt zurück
  await page.goto(`http://127.0.0.1:${PORT}/kochmodus/?liste=1`);
  await page.waitForSelector("a.pick");
  assert.match(await page.locator(".dock .tm").innerText(), /Nudeln/, "Timer in der Rezeptliste");
  await page.locator('a.pick:has-text("Vollkornbrötchen")').click();
  await page.waitForSelector(".row[data-step]");
  assert.match(await page.locator(".dock .tm.foreign .origin").innerText(), /^Bò lúc lắc$/, "Herkunft beim fremden Rezept");
  await page.click(".dock .tm.foreign .origin");
  await page.waitForSelector(".row[data-step]");
  assert.match(await page.locator("#title").innerText(), /Bò lúc lắc/);
  assert.equal(await page.locator(".dock .tm.foreign").count(), 0);
  await page.click('.dock [data-tact="stop"]');
  // Tablet quer: Detailblatt rechts neben der Liste, offener Schritt markiert
  await page.setViewportSize({ width: 1200, height: 800 });
  await page.locator('.row[data-step="sauce-anruehren"] [data-open]').click();
  await page.waitForSelector("#sheet.open");
  const box = await page.locator("#sheet").boundingBox();
  assert.ok(box.x > 500 && box.height > 600, `Sheet rechts als Spalte (x=${box.x}, h=${box.height})`);
  assert.equal(await page.locator(".row.current").count(), 1);
  assert.ok(!(await page.locator("#backdrop").isVisible()), "kein Abdunkeln im Split");
  await page.click('#sheet [data-nav="1"]');
  assert.equal(await page.locator('.row.current[data-step="essig-zwiebeln-ansetzen"]').count(), 1, "Markierung wandert mit");
  await page.click("#sheet .close");
  await page.setViewportSize({ width: 390, height: 844 });
  // Offline: Service Worker liefert App-Hülle und zuletzt geladenes Rezept aus dem Cache
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload(); await page.waitForSelector(".row[data-step]");  // jetzt vom SW kontrolliert
  await page.context().setOffline(true);
  await page.reload(); await page.waitForSelector(".row[data-step]");
  assert.match(await page.locator("#title").innerText(), /Bò lúc lắc/, "offline geladen");
  await page.context().setOffline(false);
  if (SHOT) {
    await page.click('button[data-view="plan"]');
    await page.screenshot({ path: SHOT.replace(/\.png$/, "-plan.png") });
    await page.goto(`http://127.0.0.1:${PORT}/kochmodus/?r=../gerichte/thit-kho-trung.json`);
    await page.waitForSelector(".row[data-step]");
    await page.click('button[data-view="kochen"]');
    await page.screenshot({ path: SHOT });
    await page.locator('.row[data-step="karamell-der-entscheidende-schritt"] [data-open]').click();
    await page.waitForSelector("#sheet.open");
    await page.screenshot({ path: SHOT.replace(/\.png$/, "-sheet.png") });
  }
} finally {
  await browser.close();
  server.close();
}
if (errors.length) { console.log("Browser-Fehler:\n  " + errors.join("\n  ")); process.exit(1); }
console.log("Rauchtest ok: thit-kho (9 Schritte, Sheet, Notiz, Skalierung, Timer, Export, Einkauf, Lesen) + Menü (Plan 9×5, 32 Chips, 60 Schritte, 55 Posten) + Varianten (Brötchen: Ein-/Ausblenden, Mengen, Einkauf, Zeitpläne) + App (Liste, zuletzt geöffnet, Schnell-Timer, Split, offline)");
