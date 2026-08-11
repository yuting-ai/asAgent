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

interface DesktopBridge {
  getAppInfo(): Promise<DesktopAppInfo>
  getBackendStatus(): Promise<{ status: 'ready' | 'unavailable' }>
  listConversations(): Promise<ConversationSummary[]>
  listConversationMessages(conversationId: string): Promise<ConversationMessage[]>
  createConversation(): Promise<ConversationSummary>
  submitMessage(conversationId: string, content: string): Promise<ConversationMessage>
}

declare global {
  interface Window {
    desktop: DesktopBridge
  }
}

export {}
