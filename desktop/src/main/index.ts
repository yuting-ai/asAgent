import {
  app,
  BrowserWindow,
  clipboard,
  dialog,
  ipcMain,
  session,
  shell,
  WebContentsView,
  type WebContents
} from 'electron'
import { stat } from 'node:fs/promises'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { electronApp, is, optimizer } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import {
  BackendLauncher,
  isToolApprovalDecision,
  type StorageSettingsInput,
  type SubmittedMessage,
  type ToolApproval
} from './backend_launcher'
import { BrowserPageBridge } from './browser_page_bridge'
import { BROWSER_SESSION_FILE_NAME, BrowserSessionStore } from './browser_session'
import {
  parseBrowserControlAction,
  parseBrowserTabId,
  parseBrowserViewBounds,
  VisibleBrowser,
  type BrowserHostWindow,
  type BrowserTabState
} from './browser_view'
import { listWorkspaceTree, readFilePreview } from './workspace_tree'
import { parseExternalWebUrl } from './external_url'

let backendLauncher: BackendLauncher | undefined
let visibleBrowser: VisibleBrowser | undefined
let browserPageBridge: BrowserPageBridge | undefined
let browserSessionStore: BrowserSessionStore | undefined
let isQuitting = false
const runWatchers = new Map<string, () => void>()
let dataProcessingMode: 'local' | 'external' = 'local'

if (!app.isPackaged) {
  app.setPath('userData', join(app.getAppPath(), '..', '.local-data', 'electron-user-data'))
}

function desktopAppHome(): string {
  if (app.isPackaged) {
    return app.getPath('userData')
  }
  return join(app.getAppPath(), '..', '.local-data')
}

function scheduleBrowserSessionSave(): void {
  if (browserSessionStore === undefined || visibleBrowser === undefined) {
    return
  }

  browserSessionStore.scheduleSave(visibleBrowser)
}

function noteBrowserTabState(state: BrowserTabState): void {
  broadcastBrowserTabState(state)
  scheduleBrowserSessionSave()
}

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
    width: 1280,
    height: 840,
    minWidth: 820,
    minHeight: 600,
    show: false,
    title: 'asAgent',
    autoHideMenuBar: true,
    ...(process.platform === 'darwin'
      ? {
          titleBarStyle: 'hidden' as const,
          trafficLightPosition: { x: 6, y: 12 }
        }
      : {}),
    icon,
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

  mainWindow.on('closed', () => {
    visibleBrowser?.hide()
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

function parseOptionalTavilyApiKey(value: unknown): string | undefined {
  if (value === undefined) {
    return undefined
  }

  if (typeof value !== 'string') {
    throw new Error('Tavily API key is invalid.')
  }

  const trimmed = value.trim()
  if (!trimmed) {
    throw new Error('Tavily API key is invalid.')
  }

  return trimmed
}

function parseModelSettingsInput(value: unknown): {
  location: 'local' | 'external'
  model: string
  baseUrl: string
  apiKey?: string
} {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error('Model settings are invalid.')
  }

  const input = value as Record<string, unknown>
  const location = input['location']
  const model = input['model']
  const baseUrl = input['baseUrl']
  const apiKey = input['apiKey']

  if (
    (location !== 'local' && location !== 'external') ||
    typeof model !== 'string' ||
    !model.trim() ||
    typeof baseUrl !== 'string' ||
    !baseUrl.trim()
  ) {
    throw new Error('Model settings are invalid.')
  }
  if (apiKey !== undefined && (typeof apiKey !== 'string' || !apiKey.trim())) {
    throw new Error('Model settings are invalid.')
  }

  return {
    location,
    model: model.trim(),
    baseUrl: baseUrl.trim(),
    ...(apiKey === undefined ? {} : { apiKey: apiKey.trim() })
  }
}

function parseAgentSettingsInput(value: unknown): { maxSteps: number } {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error('Agent settings are invalid.')
  }

  const input = value as Record<string, unknown>
  if (Object.keys(input).length !== 1 || !('maxSteps' in input)) {
    throw new Error('Agent settings are invalid.')
  }

  const maxSteps = input['maxSteps']
  if (
    typeof maxSteps !== 'number' ||
    !Number.isInteger(maxSteps) ||
    maxSteps < 1 ||
    maxSteps > 50
  ) {
    throw new Error('Agent settings are invalid.')
  }

  return { maxSteps }
}

