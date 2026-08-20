import { describe, expect, it } from 'vitest'

import { parseBrowserWebUrl, parseExternalWebUrl } from './external_url'

describe('parseExternalWebUrl', () => {
  it('accepts ordinary HTTP and HTTPS links', () => {
    expect(parseExternalWebUrl('https://example.com/search?q=Perth')).toBe(
      'https://example.com/search?q=Perth'
    )
    expect(parseExternalWebUrl('http://example.com')).toBe('http://example.com/')
  })

  it.each([
    '',
    'relative/path',
    'file:///Users/example/secret.txt',
    'javascript:alert(1)',
    'mailto:user@example.com',
    'https://user:password@example.com',
    'file:///tmp/test',
    'data:text/html,hello',
    'ftp://example.com',
    'about:blank',
    'https://user@example.com'
  ])('rejects unsafe or malformed links: %s', (value) => {
    expect(() => parseExternalWebUrl(value)).toThrow(/External link/)
  })
})

describe('parseBrowserWebUrl', () => {
  it('accepts HTTP, HTTPS, credentials, and HTTPS-prefixed hostnames', () => {
    expect(parseBrowserWebUrl('https://example.com/search?q=Perth')).toBe(
      'https://example.com/search?q=Perth'
    )
    expect(parseBrowserWebUrl('http://example.com')).toBe('http://example.com/')
    expect(parseBrowserWebUrl('https://user:password@example.com/secret')).toBe(
      'https://user:password@example.com/secret'
    )
    expect(parseBrowserWebUrl('example.com')).toBe('https://example.com/')
    expect(parseBrowserWebUrl('localhost:3000/health')).toBe('https://localhost:3000/health')
  })

  it('converts search keywords and phrases to Google search queries', () => {
    expect(parseBrowserWebUrl('react hooks tutorial')).toBe(
      'https://www.google.com/search?q=react%20hooks%20tutorial'
    )
    expect(parseBrowserWebUrl('deepseek')).toBe('https://www.google.com/search?q=deepseek')
    expect(parseBrowserWebUrl('agent architecture 101')).toBe(
      'https://www.google.com/search?q=agent%20architecture%20101'
    )
    expect(parseBrowserWebUrl('what is an agent?')).toBe(
      'https://www.google.com/search?q=what%20is%20an%20agent%3F'
    )
    expect(parseBrowserWebUrl('c++')).toBe('https://www.google.com/search?q=c%2B%2B')
  })

  it.each([
    '',
    'file:///tmp/test',
    'javascript:alert(1)',
    'mailto:user@example.com',
    'data:text/html,hello',
    'ftp://example.com',
    'about:blank'
  ])('rejects non-web addresses: %s', (value) => {
    expect(() => parseBrowserWebUrl(value)).toThrow(/Browser address/)
  })
})
