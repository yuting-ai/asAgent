import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, it, expect } from 'vitest'
import { BrowserBookmarkStore } from './browser_bookmarks'

describe('browser bookmarks', () => {
  it('serializes writes, deduplicates URLs, and restores edits and deletion', async () => {
    const dir = await mkdtemp(join(tmpdir(), 'bookmarks-'))
    try {
      const file = join(dir, 'bookmarks.json')
      const store = new BrowserBookmarkStore(file)
      expect(await store.list()).toEqual([])
      await Promise.all([
        store.update('save', { url: 'https://example.com', title: 'Example' }),
        store.update('save', { url: 'https://example.org', title: 'Other' })
      ])
      await store.update('save', { url: 'https://example.com/', title: 'Renamed' })
      expect(await new BrowserBookmarkStore(file).list()).toEqual([
        { url: 'https://example.com/', title: 'Renamed' },
        { url: 'https://example.org/', title: 'Other' }
      ])
      await store.update('remove', { url: 'https://example.com', title: 'Renamed' })
      expect(await new BrowserBookmarkStore(file).list()).toHaveLength(1)
      for (const url of [
        'javascript:alert(1)',
        'file:///private/test',
        'https://user:secret@example.com'
      ]) {
        await expect(store.update('save', { url, title: 'Invalid' })).rejects.toThrow()
      }
      expect(await store.list()).toHaveLength(1)
    } finally {
      await rm(dir, { recursive: true, force: true })
    }
  })
  it('does not overwrite an unreadable or malformed collection', async () => {
    const dir = await mkdtemp(join(tmpdir(), 'bookmarks-'))
    try {
      const file = join(dir, 'bookmarks.json')
      await writeFile(file, 'broken')
      const store = new BrowserBookmarkStore(file)
      await expect(
        store.update('save', { url: 'https://example.com', title: 'Example' })
      ).rejects.toThrow()
      expect(await readFile(file, 'utf8')).toBe('broken')
    } finally {
      await rm(dir, { recursive: true, force: true })
    }
  })
})