function parseStorageSettingsInput(value: unknown): StorageSettingsInput {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error('Storage settings are invalid.')
  }

  const input = value as Record<string, unknown>
  if (Object.keys(input).length !== 1 || !('snapshot_retention_days' in input)) {
    throw new Error('Storage settings are invalid.')
  }

  const retentionDays = input['snapshot_retention_days']
  if (
    typeof retentionDays !== 'number' ||
    !Number.isInteger(retentionDays) ||
    ![0, 1, 3, 7, 30].includes(retentionDays)
  ) {
    throw new Error('Storage settings are invalid.')
  }

  return { snapshot_retention_days: retentionDays }
}

function parseWorkspaceSettings(value: unknown): {
  additionalFiles: string[]
  additionalRoots: string[]
} {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error('Workspace paths are invalid.')
  }

  const input = value as Record<string, unknown>
  if (
    Object.keys(input).length !== 2 ||
    !('additionalFiles' in input) ||
    !('additionalRoots' in input)
  ) {
    throw new Error('Workspace paths are invalid.')
  }

  const additionalFiles = input['additionalFiles']
  const additionalRoots = input['additionalRoots']
  if (
    !Array.isArray(additionalFiles) ||
    !Array.isArray(additionalRoots) ||
    additionalFiles.length + additionalRoots.length > 16 ||
    [...additionalFiles, ...additionalRoots].some(
      (path) => typeof path !== 'string' || !path.trim()
    )
  ) {
    throw new Error('Workspace paths are invalid.')
  }

  return {
    additionalFiles: additionalFiles.map((path) => (path as string).trim()),
    additionalRoots: additionalRoots.map((path) => (path as string).trim())
  }
}

function createBackendLauncher(browserBridge?: {
  baseUrl: string
  token: string
}): BackendLauncher {
  const appHome = desktopAppHome()
  const onDiagnosticOutput = app.isPackaged
    ? undefined
    : (stream: 'stdout' | 'stderr', output: string): void => {
        const destination = stream === 'stderr' ? process.stderr : process.stdout
        destination.write(`[asAgent backend ${stream}] ${output}`)
      }

  if (app.isPackaged) {
    const backendExecutable = join(
      process.resourcesPath,
      'backend',
      'asagent-backend',
      'asagent-backend'
    )
    return new BackendLauncher({
      backendExecutable,
      projectRoot: process.resourcesPath,
      appHome,
      browserBridge,
      onDiagnosticOutput
    })
  }

  const projectRoot = join(app.getAppPath(), '..')
  const providerProfile = process.env['ASAGENT_DESKTOP_PROFILE']
  const secretEnvironmentName = process.env['ASAGENT_DESKTOP_SECRET_ENV']

  if (providerProfile === undefined && secretEnvironmentName === undefined) {
    dataProcessingMode = 'local'
    return new BackendLauncher({
      projectRoot,
      appHome,
      browserBridge,
      onDiagnosticOutput
    })
  }

  if (providerProfile === undefined || secretEnvironmentName === undefined) {
    throw new Error('Desktop real Provider configuration is incomplete.')
  }

  dataProcessingMode = 'external'
  return new BackendLauncher({
    projectRoot,
    appHome,
    providerProfile,
    secretEnvironmentName,
    environmentFile: join(projectRoot, '.env'),
    browserBridge,
    onDiagnosticOutput
  })
}

async function refreshDataProcessingMode(): Promise<void> {
  if (process.env['ASAGENT_DESKTOP_PROFILE'] !== undefined) {
    dataProcessingMode = 'external'
    return
  }

  const modelSettings = await getReadyBackendLauncher().getModelSettings()
  dataProcessingMode = modelSettings.location === 'external' ? 'external' : 'local'
}

function isTerminalRunEvent(eventType: string): boolean {
  return ['run.completed', 'run.failed', 'run.cancelled', 'run.limit_reached'].includes(eventType)
}

function stopRunWatcher(runId: string): void {
  const stop = runWatchers.get(runId)
  runWatchers.delete(runId)
  stop?.()
}

async function restartSettingsRuntime(sender: WebContents): Promise<void> {
  if (!is.dev) {
    app.relaunch()
    app.quit()
    return
  }

  for (const runId of runWatchers.keys()) {
    stopRunWatcher(runId)
  }

  const launcher = getReadyBackendLauncher()
  await launcher.stop()
  await launcher.start()
  await refreshDataProcessingMode()

  setTimeout(() => {
    if (!sender.isDestroyed()) {
      sender.reload()
    }
  }, 0)
}

