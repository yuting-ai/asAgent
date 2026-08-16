import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { dirname } from 'node:path'

import {
  MAX_BROWSER_TABS,
  browserDisplayUrl,
  parseBrowserTabId,
  type VisibleBrowser
} from './browser_view'

export const BROWSER_SESSION_VERSION = 1 as const
export const BROWSER_SESSION_FILE_NAME = 'browser-session.json'

export type BrowserSessionTab = {
  tabId: string
  url: string
  conversationId: string | null
}

export type BrowserSessionSnapshot = {
  version: typeof BROWSER_SESSION_VERSION
  visibleTabId: string
  tabs: BrowserSessionTab[]
}

function parseConversationId(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null
  }

  if (typeof value !== 'string') {
    return null
  }

  const conversationId = value.trim()
  if (
    conversationId === '' ||
    conversationId.length > 80 ||
    !/^[A-Za-z0-9_-]+$/.test(conversationId)
  ) {
    return null
  }

  return conversationId
}

function parseStoredUrl(value: unknown): string {
  if (typeof value !== 'string') {
    return ''
  }

  const display = browserDisplayUrl(value.trim())
  if (display === '') {
    return ''
  }

  try {
    const parsed = new URL(display)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return ''
    }
    if (!parsed.hostname) {
      return ''
    }
    return display
  } catch {
    return ''
  }
}

export function emptyBrowserSession(): BrowserSessionSnapshot {
  const tabId = crypto.randomUUID()
  return {
    version: BROWSER_SESSION_VERSION,
    visibleTabId: tabId,
    tabs: [{ tabId, url: '', conversationId: null }]
  }
}

export function normalizeBrowserSession(raw: unknown): BrowserSessionSnapshot | null {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
    return null
  }

  const record = raw as Record<string, unknown>
  if (record['version'] !== BROWSER_SESSION_VERSION) {
    return null
  }

  if (!Array.isArray(record['tabs'])) {
    return null
  }

  const tabs: BrowserSessionTab[] = []
  const seen = new Set<string>()

  for (const entry of record['tabs']) {
    if (tabs.length >= MAX_BROWSER_TABS) {
      break
    }

    if (typeof entry !== 'object' || entry === null || Array.isArray(entry)) {
      continue
    }

    const tabRecord = entry as Record<string, unknown>
    let tabId: string
    try {
      tabId = parseBrowserTabId(tabRecord['tabId'])
    } catch {
      continue
    }

    if (seen.has(tabId)) {
      continue
    }

    seen.add(tabId)
    tabs.push({
      tabId,
      url: parseStoredUrl(tabRecord['url']),
      conversationId: parseConversationId(tabRecord['conversationId'])
    })
  }

  if (tabs.length === 0) {
    return null
  }

  let visibleTabId: string
  try {
    visibleTabId = parseBrowserTabId(record['visibleTabId'])
  } catch {
    visibleTabId = tabs[0]!.tabId
  }

  if (!seen.has(visibleTabId)) {
    visibleTabId = tabs[0]!.tabId
  }

  return {
    version: BROWSER_SESSION_VERSION,
    visibleTabId,
    tabs
  }
}

export function filterBrowserSessionBindings(
  snapshot: BrowserSessionSnapshot,
  knownConversationIds: ReadonlySet<string>
): BrowserSessionSnapshot {
  return {
    ...snapshot,
    tabs: snapshot.tabs.map((tab) => ({
      ...tab,
      conversationId:
        tab.conversationId !== null && knownConversationIds.has(tab.conversationId)
          ? tab.conversationId
          : null
    }))
  }
}

export async function readBrowserSessionFile(
  filePath: string
): Promise<BrowserSessionSnapshot | null> {
  let text: string
  try {
    text = await readFile(filePath, 'utf8')
  } catch {
    return null
  }

  try {
    return normalizeBrowserSession(JSON.parse(text) as unknown)
  } catch {
    return null
  }
}

export async function writeBrowserSessionFile(
  filePath: string,
  snapshot: BrowserSessionSnapshot
): Promise<void> {
  const normalized = normalizeBrowserSession(snapshot) ?? emptyBrowserSession()
  await mkdir(dirname(filePath), { recursive: true })
  await writeFile(filePath, `${JSON.stringify(normalized, null, 2)}\n`, 'utf8')
}

