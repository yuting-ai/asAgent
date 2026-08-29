import { describe, expect, it } from 'vitest'
import { compareSemver, UpdateChecker } from './update_checker'

describe('compareSemver', () => {
  it('correctly compares version numbers with or without v prefix', () => {
    expect(compareSemver('0.0.2', '0.0.1')).toBe(1)
    expect(compareSemver('v0.0.2', 'v0.0.1')).toBe(1)
    expect(compareSemver('0.1.0', '0.0.9')).toBe(1)
    expect(compareSemver('1.0.0', '0.9.9')).toBe(1)
    expect(compareSemver('0.0.1', '0.0.1')).toBe(0)
    expect(compareSemver('v0.0.1', '0.0.1')).toBe(0)
    expect(compareSemver('0.0.1', '0.0.2')).toBe(-1)
  })
})

describe('UpdateChecker', () => {
  it('detects when an update is available', async () => {
    const mockFetch = (async () => {
      return new Response(
        JSON.stringify({
          tag_name: 'v0.0.2',
          html_url: 'https://github.com/yuting-ai/asAgent/releases/tag/v0.0.2',
          body: '- Added auto update\n- Bug fixes',
          published_at: '2026-08-29T12:00:00Z'
        }),
        { status: 200 }
      )
    }) as unknown as typeof fetch

    const checker = new UpdateChecker({
      currentVersion: '0.0.1',
      fetchFn: mockFetch
    })

    const result = await checker.checkForUpdates()
    expect(result.hasUpdate).toBe(true)
    expect(result.currentVersion).toBe('0.0.1')
    expect(result.latestVersion).toBe('v0.0.2')
    expect(result.releaseUrl).toBe('https://github.com/yuting-ai/asAgent/releases/tag/v0.0.2')
    expect(result.releaseNotes).toContain('Added auto update')
  })

  it('detects when the current version is already up to date', async () => {
    const mockFetch = (async () => {
      return new Response(
        JSON.stringify({
          tag_name: 'v0.0.1',
          html_url: 'https://github.com/yuting-ai/asAgent/releases/tag/v0.0.1',
          body: 'Initial release',
          published_at: '2026-08-29T10:00:00Z'
        }),
        { status: 200 }
      )
    }) as unknown as typeof fetch

    const checker = new UpdateChecker({
      currentVersion: '0.0.1',
      fetchFn: mockFetch
    })

    const result = await checker.checkForUpdates()
    expect(result.hasUpdate).toBe(false)
    expect(result.latestVersion).toBe('v0.0.1')
  })

  it('throws an error if GitHub API returns non-200 status', async () => {
    const mockFetch = (async () => {
      return new Response('Not Found', { status: 404 })
    }) as unknown as typeof fetch

    const checker = new UpdateChecker({
      currentVersion: '0.0.1',
      fetchFn: mockFetch
    })

    await expect(checker.checkForUpdates()).rejects.toThrow(
      'Failed to check for updates (HTTP 404)'
    )
  })
})
