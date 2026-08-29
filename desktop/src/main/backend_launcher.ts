import { spawn, type ChildProcess } from 'node:child_process'
import { randomBytes } from 'node:crypto'

const READY_PREFIX = 'ASAGENT_READY '
const ANSI_ESCAPE_PATTERN = new RegExp(String.raw`\x1B\[[0-?]*[ -/]*[@-~]`, 'g')

type ServerReady = {
  host: string
  port: number
  pid: number
  protocolVersion: number
}

export type ConversationSummary = {
  conversation_id: string
  created_at: string
  updated_at: string
  title: string | null
  last_page_url: string | null
  last_page_title: string | null
}

export type AutomationSummary = {
  automation_id: string
  name: string
  plan_summary: string
  allowed_capabilities: string[]
  status: 'draft' | 'active' | 'paused'
  created_at: string
  updated_at: string
}

export type AutomationTrigger = {
  automation_trigger_id: string
  kind: 'once' | 'daily' | 'weekly'
  timezone: string
  local_time: string
  weekday: number | null
  next_run_at: string | null
  enabled: boolean
}

export type AutomationExecution = {
  automation_execution_id: string
  scheduled_for: string
  status: 'claimed' | 'missed' | 'completed' | 'failed' | 'cancelled'
  run_id: string | null
  claimed_at: string
  completed_at: string | null
}

export type CreateAutomationInput = {
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

export type UpdateAutomationInput = CreateAutomationInput

export type ConversationMessage = {
  message_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export type RunSummary = {
  run_id: string
  status: 'created' | 'completed' | 'failed' | 'cancelled' | 'limit_reached'
  created_at: string
  updated_at: string
}

export type SubmittedMessage = {
  message: ConversationMessage
  run: RunSummary
  conversation: ConversationSummary
}

export type RunEvent = {
  event_id: string
  run_id: string
  conversation_id: string
  sequence: number
  event_type: string
  created_at: string
  data: Record<string, unknown>
}

export type RunHistory = {
  run: RunSummary
  events: Array<{
    event_type: string
    created_at: string
    data: Record<string, unknown>
  }>
}

export type ToolApprovalDecision = 'deny' | 'allow_once' | 'allow_conversation'

const TOOL_APPROVAL_DECISIONS: ReadonlySet<ToolApprovalDecision> = new Set([
  'deny',
  'allow_once',
  'allow_conversation'
])

export function isToolApprovalDecision(value: unknown): value is ToolApprovalDecision {
  return typeof value === 'string' && TOOL_APPROVAL_DECISIONS.has(value as ToolApprovalDecision)
}

export type ToolApproval = {
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

export type FileChange = {
  change_id: string
  run_id: string
  operation: 'create' | 'replace' | 'delete'
  status: 'prepared' | 'applied' | 'reverted' | 'conflicted'
  path: string
  created_at: string
  updated_at: string
}

export type CreatedConversation = ConversationSummary

export type TavilySettingsStatus = {
  enabled: boolean
  api_key_saved: boolean
}

export type SavedProviderConfigStatus = {
  location: 'local' | 'external'
  model: string
  base_url: string
  api_key_saved: boolean
}

export type ModelSettingsStatus = {
  configured: boolean
  active: boolean
  issue: 'api_key_missing' | 'credential_store_unavailable' | null
  location: 'local' | 'external' | null
  api_key_saved: boolean
  model: string | null
  base_url: string | null
  saved_providers?: Record<string, SavedProviderConfigStatus>
}

export type AgentSettingsStatus = {
  max_steps: number
}

export type ModelSettingsInput = {
  location: 'local' | 'external'
  model: string
  baseUrl: string
  apiKey?: string
}

export type AgentSettingsInput = {
  maxSteps: number
}

export type StorageSettingsStatus = {
  snapshot_retention_days: number
  usage_bytes: number
  snapshot_count: number
}

export type StorageSettingsInput = {
  snapshot_retention_days: number
}

export type ClearStorageResult = {
  freed_bytes: number
  deleted_count: number
}

export type WorkspaceSettingsStatus = {
  workspace_root: string
  additional_roots: string[]
  additional_files: string[]
}

export type WorkspaceSettingsInput = {
  additionalRoots: string[]
  additionalFiles: string[]
}

type BackendLauncherOptions = {
  projectRoot: string
  appHome: string
  backendExecutable?: string
  spawnBackend?: typeof spawn
  fetchBackend?: typeof fetch
  startupTimeoutMs?: number
  healthTimeoutMs?: number
  healthRetryIntervalMs?: number
  stopTimeoutMs?: number
  onDiagnosticOutput?: (stream: 'stdout' | 'stderr', output: string) => void
  providerProfile?: string
  secretEnvironmentName?: string
  environmentFile?: string
  browserBridge?: {
    baseUrl: string
    token: string
  }
}

function sanitizeDiagnosticOutput(output: string): string {
  return output
    .replace(ANSI_ESCAPE_PATTERN, '')
    .replace(/("token"\s*:\s*")[^"]+("?)/gi, '$1[REDACTED]$2')
    .replace(/(Bearer\s+)[A-Za-z0-9._~+/=-]+/gi, '$1[REDACTED]')
}

function parseReadyRecord(line: string): ServerReady | null {
  if (!line.startsWith(READY_PREFIX)) {
    return null
  }

  let payload: unknown
  try {
    payload = JSON.parse(line.slice(READY_PREFIX.length))
  } catch {
    throw new Error('Backend ready record is invalid.')
  }

  if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
    throw new Error('Backend ready record is invalid.')
  }

  const record = payload as Record<string, unknown>

  if (
    record.host !== '127.0.0.1' ||
    !Number.isInteger(record.port) ||
    typeof record.port !== 'number' ||
    record.port < 1 ||
    record.port > 65535 ||
    !Number.isInteger(record.pid) ||
    typeof record.pid !== 'number' ||
    record.pid < 1 ||
    record.protocol_version !== 1
  ) {
    throw new Error('Backend ready record is invalid.')
  }

  return {
    host: record.host,
    port: record.port,
    pid: record.pid,
    protocolVersion: record.protocol_version
  }
}

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds)
  })
}

