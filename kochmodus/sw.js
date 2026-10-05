// Service Worker des Kochmodus: offline kochen (App-Hülle vorab, Rezepte beim Öffnen).
// App-Hülle: sofort aus dem Cache, im Hintergrund aktualisiert (gilt ab dem nächsten Laden).
// Rezepte, Rezeptliste, Seitenaufrufe: Netz zuerst, Cache als Rückfall (auch wenn das Netz hängt) — ein neu gebautes
// Rezept ist sofort da, im Funkloch gilt der letzte Stand.
// Nach Änderungen an der App-Hülle VERSION erhöhen, damit alte Caches verschwinden.
const VERSION = "km-v3";
const SHELL = ["./", "index.html", "app.js", "lib.js", "style.css", "manifest.webmanifest", "rezepte.json",
               "icons/icon-192.png", "icons/icon-512.png", "https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => Promise.allSettled(SHELL.map((u) => c.add(u)))).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
const STATIC = new Set(SHELL.filter((u) => u !== "./" && u !== "rezepte.json").map((u) => new URL(u, self.location).href));
const SLOW_MS = 4000;  // so lange darf das Netz brauchen, bevor ein vorhandener Cache-Stand antwortet
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  const cached = () => caches.match(e.request, { ignoreSearch: e.request.mode === "navigate" });
  const offline = () => cached().then((hit) => hit || new Response("Offline — diese Seite liegt noch nicht im Cache.",
    { status: 503, headers: { "content-type": "text/plain; charset=utf-8" } }));
  const net = fetch(e.request).then((res) => {
    if (res.status === 200 || res.type === "opaque") {  // 206 (Range) lässt sich nicht cachen
      const copy = res.clone();
      e.waitUntil(caches.open(VERSION).then((c) => c.put(e.request, copy)).catch(() => {}));
    }
    return res;
  });
  e.waitUntil(net.catch(() => {}));  // Cache-Update zu Ende führen, auch wenn der Cache schon geantwortet hat
  if (STATIC.has(e.request.url)) {  // App-Hülle: stale-while-revalidate
    e.respondWith(caches.match(e.request).then((hit) => hit || net.catch(offline)));
    return;
  }
  // Funkloch: Netz hängt statt zu scheitern → nach SLOW_MS den Cache nehmen; ohne Treffer weiter aufs Netz warten
  const slow = new Promise((r) => setTimeout(r, SLOW_MS)).then(cached).then((hit) => hit || net);
  e.respondWith(Promise.race([net.catch(offline), slow]));
});
