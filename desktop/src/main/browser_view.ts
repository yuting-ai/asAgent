import type { Session, WebContentsViewConstructorOptions } from 'electron'

import { parseBrowserWebUrl } from './external_url'

export const MAX_BROWSER_TABS = 16
export const BROWSER_HOME_URL = 'about:blank'
export const BROWSER_CONTROL_ACTIONS = ['back', 'forward', 'reload', 'home'] as const

export type BrowserControlAction = (typeof BROWSER_CONTROL_ACTIONS)[number]

export type BrowserTabState = {
  tabId: string
  url: string
  title: string
  canGoBack: boolean
  canGoForward: boolean
}

export type BrowserPageContent = {
  title: string
  url: string
  text: string
}

export const BROWSER_PAGE_TITLE_LIMIT = 512
export const BROWSER_PAGE_TEXT_LIMIT = 32 * 1024

const BROWSER_PAGE_EXTRACT_SCRIPT = `(() => {
  const title = String(document.title || '')
  const text = String(document.body && document.body.innerText ? document.body.innerText : '')
  return { title, text }
})()`

export type BrowserViewBounds = {
  x: number
  y: number
  width: number
  height: number
}

export type BrowserNavigationEvent = {
  preventDefault(): void
  url?: string
}

export type BrowserPageView = {
  setBounds(bounds: BrowserViewBounds): void
  setVisible(visible: boolean): void
  webContents: {
    loadURL(url: string): Promise<void>
    close(): void
    getURL(): string
    getTitle(): string
    canGoBack(): boolean
    canGoForward(): boolean
    goBack(): void
    goForward(): void
    reload(): void
    executeJavaScript(code: string): Promise<unknown>
    setWindowOpenHandler(handler: (details?: { url?: string }) => { action: 'deny' }): void
    on(
      event:
        | 'will-navigate'
        | 'will-redirect'
        | 'will-frame-navigate'
        | 'did-navigate'
        | 'did-navigate-in-page'
        | 'page-title-updated',
      listener: (event: BrowserNavigationEvent, urlOrTitle?: string) => void
    ): void
  }
}

export type BrowserHostWindow = {
  isDestroyed(): boolean
  contentView: {
    children: readonly unknown[]
    addChildView(view: BrowserPageView): void
    removeChildView(view: BrowserPageView): void
  }
}

export type VisibleBrowserOptions = {
  session: Session
  createView: (options: WebContentsViewConstructorOptions) => BrowserPageView
  onTabState?: (state: BrowserTabState) => void
}

export function parseBrowserViewBounds(value: unknown): BrowserViewBounds {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error('Browser view bounds are invalid.')
  }

  const input = value as Record<string, unknown>
  const x = input['x']
  const y = input['y']
  const width = input['width']
  const height = input['height']
  if (
    typeof x !== 'number' ||
    !Number.isFinite(x) ||
    typeof y !== 'number' ||
    !Number.isFinite(y) ||
    typeof width !== 'number' ||
    !Number.isFinite(width) ||
    width < 0 ||
    typeof height !== 'number' ||
    !Number.isFinite(height) ||
    height < 0
  ) {
    throw new Error('Browser view bounds are invalid.')
  }

  return {
    x: Math.round(x),
    y: Math.round(y),
    width: Math.round(width),
    height: Math.round(height)
  }
}

export function parseBrowserControlAction(value: unknown): BrowserControlAction {
  if (value === 'back' || value === 'forward' || value === 'reload' || value === 'home') {
    return value
  }

  throw new Error('Browser control is invalid.')
}

export function parseBrowserTabId(value: unknown): string {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error('Browser tab is invalid.')
  }

  const tabId = value.trim()
  if (tabId.length > 80 || !/^[A-Za-z0-9_-]+$/.test(tabId)) {
    throw new Error('Browser tab is invalid.')
  }

  return tabId
}

function navigationTarget(event: BrowserNavigationEvent, url?: string): string {
  if (typeof url === 'string') {
    return url
  }

  return typeof event.url === 'string' ? event.url : ''
}

function isBlankBrowserUrl(url: string): boolean {
  return url === '' || url === BROWSER_HOME_URL
}

export function browserDisplayUrl(url: string): string {
  if (isBlankBrowserUrl(url)) {
    return ''
  }

  try {
    const parsed = new URL(url)
    parsed.username = ''
    parsed.password = ''
    return parsed.toString()
  } catch {
    return ''
  }
}

function truncateBrowserText(value: string, limit: number): string {
  return value.length <= limit ? value : value.slice(0, limit)
}

async function loadTabUrl(view: BrowserPageView, url: string): Promise<void> {
  try {
    await view.webContents.loadURL(url)
  } catch {
    throw new Error('Browser page could not be opened.')
  }
}

function titleFromUrl(url: string): string {
  if (isBlankBrowserUrl(url)) {
    return 'New Tab'
  }

  try {
    const hostname = new URL(url).hostname.replace(/^www\./u, '')
    return hostname === '' ? 'New Tab' : hostname
  } catch {
    return 'New Tab'
  }
}