function parseSseEvent(frame: string): RunEvent | null {
  const dataLine = frame.split('\n').find((line) => line.startsWith('data: '))

  if (dataLine === undefined) {
    return null
  }

  let payload: unknown
  try {
    payload = JSON.parse(dataLine.slice('data: '.length))
  } catch {
    throw new Error('Backend SSE event is invalid.')
  }

  if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
    throw new Error('Backend SSE event is invalid.')
  }

  const event = payload as Record<string, unknown>

  if (
    typeof event.event_id !== 'string' ||
    typeof event.run_id !== 'string' ||
    typeof event.conversation_id !== 'string' ||
    typeof event.sequence !== 'number' ||
    typeof event.event_type !== 'string' ||
    typeof event.created_at !== 'string' ||
    typeof event.data !== 'object' ||
    event.data === null ||
    Array.isArray(event.data)
  ) {
    throw new Error('Backend SSE event is invalid.')
  }

  return {
    event_id: event.event_id,
    run_id: event.run_id,
    conversation_id: event.conversation_id,
    sequence: event.sequence,
    event_type: event.event_type,
    created_at: event.created_at,
    data: event.data as Record<string, unknown>
  }
}

export class BackendLauncher {
  private readonly projectRoot: string
  private readonly appHome: string
  private readonly backendExecutable: string | undefined
  private readonly spawnBackend: typeof spawn
  private readonly fetchBackend: typeof fetch
  private readonly startupTimeoutMs: number
  private readonly healthTimeoutMs: number
  private readonly healthRetryIntervalMs: number
  private readonly stopTimeoutMs: number
  private readonly onDiagnosticOutput:
    ((stream: 'stdout' | 'stderr', output: string) => void) | undefined
  private readonly providerProfile: string | undefined
  private readonly secretEnvironmentName: string | undefined
  private readonly environmentFile: string | undefined
  private readonly browserBridge:
    | {
        baseUrl: string
        token: string
      }
    | undefined
  private child: ChildProcess | undefined
  private ready: ServerReady | undefined
  private token: string | undefined

