import { useEffect, useState } from 'react'

type AppInfo = {
  appName: string
  version: string
}

type ConversationSummary = {
  conversation_id: string
  created_at: string
  updated_at: string
}

type ConversationMessage = {
  message_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

function conversationLabel(conversationId: string): string {
  return `Conversation ${conversationId.slice(-8)}`
}

export default function App(): React.JSX.Element {
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null)
  const [backendStatus, setBackendStatus] = useState<'checking' | 'ready' | 'unavailable'>(
    'checking'
  )
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadInitialData(): Promise<void> {
      try {
        const [info, status, items] = await Promise.all([
          window.desktop.getAppInfo(),
          window.desktop.getBackendStatus(),
          window.desktop.listConversations()
        ])

        if (cancelled) {
          return
        }

        setAppInfo(info)
        setBackendStatus(status.status)
        setConversations(items)
        setSelectedConversationId(items[0]?.conversation_id ?? null)
      } catch {
        if (!cancelled) {
          setBackendStatus('unavailable')
          setErrorMessage('Conversation history could not be loaded.')
        }
      }
    }

    void loadInitialData()

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (selectedConversationId === null) {
      return
    }

    const conversationId = selectedConversationId
    let cancelled = false

    async function loadMessages(): Promise<void> {
      try {
        const items = await window.desktop.listConversationMessages(conversationId)

        if (!cancelled) {
          setMessages(items)
          setErrorMessage(null)
        }
      } catch {
        if (!cancelled) {
          setErrorMessage('Messages could not be loaded.')
        }
      }
    }

    void loadMessages()

    return () => {
      cancelled = true
    }
  }, [selectedConversationId])

  const selectedConversation = conversations.find(
    (conversation) => conversation.conversation_id === selectedConversationId
  )
  const visibleMessages = selectedConversationId === null ? [] : messages

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">LOCAL PERSONAL ASSISTANT</p>
          <h1>asAgent</h1>
        </div>

        <button className="new-conversation" disabled type="button">
          + New conversation
        </button>

        <nav aria-label="Conversations">
          <p className="section-label">Conversations</p>

          {conversations.length === 0 ? (
            <p className="empty-state">No conversations yet.</p>
          ) : (
            conversations.map((conversation) => (
              <button
                className={`conversation ${
                  conversation.conversation_id === selectedConversationId ? 'active' : ''
                }`}
                key={conversation.conversation_id}
                onClick={() => setSelectedConversationId(conversation.conversation_id)}
                type="button"
              >
                <span>{conversationLabel(conversation.conversation_id)}</span>
              </button>
            ))
          )}
        </nav>

        <p className="version">
          {appInfo ? `${appInfo.appName} ${appInfo.version}` : 'Loading app info…'}
        </p>
      </aside>

      <section className="chat">
        <header className="chat-header">
          <div>
            <p className="eyebrow">Current conversation</p>
            <h2>
              {selectedConversation
                ? conversationLabel(selectedConversation.conversation_id)
                : 'No conversation selected'}
            </h2>
          </div>
          <span className={`connection-status ${backendStatus}`}>
            {backendStatus === 'ready'
              ? 'Backend ready'
              : backendStatus === 'checking'
                ? 'Checking backend…'
                : 'Backend unavailable'}
          </span>
        </header>

        <div className="messages">
          {errorMessage ? (
            <p className="error-state">{errorMessage}</p>
          ) : visibleMessages.length === 0 ? (
            <p className="empty-state">Select a conversation to view its history.</p>
          ) : (
            visibleMessages.map((message) => (
              <article className={`message ${message.role}`} key={message.message_id}>
                <p className="message-role">{message.role === 'assistant' ? 'asAgent' : 'You'}</p>
                <p>{message.content}</p>
              </article>
            ))
          )}
        </div>

        <form className="composer">
          <label className="sr-only" htmlFor="message">
            Message
          </label>
          <textarea
            disabled
            id="message"
            placeholder="Sending messages will be available next."
            rows={3}
          />
          <div className="composer-footer">
            <span>Conversation history is read-only in this build.</span>
            <button disabled type="submit">
              Send
            </button>
          </div>
        </form>
      </section>
    </main>
  )
}
