import { mkdir, readFile, rename, writeFile } from 'node:fs/promises'
import { dirname } from 'node:path'
import { parseExternalWebUrl } from './external_url'

export type BrowserBookmark = { url: string; title: string }

// Bookmarks have their own lifetime, independent of open tabs and conversations.
export class BrowserBookmarkStore {
  private pending: Promise<unknown> = Promise.resolve()
  constructor(private readonly filePath: string) {}

  private normalize(value: unknown): BrowserBookmark {
    if (!value || typeof value !== 'object') throw new Error('Invalid bookmark.')
    const { url, title } = value as Record<string, unknown>
    if (
      typeof url !== 'string' ||
      url.length > 8192 ||
      typeof title !== 'string' ||
      !title.trim() ||
      title.length > 500
    )
      throw new Error('Invalid bookmark.')
    return { url: parseExternalWebUrl(url), title: title.trim() }
  }

  private async read(): Promise<BrowserBookmark[]> {
    let text: string
    try {
      text = await readFile(this.filePath, 'utf8')
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return []
      throw error
    }
    const data: unknown = JSON.parse(text)
    if (!Array.isArray(data) || data.length > 2000) throw new Error('Invalid bookmarks file.')
    return data.map((item) => this.normalize(item))
  }

  async list(): Promise<BrowserBookmark[]> {
    await this.pending
    return this.read()
  }

  update(action: unknown, value: unknown): Promise<BrowserBookmark[]> {
    const operation = this.pending.then(async () => {
      if (action !== 'save' && action !== 'remove') throw new Error('Invalid bookmark action.')
      const bookmark = this.normalize(value)
      const existing = await this.read()
      const items = existing.filter((item) => item.url !== bookmark.url)
      if (action === 'save') items.unshift(bookmark)
      if (items.length > 2000) throw new Error('Bookmark limit reached.')
      await mkdir(dirname(this.filePath), { recursive: true })
      await writeFile(this.filePath + '.tmp', JSON.stringify(items), { mode: 0o600 })
      await rename(this.filePath + '.tmp', this.filePath)
      return items
    })
    // Serialize edits and allow a later request to recover after a write failure.
    this.pending = operation.catch(() => undefined)
    return operation
  }
}
