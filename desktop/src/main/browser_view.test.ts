import type { Session, WebContentsViewConstructorOptions } from 'electron'
import { describe, expect, it, vi } from 'vitest'

import {
  MAX_BROWSER_TABS,
  parseBrowserControlAction,
  parseBrowserTabId,
  parseBrowserViewBounds,
  VisibleBrowser,
  type BrowserHostWindow,
  type BrowserNavigationEvent,
  type BrowserPageView,
  type BrowserTabState
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
  setWindowOpenHandler: ReturnType<typeof vi.fn>
  on: ReturnType<typeof vi.fn>
}

type FakePageView = BrowserPageView & {
  setBounds: ReturnType<typeof vi.fn>
  setVisible: ReturnType<typeof vi.fn>
  webContents: FakeWebContents
}

function createFakeView(options: WebContentsViewConstructorOptions): FakePageView {
  const listeners = new Map<string, (event: BrowserNavigationEvent, url?: string) => void>()
  const webContents = {
    loadURL: vi.fn(async () => undefined),
    close: vi.fn(),
    getURL: vi.fn(() => ''),
    getTitle: vi.fn(() => ''),
    canGoBack: vi.fn(() => false),
    canGoForward: vi.fn(() => false),
    goBack: vi.fn(),
    goForward: vi.fn(),
    reload: vi.fn(),
    executeJavaScript: vi.fn(async () => ({ title: '', text: '' })),
    setWindowOpenHandler: vi.fn(),
    on: vi.fn((event: string, listener: (event: BrowserNavigationEvent, url?: string) => void) => {
      listeners.set(event, listener)
    })
  }

  return {
    setBounds: vi.fn(),
    setVisible: vi.fn(),
    webContents,
    emit(event: string, navigationEvent: BrowserNavigationEvent, url?: string) {
      listeners.get(event)?.(navigationEvent, url)
    },
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

function createBrowser(): {
  browser: VisibleBrowser
  createView: ReturnType<typeof vi.fn>
  session: Session
} {
  const session = { id: 'browser-profile' } as unknown as Session
  const createView = vi.fn((options: WebContentsViewConstructorOptions) => createFakeView(options))
  return {
    browser: new VisibleBrowser({ session, createView }),
    createView,
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

  it('rejects reads after the tab is no longer visible', async () => {
    const { browser, createView } = createBrowser()
    const window = createFakeWindow()
    browser.show(window, bounds, 'tab-1')
    browser.hide()
    const view = createView.mock.results[0]?.value as ReturnType<typeof createFakeView>

    await expect(browser.readCurrentPage('tab-1')).rejects.toThrow('not visible')
    expect(view.webContents.executeJavaScript).not.toHaveBeenCalled()
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
})
