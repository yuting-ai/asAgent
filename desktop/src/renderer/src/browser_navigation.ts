export type BrowserNavigationFailure = { tabId: string; message: string }

function navigationError(error: unknown): string | null {
  const text = error instanceof Error ? error.message : String(error)
  if (text.includes('Browser navigation was interrupted.')) return null
  return text.includes('could not be opened')
    ? 'This page could not be opened.'
    : 'This address is not allowed. Enter a web address such as example.com.'
}

// Each tab owns a request token. A newer request or confirmed load invalidates
// old promise rejections, including those delivered after the success event.
export function beginBrowserNavigationRequest(
  requests: Map<string, object>,
  tabId: string,
  report: (failure: BrowserNavigationFailure) => void
): (error: unknown) => void {
  const request = {}
  requests.set(tabId, request)
  return (error) => {
    if (requests.get(tabId) !== request) return
    const message = navigationError(error)
    if (message !== null) report({ tabId, message })
  }
}
