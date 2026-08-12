import json
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
import pytest
from alembic.config import Config

from alembic import command
from asagent.agent.run_submission import RunSubmissionService, SubmittedRun
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.bootstrap.model_settings import MODEL_CONNECTION_ID, ModelSettings
from asagent.bootstrap.tavily_settings import (
    TAVILY_CONNECTION_ID,
    TAVILY_SERVER_NAME,
    TavilySettings,
)
from asagent.core.connection import Connection, ConnectionStatus
from asagent.core.conversation import Conversation
from asagent.core.ids import ConnectionId, MessageId, RunId, UserId
from asagent.core.messages import UserMessage
from asagent.core.repositories import RunRepository
from asagent.core.run import Run
from asagent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from asagent.storage.sqlite.connection_repository import (
    SqliteConnectionRepository,
)
from asagent.tools.mcp_config import load_mcp_server_configs
from asagent.workspace.settings import WorkspaceSettings

_TOKEN = LocalApiToken("test-token")
_FIXED_NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
_TAVILY_API_KEY = "tvly-test-key-not-real"
_OTHER_SERVER_NAME = "other-server"
_UNUSED_RUNS = cast(RunRepository, object())


class InMemoryCredentialStore:
    def __init__(self) -> None:
        self._credentials: dict[ConnectionId, str] = {}

    def get_credential(self, connection_id: ConnectionId) -> str | None:
        return self._credentials.get(connection_id)

    def save_credential(
        self,
        connection_id: ConnectionId,
        credential: str,
    ) -> None:
        if not credential:
            raise ValueError("credentials must not be empty")
        self._credentials[connection_id] = credential

    def delete_credential(self, connection_id: ConnectionId) -> None:
        self._credentials.pop(connection_id, None)


class UnusedRunStarter:
    async def start(
        self,
        *,
        conversation: Conversation,
        user_message: UserMessage,
        run: Run,
    ) -> None:
        del conversation, user_message, run
        raise AssertionError("run submission is not used by this test")


def _discard_submission(submission: SubmittedRun) -> None:
    del submission


def _cancel_nothing(run_id: RunId) -> bool:
    del run_id
    return False


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


