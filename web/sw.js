
const VERSION = "rs-v11";
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
  if (e.request.method !== "GET" || url.pathname.includes("/video/") || url.pathname.endsWith(".pdf")) return;

  const appFile = url.origin === location.origin && !/\/data\/(segments|model|replay2024|heat|y1997|metrics)\.js$/.test(url.pathname);
  if (appFile) {
    e.respondWith(fetch(e.request).then((r) => { const cp = r.clone(); caches.open(VERSION).then((c) => c.put(e.request, cp)); return r; })
      .catch(() => caches.match(e.request)));
    return;
  }

  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((r) => {
    if (r.ok && (url.origin === location.origin || url.host.includes("arcgisonline") || url.host.includes("cdnjs"))) {
      const cp = r.clone(); caches.open(VERSION).then((c) => c.put(e.request, cp));
    }
    return r;
  }).catch(() => hit)));
});
