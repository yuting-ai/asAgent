interface DesktopAppInfo {
  appName: string
  version: string
}

interface ConversationSummary {
  conversation_id: string
  created_at: string
  updated_at: string
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

interface DesktopBridge {
  getAppInfo(): Promise<DesktopAppInfo>
  getBackendStatus(): Promise<{ status: 'ready' | 'unavailable' }>
  listConversations(): Promise<ConversationSummary[]>
  listConversationMessages(conversationId: string): Promise<ConversationMessage[]>
  createConversation(): Promise<ConversationSummary>
  submitMessage(conversationId: string, content: string): Promise<SubmittedMessage>
  cancelRun(runId: string): Promise<void>
  onRunEvent(callback: (update: RunUpdate) => void): () => void
  onRunStreamError(callback: (error: RunStreamError) => void): () => void
}

declare global {
  interface Window {
    desktop: DesktopBridge
  }
}

export {}
