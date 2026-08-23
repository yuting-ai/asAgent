from typing import NewType

UserId = NewType("UserId", str)
ConversationId = NewType("ConversationId", str)
RunId = NewType("RunId", str)
ToolCallId = NewType("ToolCallId", str)
ApprovalId = NewType("ApprovalId", str)
EventId = NewType("EventId", str)
MessageId = NewType("MessageId", str)
ConnectionId = NewType("ConnectionId", str)
FileChangeId = NewType("FileChangeId", str)
AutomationId = NewType("AutomationId", str)
AutomationTriggerId = NewType("AutomationTriggerId", str)
AutomationExecutionId = NewType("AutomationExecutionId", str)
