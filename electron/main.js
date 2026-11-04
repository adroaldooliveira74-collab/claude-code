// Electron wrapper — abre o app como executável de desktop (PC).
const { app, BrowserWindow, session } = require("electron");
const path = require("path");

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 850,
    title: "Perito · Laudo",
    backgroundColor: "#f6f8f1",
    webPreferences: { contextIsolation: true, nodeIntegration: false }
  });
  win.setMenuBarVisibility(false);
  win.loadFile(path.join(__dirname, "..", "index.html"));
}

app.whenReady().then(() => {
  // Concede geolocalização quando solicitada pela página (GPS no desktop, se houver).
  try {
    session.defaultSession.setPermissionRequestHandler((wc, permission, cb) => cb(true));
  } catch (e) {}
  createWindow();
  app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
