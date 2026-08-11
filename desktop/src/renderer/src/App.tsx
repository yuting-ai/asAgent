import { FormEvent, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'

type AppInfo = {
  appName: string
  version: string
  dataProcessingMode: 'local' | 'external'
}

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

type ActiveRun = {
  runId: string
  conversationId: string
  status: 'running' | 'cancelling'
}

type RunActivityOutcome = 'completed' | 'failed' | 'cancelled' | 'limit'

type RunActivity = {
  runId: string
  conversationId: string
  entries: string[]
  phase: 'live' | 'done'
  outcome: RunActivityOutcome | null
  startedAt: number
  endedAt: number | null
}

type AppView =
  | 'chat'
  | 'activity'
  | 'privacy'
  | 'scheduled'
  | 'automations'
  | 'history'
  | 'files'
  | 'mail'
  | 'calendar'
  | 'add-app'
  | 'preferences'

type ActivityTab = 'approvals' | 'schedule'

function conversationLabel(title: string | null): string {
  return title ?? 'New conversation'
}

function orderConversations(conversations: ConversationSummary[]): ConversationSummary[] {
  return [...conversations].sort((left, right) => {
    const updatedAtDifference =
      new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()

    if (updatedAtDifference !== 0) {
      return updatedAtDifference
    }

    return right.conversation_id.localeCompare(left.conversation_id)
  })
}

function formatThreadTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return ''
  }

  const now = new Date()
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()

  if (sameDay) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  const isYesterday =
    date.getFullYear() === yesterday.getFullYear() &&
    date.getMonth() === yesterday.getMonth() &&
    date.getDate() === yesterday.getDate()

  if (isYesterday) {
    return 'Yesterday'
  }

  return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
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

function runActivityOutcome(eventType: string): RunActivityOutcome | null {
  switch (eventType) {
    case 'run.completed':
      return 'completed'
    case 'run.failed':
      return 'failed'
    case 'run.cancelled':
      return 'cancelled'
    case 'run.limit_reached':
      return 'limit'
    default:
      return null
  }
}

function formatElapsed(startedAt: number, endedAt: number | null): string | null {
  const end = endedAt ?? Date.now()
  const seconds = Math.max(1, Math.round((end - startedAt) / 1000))
  return `${seconds}s`
}

function activitySummaryLabel(activity: RunActivity): string {
  const stepCount = activity.entries.length
  const steps = `${stepCount} step${stepCount === 1 ? '' : 's'}`
  const elapsed = formatElapsed(activity.startedAt, activity.endedAt)
  const withTime = elapsed === null ? steps : `${steps} · ${elapsed}`

  switch (activity.outcome) {
    case 'failed':
      return `Failed · ${withTime}`
    case 'cancelled':
      return `Cancelled · ${withTime}`
    case 'limit':
      return `Stopped · ${withTime}`
    case 'completed':
    default:
      return `Worked · ${withTime}`
  }
}

