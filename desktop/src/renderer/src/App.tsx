import {
  type CSSProperties,
  type FormEvent,
  type PointerEvent,
  useCallback,
  useEffect,
  useRef,
  useState
} from 'react'
import ReactMarkdown from 'react-markdown'

import { TOOL_APPROVAL_BANNER_ACTIONS, type ToolApprovalDecision } from './tool_approval'

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
  currentLabel: string
  toolNames: string[]
  phase: 'live' | 'done'
  outcome: RunActivityOutcome | null
  startedAt: number
  endedAt: number | null
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

type WorkspaceSettingsStatus = {
  workspace_root: string
  additional_roots: string[]
  additional_files: string[]
}

type ActivityTab = 'approvals' | 'schedule'
type ScrollArea = 'threads' | 'messages'
type ResizableColumn = 'rail' | 'threads' | 'attention'
type DesktopLayout = {
  railWidth: number
  threadWidth: number
  attentionWidth: number
}

const TAVILY_SETTINGS_LOAD_ERROR = 'Tavily settings could not be loaded.'
const TAVILY_SETTINGS_UPDATE_ERROR = 'Tavily settings could not be updated.'
const TAVILY_API_KEY_REQUIRED = 'Enter a Tavily API key before saving.'
const TAVILY_DELETE_CONFIRM = 'Remove the saved Tavily API key and disable Tavily web search?'
const MODEL_SETTINGS_LOAD_ERROR = 'Model settings could not be loaded.'
const MODEL_SETTINGS_UPDATE_ERROR = 'Model settings could not be updated.'
const MODEL_SETTINGS_REQUIRED = 'Enter a model, base URL, and API key before saving.'
const MODEL_DELETE_CONFIRM = 'Remove the saved model configuration and API key?'
const DEFAULT_RAIL_WIDTH = 226
const COLLAPSED_RAIL_WIDTH = 56
const DEFAULT_THREAD_WIDTH = 210
const DEFAULT_ATTENTION_WIDTH = 300
const MIN_RAIL_WIDTH = 180
const MAX_RAIL_WIDTH = 360
const MIN_THREAD_WIDTH = 160
const MAX_THREAD_WIDTH = 360
const MIN_ATTENTION_WIDTH = 240
const MAX_ATTENTION_WIDTH = 460
const MIN_CHAT_CONTENT_WIDTH = 360
const MIN_CENTER_WIDTH = MIN_THREAD_WIDTH + MIN_CHAT_CONTENT_WIDTH
const DESKTOP_LAYOUT_STORAGE_KEY = 'asagent.desktop.layout.v1'

function defaultDesktopLayout(): DesktopLayout {
  return {
    railWidth: DEFAULT_RAIL_WIDTH,
    threadWidth: DEFAULT_THREAD_WIDTH,
    attentionWidth: DEFAULT_ATTENTION_WIDTH
  }
}

function storedDesktopLayout(): DesktopLayout {
  try {
    const stored = window.localStorage.getItem(DESKTOP_LAYOUT_STORAGE_KEY)
    if (stored === null) {
      return defaultDesktopLayout()
    }

    const value: unknown = JSON.parse(stored)
    if (typeof value !== 'object' || value === null || Array.isArray(value)) {
      return defaultDesktopLayout()
    }

    const layout = value as Record<string, unknown>
    const railWidth = layout['railWidth']
    const threadWidth = layout['threadWidth']
    const attentionWidth = layout['attentionWidth']
    if (
      !isLayoutWidth(railWidth, MIN_RAIL_WIDTH, MAX_RAIL_WIDTH) ||
      !isLayoutWidth(threadWidth, MIN_THREAD_WIDTH, MAX_THREAD_WIDTH) ||
      !isLayoutWidth(attentionWidth, MIN_ATTENTION_WIDTH, MAX_ATTENTION_WIDTH)
    ) {
      return defaultDesktopLayout()
    }

    return { railWidth, threadWidth, attentionWidth }
  } catch {
    return defaultDesktopLayout()
  }
}

function isLayoutWidth(value: unknown, minimum: number, maximum: number): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= minimum && value <= maximum
}

function saveDesktopLayout(layout: DesktopLayout): void {
  try {
    window.localStorage.setItem(DESKTOP_LAYOUT_STORAGE_KEY, JSON.stringify(layout))
  } catch {
    // Layout persistence is optional and must never block the chat UI.
  }
}

function conversationLabel(title: string | null): string {
  return title ?? 'New conversation'
}

function fileAccessSummary(settings: WorkspaceSettingsStatus): string {
  const label = (path: string, kind: 'File' | 'Folder'): string => {
    const name = path.split(/[\\/]/).filter(Boolean).at(-1) ?? path
    return `${kind}: ${name} — ${path}`
  }
  const paths = [
    ...settings.additional_roots.map((path) => label(path, 'Folder')),
    ...settings.additional_files.map((path) => label(path, 'File'))
  ]

  return paths.join(' · ')
}

