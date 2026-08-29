export type UpdateCheckResult = {
  currentVersion: string
  latestVersion: string
  hasUpdate: boolean
  releaseUrl: string
  releaseNotes: string
  publishedAt: string
}

export type UpdateCheckerOptions = {
  currentVersion: string
  repoOwner?: string
  repoName?: string
  fetchFn?: typeof fetch
}

export function compareSemver(versionA: string, versionB: string): number {
  const parse = (v: string): number[] =>
    v
      .trim()
      .replace(/^v/i, '')
      .split('.')
      .map((part) => parseInt(part, 10) || 0)

  const partsA = parse(versionA)
  const partsB = parse(versionB)
  const maxLength = Math.max(partsA.length, partsB.length)

  for (let i = 0; i < maxLength; i++) {
    const numA = partsA[i] ?? 0
    const numB = partsB[i] ?? 0
    if (numA > numB) return 1
    if (numA < numB) return -1
  }

  return 0
}

export class UpdateChecker {
  private readonly currentVersion: string
  private readonly repoOwner: string
  private readonly repoName: string
  private readonly fetchFn: typeof fetch

  constructor(options: UpdateCheckerOptions) {
    this.currentVersion = options.currentVersion
    this.repoOwner = options.repoOwner ?? 'yuting-ai'
    this.repoName = options.repoName ?? 'asAgent'
    this.fetchFn = options.fetchFn ?? fetch
  }

  async checkForUpdates(): Promise<UpdateCheckResult> {
    const url = `https://api.github.com/repos/${this.repoOwner}/${this.repoName}/releases/latest`

    const response = await this.fetchFn(url, {
      headers: {
        Accept: 'application/vnd.github.v3+json',
        'User-Agent': 'asAgent-Desktop'
      }
    })

    if (!response.ok) {
      throw new Error(`Failed to check for updates (HTTP ${response.status})`)
    }

    const data = (await response.json()) as {
      tag_name?: string
      html_url?: string
      body?: string
      published_at?: string
    }

    if (typeof data.tag_name !== 'string' || typeof data.html_url !== 'string') {
      throw new Error('Invalid release payload received from GitHub.')
    }

    const latestVersion = data.tag_name
    const hasUpdate = compareSemver(latestVersion, this.currentVersion) > 0

    return {
      currentVersion: this.currentVersion,
      latestVersion,
      hasUpdate,
      releaseUrl: data.html_url,
      releaseNotes: typeof data.body === 'string' ? data.body : '',
      publishedAt: typeof data.published_at === 'string' ? data.published_at : ''
    }
  }
}
