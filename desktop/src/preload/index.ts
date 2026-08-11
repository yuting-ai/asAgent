import { contextBridge, ipcRenderer } from 'electron'

const desktopBridge = {
  getAppInfo: (): Promise<{ appName: string; version: string }> =>
    ipcRenderer.invoke('desktop:get-app-info')
}

contextBridge.exposeInMainWorld('desktop', desktopBridge)
