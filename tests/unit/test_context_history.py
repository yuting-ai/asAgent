from dataclasses import FrozenInstanceError

import pytest

from asagent.agent.context_budget import ConservativeUtf8TokenEstimator
from asagent.agent.context_history import (
    ContextHistorySelection,
    ContextHistoryUnit,
    ContextHistoryValidationError,
    group_context_history,
    select_recent_context_history,
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


def _unit_tokens(unit: ContextHistoryUnit) -> int:
    estimator = ConservativeUtf8TokenEstimator()
    return sum(estimator.estimate_message(message) for message in unit.messages)


def test_selection_keeps_the_newest_complete_units_in_history_order() -> None:
    oldest_unit = ContextHistoryUnit(
        messages=(
            _user("old question"),
            _assistant("old answer"),
        ),
    )
    tool_unit = ContextHistoryUnit(
        messages=(
            _user("calculate 2 + 2"),
            _assistant_tool_calls("call-1"),
            _tool_result("call-1"),
            _assistant("The answer is 4."),
        ),
    )
    newest_unit = ContextHistoryUnit(
        messages=(
            _user("new question"),
            _assistant("new answer"),
        ),
    )
    units = (oldest_unit, tool_unit, newest_unit)

    selection = select_recent_context_history(
        units=units,
        max_message_tokens=_unit_tokens(tool_unit) + _unit_tokens(newest_unit),
        estimator=ConservativeUtf8TokenEstimator(),
    )

    assert selection.units == (tool_unit, newest_unit)
    assert selection.messages == tool_unit.messages + newest_unit.messages
    assert selection.message_tokens == (
        _unit_tokens(tool_unit) + _unit_tokens(newest_unit)
    )
    assert selection.omitted_unit_count == 1


def test_selection_never_splits_a_tool_call_chain() -> None:
    tool_unit = ContextHistoryUnit(
        messages=(
            _user("calculate 2 + 2"),
            _assistant_tool_calls("call-1"),
            _tool_result("call-1"),
            _assistant("The answer is 4."),
        ),
    )

    selection = select_recent_context_history(
        units=(tool_unit,),
        max_message_tokens=_unit_tokens(tool_unit) - 1,
        estimator=ConservativeUtf8TokenEstimator(),
    )

    assert selection.units == ()
    assert selection.messages == ()
    assert selection.message_tokens == 0
    assert selection.omitted_unit_count == 1


def test_selection_stops_when_the_newest_unit_does_not_fit() -> None:
    oldest_unit = ContextHistoryUnit(messages=(_user("old"), _assistant("answer")))
    newest_unit = ContextHistoryUnit(
        messages=(
            _user("newest question"),
            _assistant("newest answer"),
        ),
    )

    selection = select_recent_context_history(
        units=(oldest_unit, newest_unit),
        max_message_tokens=_unit_tokens(newest_unit) - 1,
        estimator=ConservativeUtf8TokenEstimator(),
    )

    assert selection.units == ()
    assert selection.omitted_unit_count == 2


def test_selection_supports_empty_history_and_zero_budget() -> None:
    empty_selection = select_recent_context_history(
        units=(),
        max_message_tokens=0,
        estimator=ConservativeUtf8TokenEstimator(),
    )
    unit = ContextHistoryUnit(messages=(_user("hello"),))

    zero_budget_selection = select_recent_context_history(
        units=(unit,),
        max_message_tokens=0,
        estimator=ConservativeUtf8TokenEstimator(),
    )

    assert empty_selection == ContextHistorySelection(
        units=(),
        message_tokens=0,
        omitted_unit_count=0,
    )
    assert zero_budget_selection == ContextHistorySelection(
        units=(),
        message_tokens=0,
        omitted_unit_count=1,
    )


def test_selection_rejects_a_negative_budget_and_is_immutable() -> None:
    with pytest.raises(ValueError, match="max_message_tokens"):
        select_recent_context_history(
            units=(),
            max_message_tokens=-1,
            estimator=ConservativeUtf8TokenEstimator(),
        )

    selection = ContextHistorySelection(
        units=(),
        message_tokens=0,
        omitted_unit_count=0,
    )

    with pytest.raises(FrozenInstanceError):
        selection.message_tokens = 1  # type: ignore[misc]
