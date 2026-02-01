const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    selectFolder: () => ipcRenderer.invoke('select-folder'),
    openExternal: (path) => ipcRenderer.invoke('open-external', path),
    onMenuOpenFolder: (callback) => ipcRenderer.on('menu-open-folder', (event, path) => callback(path))
});

// Listen for Config from Main
ipcRenderer.on('config', (event, config) => {
    // Expose config to window global
    // Note: contextBridge is for exposing APIs. 
    // To set global variables readable by the app, we can do this via postMessage or just direct assignment if contextIsolation is false (secure: false).
    // But with contextIsolation: true, we need to expose it via contextBridge.
    // However, chatService reads window.CRICK_CONFIG.
    // We can expose it as a property of a "crickConfig" object or try to inject it.
});

// Since contextIsolation is standard, we must expose 'CRICK_CONFIG' via contextBridge
// But contextBridge exposes values at "window.KEY". 
// So:
const apiUrl = process.argv.find(arg => arg.startsWith('--api-url='))?.split('=')[1];

contextBridge.exposeInMainWorld('CRICK_CONFIG', {
    apiUrl: apiUrl || 'http://localhost:8000'
});
