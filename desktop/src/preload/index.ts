import { contextBridge, ipcRenderer } from 'electron'

const desktopBridge = {
  getAppInfo: (): Promise<{ appName: string; version: string }> =>
    ipcRenderer.invoke('desktop:get-app-info'),
  getBackendStatus: (): Promise<{ status: 'ready' | 'unavailable' }> =>
    ipcRenderer.invoke('desktop:get-backend-status')
}

contextBridge.exposeInMainWorld('desktop', desktopBridge)
