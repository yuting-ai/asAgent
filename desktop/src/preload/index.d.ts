interface DesktopAppInfo {
  appName: string
  version: string
}

interface DesktopBridge {
  getAppInfo(): Promise<DesktopAppInfo>
  getBackendStatus(): Promise<{ status: 'ready' | 'unavailable' }>
}

declare global {
  interface Window {
    desktop: DesktopBridge
  }
}

export {}