def _write_other_server_config(config_dir: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "mcp.json").write_text(
        json.dumps(
            {
                "servers": {
                    _OTHER_SERVER_NAME: {
                        "command": [
                            sys.executable,
                            "-u",
                            "/opt/mcp/other_server.py",
                        ],
                        "working_directory": str(config_dir.resolve()),
                    }
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


@dataclass
class TavilyApiContext:
    client: httpx.AsyncClient
    config_dir: Path
    credential_store: InMemoryCredentialStore
    connections: SqliteConnectionRepository
    workspace_root: Path


@pytest.fixture
async def tavily_api_context(tmp_path: Path) -> AsyncIterator[TavilyApiContext]:
    database_path = tmp_path / "asagent.sqlite3"
    config_dir = tmp_path / "config"
    workspace_root = tmp_path / "workspace"
    config_dir.mkdir()
    workspace_root.mkdir()
    _upgrade(database_path)

    credential_store = InMemoryCredentialStore()
    connections = SqliteConnectionRepository(database_path)
    tavily_settings = TavilySettings(
        config_dir=config_dir,
        connections=connections,
        credential_store=credential_store,
        clock=lambda: _FIXED_NOW,
    )
    model_settings = ModelSettings(
        config_dir=config_dir,
        connections=connections,
        credential_store=credential_store,
        clock=lambda: _FIXED_NOW,
    )
    workspace_settings = WorkspaceSettings(
        config_dir=config_dir,
        workspace_root=workspace_root,
    )
    conversations = InMemoryConversationRepository()
    app = create_app(
        access_token=_TOKEN,
        conversations=conversations,
        runs=_UNUSED_RUNS,
        run_submission=RunSubmissionService(
            conversations=conversations,
            run_starter=UnusedRunStarter(),
            now=lambda: _FIXED_NOW,
            new_run_id=lambda: RunId("unused-run"),
            new_message_id=lambda: MessageId("unused-message"),
        ),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
        tavily_settings=tavily_settings,
        model_settings=model_settings,
        workspace_settings=workspace_settings,
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Authorization": "Bearer test-token"},
    ) as client:
        yield TavilyApiContext(
            client=client,
            config_dir=config_dir,
            credential_store=credential_store,
            connections=connections,
            workspace_root=workspace_root,
        )

    await connections.aclose()


def _assert_response_never_leaks_api_key(
    response: httpx.Response,
    *,
    api_key: str,
) -> None:
    assert api_key not in response.text
    payload = response.json()
    assert set(payload) <= {"enabled", "api_key_saved", "detail"}
    assert "api_key" not in payload


@pytest.mark.asyncio
async def test_model_settings_save_status_and_delete_keep_api_key_private(
    tavily_api_context: TavilyApiContext,
) -> None:
    client = tavily_api_context.client
    api_key = "model-test-key-not-real"

    initial = await client.get("/api/v1/settings/model")
    assert initial.json() == {
        "configured": False,
        "api_key_saved": False,
        "model": None,
        "base_url": None,
    }

    saved = await client.put(
        "/api/v1/settings/model",
        json={
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": api_key,
        },
    )
    assert saved.status_code == 200
    assert saved.json() == {
        "configured": True,
        "api_key_saved": True,
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
    }
    assert api_key not in saved.text
    assert (
        tavily_api_context.credential_store.get_credential(MODEL_CONNECTION_ID)
        == api_key
    )
    assert api_key not in (tavily_api_context.config_dir / "providers.toml").read_text(
        encoding="utf-8",
    )

    deleted = await client.delete("/api/v1/settings/model")
    assert deleted.status_code == 200
    assert deleted.json() == {
        "configured": False,
        "api_key_saved": False,
        "model": None,
        "base_url": None,
    }


@pytest.mark.asyncio
async def test_model_settings_reject_missing_or_blank_key_before_one_is_saved(
    tavily_api_context: TavilyApiContext,
) -> None:
    missing_key = await tavily_api_context.client.put(
        "/api/v1/settings/model",
        json={
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
        },
    )
    blank_key = await tavily_api_context.client.put(
        "/api/v1/settings/model",
        json={
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "   ",
        },
    )

    assert missing_key.status_code == 409
    assert blank_key.status_code == 422


@pytest.mark.asyncio
async def test_workspace_settings_persist_selected_directories(
    tavily_api_context: TavilyApiContext,
    tmp_path: Path,
) -> None:
    selected_directory = tmp_path / "selected"
    selected_directory.mkdir()

    initial = await tavily_api_context.client.get("/api/v1/settings/workspace")
    assert initial.status_code == 200
    assert initial.json() == {
        "workspace_root": str(tavily_api_context.workspace_root.resolve()),
        "additional_roots": [],
    }

    saved = await tavily_api_context.client.put(
        "/api/v1/settings/workspace",
        json={"additional_roots": [str(selected_directory)]},
    )
    assert saved.status_code == 200
    assert saved.json() == {
        "workspace_root": str(tavily_api_context.workspace_root.resolve()),
        "additional_roots": [str(selected_directory.resolve())],
    }

    removed = await tavily_api_context.client.put(
        "/api/v1/settings/workspace",
        json={"additional_roots": []},
    )
    assert removed.status_code == 200
    assert removed.json()["additional_roots"] == []


@pytest.mark.asyncio
async def test_workspace_settings_reject_invalid_paths_and_unknown_fields(
    tavily_api_context: TavilyApiContext,
    tmp_path: Path,
) -> None:
    missing_directory = tmp_path / "missing"

    missing = await tavily_api_context.client.put(
        "/api/v1/settings/workspace",
        json={"additional_roots": [str(missing_directory)]},
    )
    unknown_field = await tavily_api_context.client.put(
        "/api/v1/settings/workspace",
        json={"additional_roots": [], "unexpected": True},
    )

    assert missing.status_code == 422
    assert unknown_field.status_code == 422


@pytest.mark.asyncio
async def test_get_returns_disabled_when_unconfigured(
    tavily_api_context: TavilyApiContext,
) -> None:
    response = await tavily_api_context.client.get("/api/v1/settings/tavily")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "api_key_saved": False,
    }


@pytest.mark.asyncio
async def test_put_saves_api_key_and_enables_tavily(
    tavily_api_context: TavilyApiContext,
) -> None:
    response = await tavily_api_context.client.put(
        "/api/v1/settings/tavily",
        json={"api_key": _TAVILY_API_KEY},
    )

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "api_key_saved": True,
    }
    _assert_response_never_leaks_api_key(response, api_key=_TAVILY_API_KEY)

    assert (
        tavily_api_context.credential_store.get_credential(TAVILY_CONNECTION_ID)
        == _TAVILY_API_KEY
    )

    stored_connection = await tavily_api_context.connections.get(TAVILY_CONNECTION_ID)
    assert stored_connection == Connection(
        connection_id=TAVILY_CONNECTION_ID,
        user_id=UserId("local-user"),
        service_id="tavily",
        account_label="Tavily Web Search",
        granted_scopes=frozenset(),
        status=ConnectionStatus.ACTIVE,
        created_at=_FIXED_NOW,
        updated_at=_FIXED_NOW,
    )

    configs = load_mcp_server_configs(tavily_api_context.config_dir)
    assert set(configs.servers) == {TAVILY_SERVER_NAME}
    tavily_config = configs.servers[TAVILY_SERVER_NAME]
    assert tavily_config.command == ("npx", "-y", "tavily-mcp@latest")
    assert tavily_config.working_directory == tavily_api_context.config_dir.resolve()
    assert tavily_config.connection_id == "connection-tavily"
    assert tavily_config.credential_environment_variable == "TAVILY_API_KEY"
    assert tavily_config.allowed_tools == ("tavily_search",)

    config_text = (tavily_api_context.config_dir / "mcp.json").read_text(
        encoding="utf-8",
    )
    assert _TAVILY_API_KEY not in config_text


@pytest.mark.asyncio
async def test_put_reenables_without_key_after_disable(
    tavily_api_context: TavilyApiContext,
) -> None:
    client = tavily_api_context.client

    save_response = await client.put(
        "/api/v1/settings/tavily",
        json={"api_key": _TAVILY_API_KEY},
    )
    assert save_response.status_code == 200

    disable_response = await client.post("/api/v1/settings/tavily/disable")
    assert disable_response.status_code == 200
    assert disable_response.json() == {
        "enabled": False,
        "api_key_saved": True,
    }

    enable_response = await client.put("/api/v1/settings/tavily", json={})
    assert enable_response.status_code == 200
    assert enable_response.json() == {
        "enabled": True,
        "api_key_saved": True,
    }
    _assert_response_never_leaks_api_key(enable_response, api_key=_TAVILY_API_KEY)

    configs = load_mcp_server_configs(tavily_api_context.config_dir)
    assert TAVILY_SERVER_NAME in configs.servers


@pytest.mark.asyncio
async def test_put_without_saved_key_returns_conflict(
    tavily_api_context: TavilyApiContext,
) -> None:
    response = await tavily_api_context.client.put(
        "/api/v1/settings/tavily",
        json={},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "tavily api key is not saved"}
    _assert_response_never_leaks_api_key(response, api_key=_TAVILY_API_KEY)


@pytest.mark.asyncio
async def test_disable_removes_mcp_entry_but_keeps_secrets(
    tavily_api_context: TavilyApiContext,
) -> None:
    client = tavily_api_context.client

    await client.put(
        "/api/v1/settings/tavily",
        json={"api_key": _TAVILY_API_KEY},
    )

    response = await client.post("/api/v1/settings/tavily/disable")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "api_key_saved": True,
    }
    _assert_response_never_leaks_api_key(response, api_key=_TAVILY_API_KEY)

    configs = load_mcp_server_configs(tavily_api_context.config_dir)
    assert TAVILY_SERVER_NAME not in configs.servers
    assert (
        tavily_api_context.credential_store.get_credential(TAVILY_CONNECTION_ID)
        == _TAVILY_API_KEY
    )
    assert await tavily_api_context.connections.get(TAVILY_CONNECTION_ID) is not None


@pytest.mark.asyncio
async def test_delete_removes_configuration_key_and_connection(
    tavily_api_context: TavilyApiContext,
) -> None:
    client = tavily_api_context.client

    await client.put(
        "/api/v1/settings/tavily",
        json={"api_key": _TAVILY_API_KEY},
    )

    response = await client.delete("/api/v1/settings/tavily")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "api_key_saved": False,
    }
    _assert_response_never_leaks_api_key(response, api_key=_TAVILY_API_KEY)

    configs = load_mcp_server_configs(tavily_api_context.config_dir)
    assert TAVILY_SERVER_NAME not in configs.servers
    assert (
        tavily_api_context.credential_store.get_credential(TAVILY_CONNECTION_ID) is None
    )
    assert await tavily_api_context.connections.get(TAVILY_CONNECTION_ID) is None


