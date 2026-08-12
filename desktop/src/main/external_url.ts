const ALLOWED_EXTERNAL_PROTOCOLS = new Set(['http:', 'https:'])

export function parseExternalWebUrl(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error('External link is invalid.')
  }

  let url: URL
  try {
    url = new URL(value)
  } catch {
    throw new Error('External link is invalid.')
  }

  if (
    !ALLOWED_EXTERNAL_PROTOCOLS.has(url.protocol) ||
    !url.hostname ||
    url.username ||
    url.password
  ) {
    throw new Error('External link is not allowed.')
  }

  return url.toString()
}
