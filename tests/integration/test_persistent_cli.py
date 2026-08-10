from collections.abc import Iterator
from pathlib import Path

import pytest

from asagent.cli import (
    _alembic_config_path,
    build_persistent_agent_runtime,
    build_persistent_development_runtime,
    get_or_create_persistent_conversation,
    run_persistent_agent_chat,
)
from asagent.core.ids import ConversationId
from asagent.models.contracts import ModelResponse
from asagent.models.fake_provider import FakeModelProvider
from asagent.paths import AppPaths
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.database import upgrade_sqlite_database
from asagent.storage.sqlite.run_finisher import SqliteRunFinisher
from asagent.storage.sqlite.run_repository import SqliteRunRepository
from asagent.storage.sqlite.run_starter import SqliteRunStarter


@pytest.mark.asyncio
async def test_persistent_cli_reuses_conversation_across_instances(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app-home")
    database_path = paths.data_dir / "asagent.sqlite3"
    upgrade_sqlite_database(
        database_path=database_path,
        alembic_config_path=_alembic_config_path(),
    )

    first_output: list[str] = []
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    finisher = SqliteRunFinisher(database_path)

    try:
        conversation = await get_or_create_persistent_conversation(
            conversations=conversations,
            conversation_id=None,
        )
        inputs = iter(("calculate 2 * (3 + 4)", "exit"))
        await run_persistent_agent_chat(
            runtime=build_persistent_development_runtime(
                conversations=conversations,
                runs=runs,
                starter=starter,
                finisher=finisher,
            ),
            conversation_id=conversation.conversation_id,
            model_name="development-tools",
            system_prompt="Use tools.",
            read_line=lambda prompt: _next_input(inputs, prompt),
            write_line=first_output.append,
        )
    finally:
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()

    second_output: list[str] = []
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    finisher = SqliteRunFinisher(database_path)

    try:
        reused = await get_or_create_persistent_conversation(
            conversations=conversations,
            conversation_id=conversation.conversation_id,
        )
        assert reused == conversation

        inputs = iter(("hello", "exit"))
        await run_persistent_agent_chat(
            runtime=build_persistent_development_runtime(
                conversations=conversations,
                runs=runs,
                starter=starter,
                finisher=finisher,
            ),
            conversation_id=reused.conversation_id,
            model_name="development-tools",
            system_prompt="Use tools.",
            read_line=lambda prompt: _next_input(inputs, prompt),
            write_line=second_output.append,
        )

        messages = await conversations.list_messages(conversation.conversation_id)
        persisted_runs = await runs.list_for_conversation(
            conversation.conversation_id,
        )

        assert first_output[0].startswith(
            "asAgent persistent agent. Conversation: ",
        )
        assert "asAgent: Tool result: 14" in first_output
        assert "asAgent: Tool result: Echo: hello" in second_output
        assert tuple(message.content for message in messages) == (
            "calculate 2 * (3 + 4)",
            "Tool result: 14",
            "hello",
            "Tool result: Echo: hello",
        )
        assert len(persisted_runs) == 2
        assert all(run.status.value == "completed" for run in persisted_runs)
    finally:
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_persistent_cli_rejects_unknown_conversation(tmp_path: Path) -> None:
    paths = AppPaths.from_root(tmp_path / "app-home")
    database_path = paths.data_dir / "asagent.sqlite3"
    upgrade_sqlite_database(
        database_path=database_path,
        alembic_config_path=_alembic_config_path(),
    )
    conversations = SqliteConversationRepository(database_path)

    try:
        with pytest.raises(ValueError, match="requested conversation"):
            await get_or_create_persistent_conversation(
                conversations=conversations,
                conversation_id=ConversationId("missing"),
            )
    finally:
        await conversations.aclose()


@pytest.mark.asyncio
async def test_persistent_runtime_persists_generic_model_provider_response(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app-home")
    database_path = paths.data_dir / "asagent.sqlite3"
    upgrade_sqlite_database(
        database_path=database_path,
        alembic_config_path=_alembic_config_path(),
    )

    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    finisher = SqliteRunFinisher(database_path)
    provider = FakeModelProvider(
        responses=(ModelResponse(text="Persisted provider reply", tool_calls=()),),
    )
    output: list[str] = []

    try:
        conversation = await get_or_create_persistent_conversation(
            conversations=conversations,
            conversation_id=None,
        )
        inputs = iter(("hello real provider", "exit"))

        await run_persistent_agent_chat(
            runtime=build_persistent_agent_runtime(
                model=provider,
                conversations=conversations,
                runs=runs,
                starter=starter,
                finisher=finisher,
            ),
            conversation_id=conversation.conversation_id,
            model_name="configured-model",
            system_prompt="Use tools when helpful.",
            read_line=lambda prompt: _next_input(inputs, prompt),
            write_line=output.append,
        )

        messages = await conversations.list_messages(
            conversation.conversation_id,
        )
        persisted_runs = await runs.list_for_conversation(
            conversation.conversation_id,
        )

        assert "asAgent: Persisted provider reply" in output
        assert tuple(message.content for message in messages) == (
            "hello real provider",
            "Persisted provider reply",
        )
        assert len(persisted_runs) == 1
        assert persisted_runs[0].status.value == "completed"
        assert len(provider.requests) == 1
    finally:
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()


def _next_input(inputs: Iterator[str], prompt: str) -> str:
    assert prompt == "You: "
    return next(inputs)
