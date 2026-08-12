import { contextBridge, ipcRenderer } from 'electron'

type ConversationSummary = {
  conversation_id: string
  created_at: string
  updated_at: string
  title: string | null
}

type ConversationMessage = {
  message_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

type SubmittedMessage = {
  message: ConversationMessage
  run: {
    run_id: string
    status: string
    created_at: string
    updated_at: string
  }
  conversation: ConversationSummary
}

type RunUpdate = {
  runId: string
  conversationId: string
  event: {
    event_type: string
    sequence: number
  }
}

type RunStreamError = {
  runId: string
  conversationId: string
  message: string
}

type ToolApproval = {
  approval_id: string
  run_id: string
  conversation_id: string
  tool_call_id: string
  tool_id: string
  display_name: string
  description: string
  arguments: Record<string, unknown>
}

const desktopBridge = {
  getAppInfo: (): Promise<{
    appName: string
    version: string
    dataProcessingMode: 'local' | 'external'
  }> => ipcRenderer.invoke('desktop:get-app-info'),
  getBackendStatus: (): Promise<{ status: 'ready' | 'unavailable' }> =>
    ipcRenderer.invoke('desktop:get-backend-status'),
  listConversations: (): Promise<ConversationSummary[]> =>
    ipcRenderer.invoke('desktop:list-conversations'),
  listConversationMessages: (conversationId: string): Promise<ConversationMessage[]> =>
    ipcRenderer.invoke('desktop:list-conversation-messages', conversationId),
  createConversation: (): Promise<ConversationSummary> =>
    ipcRenderer.invoke('desktop:create-conversation'),
  submitMessage: (conversationId: string, content: string): Promise<SubmittedMessage> =>
    ipcRenderer.invoke('desktop:submit-message', conversationId, content),
  cancelRun: (runId: string): Promise<void> => ipcRenderer.invoke('desktop:cancel-run', runId),
  decideToolApproval: (approvalId: string, approved: boolean): Promise<void> =>
    ipcRenderer.invoke('desktop:decide-tool-approval', approvalId, approved),
  onRunEvent: (callback: (update: RunUpdate) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, update: RunUpdate): void => {
      callback(update)
    }

    ipcRenderer.on('desktop:run-event', listener)
    return () => ipcRenderer.removeListener('desktop:run-event', listener)
  },
  onRunStreamError: (callback: (error: RunStreamError) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, error: RunStreamError): void => {
      callback(error)
    }

    ipcRenderer.on('desktop:run-stream-error', listener)
    return () => ipcRenderer.removeListener('desktop:run-stream-error', listener)
  },
  onToolApprovalRequested: (callback: (approval: ToolApproval) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, approval: ToolApproval): void => {
      callback(approval)
    }

    ipcRenderer.on('desktop:tool-approval-requested', listener)
    return () => ipcRenderer.removeListener('desktop:tool-approval-requested', listener)
  },
  onToolApprovalError: (callback: (error: RunStreamError) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, error: RunStreamError): void => {
      callback(error)
    }

    ipcRenderer.on('desktop:tool-approval-error', listener)
    return () => ipcRenderer.removeListener('desktop:tool-approval-error', listener)
  }
}

contextBridge.exposeInMainWorld('desktop', desktopBridge)
