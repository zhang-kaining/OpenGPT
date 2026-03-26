const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronTheme', {
  saveMode: (mode) => ipcRenderer.send('save-theme-mode', mode),
})
