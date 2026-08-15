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
}

interface ConversationMessage {
  message_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
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

interface ModelSettingsStatus {
  configured: boolean
  api_key_saved: boolean
  model: string | null
  base_url: string | null
}

interface ModelSettingsInput {
  model: string
  baseUrl: string
  apiKey?: string
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

interface DesktopBridge {
  getAppInfo(): Promise<DesktopAppInfo>
  openExternalLink(url: string): Promise<void>
  copyText(content: string): Promise<void>
  getBackendStatus(): Promise<{ status: 'ready' | 'unavailable' }>
  restartApp(): Promise<void>
  listConversations(): Promise<ConversationSummary[]>
  listConversationMessages(conversationId: string): Promise<ConversationMessage[]>
  listConversationFileChanges(conversationId: string): Promise<FileChange[]>
  undoFileChange(changeId: string, path: string): Promise<FileChange>
  createConversation(): Promise<ConversationSummary>
  updateConversationTitle(conversationId: string, title: string): Promise<ConversationSummary>
  deleteConversation(conversationId: string): Promise<void>
  submitMessage(conversationId: string, content: string): Promise<SubmittedMessage>
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
  getConversationFileAccess(conversationId: string): Promise<WorkspaceSettingsStatus>
  chooseWorkspacePath(): Promise<{ path: string; kind: 'directory' | 'file' } | null>
  saveConversationFileAccess(
    conversationId: string,
    input: WorkspaceSettingsInput
  ): Promise<WorkspaceSettingsStatus>
  onRunEvent(callback: (update: RunUpdate) => void): () => void
  onRunStreamError(callback: (error: RunStreamError) => void): () => void
  onToolApprovalRequested(callback: (approval: ToolApproval) => void): () => void
  onToolApprovalError(callback: (error: RunStreamError) => void): () => void
}

declare global {
  interface Window {
    desktop: DesktopBridge
  }
}

export {}
