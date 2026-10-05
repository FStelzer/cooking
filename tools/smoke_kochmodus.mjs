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
const MIME = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" };

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
  // Alten Zustand der ersten Fassung vorab setzen (timers als Objekt) — darf nicht crashen
  await page.addInitScript(() => { if (!localStorage.getItem("km:gerichte/thit-kho-trung"))
    localStorage.setItem("km:gerichte/thit-kho-trung", JSON.stringify({ timers: { "schmoren#0.0": Date.now() + 60000 } })); });
  await page.goto(`http://127.0.0.1:${PORT}/kochmodus/`);
  await page.waitForSelector(".row[data-step]");
  assert.equal(await page.locator(".row[data-step]").count(), 9, "9 Schritte erwartet");
  assert.equal(await page.locator(".dock .tm").count(), 1, "migrierter Timer fehlt im Dock");
  await page.click('.dock [data-tact="stop"]');
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
  await page.check('.row[data-step="fleisch-vorbereiten-blanchieren"] input[data-done]');
  await page.reload();
  await page.waitForSelector(".row[data-step]");
  assert.equal(await page.locator(".dock .tm").count(), 1, "Timer überlebt Reload nicht");
  assert.ok(await page.locator('.row[data-step="fleisch-vorbereiten-blanchieren"] input[data-done]').isChecked());
  assert.match(await page.locator("#progress").innerText(), /1 von 9/);
  // Notizen-Ansicht + Export (nach Reload)
  await page.click('button[data-view="notizen"]');
  const out = await page.locator("#mdOut").inputValue();
  assert.ok(out.includes("Notizen aus dem Kochmodus") && out.includes("dunkler als gedacht"), out);
  // Einkauf
  await page.click('button[data-view="einkauf"]');
  assert.equal(await page.locator("ul.shop li").count(), 17);
  assert.match(await page.locator("#main").innerText(), /4–5 EL Fischsauce/);
  await page.click('button[data-factor="2"]');
  assert.match(await page.locator("#main").innerText(), /8–10 EL Fischsauce/);
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
  if (SHOT) {
    await page.click('button[data-view="plan"]');
    await page.screenshot({ path: SHOT.replace(/\.png$/, "-plan.png") });
    await page.goto(`http://127.0.0.1:${PORT}/kochmodus/`);
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
console.log("Rauchtest ok: thit-kho (9 Schritte, Sheet, Notiz, Skalierung, Timer, Export, Einkauf, Lesen) + Menü (Plan 9×5, 32 Chips, 60 Schritte, 55 Posten)");
