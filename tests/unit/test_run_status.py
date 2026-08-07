from asagent.core.run_status import RunStatus


def test_run_status_values_are_stable() -> None:
    assert RunStatus.CREATED.value == "created"
    assert RunStatus.PREPARING.value == "preparing"
    assert RunStatus.CALLING_MODEL.value == "calling_model"
    assert RunStatus.MODEL_RESPONDED.value == "model_responded"
    assert RunStatus.EXECUTING_TOOLS.value == "executing_tools"
    assert RunStatus.APPENDING_RESULTS.value == "appending_results"
    assert RunStatus.COMPLETED.value == "completed"
    assert RunStatus.CANCELLED.value == "cancelled"
    assert RunStatus.FAILED.value == "failed"
    assert RunStatus.LIMIT_REACHED.value == "limit_reached"


def test_only_final_run_outcomes_are_terminal() -> None:
    terminal_statuses = {
        RunStatus.COMPLETED,
        RunStatus.CANCELLED,
        RunStatus.FAILED,
        RunStatus.LIMIT_REACHED,
    }

    for status in RunStatus:
        assert status.is_terminal is (status in terminal_statuses)


def test_limit_reached_is_terminal() -> None:
    assert RunStatus.LIMIT_REACHED.is_terminal
