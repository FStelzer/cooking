// Service Worker des Kochmodus: offline kochen (App-Hülle vorab, Rezepte beim Öffnen).
// Netz zuerst, Cache als Rückfall — ein neu gebautes Rezept ist sofort da, im Funkloch gilt der letzte Stand.
// Nach Änderungen an der App-Hülle VERSION erhöhen, damit alte Caches verschwinden.
const VERSION = "km-v1";
const SHELL = ["./", "index.html", "app.js", "lib.js", "style.css", "manifest.webmanifest", "rezepte.json",
               "icons/icon-192.png", "icons/icon-512.png", "https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => Promise.allSettled(SHELL.map((u) => c.add(u)))).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith(fetch(e.request).then((res) => {
    if (res.ok || res.type === "opaque") { const copy = res.clone(); caches.open(VERSION).then((c) => c.put(e.request, copy)); }
    return res;
  }).catch(() => caches.match(e.request, { ignoreSearch: e.request.mode === "navigate" })));
});
