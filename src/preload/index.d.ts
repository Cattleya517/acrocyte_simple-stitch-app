import { ElectronAPI } from '@electron-toolkit/preload'

interface StitchAPI {
  selectDir: () => Promise<string | null>
  runAshlar: (tilePath: string) => void
  cancelAshlar: () => void
  onAshlarLog: (callback: (line: string) => void) => void
  onAshlarDone: (callback: (code: number) => void) => void
  removeAshlarListeners: () => void
}

declare global {
  interface Window {
    electron: ElectronAPI
    api: StitchAPI
  }
}
