import { FormEvent, useEffect, useState } from 'react'

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

type ActiveRun = {
  runId: string
  conversationId: string
  status: 'running' | 'cancelling'
}

type RunActivity = {
  runId: string
  conversationId: string
  entries: string[]
}

function conversationLabel(conversationId: string): string {
  return `Conversation ${conversationId.slice(-8)}`
}

function isTerminalRunEvent(eventType: string): boolean {
  return ['run.completed', 'run.failed', 'run.cancelled', 'run.limit_reached'].includes(eventType)
}

function runActivityEntry(eventType: string): string {
  switch (eventType) {
    case 'run.started':
      return 'Run started.'
    case 'model.requested':
      return 'Thinking…'
    case 'model.completed':
      return 'Model response received.'
    case 'tool.requested':
      return 'Using a tool…'
    case 'tool.completed':
      return 'Tool completed.'
    case 'run.completed':
      return 'Response completed.'
    case 'run.cancelled':
      return 'Run cancelled.'
    case 'run.limit_reached':
      return 'Run reached its safety limit.'
    case 'run.failed':
      return 'Run failed.'
    default:
      return 'Working…'
  }
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
  const [draft, setDraft] = useState('')
  const [isCreatingConversation, setIsCreatingConversation] = useState(false)
  const [isSubmittingMessage, setIsSubmittingMessage] = useState(false)
  const [activeRun, setActiveRun] = useState<ActiveRun | null>(null)
  const [isCancellingRun, setIsCancellingRun] = useState(false)
  const [runActivity, setRunActivity] = useState<RunActivity | null>(null)

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
      queueMicrotask(() => {
        setMessages([])
      })
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

  useEffect(() => {
    const removeEventListener = window.desktop.onRunEvent((update) => {
      appendRunActivity(update.runId, runActivityEntry(update.event.event_type))

      if (!isTerminalRunEvent(update.event.event_type)) {
        return
      }

      setActiveRun((current) => (current?.runId === update.runId ? null : current))
      setIsCancellingRun(false)

      if (update.conversationId === selectedConversationId) {
        void window.desktop
          .listConversationMessages(update.conversationId)
          .then(setMessages)
          .catch(() => setErrorMessage('Messages could not be refreshed.'))
      }
    })

    const removeErrorListener = window.desktop.onRunStreamError((error) => {
      setActiveRun((current) => (current?.runId === error.runId ? null : current))
      setIsCancellingRun(false)
      appendRunActivity(error.runId, 'Run event stream failed.')
      setErrorMessage(error.message)
    })

    return () => {
      removeEventListener()
      removeErrorListener()
    }
  }, [selectedConversationId])

  const selectedConversation = conversations.find(
    (conversation) => conversation.conversation_id === selectedConversationId
  )
  const visibleMessages = selectedConversationId === null ? [] : messages

  const isBusy = isCreatingConversation || isSubmittingMessage || activeRun !== null

  function appendRunActivity(runId: string, entry: string): void {
    setRunActivity((current) => {
      if (current === null || current.runId !== runId) {
        return current
      }

      if (current.entries.at(-1) === entry) {
        return current
      }

      return {
        ...current,
        entries: [...current.entries, entry]
      }
    })
  }

  async function createConversation(): Promise<void> {
    if (isBusy) {
      return
    }

    setIsCreatingConversation(true)
    setErrorMessage(null)

    try {
      const conversation = await window.desktop.createConversation()
      setConversations((current) => [...current, conversation])
      setSelectedConversationId(conversation.conversation_id)
      setRunActivity(null)
    } catch {
      setErrorMessage('A new conversation could not be created.')
    } finally {
      setIsCreatingConversation(false)
    }
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()

    const conversationId = selectedConversationId
    const content = draft

    if (conversationId === null || !content.trim() || isBusy) {
      return
    }

    setIsSubmittingMessage(true)
    setErrorMessage(null)

    try {
      const submitted = await window.desktop.submitMessage(conversationId, content)
      setMessages((current) => [...current, submitted.message])
      setDraft('')
      setActiveRun({
        runId: submitted.run.run_id,
        conversationId,
        status: 'running'
      })
      setRunActivity({
        runId: submitted.run.run_id,
        conversationId,
        entries: ['Starting run…']
      })
    } catch {
      setErrorMessage('Message submission failed.')
    } finally {
      setIsSubmittingMessage(false)
    }
  }

  async function cancelActiveRun(): Promise<void> {
    if (activeRun === null || isCancellingRun) {
      return
    }

    setIsCancellingRun(true)
    appendRunActivity(activeRun.runId, 'Cancellation requested.')

    try {
      await window.desktop.cancelRun(activeRun.runId)
    } catch {
      setIsCancellingRun(false)
      setErrorMessage('Cancellation request failed.')
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">LOCAL PERSONAL ASSISTANT</p>
          <h1>asAgent</h1>
        </div>

        <button
          className="new-conversation"
          disabled={isBusy}
          onClick={() => void createConversation()}
          type="button"
        >
          {isCreatingConversation ? 'Creating…' : '+ New conversation'}
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
                disabled={isBusy}
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
            <>
              {visibleMessages.map((message) => (
                <article className={`message ${message.role}`} key={message.message_id}>
                  <p className="message-role">{message.role === 'assistant' ? 'asAgent' : 'You'}</p>
                  <p>{message.content}</p>
                </article>
              ))}
              {runActivity?.conversationId === selectedConversationId ? (
                <article className="message activity">
                  <p className="message-role">asAgent activity</p>
                  <ul>
                    {runActivity.entries.map((entry, index) => (
                      <li key={`${runActivity.runId}-${index}`}>{entry}</li>
                    ))}
                  </ul>
                </article>
              ) : null}
            </>
          )}
        </div>

        <form className="composer" onSubmit={(event) => void submitMessage(event)}>
          <label className="sr-only" htmlFor="message">
            Message
          </label>
          <textarea
            disabled={selectedConversationId === null || isBusy}
            id="message"
            onChange={(event) => setDraft(event.target.value)}
            placeholder={
              selectedConversationId === null
                ? 'Create or select a conversation first.'
                : 'Type a message…'
            }
            rows={3}
            value={draft}
          />
          <div className="composer-footer">
            <span>Run activity appears in the conversation.</span>
            {activeRun === null ? (
              <button
                disabled={selectedConversationId === null || !draft.trim() || isBusy}
                type="submit"
              >
                {isSubmittingMessage ? 'Sending…' : 'Send'}
              </button>
            ) : (
              <button
                className="stop-run"
                disabled={isCancellingRun}
                onClick={() => void cancelActiveRun()}
                type="button"
              >
                {isCancellingRun ? 'Stopping…' : 'Stop'}
              </button>
            )}
          </div>
        </form>
      </section>
    </main>
  )
}
