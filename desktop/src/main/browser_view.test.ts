import { EventEmitter } from 'node:events'
import { runInNewContext } from 'node:vm'
import type { Session, WebContentsViewConstructorOptions } from 'electron'
import { describe, expect, it, vi } from 'vitest'

import {
  BROWSER_EDITOR_OBSERVATION_SCRIPT,
  BROWSER_FRAME_INDEX_SCRIPT,
  MAX_BROWSER_TABS,
  parseBrowserControlAction,
  parseBrowserTabId,
  parseBrowserViewBounds,
  VisibleBrowser,
  type BrowserFrame,
  type BrowserHostWindow,
  type BrowserNavigationEvent,
  type BrowserPageView,
  type BrowserTabState,
  type VisibleBrowserOptions
} from './browser_view'

type FakeWebContents = BrowserPageView['webContents'] & {
  loadURL: ReturnType<typeof vi.fn>
  close: ReturnType<typeof vi.fn>
  getURL: ReturnType<typeof vi.fn>
  getTitle: ReturnType<typeof vi.fn>
  canGoBack: ReturnType<typeof vi.fn>
  canGoForward: ReturnType<typeof vi.fn>
  goBack: ReturnType<typeof vi.fn>
  goForward: ReturnType<typeof vi.fn>
  reload: ReturnType<typeof vi.fn>
  executeJavaScript: ReturnType<typeof vi.fn>
  sendInputEvent: ReturnType<typeof vi.fn>
  setWindowOpenHandler: ReturnType<typeof vi.fn>
  on: ReturnType<typeof vi.fn>
  mainFrame: BrowserFrame & {
    executeJavaScript: ReturnType<typeof vi.fn>
    isDestroyed: ReturnType<typeof vi.fn>
  }
}

type FakePageView = BrowserPageView & {
  setBounds: ReturnType<typeof vi.fn>
  setVisible: ReturnType<typeof vi.fn>
  webContents: FakeWebContents
  emit(event: string, navigationEvent: BrowserNavigationEvent, url?: string): void
  listenerCount(event: string): number
  options: WebContentsViewConstructorOptions
}

function createFakeFrame(
  options: {
    url?: string
    frames?: BrowserFrame[]
    executeJavaScript?: ReturnType<typeof vi.fn>
  } = {}
): BrowserFrame & {
  executeJavaScript: ReturnType<typeof vi.fn>
  isDestroyed: ReturnType<typeof vi.fn>
} {
  const executeJavaScript =
    options.executeJavaScript ?? vi.fn(async () => ({ title: '', text: '', elements: [] }))
  return {
    url: options.url ?? 'https://example.com/',
    frames: options.frames ?? [],
    isDestroyed: vi.fn(() => false),
    executeJavaScript: executeJavaScript as BrowserFrame['executeJavaScript'] &
      ReturnType<typeof vi.fn>
  }
}

function createFakeView(options: WebContentsViewConstructorOptions): FakePageView {
  const listeners = new EventEmitter()
  const executeJavaScript = vi.fn(async () => ({ title: '', text: '', elements: [] }))
  const mainFrame = createFakeFrame({ executeJavaScript })
  const webContents = {
    loadURL: vi.fn(async () => undefined),
    close: vi.fn(() => listeners.emit('destroyed')),
    getURL: vi.fn(() => ''),
    getTitle: vi.fn(() => ''),
    canGoBack: vi.fn(() => false),
    canGoForward: vi.fn(() => false),
    goBack: vi.fn(),
    goForward: vi.fn(),
    reload: vi.fn(),
    executeJavaScript,
    mainFrame,
    focus: vi.fn(),
    insertText: vi.fn(async () => undefined),
    sendInputEvent: vi.fn(),
    setWindowOpenHandler: vi.fn(),
    on: vi.fn((event: string, listener: (event: BrowserNavigationEvent, url?: string) => void) => {
      listeners.on(event, listener)
    })
  }

  return {
    setBounds: vi.fn(),
    setVisible: vi.fn(),
    webContents,
    emit(event: string, navigationEvent: BrowserNavigationEvent, url?: string) {
      listeners.emit(event, navigationEvent, url)
    },
    listenerCount: (event: string) => listeners.listenerCount(event),
    options
  } as FakePageView & {
    emit(event: string, navigationEvent: BrowserNavigationEvent, url?: string): void
    options: WebContentsViewConstructorOptions
  }
}

function createFakeWindow(): BrowserHostWindow & {
  contentView: BrowserHostWindow['contentView'] & {
    addChildView: ReturnType<typeof vi.fn>
    removeChildView: ReturnType<typeof vi.fn>
  }
} {
  const children: BrowserPageView[] = []
  return {
    isFocused: vi.fn(() => true),
    isDestroyed: vi.fn(() => false),
    contentView: {
      get children() {
        return children
      },
      addChildView: vi.fn((view: BrowserPageView) => {
        if (!children.includes(view)) {
          children.push(view)
        }
      }),
      removeChildView: vi.fn((view: BrowserPageView) => {
        const index = children.indexOf(view)
        if (index >= 0) {
          children.splice(index, 1)
        }
      })
    }
  }
}

function createBrowser(options?: Partial<VisibleBrowserOptions>): {
  browser: VisibleBrowser
  createView: ReturnType<typeof vi.fn>
  session: Session
} {
  const session = options?.session ?? ({ id: 'browser-profile' } as unknown as Session)
  const createView =
    (options?.createView as
      ((opts: WebContentsViewConstructorOptions) => BrowserPageView) | undefined) ??
    vi.fn((viewOptions: WebContentsViewConstructorOptions) => createFakeView(viewOptions))
  return {
    browser: new VisibleBrowser({
      session,
      createView,
      onTabState: options?.onTabState,
      fetchPdf: options?.fetchPdf
    }),
    createView: createView as ReturnType<typeof vi.fn>,
    session
  }
}

describe('parseBrowserViewBounds', () => {
  it('rounds finite rectangle values', () => {
    expect(parseBrowserViewBounds({ x: 10.4, y: 20.6, width: 300.2, height: 180.8 })).toEqual({
      x: 10,
      y: 21,
      width: 300,
      height: 181
    })
  })

  it.each([
    null,
    { x: 0, y: 0, width: 100 },
    { x: 0, y: 0, width: -1, height: 10 },
    { x: Number.NaN, y: 0, width: 10, height: 10 }
  ])('rejects invalid bounds: %s', (value) => {
    expect(() => parseBrowserViewBounds(value)).toThrow(/Browser view bounds/)
  })
})

describe('parseBrowserTabId', () => {
  it('accepts compact identifiers including UUID-shaped values', () => {
    expect(parseBrowserTabId('tab-1')).toBe('tab-1')
    expect(parseBrowserTabId('  2b1c0a8e-3d44-4f21-9a1b-7c8d9e0f1a2b  ')).toBe(
      '2b1c0a8e-3d44-4f21-9a1b-7c8d9e0f1a2b'
    )
  })

  it.each([null, '', '   ', 'tab/1', 'tab 1', 'x'.repeat(81)])(
    'rejects invalid tab id: %s',
    (value) => {
      expect(() => parseBrowserTabId(value)).toThrow(/Browser tab/)
    }
  )
})

