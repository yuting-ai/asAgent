import { describe, expect, it } from 'vitest'
import { normalizeProcessPath } from './path_normalizer'

describe('normalizeProcessPath', () => {
  it('augments macOS GUI PATH with Homebrew and standard tool paths', () => {
    const minimalGuiPath = '/usr/bin:/bin:/usr/sbin:/sbin'
    const normalized = normalizeProcessPath(minimalGuiPath, 'darwin', '/Users/test')

    expect(normalized).toContain('/opt/homebrew/bin')
    expect(normalized).toContain('/usr/local/bin')
    expect(normalized).toContain('/Users/test/.cargo/bin')
    expect(normalized).toContain('/usr/bin')

    const parts = normalized.split(':')
    expect(parts.indexOf('/opt/homebrew/bin')).toBeLessThan(parts.indexOf('/usr/bin'))
    expect(new Set(parts).size).toBe(parts.length)
  })

  it('preserves non-macOS PATH', () => {
    const linuxPath = '/usr/bin:/bin:/custom/bin'
    const normalized = normalizeProcessPath(linuxPath, 'linux', '/home/test')
    expect(normalized).toBe(linuxPath)
  })
})
