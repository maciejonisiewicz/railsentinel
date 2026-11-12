const VERSION = "rs-v14";
const SHELL = ["./", "index.html", "about.html", "status.html", "offline.html", "style.css", "app.js", "manifest.webmanifest",
  "vendor/leaflet/leaflet.min.js", "vendor/leaflet/leaflet.min.css",
  "icons/icon-192.png", "icons/icon-512.png", "icons/apple-touch-icon.png", "icons/favicon.png",
  "data/segments.js", "data/powiaty.js"];
const PATIENCE = 3500;
const HEAVY = /\/data\/(segments|model|replay2024|heat|y1997|metrics|powiaty)\.js$/;
const CACHED_HOSTS = /(^|\.)arcgisonline\.com$/;

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => Promise.all(SHELL.map((u) => c.add(u).catch(() => null)))));
  self.skipWaiting();
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))));
  self.clients.claim();
});

const clean = (r) => (r.redirected ? new Response(r.body, { status: r.status, statusText: r.statusText, headers: r.headers }) : r);

async function offlineFallback(req) {
  const hit = await caches.match(req, { ignoreSearch: true });
  if (hit) return hit;
  if (req.mode === "navigate") {
    const off = await caches.match("offline.html");
    if (off) return off;
  }
  return Response.error();
}

async function networkFirst(e) {
  const req = e.request;
  const cached = await caches.match(req, { ignoreSearch: true });
  const net = fetch(req).then(async (r) => {
    if (r.ok) {
      const copy = r.clone();
      await caches.open(VERSION).then((c) => c.put(req, copy));
    }
    return r;
  });
  e.waitUntil(net.catch(() => null));
  try {
    const r = cached
      ? await Promise.race([net, new Promise((resolve) => setTimeout(() => resolve(null), PATIENCE))])
      : await net;
    if (r && r.ok) return clean(r);
    return cached || r || offlineFallback(req);
  } catch (err) {
    return cached || offlineFallback(req);
  }
}

async function cacheFirst(e) {
  const req = e.request;
  const hit = await caches.match(req);
  if (hit) return hit;
  try {
    const r = await fetch(req);
    if (r.ok) {
      const copy = r.clone();
      e.waitUntil(caches.open(VERSION).then((c) => c.put(req, copy)));
    }
    return r;
  } catch (err) {
    return offlineFallback(req);
  }
}

self.addEventListener("fetch", (e) => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.pathname.includes("/video/") || url.pathname.endsWith(".pdf")) return;
  if (url.origin === location.origin) {
    e.respondWith(HEAVY.test(url.pathname) ? cacheFirst(e) : networkFirst(e));
    return;
  }
  if (CACHED_HOSTS.test(url.hostname)) e.respondWith(cacheFirst(e));
});
