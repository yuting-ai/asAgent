from asagent.core.repositories import RunRepository
from asagent.core.tool_call import ToolCall


class RepositoryToolCallRecorder:
    def __init__(self, repository: RunRepository) -> None:
        self._repository = repository

    async def record(self, tool_call: ToolCall) -> None:
        await self._repository.save_tool_call(tool_call)