@pytest.mark.asyncio
async def test_preserves_other_mcp_servers(
    tavily_api_context: TavilyApiContext,
) -> None:
    _write_other_server_config(tavily_api_context.config_dir)
    client = tavily_api_context.client

    enable_response = await client.put(
        "/api/v1/settings/tavily",
        json={"api_key": _TAVILY_API_KEY},
    )
    assert enable_response.status_code == 200

    configs = load_mcp_server_configs(tavily_api_context.config_dir)
    assert set(configs.servers) == {_OTHER_SERVER_NAME, TAVILY_SERVER_NAME}

    disable_response = await client.post("/api/v1/settings/tavily/disable")
    assert disable_response.status_code == 200

    configs = load_mcp_server_configs(tavily_api_context.config_dir)
    assert set(configs.servers) == {_OTHER_SERVER_NAME}

    delete_response = await client.delete("/api/v1/settings/tavily")
    assert delete_response.status_code == 200

    configs = load_mcp_server_configs(tavily_api_context.config_dir)
    assert set(configs.servers) == {_OTHER_SERVER_NAME}


@pytest.mark.asyncio
async def test_rejects_unknown_request_fields(
    tavily_api_context: TavilyApiContext,
) -> None:
    response = await tavily_api_context.client.put(
        "/api/v1/settings/tavily",
        json={"api_key": _TAVILY_API_KEY, "enabled": True},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_rejects_blank_api_key(
    tavily_api_context: TavilyApiContext,
) -> None:
    response = await tavily_api_context.client.put(
        "/api/v1/settings/tavily",
        json={"api_key": "   "},
    )

    assert response.status_code == 422

    configs = load_mcp_server_configs(tavily_api_context.config_dir)
    assert TAVILY_SERVER_NAME not in configs.servers
