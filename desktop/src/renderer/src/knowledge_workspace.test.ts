import { describe, expect, it } from 'vitest'

import {
  citationsForAssistant,
  formatCitationBadgeLabel,
  knowledgeFolderName,
  knowledgeLibraryNameExists,
  knowledgeRunStage,
  knowledgeSyncStatus,
  latestKnowledgeScan,
  linkKnowledgeCitationTags,
  mergeKnowledgeFolders,
  parseCitationTags,
  removeKnowledgeFolder
} from './knowledge_workspace'

describe('knowledgeRunStage', () => {
  it('maps run SSE events to the compact knowledge answer stages', () => {
    expect(knowledgeRunStage('run.started')).toBe('searching')
    expect(knowledgeRunStage('model.requested')).toBe('generating')
    expect(knowledgeRunStage('run.completed')).toBe('completed')
    expect(knowledgeRunStage('run.failed')).toBe('failed')
    expect(knowledgeRunStage('run.cancelled')).toBe('failed')
    expect(knowledgeRunStage('run.limit_reached')).toBe('failed')
    expect(knowledgeRunStage('model.completed')).toBeNull()
  })
})

describe('knowledgeLibraryNameExists', () => {
  const libraries = [
    { id: 'library-1', name: 'Research Papers' },
    { id: 'library-2', name: 'Company Handbook' }
  ]

  it('treats whitespace and letter case as the same display name', () => {
    expect(knowledgeLibraryNameExists(libraries, '  research papers ')).toBe(true)
  })

  it('allows a library to retain its own name while being renamed', () => {
    expect(knowledgeLibraryNameExists(libraries, 'Research Papers', 'library-1')).toBe(false)
  })
})

describe('knowledgeFolderName', () => {
  it('extracts a readable folder name from POSIX and Windows paths', () => {
    expect(knowledgeFolderName('/Users/research/AI Papers')).toBe('AI Papers')
    expect(knowledgeFolderName('C:\\Research\\Lab Notes')).toBe('Lab Notes')
  })
})

describe('knowledgeSyncStatus', () => {
  it('summarizes source activity and errors for the library header', () => {
    expect(knowledgeSyncStatus([])).toBe('empty')
    expect(knowledgeSyncStatus([{ path: '/papers', name: 'papers', scanStatus: 'ready' }])).toBe(
      'ready'
    )
    expect(knowledgeSyncStatus([{ path: '/papers', name: 'papers', scanStatus: 'indexing' }])).toBe(
      'updating'
    )
    expect(knowledgeSyncStatus([{ path: '/papers', name: 'papers', scanStatus: 'error' }])).toBe(
      'error'
    )
  })
})

describe('latestKnowledgeScan', () => {
  it('returns the newest completed source scan', () => {
    expect(
      latestKnowledgeScan([
        { path: '/a', name: 'a', lastScannedAt: '2026-08-31T10:00:00Z' },
        { path: '/b', name: 'b', lastScannedAt: '2026-08-31T11:00:00Z' }
      ])
    ).toBe('2026-08-31T11:00:00Z')
  })
})

describe('mergeKnowledgeFolders', () => {
  it('accepts directories while ignoring files and duplicate paths', () => {
    const result = mergeKnowledgeFolders(
      [{ path: '/Research/AI Papers', name: 'AI Papers' }],
      [
        { path: '/Research/AI Papers', kind: 'directory' },
        { path: '/Research/paper.pdf', kind: 'file' },
        { path: '/Research/Lab Notes', kind: 'directory' }
      ]
    )

    expect(result).toEqual([
      { path: '/Research/AI Papers', name: 'AI Papers' },
      { path: '/Research/Lab Notes', name: 'Lab Notes' }
    ])
  })
})

describe('removeKnowledgeFolder', () => {
  it('removes only the selected source without touching other folders', () => {
    const result = removeKnowledgeFolder(
      [
        { path: '/Research/AI Papers', name: 'AI Papers' },
        { path: '/Research/Lab Notes', name: 'Lab Notes' }
      ],
      '/Research/AI Papers'
    )

    expect(result).toEqual([{ path: '/Research/Lab Notes', name: 'Lab Notes' }])
  })
})

describe('parseCitationTags', () => {
  it('extracts unique citation tags in ascending numeric order', () => {
    const text =
      'According to [S2], SQLite WAL supports concurrent readers. As described in [S1] and also [S2], writers append log frames.'
    const tags = parseCitationTags(text)
    expect(tags).toEqual([
      { tag: '[S1]', index: 1 },
      { tag: '[S2]', index: 2 }
    ])
  })

  it('returns empty array when no citation tags are present', () => {
    expect(parseCitationTags('No citations here.')).toEqual([])
  })
})

describe('formatCitationBadgeLabel', () => {
  it('formats numeric index into bracketed tag', () => {
    expect(formatCitationBadgeLabel(1)).toBe('[S1]')
    expect(formatCitationBadgeLabel(42)).toBe('[S42]')
  })
})

describe('citationsForAssistant', () => {
  it('keeps citations with the matching answer and removes duplicate chunks', () => {
    const citations = [
      { assistantMessageId: 'message-1', chunkId: 'chunk-1', label: 'S1' },
      { assistantMessageId: 'message-1', chunkId: 'chunk-1', label: 'S1 duplicate' },
      { assistantMessageId: 'message-2', chunkId: 'chunk-2', label: 'S1' }
    ]

    expect(citationsForAssistant(citations, 'message-1')).toEqual([citations[0]])
  })
})

describe('linkKnowledgeCitationTags', () => {
  it('turns citation labels into answer-scoped Markdown links', () => {
    expect(linkKnowledgeCitationTags('Evidence [S1] and [S2].', 'message-1')).toBe(
      'Evidence [[S1]](#knowledge-citation-message-1-S1) and [[S2]](#knowledge-citation-message-1-S2).'
    )
  })
})
