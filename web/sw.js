/* RailSentinel – Service Worker: aplikacja działa offline (ostatnia pobrana prognoza). */
const VERSION = "rs-v5";
const SHELL = ["./", "index.html", "style.css", "app.js", "sim.js", "manifest.webmanifest",
  "icons/icon-192.png", "icons/icon-512.png", "icons/apple-touch-icon.png", "icons/favicon.png",
  "data/segments.js", "data/metrics.js", "data/model.js", "data/replay2024.js", "data/heat.js", "data/y1997.js",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => Promise.all(SHELL.map((u) => c.add(u).catch(() => null)))));
  self.skipWaiting();
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  // prognoza na żywo: najpierw sieć (świeże dane), w razie braku zasięgu – ostatnia zapisana
  if (url.pathname.endsWith("/data/live.js")) {
    e.respondWith(fetch(e.request).then((r) => { const cp = r.clone(); caches.open(VERSION).then((c) => c.put(e.request, cp)); return r; })
      .catch(() => caches.match(e.request)));
    return;
  }
  // kafelki mapy: z pamięci, jeśli były oglądane
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((r) => {
    if (r.ok && (url.origin === location.origin || url.host.includes("arcgisonline") || url.host.includes("cdnjs"))) {
      const cp = r.clone(); caches.open(VERSION).then((c) => c.put(e.request, cp));
    }
    return r;
  }).catch(() => hit)));
});