  constructor(options: BackendLauncherOptions) {
    this.projectRoot = options.projectRoot
    this.appHome = options.appHome
    this.backendExecutable = options.backendExecutable
    this.spawnBackend = options.spawnBackend ?? spawn
    this.fetchBackend = options.fetchBackend ?? fetch
    this.startupTimeoutMs = options.startupTimeoutMs ?? 15_000
    this.healthTimeoutMs = options.healthTimeoutMs ?? 15_000
    this.healthRetryIntervalMs = options.healthRetryIntervalMs ?? 100
    this.stopTimeoutMs = options.stopTimeoutMs ?? 3_000
    this.onDiagnosticOutput = options.onDiagnosticOutput
    this.providerProfile = options.providerProfile
    this.secretEnvironmentName = options.secretEnvironmentName
    this.environmentFile = options.environmentFile
    this.browserBridge = options.browserBridge

    const realProviderConfigured = this.providerProfile !== undefined

    if (
      realProviderConfigured !== (this.secretEnvironmentName !== undefined) ||
      realProviderConfigured !== (this.environmentFile !== undefined)
    ) {
      throw new Error('Real Provider configuration is incomplete.')
    }
  }

  get isReady(): boolean {
    return this.ready !== undefined
  }

  async listConversations(): Promise<ConversationSummary[]> {
    return this.requestJson('/api/v1/conversations', 'GET')
  }

  async listAutomations(): Promise<AutomationSummary[]> {
    return this.requestJson('/api/v1/automations', 'GET')
  }

  async createAutomation(input: CreateAutomationInput): Promise<AutomationSummary> {
    return this.requestJson('/api/v1/automations', 'POST', {
      name: input.name,
      plan_summary: input.planSummary,
      allowed_capabilities: input.allowedCapabilities,
      trigger: {
        kind: input.trigger.kind,
        timezone: input.trigger.timezone,
        local_time: input.trigger.localTime,
        weekday: input.trigger.weekday,
        next_run_at: input.trigger.nextRunAt
      }
    })
  }

  async updateAutomation(
    automationId: string,
    input: UpdateAutomationInput
  ): Promise<AutomationSummary> {
    return this.requestJson(`/api/v1/automations/${encodeURIComponent(automationId)}`, 'PUT', {
      name: input.name,
      plan_summary: input.planSummary,
      allowed_capabilities: input.allowedCapabilities,
      trigger: {
        kind: input.trigger.kind,
        timezone: input.trigger.timezone,
        local_time: input.trigger.localTime,
        weekday: input.trigger.weekday,
        next_run_at: input.trigger.nextRunAt
      }
    })
  }

  async deleteAutomation(automationId: string): Promise<void> {
    await this.request(`/api/v1/automations/${encodeURIComponent(automationId)}`, 'DELETE')
  }

  async updateAutomationStatus(
    automationId: string,
    status: AutomationSummary['status']
  ): Promise<AutomationSummary> {
    return this.requestJson(
      `/api/v1/automations/${encodeURIComponent(automationId)}/status`,
      'PUT',
      { status }
    )
  }

  async listAutomationTriggers(automationId: string): Promise<AutomationTrigger[]> {
    return this.requestJson(
      `/api/v1/automations/${encodeURIComponent(automationId)}/triggers`,
      'GET'
    )
  }

  async listAutomationExecutions(automationId: string): Promise<AutomationExecution[]> {
    return this.requestJson(
      `/api/v1/automations/${encodeURIComponent(automationId)}/executions`,
      'GET'
    )
  }