export class BrowserSessionStore {
  private readonly filePath: string
  private readonly debounceMs: number
  private readonly conversationByTabId = new Map<string, string>()
  private lastVisibleTabId: string | undefined
  private saveTimer: ReturnType<typeof setTimeout> | undefined
  private writeChain: Promise<void> = Promise.resolve()

  constructor(filePath: string, options?: { debounceMs?: number }) {
    this.filePath = filePath
    this.debounceMs = options?.debounceMs ?? 400
  }

  getSnapshot(browser: VisibleBrowser): BrowserSessionSnapshot {
    const liveTabs = browser.listPersistedTabs()
    if (liveTabs.length === 0) {
      return emptyBrowserSession()
    }

    const tabs = liveTabs.map((tab) => ({
      tabId: tab.tabId,
      url: tab.url,
      conversationId: this.conversationByTabId.get(tab.tabId) ?? null
    }))

    const visibleTabId = browser.getVisibleTabId() ?? this.lastVisibleTabId ?? tabs[0]!.tabId

    if (browser.getVisibleTabId() !== undefined) {
      this.lastVisibleTabId = browser.getVisibleTabId()
    }

    const visible = tabs.some((tab) => tab.tabId === visibleTabId) ? visibleTabId : tabs[0]!.tabId

    return {
      version: BROWSER_SESSION_VERSION,
      visibleTabId: visible,
      tabs
    }
  }

  async ensureReady(browser: VisibleBrowser): Promise<BrowserSessionSnapshot> {
    if (browser.listPersistedTabs().length === 0) {
      const empty = emptyBrowserSession()
      this.conversationByTabId.clear()
      this.lastVisibleTabId = empty.visibleTabId
      await browser.restorePersistedTabs(
        empty.tabs.map((tab) => ({ tabId: tab.tabId, url: tab.url })),
        empty.visibleTabId
      )
    }

    return this.getSnapshot(browser)
  }

  async restore(browser: VisibleBrowser): Promise<BrowserSessionSnapshot> {
    const stored = (await readBrowserSessionFile(this.filePath)) ?? emptyBrowserSession()
    this.conversationByTabId.clear()
    for (const tab of stored.tabs) {
      if (tab.conversationId !== null) {
        this.conversationByTabId.set(tab.tabId, tab.conversationId)
      }
    }

    this.lastVisibleTabId = stored.visibleTabId
    await browser.restorePersistedTabs(
      stored.tabs.map((tab) => ({ tabId: tab.tabId, url: tab.url })),
      stored.visibleTabId
    )

    return this.getSnapshot(browser)
  }

  setConversation(tabId: string, conversationId: string | null): void {
    const id = parseBrowserTabId(tabId)
    const next = parseConversationId(conversationId)
    if (next === null) {
      this.conversationByTabId.delete(id)
      return
    }

    this.conversationByTabId.set(id, next)
  }

  forgetTab(tabId: string): void {
    this.conversationByTabId.delete(parseBrowserTabId(tabId))
  }

  noteVisibleTab(tabId: string): void {
    this.lastVisibleTabId = parseBrowserTabId(tabId)
  }

  scheduleSave(browser: VisibleBrowser): void {
    if (this.saveTimer !== undefined) {
      clearTimeout(this.saveTimer)
    }

    this.saveTimer = setTimeout(() => {
      this.saveTimer = undefined
      void this.flush(browser)
    }, this.debounceMs)
  }

  async flush(browser: VisibleBrowser): Promise<void> {
    if (this.saveTimer !== undefined) {
      clearTimeout(this.saveTimer)
      this.saveTimer = undefined
    }

    if (browser.listPersistedTabs().length === 0) {
      return
    }

    const snapshot = this.getSnapshot(browser)
    this.writeChain = this.writeChain
      .catch(() => undefined)
      .then(async () => {
        await writeBrowserSessionFile(this.filePath, snapshot)
      })
    await this.writeChain
  }
}
