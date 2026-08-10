from dataclasses import FrozenInstanceError

import pytest

from asagent.agent.context_history import (
    ContextHistoryUnit,
    ContextHistoryValidationError,
    group_context_history,
)
from asagent.models.contracts import (
    ModelMessage,
    ModelMessageRole,
    ModelToolCall,
)


def _user(content: str) -> ModelMessage:
    return ModelMessage(role=ModelMessageRole.USER, content=content)


def _assistant(content: str) -> ModelMessage:
    return ModelMessage(role=ModelMessageRole.ASSISTANT, content=content)


def _tool_call(call_id: str) -> ModelToolCall:
    return ModelToolCall(
        call_id=call_id,
        name="builtin_calculator",
        arguments={"expression": "2 + 2"},
    )


def _assistant_tool_calls(*call_ids: str) -> ModelMessage:
    return ModelMessage(
        role=ModelMessageRole.ASSISTANT,
        content=None,
        tool_calls=tuple(_tool_call(call_id) for call_id in call_ids),
    )


def _tool_result(call_id: str, content: str = "4") -> ModelMessage:
    return ModelMessage(
        role=ModelMessageRole.TOOL,
        content=content,
        tool_call_id=call_id,
    )


def test_empty_history_has_no_units() -> None:
    assert group_context_history(()) == ()


def test_history_is_grouped_by_complete_user_initiated_turns() -> None:
    first_user = _user("calculate 2 + 2")
    tool_request = _assistant_tool_calls("call-1", "call-2")
    first_tool_result = _tool_result("call-1")
    second_tool_result = _tool_result("call-2", "5")
    first_answer = _assistant("The results are 4 and 5.")
    second_user = _user("thanks")
    second_answer = _assistant("You're welcome.")

    units = group_context_history(
        (
            first_user,
            tool_request,
            first_tool_result,
            second_tool_result,
            first_answer,
            second_user,
            second_answer,
        ),
    )

    assert units == (
        ContextHistoryUnit(
            messages=(
                first_user,
                tool_request,
                first_tool_result,
                second_tool_result,
                first_answer,
            ),
        ),
        ContextHistoryUnit(messages=(second_user, second_answer)),
    )


def test_context_history_unit_is_immutable() -> None:
    unit = ContextHistoryUnit(messages=(_user("hello"),))

    with pytest.raises(FrozenInstanceError):
        unit.messages = ()  # type: ignore[misc]


@pytest.mark.parametrize(
    ("messages", "message"),
    [
        (
            (_assistant("hello"),),
            "start with a user message",
        ),
        (
            (
                _user("hello"),
                ModelMessage(role=ModelMessageRole.SYSTEM, content="system"),
            ),
            "must not contain system messages",
        ),
        (
            (
                _user("calculate"),
                _assistant_tool_calls("call-1"),
            ),
            "missing matching tool results",
        ),
        (
            (
                _user("calculate"),
                _assistant_tool_calls("call-1"),
                _tool_result("other-call"),
            ),
            "does not match the expected tool call",
        ),
        (
            (
                _user("calculate"),
                _tool_result("call-1"),
            ),
            "must follow assistant tool calls",
        ),
    ],
)
def test_history_rejects_invalid_tool_call_chains(
    messages: tuple[ModelMessage, ...],
    message: str,
) -> None:
    with pytest.raises(ContextHistoryValidationError, match=message):
        group_context_history(messages)


def test_history_rejects_duplicate_tool_call_ids_in_one_assistant_message() -> None:
    with pytest.raises(
        ContextHistoryValidationError,
        match="must be unique",
    ):
        group_context_history(
            (
                _user("calculate"),
                _assistant_tool_calls("call-1", "call-1"),
                _tool_result("call-1"),
                _tool_result("call-1"),
            ),
        )