  async getAutomationExecutionMessages(
    automationId: string,
    executionId: string
  ): Promise<ConversationMessage[]> {
    return this.requestJson(
      `/api/v1/automations/${encodeURIComponent(automationId)}/executions/${encodeURIComponent(executionId)}/messages`,
      'GET'
    )
  }

  async runAutomationNow(automationId: string): Promise<AutomationExecution> {
    return this.requestJson(
      `/api/v1/automations/${encodeURIComponent(automationId)}/run-now`,
      'POST',
      {}
    )
  }

  async createAutomationDraft(
    automationId?: string,
    timezone = 'UTC'
  ): Promise<CreatedConversation> {
    return this.requestJson('/api/v1/automation-drafts', 'POST', {
      automation_id: automationId,
      timezone
    })
  }

  async listAutomationDraftMessages(conversationId: string): Promise<ConversationMessage[]> {
    return this.requestJson(
      `/api/v1/automation-drafts/${encodeURIComponent(conversationId)}/messages`,
      'GET'
    )
  }

  async submitAutomationDraftMessage(
    conversationId: string,
    content: string,
    tabId?: string
  ): Promise<SubmittedMessage> {
    return this.requestJson(
      `/api/v1/automation-drafts/${encodeURIComponent(conversationId)}/messages`,
      'POST',
      { content, tab_id: tabId }
    )
  }

  async deleteAutomationDraft(conversationId: string): Promise<void> {
    await this.request(`/api/v1/automation-drafts/${encodeURIComponent(conversationId)}`, 'DELETE')
  }

  async listConversationMessages(conversationId: string): Promise<ConversationMessage[]> {
    return this.requestJson(
      `/api/v1/conversations/${encodeURIComponent(conversationId)}/messages`,
      'GET'
    )
  }

  async listConversationRunHistory(conversationId: string): Promise<RunHistory[]> {
    return this.requestJson(
      `/api/v1/conversations/${encodeURIComponent(conversationId)}/run-history`,
      'GET'
    )
  }

  async listConversationFileChanges(conversationId: string): Promise<FileChange[]> {
    return this.requestJson(
      `/api/v1/conversations/${encodeURIComponent(conversationId)}/file-changes`,
      'GET'
    )
  }

  async undoFileChange(changeId: string, path: string): Promise<FileChange> {
    return this.requestJson(`/api/v1/file-changes/${encodeURIComponent(changeId)}/undo`, 'POST', {
      path
    })
  }

  async createConversation(): Promise<CreatedConversation> {
    return this.requestJson('/api/v1/conversations', 'POST', {})
  }

  async updateConversationTitle(
    conversationId: string,
    title: string
  ): Promise<ConversationSummary> {
    if (!title.trim()) {
      throw new Error('Conversation title is invalid.')
    }

    return this.requestJson<ConversationSummary>(
      `/api/v1/conversations/${encodeURIComponent(conversationId)}`,
      'PATCH',
      { title }
    )
  }

  async deleteConversation(conversationId: string): Promise<void> {
    await this.request(`/api/v1/conversations/${encodeURIComponent(conversationId)}`, 'DELETE')
  }

  async deleteBrowserConversation(conversationId: string): Promise<void> {
    await this.request(
      `/api/v1/browser/conversations/${encodeURIComponent(conversationId)}`,
      'DELETE'
    )
  }

  async submitMessage(conversationId: string, content: string): Promise<SubmittedMessage> {
    if (!content.trim()) {
      throw new Error('Message content is invalid.')
    }

    return this.requestJson<SubmittedMessage>(
      `/api/v1/conversations/${encodeURIComponent(conversationId)}/messages`,
      'POST',
      { content }
    )
  }

  async listBrowserConversations(): Promise<ConversationSummary[]> {
    return this.requestJson('/api/v1/browser/conversations', 'GET')
  }

  async createBrowserConversation(): Promise<CreatedConversation> {
    return this.requestJson('/api/v1/browser/conversations', 'POST', {})
  }

