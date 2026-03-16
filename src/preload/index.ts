import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

const api = {
  selectDir: (): Promise<string | null> => ipcRenderer.invoke('select-dir'),
  runAshlar: (tilePath: string): void => ipcRenderer.send('run-ashlar', tilePath),
  cancelAshlar: (): void => ipcRenderer.send('cancel-ashlar'),
  onAshlarLog: (callback: (line: string) => void): void => {
    ipcRenderer.on('ashlar-log', (_event, line) => callback(line))
  },
  onAshlarDone: (callback: (code: number) => void): void => {
    ipcRenderer.on('ashlar-done', (_event, code) => callback(code))
  },
  removeAshlarListeners: (): void => {
    ipcRenderer.removeAllListeners('ashlar-log')
    ipcRenderer.removeAllListeners('ashlar-done')
  }
}

if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore (define in dts)
  window.electron = electronAPI
  // @ts-ignore (define in dts)
  window.api = api
}
