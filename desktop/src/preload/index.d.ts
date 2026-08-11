interface DesktopAppInfo {
  appName: string
  version: string
}

interface DesktopBridge {
  getAppInfo(): Promise<DesktopAppInfo>
}

declare global {
  interface Window {
    desktop: DesktopBridge
  }
}

export {}
