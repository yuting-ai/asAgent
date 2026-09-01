export type KnowledgeFolder = {
  path: string
  name: string
  sourceId?: string
  documentCount?: number
  chunkCount?: number
  scanStatus?: string
  lastScannedAt?: string | null
}

export type KnowledgeSyncStatus = 'empty' | 'ready' | 'updating' | 'error'

export type KnowledgeRunStage = 'searching' | 'generating' | 'completed' | 'failed'

export function knowledgeRunStage(eventType: string): KnowledgeRunStage | null {
  switch (eventType) {
    case 'run.started':
      return 'searching'
    case 'model.requested':
      return 'generating'
    case 'run.completed':
      return 'completed'
    case 'run.failed':
    case 'run.cancelled':
    case 'run.limit_reached':
      return 'failed'
    default:
      return null
  }
}

export function knowledgeSyncStatus(folders: KnowledgeFolder[]): KnowledgeSyncStatus {
  if (folders.length === 0) return 'empty'
  if (folders.some((folder) => folder.scanStatus === 'error')) return 'error'
  if (
    folders.some((folder) => ['queued', 'scanning', 'indexing'].includes(folder.scanStatus ?? ''))
  ) {
    return 'updating'
  }
  return 'ready'
}

export function latestKnowledgeScan(folders: KnowledgeFolder[]): string | null {
  const timestamps = folders
    .map((folder) => folder.lastScannedAt)
    .filter((value): value is string => value !== null && value !== undefined)
  if (timestamps.length === 0) return null
  return timestamps.sort((left, right) => Date.parse(right) - Date.parse(left))[0]
}

export type WorkspaceSelection = {
  path: string
  kind: 'directory' | 'file'
}

export type KnowledgeCitationTag = {
  tag: string
  index: number
}

export type KnowledgeSearchHit = {
  rank: number
  chunk_id: string
  score: number
  citation_label: string
  document_name: string
  source_path: string
  snippet: string
  page_start: number | null
  page_end: number | null
  section_title: string | null
}

export function knowledgeLibraryNameExists(
  libraries: Array<{ id: string; name: string }>,
  name: string,
  excludedLibraryId?: string
): boolean {
  const normalizedName = name.trim().toLocaleLowerCase()
  return libraries.some(
    (library) =>
      library.id !== excludedLibraryId && library.name.trim().toLocaleLowerCase() === normalizedName
  )
}

export function knowledgeFolderName(path: string): string {
  const parts = path.replaceAll('\\', '/').split('/').filter(Boolean)
  return parts.at(-1) ?? path
}

export function mergeKnowledgeFolders(
  current: KnowledgeFolder[],
  selections: WorkspaceSelection[]
): KnowledgeFolder[] {
  const folders = [...current]
  const knownPaths = new Set(current.map((folder) => folder.path))

  for (const selection of selections) {
    if (selection.kind !== 'directory' || knownPaths.has(selection.path)) {
      continue
    }
    folders.push({ path: selection.path, name: knowledgeFolderName(selection.path) })
    knownPaths.add(selection.path)
  }

  return folders
}

export function removeKnowledgeFolder(folders: KnowledgeFolder[], path: string): KnowledgeFolder[] {
  return folders.filter((folder) => folder.path !== path)
}

export function parseCitationTags(text: string): KnowledgeCitationTag[] {
  const regex = /\[S(\d+)\]/g
  const tags: KnowledgeCitationTag[] = []
  let match: RegExpExecArray | null
  while ((match = regex.exec(text)) !== null) {
    const num = Number.parseInt(match[1], 10)
    if (!tags.some((t) => t.index === num)) {
      tags.push({ tag: match[0], index: num })
    }
  }
  return tags.sort((a, b) => a.index - b.index)
}

export function formatCitationBadgeLabel(index: number): string {
  return `[S${index}]`
}

export function citationsForAssistant<
  T extends { assistantMessageId: string | null; chunkId: string }
>(citations: T[], messageId: string): T[] {
  return citations
    .filter((citation) => citation.assistantMessageId === messageId)
    .filter(
      (citation, index, items) =>
        items.findIndex((item) => item.chunkId === citation.chunkId) === index
    )
}

export function linkKnowledgeCitationTags(text: string, messageId: string): string {
  return text.replace(
    /\[S(\d+)\]/g,
    (_match, index: string) => `[[S${index}]](#knowledge-citation-${messageId}-S${index})`
  )
}