  async listBrowserConversationMessages(conversationId: string): Promise<ConversationMessage[]> {
    return this.requestJson(
      `/api/v1/browser/conversations/${encodeURIComponent(conversationId)}/messages`,
      'GET'
    )
  }

  async listBrowserConversationRunHistory(conversationId: string): Promise<RunHistory[]> {
    return this.requestJson(
      `/api/v1/browser/conversations/${encodeURIComponent(conversationId)}/run-history`,
      'GET'
    )
  }

  async submitBrowserMessage(
    conversationId: string,
    content: string,
    tabId: string,
    lastPageUrl: string | null,
    lastPageTitle: string | null
  ): Promise<SubmittedMessage> {
    if (!content.trim()) {
      throw new Error('Message content is invalid.')
    }
    if (!tabId.trim()) {
      throw new Error('Browser tab is invalid.')
    }

    return this.requestJson<SubmittedMessage>(
      `/api/v1/browser/conversations/${encodeURIComponent(conversationId)}/messages`,
      'POST',
      {
        content,
        tab_id: tabId,
        last_page_url: lastPageUrl,
        last_page_title: lastPageTitle
      }
    )
  }

  async cancelRun(runId: string): Promise<void> {
    await this.requestJson(`/api/v1/runs/${encodeURIComponent(runId)}/cancel`, 'POST', {})
  }

  async getToolApproval(approvalId: string): Promise<ToolApproval> {
    return this.requestJson(`/api/v1/tool-approvals/${encodeURIComponent(approvalId)}`, 'GET')
  }

  async decideToolApproval(approvalId: string, decision: ToolApprovalDecision): Promise<void> {
    await this.requestJson(
      `/api/v1/tool-approvals/${encodeURIComponent(approvalId)}/decision`,
      'POST',
      { decision }
    )
  }

  async getTavilySettings(): Promise<TavilySettingsStatus> {
    return this.requestJson('/api/v1/settings/tavily', 'GET')
  }

  async enableTavily(apiKey?: string): Promise<TavilySettingsStatus> {
    return this.requestJson(
      '/api/v1/settings/tavily',
      'PUT',
      apiKey === undefined ? {} : { api_key: apiKey }
    )
  }

  async disableTavily(): Promise<TavilySettingsStatus> {
    return this.requestJson('/api/v1/settings/tavily/disable', 'POST', {})
  }

  async deleteTavily(): Promise<TavilySettingsStatus> {
    return this.requestJson('/api/v1/settings/tavily', 'DELETE')
  }

  async getModelSettings(): Promise<ModelSettingsStatus> {
    return this.requestJson('/api/v1/settings/model', 'GET')
  }

  async saveModelSettings(input: ModelSettingsInput): Promise<ModelSettingsStatus> {
    return this.requestJson('/api/v1/settings/model', 'PUT', {
      location: input.location,
      model: input.model,
      base_url: input.baseUrl,
      ...(input.apiKey === undefined ? {} : { api_key: input.apiKey })
    })
  }

  async deleteModelSettings(): Promise<ModelSettingsStatus> {
    return this.requestJson('/api/v1/settings/model', 'DELETE')
  }

  async getAgentSettings(): Promise<AgentSettingsStatus> {
    return this.requestJson('/api/v1/agent-settings', 'GET')
  }

  async saveAgentSettings(input: AgentSettingsInput): Promise<AgentSettingsStatus> {
    return this.requestJson('/api/v1/agent-settings', 'PUT', {
      max_steps: input.maxSteps
    })
  }

  async getStorageSettings(): Promise<StorageSettingsStatus> {
    return this.requestJson('/api/v1/settings/storage', 'GET')
  }

  async saveStorageSettings(input: StorageSettingsInput): Promise<StorageSettingsStatus> {
    return this.requestJson('/api/v1/settings/storage', 'PUT', {
      snapshot_retention_days: input.snapshot_retention_days
    })
  }

  async clearStorageSnapshots(): Promise<ClearStorageResult> {
    return this.requestJson('/api/v1/settings/storage/clear', 'POST')
  }

