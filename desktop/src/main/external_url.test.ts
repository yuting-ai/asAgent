import { describe, expect, it } from 'vitest'

import { parseExternalWebUrl } from './external_url'

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
    'https://user:password@example.com'
  ])('rejects unsafe or malformed links: %s', (value) => {
    expect(() => parseExternalWebUrl(value)).toThrow(/External link/)
  })
})
