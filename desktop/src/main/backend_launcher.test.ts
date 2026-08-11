import type { ChildProcess } from 'node:child_process'
import { EventEmitter } from 'node:events'
import { PassThrough } from 'node:stream'

import { describe, expect, it, vi } from 'vitest'

import { BackendLauncher } from './backend_launcher'

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
})
