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
import remarkGfm from 'remark-gfm'

import {
  findSavedAutomation,
  isAwaitingAutomationInput,
  plannerNeedsInputAfterRun
} from './automation_draft'
import { TOOL_APPROVAL_BANNER_ACTIONS, type ToolApprovalDecision } from './tool_approval'
import {
  detectProviderPreset,
  getProviderPreset,
  getProviderPresetDescription,
  MODEL_PROVIDER_PRESETS
} from './model_presets'
import { type AppLanguage, getStoredAppLanguage, LANGUAGE_STORAGE_KEY, t } from './i18n'
import { splitLiveAndPersistedRunHistory } from './run_activity_visibility'

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
  last_page_url: string | null
  last_page_title: string | null
}

type RecentConversation = {
  kind: 'chat' | 'browser'
  conversation: ConversationSummary
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

type RunActivityStepStatus = 'running' | 'completed' | 'failed' | 'waiting' | 'deferred' | 'warning'

type RunActivityStep = {
  id: string
  label: string
  status: RunActivityStepStatus
  detail: string | null
}

type RunActivity = {
  runId: string
  conversationId: string
  steps: RunActivityStep[]
  phase: 'live' | 'done'
  outcome: RunActivityOutcome | null
  startedAt: number
  endedAt: number | null
}

type PersistedRunHistory = {
  run: {
    run_id: string
    status: 'created' | 'completed' | 'failed' | 'cancelled' | 'limit_reached'
    created_at: string
    updated_at: string
  }
  events: Array<{ event_type: string; created_at: string; data: Record<string, unknown> }>
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
  resource_path: string | null
  impact_summary: string | null
  allows_conversation_approval: boolean
}

type FileChange = {
  change_id: string
  run_id: string
  operation: 'create' | 'replace' | 'delete'
  status: 'prepared' | 'applied' | 'reverted' | 'conflicted'
  path: string
  created_at: string
  updated_at: string
}

type AppView =
  | 'chat'
  | 'browser'
  | 'activity'
  | 'privacy'
  | 'automations'
  | 'history'
  | 'files'
  | 'mail'
  | 'calendar'
  | 'add-app'
  | 'preferences'

type AutomationStatus = 'active' | 'paused' | 'draft'

type AutomationPreview = {
  id: string
  name: string
  summary: string
  schedule: string
  nextRun: string | null
  lastRun: string | null
  status: AutomationStatus
  source: string
  capabilities: string[]
}

type AutomationTriggerDetail = {
  automation_trigger_id: string
  kind: 'once' | 'daily' | 'weekly'
  timezone: string
  local_time: string
  weekday: number | null
  next_run_at: string | null
  enabled: boolean
}

type AutomationExecutionDetail = {
  automation_execution_id: string
  scheduled_for: string
  status: 'claimed' | 'missed' | 'completed' | 'failed' | 'cancelled'
  run_id: string | null
  claimed_at: string
  completed_at: string | null
}

type TavilySettingsStatus = {
  enabled: boolean
  api_key_saved: boolean
}

type SavedProviderConfigStatus = {
  location: 'local' | 'external'
  model: string
  base_url: string
  api_key_saved: boolean
}

type ModelSettingsStatus = {
  configured: boolean
  active: boolean
  issue: 'api_key_missing' | 'credential_store_unavailable' | null
  location: 'local' | 'external' | null
  api_key_saved: boolean
  model: string | null
  base_url: string | null
  saved_providers?: Record<string, SavedProviderConfigStatus>
}

type AgentSettingsStatus = {
  max_steps: number
}

type StorageSettingsStatus = {
  snapshot_retention_days: number
  usage_bytes: number
  snapshot_count: number
}

type WorkspaceSettingsStatus = {
  workspace_root: string
  additional_roots: string[]
  additional_files: string[]
}

type WorkspaceFileNode = {
  name: string
  path: string
  relativePath: string
  kind: 'file' | 'directory'
  size?: number
  extension?: string
  children?: WorkspaceFileNode[]
}

type UpdateCheckResult = {
  currentVersion: string
  latestVersion: string
  hasUpdate: boolean
  releaseUrl: string
  downloadUrl: string
  releaseNotes: string
  publishedAt: string
}

type FilePreviewResult = {
  path: string
  name: string
  size: number
  content: string
  isTruncated: boolean
  isBinary: boolean
}

type BrowserTab = {
  id: string
  title: string
  address: string
  canGoBack: boolean
  canGoForward: boolean
}

type ActivityTab = 'approvals' | 'schedule'
type ScrollArea =
  'threads' | 'messages' | 'recents' | 'settings' | 'workspaceTree' | 'workspacePreview'
type ResizableColumn = 'rail' | 'threads' | 'attention' | 'browserAgent' | 'automationsMaster'
type DesktopLayout = {
  railWidth: number
  threadWidth: number
  attentionWidth: number
  attentionPanelOpen: boolean
  browserAgentPanelOpen: boolean
  browserAgentWidth: number
  automationsMasterWidth: number
}

const TAVILY_SETTINGS_LOAD_ERROR = 'Tavily settings could not be loaded.'
const TAVILY_SETTINGS_UPDATE_ERROR = 'Tavily settings could not be updated.'
const TAVILY_API_KEY_REQUIRED = 'Enter a Tavily API key before saving.'
const TAVILY_DELETE_CONFIRM = 'Remove the saved Tavily API key and disable Tavily web search?'
const MODEL_SETTINGS_LOAD_ERROR = 'Model settings could not be loaded.'
const MODEL_SETTINGS_UPDATE_ERROR = 'Model settings could not be updated.'
const MODEL_SETTINGS_REQUIRED = 'Enter a model and base URL before saving.'
const MODEL_SETTINGS_EXTERNAL_KEY_REQUIRED = 'Enter an API key for the external model.'
const AGENT_SETTINGS_LOAD_ERROR = 'Agent settings could not be loaded.'
const AGENT_SETTINGS_UPDATE_ERROR = 'Agent settings could not be updated.'
const AGENT_SETTINGS_REQUIRED = 'Enter a whole number from 1 to 50.'
const STORAGE_SETTINGS_LOAD_ERROR = 'Storage settings could not be loaded.'
const STORAGE_SETTINGS_UPDATE_ERROR = 'Storage settings could not be updated.'
const STORAGE_CLEAR_CONFIRM =
  'Clear all undo snapshots? This will immediately free disk space, but existing file changes cannot be undone from the chat.'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

function formatAutomationSchedule(
  trigger: AutomationTriggerDetail | undefined,
  lang: AppLanguage = 'en'
): string {
  if (trigger === undefined) return t(lang, 'noScheduleConfigured')
  const weekday =
    trigger.weekday === null
      ? ''
      : lang === 'zh-Hans'
        ? ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][trigger.weekday]
        : ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][
            trigger.weekday
          ]
  if (trigger.kind === 'once') {
    return lang === 'zh-Hans'
      ? `一次性 ${trigger.local_time} (${trigger.timezone})`
      : `Once at ${trigger.local_time} (${trigger.timezone})`
  }
  if (trigger.kind === 'daily') {
    return lang === 'zh-Hans'
      ? `每天 ${trigger.local_time} (${trigger.timezone})`
      : `Daily at ${trigger.local_time} (${trigger.timezone})`
  }
  return lang === 'zh-Hans'
    ? `每${weekday} ${trigger.local_time} (${trigger.timezone})`
    : `Every ${weekday} at ${trigger.local_time} (${trigger.timezone})`
}

function formatAutomationExecution(
  execution: AutomationExecutionDetail | undefined
): string | null {
  if (execution === undefined) return null
  return `${execution.status[0].toUpperCase()}${execution.status.slice(1)} · ${new Date(execution.scheduled_for).toLocaleString()}`
}

const MODEL_DELETE_CONFIRM = 'Remove the saved model configuration and API key?'
const CONVERSATION_DELETE_CONFIRM = 'Delete this conversation? This cannot be undone.'
const BROWSER_ADDRESS_ERROR =
  'This address is not allowed. Enter a web address such as example.com.'
const BROWSER_LOAD_ERROR = 'This page could not be opened.'
const MAX_BROWSER_TABS = 16
const BROWSER_AGENT_INPUT_MAX_HEIGHT = 132

function browserNavigationError(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error)
  return text.includes('could not be opened') ? BROWSER_LOAD_ERROR : BROWSER_ADDRESS_ERROR
}

function createBrowserTab(id?: string): BrowserTab {
  return {
    id: id ?? crypto.randomUUID(),
    title: 'New Tab',
    address: '',
    canGoBack: false,
    canGoForward: false
  }
}

function browserTabTitle(address: string): string {
  const trimmed = address.trim()
  if (trimmed === '') {
    return 'New Tab'
  }

  try {
    const value = trimmed.includes('://') ? trimmed : `https://${trimmed}`
    const hostname = new URL(value).hostname.replace(/^www\./u, '')
    return hostname === '' ? 'New Tab' : hostname
  } catch {
    return trimmed
  }
}

function resizeBrowserAgentInput(textarea: HTMLTextAreaElement | null): void {
  if (textarea === null) {
    return
  }

  textarea.style.height = 'auto'
  textarea.style.height = `${Math.min(textarea.scrollHeight, BROWSER_AGENT_INPUT_MAX_HEIGHT)}px`
}

function TreeChevron({ isExpanded }: { isExpanded: boolean }): React.JSX.Element {
  return (
    <svg
      className={`tree-chevron${isExpanded ? ' is-expanded' : ''}`}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
    >
      <path d="m9 18 6-6-6-6" />
    </svg>
  )
}

function TreeIcon({
  extension,
  isExpanded,
  kind
}: {
  extension?: string
  isExpanded?: boolean
  kind: 'file' | 'directory'
}): React.JSX.Element {
  if (kind === 'directory') {
    return isExpanded ? (
      <svg
        className="tree-icon tree-icon-folder"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        viewBox="0 0 24 24"
      >
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
        <path d="M2 10h20" />
      </svg>
    ) : (
      <svg
        className="tree-icon tree-icon-folder"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        viewBox="0 0 24 24"
      >
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
      </svg>
    )
  }

  const ext = extension?.toLowerCase()
  if (
    ext === 'ts' ||
    ext === 'tsx' ||
    ext === 'js' ||
    ext === 'jsx' ||
    ext === 'py' ||
    ext === 'rs' ||
    ext === 'go' ||
    ext === 'c' ||
    ext === 'cpp' ||
    ext === 'java' ||
    ext === 'sh'
  ) {
    return (
      <svg
        className="tree-icon tree-icon-code"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        viewBox="0 0 24 24"
      >
        <polyline points="16 18 22 12 16 6" />
        <polyline points="8 6 2 12 8 18" />
      </svg>
    )
  }
  if (
    ext === 'json' ||
    ext === 'yaml' ||
    ext === 'yml' ||
    ext === 'toml' ||
    ext === 'xml' ||
    ext === 'env'
  ) {
    return (
      <svg
        className="tree-icon tree-icon-config"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        viewBox="0 0 24 24"
      >
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09A1.65 1.65 0 0 0 15 4.6a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
    )
  }
  if (ext === 'md' || ext === 'txt' || ext === 'rst') {
    return (
      <svg
        className="tree-icon tree-icon-doc"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        viewBox="0 0 24 24"
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" x2="8" y1="13" y2="13" />
        <line x1="16" x2="8" y1="17" y2="17" />
      </svg>
    )
  }
  if (
    ext === 'png' ||
    ext === 'jpg' ||
    ext === 'jpeg' ||
    ext === 'gif' ||
    ext === 'svg' ||
    ext === 'webp'
  ) {
    return (
      <svg
        className="tree-icon tree-icon-media"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        viewBox="0 0 24 24"
      >
        <rect height="18" rx="2" ry="2" width="18" x="3" y="3" />
        <circle cx="8.5" cy="8.5" r="1.5" />
        <polyline points="21 15 16 10 5 21" />
      </svg>
    )
  }
  return (
    <svg
      className="tree-icon tree-icon-file"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      viewBox="0 0 24 24"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  )
}

const DEFAULT_RAIL_WIDTH = 226
const COLLAPSED_RAIL_WIDTH = 68
const DEFAULT_THREAD_WIDTH = 210
const DEFAULT_ATTENTION_WIDTH = 300
const MIN_RAIL_WIDTH = 180
const MAX_RAIL_WIDTH = 360
const MIN_THREAD_WIDTH = 160
const MAX_THREAD_WIDTH = 360
const MIN_ATTENTION_WIDTH = 240
const MAX_ATTENTION_WIDTH = 600
const DEFAULT_BROWSER_AGENT_WIDTH = 340
const MIN_BROWSER_AGENT_WIDTH = 200
const MAX_BROWSER_AGENT_WIDTH = 1200
const DEFAULT_AUTOMATIONS_MASTER_WIDTH = 340
const MIN_AUTOMATIONS_MASTER_WIDTH = 260
const MAX_AUTOMATIONS_MASTER_WIDTH = 640
const MIN_AUTOMATIONS_DETAIL_WIDTH = 380
const MIN_CHAT_CONTENT_WIDTH = 320
const MIN_BROWSER_SURFACE_WIDTH = 260
const MIN_CENTER_WIDTH = MIN_THREAD_WIDTH + MIN_CHAT_CONTENT_WIDTH
const DESKTOP_LAYOUT_STORAGE_KEY = 'asagent.desktop.layout.v1'

