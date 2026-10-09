// Service Worker des Kochmodus: offline kochen.
// - App-Hülle (HTML, JS, CSS, Icons, marked): ein Cache pro Version, beim Installieren komplett geladen und danach
//   nur aus dem Cache bedient — Seite und Skripte passen immer zusammen. VERSION ist ein Hash der Hülle und wird von
//   `task build` gesetzt (`task validate` prüft ihn), jede App-Änderung installiert also eine neue Hülle in einem Zug.
// - Rezepte und Rezeptliste: eigener Cache, den ein Update nicht löscht. Netz zuerst, Cache als Rückfall (auch wenn
//   das Netz hängt) — ein neu gebautes Rezept ist sofort da, im Funkloch gilt der letzte Stand.
// - Am HTTP-Cache des Browsers vorbei: Der Server schickt kein Cache-Control, der Browser cacht heuristisch. Ohne
//   `reload` konnte ein neuer SW altes app.js mit neuem lib.js mischen (Seite hing auf „Lade Rezept …"), ohne
//   `no-cache` kam ein frisch gebautes Rezept-JSON veraltet an.
const VERSION = "km-bfe23b2832";
const DATA = "km-daten";
const SHELL = ["index.html", "app.js", "lib.js", "style.css", "manifest.webmanifest",
               "icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-512.png", "icons/apple-touch-icon.png"];
const CDN = ["https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"];
const STATIC = new Set([...SHELL, ...CDN].map((u) => new URL(u, self.location).href));
const PAGE = new URL("index.html", self.location).href;
const SLOW_MS = 4000;  // so lange darf das Netz brauchen, bevor ein vorhandener Cache-Stand antwortet

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION)
    .then((c) => c.addAll(SHELL.map((u) => new Request(u, { cache: "reload" }))).then(() => Promise.allSettled(CDN.map((u) => c.add(u)))))
    .then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION && k !== DATA).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

const offlinePage = () => new Response("Offline — diese Seite liegt noch nicht im Cache.",
  { status: 503, headers: { "content-type": "text/plain; charset=utf-8" } });

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  // Hülle und Seitenaufrufe (./?r=…): aus dem Versions-Cache, nur beim allerersten Laden übers Netz
  if (req.mode === "navigate" || STATIC.has(req.url)) {
    const key = req.mode === "navigate" ? PAGE : req;
    e.respondWith(caches.open(VERSION).then((c) => c.match(key)).then((hit) => hit || fetch(req).catch(offlinePage)));
    return;
  }
  // Daten: Netz zuerst, in den Daten-Cache schreiben; 206 (Range) lässt sich nicht cachen
  // Treffer aus dem Cache markieren, damit die App „Offline-Stand" zeigen kann (opake Antworten bleiben, wie sie sind)
  const cached = () => caches.open(DATA).then((c) => c.match(req)).then((hit) => {
    if (!hit || hit.type === "opaque") return hit;
    const headers = new Headers(hit.headers); headers.set("x-km-offline", "1");
    return new Response(hit.body, { status: hit.status, statusText: hit.statusText, headers });
  });
  const sameOrigin = new URL(req.url).origin === self.location.origin;
  const net = fetch(req, sameOrigin ? { cache: "no-cache" } : undefined).then((res) => {
    if (res.status === 200 || res.type === "opaque") {
      const copy = res.clone();
      e.waitUntil(caches.open(DATA).then((c) => c.put(req, copy)).catch(() => {}));
    }
    return res;
  });
  const fallback = () => cached().then((hit) => hit || offlinePage());
  e.waitUntil(net.catch(() => {}));  // Cache-Update zu Ende führen, auch wenn der Cache schon geantwortet hat
  // Funkloch: Netz hängt statt zu scheitern → nach SLOW_MS den Cache nehmen; ohne Treffer weiter aufs Netz warten
  const slow = new Promise((r) => setTimeout(r, SLOW_MS)).then(cached).then((hit) => hit || net.catch(fallback));
  e.respondWith(Promise.race([net.catch(fallback), slow]));
});
