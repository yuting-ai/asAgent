import { app, BrowserWindow, dialog, ipcMain } from 'electron'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { electronApp, is, optimizer } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import { BackendLauncher } from './backend_launcher'

let backendLauncher: BackendLauncher | undefined
let isQuitting = false

function rendererUrl(): string {
  if (is.dev) {
    const developmentUrl = process.env['ELECTRON_RENDERER_URL']
    if (!developmentUrl) {
      throw new Error('Electron renderer development URL is missing.')
    }

    return developmentUrl
  }

  return pathToFileURL(join(__dirname, '../renderer/index.html')).href
}

function isTrustedRendererUrl(url: string): boolean {
  try {
    if (is.dev) {
      return new URL(url).origin === new URL(rendererUrl()).origin
    }

    return url === rendererUrl()
  } catch {
    return false
  }
}

function createWindow(): void {
  const mainWindow = new BrowserWindow({
    width: 1100,
    height: 760,
    minWidth: 820,
    minHeight: 600,
    show: false,
    title: 'asAgent',
    autoHideMenuBar: true,
    ...(process.platform === 'linux' ? { icon } : {}),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: join(__dirname, '../preload/index.js')
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))

  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!isTrustedRendererUrl(url)) {
      event.preventDefault()
    }
  })

  void mainWindow.loadURL(rendererUrl())
}

function assertTrustedRenderer(url: string): void {
  if (!isTrustedRendererUrl(url)) {
    throw new Error('Untrusted renderer IPC request.')
  }
}

function getReadyBackendLauncher(): BackendLauncher {
  if (backendLauncher === undefined || !backendLauncher.isReady) {
    throw new Error('Backend is unavailable.')
  }

  return backendLauncher
}

function createDevelopmentBackendLauncher(): BackendLauncher {
  const projectRoot = join(app.getAppPath(), '..')

  return new BackendLauncher({
    projectRoot,
    appHome: join(projectRoot, '.local-data')
  })
}

app.whenReady().then(async () => {
  electronApp.setAppUserModelId('com.asagent.desktop')

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  backendLauncher = createDevelopmentBackendLauncher()

  try {
    await backendLauncher.start()
  } catch (error) {
    dialog.showErrorBox(
      'asAgent backend unavailable',
      error instanceof Error ? error.message : 'Backend startup failed.'
    )
    await backendLauncher.stop()
    app.quit()
    return
  }

  ipcMain.handle('desktop:get-app-info', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }
    assertTrustedRenderer(frame.url)
    return { appName: 'asAgent', version: app.getVersion() }
  })

  ipcMain.handle('desktop:get-backend-status', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }
    assertTrustedRenderer(frame.url)
    return { status: backendLauncher?.isReady ? 'ready' : 'unavailable' }
  })

  ipcMain.handle('desktop:list-conversations', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().listConversations()
  })

  ipcMain.handle('desktop:list-conversation-messages', (event, conversationId: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)

    if (typeof conversationId !== 'string' || !conversationId.trim()) {
      throw new Error('Conversation ID is invalid.')
    }

    return getReadyBackendLauncher().listConversationMessages(conversationId)
  })

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('before-quit', (event) => {
  if (isQuitting) {
    return
  }

  event.preventDefault()
  isQuitting = true

  void (backendLauncher?.stop() ?? Promise.resolve()).finally(() => {
    app.quit()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
