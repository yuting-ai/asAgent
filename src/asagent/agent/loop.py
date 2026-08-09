import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime

from asagent.agent.cancellation import RunCancellationToken
from asagent.core.event_publisher import EventPublisher
from asagent.core.ids import ConversationId, EventId, RunId, ToolCallId
from asagent.core.run_event import RunEvent
from asagent.core.run_status import RunStatus
from asagent.core.tool_call import ToolCall
from asagent.core.tool_call_recorder import ToolCallRecorder
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


@dataclass(frozen=True, slots=True)
class _ToolExecutionResult:
    content: str
    succeeded: bool
    tool_id: str | None


class _EventPublishError(RuntimeError):
    pass


class _ToolCallRecordError(RuntimeError):
    pass


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
        event_publisher: EventPublisher | None = None,
        event_id_factory: Callable[[], EventId] | None = None,
        clock: Callable[[], datetime] | None = None,
        tool_call_recorder: ToolCallRecorder | None = None,
        tool_call_id_factory: Callable[[], ToolCallId] | None = None,
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
        self._event_publisher = event_publisher
        self._event_id_factory = event_id_factory
        self._clock = clock
        self._tool_call_recorder = tool_call_recorder
        self._tool_call_id_factory = tool_call_id_factory

    async def run(
        self,
        *,
        model_name: str,
        system_prompt: str,
        messages: tuple[ModelMessage, ...],
        cancellation_token: RunCancellationToken | None = None,
        run_id: RunId | None = None,
        conversation_id: ConversationId | None = None,
    ) -> AgentLoopResult:
        if self._event_publisher is not None and (
            run_id is None
            or conversation_id is None
            or self._event_id_factory is None
            or self._clock is None
        ):
            raise ValueError(
                "event publishing requires run_id, conversation_id, "
                "event_id_factory, and clock",
            )

        if self._tool_call_recorder is not None and (
            run_id is None or self._tool_call_id_factory is None or self._clock is None
        ):
            raise ValueError(
                "tool call recording requires run_id, tool_call_id_factory, and clock",
            )

        history = list(messages)
        calls_by_tool_input: dict[tuple[str, str], int] = {}
        event_sequence = 0
        steps_used = 0

        async def publish(
            event_type: str,
            data: Mapping[str, object],
        ) -> None:
            nonlocal event_sequence

            if self._event_publisher is None:
                return

            assert run_id is not None
            assert conversation_id is not None
            assert self._event_id_factory is not None
            assert self._clock is not None

            event_sequence += 1
            event = RunEvent(
                event_id=self._event_id_factory(),
                run_id=run_id,
                conversation_id=conversation_id,
                sequence=event_sequence,
                event_type=event_type,
                created_at=self._clock(),
                data=data,
            )
            try:
                await self._event_publisher.publish(event)
            except Exception as error:
                raise _EventPublishError("run event publishing failed") from error

        async def result(
            status: RunStatus,
            text: str | None,
            error: str | None = None,
        ) -> AgentLoopResult:
            await publish(
                {
                    RunStatus.COMPLETED: "run.completed",
                    RunStatus.FAILED: "run.failed",
                    RunStatus.CANCELLED: "run.cancelled",
                    RunStatus.LIMIT_REACHED: "run.limit_reached",
                }[status],
                {"steps_used": steps_used},
            )
            return AgentLoopResult(
                status=status,
                text=text,
                messages=tuple(history),
                steps_used=steps_used,
                error=error,
            )

        try:
            await publish("run.started", {})

            for next_step in range(1, self._max_steps + 1):
                if self._is_cancelled(cancellation_token):
                    return await result(RunStatus.CANCELLED, None)

                await publish("model.requested", {"step": next_step})
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
                        return await result(RunStatus.CANCELLED, None)

                    return await result(
                        RunStatus.FAILED,
                        None,
                        "model call timed out",
                    )

                steps_used = next_step
                await publish(
                    "model.completed",
                    {
                        "step": steps_used,
                        "tool_call_count": len(response.tool_calls),
                    },
                )

                if self._is_cancelled(cancellation_token):
                    return await result(RunStatus.CANCELLED, None)

                invalid_error = self._invalid_tool_calls_error(response)
                if invalid_error is not None:
                    return await result(
                        RunStatus.FAILED,
                        None,
                        invalid_error,
                    )

                assistant_message = ModelMessage(
                    role=ModelMessageRole.ASSISTANT,
                    content=response.text,
                    tool_calls=response.tool_calls,
                )
                history.append(assistant_message)

                if not response.tool_calls:
                    if response.text is None:
                        return await result(
                            RunStatus.FAILED,
                            None,
                            "model response contained no text or tool calls",
                        )

                    return await result(RunStatus.COMPLETED, response.text)

                if steps_used == self._max_steps:
                    return await result(RunStatus.LIMIT_REACHED, response.text)

                for index, tool_call in enumerate(response.tool_calls):
                    if self._is_cancelled(cancellation_token):
                        self._append_cancelled_tool_results(
                            history,
                            response.tool_calls[index:],
                        )
                        return await result(RunStatus.CANCELLED, None)

                    await publish(
                        "tool.requested",
                        {
                            "tool_call_id": tool_call.call_id,
                            "provider_tool_name": tool_call.name,
                        },
                    )
                    execution = await self._execute_tool(
                        tool_call,
                        calls_by_tool_input,
                    )
                    event_data: dict[str, object] = {
                        "tool_call_id": tool_call.call_id,
                    }
                    if execution.tool_id is not None:
                        event_data["tool_id"] = execution.tool_id
                    await publish(
                        ("tool.completed" if execution.succeeded else "tool.failed"),
                        event_data,
                    )
                    await self._record_tool_call(
                        run_id=run_id,
                        model_call=tool_call,
                        execution=execution,
                    )
                    history.append(
                        ModelMessage(
                            role=ModelMessageRole.TOOL,
                            content=self._truncate_tool_result(execution.content),
                            tool_call_id=tool_call.call_id,
                        ),
                    )

                    if self._is_cancelled(cancellation_token):
                        self._append_cancelled_tool_results(
                            history,
                            response.tool_calls[index + 1 :],
                        )
                        return await result(RunStatus.CANCELLED, None)

            raise AssertionError("agent loop exhausted unexpectedly")
        except _EventPublishError:
            return AgentLoopResult(
                status=RunStatus.FAILED,
                text=None,
                messages=tuple(history),
                steps_used=steps_used,
                error="run event publishing failed",
            )
        except _ToolCallRecordError:
            return AgentLoopResult(
                status=RunStatus.FAILED,
                text=None,
                messages=tuple(history),
                steps_used=steps_used,
                error="tool call recording failed",
            )

    async def _record_tool_call(
        self,
        *,
        run_id: RunId | None,
        model_call: ModelToolCall,
        execution: _ToolExecutionResult,
    ) -> None:
        if self._tool_call_recorder is None or execution.tool_id is None:
            return

        assert run_id is not None
        assert self._tool_call_id_factory is not None
        assert self._clock is not None
        completed_at = self._clock()
        tool_call = ToolCall(
            tool_call_id=self._tool_call_id_factory(),
            run_id=run_id,
            model_call_id=model_call.call_id,
            tool_id=execution.tool_id,
            arguments=model_call.arguments,
            result=execution.content if execution.succeeded else None,
            error=None if execution.succeeded else execution.content,
            created_at=completed_at,
            completed_at=completed_at,
        )
        try:
            await self._tool_call_recorder.record(tool_call)
        except Exception as error:
            raise _ToolCallRecordError("tool call recording failed") from error

    async def _execute_tool(
        self,
        tool_call: ModelToolCall,
        calls_by_tool_input: dict[tuple[str, str], int],
    ) -> _ToolExecutionResult:
        try:
            tool_id = self._tool_snapshot.tool_id_for(tool_call.name)
        except KeyError:
            return _ToolExecutionResult(
                content="Error: requested tool is not in the run snapshot.",
                succeeded=False,
                tool_id=None,
            )

        try:
            canonical_arguments = json.dumps(
                dict(tool_call.arguments),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError):
            return _ToolExecutionResult(
                content="Error: tool arguments are not JSON-compatible.",
                succeeded=False,
                tool_id=tool_id,
            )

        call_key = (tool_id, canonical_arguments)
        calls = calls_by_tool_input.get(call_key, 0)
        if (
            self._max_calls_per_tool_input is not None
            and calls >= self._max_calls_per_tool_input
        ):
            return _ToolExecutionResult(
                content="Error: repeated tool call limit reached.",
                succeeded=False,
                tool_id=tool_id,
            )

        calls_by_tool_input[call_key] = calls + 1

        try:
            return _ToolExecutionResult(
                content=await self._executor.execute(tool_id, tool_call.arguments),
                succeeded=True,
                tool_id=tool_id,
            )
        except ToolArgumentsValidationError:
            return _ToolExecutionResult(
                content="Error: tool arguments are invalid.",
                succeeded=False,
                tool_id=tool_id,
            )
        except ToolApprovalDeniedError:
            return _ToolExecutionResult(
                content="Error: tool approval denied.",
                succeeded=False,
                tool_id=tool_id,
            )
        except ToolPermissionDeniedError:
            return _ToolExecutionResult(
                content="Error: tool permission denied.",
                succeeded=False,
                tool_id=tool_id,
            )
        except ToolTimeoutError:
            return _ToolExecutionResult(
                content="Error: tool execution timed out.",
                succeeded=False,
                tool_id=tool_id,
            )
        except Exception:
            return _ToolExecutionResult(
                content="Error: tool execution failed.",
                succeeded=False,
                tool_id=tool_id,
            )

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
