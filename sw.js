/* Service worker — Perito · Laudo (offline shell) */
const CACHE = "perito-laudo-v1";
const ASSETS = [
  "./",
  "index.html",
  "assistencia.html",
  "manifest.webmanifest",
  "vendor/pdf.min.js",
  "vendor/pdf.worker.min.js",
  "vendor/jspdf.umd.min.js",
  "icon-192.png",
  "icon-512.png"
];
self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS).catch(() => {})).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.map(k => k === CACHE ? null : caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const r = e.request;
  if (r.method !== "GET") return;                 // never touch Gemini POST etc.
  const u = new URL(r.url);
  if (u.origin !== location.origin) return;        // let CDN fonts / Gemini go to network
  e.respondWith(
    caches.match(r).then(c => c || fetch(r).then(resp => {
      const cp = resp.clone();
      caches.open(CACHE).then(cc => cc.put(r, cp));
      return resp;
    }).catch(() => caches.match("index.html")))
  );
});
