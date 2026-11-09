// Executável de desktop (PC) — abre o app e sobe o servidor de sincronização da rede.
const { app, BrowserWindow, session, shell } = require("electron");
const path = require("path");
const { startSyncServer } = require("../server/sync.js");

const PORT = 8787;
let server = null;

function start() {
  try {
    server = startSyncServer({
      dataDir: path.join(app.getPath("userData"), "urbanclin-data"),
      wwwDir: path.join(__dirname, ".."),
      port: PORT
    });
  } catch (e) { console.error("sync server:", e); }
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1200, height: 850,
    title: "UrbanClin · Perito · Laudo (PC)",
    backgroundColor: "#f6f8f1",
    webPreferences: { contextIsolation: true, nodeIntegration: false }
  });
  win.setMenuBarVisibility(false);
  // Carrega pelo servidor local (mesma origem do app e da API de sincronização).
  win.loadURL("http://localhost:" + PORT + "/admin");
  // links externos no navegador padrão
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: "deny" }; });
}

app.whenReady().then(() => {
  try { session.defaultSession.setPermissionRequestHandler((wc, permission, cb) => cb(true)); } catch (e) {}
  start();
  createWindow();
  app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
app.on("quit", () => { try { server && server.close(); } catch (e) {} });
