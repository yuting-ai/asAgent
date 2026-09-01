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

interface AutomationSummary {
  automation_id: string
  name: string
  plan_summary: string
  allowed_capabilities: string[]
  status: 'draft' | 'active' | 'paused'
  created_at: string
  updated_at: string
}

interface AutomationTrigger {
  automation_trigger_id: string
  kind: 'once' | 'daily' | 'weekly'
  timezone: string
  local_time: string
  weekday: number | null
  next_run_at: string | null
  enabled: boolean
}
interface AutomationExecution {
  automation_execution_id: string
  scheduled_for: string
  status: 'claimed' | 'missed' | 'completed' | 'failed' | 'cancelled'
  run_id: string | null
  claimed_at: string
  completed_at: string | null
}
interface CreateAutomationInput {
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

interface KnowledgeSource {
  source_id: string
  library_id: string
  display_path: string
  canonical_path: string
  status: string
  scan_status: string
  created_at: string
  updated_at: string
  last_scanned_at: string | null
  document_count: number
  chunk_count: number
}

interface KnowledgeLibrary {
  library_id: string
  user_id: string
  name: string
  normalized_name: string
  status: string
  created_at: string
  updated_at: string
  sources: KnowledgeSource[]
  document_count: number
  chunk_count: number
}

interface KnowledgeIndexJob {
  job_id: string
  library_id: string
  source_id: string | null
  kind: string
  status: string
  discovered_files: number
  processed_files: number
  skipped_files: number
  failed_files: number
  total_chunks: number
  indexed_chunks: number
  cancel_requested: boolean
  created_at: string
  updated_at: string
  started_at: string | null
  completed_at: string | null
  last_error_code: string | null
}

interface KnowledgeIndexProgress {
  library_id: string
  status: 'empty' | 'ready' | 'scanning' | 'indexing' | 'error'
  active_jobs: number
  discovered_files: number
  processed_files: number
  failed_files: number
  total_chunks: number
  indexed_chunks: number
  document_count: number
  chunk_count: number
  updated_at: string
}

interface KnowledgeIndexStreamError {
  libraryId: string
  message: string
}

interface KnowledgeCitation {
  run_id: string
  assistant_message_id: string | null
  rank: number
  chunk_id: string
  score: number
  citation_label: string
  document_name: string
  source_path: string
  snippet: string
  page_start: number | null
  page_end: number | null
  section_title: string | null
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

interface StorageSettingsStatus {
  snapshot_retention_days: number
  usage_bytes: number
  snapshot_count: number
}

interface StorageSettingsInput {
  snapshot_retention_days: number
}

interface ClearStorageResult {
  freed_bytes: number
  deleted_count: number
}

interface WorkspaceFileNode {
  name: string
  path: string
  relativePath: string
  kind: 'file' | 'directory'
  size?: number
  extension?: string
  children?: WorkspaceFileNode[]
}

interface FilePreviewResult {
  path: string
  name: string
  size: number
  content: string
  isTruncated: boolean
  isBinary: boolean
}

interface UpdateCheckResult {
  currentVersion: string
  latestVersion: string
  hasUpdate: boolean
  releaseUrl: string
  downloadUrl: string
  releaseNotes: string
  publishedAt: string
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
  getAppVersion(): Promise<string>
  checkForUpdates(): Promise<UpdateCheckResult>
  openExternalLink(url: string): Promise<void>
  copyText(content: string): Promise<void>
  getBackendStatus(): Promise<{ status: 'ready' | 'unavailable' }>
  restartApp(): Promise<void>
  listConversations(): Promise<ConversationSummary[]>
  listKnowledgeLibraries(): Promise<KnowledgeLibrary[]>
  createKnowledgeLibrary(name: string): Promise<KnowledgeLibrary>
  renameKnowledgeLibrary(libraryId: string, name: string): Promise<KnowledgeLibrary>
  deleteKnowledgeLibrary(libraryId: string): Promise<void>
  addKnowledgeSource(libraryId: string, sourcePath: string): Promise<KnowledgeSource>
  detachKnowledgeSource(sourceId: string): Promise<void>
  indexKnowledgeSource(sourceId: string): Promise<KnowledgeIndexJob>
  getKnowledgeIndexJob(jobId: string): Promise<KnowledgeIndexJob>
  watchKnowledgeIndexProgress(libraryId: string): Promise<void>
  unwatchKnowledgeIndexProgress(libraryId: string): Promise<void>
  listKnowledgeConversations(): Promise<ConversationSummary[]>
  createKnowledgeConversation(libraryId: string): Promise<ConversationSummary>
  deleteKnowledgeConversation(conversationId: string): Promise<void>
  listKnowledgeConversationMessages(conversationId: string): Promise<ConversationMessage[]>
  listKnowledgeConversationCitations(conversationId: string): Promise<KnowledgeCitation[]>
  getKnowledgeConversationLibrary(conversationId: string): Promise<{ library_id: string | null }>
  submitKnowledgeMessage(conversationId: string, content: string): Promise<SubmittedMessage>
  listAutomations(): Promise<AutomationSummary[]>
  createAutomation(input: CreateAutomationInput): Promise<AutomationSummary>
  updateAutomation(automationId: string, input: UpdateAutomationInput): Promise<AutomationSummary>
  deleteAutomation(automationId: string): Promise<void>
  updateAutomationStatus(
    automationId: string,
    status: AutomationSummary['status']
  ): Promise<AutomationSummary>
  listAutomationTriggers(automationId: string): Promise<AutomationTrigger[]>
  listAutomationExecutions(automationId: string): Promise<AutomationExecution[]>
  getAutomationExecutionMessages(
    automationId: string,
    executionId: string
  ): Promise<ConversationMessage[]>
  runAutomationNow(automationId: string): Promise<AutomationExecution>
  createAutomationDraft(automationId?: string, timezone?: string): Promise<ConversationSummary>
  listAutomationDraftMessages(conversationId: string): Promise<ConversationMessage[]>
  submitAutomationDraftMessage(
    conversationId: string,
    content: string,
    tabId?: string
  ): Promise<SubmittedMessage>
  deleteAutomationDraft(conversationId: string): Promise<void>
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
  getStorageSettings(): Promise<StorageSettingsStatus>
  saveStorageSettings(input: StorageSettingsInput): Promise<StorageSettingsStatus>
  clearStorageSnapshots(): Promise<ClearStorageResult>
  getConversationFileAccess(conversationId: string): Promise<WorkspaceSettingsStatus>
  chooseWorkspacePath(): Promise<Array<{ path: string; kind: 'directory' | 'file' }>>
  saveConversationFileAccess(
    conversationId: string,
    input: WorkspaceSettingsInput
  ): Promise<WorkspaceSettingsStatus>
  listWorkspaceTree(folderPath: string, maxDepth?: number): Promise<WorkspaceFileNode | null>
  readFilePreview(filePath: string, maxBytes?: number): Promise<FilePreviewResult | null>
  revealInFinder(targetPath: string): Promise<void>
  onRunEvent(callback: (update: RunUpdate) => void): () => void
  onRunStreamError(callback: (error: RunStreamError) => void): () => void
  onKnowledgeIndexProgress(callback: (progress: KnowledgeIndexProgress) => void): () => void
  onKnowledgeIndexStreamError(callback: (error: KnowledgeIndexStreamError) => void): () => void
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
