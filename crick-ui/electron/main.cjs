const { app, BrowserWindow, ipcMain, dialog, Menu, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const net = require('net');

let mainWindow;
let serverProcess;
let apiPort = 8000; // Default

// --- Utils ---
function findFreePort() {
    return new Promise((resolve, reject) => {
        const server = net.createServer();
        server.unref();
        server.on('error', reject);
        server.listen(0, () => {
            const port = server.address().port;
            server.close(() => resolve(port));
        });
    });
}

function startBackend(port) {
    const isDev = !app.isPackaged;

    if (isDev) {
        // DEV: Run python script from root
        const projectRoot = path.resolve(__dirname, '..', '..');
        console.log("Starting Python Server from:", projectRoot);

        // Using shell: true helps locate 'python' in PATH
        serverProcess = spawn('python', ['server.py', '--port', port.toString()], {
            cwd: projectRoot,
            shell: true
        });
    } else {
        // PROD: Run executable
        const exePath = path.join(process.resourcesPath, 'server', 'server.exe');
        console.log("Starting Server Executable:", exePath);

        serverProcess = spawn(exePath, ['--port', port.toString()]);
    }

    // Attach logging
    if (serverProcess.stdout) {
        serverProcess.stdout.on('data', (data) => {
            console.log(`[PyServer]: ${data.toString().trim()}`);
        });
    }

    if (serverProcess.stderr) {
        serverProcess.stderr.on('data', (data) => {
            console.error(`[PyServer ERR]: ${data.toString().trim()}`);
        });
    }

    serverProcess.on('error', (err) => {
        console.error('Failed to start server process:', err);
    });

    serverProcess.on('close', (code) => {
        console.log(`Python Server exited with code ${code}`);
    });
}


function createMenu() {
    const template = [
        {
            label: 'File',
            submenu: [
                {
                    label: 'Open Folder...',
                    accelerator: 'CmdOrCtrl+O',
                    click: async () => {
                        if (!mainWindow) return;
                        const result = await dialog.showOpenDialog(mainWindow, {
                            properties: ['openDirectory']
                        });
                        if (!result.canceled && result.filePaths.length > 0) {
                            mainWindow.webContents.send('menu-open-folder', result.filePaths[0]);
                        }
                    }
                },
                { type: 'separator' },
                { role: 'quit' }
            ]
        }
    ];
    const menu = Menu.buildFromTemplate(template);
    Menu.setApplicationMenu(menu);
}

const createWindow = (port) => {
    createMenu();

    const isDev = !app.isPackaged;
    const iconPath = isDev
        ? path.join(__dirname, '../public/crick.png')
        : path.join(__dirname, '../dist/crick.png');

    mainWindow = new BrowserWindow({
        title: 'CrickCoder',
        icon: iconPath,
        width: 1280,
        height: 800,
        webPreferences: {
            preload: path.join(__dirname, 'preload.cjs'),
            contextIsolation: true,
            nodeIntegration: false,
            additionalArguments: [`--api-url=http://localhost:${port}`]
        }
    });

    // In dev, load localhost vite. In prod, load index.html
    if (isDev) {
        mainWindow.loadURL('http://localhost:5173');
        mainWindow.webContents.openDevTools();
    } else {
        mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
    }
};

app.whenReady().then(async () => {
    try {
        apiPort = await findFreePort();
        console.log(`Found free port for API: ${apiPort}`);

        startBackend(apiPort);

        // Give server a moment to start (TODO: Use proper health check loop)
        setTimeout(() => {
            createWindow(apiPort);
        }, 2000);

    } catch (e) {
        console.error("Startup error:", e);
    }

    // IPC Handler for Folder Selection
    ipcMain.handle('select-folder', async () => {
        const result = await dialog.showOpenDialog(mainWindow, {
            properties: ['openDirectory']
        });

        if (result.canceled || result.filePaths.length === 0) {
            return null;
        }

        return result.filePaths[0];
    });

    // IPC Handler to open path in Explorer
    ipcMain.handle('open-external', async (event, fullPath) => {
        if (fullPath) {
            await shell.openPath(fullPath);
        }
    });

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow(apiPort);
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});

app.on('will-quit', () => {
    if (serverProcess) {
        console.log("Stopping Backend...");
        try {
            if (process.platform === 'win32') {
                require('child_process').execSync(`taskkill /pid ${serverProcess.pid} /f /t`);
            } else {
                serverProcess.kill('SIGKILL');
            }
        } catch (e) {
            console.error("Failed to kill backend:", e.message);
        }
    }
});
