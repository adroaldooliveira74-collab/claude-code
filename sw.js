/* Service worker — Perito · Laudo
   HTML/navegação: network-first (sempre pega a versão mais nova quando online).
   Bibliotecas/ícones: cache-first (rápido e offline). */
const CACHE = "perito-laudo-v2";
const ASSETS = [
  "./",
  "index.html",
  "assistencia.html",
  "painel.html",
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
  if (r.method !== "GET") return;
  const u = new URL(r.url);
  if (u.origin !== location.origin) return;          // Gemini/fontes vão à rede
  const isDoc = r.mode === "navigate"
    || (r.headers.get("accept") || "").includes("text/html")
    || /\.html$/.test(u.pathname)
    || u.pathname.endsWith("/");
  if (isDoc) {
    // network-first para páginas
    e.respondWith(
      fetch(r).then(resp => {
        const cp = resp.clone();
        caches.open(CACHE).then(c => c.put(r, cp));
        return resp;
      }).catch(() => caches.match(r).then(c => c || caches.match("index.html")))
    );
    return;
  }
  // cache-first para estáticos
  e.respondWith(
    caches.match(r).then(c => c || fetch(r).then(resp => {
      const cp = resp.clone();
      caches.open(CACHE).then(cc => cc.put(r, cp));
      return resp;
    }))
  );
});
