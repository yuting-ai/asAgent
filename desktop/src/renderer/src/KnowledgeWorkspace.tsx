import { createPortal } from 'react-dom'
import {
  type FormEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useState
} from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { type AppLanguage, t } from './i18n'
import {
  type KnowledgeFolder,
  type KnowledgeRunStage,
  citationsForAssistant,
  knowledgeLibraryNameExists,
  knowledgeFolderName,
  knowledgeRunStage,
  knowledgeSyncStatus,
  latestKnowledgeScan,
  linkKnowledgeCitationTags,
  mergeKnowledgeFolders
} from './knowledge_workspace'

type KnowledgeMessage = {
  id: string
  content: string
  role: 'user' | 'assistant'
}

type KnowledgeConversation = {
  id: string
  title: string
  messages: KnowledgeMessage[]
  citations: KnowledgeCitation[]
}

type KnowledgeCitation = {
  runId: string
  assistantMessageId: string | null
  chunkId: string
  label: string
  documentName: string
  sourcePath: string
  snippet: string
  pageStart: number | null
  pageEnd: number | null
  sectionTitle: string | null
}

type KnowledgeLibrary = {
  id: string
  name: string
  folders: KnowledgeFolder[]
  conversations: KnowledgeConversation[]
  selectedConversationId: string
  documentCount: number
  chunkCount: number
}

type KnowledgeIndexProgress = {
  library_id: string
  status: 'empty' | 'ready' | 'scanning' | 'indexing' | 'error'
  active_jobs: number
  discovered_files: number
  processed_files: number
  failed_files: number
  total_chunks: number
  indexed_chunks: number
  document_count: number
  chunk_count: number
  updated_at: string
}

type KnowledgeRunActivity = {
  runId: string | null
  conversationId: string
  stage: Extract<KnowledgeRunStage, 'searching' | 'generating'>
}

function WorkspaceIcon({ path }: { path: string }): React.JSX.Element {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path d={path} />
    </svg>
  )
}

