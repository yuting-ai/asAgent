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

const LOCALHOST_OR_IP_PATTERN =
  /^(localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|\[[0-9a-fA-F:]+\])(:\d+)?(\/.*)?$/i
const DOMAIN_PATTERN = /^([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}(:\d+)?(\/.*)?$/

export function parseBrowserWebUrl(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error('Browser address is invalid.')
  }

  const trimmed = value.trim()
  if (NON_WEB_SCHEME.test(trimmed)) {
    throw new Error('Browser address is not allowed.')
  }

  if (EXPLICIT_WEB_SCHEME.test(trimmed)) {
    return parseHttpOrHttpsUrl(
      trimmed,
      'Browser address is invalid.',
      'Browser address is not allowed.',
      { allowCredentials: true }
    )
  }

  if (trimmed.startsWith('//')) {
    return parseHttpOrHttpsUrl(
      `https:${trimmed}`,
      'Browser address is invalid.',
      'Browser address is not allowed.',
      { allowCredentials: true }
    )
  }

  if (
    !/\s/.test(trimmed) &&
    (LOCALHOST_OR_IP_PATTERN.test(trimmed) || DOMAIN_PATTERN.test(trimmed))
  ) {
    try {
      return parseHttpOrHttpsUrl(
        `https://${trimmed}`,
        'Browser address is invalid.',
        'Browser address is not allowed.',
        { allowCredentials: true }
      )
    } catch {
      // If parsing as URL fails, fallback to search
    }
  }

  return `https://www.google.com/search?q=${encodeURIComponent(trimmed)}`
}
