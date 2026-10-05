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
  const k4 = page.locator('.row[data-step="karamell"]');
  assert.match(await k4.innerText(), /3 EL Zucker/);
  assert.equal(await k4.locator("textarea").count(), 0, "Notiz darf in der Zeile nicht sichtbar sein");
  // Sheet: Details ohne Wiederholung der Kurzansicht, Hervorhebung, Timer, Notiz
  await k4.locator("[data-open]").click();
  await page.waitForSelector("#sheet.open");
  const sheetText = await page.locator("#sheet").innerText();
  assert.equal((sheetText.match(/3 EL Zucker mit 1 EL Wasser/g) || []).length, 1, "Kurzansicht wird im Sheet wiederholt");
  assert.ok((await page.locator("#sheet mark.cue").count()) >= 1, "Cue-Hervorhebung fehlt");
  await page.fill("#noteBox", "dunkler als gedacht ging gut");
  await page.click("#sheet .close");
  assert.equal(await k4.locator(".hasnote").count(), 1, "Notiz-Punkt fehlt");
  // Skalieren ×2 ersetzt inline
  await page.click('button[data-factor="2"]');
  assert.match(await page.locator('.row[data-step="karamell"]').innerText(), /6 EL Zucker mit 2 EL Wasser/);
  assert.match(await page.locator("#meta").innerText(), /8 Portionen/);
  await page.click('button[data-factor="1"]');
  // Timer aus dem Sheet starten, Dock zeigt ihn, überlebt Reload
  await page.locator('.row[data-step="schmoren"] [data-open]').click();
  await page.click('#sheet [data-start="0"]');
  assert.equal(await page.locator(".dock .tm").count(), 1);
  await page.click("#sheet .close");
  await page.check('.row[data-step="blanchieren"] input[data-done]');
  await page.reload();
  await page.waitForSelector(".row[data-step]");
  assert.equal(await page.locator(".dock .tm").count(), 1, "Timer überlebt Reload nicht");
  assert.ok(await page.locator('.row[data-step="blanchieren"] input[data-done]').isChecked());
  assert.match(await page.locator("#progress").innerText(), /1 von 9/);
  // Notizen-Ansicht + Export
  await page.click('button[data-view="notizen"]');
  const out = await page.locator("#mdOut").inputValue();
  assert.ok(out.includes("step:karamell") && out.includes("dunkler als gedacht"), out);
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
  if (SHOT) {
    await page.click('button[data-view="kochen"]');
    await page.screenshot({ path: SHOT });
    await page.locator('.row[data-step="karamell"] [data-open]').click();
    await page.waitForSelector("#sheet.open");
    await page.screenshot({ path: SHOT.replace(/\.png$/, "-sheet.png") });
  }
} finally {
  await browser.close();
  server.close();
}
if (errors.length) { console.log("Browser-Fehler:\n  " + errors.join("\n  ")); process.exit(1); }
console.log("Rauchtest ok: 9 Schritte, Sheet ohne Wiederholung, Notiz im Sheet, Skalierung, Timer-Dock/Abhaken persistent, Export, Einkauf 17 Posten, Lesen in Reihenfolge");
