from dataclasses import dataclass

from asagent.models.contracts import ModelMessage, ModelMessageRole


class ContextHistoryValidationError(ValueError):
    """Raised when model-message history cannot be safely sent or trimmed."""


@dataclass(frozen=True, slots=True)
class ContextHistoryUnit:
    """One complete user-initiated history unit safe to retain or discard whole."""

    messages: tuple[ModelMessage, ...]

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("context history units require at least one message")
        if self.messages[0].role is not ModelMessageRole.USER:
            raise ValueError("context history units must start with a user message")


def group_context_history(
    messages: tuple[ModelMessage, ...],
) -> tuple[ContextHistoryUnit, ...]:
    """Validate history and group it into complete user-initiated units."""

    _validate_context_history(messages)

    if not messages:
        return ()

    units: list[ContextHistoryUnit] = []
    unit_start = 0

    for index, message in enumerate(messages[1:], start=1):
        if message.role is ModelMessageRole.USER:
            units.append(ContextHistoryUnit(messages=messages[unit_start:index]))
            unit_start = index

    units.append(ContextHistoryUnit(messages=messages[unit_start:]))
    return tuple(units)


def _validate_context_history(messages: tuple[ModelMessage, ...]) -> None:
    if not messages:
        return

    if messages[0].role is not ModelMessageRole.USER:
        raise ContextHistoryValidationError(
            "context history must start with a user message",
        )

    expected_tool_call_ids: tuple[str, ...] = ()
    next_tool_result_index = 0

    for message in messages:
        if message.role is ModelMessageRole.SYSTEM:
            raise ContextHistoryValidationError(
                "context history must not contain system messages",
            )

        if expected_tool_call_ids:
            if message.role is not ModelMessageRole.TOOL:
                raise ContextHistoryValidationError(
                    "assistant tool calls must be followed by matching tool results",
                )

            expected_tool_call_id = expected_tool_call_ids[next_tool_result_index]
            if message.tool_call_id != expected_tool_call_id:
                raise ContextHistoryValidationError(
                    "tool result does not match the expected tool call",
                )

            next_tool_result_index += 1
            if next_tool_result_index == len(expected_tool_call_ids):
                expected_tool_call_ids = ()
                next_tool_result_index = 0
            continue

        if message.role is ModelMessageRole.TOOL:
            raise ContextHistoryValidationError(
                "tool results must follow assistant tool calls",
            )

        if message.role is not ModelMessageRole.ASSISTANT or not message.tool_calls:
            continue

        tool_call_ids = tuple(tool_call.call_id for tool_call in message.tool_calls)
        if len(set(tool_call_ids)) != len(tool_call_ids):
            raise ContextHistoryValidationError(
                "assistant tool call ids must be unique within one message",
            )

        expected_tool_call_ids = tool_call_ids

    if expected_tool_call_ids:
        raise ContextHistoryValidationError(
            "assistant tool calls are missing matching tool results",
        )