function Icon({ path, className }: { path: string; className?: string }): React.JSX.Element {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      viewBox="0 0 24 24"
    >
      <path d={path} />
    </svg>
  )
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
  const [activityExpanded, setActivityExpanded] = useState(false)
  const [activeView, setActiveView] = useState<AppView>('chat')
  const [activityTab, setActivityTab] = useState<ActivityTab>('approvals')
  const messagesEndRef = useRef<HTMLDivElement | null>(null)

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
        setConversations(orderConversations(items))
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

      const outcome = runActivityOutcome(update.event.event_type)
      if (outcome === null) {
        return
      }

      finishRunActivity(update.runId, outcome)
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
      finishRunActivity(error.runId, 'failed')
      setErrorMessage(error.message)
    })

    return () => {
      removeEventListener()
      removeErrorListener()
    }
  }, [selectedConversationId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, runActivity?.entries.length, runActivity?.phase, selectedConversationId])

  const selectedConversation = conversations.find(
    (conversation) => conversation.conversation_id === selectedConversationId
  )
  const visibleMessages = selectedConversationId === null ? [] : messages
  const isBusy = isCreatingConversation || isSubmittingMessage || activeRun !== null

  const backendLabel =
    backendStatus === 'ready'
      ? appInfo?.dataProcessingMode === 'external'
        ? 'RUNNING · EXTERNAL MODEL ENABLED'
        : 'RUNNING LOCALLY · NO DATA LEAVES THIS DEVICE'
      : backendStatus === 'checking'
        ? 'CHECKING LOCAL BACKEND…'
        : 'BACKEND UNAVAILABLE'

  const agentSub =
    backendStatus === 'unavailable'
      ? '● Offline'
      : activeRun !== null
        ? '● Working on a run'
        : '● Idle — ready for chat'

  const usesExternalModel = appInfo?.dataProcessingMode === 'external'

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

  function finishRunActivity(runId: string, outcome: RunActivityOutcome): void {
    setRunActivity((current) => {
      if (current === null || current.runId !== runId) {
        return current
      }

      return {
        ...current,
        phase: 'done',
        outcome,
        endedAt: Date.now()
      }
    })
    setActivityExpanded(false)
  }

  async function createConversation(): Promise<void> {
    if (isBusy) {
      return
    }

    setIsCreatingConversation(true)
    setErrorMessage(null)

    try {
      const conversation = await window.desktop.createConversation()
      setConversations((current) => orderConversations([...current, conversation]))
      setSelectedConversationId(conversation.conversation_id)
      setRunActivity(null)
      setActivityExpanded(false)
      setActiveView('chat')
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
      setConversations((current) =>
        orderConversations(
          current.map((conversation) =>
            conversation.conversation_id === submitted.conversation.conversation_id
              ? submitted.conversation
              : conversation
          )
        )
      )
      setDraft('')
      setActiveRun({
        runId: submitted.run.run_id,
        conversationId,
        status: 'running'
      })
      setRunActivity({
        runId: submitted.run.run_id,
        conversationId,
        entries: ['Starting run…'],
        phase: 'live',
        outcome: null,
        startedAt: Date.now(),
        endedAt: null
      })
      setActivityExpanded(false)
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

  function railItemClass(view: AppView): string {
    return `rail-item${activeView === view ? ' active' : ''}`
  }

  function renderPlaceholderView(title: string, subtitle: string): React.JSX.Element {
    return (
      <>
        <section className="center">
          <div className="center-header">
            <div className="center-title">{title}</div>
            <div className="center-sub">{subtitle}</div>
          </div>
          <div className="placeholder-banner">
            This area is a visual placeholder. The feature is not implemented yet.
          </div>
        </section>
        <aside className="attn">
          <div className="attn-header">Coming soon</div>
          <p className="chat-context-sub">
            Connected data, schedule details, and controls for {title.toLowerCase()} will appear
            here.
          </p>
        </aside>
      </>
    )
  }

  return (
    <div className="app-shell">
      <div aria-hidden="true" className="backdrop">
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <div className="orb orb-3" />
        <div className="orb orb-4" />
      </div>

      <div className="app">
        <header className="titlebar">
          <div className="brand">
            <div className="brand-mark" />
            asAgent
          </div>

          <label className="titlebar-search">
            <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <circle cx="11" cy="11" r="7" />
              <path d="m21 21-4.3-4.3" />
            </svg>
            <input disabled placeholder="Search tasks, files, history…" type="search" />
            <kbd>⌘K</kbd>
          </label>

          <div className="titlebar-status">
            <span
              className={`dot-live${
                backendStatus === 'ready'
                  ? ''
                  : backendStatus === 'checking'
                    ? ' checking'
                    : ' offline'
              }`}
            />
            {backendLabel}
          </div>

          <button
            className="titlebar-icon-btn"
            onClick={() => setActiveView('preferences')}
            title="Notifications (placeholder)"
            type="button"
          >
            <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
              <path d="M13.7 21a2 2 0 0 1-3.4 0" />
            </svg>
          </button>
          <button
            className="titlebar-icon-btn"
            onClick={() => setActiveView('preferences')}
            title="Settings"
            type="button"
          >
            <Icon path="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09A1.65 1.65 0 0 0 15 4.6a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </button>
        </header>

        <nav aria-label="Primary" className="rail">
          <div className="rail-section">
            <div className="rail-label">Agent</div>
            <button
              className={railItemClass('chat')}
              onClick={() => setActiveView('chat')}
              type="button"
            >
              <Icon
                className="rail-icon"
                path="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"
              />
              Chat
            </button>
            <button
              className={railItemClass('activity')}
              onClick={() => setActiveView('activity')}
              type="button"
            >
              <Icon className="rail-icon" path="M13 2 3 14h7l-1 8 10-12h-7l1-8z" />
              Activity
              {activeRun !== null ? (
                <span className="rail-live">
                  <span className="rail-live-dot" />1 running
                </span>
              ) : null}
            </button>
            <button
              className={railItemClass('scheduled')}
              onClick={() => setActiveView('scheduled')}
              type="button"
            >
              <svg
                className="rail-icon"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <circle cx="12" cy="12" r="9" />
                <path d="M12 7v5l3 3" />
              </svg>
              Scheduled
              <span className="rail-count">—</span>
            </button>
            <button
              className={railItemClass('automations')}
              onClick={() => setActiveView('automations')}
              type="button"
            >
              <Icon className="rail-icon" path="M4 5h16M4 12h10M4 19h13" />
              Automations
              <span className="rail-count">—</span>
            </button>
            <button
              className={railItemClass('privacy')}
              onClick={() => setActiveView('privacy')}
              type="button"
            >
              <Icon
                className="rail-icon"
                path="M12 2 3 6v6c0 5 4 8.5 9 10 5-1.5 9-5 9-10V6l-9-4Z"
              />
              Privacy & Permissions
            </button>
            <button
              className={railItemClass('history')}
              onClick={() => setActiveView('history')}
              type="button"
            >
              <Icon className="rail-icon" path="M3 3v18h18M7 15l4-5 3 3 5-7" />
              History
            </button>
          </div>

          <div className="rail-section">
            <div className="rail-label">Connected</div>
            <button
              className={railItemClass('files')}
              onClick={() => setActiveView('files')}
              type="button"
            >
              <svg
                className="rail-icon"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <rect height="16" rx="2" width="18" x="3" y="4" />
                <path d="M3 9h18" />
              </svg>
              Files & Folders
              <span className="status-dot pending" title="Not connected yet" />
            </button>
            <button
              className={railItemClass('mail')}
              onClick={() => setActiveView('mail')}
              type="button"
            >
              <Icon className="rail-icon" path="M4 4h16v16H4zM4 8h16M8 4v16" />
              Mail
              <span className="status-dot pending" title="Not connected yet" />
            </button>
            <button
              className={railItemClass('calendar')}
              onClick={() => setActiveView('calendar')}
              type="button"
            >
              <svg
                className="rail-icon"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <rect height="14" rx="2" width="18" x="3" y="5" />
                <path d="M3 10h18" />
              </svg>
              Calendar
              <span className="status-dot pending" title="Not connected yet" />
            </button>
            <button
              className={railItemClass('add-app')}
              onClick={() => setActiveView('add-app')}
              type="button"
            >
              <svg
                className="rail-icon"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <circle cx="12" cy="12" r="9" />
                <path d="M8 12h8M12 8v8" />
              </svg>
              + Add app
            </button>
          </div>

          <div className="rail-footer">
            <button
              className="rail-settings"
              onClick={() => setActiveView('preferences')}
              type="button"
            >
              <Icon path="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09A1.65 1.65 0 0 0 15 4.6a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
              Agent preferences
            </button>
            <div className="agent-card">
              <div className="agent-card-top">
                <div className="agent-avatar">aA</div>
                <div>
                  <div className="agent-name">asAgent</div>
                  <div
                    className={`agent-sub${
                      backendStatus === 'unavailable'
                        ? ' offline'
                        : activeRun !== null
                          ? ' busy'
                          : ''
                    }`}
                  >
                    {agentSub}
                  </div>
                </div>
              </div>
              <div className="agent-meter">
                <div className="agent-meter-fill" />
              </div>
              <div className="agent-meter-label">
                <span>{appInfo ? `${appInfo.appName} ${appInfo.version}` : 'Loading…'}</span>
                <span>Local</span>
              </div>
            </div>
          </div>
        </nav>

        <div className={`view${activeView === 'chat' ? ' active' : ''}`}>
          <section className="center">
            <div className="chat-layout">
              <div className="chat-threads">
                <div className="chat-threads-header">
                  <div className="chat-threads-title">Conversations</div>
                  <button
                    className="chat-new-btn"
                    disabled={isBusy}
                    onClick={() => void createConversation()}
                    title="New conversation"
                    type="button"
                  >
                    <Icon path="M12 5v14M5 12h14" />
                  </button>
                </div>

                {conversations.length === 0 ? (
                  <p className="chat-context-sub">No conversations yet. Create one to start.</p>
                ) : (
                  conversations.map((conversation) => (
                    <button
                      className={`chat-thread-item${
                        conversation.conversation_id === selectedConversationId ? ' active' : ''
                      }`}
                      disabled={isBusy}
                      key={conversation.conversation_id}
                      onClick={() => setSelectedConversationId(conversation.conversation_id)}
                      type="button"
                    >
                      <div className="chat-thread-name">
                        {conversationLabel(conversation.title)}
                      </div>
                      <div className="chat-thread-preview">Local conversation</div>
                      <div className="chat-thread-time">
                        {formatThreadTime(conversation.updated_at)}
                      </div>
                    </button>
                  ))
                )}
              </div>

              <div className="chat-main">
                <div className="chat-thread-header">
                  <div className="chat-thread-header-title">
                    {selectedConversation
                      ? conversationLabel(selectedConversation.title)
                      : 'No conversation selected'}
                  </div>
                  <div className="chat-file-chip">
                    <Icon path="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6" />
                    Attachments soon
                  </div>
                </div>

                {errorMessage ? <p className="chat-error">{errorMessage}</p> : null}

                <div className="chat-messages">
                  {selectedConversationId === null ? (
                    <p className="chat-empty">
                      Create or select a conversation to view its history and send messages.
                    </p>
                  ) : visibleMessages.length === 0 &&
                    runActivity?.conversationId !== selectedConversationId ? (
                    <p className="chat-empty">
                      No messages yet. Say hello below to start this conversation.
                    </p>
                  ) : (
                    <>
                      {(() => {
                        const visibleActivity =
                          runActivity?.conversationId === selectedConversationId
                            ? runActivity
                            : null
                        const activityAnchorIndex =
                          visibleActivity === null
                            ? -1
                            : visibleMessages.reduce(
                                (lastIndex, message, index) =>
                                  message.role === 'user' ? index : lastIndex,
                                -1
                              )

                        function renderRunActivity(activity: RunActivity): React.JSX.Element {
                          return (
                            <div className="msg agent run-activity-msg">
                              {activity.phase === 'done' && !activityExpanded ? (
                                <button
                                  aria-expanded="false"
                                  className={`activity-summary outcome-${activity.outcome ?? 'completed'}`}
                                  onClick={() => setActivityExpanded(true)}
                                  type="button"
                                >
                                  <span className="activity-summary-label">
                                    {activitySummaryLabel(activity)}
                                  </span>
                                  <span aria-hidden="true" className="activity-chevron">
                                    ▾
                                  </span>
                                </button>
                              ) : (
                                <div
                                  className={`msg-bubble activity-shell${
                                    activity.phase === 'live' ? ' is-live' : ''
                                  }`}
                                >
                                  <div className="activity-card">
                                    {activity.phase === 'live' ? (
                                      <div className="activity-card-header">
                                        <span aria-hidden="true" className="activity-spinner" />
                                        <span className="activity-card-title">Working…</span>
                                        <span className="activity-card-meta">
                                          {activity.entries.at(-1) ?? 'Starting run…'}
                                        </span>
                                      </div>
                                    ) : (
                                      <button
                                        aria-expanded="true"
                                        className="activity-card-header is-button"
                                        onClick={() => setActivityExpanded(false)}
                                        type="button"
                                      >
                                        <span className="activity-card-title">
                                          {activitySummaryLabel(activity)}
                                        </span>
                                        <span aria-hidden="true" className="activity-chevron">
                                          ▴
                                        </span>
                                      </button>
                                    )}
                                    <ul className="activity-list">
                                      {activity.entries.map((entry, index) => {
                                        const isCurrent =
                                          activity.phase === 'live' &&
                                          index === activity.entries.length - 1

                                        return (
                                          <li
                                            className={`activity-item${isCurrent ? ' is-current' : ''}`}
                                            key={`${activity.runId}-${index}`}
                                          >
                                            <span
                                              aria-hidden="true"
                                              className="activity-item-dot"
                                            />
                                            <span>{entry}</span>
                                          </li>
                                        )
                                      })}
                                    </ul>
                                  </div>
                                </div>
                              )}
                            </div>
                          )
                        }

                        return (
                          <>
                            {visibleMessages.map((message, index) => (
                              <div className="chat-turn" key={message.message_id}>
                                <div
                                  className={`msg ${message.role === 'assistant' ? 'agent' : 'user'}`}
                                >
                                  <div className="msg-bubble">
                                    {message.role === 'assistant' ? (
                                      <div className="markdown-content">
                                        <ReactMarkdown>{message.content}</ReactMarkdown>
                                      </div>
                                    ) : (
                                      message.content
                                    )}
                                  </div>
                                </div>
                                {visibleActivity !== null && index === activityAnchorIndex
                                  ? renderRunActivity(visibleActivity)
                                  : null}
                              </div>
                            ))}
                            {visibleActivity !== null && activityAnchorIndex === -1
                              ? renderRunActivity(visibleActivity)
                              : null}
                          </>
                        )
                      })()}
                      <div ref={messagesEndRef} />
                    </>
                  )}
                </div>

                <form className="chat-composer" onSubmit={(event) => void submitMessage(event)}>
                  <div className="chat-composer-box">
                    <div className="chat-attach-btn" title="Attachments are not available yet">
                      <Icon path="m21.4 11.5-9 9a5 5 0 0 1-7-7l9-9a3.5 3.5 0 0 1 5 5l-9 9a2 2 0 0 1-3-3l8-8" />
                    </div>
                    <textarea
                      disabled={selectedConversationId === null || isBusy}
                      onChange={(event) => setDraft(event.target.value)}
                      placeholder={
                        selectedConversationId === null
                          ? 'Create or select a conversation first.'
                          : 'Chat freely, or ask about a file…'
                      }
                      rows={1}
                      value={draft}
                    />
                    {activeRun === null ? (
                      <button
                        className="composer-send"
                        disabled={selectedConversationId === null || !draft.trim() || isBusy}
                        title={isSubmittingMessage ? 'Sending…' : 'Send'}
                        type="submit"
                      >
                        <Icon path="M5 12h14M13 6l6 6-6 6" />
                      </button>
                    ) : (
                      <button
                        className="composer-stop"
                        disabled={isCancellingRun}
                        onClick={() => void cancelActiveRun()}
                        type="button"
                      >
                        {isCancellingRun ? 'Stopping…' : 'Stop'}
                      </button>
                    )}
                  </div>
                </form>
              </div>
            </div>
          </section>

          <aside className="attn">
            <div className="attn-header">Referenced in this chat</div>
            <p className="chat-context-sub">
              Files and actions this conversation has touched will appear here.
            </p>
            <div className="ctx-file">
              <div className="ctx-file-icon">
                <Icon path="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6" />
              </div>
              <div>
                <div className="ctx-file-name">No attachments yet</div>
                <div className="ctx-file-meta">Placeholder</div>
              </div>
            </div>
            <div className="ctx-action-btn">Turn this chat into an automation</div>
          </aside>
        </div>

        <div className={`view${activeView === 'activity' ? ' active' : ''}`}>
          <section className="center">
            <div className="center-header">
              <div className="center-title">Today</div>
              <div className="center-sub">
                Everything your agent has done, is doing, or is about to do.
              </div>
            </div>
            <div className="placeholder-banner">
              Activity feed is a visual preview. Live entries will come from Run events later.
            </div>
            <div className="filters">
              <div className="filter-chip active">All</div>
              <div className="filter-chip">Working</div>
              <div className="filter-chip">Waiting</div>
              <div className="filter-chip">Failed</div>
              <div className="filter-chip">Done</div>
            </div>
            <div className="log">
              <div className="log-day">SAMPLE · NOT LIVE DATA</div>
              <div className="entry">
                <div className="entry-time">—</div>
                <div className="entry-icon info">
                  <Icon path="M12 8v4M12 16h.01" />
                </div>
                <div className="entry-body">
                  <div className="entry-title">
                    No activity feed yet — use <b>Chat</b> for live runs
                  </div>
                  <div className="entry-detail">
                    When Automations land, their timelines will show up here.
                  </div>
                  <div className="entry-tag">placeholder</div>
                </div>
                <div className="entry-actions">
                  <span className="entry-action-link">Details</span>
                </div>
              </div>
            </div>
            <div className="composer">
              <div className="composer-box">
                <input disabled placeholder="Give asAgent a new task… (coming soon)" type="text" />
                <button className="composer-send" disabled type="button">
                  <Icon path="M5 12h14M13 6l6 6-6 6" />
                </button>
              </div>
              <div className="composer-note">
                One-shot tasks will live here. Prefer a back-and-forth discussion?{' '}
                <button
                  className="composer-link"
                  onClick={() => setActiveView('chat')}
                  type="button"
                >
                  Go to Chat →
                </button>
              </div>
            </div>
          </section>

          <aside className="attn">
            <div className="attn-tabs">
              <button
                className={`attn-tab${activityTab === 'approvals' ? ' active' : ''}`}
                onClick={() => setActivityTab('approvals')}
                type="button"
              >
                Approvals <span className="mini-badge">0</span>
              </button>
              <button
                className={`attn-tab${activityTab === 'schedule' ? ' active' : ''}`}
                onClick={() => setActivityTab('schedule')}
                type="button"
              >
                Schedule
              </button>
            </div>
            <div className={`tab-panel${activityTab === 'approvals' ? ' active' : ''}`}>
              <div className="attn-sub-row">Your agent stops here until you decide.</div>
              <div className="attn-list">
                <div className="attn-card">
                  <div className="attn-card-head">
                    <div className="attn-card-title">No approvals waiting</div>
                    <div className="attn-kind permission">placeholder</div>
                  </div>
                  <div className="attn-card-body">
                    Permission prompts and draft reviews will appear in this panel.
                  </div>
                  <div className="attn-actions">
                    <div className="btn btn-approve">Allow</div>
                    <div className="btn btn-review">Review</div>
                  </div>
                </div>
              </div>
            </div>
            <div className={`tab-panel${activityTab === 'schedule' ? ' active' : ''}`}>
              <div className="attn-divider">Later today</div>
              <div className="sched-item">
                <div className="sched-time">—</div>
                <div className="sched-name">
                  No scheduled items yet <b>(placeholder)</b>
                </div>
              </div>
            </div>
          </aside>
        </div>

        <div className={`view${activeView === 'privacy' ? ' active' : ''}`}>
          <section className="center">
            <div className="center-header">
              <div className="center-title">Privacy & Permissions</div>
              <div className="center-sub">Everything asAgent can see, and who has touched it.</div>
            </div>
            <div className="privacy-banner">
              <Icon path="M12 2 3 6v6c0 5 4 8.5 9 10 5-1.5 9-5 9-10V6l-9-4Z" />
              {usesExternalModel
                ? 'External model enabled. Conversation content and tool results needed for a request may be sent to the selected provider.'
                : 'All processing stays on this device. No conversation content is sent to an external model provider.'}
            </div>
            <div className="placeholder-banner">
              Permission rows below are sample layout only. Revoke / grant is not wired yet.
            </div>
            <div className="privacy-list">
              <div className="perm-row">
                <div className="perm-icon">
                  <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <rect height="16" rx="2" width="18" x="3" y="4" />
                    <path d="M3 9h18" />
                  </svg>
                </div>
                <div className="perm-body">
                  <div className="perm-title">
                    Workspace filesystem <span className="perm-scope">read / write</span>
                  </div>
                  <div className="perm-meta">Placeholder · tools will respect configured paths</div>
                </div>
                <div className="perm-revoke">Revoke</div>
              </div>
              <div className="perm-row">
                <div className="perm-icon">
                  <Icon path="M4 4h16v16H4zM4 8h16M8 4v16" />
                </div>
                <div className="perm-body">
                  <div className="perm-title">
                    Mail <span className="perm-scope">not connected</span>
                  </div>
                  <div className="perm-meta">Placeholder connector</div>
                  <div className="perm-flag">Not implemented in this build</div>
                </div>
                <div className="perm-revoke">Revoke</div>
              </div>
            </div>
            <div className="privacy-history">
              <div className="privacy-history-title">Access history</div>
              <div className="hist-row">
                <div className="hist-time">—</div>
                <div>No access history recorded yet (placeholder).</div>
              </div>
            </div>
          </section>
          <aside className="attn">
            <div className="attn-header">At a glance</div>
            <div className="stat-card">
              <div className="stat-row">
                <span className="stat-label">Apps connected</span>
                <span className="stat-value">0</span>
              </div>
              <div className="stat-row">
                <span className="stat-label">Outside default scope</span>
                <span className="stat-value">0</span>
              </div>
              <div className="stat-row">
                <span className="stat-label">Needs reconnecting</span>
                <span className="stat-value">0</span>
              </div>
              <div className="stat-row">
                <span className="stat-label">External model access</span>
                <span className={`stat-value${usesExternalModel ? ' warn' : ''}`}>
                  {usesExternalModel ? 'Enabled' : 'Off'}
                </span>
              </div>
            </div>
            <div className="trust-note">
              asAgent keeps tokens in Electron Main and never puts secrets in the renderer, URL, or
              logs. Permission management UI will plug into that policy later.
            </div>
          </aside>
        </div>

        <div className={`view${activeView === 'scheduled' ? ' active' : ''}`}>
          {renderPlaceholderView('Scheduled', 'Recurring and time-based agent jobs.')}
        </div>
        <div className={`view${activeView === 'automations' ? ' active' : ''}`}>
          {renderPlaceholderView('Automations', 'Saved workflows your agent can run.')}
        </div>
        <div className={`view${activeView === 'history' ? ' active' : ''}`}>
          {renderPlaceholderView('History', 'Longer-term activity and audit trail.')}
        </div>
        <div className={`view${activeView === 'files' ? ' active' : ''}`}>
          {renderPlaceholderView('Files & Folders', 'Local folders your agent may access.')}
        </div>
        <div className={`view${activeView === 'mail' ? ' active' : ''}`}>
          {renderPlaceholderView('Mail', 'Email connector — not implemented yet.')}
        </div>
        <div className={`view${activeView === 'calendar' ? ' active' : ''}`}>
          {renderPlaceholderView('Calendar', 'Calendar connector — not implemented yet.')}
        </div>
        <div className={`view${activeView === 'add-app' ? ' active' : ''}`}>
          {renderPlaceholderView('Add app', 'Connect another local data source.')}
        </div>
        <div className={`view${activeView === 'preferences' ? ' active' : ''}`}>
          {renderPlaceholderView('Agent preferences', 'Model, safety, and desktop preferences.')}
        </div>
      </div>
    </div>
  )
}
