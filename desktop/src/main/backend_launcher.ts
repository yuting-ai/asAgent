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
}

export type ConversationMessage = {
  message_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

type BackendLauncherOptions = {
  projectRoot: string
  appHome: string
  spawnBackend?: typeof spawn
  fetchHealth?: typeof fetch
  startupTimeoutMs?: number
  healthTimeoutMs?: number
  healthRetryIntervalMs?: number
  stopTimeoutMs?: number
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

export class BackendLauncher {
  private readonly projectRoot: string
  private readonly appHome: string
  private readonly spawnBackend: typeof spawn
  private readonly fetchHealth: typeof fetch
  private readonly startupTimeoutMs: number
  private readonly healthTimeoutMs: number
  private readonly healthRetryIntervalMs: number
  private readonly stopTimeoutMs: number
  private child: ChildProcess | undefined
  private ready: ServerReady | undefined
  private token: string | undefined

  constructor(options: BackendLauncherOptions) {
    this.projectRoot = options.projectRoot
    this.appHome = options.appHome
    this.spawnBackend = options.spawnBackend ?? spawn
    this.fetchHealth = options.fetchHealth ?? fetch
    this.startupTimeoutMs = options.startupTimeoutMs ?? 5_000
    this.healthTimeoutMs = options.healthTimeoutMs ?? 5_000
    this.healthRetryIntervalMs = options.healthRetryIntervalMs ?? 100
    this.stopTimeoutMs = options.stopTimeoutMs ?? 3_000
  }

  get isReady(): boolean {
    return this.ready !== undefined
  }

  async listConversations(): Promise<ConversationSummary[]> {
    return this.getJson('/api/v1/conversations')
  }

  async listConversationMessages(conversationId: string): Promise<ConversationMessage[]> {
    return this.getJson(`/api/v1/conversations/${encodeURIComponent(conversationId)}/messages`)
  }

  private async getJson<T>(path: string): Promise<T> {
    if (this.ready === undefined || this.token === undefined) {
      throw new Error('Backend is not ready.')
    }

    const response = await this.fetchHealth(`http://${this.ready.host}:${this.ready.port}${path}`, {
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${this.token}`
      },
      signal: AbortSignal.timeout(5_000)
    })

    if (!response.ok) {
      throw new Error(`Backend API request failed with status ${response.status}.`)
    }

    return (await response.json()) as T
  }

  async start(): Promise<void> {
    if (this.child !== undefined) {
      throw new Error('Backend has already been started.')
    }

    const token = randomBytes(32).toString('base64url')
    const child = this.spawnBackend(
      'uv',
      ['run', 'asagent', 'serve', '--bootstrap-stdin', '--app-home', this.appHome, '--port', '0'],
      {
        cwd: this.projectRoot,
        stdio: 'pipe'
      }
    )

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
        const response = await this.fetchHealth(healthUrl, {
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
