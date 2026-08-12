import { spawn, type ChildProcess } from 'node:child_process'
import { randomBytes } from 'node:crypto'

const READY_PREFIX = 'ASAGENT_READY '

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
}

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
}

export type CreatedConversation = ConversationSummary

export type TavilySettingsStatus = {
  enabled: boolean
  api_key_saved: boolean
}

type BackendLauncherOptions = {
  projectRoot: string
  appHome: string
  spawnBackend?: typeof spawn
  fetchBackend?: typeof fetch
  startupTimeoutMs?: number
  healthTimeoutMs?: number
  healthRetryIntervalMs?: number
  stopTimeoutMs?: number
  providerProfile?: string
  secretEnvironmentName?: string
  environmentFile?: string
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
  private readonly spawnBackend: typeof spawn
  private readonly fetchBackend: typeof fetch
  private readonly startupTimeoutMs: number
  private readonly healthTimeoutMs: number
  private readonly healthRetryIntervalMs: number
  private readonly stopTimeoutMs: number
  private readonly providerProfile: string | undefined
  private readonly secretEnvironmentName: string | undefined
  private readonly environmentFile: string | undefined
  private child: ChildProcess | undefined
  private ready: ServerReady | undefined
  private token: string | undefined

  constructor(options: BackendLauncherOptions) {
    this.projectRoot = options.projectRoot
    this.appHome = options.appHome
    this.spawnBackend = options.spawnBackend ?? spawn
    this.fetchBackend = options.fetchBackend ?? fetch
    this.startupTimeoutMs = options.startupTimeoutMs ?? 5_000
    this.healthTimeoutMs = options.healthTimeoutMs ?? 5_000
    this.healthRetryIntervalMs = options.healthRetryIntervalMs ?? 100
    this.stopTimeoutMs = options.stopTimeoutMs ?? 3_000
    this.providerProfile = options.providerProfile
    this.secretEnvironmentName = options.secretEnvironmentName
    this.environmentFile = options.environmentFile

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

  async listConversationMessages(conversationId: string): Promise<ConversationMessage[]> {
    return this.requestJson(
      `/api/v1/conversations/${encodeURIComponent(conversationId)}/messages`,
      'GET'
    )
  }

  async createConversation(): Promise<CreatedConversation> {
    return this.requestJson('/api/v1/conversations', 'POST', {})
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
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    body?: unknown
  ): Promise<T> {
    const response = await this.request(path, method, body)
    return (await response.json()) as T
  }

  private async request(
    path: string,
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
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
    const command = ['run']

    if (this.environmentFile !== undefined) {
      command.push('--env-file', this.environmentFile)
    }

    command.push('asagent', 'serve', '--bootstrap-stdin')

    if (this.providerProfile !== undefined && this.secretEnvironmentName !== undefined) {
      command.push('--profile', this.providerProfile, '--secret-env', this.secretEnvironmentName)
    }

    command.push('--app-home', this.appHome, '--port', '0')

    const child = this.spawnBackend('uv', command, {
      cwd: this.projectRoot,
      stdio: 'pipe'
    })

    if (child.stdin === null || child.stdout === null) {
      child.kill('SIGTERM')
      throw new Error('Backend standard streams are unavailable.')
    }

    this.child = child
    this.token = token
    child.stderr?.resume()
    child.stdin.end(`${JSON.stringify({ token })}\n`)

    try {
      const ready = await this.waitForReady(child)
      await this.waitForHealthy(ready, token)
      this.ready = ready
    } catch (error) {
      await this.stop()
      throw error
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

      const onExit = (): void => {
        fail(new Error('Backend stopped before it became ready.'))
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