  async getConversationFileAccess(conversationId: string): Promise<WorkspaceSettingsStatus> {
    return this.requestJson(`/api/v1/conversations/${conversationId}/file-access`, 'GET')
  }

  async saveConversationFileAccess(
    conversationId: string,
    input: WorkspaceSettingsInput
  ): Promise<WorkspaceSettingsStatus> {
    return this.requestJson(`/api/v1/conversations/${conversationId}/file-access`, 'PUT', {
      additional_roots: input.additionalRoots,
      additional_files: input.additionalFiles
    })
  }

  watchRunEvents(
    runId: string,
    onEvent: (event: RunEvent) => void,
    onError: (error: Error) => void
  ): () => void {
    const controller = new AbortController()

    void this.readRunEvents(runId, onEvent, controller.signal).catch((error) => {
      if (!controller.signal.aborted) {
        onError(error instanceof Error ? error : new Error('Run event stream failed.'))
      }
    })

    return () => controller.abort()
  }

  private async requestJson<T>(
    path: string,
    method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
    body?: unknown
  ): Promise<T> {
    const response = await this.request(path, method, body)
    return (await response.json()) as T
  }

  private async request(
    path: string,
    method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
    body?: unknown,
    signal?: AbortSignal
  ): Promise<Response> {
    if (this.ready === undefined || this.token === undefined) {
      throw new Error('Backend is not ready.')
    }

    const response = await this.fetchBackend(
      `http://${this.ready.host}:${this.ready.port}${path}`,
      {
        method,
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${this.token}`,
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' })
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        signal: signal ?? AbortSignal.timeout(5_000)
      }
    )

    if (!response.ok) {
      throw new Error(`Backend API request failed with status ${response.status}.`)
    }

    return response
  }

  private async readRunEvents(
    runId: string,
    onEvent: (event: RunEvent) => void,
    signal: AbortSignal
  ): Promise<void> {
    const response = await this.request(
      `/api/v1/runs/${encodeURIComponent(runId)}/events`,
      'GET',
      undefined,
      signal
    )

    if (response.body === null) {
      throw new Error('Backend SSE response has no body.')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        buffer += decoder.decode(value, { stream: !done }).replaceAll('\r\n', '\n')

        let boundary = buffer.indexOf('\n\n')
        while (boundary !== -1) {
          const frame = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)

          const event = parseSseEvent(frame)
          if (event !== null) {
            onEvent(event)
          }

          boundary = buffer.indexOf('\n\n')
        }

        if (done) {
          return
        }
      }
    } finally {
      reader.releaseLock()
    }
  }

  async start(): Promise<void> {
    if (this.child !== undefined) {
      throw new Error('Backend has already been started.')
    }

    const token = randomBytes(32).toString('base64url')
    let child: ChildProcess

    if (this.backendExecutable !== undefined) {
      const commandArgs = ['serve', '--bootstrap-stdin', '--app-home', this.appHome, '--port', '0']
      child = this.spawnBackend(this.backendExecutable, commandArgs, {
        cwd: this.projectRoot,
        env: process.env,
        stdio: 'pipe'
      })
    } else {
      const command = ['run']

      if (this.environmentFile !== undefined) {
        command.push('--env-file', this.environmentFile)
      }

      command.push('asagent', 'serve', '--bootstrap-stdin')

      if (this.providerProfile !== undefined && this.secretEnvironmentName !== undefined) {
        command.push('--profile', this.providerProfile, '--secret-env', this.secretEnvironmentName)
      }

      command.push('--app-home', this.appHome, '--port', '0')

      child = this.spawnBackend('uv', command, {
        cwd: this.projectRoot,
        env: process.env,
        stdio: 'pipe'
      })
    }

    if (child.stdin === null || child.stdout === null) {
      child.kill('SIGTERM')
      throw new Error('Backend standard streams are unavailable.')
    }

    this.child = child
    this.token = token
    const ready = this.waitForReady(child)
    child.stdout.on('data', (chunk: Buffer) => {
      this.emitDiagnosticOutput('stdout', chunk)
    })
    child.stderr?.on('data', (chunk: Buffer) => {
      this.emitDiagnosticOutput('stderr', chunk)
    })
    const bootstrap: Record<string, unknown> = { token }
    if (this.browserBridge !== undefined) {
      bootstrap['browser_bridge'] = {
        base_url: this.browserBridge.baseUrl,
        token: this.browserBridge.token
      }
    }
    child.stdin.end(`${JSON.stringify(bootstrap)}\n`)

    try {
      const readyRecord = await ready
      await this.waitForHealthy(readyRecord, token)
      this.ready = readyRecord
    } catch (error) {
      await this.stop()
      throw error
    }
  }

  private emitDiagnosticOutput(stream: 'stdout' | 'stderr', chunk: Buffer): void {
    const output = sanitizeDiagnosticOutput(chunk.toString('utf8'))
    if (output.length > 0) {
      this.onDiagnosticOutput?.(stream, output)
    }
  }

  async stop(): Promise<void> {
    const child = this.child
    this.child = undefined
    this.ready = undefined
    this.token = undefined

    if (child === undefined || child.exitCode !== null || child.killed) {
      return
    }

    await new Promise<void>((resolve) => {
      const timeout = setTimeout(() => {
        child.kill('SIGKILL')
        resolve()
      }, this.stopTimeoutMs)

      child.once('exit', () => {
        clearTimeout(timeout)
        resolve()
      })

      child.kill('SIGTERM')
    })
  }

  private waitForReady(child: ChildProcess): Promise<ServerReady> {
    const stdout = child.stdout
    if (stdout === null) {
      return Promise.reject(new Error('Backend standard output is unavailable.'))
    }

    return new Promise((resolve, reject) => {
      let buffer = ''

      const finish = (callback: () => void): void => {
        clearTimeout(timeout)
        stdout.off('data', onData)
        child.off('error', onError)
        child.off('exit', onExit)
        callback()
      }

      const fail = (error: Error): void => {
        finish(() => reject(error))
      }

      const onData = (chunk: Buffer): void => {
        buffer += chunk.toString('utf8')

        while (true) {
          const newlineIndex = buffer.indexOf('\n')
          if (newlineIndex === -1) {
            return
          }

          const line = buffer.slice(0, newlineIndex)
          buffer = buffer.slice(newlineIndex + 1)

          try {
            const ready = parseReadyRecord(line)
            if (ready !== null) {
              finish(() => resolve(ready))
              return
            }
          } catch (error) {
            fail(error instanceof Error ? error : new Error('Backend startup failed.'))
            return
          }
        }
      }

      const onError = (error: Error): void => {
        fail(error)
      }

      const onExit = (code: number | null, signal: NodeJS.Signals | null): void => {
        const reason = signal !== null ? `signal ${signal}` : `exit code ${code ?? 'unknown'}`
        fail(new Error(`Backend stopped before it became ready (${reason}).`))
      }

      const timeout = setTimeout(() => {
        fail(new Error('Backend readiness timed out.'))
      }, this.startupTimeoutMs)

      stdout.on('data', onData)
      child.once('error', onError)
      child.once('exit', onExit)
    })
  }

  private async waitForHealthy(ready: ServerReady, token: string): Promise<void> {
    const deadline = Date.now() + this.healthTimeoutMs
    const healthUrl = `http://${ready.host}:${ready.port}/api/v1/health`

    while (Date.now() < deadline) {
      try {
        const response = await this.fetchBackend(healthUrl, {
          headers: {
            Authorization: `Bearer ${token}`
          },
          signal: AbortSignal.timeout(1_000)
        })

        if (response.ok) {
          return
        }
      } catch {
        // Startup retries are bounded by the overall health deadline.
      }

      await wait(this.healthRetryIntervalMs)
    }

    throw new Error('Backend health check timed out.')
  }
}