describe('VisibleBrowser', () => {
  const bounds = { x: 226, y: 64, width: 720, height: 480 }

  it('creates a sandboxed view without a page preload and shows it in the window', () => {
    const { browser, createView, session } = createBrowser()
    const window = createFakeWindow()

    browser.show(window, bounds, 'tab-1')

    expect(createView).toHaveBeenCalledTimes(1)
    const options = createView.mock.calls[0]?.[0] as WebContentsViewConstructorOptions
    expect(options.webPreferences).toMatchObject({
      session,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    })
    expect(options.webPreferences).not.toHaveProperty('preload')

    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    expect(window.contentView.addChildView).toHaveBeenCalledWith(view)
    expect(view.setBounds).toHaveBeenCalledWith(bounds)
    expect(view.setVisible).toHaveBeenCalledWith(true)
    expect(view.webContents.setWindowOpenHandler).toHaveBeenCalledTimes(1)
    const openHandler = view.webContents.setWindowOpenHandler.mock.calls[0]?.[0] as (details?: {
      url?: string
    }) => { action: 'deny' }
    expect(openHandler()).toEqual({ action: 'deny' })
  })

  it('hides without destroying the page so a later show keeps the same view', () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>

    browser.hide()

    expect(view.setVisible).toHaveBeenCalledWith(false)
    expect(window.contentView.removeChildView).toHaveBeenCalledWith(view)
    expect(view.webContents.close).not.toHaveBeenCalled()
    expect(window.contentView.children).toEqual([])

    browser.show(window, { ...bounds, width: 800 }, 'tab-1')

    expect(createView).toHaveBeenCalledTimes(1)
    expect(window.contentView.children).toEqual([view])
    expect(view.setBounds).toHaveBeenLastCalledWith({ ...bounds, width: 800 })
    expect(view.setVisible).toHaveBeenLastCalledWith(true)
  })

  it('navigates HTTP and HTTPS pages, including URLs with credentials', async () => {
    const { browser, createView } = createBrowser()
    expect(await browser.navigate('tab-1', 'https://example.com')).toBe('https://example.com/')
    await browser.navigate('tab-1', 'https://user:password@example.com/secret')
    await browser.navigate('tab-1', 'http://example.com')
    await browser.navigate('tab-1', 'example.com')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>

    expect(view.webContents.loadURL).toHaveBeenCalledWith('https://example.com/')
    expect(view.webContents.loadURL).toHaveBeenCalledWith(
      'https://user:password@example.com/secret'
    )
    expect(view.webContents.loadURL).toHaveBeenCalledWith('http://example.com/')
    expect(view.webContents.loadURL).toHaveBeenCalledTimes(4)
    expect(createView).toHaveBeenCalledTimes(1)
  })

  it('returns a credential-free display URL after navigation', async () => {
    const { browser, createView } = createBrowser()

    await expect(
      browser.navigate('tab-1', 'https://user:password@example.com/private')
    ).resolves.toBe('https://example.com/private')

    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    expect(view.webContents.loadURL).toHaveBeenCalledWith(
      'https://user:password@example.com/private'
    )
  })

  it('returns credential-free page context for persistence', () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://user:password@example.com/private?section=one')
    view.webContents.getTitle.mockReturnValue('Private page')

    expect(browser.getTabState('tab-1')).toMatchObject({
      tabId: 'tab-1',
      url: 'https://example.com/private?section=one',
      title: 'Private page'
    })
  })

  it.each(['file:///tmp/test', 'javascript:alert(1)', 'mailto:user@example.com'])(
    'rejects non-web navigation: %s',
    async (url) => {
      const { browser, createView } = createBrowser()
      await expect(browser.navigate('tab-1', url)).rejects.toThrow(/Browser address/)
      expect(createView).not.toHaveBeenCalled()
    }
  )

  it('blocks non-web in-page navigations but allows credentialed HTTPS redirects', () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView> & {
      emit(event: string, navigationEvent: BrowserNavigationEvent, url?: string): void
    }

    const blocked = { preventDefault: vi.fn() }
    view.emit('will-navigate', blocked, 'file:///tmp/test')
    expect(blocked.preventDefault).toHaveBeenCalledTimes(1)

    const allowed = { preventDefault: vi.fn() }
    view.emit('will-navigate', allowed, 'https://example.com/next')
    view.emit('will-redirect', allowed, 'https://user:password@example.com')
    expect(allowed.preventDefault).not.toHaveBeenCalled()
  })

  it('destroys the view on dispose and refuses later use', async () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>

    browser.dispose()
    browser.dispose()

    expect(window.contentView.removeChildView).toHaveBeenCalledWith(view)
    expect(view.webContents.close).toHaveBeenCalledTimes(1)
    expect(() => browser.show(window, bounds, 'tab-1')).toThrow(/closed/)
    await expect(browser.navigate('tab-1', 'https://example.com')).rejects.toThrow(/closed/)
  })

  it('switches tabs without destroying the hidden page', () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    browser.navigate('tab-1', 'https://example.com')
    const first = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>

    browser.show(window, bounds, 'tab-2')
    const second = createView.mock.results[1]?.value as ReturnType<typeof createFakeView>

    expect(createView).toHaveBeenCalledTimes(2)
    expect(first.setVisible).toHaveBeenCalledWith(false)
    expect(window.contentView.children).toEqual([second])
    expect(first.webContents.close).not.toHaveBeenCalled()

    browser.show(window, bounds, 'tab-1')
    expect(createView).toHaveBeenCalledTimes(2)
    expect(window.contentView.children).toEqual([first])
    expect(first.setVisible).toHaveBeenLastCalledWith(true)
  })

  it('closes one tab and keeps the other', () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    browser.show(window, bounds, 'tab-2')
    const first = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    const second = createView.mock.results[1]?.value as ReturnType<typeof createFakeView>

    browser.closeTab('tab-2')

    expect(second.webContents.close).toHaveBeenCalledTimes(1)
    expect(first.webContents.close).not.toHaveBeenCalled()
    expect(window.contentView.children).toEqual([])
  })

  it('loads a background tab without attaching it until it is shown', () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.navigate('tab-2', 'https://example.com')
    const background = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>

    expect(window.contentView.children).toEqual([])
    expect(background.webContents.loadURL).toHaveBeenCalledWith('https://example.com/')

    browser.show(window, bounds, 'tab-2')
    expect(window.contentView.children).toEqual([background])
  })

  it('refuses more than the tab limit', async () => {
    const { browser } = createBrowser()
    for (let index = 0; index < MAX_BROWSER_TABS; index += 1) {
      await browser.navigate(`tab-${index}`, 'https://example.com')
    }

    await expect(browser.navigate('tab-overflow', 'https://example.com')).rejects.toThrow(
      /Too many/
    )
  })

  it('propagates page load failures from navigate and home', async () => {
    const { browser, createView } = createBrowser()
    createView.mockImplementation((options) => {
      const view = createFakeView(options)
      view.webContents.loadURL.mockRejectedValue(new Error('ERR_NAME_NOT_RESOLVED'))
      return view
    })

    await expect(browser.navigate('tab-1', 'https://example.com')).rejects.toThrow(
      /could not be opened/
    )

    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-2')
    await expect(browser.control('tab-2', 'home')).rejects.toThrow(/could not be opened/)
  })

  it('moves back, forward, reloads, and returns home', async () => {
    const { browser, createView } = createBrowser()
    await browser.navigate('tab-1', 'https://example.com')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://example.com/')
    view.webContents.canGoBack.mockReturnValue(true)
    view.webContents.canGoForward.mockReturnValue(true)

    await browser.control('tab-1', 'back')
    await browser.control('tab-1', 'forward')
    await browser.control('tab-1', 'reload')
    await browser.control('tab-1', 'home')

    expect(view.webContents.goBack).toHaveBeenCalledTimes(1)
    expect(view.webContents.goForward).toHaveBeenCalledTimes(1)
    expect(view.webContents.reload).toHaveBeenCalledTimes(1)
    expect(view.webContents.loadURL).toHaveBeenCalledWith('about:blank')
  })

  it('does not move or reload when the page has no history', () => {
    const { browser, createView } = createBrowser()
    browser.navigate('tab-1', 'https://example.com')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('')

    browser.control('tab-1', 'back')
    browser.control('tab-1', 'forward')
    browser.control('tab-1', 'reload')

    expect(view.webContents.goBack).not.toHaveBeenCalled()
    expect(view.webContents.goForward).not.toHaveBeenCalled()
    expect(view.webContents.reload).not.toHaveBeenCalled()
  })

  it('allows a blank home page and publishes tab state after navigation', () => {
    const states: BrowserTabState[] = []
    const session = { id: 'browser-profile' } as unknown as Session
    const createView = vi.fn((options: WebContentsViewConstructorOptions) =>
      createFakeView(options)
    )
    const browser = new VisibleBrowser({
      session,
      createView,
      onTabState: (state) => {
        states.push(state)
      }
    })
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView> & {
      emit(event: string, navigationEvent: BrowserNavigationEvent, url?: string): void
    }

    const homeNav = { preventDefault: vi.fn() }
    view.emit('will-navigate', homeNav, 'about:blank')
    expect(homeNav.preventDefault).not.toHaveBeenCalled()

    view.webContents.getURL.mockReturnValue('https://example.com/')
    view.webContents.getTitle.mockReturnValue('Example Domain')
    view.webContents.canGoBack.mockReturnValue(true)
    view.emit('did-navigate', { preventDefault: vi.fn() }, 'https://example.com/')

    expect(states).toEqual([
      {
        tabId: 'tab-1',
        url: 'https://example.com/',
        title: 'Example Domain',
        canGoBack: true,
        canGoForward: false
      }
    ])

    view.webContents.getURL.mockReturnValue('https://user:password@example.com/private')
    view.emit('did-navigate', { preventDefault: vi.fn() })
    expect(states[1]?.url).toBe('https://example.com/private')
  })
})

describe('parseBrowserControlAction', () => {
  it.each(['back', 'forward', 'reload', 'home'] as const)('accepts %s', (action) => {
    expect(parseBrowserControlAction(action)).toBe(action)
  })

  it.each([null, '', 'stop', 'BACK'])('rejects invalid control: %s', (value) => {
    expect(() => parseBrowserControlAction(value)).toThrow(/Browser control/)
  })
})

