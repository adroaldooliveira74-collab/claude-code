// Servidor de sincronização local (LAN/WiFi) — UrbanClin Perito·Laudo
// Roda dentro do executável de PC (Electron) e também standalone: `node server/sync.js`.
// Sem dependências externas: usa só módulos nativos do Node.
//
// Papel: o PC é o MESTRE. O admin libera um processo para um celular (fica
// bloqueado no PC). O celular baixa, trabalha offline em campo e devolve. Ao
// devolver, o PC recebe os dados, desbloqueia e o processo some do celular.

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
  fs.mkdirSync(REC, { recursive: true });

  const readIdx = () => { try { return JSON.parse(fs.readFileSync(IDX, "utf8")); } catch (e) { return { records: {} }; } };
  const writeIdx = (x) => fs.writeFileSync(IDX, JSON.stringify(x, null, 2));
  const recPath = (pid) => path.join(REC, pid.replace(/[^\w.-]/g, "_") + ".json");
  const now = () => Date.now();
  const meta = (st) => ({
    pid: st.painelId || "",
    numero: (st.processo && st.processo.numero) || "",
    parte: (st.partes && (st.partes.autor || st.partes.reu)) || "",
    modulo: st.tipoPericia ? "Perícia" : (st.__modulo || "Perícia")
  });

  // ---- operações ----
  function listRecords() {
    const idx = readIdx();
    return Object.keys(idx.records).map(pid => idx.records[pid]);
  }
  function seedRecord(payload) { // payload = {state, media}
    if (!payload || !payload.state) throw new Error("sem state");
    const st = payload.state;
    if (!st.painelId) st.painelId = crypto.randomBytes(6).toString("hex");
    const pid = st.painelId;
    fs.writeFileSync(recPath(pid), JSON.stringify(payload));
    const idx = readIdx();
    const prev = idx.records[pid] || {};
    idx.records[pid] = Object.assign({ location: "pc", locked: false, device: null }, prev, meta(st), { updated: now(), location: (prev.location === "device" ? prev.location : "pc"), locked: !!prev.locked, device: prev.device || null });
    writeIdx(idx);
    return idx.records[pid];
  }
  function releaseRecord(pid, device) {
    const idx = readIdx();
    const r = idx.records[pid];
    if (!r) throw new Error("não encontrado");
    if (r.locked) throw new Error("já está em campo (bloqueado)");
    r.location = "device"; r.locked = true; r.device = device || "celular"; r.updated = now();
    writeIdx(idx); return r;
  }
  function cancelRelease(pid) {
    const idx = readIdx();
    const r = idx.records[pid];
    if (!r) throw new Error("não encontrado");
    r.location = "pc"; r.locked = false; r.device = null; r.updated = now();
    writeIdx(idx); return r;
  }
  function outbox(device) {
    return listRecords().filter(r => r.location === "device" && (!device || r.device === device));
  }
  function pull(pid) {
    try { return JSON.parse(fs.readFileSync(recPath(pid), "utf8")); } catch (e) { return null; }
  }
  function checkin(pid, payload) { // payload = {state, media}
    if (!payload || !payload.state) throw new Error("sem state");
    fs.writeFileSync(recPath(pid), JSON.stringify(payload));
    const idx = readIdx();
    const prev = idx.records[pid] || {};
    idx.records[pid] = Object.assign({}, prev, meta(payload.state), { location: "pc", locked: false, device: null, updated: now() });
    writeIdx(idx); return idx.records[pid];
  }
  function deleteRecord(pid) {
    const idx = readIdx(); delete idx.records[pid]; writeIdx(idx);
    try { fs.unlinkSync(recPath(pid)); } catch (e) {}
  }

  // ---- http ----
  const send = (res, code, obj) => {
    res.writeHead(code, { "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Allow-Methods": "GET,POST,OPTIONS" });
    res.end(JSON.stringify(obj));
  };
  const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".json": "application/json", ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml", ".ico": "image/x-icon" };
  function serveStatic(res, rel) {
    const file = path.join(WWW, rel);
    if (!file.startsWith(WWW)) { res.writeHead(403); return res.end("forbidden"); }
    fs.readFile(file, (err, buf) => {
      if (err) { res.writeHead(404); return res.end("não encontrado"); }
      res.writeHead(200, { "Content-Type": MIME[path.extname(file)] || "application/octet-stream" });
      res.end(buf);
    });
  }
  function body(req) {
    return new Promise((resolve) => {
      let b = ""; req.on("data", c => { b += c; if (b.length > 200e6) req.destroy(); });
      req.on("end", () => { try { resolve(JSON.parse(b || "{}")); } catch (e) { resolve({}); } });
    });
  }

  const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, "http://x");
    const p = u.pathname;
    if (req.method === "OPTIONS") { return send(res, 204, {}); }
    try {
      if (p === "/api/ping") return send(res, 200, { ok: true, app: "urbanclin-sync", v: 1, port: PORT, ips: lanIps() });
      if (p === "/api/list") return send(res, 200, { records: listRecords() });
      if (p === "/api/outbox") return send(res, 200, { records: outbox(u.searchParams.get("device") || "") });
      if (p === "/api/pull") { const r = pull(u.searchParams.get("pid") || ""); return r ? send(res, 200, r) : send(res, 404, { error: "não encontrado" }); }
      if (p === "/api/seed" && req.method === "POST") { const d = await body(req); return send(res, 200, seedRecord(d)); }
      if (p === "/api/release" && req.method === "POST") { const d = await body(req); return send(res, 200, releaseRecord(d.pid, d.device)); }
      if (p === "/api/cancel" && req.method === "POST") { const d = await body(req); return send(res, 200, cancelRelease(d.pid)); }
      if (p === "/api/checkin" && req.method === "POST") { const d = await body(req); return send(res, 200, checkin(d.pid, d.payload || d)); }
      if (p === "/api/delete" && req.method === "POST") { const d = await body(req); deleteRecord(d.pid); return send(res, 200, { ok: true }); }
      // estáticos
      if (p === "/" || p === "") return serveStatic(res, "index.html");
      if (p === "/admin" || p === "/admin.html") return serveStatic(res, "admin.html");
      return serveStatic(res, p.replace(/^\//, ""));
    } catch (e) {
      return send(res, 400, { error: String(e && e.message || e) });
    }
  });
  server.listen(PORT, "0.0.0.0", () => {
    console.log("[sync] servidor em http://0.0.0.0:" + PORT + "  (dados: " + DATA + ")");
  });
  return server;
}

module.exports = { startSyncServer };

// standalone
if (require.main === module) {
  startSyncServer({ dataDir: process.env.DATA_DIR || path.join(process.cwd(), "urbanclin-data"), port: +(process.env.PORT || 8787) });
}
