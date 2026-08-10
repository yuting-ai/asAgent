from collections.abc import Iterator

import pytest

from asagent.cli import (
    ConsoleEventPublisher,
    build_development_agent_loop,
    parse_args,
    run_agent_chat,
)
from asagent.core.ids import ConversationId, RunId


@pytest.mark.asyncio
async def test_development_agent_cli_runs_tools_and_prints_events() -> None:
    inputs = iter(("calculate 2 * (3 + 4)", "hello", "exit"))
    run_ids = _run_ids()
    output: list[str] = []
    publisher = ConsoleEventPublisher(output.append)

    await run_agent_chat(
        agent_loop=build_development_agent_loop(event_publisher=publisher),
        conversation_id=ConversationId("conv_123"),
        model_name="development-tools",
        system_prompt="Use tools.",
        read_line=lambda prompt: _next_input(inputs, prompt),
        write_line=output.append,
        new_run_id=lambda: next(run_ids),
    )

    assert output[0] == "asAgent development agent. Type 'exit' to quit."
    assert "asAgent: Tool result: 14" in output
    assert "asAgent: Tool result: Echo: hello" in output
    assert "[event 1] run.started {}" in output
    assert any("tool.requested" in line for line in output)
    assert any("tool.completed" in line for line in output)
    assert output.count('[event 8] run.completed {"steps_used": 2}') == 2


def test_parse_args_supports_an_explicit_persistent_real_provider() -> None:
    args = parse_args(
        (
            "--persistent",
            "--profile",
            "deepseek",
            "--secret-env",
            "ASAGENT_MODEL_API_KEY",
            "--conversation-id",
            "conv_existing",
            "--app-home",
            "custom-app-home",
        ),
    )

    assert args.persistent is True
    assert args.profile == "deepseek"
    assert args.secret_env == "ASAGENT_MODEL_API_KEY"
    assert args.conversation_id == "conv_existing"
    assert str(args.app_home) == "custom-app-home"


def _next_input(inputs: Iterator[str], prompt: str) -> str:
    assert prompt == "You: "
    return next(inputs)


def _run_ids() -> Iterator[RunId]:
    return iter((RunId("run_1"), RunId("run_2")))
