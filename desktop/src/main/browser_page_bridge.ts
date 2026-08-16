import { createServer, type IncomingMessage, type Server, type ServerResponse } from 'node:http'
import { randomBytes, timingSafeEqual } from 'node:crypto'

export type BrowserPageContent = {
  title: string
  url: string
  text: string
}

export type BrowserPageBridgeOptions = {
  readCurrentPage: (tabId: string) => Promise<BrowserPageContent>
  createServer?: typeof createServer
  randomToken?: () => string
}

export type BrowserPageBridgeInfo = {
  baseUrl: string
  token: string
}

function readRequestBody(request: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = []
    request.on('data', (chunk: Buffer) => {
      chunks.push(chunk)
      if (chunks.reduce((total, part) => total + part.length, 0) > 4_096) {
        reject(new Error('Browser page bridge request is too large.'))
        request.destroy()
      }
    })
    request.on('end', () => {
      resolve(Buffer.concat(chunks).toString('utf8'))
    })
    request.on('error', reject)
  })
}

function writeJson(response: ServerResponse, statusCode: number, body: unknown): void {
  const payload = JSON.stringify(body)
  response.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(payload)
  })
  response.end(payload)
}

function bearerMatches(header: string | undefined, expected: string): boolean {
  if (header === undefined || !header.startsWith('Bearer ')) {
    return false
  }

  const candidate = header.slice('Bearer '.length)
  const left = Buffer.from(candidate)
  const right = Buffer.from(expected)
  if (left.length !== right.length) {
    return false
  }

  return timingSafeEqual(left, right)
}

export class BrowserPageBridge {
  private readonly readCurrentPage: (tabId: string) => Promise<BrowserPageContent>
  private readonly createHttpServer: typeof createServer
  private readonly randomToken: () => string
  private server: Server | undefined
  private info: BrowserPageBridgeInfo | undefined

  constructor(options: BrowserPageBridgeOptions) {
    this.readCurrentPage = options.readCurrentPage
    this.createHttpServer = options.createServer ?? createServer
    this.randomToken = options.randomToken ?? (() => randomBytes(32).toString('base64url'))
  }

  get isRunning(): boolean {
    return this.server !== undefined
  }

  get connection(): BrowserPageBridgeInfo | undefined {
    return this.info
  }

  async start(): Promise<BrowserPageBridgeInfo> {
    if (this.server !== undefined && this.info !== undefined) {
      return this.info
    }

    const token = this.randomToken()
    const server = this.createHttpServer((request, response) => {
      void this.handleRequest(request, response, token)
    })

    await new Promise<void>((resolve, reject) => {
      server.once('error', reject)
      server.listen(0, '127.0.0.1', () => {
        server.off('error', reject)
        resolve()
      })
    })

    const address = server.address()
    if (address === null || typeof address === 'string') {
      server.close()
      throw new Error('Browser page bridge address is unavailable.')
    }

    this.server = server
    this.info = {
      baseUrl: `http://127.0.0.1:${address.port}`,
      token
    }
    return this.info
  }

  async stop(): Promise<void> {
    const server = this.server
    this.server = undefined
    this.info = undefined
    if (server === undefined) {
      return
    }

    await new Promise<void>((resolve) => {
      server.close(() => resolve())
    })
  }

  private async handleRequest(
    request: IncomingMessage,
    response: ServerResponse,
    token: string
  ): Promise<void> {
    try {
      if (request.method !== 'POST' || request.url !== '/read-current-page') {
        writeJson(response, 404, { detail: 'not found' })
        return
      }

      if (!bearerMatches(request.headers.authorization, token)) {
        writeJson(response, 401, { detail: 'invalid browser page bridge credentials' })
        return
      }

      const rawBody = await readRequestBody(request)
      let payload: unknown
      try {
        payload = JSON.parse(rawBody)
      } catch {
        writeJson(response, 400, { detail: 'invalid request' })
        return
      }

      if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
        writeJson(response, 400, { detail: 'invalid request' })
        return
      }

      const tabId = (payload as Record<string, unknown>)['tab_id']
      if (typeof tabId !== 'string' || tabId.trim() === '') {
        writeJson(response, 400, { detail: 'invalid request' })
        return
      }

      const page = await this.readCurrentPage(tabId.trim())
      writeJson(response, 200, page)
    } catch (error) {
      writeJson(response, 409, {
        detail: error instanceof Error ? error.message : 'current browser page could not be read'
      })
    }
  }
}
