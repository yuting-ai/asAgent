import { EventEmitter } from 'node:events'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { describe, expect, it, vi } from 'vitest'

import { BrowserPageBridge } from './browser_page_bridge'

function createFakeRequest(
  method: string,
  url: string,
  headers: Record<string, string>,
  body: string
): IncomingMessage {
  const request = new EventEmitter() as IncomingMessage & EventEmitter
  Object.assign(request, {
    method,
    url,
    headers,
    destroy: vi.fn()
  })
  queueMicrotask(() => {
    if (body !== '') {
      request.emit('data', Buffer.from(body))
    }
    request.emit('end')
  })
  return request
}

function createFakeResponse(): ServerResponse & {
  writeHead: ReturnType<typeof vi.fn>
  end: ReturnType<typeof vi.fn>
  statusCode?: number
  body?: string
} {
  const response = {
    writeHead: vi.fn((statusCode: number) => {
      response.statusCode = statusCode
    }),
    end: vi.fn((payload?: string) => {
      response.body = payload
    })
  } as ServerResponse & {
    writeHead: ReturnType<typeof vi.fn>
    end: ReturnType<typeof vi.fn>
    statusCode?: number
    body?: string
  }
  return response
}

describe('BrowserPageBridge', () => {
  it('listens on loopback and requires a bearer token', async () => {
    let requestHandler: ((request: IncomingMessage, response: ServerResponse) => void) | undefined

    const server = Object.assign(new EventEmitter(), {
      listen: vi.fn(
        (
          _port?: number,
          hostname?: string,
          backlogOrCallback?: number | (() => void),
          maybeCallback?: () => void
        ) => {
          const callback =
            typeof backlogOrCallback === 'function' ? backlogOrCallback : maybeCallback
          expect(hostname).toBe('127.0.0.1')
          queueMicrotask(() => callback?.())
          return server
        }
      ),
      close: vi.fn((callback?: (error?: Error) => void) => {
        callback?.()
        return server
      }),
      address: vi.fn(() => ({ port: 43124, family: 'IPv4', address: '127.0.0.1' }))
    })

    const createServer = vi.fn((handler) => {
      requestHandler = handler
      return server
    }) as unknown as typeof import('node:http').createServer

    const readCurrentPage = vi.fn(async () => ({
      title: 'Example Domain',
      url: 'https://example.com/',
      text: 'Hello'
    }))

    const bridge = new BrowserPageBridge({
      readCurrentPage,
      createServer,
      randomToken: () => 'bridge-token'
    })

    await expect(bridge.start()).resolves.toEqual({
      baseUrl: 'http://127.0.0.1:43124',
      token: 'bridge-token'
    })

    const unauthorized = createFakeResponse()
    requestHandler?.(
      createFakeRequest('POST', '/read-current-page', {}, JSON.stringify({ tab_id: 'tab-1' })),
      unauthorized
    )
    await vi.waitFor(() => expect(unauthorized.end).toHaveBeenCalled())
    expect(unauthorized.statusCode).toBe(401)
    expect(readCurrentPage).not.toHaveBeenCalled()

    const authorized = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/read-current-page',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1' })
      ),
      authorized
    )
    await vi.waitFor(() => expect(authorized.end).toHaveBeenCalled())
    expect(authorized.statusCode).toBe(200)
    expect(JSON.parse(authorized.body ?? '')).toEqual({
      title: 'Example Domain',
      url: 'https://example.com/',
      text: 'Hello'
    })

    await bridge.stop()
  })
})