function watchRun(sender: WebContents, conversationId: string, submitted: SubmittedMessage): void {
  stopRunWatcher(submitted.run.run_id)

  const stop = getReadyBackendLauncher().watchRunEvents(
    submitted.run.run_id,
    (runEvent) => {
      if (sender.isDestroyed()) {
        stopRunWatcher(submitted.run.run_id)
        return
      }

      sender.send('desktop:run-event', {
        runId: submitted.run.run_id,
        conversationId,
        event: runEvent
      })

      if (runEvent.event_type === 'tool.approval_requested') {
        const approvalId = runEvent.data['approval_id']
        if (typeof approvalId === 'string') {
          void getReadyBackendLauncher()
            .getToolApproval(approvalId)
            .then((approval: ToolApproval) => {
              if (!sender.isDestroyed()) {
                sender.send('desktop:tool-approval-requested', approval)
              }
            })
            .catch((error) => {
              if (!sender.isDestroyed()) {
                sender.send('desktop:tool-approval-error', {
                  runId: submitted.run.run_id,
                  conversationId,
                  message:
                    error instanceof Error ? error.message : 'Tool approval could not be loaded.'
                })
              }
            })
        }
      }

      if (isTerminalRunEvent(runEvent.event_type)) {
        stopRunWatcher(submitted.run.run_id)
      }
    },
    (error) => {
      if (!sender.isDestroyed()) {
        sender.send('desktop:run-stream-error', {
          runId: submitted.run.run_id,
          conversationId,
          message: error.message
        })
      }

      stopRunWatcher(submitted.run.run_id)
    }
  )

  runWatchers.set(submitted.run.run_id, stop)
}

function broadcastBrowserTabState(state: BrowserTabState): void {
  for (const window of BrowserWindow.getAllWindows()) {
    if (!window.isDestroyed()) {
      window.webContents.send('desktop:browser-tab-state', state)
    }
  }
}