function denyUnsafeNavigation(event: BrowserNavigationEvent, url?: string): void {
  const target = navigationTarget(event, url)
  if (isBlankBrowserUrl(target)) {
    return
  }

  try {
    parseBrowserWebUrl(target)
  } catch {
    event.preventDefault()
  }
}

export class VisibleBrowser {
  private readonly session: Session
  private readonly createView: (options: WebContentsViewConstructorOptions) => BrowserPageView
  private readonly onTabState: ((state: BrowserTabState) => void) | undefined
  private readonly tabs = new Map<string, BrowserPageView>()
  private hostWindow: BrowserHostWindow | undefined
  private lastBounds: BrowserViewBounds | undefined
  private visibleTabId: string | undefined
  private disposed = false

  constructor(options: VisibleBrowserOptions) {
    this.session = options.session
    this.createView = options.createView
    this.onTabState = options.onTabState
  }

  show(window: BrowserHostWindow, bounds: BrowserViewBounds, tabId: string): void {
    this.assertNotDisposed()
    const nextTabId = parseBrowserTabId(tabId)
    const view = this.ensureView(nextTabId)
    this.lastBounds = bounds
    if (this.visibleTabId !== undefined && this.visibleTabId !== nextTabId) {
      this.detachVisibleView()
    }

    if (
      this.hostWindow !== undefined &&
      this.hostWindow !== window &&
      !this.hostWindow.isDestroyed()
    ) {
      this.hostWindow.contentView.removeChildView(view)
    }

    this.hostWindow = window
    if (!window.contentView.children.includes(view)) {
      window.contentView.addChildView(view)
    }

    view.setBounds(bounds)
    view.setVisible(true)
    this.visibleTabId = nextTabId
  }

  hide(): void {
    if (this.disposed) {
      return
    }

    this.detachVisibleView()
  }

  async navigate(tabId: string, url: string): Promise<string> {
    this.assertNotDisposed()
    const safeUrl = parseBrowserWebUrl(url)
    await loadTabUrl(this.ensureView(parseBrowserTabId(tabId)), safeUrl)
    return browserDisplayUrl(safeUrl)
  }

  async control(tabId: string, action: BrowserControlAction): Promise<void> {
    this.assertNotDisposed()
    const id = parseBrowserTabId(tabId)
    const view = action === 'home' ? this.ensureView(id) : this.tabs.get(id)
    if (view === undefined) {
      return
    }

    switch (action) {
      case 'back':
        if (view.webContents.canGoBack()) {
          view.webContents.goBack()
        }
        break
      case 'forward':
        if (view.webContents.canGoForward()) {
          view.webContents.goForward()
        }
        break
      case 'reload':
        if (!isBlankBrowserUrl(view.webContents.getURL())) {
          view.webContents.reload()
        }
        break
      case 'home':
        await loadTabUrl(view, BROWSER_HOME_URL)
        break
    }
  }

  closeTab(tabId: string): void {
    this.assertNotDisposed()
    const closedTabId = parseBrowserTabId(tabId)
    const view = this.tabs.get(closedTabId)
    if (view === undefined) {
      return
    }

    if (this.visibleTabId === closedTabId) {
      this.detachVisibleView()
    }

    if (this.hostWindow !== undefined && !this.hostWindow.isDestroyed()) {
      this.hostWindow.contentView.removeChildView(view)
    }

    view.webContents.close()
    this.tabs.delete(closedTabId)
  }

  isVisibleTab(tabId: string): boolean {
    if (this.disposed) {
      return false
    }

    return this.visibleTabId === parseBrowserTabId(tabId)
  }

  async readCurrentPage(tabId: string): Promise<BrowserPageContent> {
    this.assertNotDisposed()
    const id = parseBrowserTabId(tabId)
    if (this.visibleTabId !== id) {
      throw new Error('Browser page is not visible.')
    }

    const view = this.tabs.get(id)
    if (view === undefined) {
      throw new Error('Browser page is not available.')
    }

    let extracted: unknown
    try {
      extracted = await view.webContents.executeJavaScript(BROWSER_PAGE_EXTRACT_SCRIPT)
    } catch {
      throw new Error('Browser page could not be read.')
    }

    if (typeof extracted !== 'object' || extracted === null || Array.isArray(extracted)) {
      throw new Error('Browser page could not be read.')
    }

    const record = extracted as Record<string, unknown>
    if (typeof record.title !== 'string' || typeof record.text !== 'string') {
      throw new Error('Browser page could not be read.')
    }

    return {
      title: truncateBrowserText(record.title, BROWSER_PAGE_TITLE_LIMIT),
      url: browserDisplayUrl(view.webContents.getURL()),
      text: truncateBrowserText(record.text, BROWSER_PAGE_TEXT_LIMIT)
    }
  }

  getVisibleTabId(): string | undefined {
    return this.visibleTabId
  }

  listPersistedTabs(): Array<{ tabId: string; url: string }> {
    this.assertNotDisposed()
    return [...this.tabs.entries()].map(([tabId, view]) => ({
      tabId,
      url: browserDisplayUrl(view.webContents.getURL())
    }))
  }

