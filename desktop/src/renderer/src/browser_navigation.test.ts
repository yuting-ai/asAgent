import { describe, expect, it, vi } from 'vitest'
import { beginBrowserNavigationRequest } from './browser_navigation'

const failure = new Error('Browser page could not be opened.')

describe('browser navigation error ownership', () => {
  it('ignores a superseded request but preserves a current real failure', () => {
    const requests = new Map<string, object>()
    const report = vi.fn()
    const old = beginBrowserNavigationRequest(requests, 'a', report)
    const current = beginBrowserNavigationRequest(requests, 'a', report)
    old(failure)
    expect(report).not.toHaveBeenCalled()
    current(failure)
    expect(report).toHaveBeenCalledWith({ tabId: 'a', message: 'This page could not be opened.' })
  })
  it('ignores rejections delivered after confirmed load or tab closure', () => {
    const requests = new Map<string, object>()
    const report = vi.fn()
    const reject = beginBrowserNavigationRequest(requests, 'a', report)
    requests.delete('a')
    reject(failure)
    expect(report).not.toHaveBeenCalled()
  })
  it('keeps failure ownership on the original tab when another tab navigates', () => {
    const requests = new Map<string, object>()
    const report = vi.fn()
    const reject = beginBrowserNavigationRequest(requests, 'a', report)
    beginBrowserNavigationRequest(requests, 'b', report)
    reject(failure)
    expect(report).toHaveBeenCalledWith({ tabId: 'a', message: 'This page could not be opened.' })
  })
  it('does not display cancelled navigation as a page load failure', () => {
    const report = vi.fn()
    const reject = beginBrowserNavigationRequest(new Map(), 'a', report)
    reject(new Error('Error invoking remote method: Browser navigation was interrupted.'))
    expect(report).not.toHaveBeenCalled()
  })
  it('still reports invalid addresses', () => {
    const report = vi.fn()
    beginBrowserNavigationRequest(new Map(), 'a', report)(new Error('invalid URL'))
    expect(report).toHaveBeenCalledWith({
      tabId: 'a',
      message: 'This address is not allowed. Enter a web address such as example.com.'
    })
  })
})
