import { join } from 'node:path'

const MACOS_STANDARD_TOOL_DIRS = [
  '/opt/homebrew/bin',
  '/opt/homebrew/sbin',
  '/usr/local/bin',
  '/usr/local/sbin'
]

const MACOS_SYSTEM_BIN_DIRS = ['/usr/bin', '/bin', '/usr/sbin', '/sbin']

export function normalizeProcessPath(
  currentPath?: string,
  platform = process.platform,
  homeDir = process.env.HOME || ''
): string {
  const parts = (currentPath || '').split(':').filter(Boolean)
  const seen = new Set(parts)

  if (platform === 'darwin') {
    const toolDirs = MACOS_STANDARD_TOOL_DIRS.filter((dir) => !seen.has(dir))
    const userDirs = [join(homeDir, '.cargo', 'bin'), join(homeDir, '.local', 'bin')].filter(
      (dir) => dir && !seen.has(dir)
    )

    const prependDirs = [...toolDirs, ...userDirs]
    const updatedParts = [...prependDirs, ...parts]
    seen.clear()
    for (const d of updatedParts) {
      seen.add(d)
    }

    for (const sysDir of MACOS_SYSTEM_BIN_DIRS) {
      if (!seen.has(sysDir)) {
        updatedParts.push(sysDir)
        seen.add(sysDir)
      }
    }

    return updatedParts.join(':')
  }

  return parts.join(':')
}

export function ensureProcessPath(): void {
  if (process.platform === 'darwin') {
    process.env.PATH = normalizeProcessPath(process.env.PATH)
  }
}