describe('VisibleBrowser window.open', () => {
  const bounds = { x: 226, y: 64, width: 720, height: 480 }

  it('opens http(s) popup links in a new managed tab instead of a new window', () => {
    const states: BrowserTabState[] = []
    const session = { id: 'browser-profile' } as unknown as Session
    const createView = vi.fn((options: WebContentsViewConstructorOptions) =>
      createFakeView(options)
    )
    const browser = new VisibleBrowser({
      session,
      createView,
      onTabState: (state) => {
        states.push(state)
      }
    })
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const first = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    const openHandler = first.webContents.setWindowOpenHandler.mock.calls[0]?.[0] as (details: {
      url: string
    }) => { action: 'deny' }

    expect(openHandler({ url: 'https://b.example/xx' })).toEqual({ action: 'deny' })
    expect(createView).toHaveBeenCalledTimes(2)
    const second = createView.mock.results[1]?.value as ReturnType<typeof createFakeView>
    expect(second.webContents.loadURL).toHaveBeenCalledWith('https://b.example/xx')
    expect(window.contentView.children).toEqual([second])
    expect(states.some((state) => state.url === 'https://b.example/xx')).toBe(true)
  })

  it('ignores non-web popup targets', () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    const openHandler = view.webContents.setWindowOpenHandler.mock.calls[0]?.[0] as (details: {
      url: string
    }) => { action: 'deny' }

    expect(openHandler({ url: 'file:///tmp/secret' })).toEqual({ action: 'deny' })
    expect(createView).toHaveBeenCalledTimes(1)
  })

  it('loads the popup in the current tab when the tab limit is reached', () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    for (let index = 0; index < MAX_BROWSER_TABS; index += 1) {
      browser.navigate(`tab-${index}`, 'https://example.com')
    }
    browser.show(window, bounds, 'tab-0')
    const current = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    const openHandler = current.webContents.setWindowOpenHandler.mock.calls[0]?.[0] as (details: {
      url: string
    }) => { action: 'deny' }

    expect(openHandler({ url: 'https://b.example/xx' })).toEqual({ action: 'deny' })
    expect(createView).toHaveBeenCalledTimes(MAX_BROWSER_TABS)
    expect(current.webContents.loadURL).toHaveBeenCalledWith('https://b.example/xx')
  })

  it('reads only the currently visible tab and scrubs credentials from the URL', async () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://user:secret@example.com/path')
    view.webContents.executeJavaScript.mockResolvedValue({
      title: 'Example Domain',
      text: 'Hello page'
    })

    await expect(browser.readCurrentPage('tab-1')).resolves.toEqual({
      title: 'Example Domain',
      url: 'https://example.com/path',
      text: 'Hello page'
    })
    await expect(browser.readCurrentPage('tab-missing')).rejects.toThrow('not visible')
  })

  it('includes bounded text from nested frames without exposing their URLs', async () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://example.com/outer')
    const child = createFakeFrame({
      url: 'https://embedded.example/private',
      executeJavaScript: vi.fn(async (script: string) =>
        script === BROWSER_FRAME_INDEX_SCRIPT
          ? 0
          : {
              title: 'Embedded app',
              text: 'Prediction Results',
              structured_text: 'UG_at_PS: 13.21 wt.%\nUV_at_PS: 39.09 g H₂/L'
            }
      )
    })
    Object.defineProperty(view.webContents.mainFrame, 'frames', {
      value: [child],
      configurable: true
    })
    view.webContents.executeJavaScript.mockImplementation(async (script: string) =>
      script.includes('const child = window.frames[')
        ? true
        : {
            title: 'Outer page',
            text: 'Hugging Face Space'
          }
    )

    await expect(browser.readCurrentPage('tab-1')).resolves.toEqual({
      title: 'Outer page',
      url: 'https://example.com/outer',
      text: 'Hugging Face Space\n\n[Embedded page content]\nPrediction Results\n\n[Structured table content]\nUG_at_PS: 13.21 wt.%\nUV_at_PS: 39.09 g H₂/L'
    })
    expect(child.executeJavaScript).toHaveBeenCalledTimes(2)
    expect(String(child.executeJavaScript.mock.calls[1]?.[0])).toContain('aria-valuetext')
  })

  it('does not extract hidden frame subtrees or a frame whose owner cannot be resolved', async () => {
    const { browser, createView } = createBrowser()
    browser.show(createFakeWindow(), bounds, 'tab-1')
    const view = createView.mock.results[0].value as ReturnType<typeof createFakeView>
    const nested = createFakeFrame({ executeJavaScript: vi.fn() })
    const hidden = createFakeFrame({ executeJavaScript: vi.fn(async () => 0) })
    Object.assign(hidden, { frames: [nested] })
    const detached = createFakeFrame({ executeJavaScript: vi.fn(async () => -1) })
    Object.assign(view.webContents.mainFrame, { frames: [hidden, detached] })
    view.webContents.executeJavaScript.mockImplementation(async (script: string) =>
      script.includes('const child = window.frames[') ? false : { title: 'Page', text: 'Visible' }
    )
    expect((await browser.readCurrentPage('tab-1')).text).toBe('Visible')
    expect(hidden.executeJavaScript).toHaveBeenCalledTimes(1)
    expect(detached.executeJavaScript).toHaveBeenCalledTimes(1)
    expect(nested.executeJavaScript).not.toHaveBeenCalled()
  })

  it('rejects reads after the tab is no longer visible', async () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    browser.hide()
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>

    await expect(browser.readCurrentPage('tab-1')).rejects.toThrow('not visible')
    expect(view.webContents.executeJavaScript).not.toHaveBeenCalled()
  })

  it('returns early with the stable page after visible content changes', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.executeJavaScript
      .mockResolvedValueOnce({ title: 'Page', text: 'Working' })
      .mockResolvedValueOnce({ title: 'Page', text: 'Results are ready' })
      .mockResolvedValueOnce({ title: 'Page', text: 'Results are ready' })

    const pending = browser.waitForCurrentPage('tab-1', 15)
    await vi.advanceTimersByTimeAsync(1_000)
    await expect(pending).resolves.toEqual({
      changed: true,
      page: { title: 'Page', url: '', text: 'Results are ready' }
    })
    vi.useRealTimers()
  })

  it('returns early when navigation changes the URL without changing page text', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL
      .mockReturnValueOnce('https://example.com/before')
      .mockReturnValueOnce('https://example.com/after')
      .mockReturnValueOnce('https://example.com/after')
    view.webContents.executeJavaScript.mockResolvedValue({
      title: 'Calendar',
      text: 'Same controls'
    })

    const pending = browser.waitForCurrentPage('tab-1', 15)
    await vi.advanceTimersByTimeAsync(1_000)
    await expect(pending).resolves.toEqual({
      changed: true,
      page: { title: 'Calendar', url: 'https://example.com/after', text: 'Same controls' }
    })
    vi.useRealTimers()
  })

  it('returns the latest page at the timeout and rejects a hidden tab', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.executeJavaScript.mockResolvedValue({ title: 'Page', text: 'Working' })

    const unchanged = browser.waitForCurrentPage('tab-1', 1)
    await vi.advanceTimersByTimeAsync(1_000)
    await expect(unchanged).resolves.toEqual({
      changed: false,
      page: { title: 'Page', url: '', text: 'Working' }
    })

    const hidden = browser.waitForCurrentPage('tab-1', 1)
    await vi.advanceTimersByTimeAsync(0)
    const hiddenAssertion = expect(hidden).rejects.toThrow('not visible')
    browser.hide()
    await vi.advanceTimersByTimeAsync(500)
    await hiddenAssertion
    vi.useRealTimers()
  })

  it('restores persisted tabs and lists scrubbed urls', async () => {
    const { browser, createView } = createBrowser()
    const first = createFakeView({} as WebContentsViewConstructorOptions)
    const second = createFakeView({} as WebContentsViewConstructorOptions)
    createView.mockReturnValueOnce(first).mockReturnValueOnce(second)
    first.webContents.getURL.mockReturnValue('https://user:secret@one.example/a')
    second.webContents.getURL.mockReturnValue('https://two.example/b')

    await browser.restorePersistedTabs(
      [
        { tabId: 'tab-1', url: 'https://one.example/a' },
        { tabId: 'tab-2', url: 'https://two.example/b' }
      ],
      'tab-2'
    )

    expect(browser.getVisibleTabId()).toBe('tab-2')
    expect(first.webContents.loadURL).toHaveBeenCalledWith('https://one.example/a')
    expect(second.webContents.loadURL).toHaveBeenCalledWith('https://two.example/b')
    expect(browser.listPersistedTabs()).toEqual([
      { tabId: 'tab-1', url: 'https://one.example/a' },
      { tabId: 'tab-2', url: 'https://two.example/b' }
    ])
  })

  it('clicks the visible tab with pointer cleanup and mouse event order', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://user:secret@example.com/path')
    view.webContents.getTitle.mockReturnValue('Example')
    view.webContents.executeJavaScript
      .mockResolvedValueOnce({
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
      .mockResolvedValueOnce({ title: '', text: '' })
      .mockResolvedValueOnce({ x: 40, y: 60, activation: 'mouse' })
      .mockResolvedValueOnce({ x: 40, y: 60 })
      .mockResolvedValueOnce(true)

    await expect(browser.inspectInteractive('tab-1')).resolves.toEqual({
      url: 'https://example.com/path',
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
    const pending = browser.clickCurrentPage('tab-1', 'target_1')
    await vi.advanceTimersByTimeAsync(150)
    await expect(pending).resolves.toEqual({
      action: 'clicked',
      url: 'https://example.com/path',
      title: 'Example'
    })

    const scripts = view.webContents.executeJavaScript.mock.calls.map((call) => String(call[0]))
    expect(scripts[0]).toContain('data-asagent-target-id')
    expect(JSON.stringify(scripts[0])).not.toContain('internal selector')
    expect(scripts[2]).toContain('data-asagent-target-id')
    expect(scripts[2]).toContain('asagent-agent-pointer')
    expect(scripts[4]).toContain('asagent-agent-pointer')
    expect(view.webContents.sendInputEvent.mock.calls.map((call) => call[0])).toEqual([
      { type: 'mouseMove', x: 40, y: 60 },
      { type: 'mouseDown', x: 40, y: 60, button: 'left', clickCount: 1 },
      { type: 'mouseUp', x: 40, y: 60, button: 'left', clickCount: 1 }
    ])
    vi.useRealTimers()
  })

  it('activates semantic label targets without requiring a label click box', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_1',
            name: 'Use sample file',
            role: 'checkbox',
            tag: 'label',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce({ title: '', text: '' })
      .mockResolvedValueOnce({ x: 20, y: 30, activation: 'click' })
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce(true)

    await browser.inspectInteractive('tab-1')
    const pending = browser.clickCurrentPage('tab-1', 'target_1')
    await vi.advanceTimersByTimeAsync(150)
    await expect(pending).resolves.toMatchObject({ action: 'clicked' })

    const scripts = view.webContents.executeJavaScript.mock.calls.map((call) => String(call[0]))
    expect(scripts[2]).toContain('semanticActivation = true')
    expect(scripts[3]).toContain('target.click()')
    expect(view.webContents.sendInputEvent).not.toHaveBeenCalled()
    vi.useRealTimers()
  })

  it('fills an inspected text target without submitting the form', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://example.com/form')
    view.webContents.getTitle.mockReturnValue('Example form')
    view.webContents.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_1',
            name: 'Email',
            role: 'email',
            tag: 'input',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce(true)

    await browser.inspectInteractive('tab-1')
    const pending = browser.fillCurrentPage('tab-1', 'target_1', 'person@example.com')
    await vi.advanceTimersByTimeAsync(150)
    await expect(pending).resolves.toEqual({
      action: 'filled',
      url: 'https://example.com/form',
      title: 'Example form'
    })

    const scripts = view.webContents.executeJavaScript.mock.calls.map((call) => String(call[0]))
    expect(scripts[2]).toContain('asagent-agent-pointer')
    expect(scripts[2]).not.toContain('elementFromPoint')
    expect(scripts[3]).toContain("type === 'password'")
    expect(scripts[3]).toContain("new Event('change'")
    expect(scripts[4]).toContain('asagent-agent-pointer')
    expect(view.webContents.sendInputEvent).not.toHaveBeenCalled()
    vi.useRealTimers()
  })

  it('returns a stable page snapshot after a fill changes the URL', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://mail.example.com/compose')
    view.webContents.getTitle.mockReturnValue('Compose')
    view.webContents.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_1',
            name: 'To',
            role: 'textbox',
            tag: 'input',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce({ title: 'Compose', text: 'New message' })
      .mockResolvedValueOnce(true)
      .mockImplementationOnce(async () => {
        view.webContents.getURL.mockReturnValue('https://mail.example.com/compose?draft=123')
        return true
      })
      .mockResolvedValueOnce({ title: 'Compose', text: 'New message' })
      .mockResolvedValueOnce({ title: 'Compose', text: 'New message' })
      .mockResolvedValueOnce(true)

    await browser.inspectInteractive('tab-1')
    const pending = browser.fillCurrentPage('tab-1', 'target_1', 'person@example.com')
    await vi.advanceTimersByTimeAsync(400)
    await expect(pending).resolves.toEqual({
      action: 'filled',
      url: 'https://mail.example.com/compose?draft=123',
      title: 'Compose',
      page: {
        title: 'Compose',
        url: 'https://mail.example.com/compose?draft=123',
        text: 'New message'
      }
    })
    vi.useRealTimers()
  })

  it('returns bounded native select options from inspect snapshots', async () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://example.com/form')
    view.webContents.executeJavaScript.mockResolvedValueOnce({
      elements: [
        {
          target_id: 'target_1',
          name: 'Email',
          role: 'email',
          tag: 'input',
          disabled: false
        },
        {
          target_id: 'target_2',
          name: 'Country',
          role: 'combobox',
          tag: 'select',
          disabled: false,
          options: [
            { value: 'au', label: 'Australia', disabled: false },
            { value: 'us', label: 'United States', disabled: false }
          ]
        }
      ]
    })

    await expect(browser.inspectInteractive('tab-1')).resolves.toEqual({
      url: 'https://example.com/form',
      elements: [
        {
          target_id: 'target_1',
          name: 'Email',
          role: 'email',
          tag: 'input',
          disabled: false
        },
        {
          target_id: 'target_2',
          name: 'Country',
          role: 'combobox',
          tag: 'select',
          disabled: false,
          options: [
            { value: 'au', label: 'Australia', disabled: false },
            { value: 'us', label: 'United States', disabled: false }
          ]
        }
      ]
    })

    const script = String(view.webContents.executeJavaScript.mock.calls[0]?.[0])
    expect(script).toContain('el instanceof HTMLSelectElement')
    expect(script).toContain('item.options = selectOptions(el)')
    expect(script).toContain('[role="dialog"]')
    expect(script).toContain('dialogElements.has(el)')
    expect(script).not.toContain('internal selector')
  })

  it('selects an inspected native select without submitting the form', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://example.com/form')
    view.webContents.getTitle.mockReturnValue('Country form')
    view.webContents.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_4',
            name: 'Country',
            role: 'combobox',
            tag: 'select',
            disabled: false,
            options: [{ value: 'au', label: 'Australia', disabled: false }]
          }
        ]
      })
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce(true)

    await browser.inspectInteractive('tab-1')
    const pending = browser.selectCurrentPage('tab-1', 'target_4', 'au')
    await vi.advanceTimersByTimeAsync(150)
    await expect(pending).resolves.toEqual({
      action: 'selected',
      url: 'https://example.com/form',
      title: 'Country form'
    })

    const scripts = view.webContents.executeJavaScript.mock.calls.map((call) => String(call[0]))
    expect(scripts[2]).toContain('asagent-agent-pointer')
    expect(scripts[3]).toContain('HTMLSelectElement.prototype')
    expect(scripts[3]).toContain("new Event('input'")
    expect(scripts[3]).toContain("new Event('change'")
    expect(scripts[3]).not.toContain('form.submit')
    expect(scripts[4]).toContain('asagent-agent-pointer')
    expect(view.webContents.sendInputEvent).not.toHaveBeenCalled()
    vi.useRealTimers()
  })

  it('selects iframe native select targets only inside the child frame', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://example.com/outer')
    view.webContents.getTitle.mockReturnValue('Outer')

    const child = createFakeFrame({ url: 'https://forms.example/app' })
    Object.defineProperty(view.webContents.mainFrame, 'frames', {
      value: [child],
      configurable: true
    })

    view.webContents.mainFrame.executeJavaScript.mockResolvedValueOnce({
      elements: [
        {
          target_id: 'target_1',
          name: 'Outer',
          role: 'button',
          tag: 'button',
          disabled: false
        }
      ]
    })
    child.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_2',
            name: 'Country',
            role: 'combobox',
            tag: 'select',
            disabled: false,
            options: [{ value: 'au', label: 'Australia', disabled: false }]
          }
        ]
      })
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce(true)

    await browser.inspectInteractive('tab-1')
    const pending = browser.selectCurrentPage('tab-1', 'target_2', 'au')
    await vi.advanceTimersByTimeAsync(150)
    await expect(pending).resolves.toEqual({
      action: 'selected',
      url: 'https://example.com/outer',
      title: 'Outer'
    })

    expect(view.webContents.sendInputEvent).not.toHaveBeenCalled()
    expect(view.webContents.mainFrame.executeJavaScript).toHaveBeenCalledTimes(2)
    const childScripts = child.executeJavaScript.mock.calls.map((call) => String(call[0]))
    expect(childScripts[2]).toContain('asagent-agent-pointer')
    expect(childScripts[3]).toContain('HTMLSelectElement.prototype')
    expect(childScripts[4]).toContain('asagent-agent-pointer')
    vi.useRealTimers()
  })

  it('returns a stable page snapshot after a select navigates without changing text', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://example.com/calendar/september')
    view.webContents.getTitle.mockReturnValue('September')
    view.webContents.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_4',
            name: 'Month',
            role: 'combobox',
            tag: 'select',
            disabled: false,
            options: [{ value: '10', label: 'October', disabled: false }]
          }
        ]
      })
      .mockResolvedValueOnce({ title: 'September', text: 'Same controls' })
      .mockResolvedValueOnce(true)
      .mockImplementationOnce(async () => {
        view.webContents.getURL.mockReturnValue('https://example.com/calendar/october')
        view.webContents.getTitle.mockReturnValue('October')
        return true
      })
      .mockResolvedValueOnce({ title: 'October', text: 'Same controls' })
      .mockResolvedValueOnce({ title: 'October', text: 'Same controls' })
      .mockResolvedValueOnce(true)

    await browser.inspectInteractive('tab-1')
    const pending = browser.selectCurrentPage('tab-1', 'target_4', '10')
    await vi.advanceTimersByTimeAsync(400)
    await expect(pending).resolves.toEqual({
      action: 'selected',
      url: 'https://example.com/calendar/october',
      title: 'October',
      page: {
        title: 'October',
        url: 'https://example.com/calendar/october',
        text: 'Same controls'
      }
    })
    vi.useRealTimers()
  })

  it('rejects non-select targets, unknown options, and disabled options', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_1',
            name: 'Email',
            role: 'email',
            tag: 'input',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce(true)
      .mockRejectedValueOnce(new Error('target is not selectable'))
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_2',
            name: 'Country',
            role: 'combobox',
            tag: 'select',
            disabled: false,
            options: [
              { value: 'au', label: 'Australia', disabled: false },
              { value: 'us', label: 'United States', disabled: true }
            ]
          }
        ]
      })
      .mockResolvedValueOnce(true)
      .mockRejectedValueOnce(new Error('option was not found'))
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce(true)
      .mockRejectedValueOnce(new Error('option is disabled'))
      .mockResolvedValueOnce(true)

    await browser.inspectInteractive('tab-1')
    const notSelectable = browser.selectCurrentPage('tab-1', 'target_1', 'au')
    const notSelectableAssertion = expect(notSelectable).rejects.toThrow('target is not selectable')
    await vi.advanceTimersByTimeAsync(150)
    await notSelectableAssertion

    await browser.inspectInteractive('tab-1')
    const missingOption = browser.selectCurrentPage('tab-1', 'target_2', 'xx')
    const missingOptionAssertion = expect(missingOption).rejects.toThrow('option was not found')
    await vi.advanceTimersByTimeAsync(150)
    await missingOptionAssertion

    const disabledOption = browser.selectCurrentPage('tab-1', 'target_2', 'us')
    const disabledOptionAssertion = expect(disabledOption).rejects.toThrow('option is disabled')
    await vi.advanceTimersByTimeAsync(150)
    await disabledOptionAssertion

    await expect(browser.selectCurrentPage('tab-1', 'target_99', 'au')).rejects.toThrow(
      'page changed; inspect interactive elements again'
    )
    vi.useRealTimers()
  })

  it('submits an inspected native submit button with a real mouse path', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://example.com/form')
    view.webContents.getTitle.mockReturnValue('Form')
    view.webContents.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_3',
            name: 'Send',
            role: 'button',
            tag: 'button',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce({ title: 'Form', text: 'Ready to send' })
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce({ x: 40, y: 60, activation: 'mouse' })
      .mockResolvedValueOnce({ x: 40, y: 60 })
      .mockResolvedValueOnce({ title: 'Thanks', text: 'Message sent' })
      .mockResolvedValueOnce({ title: 'Thanks', text: 'Message sent' })
      .mockResolvedValueOnce(true)

    await browser.inspectInteractive('tab-1')
    const pending = browser.submitCurrentPage('tab-1', 'target_3')
    await vi.advanceTimersByTimeAsync(400)
    await expect(pending).resolves.toEqual({
      action: 'submitted',
      url: 'https://example.com/form',
      title: 'Form',
      page: {
        title: 'Thanks',
        url: 'https://example.com/form',
        text: 'Message sent'
      }
    })

    const scripts = view.webContents.executeJavaScript.mock.calls.map((call) => String(call[0]))
    expect(scripts[2]).toContain('target is not submittable')
    expect(scripts[2]).toContain('HTMLButtonElement')
    expect(scripts[2]).toContain('HTMLInputElement')
    expect(scripts[2]).toContain('form == null')
    expect(scripts[2]).toContain("type === 'submit'")
    expect(scripts[2]).toContain("type === 'image'")
    expect(scripts[2]).not.toContain('form.submit')
    expect(scripts[2]).not.toContain('requestSubmit')
    expect(scripts[3]).toContain('asagent-agent-pointer')
    expect(scripts[3]).toContain('semanticActivation = false')
    expect(scripts[7]).toContain('asagent-agent-pointer')
    expect(view.webContents.sendInputEvent.mock.calls.map((call) => call[0])).toEqual([
      { type: 'mouseMove', x: 40, y: 60 },
      { type: 'mouseDown', x: 40, y: 60, button: 'left', clickCount: 1 },
      { type: 'mouseUp', x: 40, y: 60, button: 'left', clickCount: 1 }
    ])
    vi.useRealTimers()
  })

  it('returns a page snapshot when submit changes the URL but not the text', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://example.com/form')
    view.webContents.getTitle.mockReturnValue('Form')
    view.webContents.sendInputEvent.mockImplementation(() => {
      view.webContents.getURL.mockReturnValue('https://example.com/thanks')
      view.webContents.getTitle.mockReturnValue('Thanks')
    })
    view.webContents.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_1',
            name: 'Create event',
            role: 'button',
            tag: 'button',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce({ title: 'Form', text: 'Event details' })
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce({ x: 22, y: 28, activation: 'mouse' })
      .mockResolvedValueOnce({ x: 22, y: 28 })
      .mockResolvedValueOnce({ title: 'Form', text: 'Event details' })
      .mockResolvedValueOnce({ title: 'Form', text: 'Event details' })
      .mockResolvedValueOnce(true)

    await browser.inspectInteractive('tab-1')
    const pending = browser.submitCurrentPage('tab-1', 'target_1')
    await vi.advanceTimersByTimeAsync(400)
    await expect(pending).resolves.toEqual({
      action: 'submitted',
      url: 'https://example.com/thanks',
      title: 'Thanks',
      page: {
        title: 'Form',
        url: 'https://example.com/thanks',
        text: 'Event details'
      }
    })
    vi.useRealTimers()
  })

  it('still returns submitted when the page cannot be read after submit', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://example.com/form')
    view.webContents.getTitle.mockReturnValue('Form')
    view.webContents.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_1',
            name: 'Send',
            role: 'button',
            tag: 'button',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce({ title: 'Form', text: 'Ready' })
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce({ x: 10, y: 12, activation: 'mouse' })
      .mockResolvedValueOnce({ x: 10, y: 12 })
      .mockRejectedValueOnce(new Error('page gone'))
      .mockResolvedValueOnce(true)

    await browser.inspectInteractive('tab-1')
    const pending = browser.submitCurrentPage('tab-1', 'target_1')
    await vi.advanceTimersByTimeAsync(150)
    await expect(pending).resolves.toEqual({
      action: 'submitted',
      url: 'https://example.com/form',
      title: 'Form'
    })
    vi.useRealTimers()
  })

  it('submits iframe native submit controls only inside the child frame', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://example.com/outer')
    view.webContents.getTitle.mockReturnValue('Outer')

    const child = createFakeFrame({ url: 'https://forms.example/app' })
    Object.defineProperty(view.webContents.mainFrame, 'frames', {
      value: [child],
      configurable: true
    })

    view.webContents.mainFrame.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_1',
            name: 'Outer',
            role: 'button',
            tag: 'button',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce({ title: '', text: '' })
    child.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_2',
            name: 'Submit',
            role: 'button',
            tag: 'button',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce({ title: '', text: '' })
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce({ x: 12, y: 18, activation: 'mouse' })
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce(true)

    await browser.inspectInteractive('tab-1')
    const pending = browser.submitCurrentPage('tab-1', 'target_2')
    await vi.advanceTimersByTimeAsync(150)
    await expect(pending).resolves.toEqual({
      action: 'submitted',
      url: 'https://example.com/outer',
      title: 'Outer'
    })

    expect(view.webContents.sendInputEvent).not.toHaveBeenCalled()
    const childScripts = child.executeJavaScript.mock.calls.map((call) => String(call[0]))
    expect(childScripts[2]).toContain('target is not submittable')
    expect(childScripts[3]).toContain('asagent-agent-pointer')
    expect(childScripts[4]).toContain('target.click()')
    expect(childScripts[5]).toContain('asagent-agent-pointer')
    vi.useRealTimers()
  })

  it('rejects non-submittable targets and stale inspect snapshots', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_1',
            name: 'Cancel',
            role: 'button',
            tag: 'button',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce({ title: 'Form', text: 'Ready' })
      .mockRejectedValueOnce(new Error('target is not submittable'))
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_2',
            name: 'Custom',
            role: 'button',
            tag: 'div',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce({ title: 'Form', text: 'Ready' })
      .mockRejectedValueOnce(new Error('target is not submittable'))
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_3',
            name: 'Send',
            role: 'button',
            tag: 'button',
            disabled: true
          }
        ]
      })
      .mockResolvedValueOnce({ title: 'Form', text: 'Ready' })
      .mockRejectedValueOnce(new Error('target is not submittable'))
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_4',
            name: 'Toggle',
            role: 'button',
            tag: 'button',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce({ title: 'Form', text: 'Ready' })
      .mockRejectedValueOnce(new Error('target is not submittable'))
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_5',
            name: 'Orphan',
            role: 'button',
            tag: 'button',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce({ title: 'Form', text: 'Ready' })
      .mockRejectedValueOnce(new Error('target is not submittable'))

    await browser.inspectInteractive('tab-1')
    await expect(browser.submitCurrentPage('tab-1', 'target_1')).rejects.toThrow(
      'target is not submittable'
    )

    await browser.inspectInteractive('tab-1')
    await expect(browser.submitCurrentPage('tab-1', 'target_2')).rejects.toThrow(
      'target is not submittable'
    )

    await browser.inspectInteractive('tab-1')
    await expect(browser.submitCurrentPage('tab-1', 'target_3')).rejects.toThrow(
      'target is not submittable'
    )

    await browser.inspectInteractive('tab-1')
    await expect(browser.submitCurrentPage('tab-1', 'target_4')).rejects.toThrow(
      'target is not submittable'
    )

    await browser.inspectInteractive('tab-1')
    await expect(browser.submitCurrentPage('tab-1', 'target_5')).rejects.toThrow(
      'target is not submittable'
    )

    await expect(browser.submitCurrentPage('tab-1', 'target_99')).rejects.toThrow(
      'page changed; inspect interactive elements again'
    )
    vi.useRealTimers()
  })

  it('invalidates submit targets after navigation', async () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView> & {
      emit(event: string, navigationEvent: BrowserNavigationEvent, url?: string): void
    }

    view.webContents.executeJavaScript.mockResolvedValueOnce({
      elements: [
        {
          target_id: 'target_1',
          name: 'Send',
          role: 'button',
          tag: 'button',
          disabled: false
        }
      ]
    })

    await browser.inspectInteractive('tab-1')
    view.emit('did-navigate', { preventDefault: () => undefined }, 'https://example.com/next')

    await expect(browser.submitCurrentPage('tab-1', 'target_1')).rejects.toThrow(
      'page changed; inspect interactive elements again'
    )
  })

  it('waits briefly for changed page content after a click', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_1',
            name: 'Run',
            role: 'button',
            tag: 'button',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce({ title: 'Page', text: 'Ready' })
      .mockResolvedValueOnce({ x: 10, y: 12, activation: 'mouse' })
      .mockResolvedValueOnce({ x: 10, y: 12 })
      .mockResolvedValueOnce({ title: 'Page', text: 'Results are ready' })
      .mockResolvedValueOnce({ title: 'Page', text: 'Results are ready' })
      .mockResolvedValueOnce(true)

    await browser.inspectInteractive('tab-1')
    const pending = browser.clickCurrentPage('tab-1', 'target_1')
    await vi.advanceTimersByTimeAsync(400)
    await expect(pending).resolves.toEqual({
      action: 'clicked',
      url: '',
      title: 'New Tab',
      page: {
        title: 'Page',
        url: '',
        text: 'Results are ready'
      }
    })

    view.webContents.executeJavaScript.mockResolvedValue({
      title: 'Page',
      text: 'Final results'
    })
    const waitPending = browser.waitForCurrentPage('tab-1', 15)
    await vi.advanceTimersByTimeAsync(500)
    await expect(waitPending).resolves.toEqual({
      changed: true,
      page: { title: 'Page', url: '', text: 'Final results' }
    })
    vi.useRealTimers()
  })

  it('rejects clicks for non-visible tabs and removes the pointer after failures', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_1',
            name: 'Go',
            role: 'button',
            tag: 'button',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce({ title: '', text: '' })
      .mockResolvedValueOnce({ x: 10, y: 12, activation: 'mouse' })
      .mockRejectedValueOnce(new Error('target is obscured'))
      .mockResolvedValueOnce(true)

    await browser.inspectInteractive('tab-1')
    const pending = browser.clickCurrentPage('tab-1', 'target_1')
    const assertion = expect(pending).rejects.toThrow('obscured')
    await vi.advanceTimersByTimeAsync(150)
    await assertion
    expect(view.webContents.executeJavaScript).toHaveBeenCalledTimes(5)
    expect(view.webContents.sendInputEvent).not.toHaveBeenCalled()

    await expect(browser.clickCurrentPage('tab-missing', 'target_1')).rejects.toThrow(
      'current browser tab is not visible'
    )
    await expect(browser.clickCurrentPage('tab-1', 'target_99')).rejects.toThrow(
      'page changed; inspect interactive elements again'
    )
    vi.useRealTimers()
  })

  it('merges interactive elements from the main frame and nested iframes', async () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://example.com/outer')

    const nested = createFakeFrame({ url: 'https://example.com/nested' })
    const child = createFakeFrame({
      url: 'https://gradio.example/app',
      frames: [nested]
    })
    Object.defineProperty(view.webContents.mainFrame, 'frames', {
      value: [child],
      configurable: true
    })

    view.webContents.mainFrame.executeJavaScript.mockResolvedValueOnce({
      elements: [
        {
          target_id: 'target_1',
          name: 'Outer',
          role: 'button',
          tag: 'button',
          disabled: false
        }
      ]
    })
    child.executeJavaScript.mockResolvedValueOnce({
      elements: [
        {
          target_id: 'target_2',
          name: 'Use sample file',
          role: 'button',
          tag: 'button',
          disabled: false
        }
      ]
    })
    nested.executeJavaScript.mockResolvedValueOnce({
      elements: [
        {
          target_id: 'target_3',
          name: 'Run',
          role: 'button',
          tag: 'button',
          disabled: false
        }
      ]
    })

    await expect(browser.inspectInteractive('tab-1')).resolves.toEqual({
      url: 'https://example.com/outer',
      elements: [
        {
          target_id: 'target_1',
          name: 'Outer',
          role: 'button',
          tag: 'button',
          disabled: false
        },
        {
          target_id: 'target_2',
          name: 'Use sample file',
          role: 'button',
          tag: 'button',
          disabled: false
        },
        {
          target_id: 'target_3',
          name: 'Run',
          role: 'button',
          tag: 'button',
          disabled: false
        }
      ]
    })

    expect(view.webContents.mainFrame.executeJavaScript).toHaveBeenCalledTimes(1)
    expect(child.executeJavaScript).toHaveBeenCalledTimes(1)
    expect(nested.executeJavaScript).toHaveBeenCalledTimes(1)
    expect(String(view.webContents.mainFrame.executeJavaScript.mock.calls[0]?.[0])).toContain(
      'FIRST_TARGET_NUMBER = 1'
    )
    expect(String(child.executeJavaScript.mock.calls[0]?.[0])).toContain('FIRST_TARGET_NUMBER = 2')
    expect(String(nested.executeJavaScript.mock.calls[0]?.[0])).toContain('FIRST_TARGET_NUMBER = 3')
  })

  it('prioritizes semantic controls and excludes iframe shells from inspection', async () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.mainFrame.executeJavaScript.mockResolvedValueOnce({ elements: [] })

    await browser.inspectInteractive('tab-1')

    const script = String(view.webContents.mainFrame.executeJavaScript.mock.calls[0]?.[0])
    expect(script).toContain("tag === 'html' || tag === 'body' || tag === 'iframe'")
    expect(script).toContain('function isSemanticallyVisible(el)')
    expect(script).toContain('function isPointerVisible(el)')
    expect(script).toContain("if (tag === 'label') {\n      return elementName(el) !== '';")
    expect(script).toContain("'checkbox', 'radio', 'switch'")
    expect(script).toContain('candidates.sort((left, right) => priority(left) - priority(right))')
  })

  it('clicks iframe targets only inside the child frame', async () => {
    vi.useFakeTimers()
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
    view.webContents.getURL.mockReturnValue('https://example.com/outer')
    view.webContents.getTitle.mockReturnValue('Outer')

    const child = createFakeFrame({ url: 'https://gradio.example/app' })
    Object.defineProperty(view.webContents.mainFrame, 'frames', {
      value: [child],
      configurable: true
    })

    view.webContents.mainFrame.executeJavaScript.mockResolvedValueOnce({
      elements: [
        {
          target_id: 'target_1',
          name: 'Outer',
          role: 'button',
          tag: 'button',
          disabled: false
        }
      ]
    })
    view.webContents.mainFrame.executeJavaScript.mockResolvedValueOnce({ title: '', text: '' })
    child.executeJavaScript
      .mockResolvedValueOnce({
        elements: [
          {
            target_id: 'target_2',
            name: 'Use sample file',
            role: 'button',
            tag: 'button',
            disabled: false
          }
        ]
      })
      .mockResolvedValueOnce({ title: '', text: '' })
      .mockResolvedValueOnce({ x: 12, y: 18, activation: 'mouse' })
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce(true)

    await browser.inspectInteractive('tab-1')
    const pending = browser.clickCurrentPage('tab-1', 'target_2')
    await vi.advanceTimersByTimeAsync(150)
    await expect(pending).resolves.toEqual({
      action: 'clicked',
      url: 'https://example.com/outer',
      title: 'Outer'
    })

    expect(view.webContents.sendInputEvent).not.toHaveBeenCalled()
    expect(view.webContents.mainFrame.executeJavaScript).toHaveBeenCalledTimes(2)
    expect(child.executeJavaScript.mock.calls.map((call) => String(call[0]))).toEqual(
      expect.arrayContaining([
        expect.stringContaining('data-asagent-target-id'),
        expect.stringContaining('target.click()'),
        expect.stringContaining('asagent-agent-pointer')
      ])
    )
    const childScripts = child.executeJavaScript.mock.calls.map((call) => String(call[0]))
    expect(childScripts[2]).toContain('asagent-agent-pointer')
    expect(childScripts[3]).toContain('target.click()')
    vi.useRealTimers()
  })

  it('invalidates interaction targets when a child frame navigates', async () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView> & {
      emit(event: string, navigationEvent: BrowserNavigationEvent, url?: string): void
    }

    const child = createFakeFrame({ url: 'https://gradio.example/app' })
    Object.defineProperty(view.webContents.mainFrame, 'frames', {
      value: [child],
      configurable: true
    })

    view.webContents.mainFrame.executeJavaScript.mockResolvedValueOnce({
      elements: [
        {
          target_id: 'target_1',
          name: 'Outer',
          role: 'button',
          tag: 'button',
          disabled: false
        }
      ]
    })
    child.executeJavaScript.mockResolvedValueOnce({
      elements: [
        {
          target_id: 'target_2',
          name: 'Use sample file',
          role: 'button',
          tag: 'button',
          disabled: false
        }
      ]
    })

    await browser.inspectInteractive('tab-1')
    view.emit(
      'did-frame-navigate',
      { preventDefault: () => undefined },
      'https://gradio.example/reloaded'
    )

    await expect(browser.clickCurrentPage('tab-1', 'target_2')).rejects.toThrow(
      'page changed; inspect interactive elements again'
    )
    expect(child.executeJavaScript).toHaveBeenCalledTimes(1)
  })

  describe('readCurrentPdf', () => {
    it('rejects when the tab is missing or not visible', async () => {
      const { browser } = createBrowser()
      await expect(browser.readCurrentPdf('tab-missing')).rejects.toThrow(
        'current browser tab is not visible'
      )
    })

    it('rejects when current URL is not an HTTP or HTTPS document', async () => {
      const { browser, createView } = createBrowser()
      const window = createFakeWindow()
      browser.show(window, bounds, 'tab-1')
      const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
      view.webContents.getURL.mockReturnValue('about:blank')

      await expect(browser.readCurrentPdf('tab-1')).rejects.toThrow(
        'current page is not an HTTP or HTTPS PDF document'
      )
    })

    it('successfully reads PDF bytes and generates stable documentId for identical URL', async () => {
      const pdfBytes = Buffer.from('%PDF-1.4 sample PDF body %%EOF')
      const fetchPdf = vi.fn(async () => pdfBytes)

      const { browser, createView } = createBrowser({ fetchPdf })
      const window = createFakeWindow()
      browser.show(window, bounds, 'tab-1')
      const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
      view.webContents.getURL.mockReturnValue('https://example.com/document.pdf')

      const result1 = await browser.readCurrentPdf('tab-1')
      expect(result1.data).toEqual(pdfBytes)
      expect(result1.documentId).toMatch(/^doc-[0-9a-f]{32}$/)

      // Second read returns the exact same documentId token
      const result2 = await browser.readCurrentPdf('tab-1')
      expect(result2.documentId).toBe(result1.documentId)
      expect(fetchPdf).toHaveBeenCalledTimes(2)
    })

    it('invalidates documentId token when tab navigates to a different URL', async () => {
      const pdfBytes = Buffer.from('%PDF-1.4 new PDF %%EOF')
      const fetchPdf = vi.fn(async () => pdfBytes)

      const { browser, createView } = createBrowser({ fetchPdf })
      const window = createFakeWindow()
      browser.show(window, bounds, 'tab-1')
      const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
      view.webContents.getURL.mockReturnValue('https://example.com/doc1.pdf')

      const result1 = await browser.readCurrentPdf('tab-1')
      expect(result1.documentId).toMatch(/^doc-[0-9a-f]{32}$/)

      // Tab navigates to doc2.pdf
      view.webContents.getURL.mockReturnValue('https://example.com/doc2.pdf')
      view.emit('did-navigate', { preventDefault: () => undefined }, 'https://example.com/doc2.pdf')

      const result2 = await browser.readCurrentPdf('tab-1')
      expect(result2.documentId).toMatch(/^doc-[0-9a-f]{32}$/)
      expect(result2.documentId).not.toBe(result1.documentId)
    })

    it('rejects when PDF size exceeds 20 MiB limit', async () => {
      const fetchPdf = vi.fn(async () => {
        throw new Error('PDF exceeds the 20 MiB limit')
      })

      const { browser, createView } = createBrowser({ fetchPdf })
      const window = createFakeWindow()
      browser.show(window, bounds, 'tab-1')
      const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
      view.webContents.getURL.mockReturnValue('https://example.com/giant.pdf')

      await expect(browser.readCurrentPdf('tab-1')).rejects.toThrow('PDF exceeds the 20 MiB limit')
    })

    it('rejects when document does not contain a valid %PDF- magic header', async () => {
      const invalidBytes = Buffer.from('<html><body>Not a PDF</body></html>')
      const fetchPdf = vi.fn(async () => invalidBytes)

      const { browser, createView } = createBrowser({ fetchPdf })
      const window = createFakeWindow()
      browser.show(window, bounds, 'tab-1')
      const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
      view.webContents.getURL.mockReturnValue('https://example.com/fake.pdf')

      await expect(browser.readCurrentPdf('tab-1')).rejects.toThrow(
        'document does not have a valid PDF header'
      )
    })

    it('rejects when fetch is aborted or times out', async () => {
      const fetchPdf = vi.fn(async (_url, _session, signal: AbortSignal) => {
        return new Promise<Buffer>((_, reject) => {
          signal.addEventListener('abort', () => {
            reject(new Error('PDF fetch was cancelled'))
          })
        })
      })

      const { browser, createView } = createBrowser({ fetchPdf })
      const window = createFakeWindow()
      browser.show(window, bounds, 'tab-1')
      const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
      view.webContents.getURL.mockReturnValue('https://example.com/pending.pdf')

      const pending = browser.readCurrentPdf('tab-1')
      // Simulate navigation during fetch
      view.emit('will-navigate', { preventDefault: () => undefined }, 'https://example.com/other')

      await expect(pending).rejects.toThrow('PDF fetch was cancelled')
    })

    it('validates identity without fetching and rejects a reload of the same URL', async () => {
      const fetchPdf = vi.fn(async () => Buffer.from('%PDF-1.4 fixture'))
      const { browser, createView } = createBrowser({ fetchPdf })
      browser.show(createFakeWindow(), bounds, 'tab-1')
      const view = createView.mock.results[0]!.value as FakePageView
      view.webContents.getURL.mockReturnValue('https://example.com/doc.pdf')
      const doc = await browser.readCurrentPdf('tab-1')
      browser.validateCurrentPdf('tab-1', doc.documentId)
      expect(fetchPdf).toHaveBeenCalledTimes(1)
      void browser.control('tab-1', 'reload')
      expect(() => browser.validateCurrentPdf('tab-1', doc.documentId)).toThrow(
        'PDF document changed'
      )
    })

    it('does not accumulate WebContents listeners on success or failure', async () => {
      const fetchPdf = vi.fn(async () => Buffer.from('%PDF-1.4 fixture'))
      const { browser, createView } = createBrowser({ fetchPdf })
      browser.show(createFakeWindow(), bounds, 'tab-1')
      const view = createView.mock.results[0]!.value as FakePageView
      view.webContents.getURL.mockReturnValue('https://example.com/doc.pdf')
      const events = ['will-navigate', 'will-redirect', 'did-start-navigation', 'destroyed']
      const counts = events.map((event) => view.listenerCount(event))
      for (let i = 0; i < 12; i++) {
        await browser.readCurrentPdf('tab-1')
        fetchPdf.mockRejectedValueOnce(new Error('failed to fetch PDF document'))
        await expect(browser.readCurrentPdf('tab-1')).rejects.toThrow(
          'failed to fetch PDF document'
        )
      }
      expect(events.map((event) => view.listenerCount(event))).toEqual(counts)
    })

    it.each([
      'close',
      'hide',
      'switch',
      'reload',
      'navigate',
      'agent-navigation',
      'programmatic-navigation',
      'destroy',
      'dispose',
      'disconnect'
    ])('cancels an in-flight PDF read on %s', async (action) => {
      let fetchSignal: AbortSignal | undefined
      const fetchPdf = vi.fn(async (_url, _session, signal: AbortSignal) => {
        fetchSignal = signal
        return new Promise<Buffer>((_, reject) => {
          signal.addEventListener('abort', () => reject(new Error('PDF fetch was cancelled')), {
            once: true
          })
        })
      })
      const { browser, createView } = createBrowser({ fetchPdf })
      const window = createFakeWindow()
      browser.show(window, bounds, 'tab-1')
      const view = createView.mock.results[0]!.value as FakePageView
      view.webContents.getURL.mockReturnValue('https://example.com/doc.pdf')
      const controller = new AbortController()
      const removeListener = vi.spyOn(controller.signal, 'removeEventListener')
      const pending = browser.readCurrentPdf('tab-1', controller.signal)
      const rejected = expect(pending).rejects.toThrow('PDF fetch was cancelled')
      switch (action) {
        case 'close':
          browser.closeTab('tab-1')
          break
        case 'hide':
          browser.hide()
          break
        case 'switch':
          browser.show(window, bounds, 'tab-2')
          break
        case 'reload':
          await browser.control('tab-1', 'reload')
          break
        case 'navigate':
          await browser.navigate('tab-1', 'https://example.com/other')
          break
        case 'agent-navigation':
          await browser.navigateCurrentPage('tab-1', 'https://example.com/other')
          break
        case 'programmatic-navigation':
          view.emit('did-start-navigation', { preventDefault: vi.fn(), isMainFrame: true })
          break
        case 'destroy':
          view.webContents.close()
          break
        case 'dispose':
          browser.dispose()
          break
        case 'disconnect':
          controller.abort()
          break
      }
      await rejected
      expect(fetchSignal?.aborted).toBe(true)
      expect(removeListener).toHaveBeenCalledWith('abort', expect.any(Function))
    })

    it('never returns bytes after the tab closes even if the fetch ignores cancellation', async () => {
      let finish!: (data: Buffer) => void
      const fetchPdf = vi.fn(
        () =>
          new Promise<Buffer>((resolve) => {
            finish = resolve
          })
      )
      const { browser, createView } = createBrowser({ fetchPdf })
      browser.show(createFakeWindow(), bounds, 'tab-1')
      const view = createView.mock.results[0]!.value as FakePageView
      view.webContents.getURL.mockReturnValue('https://example.com/doc.pdf')
      const pending = browser.readCurrentPdf('tab-1')
      const rejected = expect(pending).rejects.toThrow('PDF fetch was cancelled')
      browser.closeTab('tab-1')
      finish(Buffer.from('%PDF-1.4 fixture'))
      await rejected
    })

    it('enforces the network deadline and removes the external abort listener', async () => {
      vi.useFakeTimers()
      try {
        const fetchPdf = vi.fn(
          async (_url, _session, signal: AbortSignal) =>
            new Promise<Buffer>((_, reject) => {
              signal.addEventListener('abort', () => reject(signal.reason), { once: true })
            })
        )
        const { browser, createView } = createBrowser({ fetchPdf })
        browser.show(createFakeWindow(), bounds, 'tab-1')
        const view = createView.mock.results[0]!.value as FakePageView
        view.webContents.getURL.mockReturnValue('https://example.com/doc.pdf')
        const controller = new AbortController()
        const removeListener = vi.spyOn(controller.signal, 'removeEventListener')
        const rejected = expect(browser.readCurrentPdf('tab-1', controller.signal)).rejects.toThrow(
          'PDF fetch timed out'
        )
        await vi.advanceTimersByTimeAsync(15000)
        await rejected
        expect(removeListener).toHaveBeenCalledWith('abort', expect.any(Function))
        expect(vi.getTimerCount()).toBe(0)
      } finally {
        vi.useRealTimers()
      }
    })

    describe('defaultFetchPdf network pipeline', () => {
      it.each(['redirect', 'html', 'http-error'])(
        'cancels unused response bodies on %s',
        async (kind) => {
          const cancel = vi.fn()
          const body = new ReadableStream<Uint8Array>({ cancel })
          const response =
            kind === 'redirect'
              ? new Response(body, {
                  status: 302,
                  headers: { location: 'https://example.com/final.pdf' }
                })
              : new Response(body, {
                  status: kind === 'http-error' ? 500 : 200,
                  headers: { 'content-type': 'text/html' }
                })
          const sessionFetch = vi
            .fn()
            .mockResolvedValueOnce(response)
            .mockResolvedValue(new Response(Buffer.from('%PDF-1.4 fixture')))
          const session = { fetch: sessionFetch } as unknown as Session
          const { browser, createView } = createBrowser({ session })
          browser.show(createFakeWindow(), bounds, 'tab-1')
          const view = createView.mock.results[0]!.value as FakePageView
          view.webContents.getURL.mockReturnValue('https://example.com/doc.pdf')
          if (kind === 'redirect') await browser.readCurrentPdf('tab-1')
          else await expect(browser.readCurrentPdf('tab-1')).rejects.toThrow()
          expect(cancel).toHaveBeenCalledTimes(1)
        }
      )

      it('follows valid HTTPS redirects up to target PDF', async () => {
        const pdfBytes = Buffer.from('%PDF-1.4 redirected content %%EOF')
        const sessionFetch = vi.fn(async (url: string) => {
          if (url === 'https://example.com/initial.pdf') {
            return new Response(null, {
              status: 302,
              headers: { location: 'https://example.com/target.pdf' }
            })
          }
          return new Response(pdfBytes, {
            status: 200,
            headers: { 'content-type': 'application/pdf' }
          })
        })

        const session = { id: 'test-session', fetch: sessionFetch } as unknown as Session
        const { browser, createView } = createBrowser({ session })
        const window = createFakeWindow()
        browser.show(window, bounds, 'tab-1')
        const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
        view.webContents.getURL.mockReturnValue('https://example.com/initial.pdf')

        const result = await browser.readCurrentPdf('tab-1')
        expect(result.data).toEqual(pdfBytes)
        expect(sessionFetch).toHaveBeenCalledTimes(2)
      })

      it('blocks redirects to file:// protocol', async () => {
        const sessionFetch = vi.fn(async () => {
          return new Response(null, {
            status: 302,
            headers: { location: 'file:///etc/passwd' }
          })
        })

        const session = { id: 'test-session', fetch: sessionFetch } as unknown as Session
        const { browser, createView } = createBrowser({ session })
        const window = createFakeWindow()
        browser.show(window, bounds, 'tab-1')
        const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
        view.webContents.getURL.mockReturnValue('https://example.com/doc.pdf')

        await expect(browser.readCurrentPdf('tab-1')).rejects.toThrow(
          'redirect to non-http(s) protocol is forbidden'
        )
      })

      it('rejects responses with text/html content-type', async () => {
        const sessionFetch = vi.fn(async () => {
          return new Response('<html><body>Login Page</body></html>', {
            status: 200,
            headers: { 'content-type': 'text/html; charset=utf-8' }
          })
        })

        const session = { id: 'test-session', fetch: sessionFetch } as unknown as Session
        const { browser, createView } = createBrowser({ session })
        const window = createFakeWindow()
        browser.show(window, bounds, 'tab-1')
        const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
        view.webContents.getURL.mockReturnValue('https://example.com/protected.pdf')

        await expect(browser.readCurrentPdf('tab-1')).rejects.toThrow(
          'current page is not an HTTP or HTTPS PDF document'
        )
      })

      it('aborts and rejects when stream exceeds 20 MiB limit', async () => {
        const chunk = new Uint8Array(5 * 1024 * 1024) // 5 MiB chunk
        let chunksSent = 0
        const stream = new ReadableStream<Uint8Array>({
          pull(controller) {
            if (chunksSent < 5) {
              chunksSent++
              controller.enqueue(chunk)
            } else {
              controller.close()
            }
          }
        })

        const sessionFetch = vi.fn(async () => {
          return new Response(stream, {
            status: 200,
            headers: { 'content-type': 'application/pdf' }
          })
        })

        const session = { id: 'test-session', fetch: sessionFetch } as unknown as Session
        const { browser, createView } = createBrowser({ session })
        const window = createFakeWindow()
        browser.show(window, bounds, 'tab-1')
        const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>
        view.webContents.getURL.mockReturnValue('https://example.com/stream-huge.pdf')

        await expect(browser.readCurrentPdf('tab-1')).rejects.toThrow(
          'PDF exceeds the 20 MiB limit'
        )
      })
    })
  })
})