  async restorePersistedTabs(
    tabs: ReadonlyArray<{ tabId: string; url: string }>,
    visibleTabId: string
  ): Promise<void> {
    this.assertNotDisposed()
    const limited = tabs.slice(0, MAX_BROWSER_TABS)
    if (limited.length === 0) {
      const fallbackId = parseBrowserTabId(visibleTabId)
      this.ensureView(fallbackId)
      this.visibleTabId = fallbackId
      return
    }

    for (const tab of limited) {
      const tabId = parseBrowserTabId(tab.tabId)
      const view = this.ensureView(tabId)
      const url = tab.url.trim()
      if (url !== '') {
        try {
          await loadTabUrl(view, parseBrowserWebUrl(url))
        } catch {
          // Keep the restored tab shell even if the page fails to load.
        }
      }
      this.publishTabState(tabId, view)
    }

    try {
      this.visibleTabId = parseBrowserTabId(visibleTabId)
      if (!this.tabs.has(this.visibleTabId)) {
        this.visibleTabId = limited[0]!.tabId
      }
    } catch {
      this.visibleTabId = limited[0]!.tabId
    }
  }

  dispose(): void {
    if (this.disposed) {
      return
    }

    this.disposed = true
    for (const view of this.tabs.values()) {
      if (this.hostWindow !== undefined && !this.hostWindow.isDestroyed()) {
        this.hostWindow.contentView.removeChildView(view)
      }
      view.webContents.close()
    }

    this.tabs.clear()
    this.visibleTabId = undefined
    this.hostWindow = undefined
    this.lastBounds = undefined
  }

  private assertNotDisposed(): void {
    if (this.disposed) {
      throw new Error('Browser view has been closed.')
    }
  }

  private detachVisibleView(): void {
    if (this.visibleTabId === undefined) {
      return
    }

    const view = this.tabs.get(this.visibleTabId)
    this.visibleTabId = undefined
    if (view === undefined) {
      return
    }

    view.setVisible(false)
    if (this.hostWindow !== undefined && !this.hostWindow.isDestroyed()) {
      this.hostWindow.contentView.removeChildView(view)
    }
  }

  private ensureView(tabId: string): BrowserPageView {
    const existing = this.tabs.get(tabId)
    if (existing !== undefined) {
      return existing
    }

    if (this.tabs.size >= MAX_BROWSER_TABS) {
      throw new Error('Too many browser tabs.')
    }

    const view = this.createView({
      webPreferences: {
        session: this.session,
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true
      }
    })

    view.webContents.setWindowOpenHandler((details) => {
      this.handleWindowOpen(details?.url)
      return { action: 'deny' }
    })
    view.webContents.on('will-navigate', denyUnsafeNavigation)
    view.webContents.on('will-redirect', denyUnsafeNavigation)
    view.webContents.on('will-frame-navigate', denyUnsafeNavigation)
    const publish = (): void => {
      this.publishTabState(tabId, view)
    }
    view.webContents.on('did-navigate', publish)
    view.webContents.on('did-navigate-in-page', publish)
    view.webContents.on('page-title-updated', publish)
    this.tabs.set(tabId, view)
    return view
  }

  private handleWindowOpen(url: unknown): void {
    let safeUrl: string
    try {
      safeUrl = parseBrowserWebUrl(url)
    } catch {
      return
    }

    if (this.tabs.size >= MAX_BROWSER_TABS) {
      const fallbackId = this.visibleTabId
      if (fallbackId === undefined) {
        return
      }

      void this.ensureView(fallbackId)
        .webContents.loadURL(safeUrl)
        .catch(() => undefined)
      return
    }

    const tabId = this.createTabId()
    const view = this.ensureView(tabId)
    void view.webContents.loadURL(safeUrl).catch(() => undefined)
    if (
      this.visibleTabId !== undefined &&
      this.hostWindow !== undefined &&
      this.lastBounds !== undefined
    ) {
      this.show(this.hostWindow, this.lastBounds, tabId)
    }

    this.onTabState?.({
      tabId,
      url: browserDisplayUrl(safeUrl),
      title: titleFromUrl(safeUrl),
      canGoBack: false,
      canGoForward: false
    })
  }

  private createTabId(): string {
    let tabId = crypto.randomUUID()
    while (this.tabs.has(tabId)) {
      tabId = crypto.randomUUID()
    }

    return tabId
  }

  private publishTabState(tabId: string, view: BrowserPageView): void {
    this.onTabState?.(this.snapshot(tabId, view))
  }

  private snapshot(tabId: string, view: BrowserPageView): BrowserTabState {
    const rawUrl = view.webContents.getURL()
    const url = browserDisplayUrl(rawUrl)
    const pageTitle = view.webContents.getTitle().trim()
    const title =
      url === '' || pageTitle === '' || isBlankBrowserUrl(pageTitle) ? titleFromUrl(url) : pageTitle

    return {
      tabId,
      url,
      title,
      canGoBack: view.webContents.canGoBack(),
      canGoForward: view.webContents.canGoForward()
    }
  }
}