app.whenReady().then(async () => {
  electronApp.setAppUserModelId('com.asagent.desktop')

  if (process.platform === 'darwin' && app.dock) {
    try {
      app.dock.setIcon(icon)
    } catch {
      // Ignore if dock icon cannot be set
    }
  }

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  visibleBrowser = new VisibleBrowser({
    session: session.fromPath(join(app.getPath('userData'), 'browser-profile')),
    createView: (options) => new WebContentsView(options),
    onTabState: noteBrowserTabState
  })

  browserSessionStore = new BrowserSessionStore(join(desktopAppHome(), BROWSER_SESSION_FILE_NAME))
  try {
    await browserSessionStore.restore(visibleBrowser)
  } catch {
    await browserSessionStore.ensureReady(visibleBrowser)
  }

  browserPageBridge = new BrowserPageBridge({
    readCurrentPage: (tabId) => {
      if (visibleBrowser === undefined) {
        throw new Error('current browser tab is not visible')
      }
      return visibleBrowser.readCurrentPage(tabId)
    },
    inspectInteractive: (tabId) => {
      if (visibleBrowser === undefined) {
        throw new Error('current browser tab is not visible')
      }
      return visibleBrowser.inspectInteractive(tabId)
    },
    navigateCurrentPage: (tabId, url) => {
      if (visibleBrowser === undefined) {
        throw new Error('current browser tab is not visible')
      }
      return visibleBrowser.navigateCurrentPage(tabId, url)
    },
    clickCurrentPage: (tabId, targetId) => {
      if (visibleBrowser === undefined) {
        throw new Error('current browser tab is not visible')
      }
      return visibleBrowser.clickCurrentPage(tabId, targetId)
    },
    fillCurrentPage: (tabId, targetId, value) => {
      if (visibleBrowser === undefined) {
        throw new Error('current browser tab is not visible')
      }
      return visibleBrowser.fillCurrentPage(tabId, targetId, value)
    },
    selectCurrentPage: (tabId, targetId, value) => {
      if (visibleBrowser === undefined) {
        throw new Error('current browser tab is not visible')
      }
      return visibleBrowser.selectCurrentPage(tabId, targetId, value)
    },
    submitCurrentPage: (tabId, targetId) => {
      if (visibleBrowser === undefined) {
        throw new Error('current browser tab is not visible')
      }
      return visibleBrowser.submitCurrentPage(tabId, targetId)
    },
    waitForCurrentPage: (tabId, seconds) => {
      if (visibleBrowser === undefined) {
        throw new Error('current browser tab is not visible')
      }
      return visibleBrowser.waitForCurrentPage(tabId, seconds)
    }
  })

  let bridgeInfo
  try {
    bridgeInfo = await browserPageBridge.start()
  } catch (error) {
    dialog.showErrorBox(
      'asAgent browser bridge unavailable',
      error instanceof Error ? error.message : 'Browser page bridge startup failed.'
    )
    await browserPageBridge.stop()
    app.quit()
    return
  }

  backendLauncher = createBackendLauncher(bridgeInfo)

  try {
    await backendLauncher.start()
    await refreshDataProcessingMode()
  } catch (error) {
    dialog.showErrorBox(
      'asAgent backend unavailable',
      error instanceof Error ? error.message : 'Backend startup failed.'
    )
    await backendLauncher.stop()
    await browserPageBridge.stop()
    app.quit()
    return
  }

  ipcMain.handle('desktop:get-app-info', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }
    assertTrustedRenderer(frame.url)
    return {
      appName: 'asAgent',
      version: app.getVersion(),
      dataProcessingMode
    }
  })

  ipcMain.handle('desktop:show-browser', (event, tabId: unknown, bounds: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    const senderWindow = BrowserWindow.fromWebContents(event.sender)
    if (senderWindow === null || visibleBrowser === undefined) {
      throw new Error('Browser window is unavailable.')
    }

    visibleBrowser.show(
      senderWindow as unknown as BrowserHostWindow,
      parseBrowserViewBounds(bounds),
      parseBrowserTabId(tabId)
    )
    browserSessionStore?.noteVisibleTab(parseBrowserTabId(tabId))
    scheduleBrowserSessionSave()
  })

  ipcMain.handle('desktop:hide-browser', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    visibleBrowser?.hide()
  })

  ipcMain.handle('desktop:navigate-browser', (event, tabId: unknown, url: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    if (visibleBrowser === undefined) {
      throw new Error('Browser window is unavailable.')
    }

    return visibleBrowser
      .navigate(parseBrowserTabId(tabId), typeof url === 'string' ? url : '')
      .then((displayUrl) => {
        scheduleBrowserSessionSave()
        return displayUrl
      })
  })

  ipcMain.handle('desktop:close-browser-tab', (event, tabId: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    const parsedTabId = parseBrowserTabId(tabId)
    visibleBrowser?.closeTab(parsedTabId)
    browserSessionStore?.forgetTab(parsedTabId)
    scheduleBrowserSessionSave()
  })

  ipcMain.handle('desktop:control-browser', (event, tabId: unknown, action: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    if (visibleBrowser === undefined) {
      throw new Error('Browser window is unavailable.')
    }

    return visibleBrowser
      .control(parseBrowserTabId(tabId), parseBrowserControlAction(action))
      .then(() => {
        scheduleBrowserSessionSave()
      })
  })

  ipcMain.handle('desktop:get-browser-session', async (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    if (visibleBrowser === undefined || browserSessionStore === undefined) {
      throw new Error('Browser session is unavailable.')
    }

    return browserSessionStore.ensureReady(visibleBrowser)
  })

  ipcMain.handle(
    'desktop:set-browser-tab-conversation',
    (event, tabId: unknown, conversationId: unknown) => {
      const frame = event.senderFrame
      if (frame === null) {
        throw new Error('Untrusted renderer IPC request.')
      }

      assertTrustedRenderer(frame.url)
      if (browserSessionStore === undefined || visibleBrowser === undefined) {
        throw new Error('Browser session is unavailable.')
      }

      const parsedTabId = parseBrowserTabId(tabId)
      if (conversationId !== null && typeof conversationId !== 'string') {
        throw new Error('Conversation ID is invalid.')
      }

      browserSessionStore.setConversation(parsedTabId, conversationId)
      scheduleBrowserSessionSave()
    }
  )
  ipcMain.handle('desktop:open-external-link', (event, url: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return shell.openExternal(parseExternalWebUrl(url))
  })

  ipcMain.handle('desktop:copy-text', (event, content: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    if (typeof content !== 'string') {
      throw new Error('Copy content is invalid.')
    }

    clipboard.writeText(content)
  })

  ipcMain.handle('desktop:get-backend-status', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }
    assertTrustedRenderer(frame.url)
    return { status: backendLauncher?.isReady ? 'ready' : 'unavailable' }
  })

  ipcMain.handle('desktop:restart-app', async (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    await restartSettingsRuntime(event.sender)
  })

  ipcMain.handle('desktop:list-conversations', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().listConversations()
  })

  ipcMain.handle('desktop:list-automations', (event) => {
    const frame = event.senderFrame
    if (frame === null) throw new Error('Untrusted renderer IPC request.')
    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().listAutomations()
  })

  ipcMain.handle('desktop:create-automation', (event, input: unknown) => {
    const frame = event.senderFrame
    if (frame === null) throw new Error('Untrusted renderer IPC request.')
    assertTrustedRenderer(frame.url)
    if (typeof input !== 'object' || input === null || Array.isArray(input))
      throw new Error('Automation input is invalid.')
    return getReadyBackendLauncher().createAutomation(
      input as import('./backend_launcher').CreateAutomationInput
    )
  })

  ipcMain.handle('desktop:update-automation', (event, automationId: unknown, input: unknown) => {
    const frame = event.senderFrame
    if (frame === null) throw new Error('Untrusted renderer IPC request.')
    assertTrustedRenderer(frame.url)
    if (typeof automationId !== 'string' || !automationId.trim())
      throw new Error('Automation ID is invalid.')
    if (typeof input !== 'object' || input === null || Array.isArray(input))
      throw new Error('Automation input is invalid.')
    return getReadyBackendLauncher().updateAutomation(
      automationId,
      input as import('./backend_launcher').UpdateAutomationInput
    )
  })

  ipcMain.handle('desktop:delete-automation', (event, automationId: unknown) => {
    const frame = event.senderFrame
    if (frame === null) throw new Error('Untrusted renderer IPC request.')
    assertTrustedRenderer(frame.url)
    if (typeof automationId !== 'string' || !automationId.trim())
      throw new Error('Automation ID is invalid.')
    return getReadyBackendLauncher().deleteAutomation(automationId)
  })

  ipcMain.handle(
    'desktop:update-automation-status',
    (event, automationId: unknown, status: unknown) => {
      const frame = event.senderFrame
      if (frame === null) throw new Error('Untrusted renderer IPC request.')
      assertTrustedRenderer(frame.url)
      if (typeof automationId !== 'string' || !automationId.trim())
        throw new Error('Automation ID is invalid.')
      if (status !== 'draft' && status !== 'active' && status !== 'paused')
        throw new Error('Automation status is invalid.')
      return getReadyBackendLauncher().updateAutomationStatus(automationId, status)
    }
  )

  ipcMain.handle('desktop:list-automation-triggers', (event, automationId: unknown) => {
    const frame = event.senderFrame
    if (frame === null) throw new Error('Untrusted renderer IPC request.')
    assertTrustedRenderer(frame.url)
    if (typeof automationId !== 'string' || !automationId.trim())
      throw new Error('Automation ID is invalid.')
    return getReadyBackendLauncher().listAutomationTriggers(automationId)
  })

  ipcMain.handle('desktop:list-automation-executions', (event, automationId: unknown) => {
    const frame = event.senderFrame
    if (frame === null) throw new Error('Untrusted renderer IPC request.')
    assertTrustedRenderer(frame.url)
    if (typeof automationId !== 'string' || !automationId.trim())
      throw new Error('Automation ID is invalid.')
    return getReadyBackendLauncher().listAutomationExecutions(automationId)
  })

  ipcMain.handle(
    'desktop:get-automation-execution-messages',
    (event, automationId: unknown, executionId: unknown) => {
      const frame = event.senderFrame
      if (frame === null) throw new Error('Untrusted renderer IPC request.')
      assertTrustedRenderer(frame.url)
      if (typeof automationId !== 'string' || !automationId.trim())
        throw new Error('Automation ID is invalid.')
      if (typeof executionId !== 'string' || !executionId.trim())
        throw new Error('Execution ID is invalid.')
      return getReadyBackendLauncher().getAutomationExecutionMessages(automationId, executionId)
    }
  )

  ipcMain.handle('desktop:run-automation-now', (event, automationId: unknown) => {
    const frame = event.senderFrame
    if (frame === null) throw new Error('Untrusted renderer IPC request.')
    assertTrustedRenderer(frame.url)
    if (typeof automationId !== 'string' || !automationId.trim())
      throw new Error('Automation ID is invalid.')
    return getReadyBackendLauncher().runAutomationNow(automationId)
  })

  ipcMain.handle(
    'desktop:create-automation-draft',
    (event, automationId: unknown, timezone: unknown) => {
      const frame = event.senderFrame
      if (frame === null) throw new Error('Untrusted renderer IPC request.')
      assertTrustedRenderer(frame.url)
      if (automationId !== undefined && (typeof automationId !== 'string' || !automationId.trim()))
        throw new Error('Automation ID is invalid.')
      if (typeof timezone !== 'string' || !timezone.trim()) throw new Error('Timezone is invalid.')
      return getReadyBackendLauncher().createAutomationDraft(
        typeof automationId === 'string' ? automationId : undefined,
        timezone
      )
    }
  )

  ipcMain.handle('desktop:list-automation-draft-messages', (event, conversationId: unknown) => {
    const frame = event.senderFrame
    if (frame === null) throw new Error('Untrusted renderer IPC request.')
    assertTrustedRenderer(frame.url)
    if (typeof conversationId !== 'string' || !conversationId.trim())
      throw new Error('Conversation ID is invalid.')
    return getReadyBackendLauncher().listAutomationDraftMessages(conversationId)
  })

  ipcMain.handle(
    'desktop:submit-automation-draft-message',
    (event, conversationId: unknown, content: unknown, tabId: unknown) => {
      const frame = event.senderFrame
      if (frame === null) throw new Error('Untrusted renderer IPC request.')
      assertTrustedRenderer(frame.url)
      if (typeof conversationId !== 'string' || !conversationId.trim())
        throw new Error('Conversation ID is invalid.')
      if (typeof content !== 'string' || !content.trim())
        throw new Error('Message content is invalid.')
      if (tabId !== undefined && (typeof tabId !== 'string' || !tabId.trim()))
        throw new Error('Browser tab ID is invalid.')
      return getReadyBackendLauncher()
        .submitAutomationDraftMessage(
          conversationId,
          content,
          typeof tabId === 'string' ? tabId : undefined
        )
        .then((submitted) => {
          watchRun(event.sender, conversationId, submitted)
          return submitted
        })
    }
  )

  ipcMain.handle('desktop:delete-automation-draft', (event, conversationId: unknown) => {
    const frame = event.senderFrame
    if (frame === null) throw new Error('Untrusted renderer IPC request.')
    assertTrustedRenderer(frame.url)
    if (typeof conversationId !== 'string' || !conversationId.trim())
      throw new Error('Conversation ID is invalid.')
    return getReadyBackendLauncher().deleteAutomationDraft(conversationId)
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

  ipcMain.handle('desktop:list-conversation-run-history', (event, conversationId: unknown) => {
    const frame = event.senderFrame
    if (frame === null) throw new Error('Untrusted renderer IPC request.')
    assertTrustedRenderer(frame.url)
    if (typeof conversationId !== 'string' || !conversationId.trim()) {
      throw new Error('Conversation ID is invalid.')
    }
    return getReadyBackendLauncher().listConversationRunHistory(conversationId)
  })

  ipcMain.handle('desktop:list-conversation-file-changes', (event, conversationId: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }
    assertTrustedRenderer(frame.url)
    if (typeof conversationId !== 'string' || !conversationId.trim()) {
      throw new Error('Conversation ID is invalid.')
    }
    return getReadyBackendLauncher().listConversationFileChanges(conversationId.trim())
  })

  ipcMain.handle('desktop:undo-file-change', (event, changeId: unknown, path: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }
    assertTrustedRenderer(frame.url)
    if (typeof changeId !== 'string' || !changeId.trim()) {
      throw new Error('File change ID is invalid.')
    }
    if (typeof path !== 'string' || !path.trim()) {
      throw new Error('File change path is invalid.')
    }
    return getReadyBackendLauncher().undoFileChange(changeId.trim(), path)
  })

  ipcMain.handle('desktop:create-conversation', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().createConversation()
  })

  ipcMain.handle(
    'desktop:update-conversation-title',
    (event, conversationId: unknown, title: unknown) => {
      const frame = event.senderFrame
      if (frame === null) {
        throw new Error('Untrusted renderer IPC request.')
      }

      assertTrustedRenderer(frame.url)

      if (typeof conversationId !== 'string' || !conversationId.trim()) {
        throw new Error('Conversation ID is invalid.')
      }

      if (typeof title !== 'string' || !title.trim()) {
        throw new Error('Conversation title is invalid.')
      }

      return getReadyBackendLauncher().updateConversationTitle(conversationId.trim(), title)
    }
  )

  ipcMain.handle('desktop:delete-conversation', (event, conversationId: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)

    if (typeof conversationId !== 'string' || !conversationId.trim()) {
      throw new Error('Conversation ID is invalid.')
    }

    return getReadyBackendLauncher().deleteConversation(conversationId.trim())
  })

  ipcMain.handle('desktop:delete-browser-conversation', (event, conversationId: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)

    if (typeof conversationId !== 'string' || !conversationId.trim()) {
      throw new Error('Conversation ID is invalid.')
    }

    return getReadyBackendLauncher().deleteBrowserConversation(conversationId.trim())
  })

  ipcMain.handle('desktop:submit-message', (event, conversationId: unknown, content: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)

    if (typeof conversationId !== 'string' || !conversationId.trim()) {
      throw new Error('Conversation ID is invalid.')
    }

    if (typeof content !== 'string' || !content.trim()) {
      throw new Error('Message content is invalid.')
    }

    return getReadyBackendLauncher()
      .submitMessage(conversationId, content)
      .then((submitted) => {
        watchRun(event.sender, conversationId, submitted)
        return submitted
      })
  })

  ipcMain.handle('desktop:list-browser-conversations', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().listBrowserConversations()
  })

  ipcMain.handle('desktop:create-browser-conversation', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().createBrowserConversation()
  })

  ipcMain.handle('desktop:list-browser-conversation-messages', (event, conversationId: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)

    if (typeof conversationId !== 'string' || !conversationId.trim()) {
      throw new Error('Conversation ID is invalid.')
    }

    return getReadyBackendLauncher().listBrowserConversationMessages(conversationId)
  })

  ipcMain.handle(
    'desktop:list-browser-conversation-run-history',
    (event, conversationId: unknown) => {
      const frame = event.senderFrame
      if (frame === null) throw new Error('Untrusted renderer IPC request.')
      assertTrustedRenderer(frame.url)
      if (typeof conversationId !== 'string' || !conversationId.trim()) {
        throw new Error('Conversation ID is invalid.')
      }
      return getReadyBackendLauncher().listBrowserConversationRunHistory(conversationId)
    }
  )

  ipcMain.handle(
    'desktop:submit-browser-message',
    (event, conversationId: unknown, content: unknown, tabId: unknown) => {
      const frame = event.senderFrame
      if (frame === null) {
        throw new Error('Untrusted renderer IPC request.')
      }

      assertTrustedRenderer(frame.url)

      if (typeof conversationId !== 'string' || !conversationId.trim()) {
        throw new Error('Conversation ID is invalid.')
      }

      if (typeof content !== 'string' || !content.trim()) {
        throw new Error('Message content is invalid.')
      }

      const parsedTabId = parseBrowserTabId(tabId)
      if (visibleBrowser === undefined || !visibleBrowser.isVisibleTab(parsedTabId)) {
        throw new Error('Browser page is not visible.')
      }

      const page = visibleBrowser.getTabState(parsedTabId)
      const pageUrl = page.url.trim()
      const lastPageUrl = pageUrl !== '' && pageUrl.length <= 2048 ? pageUrl : null
      const lastPageTitle = lastPageUrl === null ? null : page.title.trim() || null

      return getReadyBackendLauncher()
        .submitBrowserMessage(conversationId, content, parsedTabId, lastPageUrl, lastPageTitle)
        .then((submitted) => {
          watchRun(event.sender, conversationId, submitted)
          return submitted
        })
    }
  )

  ipcMain.handle('desktop:cancel-run', async (event, runId: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)

    if (typeof runId !== 'string' || !runId.trim()) {
      throw new Error('Run ID is invalid.')
    }

    await getReadyBackendLauncher().cancelRun(runId)
  })

  ipcMain.handle(
    'desktop:decide-tool-approval',
    async (event, approvalId: unknown, decision: unknown) => {
      const frame = event.senderFrame
      if (frame === null) {
        throw new Error('Untrusted renderer IPC request.')
      }

      assertTrustedRenderer(frame.url)

      if (typeof approvalId !== 'string' || !approvalId.trim()) {
        throw new Error('Tool approval ID is invalid.')
      }
      if (!isToolApprovalDecision(decision)) {
        throw new Error('Tool approval decision is invalid.')
      }

      await getReadyBackendLauncher().decideToolApproval(approvalId, decision)
    }
  )

  ipcMain.handle('desktop:get-tavily-settings', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().getTavilySettings()
  })

  ipcMain.handle('desktop:enable-tavily', (event, apiKey: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().enableTavily(parseOptionalTavilyApiKey(apiKey))
  })

  ipcMain.handle('desktop:disable-tavily', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().disableTavily()
  })

  ipcMain.handle('desktop:delete-tavily', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().deleteTavily()
  })

  ipcMain.handle('desktop:get-model-settings', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().getModelSettings()
  })

  ipcMain.handle('desktop:save-model-settings', (event, input: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().saveModelSettings(parseModelSettingsInput(input))
  })

  ipcMain.handle('desktop:delete-model-settings', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().deleteModelSettings()
  })

  ipcMain.handle('desktop:get-agent-settings', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().getAgentSettings()
  })

  ipcMain.handle('desktop:save-agent-settings', (event, input: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().saveAgentSettings(parseAgentSettingsInput(input))
  })

  ipcMain.handle('desktop:get-storage-settings', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().getStorageSettings()
  })

  ipcMain.handle('desktop:save-storage-settings', (event, input: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().saveStorageSettings(parseStorageSettingsInput(input))
  })

  ipcMain.handle('desktop:clear-storage-snapshots', (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    return getReadyBackendLauncher().clearStorageSnapshots()
  })

  ipcMain.handle('desktop:get-conversation-file-access', (event, conversationId: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    if (typeof conversationId !== 'string' || !conversationId.trim()) {
      throw new Error('Conversation ID is invalid.')
    }
    return getReadyBackendLauncher().getConversationFileAccess(conversationId.trim())
  })

  ipcMain.handle('desktop:choose-workspace-path', async (event) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    const selection = await dialog.showOpenDialog({
      properties: ['openFile', 'openDirectory', 'multiSelections']
    })
    if (selection.canceled || selection.filePaths.length === 0) {
      return []
    }

    const results: Array<{ path: string; kind: 'directory' | 'file' }> = []
    for (const selectedPath of selection.filePaths) {
      const selectedPathStats = await stat(selectedPath)
      if (selectedPathStats.isDirectory() || selectedPathStats.isFile()) {
        results.push({
          path: selectedPath,
          kind: selectedPathStats.isDirectory() ? 'directory' : 'file'
        })
      }
    }
    return results
  })

  ipcMain.handle(
    'desktop:save-conversation-file-access',
    (event, conversationId: unknown, input: unknown) => {
      const frame = event.senderFrame
      if (frame === null) {
        throw new Error('Untrusted renderer IPC request.')
      }

      assertTrustedRenderer(frame.url)
      if (typeof conversationId !== 'string' || !conversationId.trim()) {
        throw new Error('Conversation ID is invalid.')
      }
      return getReadyBackendLauncher().saveConversationFileAccess(
        conversationId.trim(),
        parseWorkspaceSettings(input)
      )
    }
  )

  ipcMain.handle('desktop:list-workspace-tree', (event, folderPath: unknown, maxDepth: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    if (typeof folderPath !== 'string' || !folderPath.trim()) {
      throw new Error('Folder path is invalid.')
    }
    const depth = typeof maxDepth === 'number' && Number.isInteger(maxDepth) ? maxDepth : 3
    return listWorkspaceTree(folderPath.trim(), depth)
  })

  ipcMain.handle('desktop:read-file-preview', (event, filePath: unknown, maxBytes: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    if (typeof filePath !== 'string' || !filePath.trim()) {
      throw new Error('File path is invalid.')
    }
    const limit = typeof maxBytes === 'number' && Number.isInteger(maxBytes) ? maxBytes : 100 * 1024
    return readFilePreview(filePath.trim(), limit)
  })

  ipcMain.handle('desktop:reveal-in-finder', (event, targetPath: unknown) => {
    const frame = event.senderFrame
    if (frame === null) {
      throw new Error('Untrusted renderer IPC request.')
    }

    assertTrustedRenderer(frame.url)
    if (typeof targetPath !== 'string' || !targetPath.trim()) {
      throw new Error('Target path is invalid.')
    }
    shell.showItemInFolder(targetPath.trim())
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

  for (const runId of runWatchers.keys()) {
    stopRunWatcher(runId)
  }

  const browser = visibleBrowser
  const sessionStore = browserSessionStore
  visibleBrowser = undefined
  browserSessionStore = undefined

  void (async () => {
    if (sessionStore !== undefined && browser !== undefined) {
      try {
        await sessionStore.flush(browser)
      } catch {
        // Best-effort persistence before teardown.
      }
    }

    browser?.dispose()

    await (browserPageBridge?.stop() ?? Promise.resolve())
    await (backendLauncher?.stop() ?? Promise.resolve())
  })().finally(() => {
    app.quit()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
