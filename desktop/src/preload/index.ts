import { contextBridge, ipcRenderer } from 'electron'

type ConversationSummary = {
  conversation_id: string
  created_at: string
  updated_at: string
  title: string | null
  last_page_url: string | null
  last_page_title: string | null
}

type AutomationSummary = {
  automation_id: string
  name: string
  plan_summary: string
  allowed_capabilities: string[]
  status: 'draft' | 'active' | 'paused'
  created_at: string
  updated_at: string
}

type AutomationTrigger = {
  automation_trigger_id: string
  kind: 'once' | 'daily' | 'weekly'
  timezone: string
  local_time: string
  weekday: number | null
  next_run_at: string | null
  enabled: boolean
}
type AutomationExecution = {
  automation_execution_id: string
  scheduled_for: string
  status: 'claimed' | 'missed' | 'completed' | 'failed' | 'cancelled'
  run_id: string | null
  claimed_at: string
  completed_at: string | null
}
type CreateAutomationInput = {
  name: string
  planSummary: string
  allowedCapabilities: string[]
  trigger: {
    kind: 'once' | 'daily' | 'weekly'
    timezone: string
    localTime: string
    weekday?: number
    nextRunAt?: string
  }
}
type UpdateAutomationInput = CreateAutomationInput

type ConversationMessage = {
  message_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

type RunHistory = {
  run: {
    run_id: string
    status: 'created' | 'completed' | 'failed' | 'cancelled' | 'limit_reached'
    created_at: string
    updated_at: string
  }
  events: Array<{ event_type: string; created_at: string; data: Record<string, unknown> }>
}

type SubmittedMessage = {
  message: ConversationMessage
  run: {
    run_id: string
    status: string
    created_at: string
    updated_at: string
  }
  conversation: ConversationSummary
}

type RunUpdate = {
  runId: string
  conversationId: string
  event: {
    event_type: string
    sequence: number
    data: Record<string, unknown>
  }
}

type RunStreamError = {
  runId: string
  conversationId: string
  message: string
}

type BrowserSessionTab = {
  tabId: string
  url: string
  conversationId: string | null
}

type BrowserSessionSnapshot = {
  version: 1
  visibleTabId: string
  tabs: BrowserSessionTab[]
}

type ToolApproval = {
  approval_id: string
  run_id: string
  conversation_id: string
  tool_call_id: string
  tool_id: string
  display_name: string
  description: string
  arguments: Record<string, unknown>
  resource_path: string | null
  impact_summary: string | null
  allows_conversation_approval: boolean
}

type FileChange = {
  change_id: string
  run_id: string
  operation: 'create' | 'replace' | 'delete'
  status: 'prepared' | 'applied' | 'reverted' | 'conflicted'
  path: string
  created_at: string
  updated_at: string
}

type TavilySettingsStatus = {
  enabled: boolean
  api_key_saved: boolean
}

type SavedProviderConfigStatus = {
  location: 'local' | 'external'
  model: string
  base_url: string
  api_key_saved: boolean
}

type ModelSettingsStatus = {
  configured: boolean
  active: boolean
  issue: 'api_key_missing' | 'credential_store_unavailable' | null
  location: 'local' | 'external' | null
  api_key_saved: boolean
  model: string | null
  base_url: string | null
  saved_providers?: Record<string, SavedProviderConfigStatus>
}

type AgentSettingsStatus = {
  max_steps: number
}

type ModelSettingsInput = {
  location: 'local' | 'external'
  model: string
  baseUrl: string
  apiKey?: string
}

type AgentSettingsInput = {
  maxSteps: number
}

type StorageSettingsStatus = {
  snapshot_retention_days: number
  usage_bytes: number
  snapshot_count: number
}

type StorageSettingsInput = {
  snapshot_retention_days: number
}

type ClearStorageResult = {
  freed_bytes: number
  deleted_count: number
}

type WorkspaceSettingsStatus = {
  workspace_root: string
  additional_roots: string[]
  additional_files: string[]
}

type WorkspaceSettingsInput = {
  additionalRoots: string[]
  additionalFiles: string[]
}

type WorkspaceFileNode = {
  name: string
  path: string
  relativePath: string
  kind: 'file' | 'directory'
  size?: number
  extension?: string
  children?: WorkspaceFileNode[]
}

type FilePreviewResult = {
  path: string
  name: string
  size: number
  content: string
  isTruncated: boolean
  isBinary: boolean
}

type UpdateCheckResult = {
  currentVersion: string
  latestVersion: string
  hasUpdate: boolean
  releaseUrl: string
  releaseNotes: string
  publishedAt: string
}

const desktopBridge = {
  getAppInfo: (): Promise<{
    appName: string
    version: string
    dataProcessingMode: 'local' | 'external'
  }> => ipcRenderer.invoke('desktop:get-app-info'),
  getAppVersion: (): Promise<string> => ipcRenderer.invoke('desktop:get-app-version'),
  checkForUpdates: (): Promise<UpdateCheckResult> =>
    ipcRenderer.invoke('desktop:check-for-updates'),
  showBrowser: (
    tabId: string,
    bounds: { x: number; y: number; width: number; height: number }
  ): Promise<void> => ipcRenderer.invoke('desktop:show-browser', tabId, bounds),
  hideBrowser: (): Promise<void> => ipcRenderer.invoke('desktop:hide-browser'),
  navigateBrowser: (tabId: string, url: string): Promise<string> =>
    ipcRenderer.invoke('desktop:navigate-browser', tabId, url),
  closeBrowserTab: (tabId: string): Promise<void> =>
    ipcRenderer.invoke('desktop:close-browser-tab', tabId),
  controlBrowser: (tabId: string, action: 'back' | 'forward' | 'reload' | 'home'): Promise<void> =>
    ipcRenderer.invoke('desktop:control-browser', tabId, action),
  getBrowserSession: (): Promise<BrowserSessionSnapshot> =>
    ipcRenderer.invoke('desktop:get-browser-session'),
  setBrowserTabConversation: (tabId: string, conversationId: string | null): Promise<void> =>
    ipcRenderer.invoke('desktop:set-browser-tab-conversation', tabId, conversationId),
  openExternalLink: (url: string): Promise<void> =>
    ipcRenderer.invoke('desktop:open-external-link', url),
  copyText: (content: string): Promise<void> => ipcRenderer.invoke('desktop:copy-text', content),
  getBackendStatus: (): Promise<{ status: 'ready' | 'unavailable' }> =>
    ipcRenderer.invoke('desktop:get-backend-status'),
  restartApp: (): Promise<void> => ipcRenderer.invoke('desktop:restart-app'),
  listConversations: (): Promise<ConversationSummary[]> =>
    ipcRenderer.invoke('desktop:list-conversations'),
  listAutomations: (): Promise<AutomationSummary[]> =>
    ipcRenderer.invoke('desktop:list-automations'),
  createAutomation: (input: CreateAutomationInput): Promise<AutomationSummary> =>
    ipcRenderer.invoke('desktop:create-automation', input),
  updateAutomation: (
    automationId: string,
    input: UpdateAutomationInput
  ): Promise<AutomationSummary> =>
    ipcRenderer.invoke('desktop:update-automation', automationId, input),
  deleteAutomation: (automationId: string): Promise<void> =>
    ipcRenderer.invoke('desktop:delete-automation', automationId),
  updateAutomationStatus: (
    automationId: string,
    status: AutomationSummary['status']
  ): Promise<AutomationSummary> =>
    ipcRenderer.invoke('desktop:update-automation-status', automationId, status),
  listAutomationTriggers: (automationId: string): Promise<AutomationTrigger[]> =>
    ipcRenderer.invoke('desktop:list-automation-triggers', automationId),
  listAutomationExecutions: (automationId: string): Promise<AutomationExecution[]> =>
    ipcRenderer.invoke('desktop:list-automation-executions', automationId),
  getAutomationExecutionMessages: (
    automationId: string,
    executionId: string
  ): Promise<ConversationMessage[]> =>
    ipcRenderer.invoke('desktop:get-automation-execution-messages', automationId, executionId),
  runAutomationNow: (automationId: string): Promise<AutomationExecution> =>
    ipcRenderer.invoke('desktop:run-automation-now', automationId),
  createAutomationDraft: (automationId?: string, timezone = 'UTC'): Promise<ConversationSummary> =>
    ipcRenderer.invoke('desktop:create-automation-draft', automationId, timezone),
  listAutomationDraftMessages: (conversationId: string): Promise<ConversationMessage[]> =>
    ipcRenderer.invoke('desktop:list-automation-draft-messages', conversationId),
  submitAutomationDraftMessage: (
    conversationId: string,
    content: string,
    tabId?: string
  ): Promise<SubmittedMessage> =>
    ipcRenderer.invoke('desktop:submit-automation-draft-message', conversationId, content, tabId),
  deleteAutomationDraft: (conversationId: string): Promise<void> =>
    ipcRenderer.invoke('desktop:delete-automation-draft', conversationId),
  listConversationMessages: (conversationId: string): Promise<ConversationMessage[]> =>
    ipcRenderer.invoke('desktop:list-conversation-messages', conversationId),
  listConversationRunHistory: (conversationId: string): Promise<RunHistory[]> =>
    ipcRenderer.invoke('desktop:list-conversation-run-history', conversationId),
  listConversationFileChanges: (conversationId: string): Promise<FileChange[]> =>
    ipcRenderer.invoke('desktop:list-conversation-file-changes', conversationId),
  undoFileChange: (changeId: string, path: string): Promise<FileChange> =>
    ipcRenderer.invoke('desktop:undo-file-change', changeId, path),
  createConversation: (): Promise<ConversationSummary> =>
    ipcRenderer.invoke('desktop:create-conversation'),
  updateConversationTitle: (conversationId: string, title: string): Promise<ConversationSummary> =>
    ipcRenderer.invoke('desktop:update-conversation-title', conversationId, title),
  deleteConversation: (conversationId: string): Promise<void> =>
    ipcRenderer.invoke('desktop:delete-conversation', conversationId),
  submitMessage: (conversationId: string, content: string): Promise<SubmittedMessage> =>
    ipcRenderer.invoke('desktop:submit-message', conversationId, content),
  listBrowserConversations: (): Promise<ConversationSummary[]> =>
    ipcRenderer.invoke('desktop:list-browser-conversations'),
  createBrowserConversation: (): Promise<ConversationSummary> =>
    ipcRenderer.invoke('desktop:create-browser-conversation'),
  deleteBrowserConversation: (conversationId: string): Promise<void> =>
    ipcRenderer.invoke('desktop:delete-browser-conversation', conversationId),
  listBrowserConversationMessages: (conversationId: string): Promise<ConversationMessage[]> =>
    ipcRenderer.invoke('desktop:list-browser-conversation-messages', conversationId),
  listBrowserConversationRunHistory: (conversationId: string): Promise<RunHistory[]> =>
    ipcRenderer.invoke('desktop:list-browser-conversation-run-history', conversationId),
  submitBrowserMessage: (
    conversationId: string,
    content: string,
    tabId: string
  ): Promise<SubmittedMessage> =>
    ipcRenderer.invoke('desktop:submit-browser-message', conversationId, content, tabId),
  cancelRun: (runId: string): Promise<void> => ipcRenderer.invoke('desktop:cancel-run', runId),
  decideToolApproval: (
    approvalId: string,
    decision: 'allow_once' | 'allow_conversation' | 'deny'
  ): Promise<void> => ipcRenderer.invoke('desktop:decide-tool-approval', approvalId, decision),
  getTavilySettings: (): Promise<TavilySettingsStatus> =>
    ipcRenderer.invoke('desktop:get-tavily-settings'),
  enableTavily: (apiKey?: string): Promise<TavilySettingsStatus> =>
    ipcRenderer.invoke('desktop:enable-tavily', apiKey),
  disableTavily: (): Promise<TavilySettingsStatus> => ipcRenderer.invoke('desktop:disable-tavily'),
  deleteTavily: (): Promise<TavilySettingsStatus> => ipcRenderer.invoke('desktop:delete-tavily'),
  getModelSettings: (): Promise<ModelSettingsStatus> =>
    ipcRenderer.invoke('desktop:get-model-settings'),
  saveModelSettings: (input: ModelSettingsInput): Promise<ModelSettingsStatus> =>
    ipcRenderer.invoke('desktop:save-model-settings', input),
  deleteModelSettings: (): Promise<ModelSettingsStatus> =>
    ipcRenderer.invoke('desktop:delete-model-settings'),
  getAgentSettings: (): Promise<AgentSettingsStatus> =>
    ipcRenderer.invoke('desktop:get-agent-settings'),
  saveAgentSettings: (input: AgentSettingsInput): Promise<AgentSettingsStatus> =>
    ipcRenderer.invoke('desktop:save-agent-settings', input),
  getStorageSettings: (): Promise<StorageSettingsStatus> =>
    ipcRenderer.invoke('desktop:get-storage-settings'),
  saveStorageSettings: (input: StorageSettingsInput): Promise<StorageSettingsStatus> =>
    ipcRenderer.invoke('desktop:save-storage-settings', input),
  clearStorageSnapshots: (): Promise<ClearStorageResult> =>
    ipcRenderer.invoke('desktop:clear-storage-snapshots'),
  getConversationFileAccess: (conversationId: string): Promise<WorkspaceSettingsStatus> =>
    ipcRenderer.invoke('desktop:get-conversation-file-access', conversationId),
  chooseWorkspacePath: (): Promise<Array<{ path: string; kind: 'directory' | 'file' }>> =>
    ipcRenderer.invoke('desktop:choose-workspace-path'),
  saveConversationFileAccess: (
    conversationId: string,
    input: WorkspaceSettingsInput
  ): Promise<WorkspaceSettingsStatus> =>
    ipcRenderer.invoke('desktop:save-conversation-file-access', conversationId, input),
  listWorkspaceTree: (folderPath: string, maxDepth?: number): Promise<WorkspaceFileNode | null> =>
    ipcRenderer.invoke('desktop:list-workspace-tree', folderPath, maxDepth),
  readFilePreview: (filePath: string, maxBytes?: number): Promise<FilePreviewResult | null> =>
    ipcRenderer.invoke('desktop:read-file-preview', filePath, maxBytes),
  revealInFinder: (targetPath: string): Promise<void> =>
    ipcRenderer.invoke('desktop:reveal-in-finder', targetPath),
  onRunEvent: (callback: (update: RunUpdate) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, update: RunUpdate): void => {
      callback(update)
    }

    ipcRenderer.on('desktop:run-event', listener)
    return () => ipcRenderer.removeListener('desktop:run-event', listener)
  },
  onRunStreamError: (callback: (error: RunStreamError) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, error: RunStreamError): void => {
      callback(error)
    }

    ipcRenderer.on('desktop:run-stream-error', listener)
    return () => ipcRenderer.removeListener('desktop:run-stream-error', listener)
  },
  onToolApprovalRequested: (callback: (approval: ToolApproval) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, approval: ToolApproval): void => {
      callback(approval)
    }

    ipcRenderer.on('desktop:tool-approval-requested', listener)
    return () => ipcRenderer.removeListener('desktop:tool-approval-requested', listener)
  },
  onToolApprovalError: (callback: (error: RunStreamError) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, error: RunStreamError): void => {
      callback(error)
    }

    ipcRenderer.on('desktop:tool-approval-error', listener)
    return () => ipcRenderer.removeListener('desktop:tool-approval-error', listener)
  },
  onBrowserTabState: (
    callback: (state: {
      tabId: string
      url: string
      title: string
      canGoBack: boolean
      canGoForward: boolean
    }) => void
  ): (() => void) => {
    const listener = (
      _event: Electron.IpcRendererEvent,
      state: {
        tabId: string
        url: string
        title: string
        canGoBack: boolean
        canGoForward: boolean
      }
    ): void => {
      callback(state)
    }

    ipcRenderer.on('desktop:browser-tab-state', listener)
    return () => ipcRenderer.removeListener('desktop:browser-tab-state', listener)
  }
}

contextBridge.exposeInMainWorld('desktop', desktopBridge)
