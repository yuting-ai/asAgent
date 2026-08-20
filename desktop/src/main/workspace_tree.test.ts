import { promises as fs } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { listWorkspaceTree, readFilePreview } from './workspace_tree'

describe('workspace_tree', () => {
  let tempDir: string

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'workspace-tree-test-'))
  })

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true })
  })

  it('lists workspace tree sorted with directories first and ignores hidden/venv files', async () => {
    await fs.writeFile(path.join(tempDir, 'z_file.txt'), 'hello')
    await fs.writeFile(path.join(tempDir, 'a_file.md'), '# Markdown')
    await fs.mkdir(path.join(tempDir, 'sub_dir'))
    await fs.writeFile(path.join(tempDir, 'sub_dir', 'nested.ts'), 'export const x = 1')
    await fs.mkdir(path.join(tempDir, 'node_modules'))
    await fs.writeFile(path.join(tempDir, 'node_modules', 'dep.js'), 'bad')
    await fs.mkdir(path.join(tempDir, '.git'))

    const tree = await listWorkspaceTree(tempDir, 3)
    expect(tree).not.toBeNull()
    expect(tree?.kind).toBe('directory')
    expect(tree?.children?.length).toBe(3) // sub_dir, a_file.md, z_file.txt

    // sub_dir should be first
    expect(tree?.children?.[0].name).toBe('sub_dir')
    expect(tree?.children?.[0].kind).toBe('directory')
    expect(tree?.children?.[0].children?.[0].name).toBe('nested.ts')

    // then files alphabetically
    expect(tree?.children?.[1].name).toBe('a_file.md')
    expect(tree?.children?.[1].extension).toBe('md')
    expect(tree?.children?.[2].name).toBe('z_file.txt')
  })

  it('respects max depth when traversing', async () => {
    await fs.mkdir(path.join(tempDir, 'lvl1', 'lvl2', 'lvl3'), { recursive: true })
    await fs.writeFile(path.join(tempDir, 'lvl1', 'lvl2', 'lvl3', 'deep.txt'), 'deep')

    const tree = await listWorkspaceTree(tempDir, 1)
    expect(tree?.children?.[0].name).toBe('lvl1')
    expect(tree?.children?.[0].children?.length).toBe(0)
  })

  it('reads text file preview and detects truncation', async () => {
    const filePath = path.join(tempDir, 'sample.txt')
    await fs.writeFile(filePath, 'Hello world text preview')

    const preview = await readFilePreview(filePath, 5)
    expect(preview).not.toBeNull()
    expect(preview?.isBinary).toBe(false)
    expect(preview?.content).toBe('Hello')
    expect(preview?.isTruncated).toBe(true)
    expect(preview?.size).toBe(24)
  })

  it('detects binary file preview safely', async () => {
    const filePath = path.join(tempDir, 'binary.bin')
    const buffer = Buffer.from([0x00, 0x01, 0x02, 0x03, 0x00])
    await fs.writeFile(filePath, buffer)

    const preview = await readFilePreview(filePath, 100)
    expect(preview).not.toBeNull()
    expect(preview?.isBinary).toBe(true)
    expect(preview?.content).toBe('')
  })
})
