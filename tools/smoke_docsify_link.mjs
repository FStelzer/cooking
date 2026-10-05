// Prüft im Container: Docsify-Seite des Rezepts zeigt den Kochmodus-Knopf, Klickziel lädt den Kochmodus.
import { createRequire } from "node:module";
import http from "node:http"; import { readFile } from "node:fs/promises"; import path from "node:path"; import assert from "node:assert/strict";
const { chromium } = createRequire(process.env.PLAYWRIGHT_DIR || import.meta.url)("playwright");
const ROOT = "/work", PORT = 3457;
const MIME = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".md": "text/markdown" };
const server = http.createServer(async (rq, res) => {
  let p = decodeURIComponent(new URL(rq.url, "http://x").pathname); if (p.endsWith("/")) p += "index.html";
  try { const d = await readFile(path.join(ROOT, p)); res.writeHead(200, { "content-type": MIME[path.extname(p)] || "application/octet-stream" }).end(rq.method === "HEAD" ? "" : d); }
  catch { res.writeHead(404).end(); }
});
await new Promise((r) => server.listen(PORT, "127.0.0.1", r));
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.goto(`http://127.0.0.1:${PORT}/#/gerichte/thit-kho-trung`);
  await page.waitForSelector(".markdown-section h1 .kochmodus-btn", { timeout: 20000 });
  const href = await page.locator(".kochmodus-btn").getAttribute("href");
  assert.equal(href, "kochmodus/?r=../gerichte/thit-kho-trung.json");
  await page.goto(`http://127.0.0.1:${PORT}/#/schwangerschaft/leitfaden`);
  await page.waitForSelector(".markdown-section h1");
  await page.waitForTimeout(800);
  assert.equal(await page.locator(".kochmodus-btn").count(), 0, "Leitfaden hat kein JSON, darf keinen Knopf haben");
  await page.goto(`http://127.0.0.1:${PORT}/${href}`);
  await page.waitForSelector(".row[data-step]");
  assert.equal(await page.locator(".row[data-step]").count(), 9);
} finally { await browser.close(); server.close(); }
console.log("Docsify-Link ok: Knopf nur bei vorhandenem JSON, Ziel lädt den Kochmodus");
