import { readFileSync } from 'node:fs'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'

afterEach(() => vi.unstubAllGlobals())

describe('workspace navigation layout', () => {
  it('excludes list controls and underlying Browser and task surfaces from native drag regions', () => {
    const css = readFileSync(new URL('./assets/main.css', import.meta.url), 'utf8')
    const buttonStyle = css.match(/\.workspace-list-button\s*\{([^}]+)\}/)?.[1]
    expect(buttonStyle).toContain('-webkit-app-region: no-drag')
    expect(buttonStyle).toContain('font-size: 12px')
    expect(buttonStyle).toContain('font-weight: 600')
    const surfaceStyle = css.match(
      /\.app:has\(> \.workspace-list-show\) \.browser-chrome,[^{]+\{([^}]+)\}/
    )
    expect(surfaceStyle?.[0]).toContain('.automations-detail-canvas,')
    expect(surfaceStyle?.[0]).toContain('.automations-detail-canvas *')
    expect(surfaceStyle?.[1]).toContain('-webkit-app-region: no-drag')
  })

  it.each([
    ['en', 'Conversations', 'Browser history', 'New chat', 'New Tab', 'Hide'],
    ['zh-Hans', '对话', '浏览器历史', '新建对话', '新标签页', '隐藏']
  ])('renders workspace navigation in %s', (language, heading, browser, chat, tab, hide) => {
    const localStorage = {
      getItem: (key: string) => (key === 'asagent:app_language' ? language : null)
    }
    vi.stubGlobal('localStorage', localStorage)
    vi.stubGlobal('window', { localStorage })
    const html = renderToStaticMarkup(createElement(App))
    const start = html.indexOf('id="workspace-list"')
    const list = html.slice(start, html.indexOf('</aside>', start))
    for (const label of [heading, browser, chat, tab, hide]) expect(list).toContain(label)
    if (language === 'zh-Hans') {
      expect(list).not.toContain('Browser history')
      expect(list).not.toContain('New chat')
      expect(list).not.toContain('Hide workspace list')
    }
  })

  it('keeps the conversation list outside the collapsed primary navigation', () => {
    const localStorage = { getItem: () => null }
    vi.stubGlobal('localStorage', localStorage)
    vi.stubGlobal('window', { localStorage })
    const html = renderToStaticMarkup(createElement(App))
    const navigation = html.slice(html.indexOf('<nav'), html.indexOf('</nav>'))
    const listStart = html.indexOf('id="workspace-list"')
    const list = html.slice(listStart, html.indexOf('</aside>', listStart))

    expect(html).toContain('rail-collapsed')
    expect(navigation).toContain('title="Chat"')
    expect(navigation).toContain('title="Browser"')
    expect(navigation).not.toContain('Chat history')
    expect(navigation).not.toContain('New chat')
    expect(listStart).toBeGreaterThan(html.indexOf('</nav>'))
    expect(list).toContain('Chat history')
    expect(list).toContain('New chat')
    const titlebar = html.slice(html.indexOf('<header'), html.indexOf('</header>'))
    expect(titlebar).not.toContain('Show workspace list')
    expect(html).not.toContain('workspace-content-toolbar')
    expect(html).not.toContain('Show workspace list')
    expect(list).toContain('class="workspace-list-button" aria-label="Hide workspace list"')
    expect(html).not.toContain('workspace-list-backdrop')
    expect(list).not.toContain('>Pin<')
  })
})