function mcpServerNameFromToolId(toolId: string): string | null {
  const match = /^mcp:([a-z][a-z0-9-]{0,63}):[^:]+:[0-9a-f]+$/i.exec(toolId)
  return match?.[1] ?? null
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

function terminalActivityEntry(outcome: RunActivityOutcome): string {
  switch (outcome) {
    case 'completed':
      return 'Answered'
    case 'failed':
      return 'Run failed'
    case 'cancelled':
      return 'Stopped'
    case 'limit':
      return 'Reached the safety limit'
  }
}

function runActivityStatus(eventType: string): string | null {
  switch (eventType) {
    case 'model.requested':
      return 'Thinking…'
    case 'tool.requested':
      return 'Using a tool…'
    default:
      return null
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
  const elapsed = formatElapsed(activity.startedAt, activity.endedAt)
  const toolSummary =
    activity.toolNames.length === 0
      ? null
      : activity.toolNames.length === 1
        ? `Used ${activity.toolNames[0]}`
        : `Used ${activity.toolNames.length} tools`

  const details = [elapsed, toolSummary].filter((detail): detail is string => detail !== null)

  switch (activity.outcome) {
    case 'failed':
      return ['Failed', ...details].join(' · ')
    case 'cancelled':
      return ['Stopped', ...details].join(' · ')
    case 'limit':
      return ['Stopped for safety', ...details].join(' · ')
    case 'completed':
    default:
      return ['Worked', ...details].join(' · ')
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
  const [pendingApproval, setPendingApproval] = useState<ToolApproval | null>(null)
  const [isDecidingApproval, setIsDecidingApproval] = useState(false)
  const [activeView, setActiveView] = useState<AppView>('chat')
  const [activityTab, setActivityTab] = useState<ActivityTab>('approvals')
  const [tavilySettings, setTavilySettings] = useState<TavilySettingsStatus | null>(null)
  const [tavilyLoadError, setTavilyLoadError] = useState<string | null>(null)
  const [tavilyActionError, setTavilyActionError] = useState<string | null>(null)
  const [tavilyApiKey, setTavilyApiKey] = useState('')
  const [showTavilyKeyInput, setShowTavilyKeyInput] = useState(false)
  const [isReplacingTavilyKey, setIsReplacingTavilyKey] = useState(false)
  const [isTavilyLoading, setIsTavilyLoading] = useState(true)
  const [isTavilyBusy, setIsTavilyBusy] = useState(false)
  const [modelSettings, setModelSettings] = useState<ModelSettingsStatus | null>(null)
  const [modelLoadError, setModelLoadError] = useState<string | null>(null)
  const [modelActionError, setModelActionError] = useState<string | null>(null)
  const [restartRequested, setRestartRequested] = useState(false)
  const [isRestarting, setIsRestarting] = useState(false)
  const [modelName, setModelName] = useState('')
  const [modelBaseUrl, setModelBaseUrl] = useState('')
  const [modelApiKey, setModelApiKey] = useState('')
  const [isModelLoading, setIsModelLoading] = useState(true)
  const [isModelBusy, setIsModelBusy] = useState(false)
  const [workspaceSettings, setWorkspaceSettings] = useState<WorkspaceSettingsStatus | null>(null)
  const [isWorkspaceLoading, setIsWorkspaceLoading] = useState(true)
  const [isWorkspaceBusy, setIsWorkspaceBusy] = useState(false)
  const [visibleScrollbar, setVisibleScrollbar] = useState<ScrollArea | null>(null)
  const [desktopLayout, setDesktopLayout] = useState<DesktopLayout>(storedDesktopLayout)
  const [isRailCollapsed, setIsRailCollapsed] = useState(false)
  const [resizingColumn, setResizingColumn] = useState<ResizableColumn | null>(null)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const scrollbarHideTimerRef = useRef<number | null>(null)
  const desktopLayoutRef = useRef(desktopLayout)
  const resizingColumnRef = useRef<ResizableColumn | null>(null)
  const railWidth = isRailCollapsed ? COLLAPSED_RAIL_WIDTH : desktopLayout.railWidth

  function revealScrollbar(area: ScrollArea): void {
    setVisibleScrollbar(area)

    if (scrollbarHideTimerRef.current !== null) {
      window.clearTimeout(scrollbarHideTimerRef.current)
    }

    scrollbarHideTimerRef.current = window.setTimeout(() => {
      setVisibleScrollbar(null)
      scrollbarHideTimerRef.current = null
    }, 700)
  }

  useEffect(() => {
    return () => {
      if (scrollbarHideTimerRef.current !== null) {
        window.clearTimeout(scrollbarHideTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    document.body.classList.toggle('is-resizing-columns', resizingColumn !== null)

    return () => {
      document.body.classList.remove('is-resizing-columns')
    }
  }, [resizingColumn])

  function beginColumnResize(column: ResizableColumn, event: PointerEvent<HTMLDivElement>): void {
    if (event.button !== 0) {
      return
    }

    event.preventDefault()
    resizingColumnRef.current = column
    setResizingColumn(column)
    window.addEventListener('pointermove', handleColumnResizeMove)
    window.addEventListener('pointerup', endColumnResize)
    window.addEventListener('pointercancel', endColumnResize)
    window.addEventListener('blur', endColumnResize)
  }

  const handleColumnResizeMove = useCallback(
    (event: globalThis.PointerEvent): void => {
      const column = resizingColumnRef.current
      if (column === null) {
        return
      }

      const attentionIsVisible = window.innerWidth > 1100
      const railIsVisible = window.innerWidth > 820
      const layout = desktopLayoutRef.current
      const currentRailWidth = isRailCollapsed ? COLLAPSED_RAIL_WIDTH : layout.railWidth
      const requestedWidth =
        column === 'rail'
          ? event.clientX
          : column === 'threads'
            ? event.clientX - currentRailWidth
            : window.innerWidth - event.clientX
      const otherColumnWidth =
        column === 'rail' && attentionIsVisible
          ? layout.attentionWidth
          : column === 'attention'
            ? railIsVisible
              ? currentRailWidth
              : 0
            : 0
      const minimumWidth =
        column === 'rail'
          ? MIN_RAIL_WIDTH
          : column === 'threads'
            ? MIN_THREAD_WIDTH
            : MIN_ATTENTION_WIDTH
      const maximumWidth = Math.min(
        column === 'rail'
          ? MAX_RAIL_WIDTH
          : column === 'threads'
            ? MAX_THREAD_WIDTH
            : MAX_ATTENTION_WIDTH,
        column === 'threads'
          ? window.innerWidth -
              (railIsVisible ? currentRailWidth : 0) -
              (attentionIsVisible ? layout.attentionWidth : 0) -
              MIN_CHAT_CONTENT_WIDTH
          : window.innerWidth - otherColumnWidth - MIN_CENTER_WIDTH
      )
      const width = Math.max(minimumWidth, Math.min(requestedWidth, maximumWidth))
      const nextLayout = {
        ...desktopLayoutRef.current,
        ...(column === 'rail'
          ? { railWidth: width }
          : column === 'threads'
            ? { threadWidth: width }
            : { attentionWidth: width })
      }
      desktopLayoutRef.current = nextLayout
      setDesktopLayout(nextLayout)
    },
    [isRailCollapsed]
  )

  const endColumnResize = useCallback((): void => {
    if (resizingColumnRef.current === null) {
      return
    }

    resizingColumnRef.current = null
    saveDesktopLayout(desktopLayoutRef.current)
    setResizingColumn(null)
    window.removeEventListener('pointermove', handleColumnResizeMove)
    window.removeEventListener('pointerup', endColumnResize)
    window.removeEventListener('pointercancel', endColumnResize)
    window.removeEventListener('blur', endColumnResize)
  }, [handleColumnResizeMove])

  useEffect(() => {
    return () => {
      window.removeEventListener('pointermove', handleColumnResizeMove)
      window.removeEventListener('pointerup', endColumnResize)
      window.removeEventListener('pointercancel', endColumnResize)
      window.removeEventListener('blur', endColumnResize)
    }
  }, [endColumnResize, handleColumnResizeMove])

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
    let cancelled = false

    async function loadWorkspaceSettings(): Promise<void> {
      if (selectedConversationId === null) {
        setWorkspaceSettings(null)
        setIsWorkspaceLoading(false)
        return
      }

      setIsWorkspaceLoading(true)
      try {
        const status = await window.desktop.getConversationFileAccess(selectedConversationId)
        if (!cancelled) {
          setWorkspaceSettings(status)
        }
      } catch {
        if (!cancelled) {
          setWorkspaceSettings(null)
        }
      } finally {
        if (!cancelled) {
          setIsWorkspaceLoading(false)
        }
      }
    }

    void loadWorkspaceSettings()
    return () => {
      cancelled = true
    }
  }, [selectedConversationId])

  useEffect(() => {
    let cancelled = false

    async function loadModelSettings(): Promise<void> {
      setIsModelLoading(true)
      try {
        const status = await window.desktop.getModelSettings()
        if (!cancelled) {
          setModelSettings(status)
          setModelName(status.model ?? '')
          setModelBaseUrl(status.base_url ?? '')
          setModelLoadError(null)
        }
      } catch {
        if (!cancelled) {
          setModelLoadError(MODEL_SETTINGS_LOAD_ERROR)
        }
      } finally {
        if (!cancelled) {
          setIsModelLoading(false)
        }
      }
    }

    void loadModelSettings()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function loadTavilySettings(): Promise<void> {
      setIsTavilyLoading(true)

      try {
        const status = await window.desktop.getTavilySettings()

        if (!cancelled) {
          setTavilySettings(status)
          setTavilyLoadError(null)
        }
      } catch {
        if (!cancelled) {
          setTavilyLoadError(TAVILY_SETTINGS_LOAD_ERROR)
        }
      } finally {
        if (!cancelled) {
          setIsTavilyLoading(false)
        }
      }
    }

    void loadTavilySettings()

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
      recordRunEvent(update.runId, update.event.event_type)

      const outcome = runActivityOutcome(update.event.event_type)
      if (outcome === null) {
        return
      }

      setPendingApproval((current) => (current?.run_id === update.runId ? null : current))
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
      setRunActivityStatus(error.runId, 'Run connection lost.')
      finishRunActivity(error.runId, 'failed')
      setErrorMessage(error.message)
    })

    const removeApprovalListener = window.desktop.onToolApprovalRequested((approval) => {
      setPendingApproval(approval)
      setIsDecidingApproval(false)
      setRunActivityTool(approval.run_id, approval.display_name)
      setRunActivityStatus(approval.run_id, `Waiting for approval for ${approval.display_name}…`)
    })

    const removeApprovalErrorListener = window.desktop.onToolApprovalError((error) => {
      setErrorMessage(error.message)
    })

    return () => {
      removeEventListener()
      removeErrorListener()
      removeApprovalListener()
      removeApprovalErrorListener()
    }
    // The event handlers below only close over React state setters and stable helpers.
    // Re-subscribing on every render would risk a gap in the single active Run stream.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedConversationId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [
    messages,
    pendingApproval?.approval_id,
    runActivity?.entries.length,
    runActivity?.phase,
    selectedConversationId
  ])

  const selectedConversation = conversations.find(
    (conversation) => conversation.conversation_id === selectedConversationId
  )
  const visibleMessages = selectedConversationId === null ? [] : messages
  const visibleApproval =
    pendingApproval?.conversation_id === selectedConversationId ? pendingApproval : null
  const visibleApprovalServer =
    visibleApproval === null ? null : mcpServerNameFromToolId(visibleApproval.tool_id)
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

  function openAssistantLink(href: string | undefined): void {
    if (href === undefined) {
      return
    }

    void window.desktop.openExternalLink(href).catch(() => {
      setErrorMessage('The link could not be opened.')
    })
  }

  function setRunActivityStatus(runId: string, currentLabel: string): void {
    setRunActivity((current) => {
      if (current === null || current.runId !== runId) {
        return current
      }

      if (current.currentLabel === currentLabel) {
        return current
      }

      return {
        ...current,
        currentLabel
      }
    })
  }

  function setRunActivityTool(runId: string, toolName: string): void {
    setRunActivity((current) => {
      if (current === null || current.runId !== runId) {
        return current
      }

      if (current.toolNames.includes(toolName)) {
        return current
      }

      return {
        ...current,
        toolNames: [...current.toolNames, toolName]
      }
    })
  }

  function recordRunEvent(runId: string, eventType: string): void {
    const outcome = runActivityOutcome(eventType)
    if (outcome !== null) {
      finishRunActivity(runId, outcome)
      return
    }

    const currentLabel = runActivityStatus(eventType)
    if (currentLabel !== null) {
      setRunActivityStatus(runId, currentLabel)
    }

    if (eventType === 'tool.completed') {
      setRunActivity((current) => {
        if (current === null || current.runId !== runId) {
          return current
        }

        const toolName = current.toolNames.at(-1) ?? 'a tool'
        const entry = `Used ${toolName}`

        return {
          ...current,
          entries: current.entries.includes(entry) ? current.entries : [...current.entries, entry],
          currentLabel: 'Thinking…'
        }
      })
    }
  }

  function finishRunActivity(runId: string, outcome: RunActivityOutcome): void {
    setRunActivity((current) => {
      if (current === null || current.runId !== runId) {
        return current
      }

      const entry = terminalActivityEntry(outcome)
      return {
        ...current,
        entries: current.entries.includes(entry) ? current.entries : [...current.entries, entry],
        currentLabel: entry,
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
        entries: ['Started'],
        currentLabel: 'Starting…',
        toolNames: [],
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
    setRunActivityStatus(activeRun.runId, 'Stopping…')

    try {
      await window.desktop.cancelRun(activeRun.runId)
    } catch {
      setIsCancellingRun(false)
      setErrorMessage('Cancellation request failed.')
    }
  }

  async function decidePendingApproval(decision: ToolApprovalDecision): Promise<void> {
    const approval = pendingApproval
    if (approval === null || isDecidingApproval) {
      return
    }

    setIsDecidingApproval(true)
    setErrorMessage(null)

    try {
      await window.desktop.decideToolApproval(approval.approval_id, decision)
      setRunActivityStatus(
        approval.run_id,
        decision === 'deny' ? 'Tool denied. Continuing…' : `Using ${approval.display_name}…`
      )
      setPendingApproval(null)
    } catch {
      setErrorMessage('Tool approval decision could not be sent.')
    } finally {
      setIsDecidingApproval(false)
    }
  }

  function applyTavilyStatus(status: TavilySettingsStatus): void {
    setTavilySettings(status)
    setTavilyActionError(null)
    setRestartRequested(true)
    setTavilyApiKey('')
    setShowTavilyKeyInput(false)
    setIsReplacingTavilyKey(false)
  }

  async function handleTavilyToggle(enabled: boolean): Promise<void> {
    if (isTavilyBusy || tavilySettings === null) {
      return
    }

    setTavilyActionError(null)

    if (!enabled) {
      setIsTavilyBusy(true)
      try {
        const status = await window.desktop.disableTavily()
        applyTavilyStatus(status)
      } catch {
        setTavilyActionError(TAVILY_SETTINGS_UPDATE_ERROR)
      } finally {
        setIsTavilyBusy(false)
      }
      return
    }

    if (tavilySettings.api_key_saved) {
      setIsTavilyBusy(true)
      try {
        const status = await window.desktop.enableTavily()
        applyTavilyStatus(status)
      } catch {
        setTavilyActionError(TAVILY_SETTINGS_UPDATE_ERROR)
      } finally {
        setIsTavilyBusy(false)
      }
      return
    }

    setShowTavilyKeyInput(true)
    setIsReplacingTavilyKey(false)
  }

  async function handleSaveTavilyKey(): Promise<void> {
    if (isTavilyBusy) {
      return
    }

    setTavilyActionError(null)

    if (!tavilyApiKey.trim()) {
      setTavilyActionError(TAVILY_API_KEY_REQUIRED)
      setTavilyApiKey('')
      return
    }

    setIsTavilyBusy(true)
    try {
      const status = await window.desktop.enableTavily(tavilyApiKey.trim())
      applyTavilyStatus(status)
    } catch {
      setTavilyActionError(TAVILY_SETTINGS_UPDATE_ERROR)
      setTavilyApiKey('')
    } finally {
      setIsTavilyBusy(false)
    }
  }

  function handleStartReplaceTavilyKey(): void {
    if (isTavilyBusy) {
      return
    }

    setTavilyActionError(null)
    setTavilyApiKey('')
    setShowTavilyKeyInput(true)
    setIsReplacingTavilyKey(true)
  }

  async function handleRemoveTavilyKey(): Promise<void> {
    if (isTavilyBusy || tavilySettings === null || !tavilySettings.api_key_saved) {
      return
    }

    if (!window.confirm(TAVILY_DELETE_CONFIRM)) {
      return
    }

    setIsTavilyBusy(true)
    setTavilyActionError(null)

    try {
      const status = await window.desktop.deleteTavily()
      applyTavilyStatus(status)
    } catch {
      setTavilyActionError(TAVILY_SETTINGS_UPDATE_ERROR)
      setTavilyApiKey('')
    } finally {
      setIsTavilyBusy(false)
    }
  }

  function applyModelStatus(status: ModelSettingsStatus): void {
    setModelSettings(status)
    setModelName(status.model ?? '')
    setModelBaseUrl(status.base_url ?? '')
    setModelApiKey('')
    setModelActionError(null)
    setRestartRequested(true)
  }

  async function handleSaveModelSettings(): Promise<void> {
    if (isModelBusy) {
      return
    }
    if (
      !modelName.trim() ||
      !modelBaseUrl.trim() ||
      (!modelSettings?.api_key_saved && !modelApiKey.trim())
    ) {
      setModelActionError(MODEL_SETTINGS_REQUIRED)
      return
    }

    setIsModelBusy(true)
    setModelActionError(null)
    try {
      applyModelStatus(
        await window.desktop.saveModelSettings({
          model: modelName.trim(),
          baseUrl: modelBaseUrl.trim(),
          ...(modelApiKey.trim() ? { apiKey: modelApiKey.trim() } : {})
        })
      )
    } catch {
      setModelActionError(MODEL_SETTINGS_UPDATE_ERROR)
      setModelApiKey('')
    } finally {
      setIsModelBusy(false)
    }
  }

  async function handleRemoveModelSettings(): Promise<void> {
    if (isModelBusy || modelSettings === null || !modelSettings.configured) {
      return
    }
    if (!window.confirm(MODEL_DELETE_CONFIRM)) {
      return
    }

    setIsModelBusy(true)
    setModelActionError(null)
    try {
      applyModelStatus(await window.desktop.deleteModelSettings())
    } catch {
      setModelActionError(MODEL_SETTINGS_UPDATE_ERROR)
    } finally {
      setIsModelBusy(false)
    }
  }

  async function handleAddWorkspacePath(): Promise<void> {
    if (isWorkspaceBusy || workspaceSettings === null || selectedConversationId === null) {
      return
    }

    const selectedPath = await window.desktop.chooseWorkspacePath()
    if (
      selectedPath === null ||
      (selectedPath.kind === 'directory' &&
        workspaceSettings.additional_roots.includes(selectedPath.path)) ||
      (selectedPath.kind === 'file' &&
        workspaceSettings.additional_files.includes(selectedPath.path))
    ) {
      return
    }

    setIsWorkspaceBusy(true)
    try {
      setWorkspaceSettings(
        await window.desktop.saveConversationFileAccess(selectedConversationId, {
          additionalFiles:
            selectedPath.kind === 'file'
              ? [...workspaceSettings.additional_files, selectedPath.path]
              : workspaceSettings.additional_files,
          additionalRoots:
            selectedPath.kind === 'directory'
              ? [...workspaceSettings.additional_roots, selectedPath.path]
              : workspaceSettings.additional_roots
        })
      )
    } catch {
      setErrorMessage('File access settings could not be updated.')
    } finally {
      setIsWorkspaceBusy(false)
    }
  }

  async function handleRestartApp(): Promise<void> {
    if (isRestarting) {
      return
    }

    setIsRestarting(true)
    try {
      await window.desktop.restartApp()
    } catch {
      setIsRestarting(false)
      setErrorMessage('asAgent could not restart automatically.')
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

      <div
        className={`app${isRailCollapsed ? ' rail-collapsed' : ''}${
          resizingColumn === null ? '' : ' is-resizing'
        }`}
        style={
          {
            '--rail-width': `${railWidth}px`,
            '--thread-width': `${desktopLayout.threadWidth}px`,
            '--attention-width': `${desktopLayout.attentionWidth}px`
          } as CSSProperties
        }
      >
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

        <div
          aria-label="Resize navigation panel"
          className="column-resizer column-resizer-left"
          onPointerDown={(event) => beginColumnResize('rail', event)}
          role="separator"
        />
        <div
          aria-label="Resize activity panel"
          className="column-resizer column-resizer-right"
          onPointerDown={(event) => beginColumnResize('attention', event)}
          role="separator"
        />

        <nav aria-label="Primary" className="rail" id="primary-sidebar">
          <div className="rail-control">
            <div className="rail-label">Agent</div>
            <button
              aria-controls="primary-sidebar"
              aria-expanded={!isRailCollapsed}
              aria-label={isRailCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              className="rail-toggle"
              onClick={() => setIsRailCollapsed((collapsed) => !collapsed)}
              title={isRailCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              type="button"
            >
              <svg
                aria-hidden="true"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <path d={isRailCollapsed ? 'm9 18 6-6-6-6' : 'm15 18-6-6 6-6'} />
              </svg>
            </button>
          </div>
          <div className="rail-section">
            <button
              className={railItemClass('chat')}
              onClick={() => setActiveView('chat')}
              type="button"
            >
              <Icon
                className="rail-icon"
                path="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"
              />
              <span className="rail-item-label">Chat</span>
            </button>
            <button
              className={railItemClass('activity')}
              onClick={() => setActiveView('activity')}
              type="button"
            >
              <Icon className="rail-icon" path="M13 2 3 14h7l-1 8 10-12h-7l1-8z" />
              <span className="rail-item-label">Activity</span>
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
              <span className="rail-item-label">Scheduled</span>
              <span className="rail-count">—</span>
            </button>
            <button
              className={railItemClass('automations')}
              onClick={() => setActiveView('automations')}
              type="button"
            >
              <Icon className="rail-icon" path="M4 5h16M4 12h10M4 19h13" />
              <span className="rail-item-label">Automations</span>
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
              <span className="rail-item-label">Privacy &amp; Permissions</span>
            </button>
            <button
              className={railItemClass('history')}
              onClick={() => setActiveView('history')}
              type="button"
            >
              <Icon className="rail-icon" path="M3 3v18h18M7 15l4-5 3 3 5-7" />
              <span className="rail-item-label">History</span>
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
              <span className="rail-item-label">Files &amp; Folders</span>
              <span className="status-dot pending" title="Not connected yet" />
            </button>
            <button
              className={railItemClass('mail')}
              onClick={() => setActiveView('mail')}
              type="button"
            >
              <Icon className="rail-icon" path="M4 4h16v16H4zM4 8h16M8 4v16" />
              <span className="rail-item-label">Mail</span>
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
              <span className="rail-item-label">Calendar</span>
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
              <span className="rail-item-label">+ Add app</span>
            </button>
          </div>

          <div className="rail-footer">
            <button
              className="rail-settings"
              onClick={() => setActiveView('preferences')}
              type="button"
            >
              <Icon path="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09A1.65 1.65 0 0 0 15 4.6a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
              <span className="rail-item-label">Agent preferences</span>
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
              <div
                className={`chat-threads${visibleScrollbar === 'threads' ? ' scrollbar-visible' : ''}`}
                onWheel={() => revealScrollbar('threads')}
              >
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
                      <div className="chat-thread-time">
                        {formatThreadTime(conversation.updated_at)}
                      </div>
                    </button>
                  ))
                )}
              </div>
              <div
                aria-label="Resize conversation list"
                className="chat-column-resizer"
                onPointerDown={(event) => beginColumnResize('threads', event)}
                role="separator"
              />

              <div className="chat-main">
                <div className="chat-thread-header">
                  <div className="chat-thread-header-title">
                    {selectedConversation
                      ? conversationLabel(selectedConversation.title)
                      : 'No conversation selected'}
                  </div>
                </div>

                {errorMessage ? <p className="chat-error">{errorMessage}</p> : null}

                <div
                  className={`chat-messages${visibleScrollbar === 'messages' ? ' scrollbar-visible' : ''}`}
                  onWheel={() => revealScrollbar('messages')}
                >
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
                                  className={`activity-details${
                                    activity.phase === 'live' ? ' is-live' : ''
                                  }`}
                                >
                                  {activity.phase === 'live' ? (
                                    <div aria-live="polite" className="activity-live">
                                      <span aria-hidden="true" className="activity-spinner" />
                                      <span>{activity.currentLabel}</span>
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
                                  {activity.phase === 'done' ? (
                                    <ul className="activity-list">
                                      {activity.entries.map((entry, index) => {
                                        return (
                                          <li
                                            className="activity-item"
                                            key={`${activity.runId}-${index}`}
                                          >
                                            <span aria-hidden="true" className="activity-item-dot">
                                              ✓
                                            </span>
                                            <span>{entry}</span>
                                          </li>
                                        )
                                      })}
                                    </ul>
                                  ) : null}
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
                                        <ReactMarkdown
                                          components={{
                                            a: ({ children, href }) => (
                                              <a
                                                href={href}
                                                onClick={(event) => {
                                                  event.preventDefault()
                                                  openAssistantLink(href)
                                                }}
                                                title="Open in your default browser"
                                              >
                                                {children}
                                              </a>
                                            )
                                          }}
                                        >
                                          {message.content}
                                        </ReactMarkdown>
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

                {visibleApproval !== null ? (
                  <div aria-label="Tool approval" className="tool-approval-banner" role="region">
                    <span className="tool-approval-kind">
                      {visibleApprovalServer === null ? 'Tool' : 'MCP'}
                    </span>
                    <p className="tool-approval-banner-copy">
                      <span className="tool-approval-banner-title">
                        Allow {visibleApproval.display_name}?
                      </span>
                      {visibleApprovalServer !== null ? (
                        <span className="tool-approval-banner-source">{visibleApprovalServer}</span>
                      ) : null}
                    </p>
                    <div className="tool-approval-banner-actions">
                      {TOOL_APPROVAL_BANNER_ACTIONS.map((action) => (
                        <button
                          className={action.className}
                          disabled={isDecidingApproval}
                          key={action.decision}
                          onClick={() => void decidePendingApproval(action.decision)}
                          type="button"
                        >
                          {action.label}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}

                <form className="chat-composer" onSubmit={(event) => void submitMessage(event)}>
                  <div className="chat-composer-box">
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
                    <div className="chat-composer-footer">
                      <button
                        aria-label="Add a file or folder to local file access"
                        className="chat-attach-btn"
                        disabled={
                          selectedConversationId === null ||
                          isWorkspaceLoading ||
                          isWorkspaceBusy ||
                          workspaceSettings === null
                        }
                        onClick={() => void handleAddWorkspacePath()}
                        title="Add a file or folder to local file access"
                        type="button"
                      >
                        <Icon path="M12 5v14m-7-7h14" />
                      </button>
                      <span
                        className="chat-composer-status"
                        title={
                          workspaceSettings === null
                            ? undefined
                            : fileAccessSummary(workspaceSettings)
                        }
                      >
                        {activeRun === null
                          ? workspaceSettings === null ||
                            workspaceSettings.additional_roots.length +
                              workspaceSettings.additional_files.length ===
                              0
                            ? 'Add a file or folder to this conversation'
                            : fileAccessSummary(workspaceSettings)
                          : 'asAgent is working'}
                      </span>
                      {activeRun === null ? (
                        <button
                          aria-label={isSubmittingMessage ? 'Sending' : 'Send message'}
                          className="composer-send"
                          disabled={selectedConversationId === null || !draft.trim() || isBusy}
                          title={isSubmittingMessage ? 'Sending…' : 'Send message'}
                          type="submit"
                        >
                          <Icon path="M12 19V5m-6 6 6-6 6 6" />
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
          <section className="center">
            <div className="center-header settings-page-header">
              <div>
                <div className="settings-header-eyebrow">Preferences</div>
                <div className="center-title">Agent preferences</div>
                <div className="center-sub">Manage model access, tools, and local file scope.</div>
              </div>
              <div className={`settings-mode-card${usesExternalModel ? ' external' : ''}`}>
                <span>Processing</span>
                <strong>{usesExternalModel ? 'External model' : 'Local mode'}</strong>
                <small>
                  {usesExternalModel
                    ? 'Conversation content may leave this device.'
                    : 'No model data is sent externally.'}
                </small>
              </div>
            </div>

            <div className="settings-panel">
              <section className="settings-section">
                <div className="settings-section-header">
                  <div>
                    <div className="settings-section-eyebrow">Model &amp; privacy</div>
                    <div className="settings-section-title">Model provider</div>
                    <p className="settings-section-copy">
                      Configure one OpenAI-compatible provider for asAgent. The API key stays in
                      your system credential store and is never shown here.
                    </p>
                  </div>
                  <span
                    className={`settings-state${modelSettings?.configured ? ' configured' : ''}`}
                  >
                    {modelSettings?.configured ? 'Configured' : 'Not configured'}
                  </span>
                </div>

                {isModelLoading ? (
                  <p className="settings-section-status">Loading model settings…</p>
                ) : null}
                {modelLoadError !== null ? (
                  <p className="settings-section-error">{modelLoadError}</p>
                ) : null}
                {!isModelLoading && modelLoadError === null ? (
                  <div className="settings-key-form">
                    <label className="settings-field-label" htmlFor="model-name">
                      Model
                    </label>
                    <input
                      className="settings-text-input"
                      disabled={isModelBusy}
                      id="model-name"
                      onChange={(event) => setModelName(event.target.value)}
                      placeholder="deepseek-v4-flash"
                      spellCheck={false}
                      value={modelName}
                    />
                    <label className="settings-field-label" htmlFor="model-base-url">
                      OpenAI-compatible base URL
                    </label>
                    <input
                      className="settings-text-input"
                      disabled={isModelBusy}
                      id="model-base-url"
                      onChange={(event) => setModelBaseUrl(event.target.value)}
                      placeholder="https://api.deepseek.com/"
                      spellCheck={false}
                      value={modelBaseUrl}
                    />
                    <label className="settings-field-label" htmlFor="model-api-key">
                      {modelSettings?.api_key_saved ? 'Replace API key' : 'API key'}
                    </label>
                    <input
                      autoComplete="off"
                      className="settings-text-input"
                      disabled={isModelBusy}
                      id="model-api-key"
                      onChange={(event) => setModelApiKey(event.target.value)}
                      placeholder={
                        modelSettings?.api_key_saved ? 'Enter a new API key' : 'Enter API key'
                      }
                      spellCheck={false}
                      type="password"
                      value={modelApiKey}
                    />
                    <div className="settings-card-actions">
                      <button
                        className="settings-button settings-button-primary"
                        disabled={isModelBusy}
                        onClick={() => {
                          void handleSaveModelSettings()
                        }}
                        type="button"
                      >
                        Save model settings
                      </button>
                      {modelSettings?.configured ? (
                        <button
                          className="settings-button settings-button-danger"
                          disabled={isModelBusy}
                          onClick={() => {
                            void handleRemoveModelSettings()
                          }}
                          type="button"
                        >
                          Remove model settings
                        </button>
                      ) : null}
                    </div>
                  </div>
                ) : null}
                {modelActionError !== null ? (
                  <p className="settings-section-error">{modelActionError}</p>
                ) : null}
                <p className="settings-section-placeholder">
                  Anthropic and Gemini providers are not available yet.
                </p>
              </section>

              <section className="settings-section">
                <div className="settings-section-header">
                  <div>
                    <div className="settings-section-eyebrow">Connected tool</div>
                    <div className="settings-section-title">Tavily Web Search</div>
                    <p className="settings-section-copy">
                      Tavily lets asAgent search the web through a configured MCP server. Your API
                      key is stored in the macOS Keychain and is never shown in this window.
                    </p>
                  </div>
                  <label className="settings-toggle">
                    <input
                      checked={tavilySettings?.enabled ?? false}
                      disabled={isTavilyBusy || isTavilyLoading || tavilySettings === null}
                      onChange={(event) => {
                        void handleTavilyToggle(event.target.checked)
                      }}
                      type="checkbox"
                    />
                    <span aria-hidden="true" className="settings-toggle-track" />
                  </label>
                </div>

                {isTavilyLoading ? (
                  <p className="settings-section-status">Loading Tavily settings…</p>
                ) : null}

                {tavilyLoadError !== null ? (
                  <p className="settings-section-error">{tavilyLoadError}</p>
                ) : null}

                {!isTavilyLoading && tavilyLoadError === null && tavilySettings !== null ? (
                  <>
                    <p className="settings-section-status">
                      {tavilySettings.enabled
                        ? 'Tavily web search is enabled.'
                        : tavilySettings.api_key_saved
                          ? 'Tavily is disabled. Your API key is still saved.'
                          : 'Tavily is not configured.'}
                    </p>

                    {showTavilyKeyInput ? (
                      <div className="settings-key-form">
                        <label className="settings-field-label" htmlFor="tavily-api-key">
                          Tavily API key
                        </label>
                        <input
                          autoComplete="off"
                          className="settings-text-input"
                          disabled={isTavilyBusy}
                          id="tavily-api-key"
                          onChange={(event) => setTavilyApiKey(event.target.value)}
                          placeholder="tvly-..."
                          spellCheck={false}
                          type="password"
                          value={tavilyApiKey}
                        />
                        <div className="settings-card-actions">
                          <button
                            className="settings-button settings-button-primary"
                            disabled={isTavilyBusy}
                            onClick={() => {
                              void handleSaveTavilyKey()
                            }}
                            type="button"
                          >
                            {isReplacingTavilyKey ? 'Save new API key' : 'Save and enable'}
                          </button>
                          {isReplacingTavilyKey ? (
                            <button
                              className="settings-button settings-button-secondary"
                              disabled={isTavilyBusy}
                              onClick={() => {
                                setShowTavilyKeyInput(false)
                                setIsReplacingTavilyKey(false)
                                setTavilyApiKey('')
                                setTavilyActionError(null)
                              }}
                              type="button"
                            >
                              Cancel
                            </button>
                          ) : null}
                        </div>
                      </div>
                    ) : null}

                    {tavilySettings.api_key_saved && !showTavilyKeyInput ? (
                      <div className="settings-card-actions">
                        <button
                          className="settings-button settings-button-secondary"
                          disabled={isTavilyBusy}
                          onClick={handleStartReplaceTavilyKey}
                          type="button"
                        >
                          Replace API key
                        </button>
                        <button
                          className="settings-button settings-button-danger"
                          disabled={isTavilyBusy}
                          onClick={() => {
                            void handleRemoveTavilyKey()
                          }}
                          type="button"
                        >
                          Remove saved API key
                        </button>
                      </div>
                    ) : null}
                  </>
                ) : null}

                {tavilyActionError !== null ? (
                  <p className="settings-section-error">{tavilyActionError}</p>
                ) : null}
              </section>
            </div>
          </section>

          <aside className="attn">
            <div className="attn-header">Settings guide</div>
            <div className="settings-guide">
              <section className="settings-guide-item">
                <div className="settings-guide-title">Your credentials</div>
                <p>API keys are stored in the system Keychain and are never displayed here.</p>
              </section>
              <section className="settings-guide-item">
                <div className="settings-guide-title">File access</div>
                <p>Extra paths apply only to the selected conversation and remain read-only.</p>
              </section>
              <section className="settings-guide-item restart">
                <div className="settings-guide-title">Restart required</div>
                <p>Model and Tavily changes take effect after restarting asAgent.</p>
              </section>
            </div>
          </aside>
        </div>
      </div>
      {restartRequested ? (
        <div aria-modal="true" className="restart-modal-backdrop" role="dialog">
          <section aria-labelledby="restart-modal-title" className="restart-modal">
            <div className="restart-modal-eyebrow">Settings saved</div>
            <h2 id="restart-modal-title">Restart asAgent now?</h2>
            <p>
              Your changes are saved. Restarting applies the updated model and integrations to a new
              Sidecar.
            </p>
            <div className="restart-modal-actions">
              <button
                className="settings-button settings-button-secondary"
                disabled={isRestarting}
                onClick={() => setRestartRequested(false)}
                type="button"
              >
                Later
              </button>
              <button
                autoFocus
                className="settings-button settings-button-primary"
                disabled={isRestarting}
                onClick={() => {
                  void handleRestartApp()
                }}
                type="button"
              >
                {isRestarting ? 'Restarting…' : 'Restart now'}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  )
}
