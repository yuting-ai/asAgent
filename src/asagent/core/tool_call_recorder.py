from typing import Protocol, runtime_checkable

from asagent.core.tool_call import ToolCall


@runtime_checkable
class ToolCallRecorder(Protocol):
    async def record(self, tool_call: ToolCall) -> None: ...
