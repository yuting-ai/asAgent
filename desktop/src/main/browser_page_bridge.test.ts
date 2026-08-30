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
  headers: Record<string, string | number | readonly string[]>
  body?: string
  rawBody?: string | Buffer
} {
  const response = Object.assign(new EventEmitter(), {
    headers: {},
    writeHead: vi.fn(
      (statusCode: number, headers?: Record<string, string | number | readonly string[]>) => {
        response.statusCode = statusCode
        if (headers) {
          response.headers = headers
        }
      }
    ),
    end: vi.fn((payload?: string | Buffer) => {
      response.rawBody = payload
      response.body =
        typeof payload === 'string'
          ? payload
          : payload instanceof Buffer
            ? payload.toString('utf8')
            : undefined
    })
  }) as ServerResponse & {
    writeHead: ReturnType<typeof vi.fn>
    end: ReturnType<typeof vi.fn>
    statusCode?: number
    headers: Record<string, string | number | readonly string[]>
    body?: string
    rawBody?: string | Buffer
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
    const readCurrentPdf = vi.fn(async (tabId: string) => ({
      documentId: `doc-${tabId}`,
      data: Buffer.from('%PDF-1.4 sample content %%EOF')
    }))
    const validateCurrentPdf = vi.fn<(tabId: string, documentId: string) => void>()
    const inspectInteractive = vi.fn(async () => ({
      url: 'https://example.com/',
      elements: [
        {
          target_id: 'target_1',
          name: 'Continue',
          role: 'button',
          tag: 'button',
          disabled: false
        }
      ]
    }))
    const clickCurrentPage = vi.fn(async () => ({
      action: 'clicked' as const,
      url: 'https://example.com/next',
      title: 'Next',
      page: {
        title: 'Next',
        url: 'https://example.com/next',
        text: 'Results are ready'
      }
    }))
    const fillCurrentPage = vi.fn(async () => ({
      action: 'filled' as const,
      url: 'https://example.com/',
      title: 'Example',
      page: {
        title: 'Example',
        url: 'https://example.com/?draft=123',
        text: 'Draft saved'
      }
    }))
    const selectCurrentPage = vi.fn(async () => ({
      action: 'selected' as const,
      url: 'https://example.com/form',
      title: 'Country'
    }))
    const submitCurrentPage = vi.fn(async () => ({
      action: 'submitted' as const,
      url: 'https://example.com/thanks',
      title: 'Thanks',
      page: {
        title: 'Thanks',
        url: 'https://example.com/thanks',
        text: 'Message sent'
      }
    }))
    const navigateCurrentPage = vi.fn(async () => ({
      action: 'navigated' as const,
      url: 'https://example.com/search?q=asAgent',
      title: 'Search results',
      page: {
        title: 'Search results',
        url: 'https://example.com/search?q=asAgent',
        text: 'Found 10 results'
      }
    }))
    const waitForCurrentPage = vi.fn(async () => ({
      changed: true,
      page: {
        title: 'Results',
        url: 'https://example.com/next',
        text: 'Results are ready'
      }
    }))

    const bridge = new BrowserPageBridge({
      readCurrentPage,
      readCurrentPdf,
      validateCurrentPdf,
      inspectInteractive,
      navigateCurrentPage,
      clickCurrentPage,
      fillCurrentPage,
      selectCurrentPage,
      submitCurrentPage,
      waitForCurrentPage,
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

    const clickUnauthorized = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/click-current-page',
        {},
        JSON.stringify({ tab_id: 'tab-1', target_id: 'target_1' })
      ),
      clickUnauthorized
    )
    await vi.waitFor(() => expect(clickUnauthorized.end).toHaveBeenCalled())
    expect(clickUnauthorized.statusCode).toBe(401)
    expect(clickCurrentPage).not.toHaveBeenCalled()

    const clickTooLong = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/click-current-page',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1', target_id: 'x'.repeat(81) })
      ),
      clickTooLong
    )
    await vi.waitFor(() => expect(clickTooLong.end).toHaveBeenCalled())
    expect(clickTooLong.statusCode).toBe(400)
    expect(clickCurrentPage).not.toHaveBeenCalled()

    const inspectAuthorized = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/inspect-interactive',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1' })
      ),
      inspectAuthorized
    )
    await vi.waitFor(() => expect(inspectAuthorized.end).toHaveBeenCalled())
    expect(inspectAuthorized.statusCode).toBe(200)
    expect(inspectInteractive).toHaveBeenCalledWith('tab-1')
    expect(JSON.parse(inspectAuthorized.body ?? '')).toEqual({
      url: 'https://example.com/',
      elements: [
        {
          target_id: 'target_1',
          name: 'Continue',
          role: 'button',
          tag: 'button',
          disabled: false
        }
      ]
    })

    const waitAuthorized = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/wait-for-current-page',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1', seconds: 15 })
      ),
      waitAuthorized
    )
    await vi.waitFor(() => expect(waitAuthorized.end).toHaveBeenCalled())
    expect(waitAuthorized.statusCode).toBe(200)
    expect(waitForCurrentPage).toHaveBeenCalledWith('tab-1', 15)
    expect(JSON.parse(waitAuthorized.body ?? '')).toEqual({
      changed: true,
      page: {
        title: 'Results',
        url: 'https://example.com/next',
        text: 'Results are ready'
      }
    })

    const clickAuthorized = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/click-current-page',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1', target_id: 'target_2' })
      ),
      clickAuthorized
    )
    await vi.waitFor(() => expect(clickAuthorized.end).toHaveBeenCalled())
    expect(clickAuthorized.statusCode).toBe(200)
    expect(clickCurrentPage).toHaveBeenCalledWith('tab-1', 'target_2')
    expect(JSON.parse(clickAuthorized.body ?? '')).toEqual({
      action: 'clicked',
      url: 'https://example.com/next',
      title: 'Next',
      page: {
        title: 'Next',
        url: 'https://example.com/next',
        text: 'Results are ready'
      }
    })

    const fillAuthorized = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/fill-current-page',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1', target_id: 'target_2', value: 'hello' })
      ),
      fillAuthorized
    )
    await vi.waitFor(() => expect(fillAuthorized.end).toHaveBeenCalled())
    expect(fillAuthorized.statusCode).toBe(200)
    expect(fillCurrentPage).toHaveBeenCalledWith('tab-1', 'target_2', 'hello')
    expect(JSON.parse(fillAuthorized.body ?? '')).toEqual({
      action: 'filled',
      url: 'https://example.com/',
      title: 'Example',
      page: {
        title: 'Example',
        url: 'https://example.com/?draft=123',
        text: 'Draft saved'
      }
    })

    const selectUnauthorized = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/select-current-page',
        {},
        JSON.stringify({ tab_id: 'tab-1', target_id: 'target_4', value: 'au' })
      ),
      selectUnauthorized
    )
    await vi.waitFor(() => expect(selectUnauthorized.end).toHaveBeenCalled())
    expect(selectUnauthorized.statusCode).toBe(401)
    expect(selectCurrentPage).not.toHaveBeenCalled()

    const selectMissingValue = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/select-current-page',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1', target_id: 'target_4' })
      ),
      selectMissingValue
    )
    await vi.waitFor(() => expect(selectMissingValue.end).toHaveBeenCalled())
    expect(selectMissingValue.statusCode).toBe(400)
    expect(selectCurrentPage).not.toHaveBeenCalled()

    const selectAuthorized = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/select-current-page',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1', target_id: 'target_4', value: 'au' })
      ),
      selectAuthorized
    )
    await vi.waitFor(() => expect(selectAuthorized.end).toHaveBeenCalled())
    expect(selectAuthorized.statusCode).toBe(200)
    expect(selectCurrentPage).toHaveBeenCalledWith('tab-1', 'target_4', 'au')
    expect(JSON.parse(selectAuthorized.body ?? '')).toEqual({
      action: 'selected',
      url: 'https://example.com/form',
      title: 'Country'
    })

    const submitUnauthorized = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/submit-current-page',
        {},
        JSON.stringify({ tab_id: 'tab-1', target_id: 'target_3' })
      ),
      submitUnauthorized
    )
    await vi.waitFor(() => expect(submitUnauthorized.end).toHaveBeenCalled())
    expect(submitUnauthorized.statusCode).toBe(401)
    expect(submitCurrentPage).not.toHaveBeenCalled()

    const submitMissingTarget = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/submit-current-page',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1' })
      ),
      submitMissingTarget
    )
    await vi.waitFor(() => expect(submitMissingTarget.end).toHaveBeenCalled())
    expect(submitMissingTarget.statusCode).toBe(400)
    expect(submitCurrentPage).not.toHaveBeenCalled()

    const submitAuthorized = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/submit-current-page',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1', target_id: 'target_3' })
      ),
      submitAuthorized
    )
    await vi.waitFor(() => expect(submitAuthorized.end).toHaveBeenCalled())
    expect(submitAuthorized.statusCode).toBe(200)
    expect(submitCurrentPage).toHaveBeenCalledWith('tab-1', 'target_3')
    expect(JSON.parse(submitAuthorized.body ?? '')).toEqual({
      action: 'submitted',
      url: 'https://example.com/thanks',
      title: 'Thanks',
      page: {
        title: 'Thanks',
        url: 'https://example.com/thanks',
        text: 'Message sent'
      }
    })

    const navigateUnauthorized = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/navigate-current-page',
        {},
        JSON.stringify({ tab_id: 'tab-1', url: 'https://example.com' })
      ),
      navigateUnauthorized
    )
    await vi.waitFor(() => expect(navigateUnauthorized.end).toHaveBeenCalled())
    expect(navigateUnauthorized.statusCode).toBe(401)
    expect(navigateCurrentPage).not.toHaveBeenCalled()

    const navigateMissingUrl = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/navigate-current-page',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1' })
      ),
      navigateMissingUrl
    )
    await vi.waitFor(() => expect(navigateMissingUrl.end).toHaveBeenCalled())
    expect(navigateMissingUrl.statusCode).toBe(400)
    expect(navigateCurrentPage).not.toHaveBeenCalled()

    const navigateAuthorized = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/navigate-current-page',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1', url: 'https://example.com/search?q=asAgent' })
      ),
      navigateAuthorized
    )
    await vi.waitFor(() => expect(navigateAuthorized.end).toHaveBeenCalled())
    expect(navigateAuthorized.statusCode).toBe(200)
    expect(navigateCurrentPage).toHaveBeenCalledWith(
      'tab-1',
      'https://example.com/search?q=asAgent'
    )
    expect(JSON.parse(navigateAuthorized.body ?? '')).toEqual({
      action: 'navigated',
      url: 'https://example.com/search?q=asAgent',
      title: 'Search results',
      page: {
        title: 'Search results',
        url: 'https://example.com/search?q=asAgent',
        text: 'Found 10 results'
      }
    })

    const pdfUnauthorized = createFakeResponse()
    requestHandler?.(
      createFakeRequest('POST', '/read-current-pdf', {}, JSON.stringify({ tab_id: 'tab-1' })),
      pdfUnauthorized
    )
    await vi.waitFor(() => expect(pdfUnauthorized.end).toHaveBeenCalled())
    expect(pdfUnauthorized.statusCode).toBe(401)
    expect(readCurrentPdf).not.toHaveBeenCalled()

    const pdfMissingTab = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/read-current-pdf',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({})
      ),
      pdfMissingTab
    )
    await vi.waitFor(() => expect(pdfMissingTab.end).toHaveBeenCalled())
    expect(pdfMissingTab.statusCode).toBe(400)
    expect(readCurrentPdf).not.toHaveBeenCalled()

    const pdfAuthorized = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/read-current-pdf',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1' })
      ),
      pdfAuthorized
    )
    await vi.waitFor(() => expect(pdfAuthorized.end).toHaveBeenCalled())
    expect(pdfAuthorized.statusCode).toBe(200)
    expect(pdfAuthorized.headers['Content-Type']).toBe('application/pdf')
    expect(pdfAuthorized.headers['X-Document-Id']).toBe('doc-tab-1')
    expect(pdfAuthorized.headers['Content-Length']).toBe(
      Buffer.from('%PDF-1.4 sample content %%EOF').byteLength
    )
    expect(pdfAuthorized.body).toBe('%PDF-1.4 sample content %%EOF')
    expect(readCurrentPdf).toHaveBeenCalledWith('tab-1', expect.any(AbortSignal))
    expect(pdfAuthorized.listenerCount('close')).toBe(0)

    const documentId = `doc-${'a'.repeat(32)}`
    for (const [headers, body, status] of [
      [{}, { tab_id: 'tab-1', document_id: documentId }, 401],
      [{ authorization: 'Bearer bridge-token' }, { tab_id: 'tab-1' }, 400],
      [{ authorization: 'Bearer bridge-token' }, { tab_id: 'tab-1', document_id: documentId }, 200]
    ] as const) {
      const validation = createFakeResponse()
      requestHandler?.(
        createFakeRequest('POST', '/validate-current-pdf', headers, JSON.stringify(body)),
        validation
      )
      await vi.waitFor(() => expect(validation.end).toHaveBeenCalled())
      expect(validation.statusCode).toBe(status)
    }
    expect(validateCurrentPdf).toHaveBeenLastCalledWith('tab-1', documentId)
    expect(readCurrentPdf).toHaveBeenCalledTimes(1)

    validateCurrentPdf.mockImplementationOnce(() => {
      throw new Error('PDF document changed; start a new browser run')
    })
    const invalidated = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/validate-current-pdf',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1', document_id: documentId })
      ),
      invalidated
    )
    await vi.waitFor(() => expect(invalidated.end).toHaveBeenCalled())
    expect(invalidated.statusCode).toBe(409)

    readCurrentPdf.mockRejectedValueOnce(new Error('PDF exceeds the 20 MiB limit'))
    const pdfError = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/read-current-pdf',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1' })
      ),
      pdfError
    )
    await vi.waitFor(() => expect(pdfError.end).toHaveBeenCalled())
    expect(pdfError.statusCode).toBe(409)
    expect(JSON.parse(pdfError.body ?? '')).toEqual({
      detail: 'PDF exceeds the 20 MiB limit'
    })
    expect(pdfError.listenerCount('close')).toBe(0)

    const pendingFetch: { signal?: AbortSignal } = {}
    readCurrentPdf.mockImplementationOnce(async (_tabId: string, signal?: AbortSignal) => {
      pendingFetch.signal = signal
      return new Promise((_, reject) => {
        signal?.addEventListener('abort', () => reject(new Error('PDF fetch was cancelled')), {
          once: true
        })
      })
    })
    const disconnected = createFakeResponse()
    const disconnectedRequest = createFakeRequest(
      'POST',
      '/read-current-pdf',
      { authorization: 'Bearer bridge-token' },
      JSON.stringify({ tab_id: 'tab-1' })
    )
    requestHandler?.(disconnectedRequest, disconnected)
    await vi.waitFor(() => expect(pendingFetch.signal).toBeDefined())
    Object.assign(disconnected, { destroyed: true })
    disconnected.emit('close')
    await vi.waitFor(() => expect(pendingFetch.signal?.aborted).toBe(true))
    await vi.waitFor(() => expect(disconnected.listenerCount('close')).toBe(0))
    expect(disconnectedRequest.listenerCount('aborted')).toBe(0)
    expect(disconnected.writeHead).not.toHaveBeenCalled()
    expect(disconnected.end).not.toHaveBeenCalled()

    pendingFetch.signal = undefined
    readCurrentPdf.mockImplementationOnce(async (_tabId: string, signal?: AbortSignal) => {
      pendingFetch.signal = signal
      return new Promise((_, reject) => {
        signal?.addEventListener('abort', () => reject(new Error('PDF fetch was cancelled')), {
          once: true
        })
      })
    })
    const stopping = createFakeResponse()
    requestHandler?.(
      createFakeRequest(
        'POST',
        '/read-current-pdf',
        { authorization: 'Bearer bridge-token' },
        JSON.stringify({ tab_id: 'tab-1' })
      ),
      stopping
    )
    await vi.waitFor(() => expect(pendingFetch.signal).toBeDefined())
    await bridge.stop()
    await vi.waitFor(() => expect(stopping.end).toHaveBeenCalled())
    await vi.waitFor(() => expect(pendingFetch.signal?.aborted).toBe(true))
    expect(stopping.listenerCount('close')).toBe(0)
  })
})
