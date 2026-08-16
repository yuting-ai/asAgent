import { contextBridge, ipcRenderer } from 'electron'

type ConversationSummary = {
  conversation_id: string
  created_at: string
  updated_at: string
  title: string | null
}

type ConversationMessage = {
  message_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
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
  }
}

type RunStreamError = {
  runId: string
  conversationId: string
  message: string
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

type ModelSettingsStatus = {
  configured: boolean
  api_key_saved: boolean
  model: string | null
  base_url: string | null
}

type ModelSettingsInput = {
  model: string
  baseUrl: string
  apiKey?: string
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

const desktopBridge = {
  getAppInfo: (): Promise<{
    appName: string
    version: string
    dataProcessingMode: 'local' | 'external'
  }> => ipcRenderer.invoke('desktop:get-app-info'),
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
  openExternalLink: (url: string): Promise<void> =>
    ipcRenderer.invoke('desktop:open-external-link', url),
  copyText: (content: string): Promise<void> => ipcRenderer.invoke('desktop:copy-text', content),
  getBackendStatus: (): Promise<{ status: 'ready' | 'unavailable' }> =>
    ipcRenderer.invoke('desktop:get-backend-status'),
  restartApp: (): Promise<void> => ipcRenderer.invoke('desktop:restart-app'),
  listConversations: (): Promise<ConversationSummary[]> =>
    ipcRenderer.invoke('desktop:list-conversations'),
  listConversationMessages: (conversationId: string): Promise<ConversationMessage[]> =>
    ipcRenderer.invoke('desktop:list-conversation-messages', conversationId),
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
  listBrowserConversationMessages: (conversationId: string): Promise<ConversationMessage[]> =>
    ipcRenderer.invoke('desktop:list-browser-conversation-messages', conversationId),
  submitBrowserMessage: (conversationId: string, content: string): Promise<SubmittedMessage> =>
    ipcRenderer.invoke('desktop:submit-browser-message', conversationId, content),
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
  getConversationFileAccess: (conversationId: string): Promise<WorkspaceSettingsStatus> =>
    ipcRenderer.invoke('desktop:get-conversation-file-access', conversationId),
  chooseWorkspacePath: (): Promise<{ path: string; kind: 'directory' | 'file' } | null> =>
    ipcRenderer.invoke('desktop:choose-workspace-path'),
  saveConversationFileAccess: (
    conversationId: string,
    input: WorkspaceSettingsInput
  ): Promise<WorkspaceSettingsStatus> =>
    ipcRenderer.invoke('desktop:save-conversation-file-access', conversationId, input),
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
