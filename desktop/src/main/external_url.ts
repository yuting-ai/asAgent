const ALLOWED_WEB_PROTOCOLS = new Set(['http:', 'https:'])
const EXPLICIT_WEB_SCHEME = /^https?:/i
const NON_WEB_SCHEME = /^(file|javascript|mailto|data|ftp|about|blob):/i

function parseHttpOrHttpsUrl(
  value: unknown,
  invalidMessage: string,
  disallowedMessage: string,
  options: { allowCredentials: boolean }
): string {
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error(invalidMessage)
  }

  let url: URL
  try {
    url = new URL(value.trim())
  } catch {
    throw new Error(invalidMessage)
  }

  if (
    !ALLOWED_WEB_PROTOCOLS.has(url.protocol) ||
    !url.hostname ||
    (!options.allowCredentials && (url.username || url.password))
  ) {
    throw new Error(disallowedMessage)
  }

  return url.toString()
}

export function parseExternalWebUrl(value: unknown): string {
  return parseHttpOrHttpsUrl(value, 'External link is invalid.', 'External link is not allowed.', {
    allowCredentials: false
  })
}

export function parseBrowserWebUrl(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error('Browser address is invalid.')
  }

  const trimmed = value.trim()
  if (NON_WEB_SCHEME.test(trimmed)) {
    throw new Error('Browser address is not allowed.')
  }

  const withScheme = EXPLICIT_WEB_SCHEME.test(trimmed)
    ? trimmed
    : trimmed.startsWith('//')
      ? `https:${trimmed}`
      : `https://${trimmed}`

  return parseHttpOrHttpsUrl(
    withScheme,
    'Browser address is invalid.',
    'Browser address is not allowed.',
    { allowCredentials: true }
  )
}