describe('native editor input', () => {
  const bounds = { x: 0, y: 0, width: 800, height: 600 }
  const url = 'https://docs.google.com/document/d/test/edit'
  function setup(): { browser: VisibleBrowser; view: FakePageView; host: BrowserHostWindow } {
    const { browser, createView } = createBrowser()
    const host = createFakeWindow()
    browser.show(host, bounds, 'editor')
    const view = createView.mock.results[0].value as FakePageView
    view.webContents.getURL.mockReturnValue(url)
    view.webContents.executeJavaScript.mockResolvedValue(true)
    return { browser, view, host }
  }
  it('inserts unicode through native input without a DOM replacement or save claim', async () => {
    const { browser, view } = setup()
    const result = await browser.inputCurrentPage('editor', {
      url,
      kind: 'text',
      value: '你好\nSheet'
    })
    expect(view.webContents.insertText).toHaveBeenCalledWith('你好\nSheet')
    expect(view.webContents.sendInputEvent).not.toHaveBeenCalled()
    expect(result).toMatchObject({ action: 'input_sent', verified: false })
  })
  it('sends Sheets text through native character events, including Unicode', async () => {
    const { browser, view } = setup()
    const sheetUrl = 'https://docs.google.com/spreadsheets/d/test/edit'
    view.webContents.getURL.mockReturnValue(sheetUrl)
    await browser.inputCurrentPage('editor', { url: sheetUrl, kind: 'text', value: '订单日期😀' })
    expect(view.webContents.insertText).not.toHaveBeenCalled()
    expect(view.webContents.sendInputEvent.mock.calls).toEqual(
      Array.from('订单日期😀', (keyCode) => [{ type: 'char', keyCode }])
    )
  })
  it('finds an editor inside an iframe without changing its selection', async () => {
    const { browser, view } = setup()
    view.webContents.executeJavaScript.mockResolvedValue(false)
    const child = createFakeFrame({ executeJavaScript: vi.fn(async () => true) })
    Object.assign(view.webContents.mainFrame, { frames: [child] })
    await browser.inputCurrentPage('editor', { url, kind: 'text', value: 'cell value' })
    expect(child.executeJavaScript).toHaveBeenCalledWith(BROWSER_EDITOR_OBSERVATION_SCRIPT)
    expect(view.webContents.insertText).toHaveBeenCalledWith('cell value')
  })

  it('returns focus changes and unchanged text without claiming persistence', async () => {
    const { browser, view } = setup()
    let observed = 0
    view.webContents.executeJavaScript.mockImplementation(async (script: string) => {
      if (script !== BROWSER_EDITOR_OBSERVATION_SCRIPT) return true
      observed += 1
      return {
        focused: { name: observed === 1 ? 'Name box' : 'Formula bar', text: 'A1' },
        controls: [],
        statuses: []
      }
    })
    const result = await browser.inputCurrentPage('editor', { url, kind: 'key', value: 'Enter' })
    expect(result.observation).toMatchObject({ changed: true, status: 'observed' })
    expect(result.observation.after?.frames[0].state).toMatchObject({
      focused: { name: 'Formula bar' }
    })
    expect(result.verified).toBe(false)
  })
  it('reports unchanged observations explicitly', async () => {
    const { browser, view } = setup()
    view.webContents.executeJavaScript.mockImplementation(async (script: string) =>
      script === BROWSER_EDITOR_OBSERVATION_SCRIPT
        ? { focused: { name: 'Name box' }, controls: [], statuses: [] }
        : true
    )
    const result = await browser.inputCurrentPage('editor', { url, kind: 'key', value: 'Enter' })
    expect(result.observation.changed).toBe(false)
  })
  it('keeps dispatched input successful if observation fails afterward', async () => {
    const { browser, view } = setup()
    let reads = 0
    view.webContents.executeJavaScript.mockImplementation(async (script: string) => {
      if (script !== BROWSER_EDITOR_OBSERVATION_SCRIPT) return true
      if (++reads > 1) throw new Error('frame destroyed')
      return { focused: null, controls: [], statuses: [] }
    })
    const result = await browser.inputCurrentPage('editor', { url, kind: 'text', value: 'once' })
    expect(result.observation).toMatchObject({ after: null, status: 'unavailable', changed: null })
    expect(view.webContents.insertText).toHaveBeenCalledTimes(1)
  })

  it('sends paired editing keys', async () => {
    const { browser, view } = setup()
    await browser.inputCurrentPage('editor', { url, kind: 'key', value: 'Shift+Enter' })
    expect(view.webContents.sendInputEvent.mock.calls).toEqual([
      [{ type: 'keyDown', keyCode: 'Enter', modifiers: ['shift'] }],
      [{ type: 'char', keyCode: '\r', modifiers: ['shift'] }],
      [{ type: 'keyUp', keyCode: 'Enter', modifiers: ['shift'] }]
    ])
  })
  it('rejects missing editable focus and unsupported shortcuts', async () => {
    const { browser, view } = setup()
    view.webContents.executeJavaScript.mockResolvedValue(false)
    await expect(
      browser.inputCurrentPage('editor', { url, kind: 'text', value: 'secret' })
    ).rejects.toThrow('not editable')
    await expect(
      browser.inputCurrentPage('editor', { url, kind: 'key', value: 'Meta+L' })
    ).rejects.toThrow('not editable')
    expect(view.webContents.insertText).not.toHaveBeenCalled()
    expect(view.webContents.sendInputEvent).not.toHaveBeenCalled()
  })
  it('rejects a switched tab or navigated page during focus inspection', async () => {
    const { browser, view } = setup()
    view.webContents.executeJavaScript.mockImplementation(async () => {
      browser.show(createFakeWindow(), bounds, 'other')
      return true
    })
    await expect(
      browser.inputCurrentPage('editor', { url, kind: 'text', value: 'no' })
    ).rejects.toThrow()
    expect(view.webContents.insertText).not.toHaveBeenCalled()
  })
  it('rejects background windows and URL mismatches', async () => {
    const { browser, view, host } = setup()
    await expect(
      browser.inputCurrentPage('editor', { url: url + '?other', kind: 'text', value: 'no' })
    ).rejects.toThrow('page changed')
    vi.spyOn(host, 'isFocused').mockReturnValue(false)
    await expect(
      browser.inputCurrentPage('editor', { url, kind: 'text', value: 'no' })
    ).rejects.toThrow('not visible')
    expect(view.webContents.insertText).not.toHaveBeenCalled()
  })
})

