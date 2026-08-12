import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import pytest

from asagent.cli import (
    _alembic_config_path,
    _start_configured_mcp_servers,
    build_persistent_agent_runtime,
    get_or_create_persistent_conversation,
)
from asagent.models.contracts import ModelResponse, ModelToolCall
from asagent.models.fake_provider import FakeModelProvider
from asagent.models.tool_names import openai_compatible_tool_name
from asagent.paths import AppPaths
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.database import upgrade_sqlite_database
from asagent.storage.sqlite.run_finisher import SqliteRunFinisher
from asagent.storage.sqlite.run_repository import SqliteRunRepository
from asagent.storage.sqlite.run_starter import SqliteRunStarter
from asagent.tools.approval import ToolApprovalRequest, ToolApprovalRequestedCallback

_SERVER_PATH: Final = Path(__file__).parents[1] / "fixtures" / "mcp_test_server.py"
_SERVER_COMMAND: Final = (sys.executable, "-u", str(_SERVER_PATH))


class _ApprovingPolicy:
    async def approve(
        self,
        request: ToolApprovalRequest,
        on_requested: ToolApprovalRequestedCallback | None = None,
    ) -> bool:
        del request, on_requested
        return True


def _write_mcp_config(paths: AppPaths) -> None:
    paths.config_dir.mkdir(parents=True)
    paths.config_dir.joinpath("mcp.json").write_text(
        (
            "{\n"
            '  "servers": {\n'
            '    "test-server": {\n'
            f'      "command": ["{_SERVER_COMMAND[0]}", "-u", "{_SERVER_PATH}"],\n'
            f'      "working_directory": "{_SERVER_PATH.parent}"\n'
            "    }\n"
            "  }\n"
            "}\n"
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_missing_mcp_configuration_keeps_only_builtin_tools(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app-home")
    registry, manager, has_mcp_servers = await _start_configured_mcp_servers(
        config_dir=paths.config_dir,
        environment={"PATH": os.environ["PATH"]},
    )

    try:
        assert has_mcp_servers is False
        assert {definition.tool_id for definition in registry.definitions()} == {
            "builtin.calculator",
            "builtin.current_time",
            "builtin.echo",
        }
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_configured_mcp_tool_enters_persistent_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app-home")
    _write_mcp_config(paths)
    monkeypatch.setenv("ASAGENT_TEST_MCP_PARENT_SECRET", "must-not-leak")
    environment: Mapping[str, str] = {
        "PATH": os.environ["PATH"],
        "ASAGENT_TEST_MCP_PARENT_SECRET": "must-not-leak",
    }
    registry, manager, has_mcp_servers = await _start_configured_mcp_servers(
        config_dir=paths.config_dir,
        environment=environment,
    )
    database_path = paths.data_dir / "asagent.sqlite3"
    upgrade_sqlite_database(
        database_path=database_path,
        alembic_config_path=_alembic_config_path(),
    )
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    finisher = SqliteRunFinisher(database_path)
    tool_id = next(
        definition.tool_id
        for definition in registry.definitions()
        if definition.tool_id.startswith("mcp:test-server:add:")
    )
    provider = FakeModelProvider(
        responses=(
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="add-call",
                        name=openai_compatible_tool_name(tool_id),
                        arguments={"left": 2, "right": 3},
                    ),
                ),
            ),
            ModelResponse(text="The result is 5.", tool_calls=()),
        ),
    )

    try:
        conversation = await get_or_create_persistent_conversation(
            conversations=conversations,
            conversation_id=None,
        )
        result = await build_persistent_agent_runtime(
            model=provider,
            conversations=conversations,
            runs=runs,
            starter=starter,
            finisher=finisher,
            approval_policy=_ApprovingPolicy(),
            registry=registry,
            granted_permissions=frozenset({"tool.execute", "mcp.execute"}),
        ).run(
            conversation_id=conversation.conversation_id,
            content="Add 2 and 3.",
            model_name="fake-model",
            system_prompt="Use tools when helpful.",
        )

        assert has_mcp_servers is True
        assert result.assistant_message is not None
        assert result.assistant_message.content == "The result is 5."
        assert provider.requests[1].messages[-1].content == "5"
    finally:
        await manager.aclose()
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()
