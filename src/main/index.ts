import { app, shell, BrowserWindow, ipcMain, dialog } from 'electron'
import { join } from 'path'
import { spawn, ChildProcess } from 'child_process'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'

// Track the running Python process so we can cancel it
let ashlarProcess: ChildProcess | null = null

function createWindow(): void {
  const mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
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

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(() => {
  electronApp.setAppUserModelId('com.electron')

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
  ipcMain.on('run-ashlar', (event, tilePath: string) => {
    // Prevent concurrent runs
    if (ashlarProcess) return

    let runnerPath: string
    if (is.dev) {
      const pyCmd = process.platform === 'win32' ? 'python' : 'python3'
      runnerPath = pyCmd
    } else {
      const ext = process.platform === 'win32' ? '.exe' : ''
      runnerPath = join(process.resourcesPath, 'ashlar-runner', 'ashlar-runner' + ext)
    }

    const proc = is.dev
      ? spawn(runnerPath, ['-m', 'stitcher.runner', tilePath], { cwd: app.getAppPath() })
      : spawn(runnerPath, [tilePath])
    ashlarProcess = proc

    const safeSend = (channel: string, data: unknown): void => {
      if (!event.sender.isDestroyed()) {
        event.sender.send(channel, data)
      }
    }

    proc.stdout.on('data', (data) => {
      safeSend('ashlar-log', data.toString())
    })
    proc.stderr.on('data', (data) => {
      safeSend('ashlar-log', data.toString())
    })
    proc.on('close', (code) => {
      safeSend('ashlar-done', code)
      ashlarProcess = null
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
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

// Kill child process on quit
app.on('before-quit', () => {
  if (ashlarProcess) {
    ashlarProcess.kill()
    ashlarProcess = null
  }
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
