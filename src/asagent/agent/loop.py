from dataclasses import dataclass

from asagent.core.run_status import RunStatus
from asagent.models.contracts import (
    ModelMessage,
    ModelMessageRole,
    ModelRequest,
    ModelResponse,
    ModelToolCall,
)
from asagent.models.provider import ModelProvider
from asagent.tools.executor import ToolExecutor
from asagent.tools.snapshot import ToolSnapshot


@dataclass(frozen=True, slots=True)
class AgentLoopResult:
    status: RunStatus
    text: str | None
    messages: tuple[ModelMessage, ...]
    steps_used: int
    error: str | None = None


class AgentLoop:
    def __init__(
        self,
        *,
        model: ModelProvider,
        executor: ToolExecutor,
        tool_snapshot: ToolSnapshot,
        max_steps: int = 8,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")

        self._model = model
        self._executor = executor
        self._tool_snapshot = tool_snapshot
        self._max_steps = max_steps

    async def run(
        self,
        *,
        model_name: str,
        system_prompt: str,
        messages: tuple[ModelMessage, ...],
    ) -> AgentLoopResult:
        history = list(messages)

        for steps_used in range(1, self._max_steps + 1):
            response = await self._model.complete(
                ModelRequest(
                    model=model_name,
                    system_prompt=system_prompt,
                    messages=tuple(history),
                    tools=self._tool_snapshot.model_tools,
                ),
            )

            invalid_error = self._invalid_tool_calls_error(response)
            if invalid_error is not None:
                return AgentLoopResult(
                    status=RunStatus.FAILED,
                    text=None,
                    messages=tuple(history),
                    steps_used=steps_used,
                    error=invalid_error,
                )

            assistant_message = ModelMessage(
                role=ModelMessageRole.ASSISTANT,
                content=response.text,
                tool_calls=response.tool_calls,
            )
            history.append(assistant_message)

            if not response.tool_calls:
                if response.text is None:
                    return AgentLoopResult(
                        status=RunStatus.FAILED,
                        text=None,
                        messages=tuple(history),
                        steps_used=steps_used,
                        error="model response contained no text or tool calls",
                    )

                return AgentLoopResult(
                    status=RunStatus.COMPLETED,
                    text=response.text,
                    messages=tuple(history),
                    steps_used=steps_used,
                )

            if steps_used == self._max_steps:
                return AgentLoopResult(
                    status=RunStatus.LIMIT_REACHED,
                    text=response.text,
                    messages=tuple(history),
                    steps_used=steps_used,
                )

            for tool_call in response.tool_calls:
                result = await self._execute_tool(tool_call)
                history.append(
                    ModelMessage(
                        role=ModelMessageRole.TOOL,
                        content=result,
                        tool_call_id=tool_call.call_id,
                    ),
                )

        raise AssertionError("agent loop exhausted unexpectedly")

    async def _execute_tool(self, tool_call: ModelToolCall) -> str:
        try:
            tool_id = self._tool_snapshot.tool_id_for(tool_call.name)
        except KeyError:
            return "Error: requested tool is not in the run snapshot."

        try:
            return await self._executor.execute(tool_id, tool_call.arguments)
        except Exception:
            return "Error: tool execution failed."

    @staticmethod
    def _invalid_tool_calls_error(response: ModelResponse) -> str | None:
        call_ids = [tool_call.call_id for tool_call in response.tool_calls]

        if any(not call_id for call_id in call_ids):
            return "model response contained an empty tool call id"

        if len(set(call_ids)) != len(call_ids):
            return "model response contained duplicate tool call ids"

        return None
