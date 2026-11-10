// Servidor de sincronização local (LAN/WiFi) — UrbanClin Perito·Laudo
// Roda dentro do executável de PC (Electron) e também standalone: `node server/sync.js`.
// Sem dependências externas: usa só módulos nativos do Node.
//
// Papel: o PC é o MESTRE. O admin libera um processo para um celular (fica
// bloqueado no PC). O celular baixa, trabalha offline em campo e devolve. Ao
// devolver, o PC recebe os dados, desbloqueia e o processo some do celular.
// Segurança: PIN de pareamento (o PC mostra; o celular digita uma vez).

const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const os = require("os");

function lanIps() {
  const out = [];
  try {
    const ni = os.networkInterfaces();
    Object.keys(ni).forEach(k => (ni[k] || []).forEach(a => {
      if (a.family === "IPv4" && !a.internal) out.push(a.address);
    }));
  } catch (e) {}
  return out;
}

function startSyncServer(opts) {
  opts = opts || {};
  const DATA = opts.dataDir || path.join(process.cwd(), "urbanclin-data");
  const WWW = opts.wwwDir || path.join(__dirname, "..");
  const PORT = opts.port || 8787;
  const REC = path.join(DATA, "rec");
  const IDX = path.join(DATA, "index.json");
  const PINF = path.join(DATA, "pin.txt");
  fs.mkdirSync(REC, { recursive: true });

  // ---- PIN ----
  let PIN = "";
  try { PIN = (fs.readFileSync(PINF, "utf8") || "").trim(); } catch (e) {}
  if (!PIN) { PIN = ("" + (1000 + Math.floor(Math.random() * 9000))); try { fs.writeFileSync(PINF, PIN); } catch (e) {} }

  const readIdx = () => { try { return JSON.parse(fs.readFileSync(IDX, "utf8")); } catch (e) { return { records: {} }; } };
  const writeIdx = (x) => fs.writeFileSync(IDX, JSON.stringify(x, null, 2));
  const recPath = (pid) => path.join(REC, String(pid).replace(/[^\w.-]/g, "_") + ".json");
  const now = () => Date.now();
  const meta = (st) => ({
    pid: st.painelId || "",
    numero: (st.processo && st.processo.numero) || "",
    parte: (st.partes && (st.partes.autor || st.partes.reu)) || "",
    modulo: st.tipoPericia ? "Perícia" : (st.__modulo || "Perícia")
  });

  function listRecords() { const idx = readIdx(); return Object.keys(idx.records).map(pid => idx.records[pid]); }
  function loadRec(pid) { try { return JSON.parse(fs.readFileSync(recPath(pid), "utf8")); } catch (e) { return null; } }
  function saveRec(pid, payload) { fs.writeFileSync(recPath(pid), JSON.stringify(payload)); }

  function seedRecord(payload) {
    if (!payload || !payload.state) throw new Error("sem state");
    const st = payload.state;
    if (!st.painelId) st.painelId = crypto.randomBytes(6).toString("hex");
    const pid = st.painelId;
    saveRec(pid, { state: st, media: payload.media || {} });
    const idx = readIdx(); const prev = idx.records[pid] || {};
    idx.records[pid] = Object.assign({ location: "pc", locked: false, device: null, downloaded: false }, prev, meta(st), { updated: now() });
    if (prev.location !== "device") { idx.records[pid].location = "pc"; idx.records[pid].locked = false; }
    writeIdx(idx); return idx.records[pid];
  }
  function releaseRecord(pid, device) {
    const idx = readIdx(); const r = idx.records[pid];
    if (!r) throw new Error("não encontrado");
    if (r.locked) throw new Error("já está em campo (bloqueado)");
    r.location = "device"; r.locked = true; r.device = device || "celular"; r.downloaded = false; r.updated = now();
    writeIdx(idx); return r;
  }
  function cancelRelease(pid) {
    const idx = readIdx(); const r = idx.records[pid];
    if (!r) throw new Error("não encontrado");
    r.location = "pc"; r.locked = false; r.device = null; r.downloaded = false; r.updated = now();
    writeIdx(idx); return r;
  }
  function outbox(device) { return listRecords().filter(r => r.location === "device" && (!device || r.device === device)); }
  function pull(pid) {
    const rec = loadRec(pid); if (!rec) return null;
    const idx = readIdx(); if (idx.records[pid] && idx.records[pid].location === "device") { idx.records[pid].downloaded = true; idx.records[pid].downloadedAt = now(); writeIdx(idx); }
    return rec;
  }
  function uploadMedia(pid, id, m, d) {
    const rec = loadRec(pid) || { state: {}, media: {} };
    rec.media = rec.media || {}; rec.media[id] = { t: "blob", m: m || "image/jpeg", d: d };
    saveRec(pid, rec); return { ok: true };
  }
  function checkin(pid, state, media) {
    if (!state) throw new Error("sem state");
    const prev = loadRec(pid) || {};
    const mediaFinal = media && Object.keys(media).length ? media : (prev.media || {});
    saveRec(pid, { state: state, media: mediaFinal });
    const idx = readIdx(); const pm = idx.records[pid] || {};
    idx.records[pid] = Object.assign({}, pm, meta(state), { location: "pc", locked: false, device: null, downloaded: false, updated: now() });
    writeIdx(idx); return idx.records[pid];
  }
  function deleteRecord(pid) { const idx = readIdx(); delete idx.records[pid]; writeIdx(idx); try { fs.unlinkSync(recPath(pid)); } catch (e) {} }

  // ---- http ----
  const send = (res, code, obj) => {
    res.writeHead(code, { "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "Content-Type, x-pin", "Access-Control-Allow-Methods": "GET,POST,OPTIONS" });
    res.end(JSON.stringify(obj));
  };
  const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".json": "application/json", ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml", ".ico": "image/x-icon" };
  function serveStatic(res, rel, transform) {
    const file = path.join(WWW, rel);
    if (!file.startsWith(WWW)) { res.writeHead(403); return res.end("forbidden"); }
    fs.readFile(file, (err, buf) => {
      if (err) { res.writeHead(404); return res.end("não encontrado"); }
      let body = buf;
      if (transform) { body = Buffer.from(transform(buf.toString("utf8")), "utf8"); }
      res.writeHead(200, { "Content-Type": MIME[path.extname(file)] || "application/octet-stream" });
      res.end(body);
    });
  }
  function body(req) {
    return new Promise((resolve) => {
      let b = ""; req.on("data", c => { b += c; if (b.length > 200e6) req.destroy(); });
      req.on("end", () => { try { resolve(JSON.parse(b || "{}")); } catch (e) { resolve({}); } });
    });
  }
  const authed = (req) => !PIN || (req.headers["x-pin"] || "") === PIN;

  const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, "http://x");
    const p = u.pathname;
    if (req.method === "OPTIONS") return send(res, 204, {});
    try {
      if (p === "/api/ping") return send(res, 200, { ok: true, app: "urbanclin-sync", v: 2, port: PORT, ips: lanIps(), pinRequired: !!PIN });
      // endpoints protegidos por PIN
      if (p.startsWith("/api/")) {
        if (!authed(req)) return send(res, 401, { error: "PIN inválido" });
        if (p === "/api/list") return send(res, 200, { records: listRecords() });
        if (p === "/api/outbox") return send(res, 200, { records: outbox(u.searchParams.get("device") || "") });
        if (p === "/api/pull") { const r = pull(u.searchParams.get("pid") || ""); return r ? send(res, 200, r) : send(res, 404, { error: "não encontrado" }); }
        if (p === "/api/datadir") return send(res, 200, { dir: DATA, pin: PIN });
        if (req.method === "POST") {
          const d = await body(req);
          if (p === "/api/seed") return send(res, 200, seedRecord(d));
          if (p === "/api/release") return send(res, 200, releaseRecord(d.pid, d.device));
          if (p === "/api/cancel") return send(res, 200, cancelRelease(d.pid));
          if (p === "/api/upload") return send(res, 200, uploadMedia(d.pid, d.id, d.m, d.d));
          if (p === "/api/checkin") { const pl = d.payload || d; return send(res, 200, checkin(d.pid, pl.state, pl.media)); }
          if (p === "/api/delete") { deleteRecord(d.pid); return send(res, 200, { ok: true }); }
        }
        return send(res, 404, { error: "rota não encontrada" });
      }
      // estáticos
      if (p === "/" || p === "") return serveStatic(res, "index.html", s => s.replace("%%PIN%%", PIN));
      if (p === "/admin" || p === "/admin.html") return serveStatic(res, "admin.html", s => s.replace("%%PIN%%", PIN));
      return serveStatic(res, p.replace(/^\//, ""));
    } catch (e) { return send(res, 400, { error: String(e && e.message || e) }); }
  });
  server.listen(PORT, "0.0.0.0", () => console.log("[sync] http://0.0.0.0:" + PORT + "  PIN=" + PIN + "  dados=" + DATA));
  server.__pin = PIN; server.__data = DATA;
  return server;
}

module.exports = { startSyncServer };

if (require.main === module) {
  startSyncServer({ dataDir: process.env.DATA_DIR || path.join(process.cwd(), "urbanclin-data"), port: +(process.env.PORT || 8787) });
}