function defaultDesktopLayout(): DesktopLayout {
  return {
    railWidth: DEFAULT_RAIL_WIDTH,
    threadWidth: DEFAULT_THREAD_WIDTH,
    attentionWidth: DEFAULT_ATTENTION_WIDTH,
    attentionPanelOpen: false,
    browserAgentPanelOpen: true,
    browserAgentWidth: DEFAULT_BROWSER_AGENT_WIDTH,
    automationsMasterWidth: DEFAULT_AUTOMATIONS_MASTER_WIDTH
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
    const attentionPanelOpen = layout['attentionPanelOpen']
    const browserAgentPanelOpen = layout['browserAgentPanelOpen']
    const browserAgentWidth = layout['browserAgentWidth']
    const automationsMasterWidth = layout['automationsMasterWidth']
    if (
      !isLayoutWidth(railWidth, MIN_RAIL_WIDTH, MAX_RAIL_WIDTH) ||
      !isLayoutWidth(threadWidth, MIN_THREAD_WIDTH, MAX_THREAD_WIDTH) ||
      !isLayoutWidth(attentionWidth, MIN_ATTENTION_WIDTH, MAX_ATTENTION_WIDTH)
    ) {
      return defaultDesktopLayout()
    }

    return {
      railWidth,
      threadWidth,
      attentionWidth,
      attentionPanelOpen: attentionPanelOpen === true,
      browserAgentPanelOpen: browserAgentPanelOpen !== false,
      browserAgentWidth: isLayoutWidth(
        browserAgentWidth,
        MIN_BROWSER_AGENT_WIDTH,
        MAX_BROWSER_AGENT_WIDTH
      )
        ? browserAgentWidth
        : DEFAULT_BROWSER_AGENT_WIDTH,
      automationsMasterWidth: isLayoutWidth(
        automationsMasterWidth,
        MIN_AUTOMATIONS_MASTER_WIDTH,
        MAX_AUTOMATIONS_MASTER_WIDTH
      )
        ? automationsMasterWidth
        : DEFAULT_AUTOMATIONS_MASTER_WIDTH
    }
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

function conversationLabel(title: string | null, lang: AppLanguage = 'en'): string {
  return title ?? t(lang, 'newConversation')
}

function orderRecentConversations(
  conversations: ConversationSummary[],
  browserConversations: ConversationSummary[]
): RecentConversation[] {
  return [
    ...conversations.map((conversation) => ({ kind: 'chat' as const, conversation })),
    ...browserConversations.map((conversation) => ({
      kind: 'browser' as const,
      conversation
    }))
  ].sort((left, right) => {
    const updatedAtDifference =
      new Date(right.conversation.updated_at).getTime() -
      new Date(left.conversation.updated_at).getTime()
    if (updatedAtDifference !== 0) {
      return updatedAtDifference
    }
    return `${right.kind}:${right.conversation.conversation_id}`.localeCompare(
      `${left.kind}:${left.conversation.conversation_id}`
    )
  })
}

function mcpServerNameFromToolId(toolId: string): string | null {
  const match = /^mcp:([a-z][a-z0-9-]{0,63}):[^:]+:[0-9a-f]+$/i.exec(toolId)
  return match?.[1] ?? null
}

function browserApprovalKindLabel(toolId: string, serverName: string | null): string {
  if (toolId.startsWith('browser.')) {
    return 'Browser'
  }
  return serverName === null ? 'Tool' : 'MCP'
}

function browserApprovalDetails(approval: ToolApproval, serverName: string | null): string[] {
  const details: string[] = []
  if (approval.impact_summary !== null) {
    details.push(approval.impact_summary)
  }
  if (approval.resource_path !== null) {
    details.push(approval.resource_path)
  }
  const selector = approval.arguments.selector
  if (typeof selector === 'string' && selector.trim() !== '' && !details.includes(selector)) {
    details.push(selector)
  }
  if (serverName !== null && !details.includes(serverName)) {
    details.push(serverName)
  }
  return details
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

function formatMessageTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return ''
  }

  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
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

function isDeferredToolEvent(eventType: string, data: Record<string, unknown>): boolean {
  return (
    eventType === 'tool.deferred' ||
    (eventType === 'tool.failed' &&
      typeof data.error_summary === 'string' &&
      data.error_summary.startsWith('another tool call from this model response already ran'))
  )
}

function isWarningToolEvent(eventType: string, data: Record<string, unknown>): boolean {
  return (
    eventType === 'tool.warning' ||
    (eventType === 'tool.failed' && data.error_summary === 'tool arguments are invalid.')
  )
}

function formatElapsed(startedAt: number, endedAt: number | null): string | null {
  const end = endedAt ?? Date.now()
  const seconds = Math.max(1, Math.round((end - startedAt) / 1000))
  return `${seconds}s`
}

function activitySummaryLabel(activity: RunActivity, lang: AppLanguage = 'en'): string {
  const elapsed = formatElapsed(activity.startedAt, activity.endedAt)
  const actionCount = activity.steps.filter((step) => step.id.startsWith('tool:')).length
  const actionUnit =
    actionCount === 1 ? t(lang, 'activityActionUnit') : t(lang, 'activityActionsUnit')
  const details = [actionCount === 0 ? null : `${actionCount} ${actionUnit}`, elapsed].filter(
    (detail): detail is string => detail !== null
  )

  switch (activity.outcome) {
    case 'failed':
      return [t(lang, 'activityFailed'), ...details].join(' · ')
    case 'cancelled':
      return [t(lang, 'activityStopped'), ...details].join(' · ')
    case 'limit':
      return [t(lang, 'activityStoppedSafety'), ...details].join(' · ')
    case 'completed':
    default:
      return [t(lang, 'activityCompleted'), ...details].join(' · ')
  }
}

function activityCurrentLabel(activity: RunActivity, lang: AppLanguage = 'en'): string {
  const current = activity.steps.findLast(
    (step) => step.status === 'running' || step.status === 'waiting'
  )
  return current === undefined ? t(lang, 'activityWorking') : current.label
}

function persistedRunActivity(history: PersistedRunHistory): RunActivity {
  const steps: RunActivityStep[] = []
  for (const event of history.events) {
    if (event.event_type === 'model.requested') {
      steps.push({
        id: `model:${steps.length + 1}`,
        label: 'Planning next action',
        detail: null,
        status: 'completed'
      })
    } else if (event.event_type === 'tool.requested') {
      const callId =
        typeof event.data.tool_call_id === 'string'
          ? event.data.tool_call_id
          : `unknown-${steps.length + 1}`
      const label =
        typeof event.data.display_name === 'string' ? event.data.display_name : 'Use tool'
      steps.push({ id: `tool:${callId}`, label, detail: null, status: 'completed' })
    } else if (
      event.event_type === 'tool.failed' ||
      event.event_type === 'tool.deferred' ||
      event.event_type === 'tool.warning'
    ) {
      const callId = typeof event.data.tool_call_id === 'string' ? event.data.tool_call_id : ''
      const deferred = isDeferredToolEvent(event.event_type, event.data)
      const warning = isWarningToolEvent(event.event_type, event.data)
      const detail = deferred
        ? 'Deferred until next action.'
        : warning
          ? 'Tool arguments were invalid; replanning.'
          : typeof event.data.error_summary === 'string'
            ? event.data.error_summary
            : 'Tool failed.'
      const step = steps.find((item) => item.id === `tool:${callId}`)
      if (step !== undefined) {
        step.status = deferred ? 'deferred' : warning ? 'warning' : 'failed'
        step.detail = detail
      }
    }
  }
  const outcome: RunActivityOutcome =
    history.run.status === 'limit_reached'
      ? 'limit'
      : history.run.status === 'cancelled'
        ? 'cancelled'
        : history.run.status === 'failed'
          ? 'failed'
          : 'completed'
  return {
    runId: history.run.run_id,
    conversationId: '',
    steps,
    phase: 'done',
    outcome,
    startedAt: new Date(history.run.created_at).getTime(),
    endedAt: new Date(history.run.updated_at).getTime()
  }
}

function runHistoryByAssistantMessage(
  messages: ConversationMessage[],
  history: PersistedRunHistory[]
): Map<string, PersistedRunHistory[]> {
  const result = new Map<string, PersistedRunHistory[]>()
  for (const [index, run] of history.entries()) {
    const nextRun = history[index + 1]
    const nextRunStartedAt =
      nextRun === undefined ? Number.POSITIVE_INFINITY : new Date(nextRun.run.created_at).getTime()
    const assistant = messages.find(
      (message) =>
        message.role === 'assistant' &&
        new Date(message.created_at).getTime() >= new Date(run.run.updated_at).getTime() &&
        new Date(message.created_at).getTime() < nextRunStartedAt
    )
    if (assistant !== undefined) {
      const entries = result.get(assistant.message_id) ?? []
      entries.push(run)
      result.set(assistant.message_id, entries)
    }
  }
  return result
}

function RunActivityCard({
  activity,
  expanded,
  lang = 'en',
  onExpandedChange
}: {
  activity: RunActivity
  expanded: boolean
  lang?: AppLanguage
  onExpandedChange: (expanded: boolean) => void
}): React.JSX.Element {
  return (
    <div className="msg agent run-activity-msg">
      {activity.phase === 'done' && !expanded ? (
        <button
          aria-expanded="false"
          className={`activity-summary outcome-${activity.outcome ?? 'completed'}`}
          onClick={() => onExpandedChange(true)}
          type="button"
        >
          <span className="activity-summary-label">{activitySummaryLabel(activity, lang)}</span>
          <span aria-hidden="true" className="activity-chevron">
            ▾
          </span>
        </button>
      ) : (
        <div className={`activity-details${activity.phase === 'live' ? ' is-live' : ''}`}>
          {activity.phase === 'live' ? (
            <div aria-live="polite" className="activity-live">
              <span aria-hidden="true" className="activity-spinner" />
              <span>{activityCurrentLabel(activity, lang)}</span>
            </div>
          ) : (
            <button
              aria-expanded="true"
              className="activity-card-header is-button"
              onClick={() => onExpandedChange(false)}
              type="button"
            >
              <span className="activity-card-title">{activitySummaryLabel(activity, lang)}</span>
              <span aria-hidden="true" className="activity-chevron">
                ▴
              </span>
            </button>
          )}
          <ul className="activity-list">
            {activity.steps.map((step) => (
              <li
                className={`activity-item is-${step.status}`}
                key={`${activity.runId}-${step.id}`}
              >
                <span aria-hidden="true" className="activity-item-dot">
                  {step.status === 'completed'
                    ? '✓'
                    : step.status === 'failed'
                      ? '×'
                      : step.status === 'deferred'
                        ? '↷'
                        : step.status === 'warning'
                          ? '!'
                          : step.status === 'waiting'
                            ? '…'
                            : '•'}
                </span>
                <span>
                  {step.label}
                  {step.detail === null ? null : (
                    <span className="activity-item-detail"> — {step.detail}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function BrowserNavIcon({
  name
}: {
  name: 'back' | 'forward' | 'reload' | 'home'
}): React.JSX.Element {
  if (name === 'back') {
    return <Icon path="M15 18 9 12l6-6" />
  }

  if (name === 'forward') {
    return <Icon path="m9 18 6-6-6-6" />
  }

  if (name === 'reload') {
    return (
      <svg
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="2"
        viewBox="0 0 24 24"
      >
        <path d="M21 12a9 9 0 1 1-3.2-6.9" />
        <path d="M21 3v6h-6" />
      </svg>
    )
  }

  return (
    <svg
      fill="none"
      stroke="currentColor"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
    >
      <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-7h-4v7H5a1 1 0 0 1-1-1z" />
    </svg>
  )
}

function GoogleSearchIcon(): React.JSX.Element {
  return (
    <svg
      aria-hidden="true"
      className="browser-search-icon"
      height="14"
      viewBox="0 0 24 24"
      width="14"
    >
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
        fill="#EA4335"
      />
    </svg>
  )
}

function BingSearchIcon(): React.JSX.Element {
  return (
    <svg
      aria-hidden="true"
      className="browser-search-icon"
      fill="none"
      height="14"
      stroke="#0078D4"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2.75"
      viewBox="0 0 24 24"
      width="14"
    >
      <circle cx="10.5" cy="10.5" r="7" />
      <line x1="15.5" x2="21" y1="15.5" y2="21" />
    </svg>
  )
}

const SEARCH_ENGINE_STORAGE_KEY = 'asagent:browser_search_engine'
type BrowserSearchEngine = 'google' | 'bing'

function getStoredSearchEngine(): BrowserSearchEngine {
  try {
    const saved = window.localStorage.getItem(SEARCH_ENGINE_STORAGE_KEY)
    if (saved === 'bing' || saved === 'google') {
      return saved
    }
  } catch {
    // Ignore storage read error
  }
  return 'google'
}

const LOCALHOST_OR_IP_PATTERN =
  /^(localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|\[[0-9a-fA-F:]+\])(:\d+)?(\/.*)?$/i
const DOMAIN_PATTERN = /^([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}(:\d+)?(\/.*)?$/
const EXPLICIT_WEB_SCHEME = /^https?:/i

function isLikelyWebAddress(value: string): boolean {
  const trimmed = value.trim()
  if (!trimmed || /\s/.test(trimmed)) {
    return false
  }
  if (EXPLICIT_WEB_SCHEME.test(trimmed) || trimmed.startsWith('//')) {
    return true
  }
  return LOCALHOST_OR_IP_PATTERN.test(trimmed) || DOMAIN_PATTERN.test(trimmed)
}

function resolveSearchQuery(query: string, engine: BrowserSearchEngine): string {
  const trimmed = query.trim()
  if (engine === 'bing') {
    return `https://www.bing.com/search?q=${encodeURIComponent(trimmed)}`
  }
  return `https://www.google.com/search?q=${encodeURIComponent(trimmed)}`
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

function CopyIcon({ copied }: { copied: boolean }): React.JSX.Element {
  if (copied) {
    return <Icon path="m5 12 4 4L19 6" />
  }

  return (
    <svg aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 24 24">
      <rect height="11" rx="2" width="11" x="9" y="4" />
      <rect fill="var(--bg-raised)" height="11" rx="2" width="11" x="4" y="9" />
    </svg>
  )
}

function ContextPanelIcon({ direction }: { direction: 'collapse' | 'expand' }): React.JSX.Element {
  if (direction === 'collapse') {
    return (
      <svg
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.75"
        viewBox="0 0 24 24"
      >
        <path d="m11 17-5-5 5-5" />
        <path d="m18 17-5-5 5-5" />
      </svg>
    )
  }

  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.75"
      viewBox="0 0 24 24"
    >
      <path d="m13 17 5-5-5-5" />
      <path d="m6 17 5-5-5-5" />
    </svg>
  )
}

function BrowserAgentToggleIcon({ expanded }: { expanded: boolean }): React.JSX.Element {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
    >
      <rect height="16" rx="3" width="18" x="3" y="4" />
      {expanded ? (
        <path d="M15 4v16H18a3 3 0 0 0 3-3V7a3 3 0 0 0-3-3h-3Z" fill="currentColor" stroke="none" />
      ) : null}
      <path d="M15 4v16" />
      {expanded ? <path d="m8 9 3.5 3L8 15" /> : <path d="m11.5 9-3.5 3 3.5 3" />}
    </svg>
  )
}

function GlobeIcon(): React.JSX.Element {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
    >
      <circle cx="12" cy="12" r="10" />
      <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20M2 12h20" />
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
  const [fileChanges, setFileChanges] = useState<FileChange[]>([])
  const [undoingChangeId, setUndoingChangeId] = useState<string | null>(null)
  const [undoErrorChangeId, setUndoErrorChangeId] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null)
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null)
  const [isCreatingConversation, setIsCreatingConversation] = useState(false)
  const [renamingConversationId, setRenamingConversationId] = useState<string | null>(null)
  const [renameDraft, setRenameDraft] = useState('')
  const [isSubmittingMessage, setIsSubmittingMessage] = useState(false)
  const [activeRun, setActiveRun] = useState<ActiveRun | null>(null)
  const [isCancellingRun, setIsCancellingRun] = useState(false)
  const [runActivity, setRunActivity] = useState<RunActivity | null>(null)
  const [runHistory, setRunHistory] = useState<PersistedRunHistory[]>([])
  const [browserRunHistory, setBrowserRunHistory] = useState<PersistedRunHistory[]>([])
  const [expandedHistoryRunIds, setExpandedHistoryRunIds] = useState<Set<string>>(new Set())
  const [activityExpanded, setActivityExpanded] = useState(false)
  const [pendingApproval, setPendingApproval] = useState<ToolApproval | null>(null)
  const [isDecidingApproval, setIsDecidingApproval] = useState(false)
  const [activeView, setActiveView] = useState<AppView>('chat')
  const [automationPreviews, setAutomationPreviews] = useState<AutomationPreview[]>([])
  const [selectedAutomationId, setSelectedAutomationId] = useState<string | null>(null)
  const [automationLoadError, setAutomationLoadError] = useState<string | null>(null)
  const [automationExecutions, setAutomationExecutions] = useState<AutomationExecutionDetail[]>([])
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null)
  const [executionMessages, setExecutionMessages] = useState<ConversationMessage[]>([])
  const [isExecutionMessagesLoading, setIsExecutionMessagesLoading] = useState(false)
  const [editingAutomationId, setEditingAutomationId] = useState<string | null>(null)
  const [automationDraftConversationId, setAutomationDraftConversationId] = useState<string | null>(
    null
  )
  const [automationDraftMessages, setAutomationDraftMessages] = useState<ConversationMessage[]>([])
  const [automationInlineInput, setAutomationInlineInput] = useState('')
  const [isAutomationCreating, setIsAutomationCreating] = useState(false)
  const [automationPlannerNeedsInput, setAutomationPlannerNeedsInput] = useState(false)
  const [automationCreateStatus, setAutomationCreateStatus] = useState<string | null>(null)
  const [isAutomationRunningNow, setIsAutomationRunningNow] = useState(false)
  const [automationRunNowMessage, setAutomationRunNowMessage] = useState<string | null>(null)
  const [isCreatingNewTask, setIsCreatingNewTask] = useState(false)
  const [showTaskPrompt, setShowTaskPrompt] = useState(false)
  const [hasCopiedOutput, setHasCopiedOutput] = useState(false)
  const [browserTabs, setBrowserTabs] = useState<BrowserTab[]>([])
  const [activeBrowserTabId, setActiveBrowserTabId] = useState('')
  const [browserSessionReady, setBrowserSessionReady] = useState(false)
  const [browserError, setBrowserError] = useState<string | null>(null)
  const [browserConversations, setBrowserConversations] = useState<ConversationSummary[]>([])
  const [browserMessages, setBrowserMessages] = useState<ConversationMessage[]>([])
  const [browserDraft, setBrowserDraft] = useState('')
  const [browserEditingMessageId, setBrowserEditingMessageId] = useState<string | null>(null)
  const [browserConversationByTabId, setBrowserConversationByTabId] = useState<
    Record<string, string>
  >({})
  const selectedBrowserConversationId = browserConversationByTabId[activeBrowserTabId] ?? null
  const [activityTab, setActivityTab] = useState<ActivityTab>('approvals')
  const [tavilySettings, setTavilySettings] = useState<TavilySettingsStatus | null>(null)
  const [tavilyLoadError, setTavilyLoadError] = useState<string | null>(null)
  const [tavilyActionError, setTavilyActionError] = useState<string | null>(null)
  const [tavilyApiKey, setTavilyApiKey] = useState('')
  const [showTavilyKeyInput, setShowTavilyKeyInput] = useState(false)
  const [isReplacingTavilyKey, setIsReplacingTavilyKey] = useState(false)
  const [isTavilyLoading, setIsTavilyLoading] = useState(true)
  const [isTavilyBusy, setIsTavilyBusy] = useState(false)
  const [webSearchEnabled, setWebSearchEnabled] = useState<boolean>(() => {
    const saved = localStorage.getItem('asagent.webSearchEnabled')
    return saved !== null ? saved === 'true' : true
  })
  const webSearchEnabledRef = useRef(webSearchEnabled)
  webSearchEnabledRef.current = webSearchEnabled
  const [modelSettings, setModelSettings] = useState<ModelSettingsStatus | null>(null)
  const [modelLoadError, setModelLoadError] = useState<string | null>(null)
  const [modelActionError, setModelActionError] = useState<string | null>(null)
  const [restartRequested, setRestartRequested] = useState(false)
  const [isRestarting, setIsRestarting] = useState(false)
  const [selectedProviderId, setSelectedProviderId] = useState<string>('deepseek')
  const [modelLocation, setModelLocation] = useState<'local' | 'external'>('external')
  const [modelName, setModelName] = useState('')
  const [modelBaseUrl, setModelBaseUrl] = useState('')
  const [modelApiKey, setModelApiKey] = useState('')
  const [isModelLoading, setIsModelLoading] = useState(true)
  const [isModelBusy, setIsModelBusy] = useState(false)
  const [providerDrafts, setProviderDrafts] = useState<
    Record<string, { model: string; baseUrl: string; apiKey: string }>
  >({})
  const isSavedProvider =
    modelSettings !== null &&
    modelSettings.configured &&
    detectProviderPreset(modelSettings.base_url, modelSettings.location) === selectedProviderId
  const currentPresetSavedInfo =
    modelSettings?.saved_providers?.[selectedProviderId] ??
    (isSavedProvider
      ? {
          location: modelSettings?.location ?? 'external',
          model: modelSettings?.model ?? '',
          base_url: modelSettings?.base_url ?? '',
          api_key_saved: modelSettings?.api_key_saved ?? false
        }
      : null)
  const isCurrentPresetConfigured = currentPresetSavedInfo !== null
  const isCurrentPresetApiKeySaved = currentPresetSavedInfo?.api_key_saved ?? false
  const [agentSettings, setAgentSettings] = useState<AgentSettingsStatus | null>(null)
  const [agentMaxSteps, setAgentMaxSteps] = useState('20')
  const [agentLoadError, setAgentLoadError] = useState<string | null>(null)
  const [agentActionError, setAgentActionError] = useState<string | null>(null)
  const [isAgentLoading, setIsAgentLoading] = useState(true)
  const [isAgentBusy, setIsAgentBusy] = useState(false)
  const [storageSettings, setStorageSettings] = useState<StorageSettingsStatus | null>(null)
  const [storageRetentionDays, setStorageRetentionDays] = useState(7)
  const [storageLoadError, setStorageLoadError] = useState<string | null>(null)
  const [storageActionError, setStorageActionError] = useState<string | null>(null)
  const [storageActionSuccess, setStorageActionSuccess] = useState<string | null>(null)
  const [isStorageLoading, setIsStorageLoading] = useState(true)
  const [isStorageBusy, setIsStorageBusy] = useState(false)
  const [workspaceSettings, setWorkspaceSettings] = useState<WorkspaceSettingsStatus | null>(null)
  const [isWorkspaceLoading, setIsWorkspaceLoading] = useState(true)
  const [isWorkspaceBusy, setIsWorkspaceBusy] = useState(false)
  const [visibleScrollbar, setVisibleScrollbar] = useState<ScrollArea | null>(null)
  const [desktopLayout, setDesktopLayout] = useState<DesktopLayout>(storedDesktopLayout)
  const [browserSearchEngine, setBrowserSearchEngine] =
    useState<BrowserSearchEngine>(getStoredSearchEngine)
  const [appLanguage, setAppLanguage] = useState<AppLanguage>(getStoredAppLanguage)
  const [appVersion, setAppVersion] = useState<string>('')
  const [updateResult, setUpdateResult] = useState<UpdateCheckResult | null>(null)
  const [isCheckingUpdate, setIsCheckingUpdate] = useState(false)
  const [updateCheckError, setUpdateCheckError] = useState<string | null>(null)
  const [isRailCollapsed, setIsRailCollapsed] = useState(false)
  const [resizingColumn, setResizingColumn] = useState<ResizableColumn | null>(null)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const renameInputRef = useRef<HTMLInputElement | null>(null)
  const composerInputRef = useRef<HTMLTextAreaElement | null>(null)
  const browserAgentMessagesEndRef = useRef<HTMLDivElement | null>(null)
  const browserAgentInputRef = useRef<HTMLTextAreaElement | null>(null)
  const automationComposerInputRef = useRef<HTMLTextAreaElement | null>(null)
  const browserSurfaceRef = useRef<HTMLDivElement | null>(null)
  const browserAddressRef = useRef<HTMLInputElement | null>(null)
  const browserTabsRef = useRef(browserTabs)
  const activeBrowserTabIdRef = useRef(activeBrowserTabId)
  const selectedConversationIdRef = useRef(selectedConversationId)
  const selectedBrowserConversationIdRef = useRef(selectedBrowserConversationId)
  const automationDraftConversationIdRef = useRef(automationDraftConversationId)
  const automationDraftRunIdRef = useRef<string | null>(null)
  const automationDraftTargetIdRef = useRef<string | null>(null)
  const editingAutomationIdRef = useRef(editingAutomationId)
  const automationUpdatedAtByIdRef = useRef<Map<string, string>>(new Map())
  const automationDraftKnownVersionsRef = useRef<Map<string, string>>(new Map())
  const createNewChatSessionRef = useRef<() => void>(() => undefined)
  const browserMessageLoadIdRef = useRef(0)
  const scrollbarHideTimerRef = useRef<number | null>(null)
  const copyFeedbackTimerRef = useRef<number | null>(null)
  const desktopLayoutRef = useRef(desktopLayout)
  const activeViewRef = useRef(activeView)
  const appLanguageRef = useRef(appLanguage)
  const resizingColumnRef = useRef<ResizableColumn | null>(null)
  const railWidth = isRailCollapsed ? COLLAPSED_RAIL_WIDTH : desktopLayout.railWidth
  browserTabsRef.current = browserTabs
  activeBrowserTabIdRef.current = activeBrowserTabId
  selectedConversationIdRef.current = selectedConversationId
  automationDraftConversationIdRef.current = automationDraftConversationId
  selectedBrowserConversationIdRef.current = selectedBrowserConversationId
  appLanguageRef.current = appLanguage
  editingAutomationIdRef.current = editingAutomationId
  const [workspaceTrees, setWorkspaceTrees] = useState<Record<string, WorkspaceFileNode | null>>({})
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set())
  const [selectedPreviewFile, setSelectedPreviewFile] = useState<string | null>(null)
  const [filePreview, setFilePreview] = useState<FilePreviewResult | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)
  const [isTreeLoading, setIsTreeLoading] = useState(false)
  const [workspaceTreeVersion, setWorkspaceTreeVersion] = useState(0)

  const refreshWorkspaceTree = useCallback((): void => {
    setWorkspaceTreeVersion((v) => v + 1)
  }, [])

  const attachedFolders = workspaceSettings?.additional_roots ?? []
  const attachedFiles = workspaceSettings?.additional_files ?? []
  const hasAttachedWorkspace = attachedFolders.length > 0 || attachedFiles.length > 0
  const selectedAutomation =
    automationPreviews.find((automation) => automation.id === selectedAutomationId) ??
    automationPreviews[0] ??
    null
  const lastAutomationDraftMessage = automationDraftMessages.at(-1) ?? null
  const isAutomationAwaitingInput = isAwaitingAutomationInput(
    isCreatingNewTask,
    isAutomationCreating,
    automationPlannerNeedsInput
  )
  activeViewRef.current = activeView

  useEffect(() => {
    if (isAutomationAwaitingInput) {
      automationComposerInputRef.current?.focus()
    }
  }, [isAutomationAwaitingInput, automationDraftMessages.length])

  useEffect(() => {
    if (backendStatus !== 'ready') return
    void window.desktop
      .listAutomations()
      .then((automations) => {
        automationUpdatedAtByIdRef.current = new Map(
          automations.map((automation) => [automation.automation_id, automation.updated_at])
        )
        const values = automations.map((automation) => ({
          id: automation.automation_id,
          name: automation.name,
          summary: automation.plan_summary,
          schedule: 'Schedule details available after selection',
          nextRun: null,
          lastRun: null,
          status: automation.status,
          source: 'Confirmed scheduled task plan',
          capabilities: automation.allowed_capabilities
        }))
        setAutomationPreviews(values)
        setSelectedAutomationId((current) => current ?? values[0]?.id ?? null)
        setAutomationLoadError(null)
      })
      .catch(() => setAutomationLoadError('Scheduled tasks could not be loaded.'))
  }, [backendStatus])

  useEffect(() => {
    setSelectedExecutionId(null)
    setExecutionMessages([])
    if (backendStatus !== 'ready' || selectedAutomationId === null) {
      setAutomationExecutions([])
      return
    }
    void Promise.all([
      window.desktop.listAutomationTriggers(selectedAutomationId),
      window.desktop.listAutomationExecutions(selectedAutomationId)
    ])
      .then(([triggers, executions]) => {
        setAutomationExecutions(executions)
        const schedule = formatAutomationSchedule(triggers[0])
        const nextRun = triggers[0]?.next_run_at
          ? new Date(triggers[0].next_run_at).toLocaleString()
          : null
        const lastRun = formatAutomationExecution(executions[0])
        setAutomationPreviews((values) =>
          values.map((value) =>
            value.id === selectedAutomationId ? { ...value, schedule, nextRun, lastRun } : value
          )
        )
        if (executions.length > 0) {
          const latestId = executions[0].automation_execution_id
          setSelectedExecutionId(latestId)
          setIsExecutionMessagesLoading(true)
          window.desktop
            .getAutomationExecutionMessages(selectedAutomationId, latestId)
            .then((messages) => setExecutionMessages(messages))
            .catch(() => setExecutionMessages([]))
            .finally(() => setIsExecutionMessagesLoading(false))
        }
      })
      .catch(() => setAutomationLoadError('Scheduled task details could not be loaded.'))
  }, [backendStatus, selectedAutomationId])

  const isAttentionPanelVisible =
    (activeView === 'chat' && hasAttachedWorkspace && desktopLayout.attentionPanelOpen) ||
    (activeView !== 'chat' &&
      activeView !== 'browser' &&
      activeView !== 'preferences' &&
      activeView !== 'automations' &&
      desktopLayout.attentionPanelOpen)

  const addBrowserTab = useCallback((): void => {
    const current = browserTabsRef.current
    if (current.length >= MAX_BROWSER_TABS) {
      return
    }

    const created = createBrowserTab()
    setBrowserTabs([...current, created])
    setActiveBrowserTabId(created.id)
    setBrowserError(null)
    window.setTimeout(() => {
      browserAddressRef.current?.focus()
    }, 0)
  }, [])

  const closeBrowserTab = useCallback((tabId: string): void => {
    void window.desktop.closeBrowserTab(tabId).catch(() => undefined)
    setBrowserConversationByTabId((current) => {
      if (!(tabId in current)) {
        return current
      }
      const next = { ...current }
      delete next[tabId]
      return next
    })
    const current = browserTabsRef.current
    const index = current.findIndex((tab) => tab.id === tabId)
    const remaining = current.filter((tab) => tab.id !== tabId)
    if (remaining.length === 0) {
      const created = createBrowserTab()
      setBrowserTabs([created])
      setActiveBrowserTabId(created.id)
      setBrowserError(null)
      void window.desktop.setBrowserTabConversation(created.id, null).catch(() => undefined)
      return
    }

    setBrowserTabs(remaining)
    if (tabId === activeBrowserTabIdRef.current) {
      const fallback = remaining[Math.max(0, index - 1)] ?? remaining[0]
      if (fallback !== undefined) {
        setActiveBrowserTabId(fallback.id)
      }
    }
    setBrowserError(null)
  }, [])

  const controlBrowser = useCallback((action: 'back' | 'forward' | 'reload' | 'home'): void => {
    void window.desktop
      .controlBrowser(activeBrowserTabIdRef.current, action)
      .catch((error: unknown) => {
        setBrowserError(browserNavigationError(error))
      })
  }, [])

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
      if (copyFeedbackTimerRef.current !== null) {
        window.clearTimeout(copyFeedbackTimerRef.current)
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

      const attentionIsVisible =
        window.innerWidth > 1100 &&
        desktopLayoutRef.current.attentionPanelOpen &&
        activeViewRef.current !== 'chat' &&
        activeViewRef.current !== 'browser'
      const railIsVisible = window.innerWidth > 820
      const layout = desktopLayoutRef.current
      const currentRailWidth = isRailCollapsed ? COLLAPSED_RAIL_WIDTH : layout.railWidth
      const requestedWidth =
        column === 'rail'
          ? event.clientX
          : column === 'threads'
            ? event.clientX - currentRailWidth
            : column === 'automationsMaster'
              ? event.clientX - currentRailWidth
              : window.innerWidth - event.clientX
      const otherColumnWidth =
        column === 'rail' && attentionIsVisible
          ? layout.attentionWidth
          : column === 'attention' || column === 'browserAgent'
            ? railIsVisible
              ? currentRailWidth
              : 0
            : 0
      const minimumWidth =
        column === 'rail'
          ? MIN_RAIL_WIDTH
          : column === 'threads'
            ? MIN_THREAD_WIDTH
            : column === 'automationsMaster'
              ? MIN_AUTOMATIONS_MASTER_WIDTH
              : column === 'browserAgent'
                ? MIN_BROWSER_AGENT_WIDTH
                : MIN_ATTENTION_WIDTH
      const maximumWidth = Math.min(
        column === 'rail'
          ? MAX_RAIL_WIDTH
          : column === 'threads'
            ? MAX_THREAD_WIDTH
            : column === 'automationsMaster'
              ? MAX_AUTOMATIONS_MASTER_WIDTH
              : column === 'browserAgent'
                ? MAX_BROWSER_AGENT_WIDTH
                : MAX_ATTENTION_WIDTH,
        column === 'threads'
          ? window.innerWidth -
              (railIsVisible ? currentRailWidth : 0) -
              (attentionIsVisible ? layout.attentionWidth : 0) -
              MIN_CHAT_CONTENT_WIDTH
          : column === 'automationsMaster'
            ? window.innerWidth -
              (railIsVisible ? currentRailWidth : 0) -
              MIN_AUTOMATIONS_DETAIL_WIDTH
            : column === 'browserAgent'
              ? window.innerWidth - otherColumnWidth - MIN_BROWSER_SURFACE_WIDTH
              : window.innerWidth - otherColumnWidth - MIN_CENTER_WIDTH
      )
      const width = Math.max(minimumWidth, Math.min(requestedWidth, maximumWidth))
      const nextLayout = {
        ...desktopLayoutRef.current,
        ...(column === 'rail'
          ? { railWidth: width }
          : column === 'threads'
            ? { threadWidth: width }
            : column === 'automationsMaster'
              ? { automationsMasterWidth: width }
              : column === 'browserAgent'
                ? { browserAgentWidth: width }
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
        const [info, status, items, browserItems, browserSession] = await Promise.all([
          window.desktop.getAppInfo(),
          window.desktop.getBackendStatus(),
          window.desktop.listConversations(),
          window.desktop.listBrowserConversations(),
          window.desktop.getBrowserSession()
        ])

        if (cancelled) {
          return
        }

        const orderedBrowserItems = orderConversations(browserItems)
        const knownBrowserConversationIds = new Set(
          orderedBrowserItems.map((conversation) => conversation.conversation_id)
        )
        const sessionTabs =
          browserSession.tabs.length > 0
            ? browserSession.tabs
            : [{ tabId: crypto.randomUUID(), url: '', conversationId: null }]
        const visibleTabId = sessionTabs.some((tab) => tab.tabId === browserSession.visibleTabId)
          ? browserSession.visibleTabId
          : sessionTabs[0]!.tabId
        const conversationByTabId: Record<string, string> = {}
        for (const tab of sessionTabs) {
          if (tab.conversationId !== null && knownBrowserConversationIds.has(tab.conversationId)) {
            conversationByTabId[tab.tabId] = tab.conversationId
          }
        }

        setAppInfo(info)
        setBackendStatus(status.status)
        setConversations(orderConversations(items))
        setSelectedConversationId(items[0]?.conversation_id ?? null)
        setBrowserConversations(orderedBrowserItems)
        setBrowserTabs(
          sessionTabs.map((tab) => ({
            id: tab.tabId,
            title: browserTabTitle(tab.url),
            address: tab.url,
            canGoBack: false,
            canGoForward: false
          }))
        )
        setActiveBrowserTabId(visibleTabId)
        setBrowserConversationByTabId(conversationByTabId)
        setBrowserSessionReady(true)
      } catch {
        if (!cancelled) {
          setBackendStatus('unavailable')
          setErrorMessage('Conversation history could not be loaded.')
          const fallback = createBrowserTab()
          setBrowserTabs([fallback])
          setActiveBrowserTabId(fallback.id)
          setBrowserSessionReady(true)
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
          const detectedPreset = detectProviderPreset(status.base_url, status.location)
          setSelectedProviderId(detectedPreset)
          setModelLocation(status.location ?? 'external')
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

    async function loadAgentSettings(): Promise<void> {
      setIsAgentLoading(true)
      try {
        const status = await window.desktop.getAgentSettings()
        if (!cancelled) {
          setAgentSettings(status)
          setAgentMaxSteps(String(status.max_steps))
          setAgentLoadError(null)
        }
      } catch {
        if (!cancelled) {
          setAgentLoadError(AGENT_SETTINGS_LOAD_ERROR)
        }
      } finally {
        if (!cancelled) {
          setIsAgentLoading(false)
        }
      }
    }

    void loadAgentSettings()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function loadStorageSettings(): Promise<void> {
      setIsStorageLoading(true)
      try {
        const status = await window.desktop.getStorageSettings()
        if (!cancelled) {
          setStorageSettings(status)
          setStorageRetentionDays(status.snapshot_retention_days)
          setStorageLoadError(null)
        }
      } catch {
        if (!cancelled) {
          setStorageLoadError(STORAGE_SETTINGS_LOAD_ERROR)
        }
      } finally {
        if (!cancelled) {
          setIsStorageLoading(false)
        }
      }
    }

    void loadStorageSettings()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    void window.desktop.getAppVersion().then((version) => {
      setAppVersion(version)
    })

    const LAST_CHECK_KEY = 'asagent:last_update_check'
    const CHECK_INTERVAL_MS = 12 * 60 * 60 * 1000

    async function runSilentCheck(): Promise<void> {
      const now = Date.now()
      const lastCheck = Number(window.localStorage.getItem(LAST_CHECK_KEY) || 0)
      if (now - lastCheck < CHECK_INTERVAL_MS) {
        return
      }

      try {
        const result = await window.desktop.checkForUpdates()
        setUpdateResult(result)
        window.localStorage.setItem(LAST_CHECK_KEY, String(now))
      } catch {
        // Silent background check errors are ignored
      }
    }

    const timer = setTimeout(() => {
      void runSilentCheck()
    }, 3000)

    const interval = setInterval(() => {
      void runSilentCheck()
    }, CHECK_INTERVAL_MS)

    return () => {
      clearTimeout(timer)
      clearInterval(interval)
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
        setRunHistory([])
        setFileChanges([])
        setUndoErrorChangeId(null)
      })
      return
    }

    const conversationId = selectedConversationId
    let cancelled = false

    async function loadConversation(): Promise<void> {
      try {
        const [items, changes, history] = await Promise.all([
          window.desktop.listConversationMessages(conversationId),
          window.desktop.listConversationFileChanges(conversationId),
          window.desktop.listConversationRunHistory(conversationId)
        ])

        if (!cancelled) {
          setMessages(items)
          setFileChanges(changes)
          setRunHistory(history)
          setErrorMessage(null)
        }
      } catch {
        if (!cancelled) {
          setErrorMessage('Messages could not be loaded.')
        }
      }
    }

    void loadConversation()

    return () => {
      cancelled = true
    }
  }, [selectedConversationId])

  useEffect(() => {
    if (selectedBrowserConversationId === null) {
      queueMicrotask(() => {
        setBrowserMessages([])
        setBrowserRunHistory([])
      })
      return
    }

    const conversationId = selectedBrowserConversationId
    const loadId = ++browserMessageLoadIdRef.current
    let cancelled = false

    async function loadBrowserConversation(): Promise<void> {
      try {
        const [items, history] = await Promise.all([
          window.desktop.listBrowserConversationMessages(conversationId),
          window.desktop.listBrowserConversationRunHistory(conversationId)
        ])
        if (!cancelled && loadId === browserMessageLoadIdRef.current) {
          setBrowserMessages(items)
          setBrowserRunHistory(history)
        }
      } catch {
        if (!cancelled && loadId === browserMessageLoadIdRef.current) {
          setErrorMessage('Messages could not be loaded.')
        }
      }
    }

    void loadBrowserConversation()

    return () => {
      cancelled = true
    }
  }, [selectedBrowserConversationId])

  useEffect(() => {
    const removeEventListener = window.desktop.onRunEvent((update) => {
      recordRunEvent(update.runId, update.event.event_type, update.event.data)

      const outcome = runActivityOutcome(update.event.event_type)
      if (outcome === null) {
        return
      }

      setPendingApproval((current) => (current?.run_id === update.runId ? null : current))
      setActiveRun((current) => (current?.runId === update.runId ? null : current))
      setIsCancellingRun(false)

      if (update.conversationId === selectedConversationIdRef.current) {
        void Promise.all([
          window.desktop.listConversationMessages(update.conversationId),
          window.desktop.listConversationFileChanges(update.conversationId)
        ])
          .then(([nextMessages, changes]) => {
            setMessages(nextMessages)
            setFileChanges(changes)
            refreshWorkspaceTree()
          })
          .catch(() => setErrorMessage('Messages could not be refreshed.'))
      }

      if (update.conversationId === selectedBrowserConversationIdRef.current) {
        const loadId = ++browserMessageLoadIdRef.current
        void Promise.all([
          window.desktop.listBrowserConversationMessages(update.conversationId),
          window.desktop.listBrowserConversationRunHistory(update.conversationId)
        ])
          .then(([nextMessages, history]) => {
            if (
              loadId === browserMessageLoadIdRef.current &&
              selectedBrowserConversationIdRef.current === update.conversationId
            ) {
              setBrowserMessages(nextMessages)
              setBrowserRunHistory(history)
            }
          })
          .catch(() => setErrorMessage('Messages could not be refreshed.'))
      }

      if (update.conversationId === automationDraftConversationIdRef.current) {
        automationDraftRunIdRef.current = null
        setIsAutomationCreating(false)
        void Promise.all([
          window.desktop.listAutomationDraftMessages(update.conversationId),
          window.desktop.listAutomations()
        ])
          .then(([messages, automations]) => {
            setAutomationDraftMessages(messages)
            const savedAutomation = findSavedAutomation(
              automations,
              automationDraftKnownVersionsRef.current,
              automationDraftTargetIdRef.current
            )
            const plannerNeedsInput = plannerNeedsInputAfterRun(
              outcome,
              savedAutomation !== undefined,
              messages.at(-1)?.role ?? null
            )
            automationUpdatedAtByIdRef.current = new Map(
              automations.map((automation) => [automation.automation_id, automation.updated_at])
            )
            const values = automations.map((automation) => ({
              id: automation.automation_id,
              name: automation.name,
              summary: automation.plan_summary,
              schedule: 'Schedule details available after selection',
              nextRun: null,
              lastRun: null,
              status: automation.status,
              source: 'Confirmed scheduled task plan',
              capabilities: automation.allowed_capabilities
            }))
            setAutomationPreviews(values)
            if (savedAutomation !== undefined) {
              const savedId = savedAutomation.automation_id
              const draftConversationId = automationDraftConversationIdRef.current
              automationDraftConversationIdRef.current = null
              automationDraftTargetIdRef.current = null
              automationDraftKnownVersionsRef.current = new Map()
              editingAutomationIdRef.current = null
              setSelectedAutomationId(savedId)
              setIsCreatingNewTask(false)
              setEditingAutomationId(null)
              setAutomationDraftConversationId(null)
              setAutomationDraftMessages([])
              setAutomationPlannerNeedsInput(false)
              setAutomationInlineInput('')
              setAutomationCreateStatus(
                `✓ ${t(appLanguageRef.current, 'savedScheduledTask')}: "${savedAutomation.name}"`
              )
              automationDraftKnownVersionsRef.current.set(savedId, savedAutomation.updated_at)
              if (draftConversationId !== null) {
                void window.desktop
                  .deleteAutomationDraft(draftConversationId)
                  .catch(() => undefined)
              }
              window.setTimeout(() => {
                setAutomationCreateStatus((curr) => (curr?.startsWith('✓') ? null : curr))
              }, 4000)
            } else {
              setAutomationCreateStatus(null)
              setAutomationPlannerNeedsInput(plannerNeedsInput)
            }
          })
          .catch(() => {
            setAutomationPlannerNeedsInput(false)
            setAutomationLoadError('Scheduled tasks could not be refreshed.')
          })
      }
    })

    const removeErrorListener = window.desktop.onRunStreamError((error) => {
      if (error.runId === automationDraftRunIdRef.current) {
        automationDraftRunIdRef.current = null
        setIsAutomationCreating(false)
        setAutomationPlannerNeedsInput(false)
        setAutomationCreateStatus(null)
        setAutomationLoadError('The scheduled-task planning response was interrupted.')
      }
      setActiveRun((current) => (current?.runId === error.runId ? null : current))
      setIsCancellingRun(false)
      setRunActivityWaiting(
        error.runId,
        'Run connection lost.',
        'The live event stream disconnected.'
      )
      finishRunActivity(error.runId, 'failed')
      setErrorMessage(error.message)
    })

    const removeApprovalListener = window.desktop.onToolApprovalRequested((approval) => {
      if (
        webSearchEnabledRef.current &&
        (approval.tool_id.includes('tavily') ||
          approval.display_name.toLowerCase().includes('search'))
      ) {
        void window.desktop
          .decideToolApproval(approval.approval_id, 'allow_conversation')
          .catch(() => undefined)
        return
      }
      setPendingApproval(approval)
      setIsDecidingApproval(false)
      setRunActivityWaiting(approval.run_id, `Waiting for approval: ${approval.display_name}`, null)
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
  }, [])

  useEffect(() => {
    if (renamingConversationId === null) {
      return
    }

    renameInputRef.current?.focus()
    renameInputRef.current?.select()
  }, [renamingConversationId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [
    messages,
    pendingApproval?.approval_id,
    runActivity?.steps,
    runActivity?.phase,
    selectedConversationId
  ])

  useEffect(() => {
    browserAgentMessagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [browserMessages, selectedBrowserConversationId])

  useEffect(() => {
    resizeBrowserAgentInput(browserAgentInputRef.current)
  }, [browserDraft])

  useEffect(() => {
    const showingMainBrowser = activeView === 'browser'
    if (!showingMainBrowser) {
      void window.desktop.hideBrowser()
      return
    }

    const tabId = activeBrowserTabId
    if (!browserSessionReady || tabId === '') {
      return
    }

    const surface = browserSurfaceRef.current
    if (surface === null) {
      return
    }

    const reportBounds = (): void => {
      const rect = surface.getBoundingClientRect()
      if (rect.width <= 0 || rect.height <= 0) {
        return
      }

      void window.desktop.showBrowser(tabId, {
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height)
      })
    }

    reportBounds()
    const observer = new ResizeObserver(reportBounds)
    observer.observe(surface)
    return () => {
      observer.disconnect()
    }
  }, [
    activeView,
    activeBrowserTabId,
    browserSessionReady,
    desktopLayout.browserAgentPanelOpen,
    desktopLayout.browserAgentWidth
  ])

  useEffect(() => {
    return () => {
      void window.desktop.hideBrowser()
    }
  }, [])

  useEffect(() => {
    return window.desktop.onBrowserTabState((state) => {
      setBrowserTabs((current) => {
        const existing = current.find((tab) => tab.id === state.tabId)
        if (existing === undefined) {
          setActiveBrowserTabId(state.tabId)
          return [
            ...current,
            {
              id: state.tabId,
              title: state.title,
              address: state.url,
              canGoBack: state.canGoBack,
              canGoForward: state.canGoForward
            }
          ]
        }

        const editing =
          state.tabId === activeBrowserTabIdRef.current &&
          document.activeElement === browserAddressRef.current
        return current.map((tab) =>
          tab.id === state.tabId
            ? {
                ...tab,
                canGoBack: state.canGoBack,
                canGoForward: state.canGoForward,
                title: state.title,
                address: editing ? tab.address : state.url
              }
            : tab
        )
      })
    })
  }, [])

  useEffect(() => {
    function onGlobalShortcut(event: KeyboardEvent): void {
      if (!(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey) {
        return
      }
      if (event.key.toLowerCase() === 'n') {
        event.preventDefault()
        createNewChatSessionRef.current()
      }
    }

    window.addEventListener('keydown', onGlobalShortcut)
    return () => {
      window.removeEventListener('keydown', onGlobalShortcut)
    }
  }, [])

  useEffect(() => {
    if (activeView !== 'browser') {
      return
    }

    function onBrowserShortcut(event: KeyboardEvent): void {
      if (!(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey) {
        return
      }

      const key = event.key.toLowerCase()
      if (key === 't') {
        event.preventDefault()
        addBrowserTab()
        return
      }

      if (key === 'w') {
        event.preventDefault()
        closeBrowserTab(activeBrowserTabId)
        return
      }

      if (key === 'l') {
        event.preventDefault()
        browserAddressRef.current?.focus()
        browserAddressRef.current?.select()
        return
      }

      if (key === 'r') {
        event.preventDefault()
        controlBrowser('reload')
        return
      }

      if (key === '[') {
        event.preventDefault()
        controlBrowser('back')
        return
      }

      if (key === ']') {
        event.preventDefault()
        controlBrowser('forward')
      }
    }

    window.addEventListener('keydown', onBrowserShortcut)
    return () => {
      window.removeEventListener('keydown', onBrowserShortcut)
    }
  }, [activeView, activeBrowserTabId, addBrowserTab, closeBrowserTab, controlBrowser])

  const selectedConversation = conversations.find(
    (conversation) => conversation.conversation_id === selectedConversationId
  )
  const visibleMessages = selectedConversationId === null ? [] : messages
  const visibleApproval =
    pendingApproval?.conversation_id === selectedConversationId ? pendingApproval : null
  const visibleBrowserApproval =
    pendingApproval?.conversation_id === selectedBrowserConversationId ? pendingApproval : null
  const visibleApprovalServer =
    visibleApproval === null ? null : mcpServerNameFromToolId(visibleApproval.tool_id)
  const visibleBrowserApprovalServer =
    visibleBrowserApproval === null ? null : mcpServerNameFromToolId(visibleBrowserApproval.tool_id)
  const visibleBrowserApprovalDetails =
    visibleBrowserApproval === null
      ? []
      : browserApprovalDetails(visibleBrowserApproval, visibleBrowserApprovalServer)
  const isBusy =
    backendStatus !== 'ready' || isCreatingConversation || isSubmittingMessage || activeRun !== null
  const recentConversations = orderRecentConversations(conversations, browserConversations)
  const chatRunIsActive = activeRun?.conversationId === selectedConversationId
  const browserRunIsActive = activeRun?.conversationId === selectedBrowserConversationId

  const { liveActivity: visibleBrowserActivity, persistedHistory: visibleBrowserRunHistory } =
    splitLiveAndPersistedRunHistory(runActivity, selectedBrowserConversationId, browserRunHistory)
  const browserRunHistoryByMessage = runHistoryByAssistantMessage(
    browserMessages,
    visibleBrowserRunHistory
  )
  const matchedBrowserRunIds = new Set(
    [...browserRunHistoryByMessage.values()].flatMap((items) =>
      items.map((history) => history.run.run_id)
    )
  )
  const unmatchedBrowserRunHistory = visibleBrowserRunHistory.filter(
    (history) => !matchedBrowserRunIds.has(history.run.run_id)
  )

  const usesExternalModel = appInfo?.dataProcessingMode === 'external'
  const configuredExternalProviderUnavailable =
    modelSettings?.location === 'external' && !modelSettings.active

  function openAssistantLink(href: string | undefined): void {
    if (href === undefined) {
      return
    }

    void window.desktop.openExternalLink(href).catch(() => {
      setErrorMessage('The link could not be opened.')
    })
  }

  const activeBrowserTab =
    browserTabs.find((tab) => tab.id === activeBrowserTabId) ?? browserTabs[0]

  function selectBrowserTab(tabId: string): void {
    setActiveBrowserTabId(tabId)
    setBrowserError(null)
  }

  function updateActiveBrowserAddress(address: string): void {
    setBrowserTabs((current) =>
      current.map((tab) => (tab.id === activeBrowserTabId ? { ...tab, address } : tab))
    )
    if (browserError !== null) {
      setBrowserError(null)
    }
  }

  async function openBrowserAddress(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    const address = (activeBrowserTab?.address ?? '').trim()
    if (!address) {
      return
    }
    setBrowserError(null)
    const targetUrl = isLikelyWebAddress(address)
      ? address
      : resolveSearchQuery(address, browserSearchEngine)
    try {
      const opened = await window.desktop.navigateBrowser(activeBrowserTabId, targetUrl)
      setBrowserTabs((current) =>
        current.map((tab) =>
          tab.id === activeBrowserTabId
            ? { ...tab, address: opened, title: browserTabTitle(opened) }
            : tab
        )
      )
    } catch (error) {
      setBrowserError(browserNavigationError(error))
    }
  }

  function setRunActivityWaiting(runId: string, label: string, detail: string | null): void {
    setRunActivity((current) => {
      if (current === null || current.runId !== runId) {
        return current
      }

      return {
        ...current,
        steps: [
          ...current.steps.map((step) =>
            step.status === 'running' || step.status === 'waiting'
              ? { ...step, status: 'completed' as const }
              : step
          ),
          {
            id: `status:${current.steps.length + 1}`,
            label,
            detail,
            status: 'waiting'
          }
        ]
      }
    })
  }

  function recordRunEvent(runId: string, eventType: string, data: Record<string, unknown>): void {
    const outcome = runActivityOutcome(eventType)
    if (outcome !== null) {
      finishRunActivity(runId, outcome)
      return
    }

    setRunActivity((current) => {
      if (current === null || current.runId !== runId) return current

      const closeLiveSteps = (steps: RunActivityStep[]): RunActivityStep[] =>
        steps.map((step) =>
          step.status === 'running' || step.status === 'waiting'
            ? { ...step, status: 'completed' as const }
            : step
        )
      if (eventType === 'model.requested') {
        return {
          ...current,
          steps: [
            ...closeLiveSteps(current.steps),
            {
              id: `model:${data.step ?? current.steps.length + 1}`,
              label: 'Planning next action',
              detail: null,
              status: 'running'
            }
          ]
        }
      }
      if (eventType === 'model.completed') {
        return { ...current, steps: closeLiveSteps(current.steps) }
      }
      if (eventType === 'tool.requested') {
        const callId =
          typeof data.tool_call_id === 'string'
            ? data.tool_call_id
            : `unknown-${current.steps.length + 1}`
        const displayName = typeof data.display_name === 'string' ? data.display_name : 'Use tool'
        return {
          ...current,
          steps: [
            ...closeLiveSteps(current.steps),
            { id: `tool:${callId}`, label: displayName, detail: null, status: 'running' }
          ]
        }
      }
      if (
        eventType === 'tool.completed' ||
        eventType === 'tool.failed' ||
        eventType === 'tool.deferred' ||
        eventType === 'tool.warning'
      ) {
        const callId = typeof data.tool_call_id === 'string' ? data.tool_call_id : ''
        const deferred = isDeferredToolEvent(eventType, data)
        const warning = isWarningToolEvent(eventType, data)
        const errorSummary = deferred
          ? 'Deferred until next action.'
          : warning
            ? 'Tool arguments were invalid; replanning.'
            : typeof data.error_summary === 'string'
              ? data.error_summary
              : null
        return {
          ...current,
          steps: current.steps.map((step) =>
            step.id === `tool:${callId}`
              ? {
                  ...step,
                  status:
                    eventType === 'tool.completed'
                      ? 'completed'
                      : deferred
                        ? 'deferred'
                        : warning
                          ? 'warning'
                          : 'failed',
                  detail: errorSummary
                }
              : step
          )
        }
      }
      if (eventType === 'tool.approval_requested') {
        const displayName = typeof data.display_name === 'string' ? data.display_name : 'tool'
        return {
          ...current,
          steps: current.steps.map((step) =>
            step.status === 'running'
              ? {
                  ...step,
                  label: `Waiting for approval: ${displayName}`,
                  status: 'waiting' as const
                }
              : step
          )
        }
      }
      return current
    })
  }

  function finishRunActivity(runId: string, outcome: RunActivityOutcome): void {
    setRunActivity((current) => {
      if (current === null || current.runId !== runId) {
        return current
      }

      return {
        ...current,
        steps: current.steps.map((step) =>
          step.status === 'running' || step.status === 'waiting'
            ? {
                ...step,
                status:
                  outcome === 'failed' || outcome === 'limit'
                    ? ('failed' as const)
                    : ('completed' as const)
              }
            : step
        ),
        phase: 'done',
        outcome,
        endedAt: Date.now()
      }
    })
    setActivityExpanded(false)
  }

  async function createConversation(): Promise<void> {
    if (backendStatus !== 'ready' || isCreatingConversation) {
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
    } catch {
      setErrorMessage('A new conversation could not be created.')
    } finally {
      setIsCreatingConversation(false)
    }
  }

  function startRename(conversation: ConversationSummary): void {
    if (backendStatus !== 'ready') {
      return
    }

    setRenamingConversationId(conversation.conversation_id)
    setRenameDraft(conversationLabel(conversation.title))
    setErrorMessage(null)
  }

  function cancelRename(): void {
    setRenamingConversationId(null)
    setRenameDraft('')
  }

  async function saveRename(conversationId: string): Promise<void> {
    if (renamingConversationId !== conversationId) {
      return
    }

    const trimmed = renameDraft.trim()
    const current = conversations.find(
      (conversation) => conversation.conversation_id === conversationId
    )

    if (!trimmed || current === undefined) {
      cancelRename()
      return
    }

    if (conversationLabel(current.title) === trimmed) {
      cancelRename()
      return
    }

    try {
      const updated = await window.desktop.updateConversationTitle(conversationId, trimmed)
      setConversations((items) =>
        items.map((conversation) =>
          conversation.conversation_id === conversationId ? updated : conversation
        )
      )
      cancelRename()
    } catch {
      setErrorMessage('The conversation could not be renamed.')
      cancelRename()
    }
  }

  async function deleteConversation(conversationId: string): Promise<void> {
    if (isCreatingConversation || isSubmittingMessage) {
      return
    }

    if (!window.confirm(CONVERSATION_DELETE_CONFIRM)) {
      return
    }

    setErrorMessage(null)

    try {
      if (activeRun?.conversationId === conversationId) {
        await window.desktop.cancelRun(activeRun.runId)
        setActiveRun(null)
        setIsCancellingRun(false)
        setRunActivity(null)
        setActivityExpanded(false)
      }

      if (pendingApproval?.conversation_id === conversationId) {
        setPendingApproval(null)
        setIsDecidingApproval(false)
      }

      await window.desktop.deleteConversation(conversationId)

      setConversations((items) => {
        const next = items.filter((conversation) => conversation.conversation_id !== conversationId)

        if (selectedConversationId === conversationId) {
          setSelectedConversationId(next[0]?.conversation_id ?? null)
          setMessages([])
        }

        return next
      })

      if (renamingConversationId === conversationId) {
        cancelRename()
      }
    } catch {
      setErrorMessage('The conversation could not be deleted.')
    }
  }

  async function deleteBrowserConversation(conversationId: string): Promise<void> {
    if (isCreatingConversation || isSubmittingMessage) {
      return
    }

    if (!window.confirm(CONVERSATION_DELETE_CONFIRM)) {
      return
    }

    setErrorMessage(null)

    try {
      if (activeRun?.conversationId === conversationId) {
        await window.desktop.cancelRun(activeRun.runId)
        setActiveRun(null)
        setIsCancellingRun(false)
        setRunActivity(null)
        setActivityExpanded(false)
      }

      if (pendingApproval?.conversation_id === conversationId) {
        setPendingApproval(null)
        setIsDecidingApproval(false)
      }

      await window.desktop.deleteBrowserConversation(conversationId)

      setBrowserConversations((items) =>
        items.filter((conversation) => conversation.conversation_id !== conversationId)
      )
      setBrowserConversationByTabId((current) => {
        const next: Record<string, string> = {}
        for (const [tabId, boundId] of Object.entries(current)) {
          if (boundId === conversationId) {
            void window.desktop.setBrowserTabConversation(tabId, null).catch(() => undefined)
            continue
          }
          next[tabId] = boundId
        }
        return next
      })
      if (selectedBrowserConversationId === conversationId) {
        browserMessageLoadIdRef.current += 1
        setBrowserMessages([])
      }
    } catch {
      setErrorMessage('The conversation could not be deleted.')
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
      setEditingMessageId(null)
      setActiveRun({
        runId: submitted.run.run_id,
        conversationId,
        status: 'running'
      })
      setRunActivity({
        runId: submitted.run.run_id,
        conversationId,
        steps: [{ id: 'start', label: 'Starting…', detail: null, status: 'running' }],
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

  function beginMessageEdit(message: ConversationMessage): void {
    if (backendStatus !== 'ready') {
      return
    }

    setDraft(message.content)
    setEditingMessageId(message.message_id)
    setErrorMessage(null)
    window.requestAnimationFrame(() => composerInputRef.current?.focus())
  }

  function cancelMessageEdit(): void {
    setEditingMessageId(null)
    setDraft('')
  }

  function beginBrowserMessageEdit(message: ConversationMessage): void {
    if (backendStatus !== 'ready') return
    setBrowserDraft(message.content)
    setBrowserEditingMessageId(message.message_id)
    setErrorMessage(null)
    window.requestAnimationFrame(() => browserAgentInputRef.current?.focus())
  }

  function cancelBrowserMessageEdit(): void {
    setBrowserEditingMessageId(null)
    setBrowserDraft('')
  }

  async function copyMessage(message: ConversationMessage): Promise<void> {
    try {
      await window.desktop.copyText(message.content)
      setCopiedMessageId(message.message_id)
      if (copyFeedbackTimerRef.current !== null) {
        window.clearTimeout(copyFeedbackTimerRef.current)
      }
      copyFeedbackTimerRef.current = window.setTimeout(() => {
        setCopiedMessageId((current) => (current === message.message_id ? null : current))
        copyFeedbackTimerRef.current = null
      }, 1_500)
    } catch {
      setErrorMessage('The message could not be copied.')
    }
  }

  async function cancelActiveRun(): Promise<void> {
    if (activeRun === null || isCancellingRun) {
      return
    }

    setIsCancellingRun(true)
    setRunActivityWaiting(activeRun.runId, 'Stopping…', null)

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
      setRunActivityWaiting(
        approval.run_id,
        decision === 'deny'
          ? 'Tool denied. Continuing…'
          : decision === 'allow_conversation' && approval.tool_id.startsWith('filesystem.')
            ? 'File changes are allowed for this conversation. Continuing…'
            : `Using ${approval.display_name}…`,
        null
      )
      setPendingApproval(null)
    } catch {
      setErrorMessage('Tool approval decision could not be sent.')
    } finally {
      setIsDecidingApproval(false)
    }
  }

  async function undoFileChange(change: FileChange): Promise<void> {
    if (change.status !== 'applied' || undoingChangeId !== null) {
      return
    }
    setUndoingChangeId(change.change_id)
    setUndoErrorChangeId(null)
    try {
      const reverted = await window.desktop.undoFileChange(change.change_id, change.path)
      setFileChanges((current) =>
        current.map((item) => (item.change_id === reverted.change_id ? reverted : item))
      )
    } catch {
      setUndoErrorChangeId(change.change_id)
      if (selectedConversationId !== null) {
        void window.desktop
          .listConversationFileChanges(selectedConversationId)
          .then(setFileChanges)
          .catch(() => undefined)
      }
    } finally {
      setUndoingChangeId(null)
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

  function handleAppLanguageChange(lang: AppLanguage): void {
    setAppLanguage(lang)
    try {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, lang)
    } catch {
      // Ignore storage write error
    }
  }

  function handleToggleWebSearch(): void {
    if (tavilySettings !== null && !tavilySettings.enabled && !tavilySettings.api_key_saved) {
      setErrorMessage('Web search requires a Tavily API key. Configure it in Preferences.')
      return
    }
    setWebSearchEnabled((prev) => {
      const next = !prev
      localStorage.setItem('asagent.webSearchEnabled', String(next))
      return next
    })
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
    const detectedPreset = detectProviderPreset(status.base_url, status.location)
    setSelectedProviderId(detectedPreset)
    setModelLocation(status.location ?? 'external')
    setModelName(status.model ?? '')
    setModelBaseUrl(status.base_url ?? '')
    setModelApiKey('')
    setModelActionError(null)
    setRestartRequested(true)
    setProviderDrafts({})
  }

  function handleProviderPresetChange(presetId: string): void {
    if (isModelBusy) {
      return
    }

    setProviderDrafts((prev) => ({
      ...prev,
      [selectedProviderId]: {
        model: modelName,
        baseUrl: modelBaseUrl,
        apiKey: modelApiKey
      }
    }))

    setSelectedProviderId(presetId)
    setModelActionError(null)

    const saved = modelSettings?.saved_providers?.[presetId]
    const isTargetActive =
      modelSettings !== null &&
      modelSettings.configured &&
      detectProviderPreset(modelSettings.base_url, modelSettings.location) === presetId

    const preset = getProviderPreset(presetId)
    if (saved) {
      setModelLocation(saved.location)
      setModelName(saved.model)
      setModelBaseUrl(saved.base_url)
      setModelApiKey('')
    } else if (isTargetActive) {
      setModelLocation(modelSettings.location ?? preset.location)
      setModelName(modelSettings.model ?? '')
      setModelBaseUrl(modelSettings.base_url ?? preset.defaultBaseUrl)
      setModelApiKey('')
    } else {
      const draft = providerDrafts[presetId]
      if (draft) {
        setModelLocation(preset.location)
        setModelName(draft.model)
        setModelBaseUrl(draft.baseUrl || preset.defaultBaseUrl)
        setModelApiKey(draft.apiKey)
      } else {
        setModelLocation(preset.location)
        setModelName('')
        setModelBaseUrl(preset.defaultBaseUrl)
        setModelApiKey('')
      }
    }
  }

  function handleModelLocationChange(location: 'local' | 'external'): void {
    if (isModelBusy || location === modelLocation) {
      return
    }

    setModelLocation(location)
    setModelActionError(null)
  }

  async function handleSaveModelSettings(): Promise<void> {
    if (isModelBusy) {
      return
    }
    if (!modelName.trim() || !modelBaseUrl.trim()) {
      setModelActionError(MODEL_SETTINGS_REQUIRED)
      return
    }
    if (modelLocation === 'external' && !isCurrentPresetApiKeySaved && !modelApiKey.trim()) {
      setModelActionError(MODEL_SETTINGS_EXTERNAL_KEY_REQUIRED)
      return
    }

    setIsModelBusy(true)
    setModelActionError(null)
    try {
      applyModelStatus(
        await window.desktop.saveModelSettings({
          location: modelLocation,
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

  async function handleSaveAgentSettings(): Promise<void> {
    if (isAgentBusy) {
      return
    }

    const parsed = Number(agentMaxSteps)
    if (!Number.isInteger(parsed) || parsed < 1 || parsed > 50) {
      setAgentActionError(AGENT_SETTINGS_REQUIRED)
      return
    }

    setIsAgentBusy(true)
    setAgentActionError(null)
    try {
      const status = await window.desktop.saveAgentSettings({ maxSteps: parsed })
      setAgentSettings(status)
      setAgentMaxSteps(String(status.max_steps))
      setRestartRequested(true)
    } catch {
      setAgentActionError(AGENT_SETTINGS_UPDATE_ERROR)
    } finally {
      setIsAgentBusy(false)
    }
  }

  async function handleSaveStorageRetention(days: number): Promise<void> {
    if (isStorageBusy) {
      return
    }

    setIsStorageBusy(true)
    setStorageActionError(null)
    setStorageActionSuccess(null)
    try {
      const status = await window.desktop.saveStorageSettings({ snapshot_retention_days: days })
      setStorageSettings(status)
      setStorageRetentionDays(status.snapshot_retention_days)
      setStorageActionSuccess('Snapshot retention saved.')
    } catch {
      setStorageActionError(STORAGE_SETTINGS_UPDATE_ERROR)
    } finally {
      setIsStorageBusy(false)
    }
  }

  async function handleClearStorageSnapshots(): Promise<void> {
    if (isStorageBusy) {
      return
    }

    if (!window.confirm(STORAGE_CLEAR_CONFIRM)) {
      return
    }

    setIsStorageBusy(true)
    setStorageActionError(null)
    setStorageActionSuccess(null)
    try {
      const result = await window.desktop.clearStorageSnapshots()
      const status = await window.desktop.getStorageSettings()
      setStorageSettings(status)
      setStorageActionSuccess(
        `Cleared ${formatBytes(result.freed_bytes)} (${result.deleted_count} snapshot${result.deleted_count === 1 ? '' : 's'} removed).`
      )
    } catch {
      setStorageActionError('Failed to clear snapshots.')
    } finally {
      setIsStorageBusy(false)
    }
  }

  async function handleManualCheckForUpdates(): Promise<void> {
    if (isCheckingUpdate) {
      return
    }

    setIsCheckingUpdate(true)
    setUpdateCheckError(null)
    try {
      const result = await window.desktop.checkForUpdates()
      setUpdateResult(result)
    } catch {
      setUpdateCheckError(t(appLanguage, 'checkUpdateFailed'))
    } finally {
      setIsCheckingUpdate(false)
    }
  }

  async function handleAddWorkspacePath(): Promise<void> {
    if (isWorkspaceBusy || workspaceSettings === null || selectedConversationId === null) {
      return
    }

    const selectedPaths = await window.desktop.chooseWorkspacePath()
    if (selectedPaths.length === 0) {
      return
    }

    const nextRoots = [...workspaceSettings.additional_roots]
    const nextFiles = [...workspaceSettings.additional_files]

    for (const item of selectedPaths) {
      if (item.kind === 'directory' && !nextRoots.includes(item.path)) {
        nextRoots.push(item.path)
      } else if (item.kind === 'file' && !nextFiles.includes(item.path)) {
        nextFiles.push(item.path)
      }
    }

    if (
      nextRoots.length === workspaceSettings.additional_roots.length &&
      nextFiles.length === workspaceSettings.additional_files.length
    ) {
      return
    }

    setIsWorkspaceBusy(true)
    try {
      setWorkspaceSettings(
        await window.desktop.saveConversationFileAccess(selectedConversationId, {
          additionalFiles: nextFiles,
          additionalRoots: nextRoots
        })
      )
    } catch {
      setErrorMessage('File access settings could not be updated.')
    } finally {
      setIsWorkspaceBusy(false)
    }
  }

  async function handleRemoveWorkspacePath(
    pathToRemove: string,
    kind: 'directory' | 'file'
  ): Promise<void> {
    if (isWorkspaceBusy || workspaceSettings === null || selectedConversationId === null) {
      return
    }

    setIsWorkspaceBusy(true)
    try {
      setWorkspaceSettings(
        await window.desktop.saveConversationFileAccess(selectedConversationId, {
          additionalFiles:
            kind === 'file'
              ? workspaceSettings.additional_files.filter((path) => path !== pathToRemove)
              : workspaceSettings.additional_files,
          additionalRoots:
            kind === 'directory'
              ? workspaceSettings.additional_roots.filter((path) => path !== pathToRemove)
              : workspaceSettings.additional_roots
        })
      )
    } catch {
      setErrorMessage('File access settings could not be updated.')
    } finally {
      setIsWorkspaceBusy(false)
    }
  }

  useEffect(() => {
    if (!workspaceSettings || workspaceSettings.additional_roots.length === 0) {
      setWorkspaceTrees({})
      setSelectedPreviewFile(null)
      setFilePreview(null)
      return
    }

    const roots = workspaceSettings.additional_roots
    let cancelled = false

    setExpandedFolders((current) => {
      const next = new Set(current)
      for (const root of roots) {
        next.add(root)
      }
      return next
    })

    async function loadTrees(): Promise<void> {
      setIsTreeLoading(true)
      const results: Record<string, WorkspaceFileNode | null> = {}
      for (const root of roots) {
        try {
          const tree = await window.desktop.listWorkspaceTree(root, 3)
          if (!cancelled) {
            results[root] = tree
          }
        } catch {
          if (!cancelled) {
            results[root] = null
          }
        }
      }
      if (!cancelled) {
        setWorkspaceTrees(results)
        setIsTreeLoading(false)
      }
    }

    void loadTrees()

    if (selectedPreviewFile) {
      void window.desktop.readFilePreview(selectedPreviewFile, 100 * 1024).then((result) => {
        if (!cancelled && result) {
          setFilePreview(result)
        }
      })
    }

    return () => {
      cancelled = true
    }
  }, [workspaceSettings, workspaceTreeVersion, fileChanges, selectedPreviewFile])

  async function handleSelectFileForPreview(filePath: string): Promise<void> {
    if (selectedPreviewFile === filePath) {
      setSelectedPreviewFile(null)
      setFilePreview(null)
      return
    }

    setSelectedPreviewFile(filePath)
    setIsPreviewLoading(true)
    try {
      const result = await window.desktop.readFilePreview(filePath, 100 * 1024)
      setFilePreview(result)
    } catch {
      setFilePreview(null)
    } finally {
      setIsPreviewLoading(false)
    }
  }

  function handleToggleFolder(folderPath: string): void {
    setExpandedFolders((current) => {
      const next = new Set(current)
      if (next.has(folderPath)) {
        next.delete(folderPath)
      } else {
        next.add(folderPath)
      }
      return next
    })
  }

  function handleQuoteInChat(fileName: string): void {
    setDraft((prev) => (prev ? `${prev} @${fileName}` : `@${fileName} `))
    composerInputRef.current?.focus()
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

  function createNewChatSession(): void {
    if (backendStatus !== 'ready' || isCreatingConversation) {
      return
    }
    setActiveView('chat')
    void createConversation()
  }
  createNewChatSessionRef.current = createNewChatSession

  function createNewBrowserSession(): void {
    if (backendStatus !== 'ready' || isCreatingConversation) {
      return
    }
    setActiveView('browser')
    const currentTabs = browserTabsRef.current
    for (const tab of currentTabs) {
      void window.desktop.closeBrowserTab(tab.id).catch(() => undefined)
    }

    const created = createBrowserTab()
    setBrowserTabs([created])
    setActiveBrowserTabId(created.id)
    setBrowserConversationByTabId({})
    setBrowserError(null)

    setIsCreatingConversation(true)
    setErrorMessage(null)
    void window.desktop
      .createBrowserConversation()
      .then((newConv) => {
        setBrowserConversations((current) => orderConversations([newConv, ...current]))
        browserMessageLoadIdRef.current += 1
        setBrowserMessages([])
        setBrowserConversationByTabId({ [created.id]: newConv.conversation_id })
        void window.desktop
          .setBrowserTabConversation(created.id, newConv.conversation_id)
          .catch(() => undefined)
        setBrowserDraft('')
      })
      .catch(() => {
        setErrorMessage('The conversation could not be created.')
      })
      .finally(() => {
        setIsCreatingConversation(false)
      })
  }

  function toggleAutomationPreview(automationId: string): void {
    const current = automationPreviews.find((automation) => automation.id === automationId)
    if (current === undefined) return
    const status = current.status === 'active' ? 'paused' : 'active'
    void window.desktop.updateAutomationStatus(automationId, status).then((saved) => {
      setAutomationPreviews((values) =>
        values.map((value) =>
          value.id === automationId ? { ...value, status: saved.status } : value
        )
      )
    })
  }

  function deleteAutomation(automationId: string): void {
    if (isAutomationCreating) return
    if (!window.confirm('Delete this scheduled task and its execution history?')) return
    discardAutomationDraft()
    void window.desktop
      .deleteAutomation(automationId)
      .then(() => {
        setAutomationPreviews((current) =>
          current.filter((automation) => automation.id !== automationId)
        )
        setSelectedAutomationId((current) => (current === automationId ? null : current))
        setEditingAutomationId((current) => (current === automationId ? null : current))
      })
      .catch(() => setAutomationLoadError('The scheduled task could not be deleted.'))
  }

  function discardAutomationDraft(): void {
    if (isAutomationCreating) return
    const conversationId = automationDraftConversationIdRef.current
    automationDraftConversationIdRef.current = null
    automationDraftRunIdRef.current = null
    automationDraftTargetIdRef.current = null
    automationDraftKnownVersionsRef.current = new Map()
    editingAutomationIdRef.current = null
    setAutomationDraftConversationId(null)
    setAutomationDraftMessages([])
    setAutomationPlannerNeedsInput(false)
    setAutomationCreateStatus(null)
    setAutomationInlineInput('')
    setEditingAutomationId(null)
    if (conversationId !== null) {
      void window.desktop.deleteAutomationDraft(conversationId).catch(() => undefined)
    }
  }

  async function submitAutomationInline(event?: React.FormEvent<HTMLFormElement>): Promise<void> {
    if (event) event.preventDefault()
    const content = automationInlineInput.trim()
    if (!content || isAutomationCreating) return
    setIsAutomationCreating(true)
    setAutomationPlannerNeedsInput(false)
    setAutomationCreateStatus(t(appLanguage, 'planningScheduledTask'))
    setAutomationLoadError(null)
    try {
      let conversationId = automationDraftConversationIdRef.current
      if (conversationId === null) {
        const targetAutomationId = editingAutomationIdRef.current
        automationDraftTargetIdRef.current = targetAutomationId
        automationDraftKnownVersionsRef.current = new Map(automationUpdatedAtByIdRef.current)
        const conversation = await window.desktop.createAutomationDraft(
          targetAutomationId ?? undefined,
          Intl.DateTimeFormat().resolvedOptions().timeZone
        )
        conversationId = conversation.conversation_id
        automationDraftConversationIdRef.current = conversationId
        setAutomationDraftConversationId(conversationId)
        setAutomationDraftMessages([])
      }
      const submitted = await window.desktop.submitAutomationDraftMessage(conversationId, content)
      automationDraftRunIdRef.current = submitted.run.run_id
      setAutomationInlineInput('')
      setAutomationDraftMessages(await window.desktop.listAutomationDraftMessages(conversationId))
    } catch {
      setIsAutomationCreating(false)
      setAutomationPlannerNeedsInput(false)
      setAutomationCreateStatus(null)
      setAutomationLoadError('Failed to create or update the scheduled task.')
    }
  }

  function startEditingAutomation(automationId: string): void {
    if (isAutomationCreating) return
    const target = automationPreviews.find((a) => a.id === automationId)
    if (!target) return
    discardAutomationDraft()
    editingAutomationIdRef.current = automationId
    setEditingAutomationId(automationId)
    setIsCreatingNewTask(true)
    setAutomationInlineInput(`Update "${target.name}": `)
  }

  function startCreatingAutomation(): void {
    if (isAutomationCreating) return
    discardAutomationDraft()
    editingAutomationIdRef.current = null
    setEditingAutomationId(null)
    setIsCreatingNewTask(true)
  }

  function runAutomationNow(automationId: string): void {
    if (isAutomationRunningNow) return
    setIsAutomationRunningNow(true)
    setAutomationRunNowMessage('Starting execution…')
    void window.desktop
      .runAutomationNow(automationId)
      .then(async (started) => {
        setAutomationRunNowMessage('Execution running. Waiting for results…')
        setSelectedExecutionId(started.automation_execution_id)
        setIsExecutionMessagesLoading(true)
        for (let attempt = 0; attempt < 120; attempt += 1) {
          await new Promise<void>((resolve) => window.setTimeout(resolve, 1000))
          const executions = await window.desktop.listAutomationExecutions(automationId)
          setAutomationExecutions(executions)
          const target =
            executions.find((e) => e.automation_execution_id === started.automation_execution_id) ??
            executions[0]
          if (target !== undefined && target.status !== 'claimed') {
            setAutomationRunNowMessage(
              target.status === 'completed'
                ? 'Execution completed successfully.'
                : `Execution finished with status: ${target.status}.`
            )
            setSelectedExecutionId(target.automation_execution_id)
            const messages = await window.desktop.getAutomationExecutionMessages(
              automationId,
              target.automation_execution_id
            )
            setExecutionMessages(messages)
            setIsExecutionMessagesLoading(false)
            return
          }
        }
        setAutomationRunNowMessage(
          'Execution is taking longer than expected. It will complete in the background.'
        )
      })
      .catch(() => {
        setAutomationRunNowMessage(null)
        setAutomationLoadError('The scheduled task could not be started.')
      })
      .finally(() => {
        setIsAutomationRunningNow(false)
        setIsExecutionMessagesLoading(false)
      })
  }

  function selectExecutionHistory(executionId: string): void {
    if (selectedAutomation === null) return
    setSelectedExecutionId(executionId)
    setIsExecutionMessagesLoading(true)
    window.desktop
      .getAutomationExecutionMessages(selectedAutomation.id, executionId)
      .then((messages) => {
        setExecutionMessages(messages)
      })
      .catch(() => {
        setExecutionMessages([])
      })
      .finally(() => setIsExecutionMessagesLoading(false))
  }

  function copyExecutionOutput(text: string): void {
    void window.desktop.copyText(text)
    setHasCopiedOutput(true)
    if (copyFeedbackTimerRef.current !== null) {
      window.clearTimeout(copyFeedbackTimerRef.current)
    }
    copyFeedbackTimerRef.current = window.setTimeout(() => {
      setHasCopiedOutput(false)
    }, 2000)
  }

  function setAttentionPanelOpen(open: boolean): void {
    const next = { ...desktopLayoutRef.current, attentionPanelOpen: open }
    desktopLayoutRef.current = next
    setDesktopLayout(next)
    saveDesktopLayout(next)
  }

  function closeAttentionPanel(): void {
    setAttentionPanelOpen(false)
  }

  function openAttentionPanel(): void {
    setAttentionPanelOpen(true)
  }

  function setBrowserAgentPanelOpen(open: boolean): void {
    const next = { ...desktopLayoutRef.current, browserAgentPanelOpen: open }
    desktopLayoutRef.current = next
    setDesktopLayout(next)
    saveDesktopLayout(next)
  }

  function bindBrowserConversationToActiveTab(conversationId: string): void {
    const tabId = activeBrowserTabId
    setBrowserConversationByTabId((current) =>
      current[tabId] === conversationId ? current : { ...current, [tabId]: conversationId }
    )
    void window.desktop.setBrowserTabConversation(tabId, conversationId).catch(() => undefined)
  }

  function openBrowserConversation(conversationId: string): void {
    const currentTabs = browserTabsRef.current
    const conversation = browserConversations.find(
      (candidate) => candidate.conversation_id === conversationId
    )
    if (conversation === undefined) {
      setErrorMessage('The conversation could not be opened.')
      return
    }
    const boundTab = currentTabs.find(
      (tab) => browserConversationByTabId[tab.id] === conversationId
    )
    if (boundTab !== undefined) {
      selectBrowserTab(boundTab.id)
      return
    }

    for (const tab of currentTabs) {
      void window.desktop.closeBrowserTab(tab.id).catch(() => undefined)
    }

    const created = createBrowserTab()
    if (conversation.last_page_url !== null) {
      created.address = conversation.last_page_url
      created.title = conversation.last_page_title ?? browserTabTitle(conversation.last_page_url)
    }
    setBrowserTabs([created])
    setBrowserConversationByTabId({
      [created.id]: conversationId
    })
    setActiveBrowserTabId(created.id)
    setBrowserError(null)
    void window.desktop
      .setBrowserTabConversation(created.id, conversationId)
      .catch(() => setErrorMessage('The conversation could not be opened.'))
    if (conversation.last_page_url !== null) {
      void window.desktop.navigateBrowser(created.id, conversation.last_page_url).catch((error) => {
        setBrowserError(browserNavigationError(error))
      })
    }
  }

  async function createBrowserConversationForActiveTab(): Promise<void> {
    if (backendStatus !== 'ready' || isCreatingConversation) {
      return
    }

    setIsCreatingConversation(true)
    setErrorMessage(null)
    try {
      const created = await window.desktop.createBrowserConversation()
      setBrowserConversations((current) => orderConversations([created, ...current]))
      browserMessageLoadIdRef.current += 1
      setBrowserMessages([])
      bindBrowserConversationToActiveTab(created.conversation_id)
      setBrowserDraft('')
    } catch {
      setErrorMessage('The conversation could not be created.')
    } finally {
      setIsCreatingConversation(false)
    }
  }

  async function submitBrowserMessage(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    const content = browserDraft
    const tabId = activeBrowserTabId
    if (!content.trim() || isBusy) {
      return
    }

    setIsSubmittingMessage(true)
    setErrorMessage(null)

    try {
      let conversationId = browserConversationByTabId[tabId] ?? selectedBrowserConversationId
      if (conversationId === null) {
        const created = await window.desktop.createBrowserConversation()
        conversationId = created.conversation_id
        setBrowserConversations((current) => orderConversations([created, ...current]))
        bindBrowserConversationToActiveTab(conversationId)
      }

      const submitted = await window.desktop.submitBrowserMessage(conversationId, content, tabId)
      if (selectedBrowserConversationIdRef.current === conversationId) {
        browserMessageLoadIdRef.current += 1
        setBrowserMessages((current) => [...current, submitted.message])
      }
      setBrowserConversations((current) =>
        orderConversations(
          current.map((conversation) =>
            conversation.conversation_id === submitted.conversation.conversation_id
              ? submitted.conversation
              : conversation
          )
        )
      )
      setBrowserDraft('')
      setBrowserEditingMessageId(null)
      setActiveRun({
        runId: submitted.run.run_id,
        conversationId,
        status: 'running'
      })
      setRunActivity({
        runId: submitted.run.run_id,
        conversationId,
        steps: [{ id: 'start', label: 'Starting…', detail: null, status: 'running' }],
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

  function ContextPanelExpandButton(): React.JSX.Element | null {
    if (desktopLayout.attentionPanelOpen) {
      return null
    }

    return (
      <button
        aria-label="Expand context panel"
        className="panel-expand-btn"
        onClick={openAttentionPanel}
        title="Expand context panel"
        type="button"
      >
        <ContextPanelIcon direction="expand" />
      </button>
    )
  }

  function CenterPageHeader({
    children,
    subtitle,
    title
  }: {
    children?: React.ReactNode
    subtitle: string
    title: string
  }): React.JSX.Element {
    return (
      <div className="center-header">
        <div className="center-header-main">
          <div className="center-title">{title}</div>
          <div className="center-sub">{subtitle}</div>
          {children}
        </div>
        <ContextPanelExpandButton />
      </div>
    )
  }

  function AttentionAside({
    actions,
    children,
    header
  }: {
    actions?: React.ReactNode
    children: React.ReactNode
    header?: React.ReactNode
  }): React.JSX.Element {
    return (
      <aside className="attn">
        <div className="attn-top">
          {header !== undefined ? <div className="attn-top-main">{header}</div> : null}
          <div className="attn-top-actions">
            {actions}
            <button
              aria-label="Collapse context panel"
              className="attention-panel-close"
              onClick={closeAttentionPanel}
              title="Collapse context panel"
              type="button"
            >
              <ContextPanelIcon direction="collapse" />
            </button>
          </div>
        </div>
        {children}
      </aside>
    )
  }

  function WorkspaceTreeNodeItem({
    node,
    depth = 0
  }: {
    node: WorkspaceFileNode
    depth?: number
  }): React.JSX.Element {
    const isExpanded = expandedFolders.has(node.path)
    const isSelected = selectedPreviewFile === node.path

    if (node.kind === 'directory') {
      return (
        <div className="workspace-tree-dir" key={node.path}>
          <button
            className="workspace-tree-row workspace-tree-dir-btn"
            onClick={() => handleToggleFolder(node.path)}
            style={{ paddingLeft: `${6 + depth * 12}px` }}
            title={node.path}
            type="button"
          >
            <TreeChevron isExpanded={isExpanded} />
            <TreeIcon isExpanded={isExpanded} kind="directory" />
            <span className="workspace-tree-name">{node.name}</span>
          </button>
          {isExpanded && node.children && node.children.length > 0 ? (
            <div className="workspace-tree-children">
              {node.children.map((child) => (
                <WorkspaceTreeNodeItem depth={depth + 1} key={child.path} node={child} />
              ))}
            </div>
          ) : isExpanded && node.children && node.children.length === 0 ? (
            <div
              className="workspace-tree-empty-sub"
              style={{ paddingLeft: `${22 + depth * 12}px` }}
            >
              {t(appLanguage, 'emptyDirectory')}
            </div>
          ) : null}
        </div>
      )
    }

    return (
      <div
        className={`workspace-tree-row workspace-tree-file-row${isSelected ? ' is-selected' : ''}`}
        key={node.path}
        style={{ paddingLeft: `${18 + depth * 12}px` }}
      >
        <button
          className="workspace-tree-file-btn"
          onClick={() => void handleSelectFileForPreview(node.path)}
          title={`${t(appLanguage, 'previewFile')} ${node.name}`}
          type="button"
        >
          <TreeIcon extension={node.extension} kind="file" />
          <span className="workspace-tree-name">{node.name}</span>
          {node.size !== undefined ? (
            <span className="workspace-tree-size">{formatBytes(node.size)}</span>
          ) : null}
        </button>
        <div className="workspace-tree-actions">
          <button
            aria-label={t(appLanguage, 'quoteInChat')}
            className="workspace-tree-action-btn"
            onClick={() => handleQuoteInChat(node.name)}
            title={t(appLanguage, 'quoteInPrompt')}
            type="button"
          >
            <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </button>
          <button
            aria-label={t(appLanguage, 'revealInFinder')}
            className="workspace-tree-action-btn"
            onClick={() => void window.desktop.revealInFinder(node.path)}
            title={t(appLanguage, 'revealInFinder')}
            type="button"
          >
            <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
              <polyline points="15 3 21 3 21 9" />
              <line x1="10" x2="21" y1="14" y2="3" />
            </svg>
          </button>
        </div>
      </div>
    )
  }

  function renderPlaceholderView(title: string, subtitle: string): React.JSX.Element {
    return (
      <>
        <section className="center">
          <CenterPageHeader subtitle={subtitle} title={title} />
          <div className="placeholder-banner">
            This area is a visual placeholder. The feature is not implemented yet.
          </div>
        </section>
        <AttentionAside header={<div className="attn-header">Coming soon</div>}>
          <p className="chat-context-sub">
            Connected data, schedule details, and controls for {title.toLowerCase()} will appear
            here.
          </p>
        </AttentionAside>
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
          isAttentionPanelVisible ? ' attention-open' : ' attention-collapsed'
        }${activeView === 'browser' ? ' browser-active' : ''}${
          resizingColumn === null ? '' : ' is-resizing'
        }`}
        style={
          {
            '--rail-width': `${railWidth}px`,
            '--thread-width': `${desktopLayout.threadWidth}px`,
            '--attention-width': `${desktopLayout.attentionWidth}px`,
            '--automations-master-width': `${desktopLayout.automationsMasterWidth}px`
          } as CSSProperties
        }
      >
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
          <div aria-hidden="true" className="rail-window-controls" />
          <div className="rail-section rail-actions-section">
            <button
              className="rail-new-btn is-chat"
              disabled={backendStatus !== 'ready' || isCreatingConversation}
              onClick={createNewChatSession}
              title={t(appLanguage, 'newChat')}
              type="button"
            >
              <Icon className="rail-icon" path="M12 5v14M5 12h14" />
              <span className="rail-item-label">{t(appLanguage, 'newChat')}</span>
            </button>
            <button
              className="rail-new-btn is-browser"
              disabled={backendStatus !== 'ready' || isCreatingConversation}
              onClick={createNewBrowserSession}
              title={t(appLanguage, 'newBrowser')}
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
                <path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18" />
              </svg>
              <span className="rail-item-label">{t(appLanguage, 'newBrowser')}</span>
            </button>
          </div>

          <div className="rail-section rail-automation-section">
            <button
              className={railItemClass('automations')}
              onClick={() => {
                setActiveView('automations')
              }}
              title={t(appLanguage, 'automationsTitle')}
              type="button"
            >
              <svg
                className="rail-icon"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <circle cx="12" cy="12" r="9" />
                <path d="M12 7v5l3 3" />
              </svg>
              <span className="rail-item-label">{t(appLanguage, 'automationsTitle')}</span>
              <span className="rail-count">{automationPreviews.length}</span>
            </button>
          </div>

          <div className="rail-section rail-recents">
            <div className="rail-recents-header">
              <div className="rail-label">{t(appLanguage, 'recents')}</div>
            </div>
            <div
              className={`rail-recents-list${
                visibleScrollbar === 'recents' ? ' scrollbar-visible' : ''
              }`}
              onWheel={() => revealScrollbar('recents')}
            >
              {recentConversations.length === 0 ? (
                <p className="rail-recents-empty">{t(appLanguage, 'noRecents')}</p>
              ) : (
                recentConversations.map(({ kind, conversation }) => {
                  const selected =
                    kind === 'chat'
                      ? activeView === 'chat' &&
                        conversation.conversation_id === selectedConversationId
                      : activeView === 'browser' &&
                        conversation.conversation_id === selectedBrowserConversationId
                  const renaming =
                    kind === 'chat' && renamingConversationId === conversation.conversation_id

                  return (
                    <div
                      className={`rail-recent-item${selected ? ' active' : ''}${
                        renaming ? ' renaming' : ''
                      }`}
                      key={`${kind}:${conversation.conversation_id}`}
                    >
                      {renaming ? (
                        <input
                          ref={renameInputRef}
                          className="rail-recent-rename"
                          onBlur={() => void saveRename(conversation.conversation_id)}
                          onChange={(event) => setRenameDraft(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter') {
                              event.preventDefault()
                              void saveRename(conversation.conversation_id)
                            }
                            if (event.key === 'Escape') {
                              event.preventDefault()
                              cancelRename()
                            }
                          }}
                          type="text"
                          value={renameDraft}
                        />
                      ) : (
                        <>
                          <button
                            className="rail-recent-body"
                            disabled={backendStatus !== 'ready'}
                            onClick={() => {
                              if (kind === 'chat') {
                                setActiveView('chat')
                                setSelectedConversationId(conversation.conversation_id)
                              } else {
                                setActiveView('browser')
                                openBrowserConversation(conversation.conversation_id)
                              }
                            }}
                            title={
                              kind === 'browser' && conversation.last_page_url !== null
                                ? conversation.last_page_url
                                : conversationLabel(conversation.title, appLanguage)
                            }
                            type="button"
                          >
                            {kind === 'chat' ? (
                              <Icon
                                className="rail-recent-kind is-chat"
                                path="M21 11.5a8.5 8.5 0 0 1-12.3 7.6L3 21l1.9-5.7A8.5 8.5 0 1 1 21 11.5Z"
                              />
                            ) : (
                              <svg
                                aria-hidden="true"
                                className="rail-recent-kind is-browser"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                viewBox="0 0 24 24"
                              >
                                <circle cx="12" cy="12" r="9" />
                                <path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18" />
                              </svg>
                            )}
                            <span className="rail-recent-title">
                              {conversationLabel(conversation.title, appLanguage)}
                            </span>
                            <time className="rail-recent-time" dateTime={conversation.updated_at}>
                              {formatThreadTime(conversation.updated_at)}
                            </time>
                          </button>
                          <div className="rail-recent-actions">
                            {kind === 'chat' ? (
                              <button
                                aria-label={t(appLanguage, 'rename')}
                                disabled={backendStatus !== 'ready'}
                                onClick={() => startRename(conversation)}
                                title={t(appLanguage, 'rename')}
                                type="button"
                              >
                                <Icon path="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4Z" />
                              </button>
                            ) : null}
                            <button
                              aria-label={t(appLanguage, 'delete')}
                              className="danger"
                              disabled={
                                backendStatus !== 'ready' ||
                                activeRun?.conversationId === conversation.conversation_id
                              }
                              onClick={() =>
                                void (kind === 'chat'
                                  ? deleteConversation(conversation.conversation_id)
                                  : deleteBrowserConversation(conversation.conversation_id))
                              }
                              title={t(appLanguage, 'delete')}
                              type="button"
                            >
                              <Icon path="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6" />
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  )
                })
              )}
            </div>
          </div>

          <div className="rail-footer">
            <button
              className={railItemClass('preferences')}
              onClick={() => setActiveView('preferences')}
              title={t(appLanguage, 'settings')}
              type="button"
            >
              <svg
                className="rail-icon"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
              <span className="rail-item-label">{t(appLanguage, 'settings')}</span>
              {updateResult?.hasUpdate ? (
                <span className="rail-update-badge" title={t(appLanguage, 'updateAvailable')} />
              ) : null}
            </button>
            <button
              aria-controls="primary-sidebar"
              aria-expanded={!isRailCollapsed}
              aria-label={
                isRailCollapsed
                  ? t(appLanguage, 'expandSidebar')
                  : t(appLanguage, 'collapseSidebar')
              }
              className="rail-toggle"
              onClick={() => setIsRailCollapsed((collapsed) => !collapsed)}
              title={
                isRailCollapsed
                  ? t(appLanguage, 'expandSidebar')
                  : t(appLanguage, 'collapseSidebar')
              }
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
              <span className="rail-item-label">
                {isRailCollapsed
                  ? t(appLanguage, 'expandSidebar')
                  : t(appLanguage, 'collapseSidebar')}
              </span>
            </button>
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
                  <label className="chat-threads-search">
                    <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <circle cx="11" cy="11" r="7" />
                      <path d="m21 21-4.3-4.3" />
                    </svg>
                    <input
                      disabled
                      placeholder={t(appLanguage, 'searchPlaceholder')}
                      type="search"
                    />
                    <kbd>⌘K</kbd>
                  </label>
                  <button
                    className="chat-new-btn"
                    disabled={backendStatus !== 'ready' || isCreatingConversation}
                    onClick={() => void createConversation()}
                    title={t(appLanguage, 'newConversation')}
                    type="button"
                  >
                    <Icon path="M12 5v14M5 12h14" />
                  </button>
                </div>

                {conversations.length === 0 ? (
                  <p className="chat-context-sub">{t(appLanguage, 'noConversationsYet')}</p>
                ) : (
                  conversations.map((conversation) =>
                    renamingConversationId === conversation.conversation_id ? (
                      <div
                        className={`chat-thread-item chat-thread-item-renaming${
                          conversation.conversation_id === selectedConversationId ? ' active' : ''
                        }`}
                        key={conversation.conversation_id}
                      >
                        <input
                          className="chat-thread-rename-input"
                          onBlur={() => void saveRename(conversation.conversation_id)}
                          onChange={(event) => setRenameDraft(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter') {
                              event.preventDefault()
                              void saveRename(conversation.conversation_id)
                            }

                            if (event.key === 'Escape') {
                              event.preventDefault()
                              cancelRename()
                            }
                          }}
                          type="text"
                          value={renameDraft}
                        />
                      </div>
                    ) : (
                      <div
                        className={`chat-thread-item${
                          conversation.conversation_id === selectedConversationId ? ' active' : ''
                        }`}
                        key={conversation.conversation_id}
                      >
                        <button
                          className="chat-thread-body"
                          disabled={backendStatus !== 'ready'}
                          onClick={() => setSelectedConversationId(conversation.conversation_id)}
                          type="button"
                        >
                          <div className="chat-thread-name">
                            {conversationLabel(conversation.title, appLanguage)}
                          </div>
                          <div className="chat-thread-time">
                            {formatThreadTime(conversation.updated_at)}
                          </div>
                        </button>
                        <div className="chat-thread-actions">
                          <button
                            aria-label={t(appLanguage, 'rename')}
                            className="chat-thread-action-btn"
                            disabled={backendStatus !== 'ready'}
                            onClick={() => startRename(conversation)}
                            title={t(appLanguage, 'rename')}
                            type="button"
                          >
                            <svg
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              viewBox="0 0 24 24"
                            >
                              <path d="M12 20h9" />
                              <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
                            </svg>
                          </button>
                          <button
                            aria-label={t(appLanguage, 'delete')}
                            className="chat-thread-action-btn chat-thread-action-btn-danger"
                            disabled={
                              backendStatus !== 'ready' ||
                              activeRun?.conversationId === conversation.conversation_id
                            }
                            onClick={() => void deleteConversation(conversation.conversation_id)}
                            title={t(appLanguage, 'delete')}
                            type="button"
                          >
                            <svg
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              viewBox="0 0 24 24"
                            >
                              <path d="M3 6h18" />
                              <path d="M8 6V4h8v2" />
                              <path d="M19 6 18 20H6L5 6" />
                              <path d="M10 11v6" />
                              <path d="M14 11v6" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    )
                  )
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
                      ? conversationLabel(selectedConversation.title, appLanguage)
                      : t(appLanguage, 'noConversationSelected')}
                  </div>
                  {hasAttachedWorkspace ? (
                    <button
                      aria-label="Toggle workspace files panel"
                      className={`chat-workspace-toggle-btn${desktopLayout.attentionPanelOpen ? ' is-active' : ''}`}
                      onClick={() => setAttentionPanelOpen(!desktopLayout.attentionPanelOpen)}
                      title={
                        desktopLayout.attentionPanelOpen
                          ? t(appLanguage, 'hideWorkspaceFiles')
                          : t(appLanguage, 'showWorkspaceFiles')
                      }
                      type="button"
                    >
                      <svg
                        className="chat-workspace-toggle-svg"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        viewBox="0 0 24 24"
                      >
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                      </svg>
                      <span>{t(appLanguage, 'workspaceFiles')}</span>
                      <span className="chat-workspace-toggle-count">
                        {(workspaceSettings?.additional_roots.length ?? 0) +
                          (workspaceSettings?.additional_files.length ?? 0)}
                      </span>
                      {!desktopLayout.attentionPanelOpen ? (
                        <svg
                          aria-hidden="true"
                          className="chat-workspace-toggle-arrow"
                          fill="none"
                          stroke="currentColor"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          viewBox="0 0 24 24"
                        >
                          <path d="m13 17 5-5-5-5" />
                          <path d="m6 17 5-5-5-5" />
                        </svg>
                      ) : null}
                    </button>
                  ) : null}
                </div>

                {errorMessage ? <p className="chat-error">{errorMessage}</p> : null}

                <div
                  className={`chat-messages${visibleScrollbar === 'messages' ? ' scrollbar-visible' : ''}`}
                  onWheel={() => revealScrollbar('messages')}
                >
                  {selectedConversationId === null ? (
                    <p className="chat-empty">
                      {appLanguage === 'zh-Hans'
                        ? '请创建或选择一个对话以查看历史并发送消息。'
                        : 'Create or select a conversation to view its history and send messages.'}
                    </p>
                  ) : visibleMessages.length === 0 &&
                    fileChanges.length === 0 &&
                    runActivity?.conversationId !== selectedConversationId ? (
                    <p className="chat-empty">
                      {appLanguage === 'zh-Hans'
                        ? '暂无消息。在下方打个招呼以开启对话吧。'
                        : 'No messages yet. Say hello below to start this conversation.'}
                    </p>
                  ) : (
                    <>
                      {(() => {
                        const visibleActivity =
                          runActivity?.conversationId === selectedConversationId &&
                          !runHistory.some((history) => history.run.run_id === runActivity.runId)
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
                        const fileChangesAfterMessage = new Map<number, FileChange[]>()
                        const unanchoredFileChanges: FileChange[] = []
                        const runHistoryBeforeAssistant = runHistoryByAssistantMessage(
                          visibleMessages,
                          runHistory
                        )

                        for (const change of fileChanges) {
                          const changeTime = new Date(change.created_at).getTime()
                          let anchorIndex = visibleMessages.findIndex(
                            (message) =>
                              message.role === 'assistant' &&
                              new Date(message.created_at).getTime() >= changeTime
                          )
                          let precedingIndex = -1
                          for (let index = 0; index < visibleMessages.length; index += 1) {
                            if (
                              new Date(visibleMessages[index].created_at).getTime() <= changeTime
                            ) {
                              precedingIndex = index
                            } else {
                              break
                            }
                          }
                          if (anchorIndex === -1) {
                            anchorIndex = precedingIndex
                          }
                          if (anchorIndex === -1) {
                            unanchoredFileChanges.push(change)
                          } else {
                            const anchored = fileChangesAfterMessage.get(anchorIndex) ?? []
                            anchored.push(change)
                            fileChangesAfterMessage.set(anchorIndex, anchored)
                          }
                        }

                        function renderFileChange(change: FileChange): React.JSX.Element {
                          const hasUndoError = undoErrorChangeId === change.change_id
                          return (
                            <div className="file-change-card" key={change.change_id}>
                              <div className="file-change-card-copy">
                                <span className="file-change-operation">
                                  {change.operation === 'create'
                                    ? t(appLanguage, 'createdFile')
                                    : change.operation === 'replace'
                                      ? t(appLanguage, 'updatedFile')
                                      : t(appLanguage, 'deletedFile')}
                                </span>
                                <span className="file-change-path" title={change.path}>
                                  {change.path}
                                </span>
                                {change.status === 'conflicted' ? (
                                  <span className="file-change-conflict" role="status">
                                    <strong>{t(appLanguage, 'undoUnavailable')}</strong>
                                    <span>{t(appLanguage, 'fileVersionChanged')}</span>
                                  </span>
                                ) : null}
                              </div>
                              {change.status === 'applied' ? (
                                <div className="file-change-action">
                                  <button
                                    disabled={undoingChangeId !== null}
                                    onClick={() => void undoFileChange(change)}
                                    type="button"
                                  >
                                    {undoingChangeId === change.change_id
                                      ? t(appLanguage, 'undoing')
                                      : t(appLanguage, 'undo')}
                                  </button>
                                  {hasUndoError ? (
                                    <span className="file-change-undo-error" role="status">
                                      {t(appLanguage, 'undoError')}
                                    </span>
                                  ) : null}
                                </div>
                              ) : change.status === 'conflicted' ? null : (
                                <span className={`file-change-status is-${change.status}`}>
                                  {change.status === 'reverted'
                                    ? t(appLanguage, 'undone')
                                    : t(appLanguage, 'unavailable')}
                                </span>
                              )}
                            </div>
                          )
                        }

                        return (
                          <>
                            {visibleMessages.map((message, index) => (
                              <div className="chat-turn" key={message.message_id}>
                                {message.role === 'assistant'
                                  ? (runHistoryBeforeAssistant.get(message.message_id) ?? []).map(
                                      (history) => {
                                        const activity = persistedRunActivity(history)
                                        return (
                                          <RunActivityCard
                                            activity={activity}
                                            expanded={expandedHistoryRunIds.has(activity.runId)}
                                            key={activity.runId}
                                            lang={appLanguage}
                                            onExpandedChange={(expanded) =>
                                              setExpandedHistoryRunIds((current) => {
                                                const next = new Set(current)
                                                if (expanded) next.add(activity.runId)
                                                else next.delete(activity.runId)
                                                return next
                                              })
                                            }
                                          />
                                        )
                                      }
                                    )
                                  : null}
                                <div className={`message-entry ${message.role}`}>
                                  <div
                                    className={`msg ${message.role === 'assistant' ? 'agent' : 'user'}`}
                                  >
                                    <div className="msg-bubble">
                                      {message.role === 'assistant' ? (
                                        <div className="markdown-content">
                                          <ReactMarkdown
                                            remarkPlugins={[remarkGfm]}
                                            components={{
                                              a: ({ children, href }) => (
                                                <a
                                                  href={href}
                                                  onClick={(event) => {
                                                    event.preventDefault()
                                                    openAssistantLink(href)
                                                  }}
                                                  title={t(appLanguage, 'openInDefaultBrowser')}
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
                                  <div className="message-meta">
                                    <time
                                      dateTime={message.created_at}
                                      title={new Date(message.created_at).toLocaleString()}
                                    >
                                      {formatMessageTime(message.created_at)}
                                    </time>
                                    <button
                                      aria-label={
                                        copiedMessageId === message.message_id
                                          ? t(appLanguage, 'copiedMessage')
                                          : t(appLanguage, 'copyMessage')
                                      }
                                      className="message-action"
                                      onClick={() => void copyMessage(message)}
                                      title={
                                        copiedMessageId === message.message_id
                                          ? t(appLanguage, 'copiedMessage')
                                          : t(appLanguage, 'copyMessage')
                                      }
                                      type="button"
                                    >
                                      <CopyIcon copied={copiedMessageId === message.message_id} />
                                    </button>
                                    {message.role === 'user' ? (
                                      <button
                                        aria-label={t(appLanguage, 'editAndResend')}
                                        className="message-action"
                                        disabled={backendStatus !== 'ready'}
                                        onClick={() => beginMessageEdit(message)}
                                        title={t(appLanguage, 'editAndResend')}
                                        type="button"
                                      >
                                        <Icon path="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4Z" />
                                      </button>
                                    ) : null}
                                  </div>
                                </div>
                                {visibleActivity !== null && index === activityAnchorIndex ? (
                                  <RunActivityCard
                                    activity={visibleActivity}
                                    expanded={activityExpanded}
                                    lang={appLanguage}
                                    onExpandedChange={setActivityExpanded}
                                  />
                                ) : null}
                                {(fileChangesAfterMessage.get(index) ?? []).map(renderFileChange)}
                              </div>
                            ))}
                            {visibleActivity !== null && activityAnchorIndex === -1 ? (
                              <RunActivityCard
                                activity={visibleActivity}
                                expanded={activityExpanded}
                                lang={appLanguage}
                                onExpandedChange={setActivityExpanded}
                              />
                            ) : null}
                            {unanchoredFileChanges.map(renderFileChange)}
                          </>
                        )
                      })()}
                      <div ref={messagesEndRef} />
                    </>
                  )}
                </div>

                {visibleApproval !== null ? (
                  <div
                    aria-label={t(appLanguage, 'approvalsTitle')}
                    className="tool-approval-banner"
                    role="region"
                  >
                    <span className="tool-approval-kind">
                      {visibleApprovalServer === null ? 'Tool' : 'MCP'}
                    </span>
                    <p className="tool-approval-banner-copy">
                      <span className="tool-approval-banner-title">
                        {appLanguage === 'zh-Hans'
                          ? `是否允许 ${visibleApproval.display_name}？`
                          : `Allow ${visibleApproval.display_name}?`}
                      </span>
                      {visibleApproval.resource_path !== null ? (
                        <>
                          <span className="tool-approval-banner-source">
                            {visibleApproval.impact_summary}
                          </span>
                          <span className="tool-approval-banner-source">
                            {visibleApproval.resource_path}
                          </span>
                        </>
                      ) : visibleApprovalServer !== null ? (
                        <span className="tool-approval-banner-source">{visibleApprovalServer}</span>
                      ) : null}
                    </p>
                    <div className="tool-approval-banner-actions">
                      {TOOL_APPROVAL_BANNER_ACTIONS.filter(
                        (action) =>
                          action.decision !== 'allow_conversation' ||
                          visibleApproval.allows_conversation_approval
                      ).map((action) => (
                        <button
                          className={action.className}
                          disabled={isDecidingApproval}
                          key={action.decision}
                          onClick={() => void decidePendingApproval(action.decision)}
                          type="button"
                        >
                          {action.decision === 'allow_conversation'
                            ? visibleApproval.tool_id.startsWith('filesystem.')
                              ? t(appLanguage, 'alwaysAllowFileChanges')
                              : t(appLanguage, 'allowForChat')
                            : action.decision === 'allow_once'
                              ? t(appLanguage, 'allowOnce')
                              : t(appLanguage, 'deny')}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}

                <form className="chat-composer" onSubmit={(event) => void submitMessage(event)}>
                  <div className="chat-composer-box">
                    {editingMessageId !== null ? (
                      <div className="composer-editing">
                        <span>{t(appLanguage, 'editingPreviousMessage')}</span>
                        <button onClick={cancelMessageEdit} type="button">
                          {t(appLanguage, 'cancel')}
                        </button>
                      </div>
                    ) : null}
                    <textarea
                      ref={composerInputRef}
                      disabled={selectedConversationId === null || backendStatus !== 'ready'}
                      onChange={(event) => setDraft(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' && !event.shiftKey) {
                          event.preventDefault()
                          event.currentTarget.form?.requestSubmit()
                        }
                      }}
                      placeholder={
                        selectedConversationId === null
                          ? t(appLanguage, 'composerPlaceholderEmpty')
                          : t(appLanguage, 'composerPlaceholder')
                      }
                      rows={1}
                      value={draft}
                    />
                    <div className="chat-composer-footer">
                      <button
                        aria-label={t(appLanguage, 'attachFileOrFolder')}
                        className="chat-attach-btn"
                        disabled={
                          selectedConversationId === null ||
                          isWorkspaceLoading ||
                          isWorkspaceBusy ||
                          workspaceSettings === null
                        }
                        onClick={() => void handleAddWorkspacePath()}
                        title={t(appLanguage, 'attachFileOrFolder')}
                        type="button"
                      >
                        <Icon path="M12 5v14m-7-7h14" />
                      </button>
                      <div className="chat-composer-context">
                        {workspaceSettings !== null &&
                        (workspaceSettings.additional_roots.length > 0 ||
                          workspaceSettings.additional_files.length > 0) ? (
                          <div className="chat-context-chips">
                            {workspaceSettings.additional_roots.map((rootPath) => {
                              const folderName =
                                rootPath.split(/[\\/]/).filter(Boolean).at(-1) ?? rootPath
                              return (
                                <span className="chat-context-chip" key={rootPath} title={rootPath}>
                                  <span className="chat-context-chip-icon">📁</span>
                                  <span className="chat-context-chip-name">{folderName}</span>
                                  <button
                                    aria-label={`Remove folder ${folderName}`}
                                    className="chat-context-chip-remove"
                                    disabled={isWorkspaceBusy}
                                    onClick={() =>
                                      void handleRemoveWorkspacePath(rootPath, 'directory')
                                    }
                                    title={`Remove ${rootPath}`}
                                    type="button"
                                  >
                                    <Icon path="M18 6 6 18M6 6l12 12" />
                                  </button>
                                </span>
                              )
                            })}
                            {workspaceSettings.additional_files.map((filePath) => {
                              const fileName =
                                filePath.split(/[\\/]/).filter(Boolean).at(-1) ?? filePath
                              return (
                                <span className="chat-context-chip" key={filePath} title={filePath}>
                                  <span className="chat-context-chip-icon">📄</span>
                                  <span className="chat-context-chip-name">{fileName}</span>
                                  <button
                                    aria-label={`Remove file ${fileName}`}
                                    className="chat-context-chip-remove"
                                    disabled={isWorkspaceBusy}
                                    onClick={() => void handleRemoveWorkspacePath(filePath, 'file')}
                                    title={`Remove ${filePath}`}
                                    type="button"
                                  >
                                    <Icon path="M18 6 6 18M6 6l12 12" />
                                  </button>
                                </span>
                              )
                            })}
                          </div>
                        ) : chatRunIsActive || activeRun !== null ? (
                          <span className="chat-composer-status">
                            {chatRunIsActive
                              ? appLanguage === 'zh-Hans'
                                ? 'asAgent 正在执行'
                                : 'asAgent is working'
                              : appLanguage === 'zh-Hans'
                                ? '另一对话正在执行'
                                : 'Another conversation is running'}
                          </span>
                        ) : null}
                      </div>
                      <div className="chat-composer-actions">
                        <button
                          aria-label={
                            webSearchEnabled
                              ? t(appLanguage, 'webSearchEnabled')
                              : t(appLanguage, 'webSearchDisabled')
                          }
                          aria-pressed={webSearchEnabled}
                          className={`chat-search-btn${webSearchEnabled ? ' active' : ''}`}
                          disabled={backendStatus !== 'ready'}
                          onClick={handleToggleWebSearch}
                          title={
                            webSearchEnabled
                              ? t(appLanguage, 'webSearchEnabled')
                              : t(appLanguage, 'webSearchDisabled')
                          }
                          type="button"
                        >
                          <GlobeIcon />
                          <span className="chat-search-btn-label">
                            {appLanguage === 'zh-Hans' ? '联网' : 'Search'}
                          </span>
                        </button>
                        {!chatRunIsActive ? (
                          <button
                            aria-label={
                              isSubmittingMessage
                                ? appLanguage === 'zh-Hans'
                                  ? '发送中'
                                  : 'Sending'
                                : appLanguage === 'zh-Hans'
                                  ? '发送消息'
                                  : 'Send message'
                            }
                            className="composer-send"
                            disabled={selectedConversationId === null || !draft.trim() || isBusy}
                            title={
                              isSubmittingMessage
                                ? appLanguage === 'zh-Hans'
                                  ? '发送中…'
                                  : 'Sending…'
                                : appLanguage === 'zh-Hans'
                                  ? '发送消息'
                                  : 'Send message'
                            }
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
                            {isCancellingRun
                              ? appLanguage === 'zh-Hans'
                                ? '正在停止…'
                                : 'Stopping…'
                              : t(appLanguage, 'stopGenerating')}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </form>
              </div>
            </div>
          </section>
          {hasAttachedWorkspace ? (
            <AttentionAside
              actions={
                <div className="workspace-header-actions">
                  <button
                    aria-label="Add folder or file"
                    className="workspace-ghost-btn"
                    disabled={isWorkspaceBusy}
                    onClick={() => void handleAddWorkspacePath()}
                    title="Add folder or file"
                    type="button"
                  >
                    <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path d="M12 5v14m-7-7h14" />
                    </svg>
                  </button>
                  <button
                    aria-label="Refresh files"
                    className="workspace-ghost-btn"
                    disabled={isTreeLoading}
                    onClick={refreshWorkspaceTree}
                    title="Refresh workspace files"
                    type="button"
                  >
                    <svg
                      className={isTreeLoading ? 'is-spinning' : ''}
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      viewBox="0 0 24 24"
                    >
                      <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
                    </svg>
                  </button>
                </div>
              }
              header={
                <div className="workspace-panel-title">
                  <span className="workspace-panel-label">Workspace</span>
                  <span className="workspace-panel-count">
                    {(workspaceSettings?.additional_roots.length ?? 0) +
                      (workspaceSettings?.additional_files.length ?? 0)}
                  </span>
                </div>
              }
            >
              <div className="workspace-inspector">
                <div
                  className={`workspace-tree-container${visibleScrollbar === 'workspaceTree' ? ' scrollbar-visible' : ''}`}
                  onWheel={() => revealScrollbar('workspaceTree')}
                >
                  {isTreeLoading && Object.keys(workspaceTrees).length === 0 ? (
                    <div className="workspace-tree-status">Scanning workspace…</div>
                  ) : attachedFolders.length > 0 || attachedFiles.length > 0 ? (
                    <div className="workspace-tree">
                      {attachedFolders.map((rootPath) => {
                        const tree = workspaceTrees[rootPath]
                        if (!tree) {
                          const folderName =
                            rootPath.split(/[\\/]/).filter(Boolean).at(-1) ?? rootPath
                          return (
                            <div className="workspace-tree-row" key={rootPath}>
                              <TreeIcon isExpanded={false} kind="directory" />
                              <span className="workspace-tree-name">{folderName}</span>
                              <span className="workspace-tree-size">Loading…</span>
                            </div>
                          )
                        }
                        return <WorkspaceTreeNodeItem key={rootPath} node={tree} />
                      })}
                      {attachedFiles.map((filePath) => {
                        const fileName = filePath.split(/[\\/]/).filter(Boolean).at(-1) ?? filePath
                        const ext = fileName.split('.').at(-1)
                        const fileNode: WorkspaceFileNode = {
                          name: fileName,
                          path: filePath,
                          relativePath: fileName,
                          kind: 'file',
                          extension: ext
                        }
                        return <WorkspaceTreeNodeItem key={filePath} node={fileNode} />
                      })}
                    </div>
                  ) : (
                    <div className="workspace-tree-empty">No files available</div>
                  )}
                </div>

                {selectedPreviewFile !== null ? (
                  <div className="workspace-preview-panel">
                    <div className="workspace-preview-header">
                      <div className="workspace-preview-info">
                        <span className="workspace-preview-name">
                          {selectedPreviewFile.split(/[\\/]/).filter(Boolean).at(-1)}
                        </span>
                        {filePreview && !filePreview.isBinary ? (
                          <span className="workspace-preview-meta">
                            {formatBytes(filePreview.size)}
                            {filePreview.isTruncated ? ' (previewing 100KB)' : ''}
                          </span>
                        ) : null}
                      </div>
                      <div className="workspace-preview-actions">
                        <button
                          aria-label="Reveal in Finder"
                          className="workspace-preview-action-btn"
                          onClick={() => void window.desktop.revealInFinder(selectedPreviewFile)}
                          title="Reveal in Finder"
                          type="button"
                        >
                          ↗
                        </button>
                        <button
                          aria-label="Close preview"
                          className="workspace-preview-action-btn"
                          onClick={() => {
                            setSelectedPreviewFile(null)
                            setFilePreview(null)
                          }}
                          title="Close preview"
                          type="button"
                        >
                          ×
                        </button>
                      </div>
                    </div>
                    <div
                      className={`workspace-preview-body${visibleScrollbar === 'workspacePreview' ? ' scrollbar-visible' : ''}`}
                      onWheel={() => revealScrollbar('workspacePreview')}
                    >
                      {isPreviewLoading ? (
                        <div className="workspace-preview-status">Loading preview…</div>
                      ) : filePreview?.isBinary ? (
                        <div className="workspace-preview-binary">
                          <span>📦</span>
                          <strong>Binary file</strong>
                          <small>{formatBytes(filePreview.size)}</small>
                        </div>
                      ) : filePreview ? (
                        <pre className="workspace-preview-code">
                          <code>{filePreview.content}</code>
                        </pre>
                      ) : (
                        <div className="workspace-preview-status">Preview unavailable</div>
                      )}
                    </div>
                  </div>
                ) : null}
              </div>
            </AttentionAside>
          ) : null}
        </div>

        <div className={`view${activeView === 'browser' ? ' active' : ''}`}>
          <section className="center browser-center">
            <div
              className="browser-page"
              style={
                {
                  '--browser-agent-width': `${desktopLayout.browserAgentWidth}px`
                } as CSSProperties
              }
            >
              <div className="browser-chrome">
                <div aria-label="Browser tabs" className="browser-tabstrip" role="tablist">
                  {browserTabs.map((tab) => {
                    const selected = tab.id === activeBrowserTabId
                    return (
                      <div
                        aria-selected={selected}
                        className={`browser-tab${selected ? ' is-active' : ''}`}
                        key={tab.id}
                        onClick={() => selectBrowserTab(tab.id)}
                        onAuxClick={(event) => {
                          if (event.button === 1) {
                            event.preventDefault()
                            closeBrowserTab(tab.id)
                          }
                        }}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault()
                            selectBrowserTab(tab.id)
                          }
                        }}
                        role="tab"
                        tabIndex={selected ? 0 : -1}
                        title={tab.title}
                      >
                        <span className="browser-tab-title">{tab.title}</span>
                        <button
                          aria-label={`Close ${tab.title}`}
                          className="browser-tab-close"
                          onClick={(event) => {
                            event.stopPropagation()
                            closeBrowserTab(tab.id)
                          }}
                          type="button"
                        >
                          ×
                        </button>
                      </div>
                    )
                  })}
                  <button
                    aria-label={t(appLanguage, 'newTab')}
                    className="browser-tab-new"
                    disabled={browserTabs.length >= MAX_BROWSER_TABS}
                    onClick={addBrowserTab}
                    type="button"
                  >
                    <Icon path="M12 5v14M5 12h14" />
                  </button>
                </div>
                <form
                  className="browser-address-form"
                  onSubmit={(event) => void openBrowserAddress(event)}
                >
                  <div className="browser-nav">
                    <button
                      aria-label={t(appLanguage, 'back')}
                      className="browser-nav-button"
                      disabled={!(activeBrowserTab?.canGoBack ?? false)}
                      onClick={() => controlBrowser('back')}
                      type="button"
                    >
                      <BrowserNavIcon name="back" />
                    </button>
                    <button
                      aria-label={t(appLanguage, 'forward')}
                      className="browser-nav-button"
                      disabled={!(activeBrowserTab?.canGoForward ?? false)}
                      onClick={() => controlBrowser('forward')}
                      type="button"
                    >
                      <BrowserNavIcon name="forward" />
                    </button>
                    <button
                      aria-label={t(appLanguage, 'reload')}
                      className="browser-nav-button"
                      disabled={(activeBrowserTab?.address ?? '') === ''}
                      onClick={() => controlBrowser('reload')}
                      type="button"
                    >
                      <BrowserNavIcon name="reload" />
                    </button>
                    <button
                      aria-label={t(appLanguage, 'home')}
                      className="browser-nav-button"
                      onClick={() => controlBrowser('home')}
                      type="button"
                    >
                      <BrowserNavIcon name="home" />
                    </button>
                  </div>
                  <div className="browser-address-box">
                    <button
                      aria-label={`Search engine: ${browserSearchEngine === 'google' ? 'Google' : 'Bing'}. Click to switch.`}
                      className="browser-search-engine-btn"
                      onClick={() => {
                        const nextEngine: BrowserSearchEngine =
                          browserSearchEngine === 'google' ? 'bing' : 'google'
                        setBrowserSearchEngine(nextEngine)
                        try {
                          window.localStorage.setItem(SEARCH_ENGINE_STORAGE_KEY, nextEngine)
                        } catch {
                          // Ignore storage write error
                        }
                      }}
                      title={`Search engine: ${browserSearchEngine === 'google' ? 'Google' : 'Bing'} (Click to switch to ${browserSearchEngine === 'google' ? 'Bing' : 'Google'})`}
                      type="button"
                    >
                      {browserSearchEngine === 'google' ? <GoogleSearchIcon /> : <BingSearchIcon />}
                    </button>
                    <span aria-hidden="true" className="browser-search-divider" />
                    <input
                      autoCapitalize="off"
                      autoComplete="off"
                      autoCorrect="off"
                      className="browser-address-input"
                      id="browser-address"
                      onChange={(event) => updateActiveBrowserAddress(event.target.value)}
                      placeholder={
                        appLanguage === 'zh-Hans'
                          ? `在 ${browserSearchEngine === 'google' ? 'Google' : 'Bing'} 中搜索或输入网址`
                          : `Search ${browserSearchEngine === 'google' ? 'Google' : 'Bing'} or enter URL`
                      }
                      ref={browserAddressRef}
                      spellCheck={false}
                      type="text"
                      value={activeBrowserTab?.address ?? ''}
                    />
                  </div>
                  <button aria-label="Go" className="browser-go" title="Go" type="submit">
                    <Icon path="M5 12h14M13 6l6 6-6 6" />
                  </button>
                  <button
                    aria-expanded={desktopLayout.browserAgentPanelOpen}
                    aria-label={
                      desktopLayout.browserAgentPanelOpen
                        ? appLanguage === 'zh-Hans'
                          ? '收起网页助手'
                          : 'Collapse page assistant'
                        : appLanguage === 'zh-Hans'
                          ? '展开网页助手'
                          : 'Expand page assistant'
                    }
                    className="browser-agent-toggle"
                    onClick={() => setBrowserAgentPanelOpen(!desktopLayout.browserAgentPanelOpen)}
                    title={
                      desktopLayout.browserAgentPanelOpen
                        ? appLanguage === 'zh-Hans'
                          ? '收起网页助手'
                          : 'Collapse page assistant'
                        : appLanguage === 'zh-Hans'
                          ? '展开网页助手'
                          : 'Expand page assistant'
                    }
                    type="button"
                  >
                    <BrowserAgentToggleIcon expanded={desktopLayout.browserAgentPanelOpen} />
                  </button>
                </form>
              </div>
              {browserError !== null ? <p className="browser-error">{browserError}</p> : null}
              <div className="browser-body">
                <div className="browser-surface" ref={browserSurfaceRef} />
                {desktopLayout.browserAgentPanelOpen ? (
                  <aside aria-label="Page assistant" className="browser-agent">
                    <div
                      aria-label="Resize page assistant"
                      className="browser-agent-resizer"
                      onPointerDown={(event) => beginColumnResize('browserAgent', event)}
                      role="separator"
                    />
                    <div className="browser-agent-toolbar">
                      <button
                        aria-label={t(appLanguage, 'newConversation')}
                        className="browser-agent-toolbar-button"
                        disabled={backendStatus !== 'ready' || isCreatingConversation}
                        onClick={() => void createBrowserConversationForActiveTab()}
                        title={t(appLanguage, 'newConversation')}
                        type="button"
                      >
                        <Icon path="M12 5v14M5 12h14" />
                      </button>
                    </div>
                    {errorMessage !== null && activeView === 'browser' ? (
                      <p className="browser-agent-error">{errorMessage}</p>
                    ) : null}
                    <div className="browser-agent-messages">
                      {browserMessages.length === 0 &&
                      visibleBrowserRunHistory.length === 0 &&
                      runActivity?.conversationId !== selectedBrowserConversationId ? (
                        <div className="browser-agent-empty">
                          <div aria-hidden="true" className="browser-agent-empty-icon">
                            <Icon path="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                          </div>
                          <p className="browser-agent-empty-title">
                            {appLanguage === 'zh-Hans' ? '与 asAgent 对话' : 'Talk with asAgent'}
                          </p>
                          <p className="browser-agent-empty-copy">
                            {t(appLanguage, 'browserAssistantEmpty')}
                          </p>
                        </div>
                      ) : (
                        (() => {
                          const browserActivityAnchorIndex = browserMessages.reduce(
                            (lastIndex, message, index) =>
                              message.role === 'user' ? index : lastIndex,
                            -1
                          )

                          return (
                            <>
                              {browserMessages.map((message, index) => (
                                <div
                                  className={`browser-agent-turn ${message.role === 'user' ? 'is-user' : 'is-assistant'}`}
                                  key={message.message_id}
                                >
                                  {message.role === 'assistant'
                                    ? (
                                        browserRunHistoryByMessage.get(message.message_id) ?? []
                                      ).map((history) => {
                                        const activity = persistedRunActivity(history)
                                        return (
                                          <RunActivityCard
                                            activity={activity}
                                            expanded={expandedHistoryRunIds.has(activity.runId)}
                                            key={activity.runId}
                                            lang={appLanguage}
                                            onExpandedChange={(expanded) =>
                                              setExpandedHistoryRunIds((current) => {
                                                const next = new Set(current)
                                                if (expanded) next.add(activity.runId)
                                                else next.delete(activity.runId)
                                                return next
                                              })
                                            }
                                          />
                                        )
                                      })
                                    : null}
                                  <div className="browser-agent-bubble">
                                    {message.role === 'assistant' ? (
                                      <div className="markdown-content">
                                        <ReactMarkdown
                                          remarkPlugins={[remarkGfm]}
                                          components={{
                                            a: ({ children, href }) => (
                                              <a
                                                href={href}
                                                onClick={(event) => {
                                                  event.preventDefault()
                                                  openAssistantLink(href)
                                                }}
                                                title={t(appLanguage, 'openInDefaultBrowser')}
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
                                  <div className="message-meta browser-agent-meta">
                                    <time
                                      dateTime={message.created_at}
                                      title={new Date(message.created_at).toLocaleString()}
                                    >
                                      {formatMessageTime(message.created_at)}
                                    </time>
                                    <button
                                      aria-label={
                                        copiedMessageId === message.message_id
                                          ? t(appLanguage, 'copiedMessage')
                                          : t(appLanguage, 'copyMessage')
                                      }
                                      className="message-action"
                                      onClick={() => void copyMessage(message)}
                                      title={
                                        copiedMessageId === message.message_id
                                          ? t(appLanguage, 'copiedMessage')
                                          : t(appLanguage, 'copyMessage')
                                      }
                                      type="button"
                                    >
                                      <CopyIcon copied={copiedMessageId === message.message_id} />
                                    </button>
                                    {message.role === 'user' ? (
                                      <button
                                        aria-label={t(appLanguage, 'editAndResend')}
                                        className="message-action"
                                        disabled={backendStatus !== 'ready'}
                                        onClick={() => beginBrowserMessageEdit(message)}
                                        title={t(appLanguage, 'editAndResend')}
                                        type="button"
                                      >
                                        <Icon path="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4Z" />
                                      </button>
                                    ) : null}
                                  </div>
                                  {visibleBrowserActivity !== null &&
                                  index === browserActivityAnchorIndex ? (
                                    <RunActivityCard
                                      activity={visibleBrowserActivity}
                                      expanded={activityExpanded}
                                      lang={appLanguage}
                                      onExpandedChange={setActivityExpanded}
                                    />
                                  ) : null}
                                </div>
                              ))}
                              {unmatchedBrowserRunHistory.map((history) => {
                                const activity = persistedRunActivity(history)
                                return (
                                  <RunActivityCard
                                    activity={activity}
                                    expanded={expandedHistoryRunIds.has(activity.runId)}
                                    key={activity.runId}
                                    lang={appLanguage}
                                    onExpandedChange={(expanded) =>
                                      setExpandedHistoryRunIds((current) => {
                                        const next = new Set(current)
                                        if (expanded) next.add(activity.runId)
                                        else next.delete(activity.runId)
                                        return next
                                      })
                                    }
                                  />
                                )
                              })}
                              {visibleBrowserActivity !== null &&
                              browserActivityAnchorIndex === -1 ? (
                                <RunActivityCard
                                  activity={visibleBrowserActivity}
                                  expanded={activityExpanded}
                                  lang={appLanguage}
                                  onExpandedChange={setActivityExpanded}
                                />
                              ) : null}
                              <div ref={browserAgentMessagesEndRef} />
                            </>
                          )
                        })()
                      )}
                    </div>
                    {visibleBrowserApproval !== null ? (
                      <div
                        aria-label={t(appLanguage, 'approvalsTitle')}
                        className="browser-agent-approval"
                        role="region"
                      >
                        <div className="browser-agent-approval-card">
                          <div className="browser-agent-approval-header">
                            <span className="browser-agent-approval-kind">
                              {browserApprovalKindLabel(
                                visibleBrowserApproval.tool_id,
                                visibleBrowserApprovalServer
                              )}
                            </span>
                            <span className="browser-agent-approval-hint">
                              {t(appLanguage, 'approvalNeeded')}
                            </span>
                          </div>
                          <p className="browser-agent-approval-title">
                            {appLanguage === 'zh-Hans'
                              ? `是否允许 ${visibleBrowserApproval.display_name}？`
                              : `Allow ${visibleBrowserApproval.display_name}?`}
                          </p>
                          {visibleBrowserApprovalDetails.length > 0 ? (
                            <div className="browser-agent-approval-details">
                              {visibleBrowserApprovalDetails.map((detail) => (
                                <span
                                  className="browser-agent-approval-detail"
                                  key={detail}
                                  title={detail}
                                >
                                  {detail}
                                </span>
                              ))}
                            </div>
                          ) : null}
                          <div
                            className={`browser-agent-approval-actions${
                              visibleBrowserApproval.allows_conversation_approval
                                ? ' has-conversation'
                                : ''
                            }`}
                          >
                            {TOOL_APPROVAL_BANNER_ACTIONS.filter(
                              (action) =>
                                action.decision !== 'allow_conversation' ||
                                visibleBrowserApproval.allows_conversation_approval
                            ).map((action) => (
                              <button
                                className={`browser-agent-approval-btn ${action.className}`}
                                disabled={isDecidingApproval}
                                key={action.decision}
                                onClick={() => void decidePendingApproval(action.decision)}
                                type="button"
                              >
                                {action.decision === 'allow_conversation'
                                  ? t(appLanguage, 'allowForChat')
                                  : action.decision === 'allow_once'
                                    ? t(appLanguage, 'allowOnce')
                                    : t(appLanguage, 'deny')}
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : null}
                    <form
                      className="browser-agent-composer"
                      onSubmit={(event) => void submitBrowserMessage(event)}
                    >
                      {browserEditingMessageId !== null ? (
                        <div className="composer-editing">
                          <span>{t(appLanguage, 'editingPreviousMessage')}</span>
                          <button onClick={cancelBrowserMessageEdit} type="button">
                            {t(appLanguage, 'cancel')}
                          </button>
                        </div>
                      ) : null}
                      <label className="browser-agent-input">
                        <textarea
                          ref={browserAgentInputRef}
                          onChange={(event) => setBrowserDraft(event.target.value)}
                          onInput={(event) => resizeBrowserAgentInput(event.currentTarget)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter' && !event.shiftKey) {
                              event.preventDefault()
                              event.currentTarget.form?.requestSubmit()
                            }
                          }}
                          placeholder={t(appLanguage, 'composerPlaceholder')}
                          rows={1}
                          value={browserDraft}
                        />
                        {browserRunIsActive ? (
                          <button
                            className="composer-stop"
                            disabled={isCancellingRun}
                            onClick={() => void cancelActiveRun()}
                            type="button"
                          >
                            {isCancellingRun
                              ? t(appLanguage, 'stopping')
                              : t(appLanguage, 'stopGenerating')}
                          </button>
                        ) : (
                          <button
                            aria-label={t(appLanguage, 'sendMessage')}
                            className="composer-send"
                            disabled={!browserDraft.trim() || isBusy}
                            title={t(appLanguage, 'sendMessage')}
                            type="submit"
                          >
                            <Icon path="M12 19V5m-6 6 6-6 6 6" />
                          </button>
                        )}
                      </label>
                    </form>
                  </aside>
                ) : null}
              </div>
            </div>
          </section>
        </div>

        <div className={`view${activeView === 'activity' ? ' active' : ''}`}>
          <section className="center">
            <CenterPageHeader
              subtitle="Everything your agent has done, is doing, or is about to do."
              title="Today"
            />
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
                  <div className="entry-detail">Scheduled-task timelines will appear here.</div>
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

          <AttentionAside
            header={
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
            }
          >
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
                <div className="sched-name">No scheduled task activity yet.</div>
              </div>
            </div>
          </AttentionAside>
        </div>

        <div className={`view${activeView === 'privacy' ? ' active' : ''}`}>
          <section className="center">
            <CenterPageHeader
              subtitle="Everything asAgent can see, and who has touched it."
              title="Privacy & Permissions"
            />
            <div
              className={`privacy-banner${configuredExternalProviderUnavailable ? ' issue' : ''}`}
            >
              <Icon path="M12 2 3 6v6c0 5 4 8.5 9 10 5-1.5 9-5 9-10V6l-9-4Z" />
              {configuredExternalProviderUnavailable
                ? 'The configured external provider is unavailable. New requests are using the offline fallback until its credential is restored.'
                : usesExternalModel
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
          <AttentionAside header={<div className="attn-header">At a glance</div>}>
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
                <span
                  className={`stat-value${
                    usesExternalModel || configuredExternalProviderUnavailable ? ' warn' : ''
                  }`}
                >
                  {configuredExternalProviderUnavailable
                    ? 'Unavailable'
                    : usesExternalModel
                      ? 'Enabled'
                      : 'Off'}
                </span>
              </div>
            </div>
            <div className="trust-note">
              asAgent keeps tokens in Electron Main and never puts secrets in the renderer, URL, or
              logs. Permission management UI will plug into that policy later.
            </div>
          </AttentionAside>
        </div>

        <div className={`view${activeView === 'automations' ? ' active' : ''}`}>
          <section className="center automations-center-shell">
            <div className="automations-view-shell">
              {/* Master Pane: Scheduled Tasks List */}
              <section className="automations-master-pane">
                <div className="automations-master-header">
                  <div className="automations-master-header-text">
                    <div className="automations-master-title">
                      {t(appLanguage, 'automationsTitle')}
                    </div>
                    <div className="automations-master-sub">
                      {automationPreviews.length} {t(appLanguage, 'automationsTitle').toLowerCase()}
                    </div>
                  </div>
                  <button
                    className="automations-new-task-btn"
                    disabled={isAutomationCreating}
                    onClick={startCreatingAutomation}
                    title={t(appLanguage, 'newTask')}
                    type="button"
                  >
                    <Icon path="M12 5v14M5 12h14" />
                    <span>{t(appLanguage, 'newTask')}</span>
                  </button>
                </div>

                {/* List of Tasks */}
                <div className="automations-list" role="list">
                  {isCreatingNewTask && (
                    <div className="automation-card selected is-draft-card" role="listitem">
                      <div className="automation-card-main">
                        <div className="automation-card-toprow">
                          <span className="automation-status draft">
                            <span aria-hidden="true" className="automation-status-dot" />
                            {editingAutomationId !== null
                              ? t(appLanguage, 'editTask')
                              : t(appLanguage, 'statusDraft')}
                          </span>
                        </div>
                        <h2>
                          {editingAutomationId !== null
                            ? (automationPreviews.find((a) => a.id === editingAutomationId)?.name ??
                              t(appLanguage, 'newScheduledTask'))
                            : t(appLanguage, 'newScheduledTask')}
                        </h2>
                        <p className="automation-card-draft-hint">
                          {editingAutomationId !== null
                            ? t(appLanguage, 'editingTaskInCanvas')
                            : t(appLanguage, 'draftingTaskInCanvas')}
                        </p>
                      </div>
                    </div>
                  )}
                  {automationLoadError !== null && (
                    <p className="automation-empty-detail">{automationLoadError}</p>
                  )}
                  {automationLoadError === null &&
                    automationPreviews.length === 0 &&
                    !isCreatingNewTask && (
                      <p className="automation-empty-detail">
                        {t(appLanguage, 'noAutomationsYet')}
                      </p>
                    )}
                  {automationPreviews.map((automation) => (
                    <button
                      aria-pressed={!isCreatingNewTask && selectedAutomation?.id === automation.id}
                      className={`automation-card${
                        !isCreatingNewTask && selectedAutomation?.id === automation.id
                          ? ' selected'
                          : ''
                      }`}
                      disabled={isAutomationCreating}
                      key={automation.id}
                      onClick={() => {
                        discardAutomationDraft()
                        setSelectedAutomationId(automation.id)
                        setIsCreatingNewTask(false)
                      }}
                      role="listitem"
                      type="button"
                    >
                      <div className="automation-card-main">
                        <div className="automation-card-toprow">
                          <span className={`automation-status ${automation.status}`}>
                            <span aria-hidden="true" className="automation-status-dot" />
                            {automation.status === 'active'
                              ? t(appLanguage, 'statusActive')
                              : automation.status === 'paused'
                                ? t(appLanguage, 'statusPaused')
                                : t(appLanguage, 'statusDraft')}
                          </span>
                        </div>
                        <h2>{automation.name}</h2>
                        <p>{automation.summary}</p>
                      </div>
                      <div className="automation-card-meta">
                        <span className="automation-card-schedule">{automation.schedule}</span>
                        <span className="automation-card-next">
                          {automation.nextRun
                            ? `${t(appLanguage, 'nextRun')}: ${automation.nextRun}`
                            : t(appLanguage, 'noUpcomingRun')}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              </section>

              {/* Column Resizer between Master Pane & Canvas */}
              <div
                aria-label="Resize scheduled tasks list"
                className="automations-column-resizer"
                onPointerDown={(event) => beginColumnResize('automationsMaster', event)}
                role="separator"
              />

              {/* Detail Canvas: Hero Task Dashboard or Creation Workspace */}
              <section className="automations-detail-canvas">
                {isCreatingNewTask ? (
                  <div className="automation-creation-dashboard">
                    <div className="automation-hero-header">
                      <div className="automation-hero-header-info">
                        <div className="automation-hero-meta-row">
                          <span className="automation-status draft">
                            <span aria-hidden="true" className="automation-status-dot" />
                            {editingAutomationId !== null
                              ? t(appLanguage, 'editTask')
                              : t(appLanguage, 'statusDraft')}
                          </span>
                        </div>
                        <h1 className="automation-hero-title">
                          {editingAutomationId !== null
                            ? `${t(appLanguage, 'editTask')}: "${
                                automationPreviews.find((a) => a.id === editingAutomationId)
                                  ?.name ?? 'plan'
                              }"`
                            : t(appLanguage, 'newScheduledTask')}
                        </h1>
                        <p className="automation-creation-sub">
                          {editingAutomationId !== null
                            ? t(appLanguage, 'refineTaskSub')
                            : t(appLanguage, 'createTaskSub')}
                        </p>
                      </div>
                      <div className="automation-hero-actions">
                        <button
                          className="automation-action-btn"
                          disabled={isAutomationCreating}
                          onClick={() => {
                            discardAutomationDraft()
                            setIsCreatingNewTask(false)
                          }}
                          type="button"
                        >
                          {t(appLanguage, 'cancel')}
                        </button>
                      </div>
                    </div>

                    {/* Big Spacious Composer */}
                    <div className="automation-canvas-composer-card">
                      {isAutomationAwaitingInput && lastAutomationDraftMessage !== null && (
                        <div
                          aria-live="polite"
                          className="automation-input-needed"
                          id="automation-planning-question"
                          role="status"
                        >
                          <span aria-hidden="true" className="automation-status-dot" />
                          <div>
                            <strong>{t(appLanguage, 'needsYourInput')}</strong>
                            <p>{lastAutomationDraftMessage.content}</p>
                          </div>
                        </div>
                      )}
                      <form
                        className="automation-canvas-form"
                        onSubmit={(e) => void submitAutomationInline(e)}
                      >
                        <div className="automation-canvas-textarea-wrapper">
                          <textarea
                            aria-describedby={
                              isAutomationAwaitingInput ? 'automation-planning-question' : undefined
                            }
                            aria-label={t(appLanguage, 'describeScheduledTask')}
                            className="automation-canvas-textarea"
                            disabled={isAutomationCreating}
                            ref={automationComposerInputRef}
                            onChange={(e) => setAutomationInlineInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault()
                                void submitAutomationInline()
                              }
                            }}
                            placeholder={
                              editingAutomationId !== null
                                ? appLanguage === 'zh-Hans'
                                  ? `正在编辑 "${
                                      automationPreviews.find((a) => a.id === editingAutomationId)
                                        ?.name ?? '任务'
                                    }"… 输入要调整的内容。`
                                  : `Editing "${
                                      automationPreviews.find((a) => a.id === editingAutomationId)
                                        ?.name ?? 'plan'
                                    }"… Type changes to update.`
                                : isAutomationAwaitingInput
                                  ? t(appLanguage, 'replyToContinuePlanning')
                                  : t(appLanguage, 'draftPromptHint')
                            }
                            rows={4}
                            value={automationInlineInput}
                          />
                        </div>

                        {/* Quick Suggestion Chips (when drafting new task) */}
                        {editingAutomationId === null && (
                          <div className="automation-template-chips">
                            <span className="automation-template-label">
                              {t(appLanguage, 'templateSuggestions')}
                            </span>
                            <button
                              className="automation-template-chip"
                              disabled={isAutomationCreating}
                              onClick={() =>
                                setAutomationInlineInput(
                                  (curr) =>
                                    (curr ? curr + ' ' : '') +
                                    (appLanguage === 'zh-Hans'
                                      ? '每天早上 08:00，'
                                      : 'Every morning at 08:00 AM, ')
                                )
                              }
                              type="button"
                            >
                              {appLanguage === 'zh-Hans' ? '📅 每天 08:00 AM' : '📅 Daily 08:00 AM'}
                            </button>
                            <button
                              className="automation-template-chip"
                              disabled={isAutomationCreating}
                              onClick={() =>
                                setAutomationInlineInput(
                                  (curr) =>
                                    (curr ? curr + ' ' : '') +
                                    (appLanguage === 'zh-Hans'
                                      ? '每周一早上 09:00，'
                                      : 'Every Monday at 09:00 AM, ')
                                )
                              }
                              type="button"
                            >
                              {appLanguage === 'zh-Hans'
                                ? '📅 每周一 09:00 AM'
                                : '📅 Every Monday 09:00 AM'}
                            </button>
                            <button
                              className="automation-template-chip"
                              disabled={isAutomationCreating}
                              onClick={() =>
                                setAutomationInlineInput(
                                  (curr) =>
                                    (curr ? curr + ' ' : '') +
                                    (appLanguage === 'zh-Hans'
                                      ? '每小时执行一次，'
                                      : 'Every hour, ')
                                )
                              }
                              type="button"
                            >
                              {appLanguage === 'zh-Hans' ? '⏱ 每小时' : '⏱ Hourly'}
                            </button>
                            <button
                              className="automation-template-chip"
                              disabled={isAutomationCreating}
                              onClick={() =>
                                setAutomationInlineInput(
                                  appLanguage === 'zh-Hans'
                                    ? '每天早上 08:30 打开 Google News 澳洲主页 (https://news.google.com/?hl=en-AU&gl=AU&ceid=AU:en)，抓取置顶澳洲新闻头条并生成简要摘要。'
                                    : 'Every morning at 08:30, open Google News AU (https://news.google.com/?hl=en-AU&gl=AU&ceid=AU:en), extract the top Australian news headlines and summarize them.'
                                )
                              }
                              type="button"
                            >
                              {appLanguage === 'zh-Hans'
                                ? '📰 Google 新闻早报'
                                : '📰 Google News AU Digest'}
                            </button>
                          </div>
                        )}

                        <div className="automation-canvas-composer-bottom">
                          <button
                            className="automation-create-btn"
                            disabled={isAutomationCreating || !automationInlineInput.trim()}
                            type="submit"
                          >
                            {isAutomationCreating ? (
                              <>
                                <span className="automation-create-status-dot" />
                                <span>{t(appLanguage, 'planningScheduledTask')}</span>
                              </>
                            ) : (
                              <>
                                <Icon path="m5 12 14-7-4 14-3-5-4 2 1-5-4-3Z" />
                                <span>{t(appLanguage, 'save')}</span>
                              </>
                            )}
                          </button>
                        </div>
                      </form>

                      {automationCreateStatus !== null && (
                        <div className="automation-create-status-bar">
                          {isAutomationCreating && (
                            <span className="automation-create-status-dot" />
                          )}
                          <span>{automationCreateStatus}</span>
                        </div>
                      )}
                    </div>

                    {/* Planning Conversation Stream (if any messages) */}
                    {automationDraftMessages.length > 0 ? (
                      <div aria-live="polite" className="automation-canvas-messages" role="log">
                        {automationDraftMessages.map((message) => (
                          <div
                            className={`automation-draft-message-card ${message.role}`}
                            key={message.message_id}
                          >
                            <div className="automation-draft-message-role">
                              {message.role === 'assistant'
                                ? 'asAgent'
                                : t(appLanguage, 'planningUserRole')}
                            </div>
                            <div className="automation-draft-message-content">
                              {message.role === 'assistant' ? (
                                <div className="markdown-content">
                                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {message.content}
                                  </ReactMarkdown>
                                </div>
                              ) : (
                                message.content
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      /* Planning Tips Guide */
                      <div className="automation-canvas-guide">
                        <div className="automation-canvas-guide-title">
                          {t(appLanguage, 'planningGuideTitle')}
                        </div>
                        <div className="automation-canvas-guide-grid">
                          <div className="automation-canvas-guide-card">
                            <div className="automation-guide-card-icon">🎯</div>
                            <div className="automation-guide-card-title">
                              {t(appLanguage, 'planningTipTaskTitle')}
                            </div>
                            <div className="automation-guide-card-desc">
                              {t(appLanguage, 'planningTipTaskDesc')}
                            </div>
                          </div>
                          <div className="automation-canvas-guide-card">
                            <div className="automation-guide-card-icon">⏰</div>
                            <div className="automation-guide-card-title">
                              {t(appLanguage, 'planningTipScheduleTitle')}
                            </div>
                            <div className="automation-guide-card-desc">
                              {t(appLanguage, 'planningTipScheduleDesc')}
                            </div>
                          </div>
                          <div className="automation-canvas-guide-card">
                            <div className="automation-guide-card-icon">⚡</div>
                            <div className="automation-guide-card-title">
                              {t(appLanguage, 'planningTipSaveTitle')}
                            </div>
                            <div className="automation-guide-card-desc">
                              {t(appLanguage, 'planningTipSaveDesc')}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ) : selectedAutomation === null ? (
                  <div className="automations-canvas-empty">
                    <div className="automations-canvas-empty-icon">
                      <svg
                        fill="none"
                        stroke="currentColor"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="1.5"
                        viewBox="0 0 24 24"
                      >
                        <circle cx="12" cy="12" r="9" />
                        <path d="M12 7v5l3 3" />
                      </svg>
                    </div>
                    <h3>{t(appLanguage, 'automationsTitle')}</h3>
                    <p>{t(appLanguage, 'createFirstAutomation')}</p>
                    <button
                      className="settings-button settings-button-primary"
                      onClick={startCreatingAutomation}
                      type="button"
                    >
                      {t(appLanguage, 'newTask')}
                    </button>
                  </div>
                ) : (
                  <div className="automation-hero-dashboard">
                    {/* Hero Header */}
                    <div className="automation-hero-header">
                      <div className="automation-hero-header-info">
                        <div className="automation-hero-meta-row">
                          <span className={`automation-status ${selectedAutomation.status}`}>
                            <span aria-hidden="true" className="automation-status-dot" />
                            {selectedAutomation.status === 'active'
                              ? t(appLanguage, 'statusActive')
                              : selectedAutomation.status === 'paused'
                                ? t(appLanguage, 'statusPaused')
                                : t(appLanguage, 'statusDraft')}
                          </span>
                          <span className="automation-hero-schedule-badge">
                            📅 {selectedAutomation.schedule}
                          </span>
                          {selectedAutomation.nextRun && (
                            <span className="automation-hero-next-badge">
                              ⏱ {t(appLanguage, 'nextRun')}: {selectedAutomation.nextRun}
                            </span>
                          )}
                        </div>
                        <h1 className="automation-hero-title">{selectedAutomation.name}</h1>
                      </div>

                      <div className="automation-hero-actions">
                        <button
                          className="automation-action-btn primary"
                          disabled={isAutomationRunningNow}
                          onClick={() => void runAutomationNow(selectedAutomation.id)}
                          type="button"
                        >
                          {isAutomationRunningNow ? (
                            <>
                              <span className="automation-create-status-dot" />
                              <span>{t(appLanguage, 'runningAutomation')}</span>
                            </>
                          ) : (
                            <>
                              <svg
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                viewBox="0 0 24 24"
                              >
                                <polygon points="5 3 19 12 5 21 5 3" />
                              </svg>
                              <span>{t(appLanguage, 'runNow')}</span>
                            </>
                          )}
                        </button>
                        <button
                          className="automation-action-btn"
                          onClick={() => toggleAutomationPreview(selectedAutomation.id)}
                          type="button"
                        >
                          {selectedAutomation.status === 'active'
                            ? t(appLanguage, 'pause')
                            : t(appLanguage, 'activate')}
                        </button>
                        <button
                          className="automation-action-btn"
                          disabled={isAutomationCreating}
                          onClick={() => startEditingAutomation(selectedAutomation.id)}
                          type="button"
                        >
                          {t(appLanguage, 'editPlan')}
                        </button>
                        <button
                          className="automation-action-btn danger"
                          disabled={isAutomationCreating}
                          onClick={() => deleteAutomation(selectedAutomation.id)}
                          type="button"
                        >
                          {t(appLanguage, 'delete')}
                        </button>
                      </div>
                    </div>

                    {automationRunNowMessage !== null && (
                      <div className="automation-hero-run-banner">
                        {isAutomationRunningNow && (
                          <span className="automation-create-status-dot" />
                        )}
                        <span>{automationRunNowMessage}</span>
                      </div>
                    )}

                    {automationCreateStatus !== null && (
                      <div aria-live="polite" className="automation-hero-run-banner" role="status">
                        <span>{automationCreateStatus}</span>
                      </div>
                    )}

                    {/* Plan Summary Card */}
                    <div className="automation-plan-summary-card">
                      <div className="automation-plan-summary-header">
                        <span className="automation-plan-label">{t(appLanguage, 'taskPlan')}</span>
                        <button
                          className="automation-plan-edit-link"
                          onClick={() => startEditingAutomation(selectedAutomation.id)}
                          type="button"
                        >
                          {t(appLanguage, 'editPlan')}
                        </button>
                      </div>
                      <p className="automation-plan-summary-text">{selectedAutomation.summary}</p>
                    </div>

                    {/* Hero Execution Output Box */}
                    {(() => {
                      const currentExecution =
                        automationExecutions.find(
                          (e) => e.automation_execution_id === selectedExecutionId
                        ) ?? automationExecutions[0]
                      const assistantMsg =
                        executionMessages.find((m) => m.role === 'assistant')?.content ?? null
                      const userPromptMsg = executionMessages.find((m) => m.role === 'user') ?? null

                      return (
                        <div className="automation-hero-output-box">
                          <div className="automation-hero-output-header">
                            <div className="automation-hero-output-title-row">
                              <span className="automation-hero-output-heading">
                                {t(appLanguage, 'latestOutput')}
                              </span>
                              {currentExecution !== undefined && (
                                <span className={`automation-status ${currentExecution.status}`}>
                                  <span aria-hidden="true" className="automation-status-dot" />
                                  {currentExecution.status === 'completed'
                                    ? t(appLanguage, 'executionStatusCompleted')
                                    : currentExecution.status === 'failed'
                                      ? t(appLanguage, 'executionStatusFailed')
                                      : currentExecution.status === 'missed'
                                        ? t(appLanguage, 'executionStatusMissed')
                                        : currentExecution.status === 'cancelled'
                                          ? t(appLanguage, 'executionStatusCancelled')
                                          : t(appLanguage, 'executionStatusClaimed')}
                                </span>
                              )}
                              {currentExecution?.scheduled_for && (
                                <span className="automation-hero-output-time">
                                  {new Date(currentExecution.scheduled_for).toLocaleString()}
                                </span>
                              )}
                            </div>

                            <div className="automation-hero-output-controls">
                              {assistantMsg && (
                                <button
                                  className="automation-copy-btn"
                                  onClick={() => copyExecutionOutput(assistantMsg)}
                                  type="button"
                                >
                                  {hasCopiedOutput
                                    ? t(appLanguage, 'copied')
                                    : t(appLanguage, 'copyOutput')}
                                </button>
                              )}
                              {userPromptMsg && (
                                <button
                                  className="automation-toggle-prompt-btn"
                                  onClick={() => setShowTaskPrompt((v) => !v)}
                                  type="button"
                                >
                                  {showTaskPrompt
                                    ? t(appLanguage, 'hidePrompt')
                                    : t(appLanguage, 'viewPrompt')}
                                </button>
                              )}
                            </div>
                          </div>

                          {/* Optional Task Prompt Viewer */}
                          {showTaskPrompt && userPromptMsg && (
                            <div className="automation-task-prompt-container">
                              <div className="automation-task-prompt-hint">
                                {t(appLanguage, 'taskPromptDescription')}
                              </div>
                              <div className="automation-task-prompt-content">
                                {userPromptMsg.content}
                              </div>
                            </div>
                          )}

                          {/* Execution Output Canvas */}
                          <div className="automation-hero-output-content">
                            {isExecutionMessagesLoading ? (
                              <div className="automation-output-loading">
                                <span className="automation-create-status-dot" />
                                <span>{t(appLanguage, 'loadingExecutionOutput')}</span>
                              </div>
                            ) : isAutomationRunningNow && executionMessages.length <= 1 ? (
                              <div className="automation-output-running-card">
                                <span className="automation-running-spinner" />
                                <div className="automation-running-text">
                                  <strong>{t(appLanguage, 'runningTask')}</strong>
                                  <p>{t(appLanguage, 'executingAutonomousSteps')}</p>
                                </div>
                              </div>
                            ) : assistantMsg ? (
                              <div className="automation-output-markdown-canvas">
                                <div className="markdown-content">
                                  <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                      a: ({ children, href }) => (
                                        <a
                                          href={href}
                                          onClick={(event) => {
                                            event.preventDefault()
                                            openAssistantLink(href)
                                          }}
                                          title={t(appLanguage, 'openInDefaultBrowser')}
                                        >
                                          {children}
                                        </a>
                                      )
                                    }}
                                  >
                                    {assistantMsg}
                                  </ReactMarkdown>
                                </div>
                              </div>
                            ) : currentExecution?.status === 'failed' ? (
                              <div className="automation-output-failed-card">
                                <strong>{t(appLanguage, 'executionStatusFailed')}</strong>
                                <p>{t(appLanguage, 'executionErrorOccurred')}</p>
                                <button
                                  className="settings-button settings-button-primary"
                                  onClick={() => void runAutomationNow(selectedAutomation.id)}
                                  type="button"
                                >
                                  {t(appLanguage, 'runNow')}
                                </button>
                              </div>
                            ) : automationExecutions.length === 0 ? (
                              <div className="automation-output-empty-card">
                                <p>{t(appLanguage, 'noExecutionsYetPrompt')}</p>
                                <button
                                  className="settings-button settings-button-primary"
                                  onClick={() => void runAutomationNow(selectedAutomation.id)}
                                  type="button"
                                >
                                  {t(appLanguage, 'runNow')}
                                </button>
                              </div>
                            ) : (
                              <div className="automation-output-empty-card">
                                <p>{t(appLanguage, 'noExecutionMessages')}</p>
                              </div>
                            )}
                          </div>
                        </div>
                      )
                    })()}

                    {/* Execution History Timeline Strip */}
                    {automationExecutions.length > 0 && (
                      <div className="automation-history-timeline-strip">
                        <span className="automation-history-timeline-label">
                          {t(appLanguage, 'executionHistoryTimeline')} (
                          {automationExecutions.length}):
                        </span>
                        <div className="automation-history-pills">
                          {automationExecutions.slice(0, 10).map((execution) => {
                            const isSelected =
                              selectedExecutionId === execution.automation_execution_id ||
                              (selectedExecutionId === null &&
                                automationExecutions[0]?.automation_execution_id ===
                                  execution.automation_execution_id)
                            return (
                              <button
                                className={`automation-history-pill ${execution.status}${
                                  isSelected ? ' is-selected' : ''
                                }`}
                                key={execution.automation_execution_id}
                                onClick={() =>
                                  selectExecutionHistory(execution.automation_execution_id)
                                }
                                type="button"
                              >
                                <span className="automation-history-pill-dot" />
                                <span className="automation-history-pill-time">
                                  {new Date(execution.scheduled_for).toLocaleString([], {
                                    month: 'numeric',
                                    day: 'numeric',
                                    hour: '2-digit',
                                    minute: '2-digit'
                                  })}
                                </span>
                                <span className="automation-history-pill-status">
                                  {execution.status === 'completed'
                                    ? '✓'
                                    : execution.status === 'failed'
                                      ? '✗'
                                      : '●'}
                                </span>
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </section>
            </div>
          </section>
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
              <div className="center-header-main">
                <div className="center-title">{t(appLanguage, 'settingsTitle')}</div>
                <div className="center-sub">{t(appLanguage, 'settingsSub')}</div>
              </div>
            </div>

            <div
              className={`settings-panel${visibleScrollbar === 'settings' ? ' scrollbar-visible' : ''}`}
              onScroll={() => revealScrollbar('settings')}
            >
              <section className="settings-section">
                <div className="settings-section-header">
                  <div>
                    <div className="settings-section-eyebrow">
                      {t(appLanguage, 'generalCategory')}
                    </div>
                    <div className="settings-section-title">
                      {t(appLanguage, 'languageSectionTitle')}
                    </div>
                    <p className="settings-section-copy">{t(appLanguage, 'languageSectionCopy')}</p>
                  </div>
                  <span className="settings-state configured">
                    {appLanguage === 'zh-Hans' ? '中文' : 'English'}
                  </span>
                </div>

                <div className="settings-key-form">
                  <label className="settings-field-label" htmlFor="settings-app-language">
                    {t(appLanguage, 'interfaceLanguageLabel')}
                  </label>
                  <select
                    className="settings-select"
                    id="settings-app-language"
                    onChange={(event) => {
                      handleAppLanguageChange(event.target.value as AppLanguage)
                    }}
                    value={appLanguage}
                  >
                    <option value="en">{t(appLanguage, 'languageEnglish')}</option>
                    <option value="zh-Hans">{t(appLanguage, 'languageChinese')}</option>
                  </select>
                </div>
              </section>

              <section className="settings-section">
                <div className="settings-section-header">
                  <div>
                    <div className="settings-section-eyebrow">
                      {t(appLanguage, 'modelPrivacyCategory')}
                    </div>
                    <div className="settings-section-title">
                      {t(appLanguage, 'modelProviderTitle')}
                    </div>
                    <p className="settings-section-copy">{t(appLanguage, 'modelProviderCopy')}</p>
                  </div>
                  <span
                    className={`settings-state${
                      modelSettings?.configured
                        ? modelSettings.active
                          ? ' configured'
                          : ' issue'
                        : ''
                    }`}
                  >
                    {modelSettings?.configured
                      ? modelSettings.active
                        ? `${modelSettings.location === 'local' ? t(appLanguage, 'badgeLocal') : t(appLanguage, 'badgeExternal')} ${t(appLanguage, 'activeBadge')}`
                        : `${modelSettings.location === 'local' ? t(appLanguage, 'badgeLocal') : t(appLanguage, 'badgeExternal')} ${t(appLanguage, 'needsAttentionBadge')}`
                      : t(appLanguage, 'notConfiguredBadge')}
                  </span>
                </div>

                {isModelLoading ? (
                  <p className="settings-section-status">
                    {t(appLanguage, 'loadingModelSettings')}
                  </p>
                ) : null}
                {modelLoadError !== null ? (
                  <p className="settings-section-error">{modelLoadError}</p>
                ) : null}
                {!isModelLoading && modelLoadError === null ? (
                  <div className="model-settings-flow">
                    <div className="model-connection-panel">
                      <div className="model-connection-header">
                        <p className="model-connection-copy">
                          {selectedProviderId === 'custom'
                            ? modelLocation === 'local'
                              ? t(appLanguage, 'localServerDesc')
                              : t(appLanguage, 'externalProviderDesc')
                            : getProviderPresetDescription(selectedProviderId, appLanguage)}
                        </p>
                        <span
                          className={`model-privacy-badge${
                            modelLocation === 'external' ? ' external' : ''
                          }`}
                        >
                          {modelLocation === 'local'
                            ? t(appLanguage, 'staysOnDevice')
                            : t(appLanguage, 'dataMayLeaveDevice')}
                        </span>
                      </div>

                      {isCurrentPresetConfigured &&
                      modelSettings !== null &&
                      modelSettings.issue !== null &&
                      modelSettings.location === modelLocation ? (
                        <div className="model-provider-warning" role="status">
                          <strong>{t(appLanguage, 'savedProviderNotActive')}</strong>
                          <span>
                            {modelSettings.issue === 'credential_store_unavailable'
                              ? t(appLanguage, 'keychainAccessError')
                              : t(appLanguage, 'savedApiKeyMissing')}
                          </span>
                        </div>
                      ) : null}

                      <div className="model-fields-grid">
                        <div className="model-field model-field-wide">
                          <label className="settings-field-label" htmlFor="model-provider-preset">
                            {t(appLanguage, 'provider')}
                          </label>
                          <select
                            className="settings-select"
                            disabled={isModelBusy}
                            id="model-provider-preset"
                            onChange={(event) => handleProviderPresetChange(event.target.value)}
                            value={selectedProviderId}
                          >
                            {MODEL_PROVIDER_PRESETS.map((preset) => (
                              <option key={preset.id} value={preset.id}>
                                {preset.name}
                              </option>
                            ))}
                          </select>
                        </div>

                        {selectedProviderId === 'custom' ? (
                          <div className="model-field model-field-wide">
                            <label className="settings-field-label" htmlFor="model-custom-location">
                              {t(appLanguage, 'locationLabel')}
                            </label>
                            <select
                              className="settings-select"
                              disabled={isModelBusy}
                              id="model-custom-location"
                              onChange={(event) =>
                                handleModelLocationChange(
                                  event.target.value as 'local' | 'external'
                                )
                              }
                              value={modelLocation}
                            >
                              <option value="external">
                                {t(appLanguage, 'locationExternalOption')}
                              </option>
                              <option value="local">{t(appLanguage, 'locationLocalOption')}</option>
                            </select>
                          </div>
                        ) : null}

                        <div className="model-field">
                          <label className="settings-field-label" htmlFor="model-name">
                            {t(appLanguage, 'modelName')}
                          </label>
                          <input
                            className="settings-text-input"
                            disabled={isModelBusy}
                            id="model-name"
                            onChange={(event) => setModelName(event.target.value)}
                            placeholder={getProviderPreset(selectedProviderId).placeholderModel}
                            spellCheck={false}
                            value={modelName}
                          />
                        </div>

                        <div className="model-field">
                          <label className="settings-field-label" htmlFor="model-base-url">
                            {t(appLanguage, 'baseUrl')}
                          </label>
                          <input
                            className="settings-text-input"
                            disabled={isModelBusy}
                            id="model-base-url"
                            onChange={(event) => setModelBaseUrl(event.target.value)}
                            placeholder={
                              getProviderPreset(selectedProviderId).defaultBaseUrl ||
                              (modelLocation === 'local'
                                ? 'http://127.0.0.1:11434/v1'
                                : 'https://api.openai.com/v1')
                            }
                            spellCheck={false}
                            value={modelBaseUrl}
                          />
                        </div>

                        <div className="model-field model-field-wide">
                          <label className="settings-field-label" htmlFor="model-api-key">
                            {modelLocation === 'local'
                              ? t(appLanguage, 'apiKeyOptionalLabel')
                              : t(appLanguage, 'apiKey')}
                          </label>
                          <input
                            autoComplete="off"
                            className="settings-text-input"
                            disabled={isModelBusy}
                            id="model-api-key"
                            onChange={(event) => setModelApiKey(event.target.value)}
                            placeholder={
                              isCurrentPresetApiKeySaved
                                ? '••••••••••••••••••••••••'
                                : modelLocation === 'local'
                                  ? t(appLanguage, 'apiKeyOnlyIfRequired')
                                  : t(appLanguage, 'apiKeyPlaceholder')
                            }
                            spellCheck={false}
                            title={
                              isCurrentPresetApiKeySaved
                                ? t(appLanguage, 'apiKeySavedInKeychain')
                                : undefined
                            }
                            type="password"
                            value={modelApiKey}
                          />
                        </div>
                      </div>

                      {modelActionError !== null ? (
                        <p className="settings-section-error model-settings-error">
                          {modelActionError}
                        </p>
                      ) : null}
                      <div className="settings-card-actions model-settings-actions">
                        <button
                          className="settings-button settings-button-primary"
                          disabled={isModelBusy}
                          onClick={() => {
                            void handleSaveModelSettings()
                          }}
                          type="button"
                        >
                          {t(appLanguage, 'saveModelSettings')}
                        </button>
                        {isCurrentPresetConfigured ? (
                          <button
                            className="settings-button settings-button-danger"
                            disabled={isModelBusy}
                            onClick={() => {
                              void handleRemoveModelSettings()
                            }}
                            type="button"
                          >
                            {t(appLanguage, 'removeModelSettings')}
                          </button>
                        ) : null}
                      </div>
                    </div>
                  </div>
                ) : null}
              </section>

              <section className="settings-section">
                <div className="settings-section-header">
                  <div>
                    <div className="settings-section-eyebrow">
                      {t(appLanguage, 'agentRuntimeCategory')}
                    </div>
                    <div className="settings-section-title">
                      {t(appLanguage, 'maxAgentStepsTitle')}
                    </div>
                    <p className="settings-section-copy">{t(appLanguage, 'maxAgentStepsCopy')}</p>
                  </div>
                  <span className="settings-state configured">
                    {agentSettings === null
                      ? '—'
                      : `${agentSettings.max_steps} ${t(appLanguage, 'stepUnit')}`}
                  </span>
                </div>

                {isAgentLoading ? (
                  <p className="settings-section-status">
                    {t(appLanguage, 'loadingAgentSettings')}
                  </p>
                ) : null}
                {agentLoadError !== null ? (
                  <p className="settings-section-error">{agentLoadError}</p>
                ) : null}
                {!isAgentLoading && agentLoadError === null ? (
                  <div className="settings-key-form">
                    <label className="settings-field-label" htmlFor="agent-max-steps">
                      {t(appLanguage, 'maxAgentStepsLabel')}
                    </label>
                    <input
                      className="settings-text-input"
                      disabled={isAgentBusy}
                      id="agent-max-steps"
                      inputMode="numeric"
                      max={50}
                      min={1}
                      onChange={(event) => setAgentMaxSteps(event.target.value)}
                      step={1}
                      type="number"
                      value={agentMaxSteps}
                    />
                    <div className="settings-card-actions">
                      <button
                        className="settings-button settings-button-primary"
                        disabled={isAgentBusy}
                        onClick={() => {
                          void handleSaveAgentSettings()
                        }}
                        type="button"
                      >
                        {t(appLanguage, 'saveAgentSettings')}
                      </button>
                    </div>
                  </div>
                ) : null}
                {agentActionError !== null ? (
                  <p className="settings-section-error">{agentActionError}</p>
                ) : null}
              </section>

              <section className="settings-section">
                <div className="settings-section-header">
                  <div>
                    <div className="settings-section-eyebrow">
                      {t(appLanguage, 'connectedToolCategory')}
                    </div>
                    <div className="settings-section-title">
                      {t(appLanguage, 'tavilySearchTitle')}
                    </div>
                    <p className="settings-section-copy">{t(appLanguage, 'tavilySearchCopy')}</p>
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
                  <p className="settings-section-status">
                    {t(appLanguage, 'loadingTavilySettings')}
                  </p>
                ) : null}

                {tavilyLoadError !== null ? (
                  <p className="settings-section-error">{tavilyLoadError}</p>
                ) : null}

                {!isTavilyLoading && tavilyLoadError === null && tavilySettings !== null ? (
                  <>
                    <p className="settings-section-status">
                      {tavilySettings.enabled
                        ? t(appLanguage, 'tavilyEnabledStatus')
                        : tavilySettings.api_key_saved
                          ? t(appLanguage, 'tavilyDisabledStatus')
                          : t(appLanguage, 'tavilyNotConfiguredStatus')}
                    </p>

                    {showTavilyKeyInput ? (
                      <div className="settings-key-form">
                        <label className="settings-field-label" htmlFor="tavily-api-key">
                          {t(appLanguage, 'apiKey')}
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
                            {isReplacingTavilyKey
                              ? t(appLanguage, 'saveApiKey')
                              : t(appLanguage, 'saveAndEnable')}
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
                              {t(appLanguage, 'cancel')}
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
                          {t(appLanguage, 'changeApiKey')}
                        </button>
                        <button
                          className="settings-button settings-button-danger"
                          disabled={isTavilyBusy}
                          onClick={() => {
                            void handleRemoveTavilyKey()
                          }}
                          type="button"
                        >
                          {t(appLanguage, 'removeSavedApiKey')}
                        </button>
                      </div>
                    ) : null}
                  </>
                ) : null}

                {tavilyActionError !== null ? (
                  <p className="settings-section-error">{tavilyActionError}</p>
                ) : null}
              </section>

              <section className="settings-section">
                <div className="settings-section-header">
                  <div>
                    <div className="settings-section-eyebrow">
                      {t(appLanguage, 'dataSpaceCategory')}
                    </div>
                    <div className="settings-section-title">
                      {t(appLanguage, 'storageSnapshotsTitle')}
                    </div>
                    <p className="settings-section-copy">
                      {t(appLanguage, 'storageSnapshotsCopy')}
                    </p>
                  </div>
                </div>

                {isStorageLoading ? (
                  <p className="settings-section-status">
                    {t(appLanguage, 'loadingStorageSettings')}
                  </p>
                ) : null}

                {storageLoadError !== null ? (
                  <p className="settings-section-error">{storageLoadError}</p>
                ) : null}

                {!isStorageLoading && storageLoadError === null && storageSettings !== null ? (
                  <div className="settings-key-form">
                    <div className="storage-usage-row">
                      <span className="settings-field-label">
                        {t(appLanguage, 'currentSnapshotUsage')}
                      </span>
                      <span className="storage-usage-value">
                        {formatBytes(storageSettings.usage_bytes)} ({storageSettings.snapshot_count}{' '}
                        {storageSettings.snapshot_count === 1
                          ? t(appLanguage, 'snapshotUnitSingle')
                          : t(appLanguage, 'snapshotUnit')}
                        )
                      </span>
                    </div>

                    <label className="settings-field-label" htmlFor="storage-retention">
                      {t(appLanguage, 'snapshotRetentionLabel')}
                    </label>
                    <select
                      className="settings-text-input settings-select"
                      disabled={isStorageBusy}
                      id="storage-retention"
                      onChange={(event) => {
                        void handleSaveStorageRetention(Number(event.target.value))
                      }}
                      value={storageRetentionDays}
                    >
                      <option value={1}>{t(appLanguage, 'retention1Day')}</option>
                      <option value={3}>{t(appLanguage, 'retention3Days')}</option>
                      <option value={7}>{t(appLanguage, 'retention7Days')}</option>
                      <option value={30}>{t(appLanguage, 'retention30Days')}</option>
                      <option value={0}>{t(appLanguage, 'retentionNever')}</option>
                    </select>

                    <div className="settings-card-actions" style={{ marginTop: '12px' }}>
                      <button
                        className="settings-button settings-button-danger"
                        disabled={isStorageBusy || storageSettings.snapshot_count === 0}
                        onClick={() => {
                          void handleClearStorageSnapshots()
                        }}
                        type="button"
                      >
                        {t(appLanguage, 'clearAllSnapshotsNow')}
                      </button>
                    </div>

                    {storageActionSuccess !== null ? (
                      <p
                        className="settings-section-status"
                        style={{ color: 'var(--success, #2e7d32)', marginTop: '8px' }}
                      >
                        {storageActionSuccess}
                      </p>
                    ) : null}
                  </div>
                ) : null}

                {storageActionError !== null ? (
                  <p className="settings-section-error">{storageActionError}</p>
                ) : null}
              </section>

              <section className="settings-section">
                <div className="settings-section-header">
                  <div>
                    <div className="settings-section-eyebrow">
                      {t(appLanguage, 'aboutCategory')}
                    </div>
                    <div className="settings-section-title">{t(appLanguage, 'aboutTitle')}</div>
                    <p className="settings-section-copy">{t(appLanguage, 'aboutCopy')}</p>
                  </div>
                </div>

                <div className="settings-key-form">
                  <div className="storage-usage-row">
                    <span className="settings-field-label">
                      {t(appLanguage, 'currentVersionLabel')}
                    </span>
                    <span
                      className="storage-usage-value"
                      style={{ fontFamily: 'var(--font-mono, monospace)' }}
                    >
                      v{appVersion || '0.0.1'}
                    </span>
                  </div>

                  <div className="settings-card-actions" style={{ marginTop: '14px' }}>
                    <button
                      className="settings-button settings-button-secondary"
                      disabled={isCheckingUpdate}
                      onClick={() => {
                        void handleManualCheckForUpdates()
                      }}
                      type="button"
                    >
                      {isCheckingUpdate
                        ? t(appLanguage, 'checkingForUpdates')
                        : t(appLanguage, 'checkForUpdates')}
                    </button>
                  </div>

                  {updateResult !== null && updateResult.hasUpdate ? (
                    <div className="update-available-banner">
                      <div className="update-available-header">
                        <span className="update-available-badge">
                          {t(appLanguage, 'updateAvailable')}: {updateResult.latestVersion}
                        </span>
                        <p className="update-available-copy">{t(appLanguage, 'newVersionFound')}</p>
                      </div>
                      {updateResult.releaseNotes ? (
                        <div className="update-release-notes">
                          <div className="update-notes-title">
                            {t(appLanguage, 'releaseNotesTitle')}
                          </div>
                          <pre className="update-notes-content">{updateResult.releaseNotes}</pre>
                        </div>
                      ) : null}
                      <div style={{ marginTop: '12px' }}>
                        <button
                          className="settings-button settings-button-primary"
                          onClick={() => {
                            void window.desktop.openExternalLink(
                              updateResult.downloadUrl ||
                                'https://github.com/yuting-ai/asAgent/releases/latest/download/asAgent-arm64.dmg'
                            )
                          }}
                          type="button"
                        >
                          {t(appLanguage, 'downloadUpdate')}
                        </button>
                      </div>
                    </div>
                  ) : null}

                  {updateResult !== null && !updateResult.hasUpdate && !isCheckingUpdate ? (
                    <p
                      className="settings-section-status"
                      style={{ color: 'var(--success, #2e7d32)', marginTop: '10px' }}
                    >
                      ✓ {t(appLanguage, 'upToDate')} (v{appVersion || '0.0.1'})
                    </p>
                  ) : null}

                  {updateCheckError !== null ? (
                    <p className="settings-section-error" style={{ marginTop: '10px' }}>
                      {updateCheckError}
                    </p>
                  ) : null}
                </div>
              </section>
            </div>
          </section>
        </div>
      </div>
      {restartRequested ? (
        <div aria-modal="true" className="restart-modal-backdrop" role="dialog">
          <section aria-labelledby="restart-modal-title" className="restart-modal">
            <div className="restart-modal-eyebrow">{t(appLanguage, 'restartNoticeTitle')}</div>
            <h2 id="restart-modal-title">{t(appLanguage, 'restartDialogTitle')}</h2>
            <p>{t(appLanguage, 'restartNoticeBody')}</p>
            <div className="restart-modal-actions">
              <button
                className="settings-button settings-button-secondary"
                disabled={isRestarting}
                onClick={() => setRestartRequested(false)}
                type="button"
              >
                {t(appLanguage, 'restartLater')}
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
                {isRestarting ? t(appLanguage, 'restarting') : t(appLanguage, 'restartNow')}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  )
}
