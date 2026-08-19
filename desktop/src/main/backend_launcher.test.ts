import type { ChildProcess } from 'node:child_process'
import { EventEmitter } from 'node:events'
import { PassThrough } from 'node:stream'

import { describe, expect, it, vi } from 'vitest'

import { BackendLauncher, isToolApprovalDecision } from './backend_launcher'

type FakeChildProcess = ChildProcess & {
  stdin: PassThrough
  stdout: PassThrough
  stderr: PassThrough
  kill: ReturnType<typeof vi.fn>
}

function createChild(): FakeChildProcess {
  const child = new EventEmitter() as FakeChildProcess

  Object.assign(child, {
    pid: 12345,
    stdin: new PassThrough(),
    stdout: new PassThrough(),
    stderr: new PassThrough(),
    exitCode: null,
    killed: false
  })

  child.kill = vi.fn(() => {
    queueMicrotask(() => {
      child.emit('exit', 0, null)
    })
    return true
  })

  return child
}

function sseResponse(data: string): Response {
  const encoder = new TextEncoder()

  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(data))
        controller.close()
      }
    }),
    { status: 200 }
  )
}

describe('BackendLauncher', () => {
  it('passes the token privately, validates readiness, and checks health', async () => {
    const child = createChild()
    let bootstrap = ''
    child.stdin.on('data', (chunk) => {
      bootstrap += chunk.toString('utf8')
    })

    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn
    const fetchBackend = vi.fn(async () => new Response(null, { status: 200 }))

    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      spawnBackend,
      fetchBackend
    })

    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
    )

    await expect(starting).resolves.toBeUndefined()

    expect(launcher.isReady).toBe(true)
    expect(bootstrap).toMatch(/^\{"token":"[^"]+"\}\n$/)
    expect(fetchBackend).toHaveBeenCalledWith(
      'http://127.0.0.1:43123/api/v1/health',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /)
        })
      })
    )
  })

  it('passes only real Provider configuration names to the Python Sidecar', async () => {
    const child = createChild()
    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn

    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      providerProfile: 'deepseek',
      secretEnvironmentName: 'ASAGENT_MODEL_API_KEY',
      environmentFile: '/project/.env',
      spawnBackend,
      fetchBackend: vi.fn(async () => new Response(null, { status: 200 }))
    })

    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
    )

    await expect(starting).resolves.toBeUndefined()

    expect(spawnBackend).toHaveBeenCalledWith(
      'uv',
      [
        'run',
        '--env-file',
        '/project/.env',
        'asagent',
        'serve',
        '--bootstrap-stdin',
        '--profile',
        'deepseek',
        '--secret-env',
        'ASAGENT_MODEL_API_KEY',
        '--app-home',
        '/project/.local-data',
        '--port',
        '0'
      ],
      expect.objectContaining({
        cwd: '/project',
        stdio: 'pipe'
      })
    )
  })

  it('reads conversations through its private backend connection', async () => {
    const child = createChild()
    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn
    const fetchBackend = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              conversation_id: 'conv-1',
              created_at: '2026-08-11T00:00:00Z',
              updated_at: '2026-08-11T00:00:00Z',
              title: null
            }
          ]),
          { status: 200 }
        )
      )

    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      spawnBackend,
      fetchBackend
    })

    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
    )

    await starting

    await expect(launcher.listConversations()).resolves.toEqual([
      {
        conversation_id: 'conv-1',
        created_at: '2026-08-11T00:00:00Z',
        updated_at: '2026-08-11T00:00:00Z',
        title: null
      }
    ])

    expect(fetchBackend).toHaveBeenLastCalledWith(
      'http://127.0.0.1:43123/api/v1/conversations',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /)
        })
      })
    )
  })

  it('reads and saves one conversation file access through its private backend connection', async () => {
    const child = createChild()
    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn
    const fetchBackend = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            workspace_root: '/project/workspace',
            additional_roots: ['/project/files'],
            additional_files: ['/project/brief.pdf']
          }),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            workspace_root: '/project/workspace',
            additional_roots: ['/project/files', '/project/notes'],
            additional_files: ['/project/brief.pdf', '/project/todo.md']
          }),
          { status: 200 }
        )
      )
    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      spawnBackend,
      fetchBackend
    })

    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
    )
    await starting

    await expect(launcher.getConversationFileAccess('conv-1')).resolves.toEqual({
      workspace_root: '/project/workspace',
      additional_roots: ['/project/files'],
      additional_files: ['/project/brief.pdf']
    })
    await expect(
      launcher.saveConversationFileAccess('conv-1', {
        additionalRoots: ['/project/files', '/project/notes'],
        additionalFiles: ['/project/brief.pdf', '/project/todo.md']
      })
    ).resolves.toEqual({
      workspace_root: '/project/workspace',
      additional_roots: ['/project/files', '/project/notes'],
      additional_files: ['/project/brief.pdf', '/project/todo.md']
    })
    expect(fetchBackend).toHaveBeenLastCalledWith(
      'http://127.0.0.1:43123/api/v1/conversations/conv-1/file-access',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          additional_roots: ['/project/files', '/project/notes'],
          additional_files: ['/project/brief.pdf', '/project/todo.md']
        })
      })
    )
  })

  it('reads and decides a tool approval through its private backend connection', async () => {
    const child = createChild()
    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn
    const fetchBackend = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            approval_id: 'approval-1',
            run_id: 'run-1',
            conversation_id: 'conv-1',
            tool_call_id: 'call-1',
            tool_id: 'mcp:test-server:add:1234',
            display_name: 'Add numbers',
            description: 'Add two numbers.',
            arguments: { left: 2, right: 3 }
          }),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ approval_id: 'approval-1', decision: 'allow_once' }), {
          status: 200
        })
      )

    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      spawnBackend,
      fetchBackend
    })
    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
    )
    await starting

    await expect(launcher.getToolApproval('approval-1')).resolves.toMatchObject({
      approval_id: 'approval-1',
      arguments: { left: 2, right: 3 }
    })
    await expect(launcher.decideToolApproval('approval-1', 'allow_once')).resolves.toBeUndefined()

    expect(fetchBackend).toHaveBeenLastCalledWith(
      'http://127.0.0.1:43123/api/v1/tool-approvals/approval-1/decision',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ decision: 'allow_once' }),
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /)
        })
      })
    )
  })

  it.each(['deny', 'allow_once', 'allow_conversation'] as const)(
    'posts the %s tool approval decision to the backend',
    async (decision) => {
      const child = createChild()
      const spawnBackend = vi.fn(
        () => child
      ) as unknown as typeof import('node:child_process').spawn
      const fetchBackend = vi
        .fn()
        .mockResolvedValueOnce(new Response(null, { status: 200 }))
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ approval_id: 'approval-1', decision }), {
            status: 200
          })
        )

      const launcher = new BackendLauncher({
        projectRoot: '/project',
        appHome: '/project/.local-data',
        spawnBackend,
        fetchBackend
      })
      const starting = launcher.start()
      child.stdout.write(
        'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
      )
      await starting

      await expect(launcher.decideToolApproval('approval-1', decision)).resolves.toBeUndefined()

      expect(fetchBackend).toHaveBeenLastCalledWith(
        'http://127.0.0.1:43123/api/v1/tool-approvals/approval-1/decision',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ decision }),
          headers: expect.objectContaining({
            Authorization: expect.stringMatching(/^Bearer /)
          })
        })
      )
    }
  )

  it('accepts the renderer banner decisions and rejects a boolean flag', () => {
    expect(isToolApprovalDecision('deny')).toBe(true)
    expect(isToolApprovalDecision('allow_once')).toBe(true)
    expect(isToolApprovalDecision('allow_conversation')).toBe(true)
    expect(isToolApprovalDecision(true)).toBe(false)
    expect(isToolApprovalDecision(false)).toBe(false)
  })

  it('creates a conversation and submits a message through its private backend connection', async () => {
    const child = createChild()
    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn
    const fetchBackend = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            conversation_id: 'conv-1',
            created_at: '2026-08-11T00:00:00Z',
            updated_at: '2026-08-11T00:00:00Z',
            title: null
          }),
          { status: 201 }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            message: {
              message_id: 'msg-1',
              role: 'user',
              content: 'Hello.',
              created_at: '2026-08-11T00:00:01Z'
            },
            run: {
              run_id: 'run-1',
              status: 'created',
              created_at: '2026-08-11T00:00:01Z',
              updated_at: '2026-08-11T00:00:01Z'
            },
            conversation: {
              conversation_id: 'conv-1',
              created_at: '2026-08-11T00:00:00Z',
              updated_at: '2026-08-11T00:00:01Z',
              title: 'Hello.'
            }
          }),
          { status: 201 }
        )
      )

    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      spawnBackend,
      fetchBackend
    })

    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
    )
    await starting

    await expect(launcher.createConversation()).resolves.toMatchObject({
      conversation_id: 'conv-1'
    })
    await expect(launcher.submitMessage('conv-1', 'Hello.')).resolves.toMatchObject({
      message: {
        message_id: 'msg-1',
        content: 'Hello.'
      }
    })

    expect(fetchBackend).toHaveBeenNthCalledWith(
      2,
      'http://127.0.0.1:43123/api/v1/conversations',
      expect.objectContaining({
        method: 'POST',
        body: '{}',
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /),
          'Content-Type': 'application/json'
        })
      })
    )
    expect(fetchBackend).toHaveBeenNthCalledWith(
      3,
      'http://127.0.0.1:43123/api/v1/conversations/conv-1/messages',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ content: 'Hello.' }),
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /),
          'Content-Type': 'application/json'
        })
      })
    )
  })

  it('lists, creates, and submits isolated browser conversations', async () => {
    const child = createChild()
    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn
    const fetchBackend = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              conversation_id: 'browser-1',
              created_at: '2026-08-16T00:00:00Z',
              updated_at: '2026-08-16T00:00:00Z',
              title: 'Page question'
            }
          ]),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            conversation_id: 'browser-2',
            created_at: '2026-08-16T00:01:00Z',
            updated_at: '2026-08-16T00:01:00Z',
            title: null
          }),
          { status: 201 }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              message_id: 'msg-browser',
              role: 'user',
              content: 'Summarize this.',
              created_at: '2026-08-16T00:02:00Z'
            }
          ]),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            message: {
              message_id: 'msg-browser-2',
              role: 'user',
              content: 'Summarize this.',
              created_at: '2026-08-16T00:03:00Z'
            },
            run: {
              run_id: 'run-browser',
              status: 'created',
              created_at: '2026-08-16T00:03:00Z',
              updated_at: '2026-08-16T00:03:00Z'
            },
            conversation: {
              conversation_id: 'browser-2',
              created_at: '2026-08-16T00:01:00Z',
              updated_at: '2026-08-16T00:03:00Z',
              title: 'Summarize this.'
            }
          }),
          { status: 201 }
        )
      )

    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      spawnBackend,
      fetchBackend
    })

    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
    )
    await starting

    await expect(launcher.listBrowserConversations()).resolves.toEqual([
      {
        conversation_id: 'browser-1',
        created_at: '2026-08-16T00:00:00Z',
        updated_at: '2026-08-16T00:00:00Z',
        title: 'Page question'
      }
    ])
    await expect(launcher.createBrowserConversation()).resolves.toMatchObject({
      conversation_id: 'browser-2'
    })
    await expect(launcher.listBrowserConversationMessages('browser-2')).resolves.toEqual([
      {
        message_id: 'msg-browser',
        role: 'user',
        content: 'Summarize this.',
        created_at: '2026-08-16T00:02:00Z'
      }
    ])
    await expect(
      launcher.submitBrowserMessage(
        'browser-2',
        'Summarize this.',
        'tab-1',
        'https://example.com/article',
        'Example article'
      )
    ).resolves.toMatchObject({
      message: {
        message_id: 'msg-browser-2',
        content: 'Summarize this.'
      }
    })

    expect(fetchBackend).toHaveBeenNthCalledWith(
      2,
      'http://127.0.0.1:43123/api/v1/browser/conversations',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /)
        })
      })
    )
    expect(fetchBackend).toHaveBeenNthCalledWith(
      3,
      'http://127.0.0.1:43123/api/v1/browser/conversations',
      expect.objectContaining({
        method: 'POST',
        body: '{}',
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /),
          'Content-Type': 'application/json'
        })
      })
    )
    expect(fetchBackend).toHaveBeenNthCalledWith(
      4,
      'http://127.0.0.1:43123/api/v1/browser/conversations/browser-2/messages',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /)
        })
      })
    )
    expect(fetchBackend).toHaveBeenNthCalledWith(
      5,
      'http://127.0.0.1:43123/api/v1/browser/conversations/browser-2/messages',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          content: 'Summarize this.',
          tab_id: 'tab-1',
          last_page_url: 'https://example.com/article',
          last_page_title: 'Example article'
        }),
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /),
          'Content-Type': 'application/json'
        })
      })
    )
  })

  it('includes the private browser bridge in bootstrap without exposing it in ready output', async () => {
    const child = createChild()
    let bootstrap = ''
    child.stdin.on('data', (chunk) => {
      bootstrap += chunk.toString('utf8')
    })

    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn
    const fetchBackend = vi.fn(async () => new Response(null, { status: 200 }))
    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      spawnBackend,
      fetchBackend,
      browserBridge: {
        baseUrl: 'http://127.0.0.1:43124',
        token: 'bridge-token'
      }
    })

    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
    )
    await starting

    const payload = JSON.parse(bootstrap.trim()) as {
      token: string
      browser_bridge: { base_url: string; token: string }
    }
    expect(payload.token).toMatch(/^[A-Za-z0-9_-]+$/)
    expect(payload.browser_bridge).toEqual({
      base_url: 'http://127.0.0.1:43124',
      token: 'bridge-token'
    })
    expect(bootstrap).not.toContain('ASAGENT_READY')
  })

  it('streams authenticated run events and requests cancellation', async () => {
    const child = createChild()
    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn
    const fetchBackend = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(
        sseResponse(
          'id: 1\n' +
            'event: run.completed\n' +
            'data: {"event_id":"event-1","run_id":"run-1","conversation_id":"conv-1","sequence":1,"event_type":"run.completed","created_at":"2026-08-11T00:00:00Z","data":{}}\n\n'
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ run_id: 'run-1', cancellation_requested: true }), {
          status: 202
        })
      )

    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      spawnBackend,
      fetchBackend
    })

    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
    )
    await starting

    const events: string[] = []
    launcher.watchRunEvents(
      'run-1',
      (event) => events.push(event.event_type),
      (error) => {
        throw error
      }
    )

    await vi.waitFor(() => {
      expect(events).toEqual(['run.completed'])
    })

    await launcher.cancelRun('run-1')

    expect(fetchBackend).toHaveBeenLastCalledWith(
      'http://127.0.0.1:43123/api/v1/runs/run-1/cancel',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /)
        })
      })
    )
  })

  it('stops its own process when the ready record is invalid', async () => {
    const child = createChild()
    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn

    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      spawnBackend,
      fetchBackend: vi.fn()
    })

    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"0.0.0.0","pid":12345,"port":43123,"protocol_version":1}\n'
    )

    await expect(starting).rejects.toThrow('Backend ready record is invalid.')
    expect(child.kill).toHaveBeenCalledWith('SIGTERM')
  })

  it('reads Tavily settings through its private backend connection', async () => {
    const child = createChild()
    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn
    const fetchBackend = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ enabled: false, api_key_saved: true }), {
          status: 200
        })
      )

    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      spawnBackend,
      fetchBackend
    })

    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
    )
    await starting

    await expect(launcher.getTavilySettings()).resolves.toEqual({
      enabled: false,
      api_key_saved: true
    })

    expect(fetchBackend).toHaveBeenLastCalledWith(
      'http://127.0.0.1:43123/api/v1/settings/tavily',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /)
        })
      })
    )
  })

  it('enables Tavily with a PUT request and optional API key body', async () => {
    const child = createChild()
    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn
    const fetchBackend = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ enabled: true, api_key_saved: true }), {
          status: 200
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ enabled: true, api_key_saved: true }), {
          status: 200
        })
      )

    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      spawnBackend,
      fetchBackend
    })

    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
    )
    await starting

    await expect(launcher.enableTavily('tvly-test-key')).resolves.toEqual({
      enabled: true,
      api_key_saved: true
    })
    await expect(launcher.enableTavily()).resolves.toEqual({
      enabled: true,
      api_key_saved: true
    })

    expect(fetchBackend).toHaveBeenNthCalledWith(
      2,
      'http://127.0.0.1:43123/api/v1/settings/tavily',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ api_key: 'tvly-test-key' }),
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /),
          'Content-Type': 'application/json'
        })
      })
    )
    expect(fetchBackend).toHaveBeenNthCalledWith(
      3,
      'http://127.0.0.1:43123/api/v1/settings/tavily',
      expect.objectContaining({
        method: 'PUT',
        body: '{}',
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /),
          'Content-Type': 'application/json'
        })
      })
    )
  })

  it('disables Tavily with a POST request', async () => {
    const child = createChild()
    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn
    const fetchBackend = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ enabled: false, api_key_saved: true }), {
          status: 200
        })
      )

    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      spawnBackend,
      fetchBackend
    })

    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
    )
    await starting

    await expect(launcher.disableTavily()).resolves.toEqual({
      enabled: false,
      api_key_saved: true
    })

    expect(fetchBackend).toHaveBeenLastCalledWith(
      'http://127.0.0.1:43123/api/v1/settings/tavily/disable',
      expect.objectContaining({
        method: 'POST',
        body: '{}',
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /),
          'Content-Type': 'application/json'
        })
      })
    )
  })

  it('deletes Tavily settings with a DELETE request', async () => {
    const child = createChild()
    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn
    const fetchBackend = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ enabled: false, api_key_saved: false }), {
          status: 200
        })
      )

    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      spawnBackend,
      fetchBackend
    })

    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
    )
    await starting

    await expect(launcher.deleteTavily()).resolves.toEqual({
      enabled: false,
      api_key_saved: false
    })

    expect(fetchBackend).toHaveBeenLastCalledWith(
      'http://127.0.0.1:43123/api/v1/settings/tavily',
      expect.objectContaining({
        method: 'DELETE',
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /)
        })
      })
    )

    const lastCall = fetchBackend.mock.calls.at(-1)
    expect(lastCall?.[1]).not.toHaveProperty('body')
  })

  it('reads and saves model settings without exposing its API key', async () => {
    const child = createChild()
    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn
    const fetchBackend = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            configured: true,
            active: true,
            issue: null,
            location: 'external',
            api_key_saved: true,
            model: 'deepseek-chat',
            base_url: 'https://api.deepseek.com/v1'
          }),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            configured: true,
            active: true,
            issue: null,
            location: 'external',
            api_key_saved: true,
            model: 'deepseek-chat',
            base_url: 'https://api.deepseek.com/v1'
          }),
          { status: 200 }
        )
      )

    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      spawnBackend,
      fetchBackend
    })
    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
    )
    await starting

    await expect(launcher.getModelSettings()).resolves.toMatchObject({
      configured: true,
      api_key_saved: true,
      model: 'deepseek-chat'
    })
    await expect(
      launcher.saveModelSettings({
        location: 'external',
        model: 'deepseek-chat',
        baseUrl: 'https://api.deepseek.com/v1',
        apiKey: 'secret-model-key'
      })
    ).resolves.toMatchObject({ configured: true, api_key_saved: true })

    expect(fetchBackend).toHaveBeenLastCalledWith(
      'http://127.0.0.1:43123/api/v1/settings/model',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          location: 'external',
          model: 'deepseek-chat',
          base_url: 'https://api.deepseek.com/v1',
          api_key: 'secret-model-key'
        }),
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /)
        })
      })
    )

    fetchBackend.mockResolvedValueOnce(
      new Response(JSON.stringify({ max_steps: 20 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    )
    fetchBackend.mockResolvedValueOnce(
      new Response(JSON.stringify({ max_steps: 30 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    )

    await expect(launcher.getAgentSettings()).resolves.toEqual({ max_steps: 20 })
    await expect(launcher.saveAgentSettings({ maxSteps: 30 })).resolves.toEqual({ max_steps: 30 })
    expect(fetchBackend).toHaveBeenLastCalledWith(
      'http://127.0.0.1:43123/api/v1/agent-settings',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ max_steps: 30 }),
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /)
        })
      })
    )
  })

  it('lists conversation file changes and sends exact path for undo', async () => {
    const child = createChild()
    const spawnBackend = vi.fn(() => child) as unknown as typeof import('node:child_process').spawn
    const change = {
      change_id: 'change-1',
      run_id: 'run-1',
      operation: 'replace',
      status: 'applied',
      path: '/workspace/notes.txt',
      created_at: '2026-08-15T12:00:00Z',
      updated_at: '2026-08-15T12:00:00Z'
    }
    const fetchBackend = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([change]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...change, status: 'reverted' }), { status: 200 })
      )
    const launcher = new BackendLauncher({
      projectRoot: '/project',
      appHome: '/project/.local-data',
      spawnBackend,
      fetchBackend
    })
    const starting = launcher.start()
    child.stdout.write(
      'ASAGENT_READY {"host":"127.0.0.1","pid":12345,"port":43123,"protocol_version":1}\n'
    )
    await starting

    await expect(launcher.listConversationFileChanges('conversation/1')).resolves.toEqual([change])
    await expect(launcher.undoFileChange('change-1', change.path)).resolves.toMatchObject({
      status: 'reverted'
    })
    expect(fetchBackend).toHaveBeenNthCalledWith(
      2,
      'http://127.0.0.1:43123/api/v1/conversations/conversation%2F1/file-changes',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: expect.stringMatching(/^Bearer /) })
      })
    )
    expect(fetchBackend).toHaveBeenNthCalledWith(
      3,
      'http://127.0.0.1:43123/api/v1/file-changes/change-1/undo',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ path: '/workspace/notes.txt' }),
        headers: expect.objectContaining({ Authorization: expect.stringMatching(/^Bearer /) })
      })
    )
  })
})
