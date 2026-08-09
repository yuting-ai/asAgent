import json
from dataclasses import dataclass

from asagent.agent.cancellation import RunCancellationToken
from asagent.core.run_status import RunStatus
from asagent.models.contracts import (
    ModelMessage,
    ModelMessageRole,
    ModelRequest,
    ModelResponse,
    ModelToolCall,
)
from asagent.models.errors import ProviderTimeoutError
from asagent.models.provider import ModelProvider
from asagent.tools.errors import (
    ToolApprovalDeniedError,
    ToolArgumentsValidationError,
    ToolPermissionDeniedError,
    ToolTimeoutError,
)
from asagent.tools.executor import ToolExecutor
from asagent.tools.snapshot import ToolSnapshot

_TOOL_RESULT_TRUNCATION_MARKER = "\n\n[Tool result truncated]"


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
        max_calls_per_tool_input: int | None = None,
        max_tool_result_chars: int = 4_000,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        if max_calls_per_tool_input is not None and max_calls_per_tool_input < 1:
            raise ValueError("max_calls_per_tool_input must be positive")
        if max_tool_result_chars < len(_TOOL_RESULT_TRUNCATION_MARKER):
            raise ValueError(
                "max_tool_result_chars must fit the truncation marker",
            )

        self._model = model
        self._executor = executor
        self._tool_snapshot = tool_snapshot
        self._max_steps = max_steps
        self._max_calls_per_tool_input = max_calls_per_tool_input
        self._max_tool_result_chars = max_tool_result_chars

    async def run(
        self,
        *,
        model_name: str,
        system_prompt: str,
        messages: tuple[ModelMessage, ...],
        cancellation_token: RunCancellationToken | None = None,
    ) -> AgentLoopResult:
        history = list(messages)
        calls_by_tool_input: dict[tuple[str, str], int] = {}

        for next_step in range(1, self._max_steps + 1):
            if self._is_cancelled(cancellation_token):
                return self._cancelled_result(
                    history,
                    steps_used=next_step - 1,
                )

            try:
                response = await self._model.complete(
                    ModelRequest(
                        model=model_name,
                        system_prompt=system_prompt,
                        messages=tuple(history),
                        tools=self._tool_snapshot.model_tools,
                    ),
                )
            except ProviderTimeoutError:
                if self._is_cancelled(cancellation_token):
                    return self._cancelled_result(
                        history,
                        steps_used=next_step - 1,
                    )

                return AgentLoopResult(
                    status=RunStatus.FAILED,
                    text=None,
                    messages=tuple(history),
                    steps_used=next_step - 1,
                    error="model call timed out",
                )

            steps_used = next_step

            if self._is_cancelled(cancellation_token):
                return self._cancelled_result(
                    history,
                    steps_used=steps_used,
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

            for index, tool_call in enumerate(response.tool_calls):
                if self._is_cancelled(cancellation_token):
                    self._append_cancelled_tool_results(
                        history,
                        response.tool_calls[index:],
                    )
                    return self._cancelled_result(
                        history,
                        steps_used=steps_used,
                    )

                result = self._truncate_tool_result(
                    await self._execute_tool(
                        tool_call,
                        calls_by_tool_input,
                    ),
                )
                history.append(
                    ModelMessage(
                        role=ModelMessageRole.TOOL,
                        content=result,
                        tool_call_id=tool_call.call_id,
                    ),
                )

                if self._is_cancelled(cancellation_token):
                    self._append_cancelled_tool_results(
                        history,
                        response.tool_calls[index + 1 :],
                    )
                    return self._cancelled_result(
                        history,
                        steps_used=steps_used,
                    )

        raise AssertionError("agent loop exhausted unexpectedly")

    async def _execute_tool(
        self,
        tool_call: ModelToolCall,
        calls_by_tool_input: dict[tuple[str, str], int],
    ) -> str:
        try:
            tool_id = self._tool_snapshot.tool_id_for(tool_call.name)
        except KeyError:
            return "Error: requested tool is not in the run snapshot."

        try:
            canonical_arguments = json.dumps(
                dict(tool_call.arguments),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError):
            return "Error: tool arguments are not JSON-compatible."

        call_key = (tool_id, canonical_arguments)
        calls = calls_by_tool_input.get(call_key, 0)
        if (
            self._max_calls_per_tool_input is not None
            and calls >= self._max_calls_per_tool_input
        ):
            return "Error: repeated tool call limit reached."

        calls_by_tool_input[call_key] = calls + 1

        try:
            return await self._executor.execute(tool_id, tool_call.arguments)
        except ToolArgumentsValidationError:
            return "Error: tool arguments are invalid."
        except ToolApprovalDeniedError:
            return "Error: tool approval denied."
        except ToolPermissionDeniedError:
            return "Error: tool permission denied."
        except ToolTimeoutError:
            return "Error: tool execution timed out."
        except Exception:
            return "Error: tool execution failed."

    @staticmethod
    def _is_cancelled(
        cancellation_token: RunCancellationToken | None,
    ) -> bool:
        return cancellation_token is not None and cancellation_token.is_cancelled

    @staticmethod
    def _append_cancelled_tool_results(
        history: list[ModelMessage],
        tool_calls: tuple[ModelToolCall, ...],
    ) -> None:
        for tool_call in tool_calls:
            history.append(
                ModelMessage(
                    role=ModelMessageRole.TOOL,
                    content="Error: tool execution cancelled.",
                    tool_call_id=tool_call.call_id,
                ),
            )

    @staticmethod
    def _cancelled_result(
        history: list[ModelMessage],
        *,
        steps_used: int,
    ) -> AgentLoopResult:
        return AgentLoopResult(
            status=RunStatus.CANCELLED,
            text=None,
            messages=tuple(history),
            steps_used=steps_used,
        )

    def _truncate_tool_result(self, result: str) -> str:
        if len(result) <= self._max_tool_result_chars:
            return result

        prefix_length = self._max_tool_result_chars - len(
            _TOOL_RESULT_TRUNCATION_MARKER
        )
        return result[:prefix_length] + _TOOL_RESULT_TRUNCATION_MARKER

    @staticmethod
    def _invalid_tool_calls_error(response: ModelResponse) -> str | None:
        call_ids = [tool_call.call_id for tool_call in response.tool_calls]

        if any(not call_id for call_id in call_ids):
            return "model response contained an empty tool call id"

        if len(set(call_ids)) != len(call_ids):
            return "model response contained duplicate tool call ids"

        return None
