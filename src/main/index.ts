import { app, shell, BrowserWindow, ipcMain, dialog } from 'electron'
import { join } from 'path'
import { spawn, ChildProcess } from 'child_process'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'

// Track the running Python process so we can cancel it
let ashlarProcess: ChildProcess | null = null

function createWindow(): void {
  // Create the browser window.
  const mainWindow = new BrowserWindow({
    width: 500,
    height: 300,
    show: false,
    autoHideMenuBar: true,
    ...(process.platform === 'linux' ? { icon } : {}),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  // HMR for renderer base on electron-vite cli.
  // Load the remote URL for development or the local html file for production.
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
  // Set app user model id for windows
  electronApp.setAppUserModelId('com.electron')

  // Default open or close DevTools by F12 in development
  // and ignore CommandOrControl + R in production.
  // see https://github.com/alex8088/electron-toolkit/tree/master/packages/utils
  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // --- IPC: Open directory picker ---
  ipcMain.handle('select-dir', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openDirectory'],
      title: 'Select tile folder to stitch'
    })
    if (result.canceled || result.filePaths.length === 0) return null
    return result.filePaths[0]
  })

  // --- IPC: Run ashlar stitching ---
  // TODO: You implement this handler.
  //
  // It should:
  //   1. Determine the Python command: 'python' on Windows, 'python3' on macOS
  //   2. Spawn: python -m python.runner <tilePath>
  //      - Set cwd to the project root (app.getAppPath() in dev)
  //   3. Stream stdout/stderr lines back to the renderer via event.sender.send('ashlar-log', line)
  //   4. When the process exits, send 'ashlar-done' with the exit code
  //   5. Store the process in ashlarProcess so it can be cancelled
  //
  // Hints:
  //   - const pyCmd = process.platform === 'win32' ? 'python' : 'python3'
  //   - spawn(pyCmd, ['-m', 'python.runner', tilePath], { cwd: ... })
  //   - proc.stdout.on('data', (data) => { ... })
  //   - proc.on('close', (code) => { ... })
  ipcMain.on('run-ashlar', (_event, _tilePath: string) => {
    let runnerPath: string
    if (is.dev) {
      // Dev mode: call Python directly
      const pyCmd = process.platform === 'win32' ? 'python' : 'python3'
      runnerPath = pyCmd
    } else {
      // Production: use bundled executable
      const ext = process.platform === 'win32' ? '.exe' : ''
      runnerPath = join(process.resourcesPath, 'ashlar-runner', 'ashlar-runner' + ext)
    }

    const proc = is.dev
      ? spawn(runnerPath, ['-m', 'stitcher.runner', _tilePath], { cwd: app.getAppPath() })
      : spawn(runnerPath, [_tilePath])
    ashlarProcess = proc
    proc.stdout.on('data', (data) => {
      _event.sender.send('ashlar-log', data.toString())
    })
    proc.on('close', (code) => {
      _event.sender.send('ashlar-done', code)
      ashlarProcess = null
    })
    proc.stderr.on('data', (data) => {
      _event.sender.send('ashlar-log', data.toString())
    })
  })

  // --- IPC: Cancel running stitch ---
  ipcMain.on('cancel-ashlar', () => {
    if (ashlarProcess) {
      ashlarProcess.kill()
      ashlarProcess = null
    }
  })

  createWindow()

  app.on('activate', function () {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// In this file you can include the rest of your app's specific main process
// code. You can also put them in separate files and require them here.
