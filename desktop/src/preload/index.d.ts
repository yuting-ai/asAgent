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

interface DesktopBridge {
  getAppInfo(): Promise<DesktopAppInfo>
  openExternalLink(url: string): Promise<void>
  getBackendStatus(): Promise<{ status: 'ready' | 'unavailable' }>
  restartApp(): Promise<void>
  listConversations(): Promise<ConversationSummary[]>
  listConversationMessages(conversationId: string): Promise<ConversationMessage[]>
  createConversation(): Promise<ConversationSummary>
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
