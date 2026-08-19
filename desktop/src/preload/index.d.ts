interface DesktopAppInfo {
  appName: string
  version: string
  dataProcessingMode: 'local' | 'external'
}

interface ConversationSummary {
  conversation_id: string
  created_at: string
  updated_at: string
  title: string | null
  last_page_url: string | null
  last_page_title: string | null
}

interface ConversationMessage {
  message_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

interface RunHistory {
  run: {
    run_id: string
    status: 'created' | 'completed' | 'failed' | 'cancelled' | 'limit_reached'
    created_at: string
    updated_at: string
  }
  events: Array<{ event_type: string; created_at: string; data: Record<string, unknown> }>
}

interface SubmittedMessage {
  message: ConversationMessage
  run: {
    run_id: string
    status: string
    created_at: string
    updated_at: string
  }
  conversation: ConversationSummary
}

interface RunUpdate {
  runId: string
  conversationId: string
  event: {
    event_type: string
    sequence: number
    data: Record<string, unknown>
  }
}

interface RunStreamError {
  runId: string
  conversationId: string
  message: string
}

interface ToolApproval {
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

interface FileChange {
  change_id: string
  run_id: string
  operation: 'create' | 'replace' | 'delete'
  status: 'prepared' | 'applied' | 'reverted' | 'conflicted'
  path: string
  created_at: string
  updated_at: string
}

interface TavilySettingsStatus {
  enabled: boolean
  api_key_saved: boolean
}

interface SavedProviderConfigStatus {
  location: 'local' | 'external'
  model: string
  base_url: string
  api_key_saved: boolean
}

interface ModelSettingsStatus {
  configured: boolean
  active: boolean
  issue: 'api_key_missing' | 'credential_store_unavailable' | null
  location: 'local' | 'external' | null
  api_key_saved: boolean
  model: string | null
  base_url: string | null
  saved_providers?: Record<string, SavedProviderConfigStatus>
}

interface AgentSettingsStatus {
  max_steps: number
}

interface ModelSettingsInput {
  location: 'local' | 'external'
  model: string
  baseUrl: string
  apiKey?: string
}

interface AgentSettingsInput {
  maxSteps: number
}

interface WorkspaceSettingsStatus {
  workspace_root: string
  additional_roots: string[]
  additional_files: string[]
}

interface WorkspaceSettingsInput {
  additionalRoots: string[]
  additionalFiles: string[]
}

interface BrowserSessionTab {
  tabId: string
  url: string
  conversationId: string | null
}

interface BrowserSessionSnapshot {
  version: 1
  visibleTabId: string
  tabs: BrowserSessionTab[]
}

interface DesktopBridge {
  getAppInfo(): Promise<DesktopAppInfo>
  showBrowser(
    tabId: string,
    bounds: { x: number; y: number; width: number; height: number }
  ): Promise<void>
  hideBrowser(): Promise<void>
  navigateBrowser(tabId: string, url: string): Promise<string>
  closeBrowserTab(tabId: string): Promise<void>
  controlBrowser(tabId: string, action: 'back' | 'forward' | 'reload' | 'home'): Promise<void>
  getBrowserSession(): Promise<BrowserSessionSnapshot>
  setBrowserTabConversation(tabId: string, conversationId: string | null): Promise<void>
  openExternalLink(url: string): Promise<void>
  copyText(content: string): Promise<void>
  getBackendStatus(): Promise<{ status: 'ready' | 'unavailable' }>
  restartApp(): Promise<void>
  listConversations(): Promise<ConversationSummary[]>
  listConversationMessages(conversationId: string): Promise<ConversationMessage[]>
  listConversationRunHistory(conversationId: string): Promise<RunHistory[]>
  listConversationFileChanges(conversationId: string): Promise<FileChange[]>
  undoFileChange(changeId: string, path: string): Promise<FileChange>
  createConversation(): Promise<ConversationSummary>
  updateConversationTitle(conversationId: string, title: string): Promise<ConversationSummary>
  deleteConversation(conversationId: string): Promise<void>
  submitMessage(conversationId: string, content: string): Promise<SubmittedMessage>
  listBrowserConversations(): Promise<ConversationSummary[]>
  createBrowserConversation(): Promise<ConversationSummary>
  deleteBrowserConversation(conversationId: string): Promise<void>
  listBrowserConversationMessages(conversationId: string): Promise<ConversationMessage[]>
  listBrowserConversationRunHistory(conversationId: string): Promise<RunHistory[]>
  submitBrowserMessage(
    conversationId: string,
    content: string,
    tabId: string
  ): Promise<SubmittedMessage>
  cancelRun(runId: string): Promise<void>
  decideToolApproval(
    approvalId: string,
    decision: 'allow_once' | 'allow_conversation' | 'deny'
  ): Promise<void>
  getTavilySettings(): Promise<TavilySettingsStatus>
  enableTavily(apiKey?: string): Promise<TavilySettingsStatus>
  disableTavily(): Promise<TavilySettingsStatus>
  deleteTavily(): Promise<TavilySettingsStatus>
  getModelSettings(): Promise<ModelSettingsStatus>
  saveModelSettings(input: ModelSettingsInput): Promise<ModelSettingsStatus>
  deleteModelSettings(): Promise<ModelSettingsStatus>
  getAgentSettings(): Promise<AgentSettingsStatus>
  saveAgentSettings(input: AgentSettingsInput): Promise<AgentSettingsStatus>
  getConversationFileAccess(conversationId: string): Promise<WorkspaceSettingsStatus>
  chooseWorkspacePath(): Promise<Array<{ path: string; kind: 'directory' | 'file' }>>
  saveConversationFileAccess(
    conversationId: string,
    input: WorkspaceSettingsInput
  ): Promise<WorkspaceSettingsStatus>
  onRunEvent(callback: (update: RunUpdate) => void): () => void
  onRunStreamError(callback: (error: RunStreamError) => void): () => void
  onToolApprovalRequested(callback: (approval: ToolApproval) => void): () => void
  onToolApprovalError(callback: (error: RunStreamError) => void): () => void
  onBrowserTabState(
    callback: (state: {
      tabId: string
      url: string
      title: string
      canGoBack: boolean
      canGoForward: boolean
    }) => void
  ): () => void
}

declare global {
  interface Window {
    desktop: DesktopBridge
  }
}

export {}