export default function KnowledgeWorkspace({
  lang,
  listHost
}: {
  lang: AppLanguage
  listHost: HTMLDivElement | null
}): React.JSX.Element {
  const [libraries, setLibraries] = useState<KnowledgeLibrary[]>([])
  const [selectedLibraryId, setSelectedLibraryId] = useState('')
  const [isCreatingLibrary, setIsCreatingLibrary] = useState(false)
  const [newLibraryName, setNewLibraryName] = useState('')
  const [libraryCreateError, setLibraryCreateError] = useState<string | null>(null)
  const [openLibraryMenuId, setOpenLibraryMenuId] = useState<string | null>(null)
  const [libraryToRenameId, setLibraryToRenameId] = useState<string | null>(null)
  const [renameLibraryName, setRenameLibraryName] = useState('')
  const [renameLibraryError, setRenameLibraryError] = useState<string | null>(null)
  const [libraryToDeleteId, setLibraryToDeleteId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [historyOpen, setHistoryOpen] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [folderToRemove, setFolderToRemove] = useState<KnowledgeFolder | null>(null)
  const [isBusy, setIsBusy] = useState(false)
  const [indexProgress, setIndexProgress] = useState<KnowledgeIndexProgress | null>(null)
  const [runActivity, setRunActivity] = useState<KnowledgeRunActivity | null>(null)

  const reloadWorkspace = useCallback(
    async (preferredLibraryId?: string, preferredConversationId?: string): Promise<void> => {
      const [backendLibraries, backendConversations] = await Promise.all([
        window.desktop.listKnowledgeLibraries(),
        window.desktop.listKnowledgeConversations()
      ])
      const conversationDetails = await Promise.all(
        backendConversations.map(async (conversation) => {
          const [binding, messages, citations] = await Promise.all([
            window.desktop.getKnowledgeConversationLibrary(conversation.conversation_id),
            window.desktop.listKnowledgeConversationMessages(conversation.conversation_id),
            window.desktop.listKnowledgeConversationCitations(conversation.conversation_id)
          ])
          return {
            libraryId: binding.library_id,
            conversation: {
              id: conversation.conversation_id,
              title: conversation.title ?? t(lang, 'knowledgeNewConversation'),
              messages: messages.map((message) => ({
                id: message.message_id,
                content: message.content,
                role: message.role
              })),
              citations: citations.map((citation) => ({
                runId: citation.run_id,
                assistantMessageId: citation.assistant_message_id,
                chunkId: citation.chunk_id,
                label: citation.citation_label,
                documentName: citation.document_name,
                sourcePath: citation.source_path,
                snippet: citation.snippet,
                pageStart: citation.page_start,
                pageEnd: citation.page_end,
                sectionTitle: citation.section_title
              }))
            }
          }
        })
      )

      const nextLibraries: KnowledgeLibrary[] = backendLibraries.map((library) => {
        const conversations = conversationDetails
          .filter((item) => item.libraryId === library.library_id)
          .map((item) => item.conversation)
        return {
          id: library.library_id,
          name: library.name,
          folders: library.sources.map((source) => ({
            path: source.display_path,
            name: knowledgeFolderName(source.display_path),
            sourceId: source.source_id,
            documentCount: source.document_count,
            chunkCount: source.chunk_count,
            scanStatus: source.scan_status,
            lastScannedAt: source.last_scanned_at
          })),
          conversations,
          documentCount: library.document_count,
          chunkCount: library.chunk_count,
          selectedConversationId:
            preferredConversationId !== undefined &&
            conversations.some((conversation) => conversation.id === preferredConversationId)
              ? preferredConversationId
              : (conversations[0]?.id ?? '')
        }
      })
      setLibraries(nextLibraries)
      setSelectedLibraryId((current) => {
        const requested = preferredLibraryId ?? current
        return nextLibraries.some((library) => library.id === requested)
          ? requested
          : (nextLibraries[0]?.id ?? '')
      })
    },
    [lang]
  )

  const refreshLibraryStatuses = useCallback(async (): Promise<void> => {
    const backendLibraries = await window.desktop.listKnowledgeLibraries()
    setLibraries((current) =>
      current.map((library) => {
        const backend = backendLibraries.find((item) => item.library_id === library.id)
        if (backend === undefined) return library
        return {
          ...library,
          name: backend.name,
          documentCount: backend.document_count,
          chunkCount: backend.chunk_count,
          folders: backend.sources.map((source) => ({
            path: source.display_path,
            name: knowledgeFolderName(source.display_path),
            sourceId: source.source_id,
            documentCount: source.document_count,
            chunkCount: source.chunk_count,
            scanStatus: source.scan_status,
            lastScannedAt: source.last_scanned_at
          }))
        }
      })
    )
  }, [])

  useEffect(() => {
    const interval = window.setInterval(() => {
      void refreshLibraryStatuses().catch(() => undefined)
    }, 10_000)
    return () => window.clearInterval(interval)
  }, [refreshLibraryStatuses])

  useEffect(
    () =>
      window.desktop.onKnowledgeIndexProgress((progress) => {
        setIndexProgress(progress)
        setLibraries((current) =>
          current.map((library) =>
            library.id === progress.library_id
              ? {
                  ...library,
                  documentCount: progress.document_count,
                  chunkCount: progress.chunk_count
                }
              : library
          )
        )
        if (progress.status === 'ready' || progress.status === 'error') {
          void refreshLibraryStatuses().catch(() => undefined)
        }
      }),
    [refreshLibraryStatuses]
  )

  useEffect(
    () =>
      window.desktop.onKnowledgeIndexStreamError((error) => {
        if (error.libraryId === selectedLibraryId) setNotice(error.message)
      }),
    [selectedLibraryId]
  )

  useEffect(() => {
    if (!selectedLibraryId) return undefined
    const libraryId = selectedLibraryId
    void window.desktop
      .watchKnowledgeIndexProgress(libraryId)
      .catch(() => setNotice(t(lang, 'knowledgeBackendPending')))
    return () => {
      void window.desktop.unwatchKnowledgeIndexProgress(libraryId)
    }
  }, [lang, selectedLibraryId])

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void reloadWorkspace().catch(() => setNotice(t(lang, 'knowledgeBackendPending')))
    }, 0)
    return () => window.clearTimeout(timeout)
  }, [lang, reloadWorkspace])

  useEffect(
    () =>
      window.desktop.onRunEvent((update) => {
        const isKnowledgeConversation = libraries.some((library) =>
          library.conversations.some((conversation) => conversation.id === update.conversationId)
        )
        const isActiveKnowledgeRun = runActivity?.conversationId === update.conversationId
        if (!isKnowledgeConversation && !isActiveKnowledgeRun) return

        const stage = knowledgeRunStage(update.event.event_type)
        if (stage === 'searching' || stage === 'generating') {
          setRunActivity({
            runId: update.runId,
            conversationId: update.conversationId,
            stage
          })
        } else if (stage === 'completed' || stage === 'failed') {
          setRunActivity((current) =>
            current?.runId === null || current?.runId === update.runId ? null : current
          )
          setIsBusy(false)
          void reloadWorkspace(selectedLibraryId, update.conversationId)
        }
      }),
    [libraries, reloadWorkspace, runActivity?.conversationId, selectedLibraryId]
  )

  useEffect(
    () =>
      window.desktop.onRunStreamError((error) => {
        const isKnowledgeConversation = libraries.some((library) =>
          library.conversations.some((conversation) => conversation.id === error.conversationId)
        )
        if (isKnowledgeConversation || runActivity?.conversationId === error.conversationId) {
          setRunActivity((current) =>
            current?.conversationId === error.conversationId ? null : current
          )
          setIsBusy(false)
          setNotice(error.message)
        }
      }),
    [libraries, runActivity?.conversationId]
  )

  const selectedLibrary =
    libraries.find((library) => library.id === selectedLibraryId) ?? libraries[0]
  const libraryToRename = libraries.find((library) => library.id === libraryToRenameId)
  const libraryToDelete = libraries.find((library) => library.id === libraryToDeleteId)
  const selectedConversation = useMemo(() => {
    if (selectedLibrary === undefined) {
      return undefined
    }
    return (
      selectedLibrary.conversations.find(
        (conversation) => conversation.id === selectedLibrary.selectedConversationId
      ) ?? selectedLibrary.conversations[0]
    )
  }, [selectedLibrary])
  const selectedLibrarySyncStatus = knowledgeSyncStatus(selectedLibrary?.folders ?? [])
  const selectedLibraryLastScan = latestKnowledgeScan(selectedLibrary?.folders ?? [])
  const selectedLibraryProgress =
    indexProgress?.library_id === selectedLibrary?.id ? indexProgress : null
  const displayedSyncStatus =
    selectedLibraryProgress?.status === 'error'
      ? 'error'
      : selectedLibraryProgress?.status === 'scanning' ||
          selectedLibraryProgress?.status === 'indexing'
        ? 'updating'
        : selectedLibrarySyncStatus
  const visibleRunActivity =
    runActivity?.conversationId === selectedConversation?.id ? runActivity : null

  function updateSelectedLibrary(update: (library: KnowledgeLibrary) => KnowledgeLibrary): void {
    setLibraries((current) =>
      current.map((library) => (library.id === selectedLibraryId ? update(library) : library))
    )
  }

  function selectLibrary(libraryId: string): void {
    setSelectedLibraryId(libraryId)
    setDraft('')
    setNotice(null)
    setHistoryOpen(false)
    setFolderToRemove(null)
    setOpenLibraryMenuId(null)
  }

  async function createLibrary(event: FormEvent): Promise<void> {
    event.preventDefault()
    const name = newLibraryName.trim()
    if (!name) {
      return
    }
    if (knowledgeLibraryNameExists(libraries, name)) {
      setLibraryCreateError(t(lang, 'knowledgeDuplicateLibraryName'))
      return
    }
    try {
      setIsBusy(true)
      const created = await window.desktop.createKnowledgeLibrary(name)
      await reloadWorkspace(created.library_id)
      setNewLibraryName('')
      setLibraryCreateError(null)
      setIsCreatingLibrary(false)
      setDraft('')
      setNotice(null)
    } catch {
      setLibraryCreateError(t(lang, 'knowledgeDuplicateLibraryName'))
    } finally {
      setIsBusy(false)
    }
  }

  function openRenameLibrary(library: KnowledgeLibrary): void {
    setLibraryToRenameId(library.id)
    setRenameLibraryName(library.name)
    setRenameLibraryError(null)
    setOpenLibraryMenuId(null)
  }

  async function renameLibrary(event: FormEvent): Promise<void> {
    event.preventDefault()
    if (libraryToRename === undefined) {
      return
    }
    const name = renameLibraryName.trim()
    if (!name) {
      return
    }
    if (knowledgeLibraryNameExists(libraries, name, libraryToRename.id)) {
      setRenameLibraryError(t(lang, 'knowledgeDuplicateLibraryName'))
      return
    }
    try {
      setIsBusy(true)
      await window.desktop.renameKnowledgeLibrary(libraryToRename.id, name)
      await reloadWorkspace(selectedLibraryId)
      setLibraryToRenameId(null)
      setRenameLibraryName('')
      setRenameLibraryError(null)
    } catch {
      setRenameLibraryError(t(lang, 'knowledgeDuplicateLibraryName'))
    } finally {
      setIsBusy(false)
    }
  }

  async function confirmLibraryDeletion(): Promise<void> {
    if (libraryToDelete === undefined || libraries.length === 1) {
      return
    }
    try {
      setIsBusy(true)
      await window.desktop.deleteKnowledgeLibrary(libraryToDelete.id)
      await reloadWorkspace()
      setDraft('')
      setNotice(null)
      setHistoryOpen(false)
      setFolderToRemove(null)
      setLibraryToDeleteId(null)
      setOpenLibraryMenuId(null)
    } catch {
      setNotice(t(lang, 'knowledgeBackendPending'))
    } finally {
      setIsBusy(false)
    }
  }

  async function addFolder(): Promise<void> {
    if (selectedLibrary === undefined) {
      return
    }
    setNotice(null)
    try {
      const selections = await window.desktop.chooseWorkspacePath()
      const nextFolders = mergeKnowledgeFolders(selectedLibrary.folders, selections)
      if (selections.length > 0 && nextFolders.length === selectedLibrary.folders.length) {
        const selectedFile = selections.some((selection) => selection.kind === 'file')
        setNotice(
          selectedFile ? t(lang, 'knowledgeFolderOnly') : t(lang, 'knowledgeFolderAlreadyAdded')
        )
        return
      }
      setIsBusy(true)
      for (const folder of nextFolders.slice(selectedLibrary.folders.length)) {
        const source = await window.desktop.addKnowledgeSource(selectedLibrary.id, folder.path)
        try {
          await window.desktop.indexKnowledgeSource(source.source_id)
        } catch {
          await reloadWorkspace(selectedLibrary.id)
          setNotice(t(lang, 'knowledgeIndexStartError'))
          return
        }
      }
      await reloadWorkspace(selectedLibrary.id)
    } catch {
      setNotice(t(lang, 'knowledgeAddFolderError'))
    } finally {
      setIsBusy(false)
    }
  }

  async function confirmFolderRemoval(): Promise<void> {
    if (folderToRemove === null || folderToRemove.sourceId === undefined) {
      return
    }
    try {
      setIsBusy(true)
      await window.desktop.detachKnowledgeSource(folderToRemove.sourceId)
      await reloadWorkspace(selectedLibraryId)
      setFolderToRemove(null)
      setNotice(null)
    } catch {
      setNotice(t(lang, 'knowledgeBackendPending'))
    } finally {
      setIsBusy(false)
    }
  }

  async function startConversation(): Promise<void> {
    if (selectedLibrary === undefined) {
      return
    }
    try {
      setIsBusy(true)
      const conversation = await window.desktop.createKnowledgeConversation(selectedLibrary.id)
      await reloadWorkspace(selectedLibrary.id, conversation.conversation_id)
      setDraft('')
      setNotice(null)
      setHistoryOpen(false)
    } catch {
      setNotice(t(lang, 'knowledgeBackendPending'))
    } finally {
      setIsBusy(false)
    }
  }

  async function submitQuestion(event?: FormEvent): Promise<void> {
    event?.preventDefault()
    const content = draft.trim()
    if (!content || selectedLibrary === undefined || isBusy) {
      return
    }
    try {
      setIsBusy(true)
      let conversation = selectedConversation
      if (conversation === undefined) {
        const created = await window.desktop.createKnowledgeConversation(selectedLibrary.id)
        await reloadWorkspace(selectedLibrary.id, created.conversation_id)
        conversation = { id: created.conversation_id, title: '', messages: [], citations: [] }
      }
      setRunActivity({ runId: null, conversationId: conversation.id, stage: 'searching' })
      const submitted = await window.desktop.submitKnowledgeMessage(conversation.id, content)
      setRunActivity((current) =>
        current?.conversationId === conversation.id && current.runId === null
          ? { ...current, runId: submitted.run.run_id }
          : current
      )
      setDraft('')
      setNotice(null)
      await reloadWorkspace(selectedLibrary.id, conversation.id)
    } catch {
      setRunActivity(null)
      setIsBusy(false)
      setNotice(t(lang, 'knowledgeBackendPending'))
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void submitQuestion()
    }
  }

  return (
    <section className="center knowledge-center-shell">
      <div className="knowledge-workspace">
        {listHost
          ? createPortal(
              <aside className="knowledge-libraries-pane">
                <div className="workspace-list-actions">
                  <button
                    aria-label={t(lang, 'knowledgeNewLibrary')}
                    className="workspace-create-button"
                    onClick={() => {
                      setIsCreatingLibrary((creating) => !creating)
                      setNewLibraryName('')
                      setLibraryCreateError(null)
                      setOpenLibraryMenuId(null)
                    }}
                    title={t(lang, 'knowledgeNewLibrary')}
                    type="button"
                  >
                    <WorkspaceIcon path="M12 5v14M5 12h14" />
                    <span>{t(lang, 'knowledgeNewLibrary')}</span>
                  </button>
                </div>

                {isCreatingLibrary ? (
                  <form className="knowledge-library-create" onSubmit={createLibrary}>
                    <input
                      aria-label={t(lang, 'knowledgeLibraryName')}
                      autoFocus
                      onChange={(event) => {
                        setNewLibraryName(event.target.value)
                        setLibraryCreateError(null)
                      }}
                      placeholder={t(lang, 'knowledgeLibraryNamePlaceholder')}
                      value={newLibraryName}
                    />
                    {libraryCreateError ? (
                      <div className="knowledge-library-form-error">{libraryCreateError}</div>
                    ) : null}
                    <div>
                      <button
                        onClick={() => {
                          setIsCreatingLibrary(false)
                          setNewLibraryName('')
                          setLibraryCreateError(null)
                        }}
                        type="button"
                      >
                        {t(lang, 'cancel')}
                      </button>
                      <button className="primary" disabled={!newLibraryName.trim()} type="submit">
                        {t(lang, 'create')}
                      </button>
                    </div>
                  </form>
                ) : null}

                <div className="knowledge-library-list" role="list">
                  {libraries.map((library) => (
                    <div
                      className={`knowledge-library-item${
                        library.id === selectedLibraryId ? ' active' : ''
                      }${openLibraryMenuId === library.id ? ' menu-open' : ''}`}
                      key={library.id}
                      role="listitem"
                    >
                      <button
                        aria-current={library.id === selectedLibraryId ? 'page' : undefined}
                        className="knowledge-library-select"
                        onClick={() => {
                          selectLibrary(library.id)
                        }}
                        type="button"
                      >
                        <span className="knowledge-library-icon">
                          <WorkspaceIcon path="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2zM22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
                        </span>
                        <span className="knowledge-library-info">
                          <strong>{library.name}</strong>
                          <small>
                            {library.folders.length}{' '}
                            {library.folders.length === 1
                              ? t(lang, 'knowledgeFolderCountSingle')
                              : t(lang, 'knowledgeFolderCount')}
                            {library.documentCount > 0
                              ? ` · ${library.documentCount} ${t(
                                  lang,
                                  library.documentCount === 1
                                    ? 'knowledgeDocumentSingle'
                                    : 'knowledgeDocuments'
                                )}`
                              : ''}
                          </small>
                        </span>
                      </button>
                      <button
                        aria-expanded={openLibraryMenuId === library.id}
                        aria-label={`${t(lang, 'knowledgeLibraryActions')}: ${library.name}`}
                        className="knowledge-library-menu-button"
                        onClick={() =>
                          setOpenLibraryMenuId((openId) =>
                            openId === library.id ? null : library.id
                          )
                        }
                        title={t(lang, 'knowledgeLibraryActions')}
                        type="button"
                      >
                        <WorkspaceIcon path="M5 12h.01M12 12h.01M19 12h.01" />
                      </button>
                      {openLibraryMenuId === library.id ? (
                        <div className="knowledge-library-menu">
                          <button onClick={() => openRenameLibrary(library)} type="button">
                            <WorkspaceIcon path="M4 20h4l11-11-4-4L4 16v4zM13.5 6.5l4 4" />
                            {t(lang, 'knowledgeRenameLibrary')}
                          </button>
                          <button
                            className="danger"
                            disabled={libraries.length === 1}
                            onClick={() => {
                              setLibraryToDeleteId(library.id)
                              setOpenLibraryMenuId(null)
                            }}
                            title={
                              libraries.length === 1
                                ? t(lang, 'knowledgeLastLibraryCannotDelete')
                                : t(lang, 'knowledgeDeleteLibrary')
                            }
                            type="button"
                          >
                            <WorkspaceIcon path="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5" />
                            {t(lang, 'knowledgeDeleteLibrary')}
                          </button>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </aside>,
              listHost
            )
          : null}

        <div className="knowledge-library-content">
          <header className="knowledge-header">
            <div className="knowledge-header-top">
              <div className="knowledge-title-group">
                <h1>{selectedLibrary?.name}</h1>
                <div
                  className={`knowledge-status-chip status-${displayedSyncStatus}`}
                  title={
                    selectedLibraryLastScan !== null
                      ? `${selectedLibrary?.documentCount ?? 0} ${t(
                          lang,
                          selectedLibrary?.documentCount === 1
                            ? 'knowledgeDocumentSingle'
                            : 'knowledgeDocuments'
                        )} · ${t(lang, 'knowledgeUpdated')} ${new Date(selectedLibraryLastScan).toLocaleString()}`
                      : `${selectedLibrary?.documentCount ?? 0} ${t(
                          lang,
                          selectedLibrary?.documentCount === 1
                            ? 'knowledgeDocumentSingle'
                            : 'knowledgeDocuments'
                        )}`
                  }
                >
                  <span className="knowledge-status-dot" />
                  <span className="knowledge-status-text">
                    {displayedSyncStatus === 'updating'
                      ? selectedLibraryProgress !== null &&
                        selectedLibraryProgress.discovered_files > 0
                        ? t(lang, 'knowledgeIndexProgress')
                            .replace('{processed}', String(selectedLibraryProgress.processed_files))
                            .replace(
                              '{discovered}',
                              String(selectedLibraryProgress.discovered_files)
                            )
                            .replace('{chunks}', String(selectedLibraryProgress.indexed_chunks))
                        : selectedLibrary?.folders.some(
                              (folder) => folder.scanStatus === 'indexing'
                            )
                          ? t(lang, 'knowledgeGeneratingEmbeddings')
                          : t(lang, 'knowledgeUpdating')
                      : displayedSyncStatus === 'error'
                        ? t(lang, 'knowledgeNeedsAttention')
                        : displayedSyncStatus === 'empty'
                          ? t(lang, 'knowledgeWaitingForSources')
                          : `${t(lang, 'knowledgeReady')} · ${selectedLibrary?.documentCount ?? 0} ${t(
                              lang,
                              selectedLibrary?.documentCount === 1
                                ? 'knowledgeDocumentSingle'
                                : 'knowledgeDocuments'
                            )}`}
                  </span>
                </div>
              </div>

              <div className="knowledge-header-actions">
                <button
                  className="knowledge-button knowledge-button-secondary"
                  disabled={isBusy}
                  onClick={() => void startConversation()}
                  type="button"
                >
                  <WorkspaceIcon path="M12 5v14M5 12h14" />
                  {t(lang, 'knowledgeNewConversation')}
                </button>
                <button
                  className="knowledge-button knowledge-button-secondary"
                  onClick={() => setHistoryOpen((open) => !open)}
                  type="button"
                >
                  <WorkspaceIcon path="M4 12a8 8 0 1 0 2.34-5.66L4 8.68M4 4v4.68h4.68M12 8v4l2.5 1.5" />
                  {t(lang, 'knowledgeHistory')}
                </button>
              </div>
            </div>

            <div className="knowledge-sources-bar" aria-label={t(lang, 'knowledgeSources')}>
              {selectedLibrary?.folders.length === 0 ? (
                <div className="knowledge-sources-empty">
                  <span>{t(lang, 'knowledgeNoFolders')}</span>
                  <button
                    className="knowledge-add-source-button"
                    onClick={() => void addFolder()}
                    type="button"
                  >
                    <WorkspaceIcon path="M12 5v14M5 12h14" />
                    <span>{t(lang, 'knowledgeAddFolder')}</span>
                  </button>
                </div>
              ) : (
                <div className="knowledge-sources-list">
                  {selectedLibrary?.folders.map((folder) => (
                    <div
                      className="knowledge-source-pill"
                      key={folder.path}
                      title={`${folder.name}\n${folder.path}\n${folder.documentCount ?? 0} ${t(
                        lang,
                        folder.documentCount === 1
                          ? 'knowledgeDocumentSingle'
                          : 'knowledgeDocuments'
                      )} · ${folder.scanStatus ?? 'queued'}`}
                    >
                      <WorkspaceIcon path="M3.5 6.5h6l2 2h9v10h-17z" />
                      <span className="knowledge-source-pill-name">{folder.name}</span>
                      <span className="knowledge-source-pill-badge">
                        {folder.documentCount ?? 0}{' '}
                        {t(
                          lang,
                          folder.documentCount === 1
                            ? 'knowledgeDocumentSingle'
                            : 'knowledgeDocuments'
                        )}
                      </span>
                      <button
                        aria-label={`${t(lang, 'knowledgeRemoveFolder')}: ${folder.name}`}
                        className="knowledge-source-pill-remove"
                        onClick={() => setFolderToRemove(folder)}
                        title={t(lang, 'knowledgeRemoveFolder')}
                        type="button"
                      >
                        <WorkspaceIcon path="M6 6l12 12M18 6 6 18" />
                      </button>
                    </div>
                  ))}
                  <button
                    className="knowledge-add-source-button"
                    onClick={() => void addFolder()}
                    title={t(lang, 'knowledgeAddFolder')}
                    type="button"
                  >
                    <WorkspaceIcon path="M12 5v14M5 12h14" />
                    <span>{t(lang, 'knowledgeAddFolder')}</span>
                  </button>
                </div>
              )}
            </div>
          </header>

          <main className="knowledge-conversation">
            <div className="knowledge-messages" aria-live="polite">
              {(selectedConversation?.messages.length ?? 0) > 0 || visibleRunActivity ? (
                <>
                  {(selectedConversation?.messages ?? []).map((message) => {
                    const citations = citationsForAssistant(
                      selectedConversation?.citations ?? [],
                      message.id
                    )
                    const markdownContent = linkKnowledgeCitationTags(message.content, message.id)
                    return (
                      <div className={`knowledge-message-group ${message.role}`} key={message.id}>
                        <div
                          className={
                            message.role === 'assistant'
                              ? 'knowledge-assistant-message'
                              : 'knowledge-user-message'
                          }
                        >
                          {message.role === 'assistant' ? (
                            <div className="knowledge-markdown-content">
                              <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                components={{
                                  a: ({ children, href }) => (
                                    <a
                                      href={href}
                                      onClick={(event) => {
                                        event.preventDefault()
                                        if (href?.startsWith('#knowledge-citation-')) {
                                          document.querySelector(href)?.scrollIntoView({
                                            behavior: 'smooth',
                                            block: 'center'
                                          })
                                          return
                                        }
                                        if (href) void window.desktop.openExternalLink(href)
                                      }}
                                    >
                                      {children}
                                    </a>
                                  )
                                }}
                              >
                                {markdownContent}
                              </ReactMarkdown>
                            </div>
                          ) : (
                            message.content
                          )}
                        </div>
                        {message.role === 'assistant' ? (
                          <div className="knowledge-answer-meta">
                            {citations.length > 0 ? (
                              <details className="knowledge-answer-sources">
                                <summary>
                                  {t(lang, 'knowledgeSourcesLabel')} <span>{citations.length}</span>
                                </summary>
                                <div className="knowledge-citations">
                                  {citations.map((citation) => (
                                    <details
                                      id={`knowledge-citation-${message.id}-${citation.label}`}
                                      key={`${citation.runId}-${citation.chunkId}`}
                                    >
                                      <summary>
                                        <strong>[{citation.label}]</strong> {citation.documentName}
                                        {citation.pageStart !== null
                                          ? citation.pageEnd !== null &&
                                            citation.pageEnd !== citation.pageStart
                                            ? ` · pp.${citation.pageStart}–${citation.pageEnd}`
                                            : ` · p.${citation.pageStart}`
                                          : ''}
                                      </summary>
                                      {citation.sectionTitle ? (
                                        <em>{citation.sectionTitle}</em>
                                      ) : null}
                                      <p>{citation.snippet}</p>
                                      <small title={citation.sourcePath}>
                                        {citation.sourcePath}
                                      </small>
                                    </details>
                                  ))}
                                </div>
                              </details>
                            ) : null}
                            <button
                              onClick={() => void window.desktop.copyText(message.content)}
                              type="button"
                            >
                              {t(lang, 'knowledgeCopyAnswer')}
                            </button>
                          </div>
                        ) : null}
                      </div>
                    )
                  })}
                  {visibleRunActivity ? (
                    <div className="knowledge-run-activity" role="status">
                      <span aria-hidden="true" className="activity-spinner" />
                      <span>
                        {visibleRunActivity.stage === 'searching'
                          ? t(lang, 'knowledgeSearching')
                          : t(lang, 'knowledgeGeneratingAnswer')}
                      </span>
                    </div>
                  ) : null}
                </>
              ) : (
                <div className="knowledge-empty-state">
                  <div className="knowledge-empty-icon">
                    <WorkspaceIcon path="M4 5.5h16v11H8l-4 3v-14zM8 9h8M8 13h5" />
                  </div>
                  <h2>{t(lang, 'knowledgeAskTitle')}</h2>
                  <p>{t(lang, 'knowledgeAskHint')}</p>
                </div>
              )}
            </div>

            <div className="knowledge-composer-wrap">
              {notice ? <div className="knowledge-notice">{notice}</div> : null}
              <form className="knowledge-composer message-composer" onSubmit={submitQuestion}>
                <textarea
                  aria-label={t(lang, 'knowledgeAskPlaceholder')}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={handleComposerKeyDown}
                  placeholder={t(lang, 'knowledgeAskPlaceholder')}
                  rows={2}
                  value={draft}
                />
                <button
                  aria-label={t(lang, 'sendMessage')}
                  disabled={draft.trim().length === 0 || isBusy}
                  type="submit"
                >
                  <WorkspaceIcon path="M12 19V5M6.5 10.5 12 5l5.5 5.5" />
                </button>
              </form>
            </div>
          </main>

          {historyOpen ? (
            <>
              <button
                aria-label={t(lang, 'knowledgeCloseHistory')}
                className="knowledge-history-backdrop"
                onClick={() => setHistoryOpen(false)}
                type="button"
              />
              <aside className="knowledge-history-drawer">
                <div className="knowledge-history-header">
                  <div>
                    <span>{t(lang, 'knowledgeTitle')}</span>
                    <h2>{t(lang, 'knowledgeHistoryTitle')}</h2>
                  </div>
                  <button
                    aria-label={t(lang, 'knowledgeCloseHistory')}
                    onClick={() => setHistoryOpen(false)}
                    type="button"
                  >
                    <WorkspaceIcon path="M6 6l12 12M18 6 6 18" />
                  </button>
                </div>
                <button className="knowledge-history-new" onClick={startConversation} type="button">
                  <WorkspaceIcon path="M12 5v14M5 12h14" />
                  {t(lang, 'knowledgeNewConversation')}
                </button>
                <div className="knowledge-history-list">
                  {selectedLibrary?.conversations.map((conversation) => (
                    <button
                      className={
                        conversation.id === selectedLibrary.selectedConversationId ? 'active' : ''
                      }
                      key={conversation.id}
                      onClick={() => {
                        updateSelectedLibrary((library) => ({
                          ...library,
                          selectedConversationId: conversation.id
                        }))
                        setNotice(null)
                        setHistoryOpen(false)
                      }}
                      type="button"
                    >
                      <WorkspaceIcon path="M4 5.5h16v11H8l-4 3v-14z" />
                      <span>
                        <strong>{conversation.title}</strong>
                        <small>
                          {conversation.messages.length} {t(lang, 'knowledgeMessageCount')}
                        </small>
                      </span>
                    </button>
                  ))}
                </div>
              </aside>
            </>
          ) : null}

          {folderToRemove ? (
            <>
              <button
                aria-label={t(lang, 'cancel')}
                className="knowledge-remove-backdrop"
                onClick={() => setFolderToRemove(null)}
                type="button"
              />
              <section
                aria-labelledby="knowledge-remove-title"
                aria-modal="true"
                className="knowledge-remove-dialog"
                role="dialog"
              >
                <div className="knowledge-remove-icon">
                  <WorkspaceIcon path="M3.5 6.5h6l2 2h9v10h-17z" />
                </div>
                <h2 id="knowledge-remove-title">{t(lang, 'knowledgeRemoveConfirmTitle')}</h2>
                <div className="knowledge-remove-target" title={folderToRemove.path}>
                  <strong>{folderToRemove.name}</strong>
                  <small>{folderToRemove.path}</small>
                </div>
                <p>{t(lang, 'knowledgeRemoveConfirmBody')}</p>
                <div className="knowledge-remove-preserved">
                  <WorkspaceIcon path="M12 3 5 6v5c0 4.6 2.9 8.1 7 10 4.1-1.9 7-5.4 7-10V6l-7-3zM9 12l2 2 4-4" />
                  <span>{t(lang, 'knowledgeRemoveKeepsIndex')}</span>
                </div>
                <div className="knowledge-remove-actions">
                  <button onClick={() => setFolderToRemove(null)} type="button">
                    {t(lang, 'cancel')}
                  </button>
                  <button className="primary" onClick={confirmFolderRemoval} type="button">
                    {t(lang, 'knowledgeRemoveAction')}
                  </button>
                </div>
              </section>
            </>
          ) : null}
        </div>

        {libraryToRename ? (
          <>
            <button
              aria-label={t(lang, 'cancel')}
              className="knowledge-library-dialog-backdrop"
              onClick={() => setLibraryToRenameId(null)}
              type="button"
            />
            <form
              aria-labelledby="knowledge-rename-library-title"
              aria-modal="true"
              className="knowledge-library-dialog"
              onSubmit={renameLibrary}
              role="dialog"
            >
              <h2 id="knowledge-rename-library-title">{t(lang, 'knowledgeRenameLibraryTitle')}</h2>
              <label htmlFor="knowledge-rename-library-input">
                {t(lang, 'knowledgeLibraryName')}
              </label>
              <input
                autoFocus
                id="knowledge-rename-library-input"
                onChange={(event) => {
                  setRenameLibraryName(event.target.value)
                  setRenameLibraryError(null)
                }}
                value={renameLibraryName}
              />
              {renameLibraryError ? (
                <div className="knowledge-library-form-error">{renameLibraryError}</div>
              ) : null}
              <div className="knowledge-library-dialog-actions">
                <button onClick={() => setLibraryToRenameId(null)} type="button">
                  {t(lang, 'cancel')}
                </button>
                <button className="primary" disabled={!renameLibraryName.trim()} type="submit">
                  {t(lang, 'save')}
                </button>
              </div>
            </form>
          </>
        ) : null}

        {libraryToDelete ? (
          <>
            <button
              aria-label={t(lang, 'cancel')}
              className="knowledge-library-dialog-backdrop"
              onClick={() => setLibraryToDeleteId(null)}
              type="button"
            />
            <section
              aria-labelledby="knowledge-delete-library-title"
              aria-modal="true"
              className="knowledge-library-dialog knowledge-library-delete-dialog"
              role="dialog"
            >
              <div className="knowledge-library-delete-icon">
                <WorkspaceIcon path="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5" />
              </div>
              <h2 id="knowledge-delete-library-title">{t(lang, 'knowledgeDeleteLibraryTitle')}</h2>
              <div className="knowledge-delete-library-name">{libraryToDelete.name}</div>
              <p>{t(lang, 'knowledgeDeleteLibraryBody')}</p>
              <div className="knowledge-delete-library-summary">
                <span>
                  {libraryToDelete.folders.length}{' '}
                  {libraryToDelete.folders.length === 1
                    ? t(lang, 'knowledgeFolderCountSingle')
                    : t(lang, 'knowledgeFolderCount')}
                </span>
                <span aria-hidden="true">·</span>
                <span>
                  {libraryToDelete.conversations.length}{' '}
                  {libraryToDelete.conversations.length === 1
                    ? t(lang, 'knowledgeConversationCountSingle')
                    : t(lang, 'knowledgeConversationCount')}
                </span>
              </div>
              <div className="knowledge-library-files-safe">
                <WorkspaceIcon path="M12 3 5 6v5c0 4.6 2.9 8.1 7 10 4.1-1.9 7-5.4 7-10V6l-7-3zM9 12l2 2 4-4" />
                {t(lang, 'knowledgeLibraryFilesUnaffected')}
              </div>
              <div className="knowledge-library-dialog-actions">
                <button onClick={() => setLibraryToDeleteId(null)} type="button">
                  {t(lang, 'cancel')}
                </button>
                <button className="danger" onClick={confirmLibraryDeletion} type="button">
                  {t(lang, 'knowledgeDeleteLibrary')}
                </button>
              </div>
            </section>
          </>
        ) : null}
      </div>
    </section>
  )
}
