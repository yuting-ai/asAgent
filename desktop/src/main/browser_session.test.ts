import { mkdtemp, readFile, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  BrowserSessionStore,
  emptyBrowserSession,
  filterBrowserSessionBindings,
  normalizeBrowserSession,
  readBrowserSessionFile,
  writeBrowserSessionFile
} from './browser_session'
import type { VisibleBrowser } from './browser_view'

describe('normalizeBrowserSession', () => {
  it('accepts a valid snapshot and scrubs credentials from URLs', () => {
    const snapshot = normalizeBrowserSession({
      version: 1,
      visibleTabId: 'tab-visible',
      tabs: [
        {
          tabId: 'tab-visible',
          url: 'https://user:secret@example.com/path',
          conversationId: 'conv_abc'
        },
        {
          tabId: 'tab-2',
          url: 'about:blank',
          conversationId: null
        }
      ]
    })

    expect(snapshot).toEqual({
      version: 1,
      visibleTabId: 'tab-visible',
      tabs: [
        {
          tabId: 'tab-visible',
          url: 'https://example.com/path',
          conversationId: 'conv_abc'
        },
        {
          tabId: 'tab-2',
          url: '',
          conversationId: null
        }
      ]
    })
  })

  it('rejects corrupt payloads and recovers visible tab when missing', () => {
    expect(normalizeBrowserSession(null)).toBeNull()
    expect(normalizeBrowserSession({ version: 2, tabs: [] })).toBeNull()
    expect(
      normalizeBrowserSession({
        version: 1,
        visibleTabId: 'missing',
        tabs: [{ tabId: 'tab-1', url: 'https://example.com/', conversationId: null }]
      })
    ).toEqual({
      version: 1,
      visibleTabId: 'tab-1',
      tabs: [{ tabId: 'tab-1', url: 'https://example.com/', conversationId: null }]
    })
  })

  it('drops invalid conversation ids and duplicate tabs', () => {
    const snapshot = normalizeBrowserSession({
      version: 1,
      visibleTabId: 'tab-1',
      tabs: [
        { tabId: 'tab-1', url: 'https://example.com/', conversationId: 'bad id' },
        { tabId: 'tab-1', url: 'https://other.example/', conversationId: 'conv_ok' },
        { tabId: 'tab-2', url: 'file:///tmp/x', conversationId: 'conv_ok' }
      ]
    })

    expect(snapshot).toEqual({
      version: 1,
      visibleTabId: 'tab-1',
      tabs: [
        { tabId: 'tab-1', url: 'https://example.com/', conversationId: null },
        { tabId: 'tab-2', url: '', conversationId: 'conv_ok' }
      ]
    })
  })
})

describe('filterBrowserSessionBindings', () => {
  it('clears bindings for deleted conversations', () => {
    const filtered = filterBrowserSessionBindings(
      {
        version: 1,
        visibleTabId: 'tab-1',
        tabs: [
          { tabId: 'tab-1', url: 'https://example.com/', conversationId: 'conv_keep' },
          { tabId: 'tab-2', url: '', conversationId: 'conv_gone' }
        ]
      },
      new Set(['conv_keep'])
    )

    expect(filtered.tabs.map((tab) => tab.conversationId)).toEqual(['conv_keep', null])
  })
})

describe('browser session file IO', () => {
  it('round-trips a snapshot through disk', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'asagent-browser-session-'))
    const filePath = join(directory, 'browser-session.json')
    const snapshot = {
      version: 1 as const,
      visibleTabId: 'tab-1',
      tabs: [{ tabId: 'tab-1', url: 'https://example.com/', conversationId: 'conv_1' }]
    }

    await writeBrowserSessionFile(filePath, snapshot)
    await expect(readBrowserSessionFile(filePath)).resolves.toEqual(snapshot)
    const written = await readFile(filePath, 'utf8')
    expect(written).not.toContain('user:')
    expect(written).not.toContain('password')
  })

  it('returns null for missing or corrupt files', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'asagent-browser-session-'))
    await expect(readBrowserSessionFile(join(directory, 'missing.json'))).resolves.toBeNull()

    const corruptPath = join(directory, 'corrupt.json')
    await writeFile(corruptPath, '{not-json', 'utf8')
    await expect(readBrowserSessionFile(corruptPath)).resolves.toBeNull()
  })
})

describe('BrowserSessionStore', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('restores tabs, remembers bindings, and debounces writes', async () => {
    vi.useFakeTimers()
    const directory = await mkdtemp(join(tmpdir(), 'asagent-browser-session-'))
    const filePath = join(directory, 'browser-session.json')
    await writeBrowserSessionFile(filePath, {
      version: 1,
      visibleTabId: 'tab-a',
      tabs: [
        { tabId: 'tab-a', url: 'https://a.example/', conversationId: 'conv_a' },
        { tabId: 'tab-b', url: 'https://b.example/', conversationId: null }
      ]
    })

    const restored: Array<{ tabId: string; url: string }> = []
    let visibleTabId: string | undefined = 'tab-a'
    const browser = {
      restorePersistedTabs: vi.fn(async (tabs, visible) => {
        restored.push(...tabs)
        visibleTabId = visible
      }),
      listPersistedTabs: vi.fn(() => [
        { tabId: 'tab-a', url: 'https://a.example/' },
        { tabId: 'tab-b', url: 'https://b.example/' }
      ]),
      getVisibleTabId: vi.fn(() => visibleTabId)
    } as unknown as VisibleBrowser

    const store = new BrowserSessionStore(filePath, { debounceMs: 50 })
    const snapshot = await store.restore(browser)

    expect(snapshot.visibleTabId).toBe('tab-a')
    expect(snapshot.tabs[0]?.conversationId).toBe('conv_a')
    expect(restored).toEqual([
      { tabId: 'tab-a', url: 'https://a.example/' },
      { tabId: 'tab-b', url: 'https://b.example/' }
    ])

    store.setConversation('tab-b', 'conv_b')
    store.scheduleSave(browser)
    await vi.advanceTimersByTimeAsync(49)
    await expect(readBrowserSessionFile(filePath)).resolves.toMatchObject({
      tabs: [{ conversationId: 'conv_a' }, { conversationId: null }]
    })
    await vi.advanceTimersByTimeAsync(1)
    await store.flush(browser)

    await expect(readBrowserSessionFile(filePath)).resolves.toMatchObject({
      visibleTabId: 'tab-a',
      tabs: [
        { tabId: 'tab-a', conversationId: 'conv_a' },
        { tabId: 'tab-b', conversationId: 'conv_b' }
      ]
    })
  })

  it('creates an empty session when nothing is stored', () => {
    const empty = emptyBrowserSession()
    expect(empty.tabs).toHaveLength(1)
    expect(empty.visibleTabId).toBe(empty.tabs[0]?.tabId)
    expect(empty.tabs[0]?.url).toBe('')
  })
})