describe('editor observation extraction', () => {
  it('bounds editor text and redacts password values while retaining name-box identity', () => {
    class Element {
      tagName = 'INPUT'
      id = 't-name-box'
      className = ''
      type = 'text'
      value = 'A1:E10'
      selectionStart = 0
      selectionEnd = 6
      disabled = false
      readOnly = false
      getAttribute(name: string): string | null {
        return name === 'aria-label' ? 'Name box' : null
      }
      getClientRects(): number[] {
        return [1]
      }
    }
    class Textarea extends Element {}
    const el = new Element()
    const document = {
      hasFocus: () => true,
      activeElement: el,
      getElementById: () => null,
      querySelectorAll: (selector: string) => (selector.startsWith('input') ? [el] : [])
    }
    const context = {
      document,
      HTMLElement: Element,
      HTMLInputElement: Element,
      HTMLTextAreaElement: Textarea,
      getComputedStyle: () => ({ visibility: 'visible', display: 'block' })
    }
    const observe = (): {
      focused: { name: string; text?: string; redacted: boolean; textTruncated?: boolean }
      controls: unknown[]
    } => runInNewContext(BROWSER_EDITOR_OBSERVATION_SCRIPT, context)
    expect(observe().focused).toMatchObject({
      name: 'Name box',
      text: 'A1:E10',
      selection: { start: 0, end: 6 }
    })
    el.value = 'x'.repeat(700)
    expect(observe().focused.text).toHaveLength(500)
    expect(observe().focused.textTruncated).toBe(true)
    el.type = 'password'
    const state = observe()
    expect(state.focused.redacted).toBe(true)
    expect(state.focused.text).toBeUndefined()
    expect(state.controls).toEqual([])
  })
})
