export type ToolApprovalDecision = 'allow_once' | 'allow_conversation' | 'deny'

export const TOOL_APPROVAL_BANNER_ACTIONS: readonly {
  decision: ToolApprovalDecision
  label: string
  className: string
}[] = [
  { decision: 'deny', label: 'Deny', className: 'tool-approval-deny' },
  {
    decision: 'allow_conversation',
    label: 'Allow for this conversation',
    className: 'tool-approval-allow-conversation'
  },
  { decision: 'allow_once', label: 'Allow once', className: 'tool-approval-allow' }
]
