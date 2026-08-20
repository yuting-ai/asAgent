import { promises as fs } from 'node:fs'
import path from 'node:path'

export type WorkspaceFileNode = {
  name: string
  path: string
  relativePath: string
  kind: 'file' | 'directory'
  size?: number
  extension?: string
  children?: WorkspaceFileNode[]
}

export type FilePreviewResult = {
  path: string
  name: string
  size: number
  content: string
  isTruncated: boolean
  isBinary: boolean
}

const DEFAULT_IGNORE_NAMES = new Set([
  '.git',
  'node_modules',
  '.venv',
  'venv',
  '__pycache__',
  '.pytest_cache',
  '.mypy_cache',
  '.ruff_cache',
  'dist',
  'build',
  '.DS_Store'
])

export async function listWorkspaceTree(
  rootPath: string,
  maxDepth = 3,
  currentDepth = 0,
  currentRelativePath = ''
): Promise<WorkspaceFileNode | null> {
  try {
    const stats = await fs.stat(rootPath)
    if (!stats.isDirectory()) {
      return null
    }

    const nodeName = path.basename(rootPath)
    const node: WorkspaceFileNode = {
      name: nodeName,
      path: rootPath,
      relativePath: currentRelativePath || nodeName,
      kind: 'directory',
      children: []
    }

    if (currentDepth >= maxDepth) {
      return node
    }

    const entries = await fs.readdir(rootPath, { withFileTypes: true })
    const sortedEntries = entries
      .filter((entry) => !DEFAULT_IGNORE_NAMES.has(entry.name) && !entry.name.startsWith('._'))
      .sort((a, b) => {
        if (a.isDirectory() && !b.isDirectory()) {
          return -1
        }
        if (!a.isDirectory() && b.isDirectory()) {
          return 1
        }
        return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' })
      })

    const children: WorkspaceFileNode[] = []
    for (const entry of sortedEntries) {
      const childPath = path.join(rootPath, entry.name)
      const childRelPath = currentRelativePath
        ? path.join(currentRelativePath, entry.name)
        : entry.name

      if (entry.isDirectory()) {
        const subDir = await listWorkspaceTree(childPath, maxDepth, currentDepth + 1, childRelPath)
        if (subDir) {
          children.push(subDir)
        }
      } else if (entry.isFile()) {
        try {
          const fileStat = await fs.stat(childPath)
          const ext = path.extname(entry.name).toLowerCase().replace(/^\./, '')
          children.push({
            name: entry.name,
            path: childPath,
            relativePath: childRelPath,
            kind: 'file',
            size: fileStat.size,
            extension: ext
          })
        } catch {
          // Skip inaccessible file
        }
      }
    }

    node.children = children
    return node
  } catch {
    return null
  }
}

export async function readFilePreview(
  filePath: string,
  maxBytes = 100 * 1024
): Promise<FilePreviewResult | null> {
  try {
    const stat = await fs.stat(filePath)
    if (!stat.isFile()) {
      return null
    }

    const name = path.basename(filePath)
    const size = stat.size

    const fileHandle = await fs.open(filePath, 'r')
    try {
      const readLength = Math.min(size, maxBytes)
      const buffer = Buffer.alloc(readLength)
      await fileHandle.read(buffer, 0, readLength, 0)

      const sampleLength = Math.min(readLength, 1024)
      let isBinary = false
      for (let i = 0; i < sampleLength; i++) {
        if (buffer[i] === 0) {
          isBinary = true
          break
        }
      }

      if (isBinary) {
        return {
          path: filePath,
          name,
          size,
          content: '',
          isTruncated: false,
          isBinary: true
        }
      }

      const content = buffer.toString('utf-8')
      const isTruncated = size > maxBytes

      return {
        path: filePath,
        name,
        size,
        content,
        isTruncated,
        isBinary: false
      }
    } finally {
      await fileHandle.close()
    }
  } catch {
    return null
  }
}
