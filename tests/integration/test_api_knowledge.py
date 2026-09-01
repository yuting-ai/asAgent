from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
import pytest
from alembic.config import Config
from fastapi import FastAPI

from alembic import command
from asagent.agent.run_submission import RunSubmissionService, SubmittedRun
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.api.server import LocalApiServer
from asagent.core.conversation import Conversation
from asagent.core.ids import (
    MessageId,
    RunId,
)
from asagent.core.messages import UserMessage
from asagent.core.run import Run
from asagent.knowledge.embedder import LocalMiniLMEmbedder
from asagent.knowledge.indexer import KnowledgeIndexer
from asagent.knowledge.retriever import KnowledgeRetriever
from asagent.knowledge.service import KnowledgeLibraryService
from asagent.storage.qdrant import KnowledgeVectorStore
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.knowledge_repository import (
    SqliteKnowledgeRepository,
)
from asagent.storage.sqlite.run_repository import SqliteRunRepository

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MODEL_DIR = (
    _PROJECT_ROOT / "app-assets" / "models" / "paraphrase-multilingual-MiniLM-L12-v2"
)
_TOKEN = LocalApiToken("valid-token")


class _UnusedRunStarter:
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


@pytest.fixture
def embedder() -> LocalMiniLMEmbedder:
    return LocalMiniLMEmbedder(_MODEL_DIR)


@pytest.fixture
async def knowledge_client(
    embedder: LocalMiniLMEmbedder, tmp_path: Path
) -> AsyncIterator[
    tuple[
        httpx.AsyncClient,
        SqliteKnowledgeRepository,
        SqliteConversationRepository,
        Path,
        object,
    ]
]:
    db_path = tmp_path / "asagent.sqlite3"
    _upgrade(db_path)
    repo = SqliteKnowledgeRepository(db_path)
    conv_repo = SqliteConversationRepository(db_path)
    run_repo = SqliteRunRepository(db_path)

    qdrant_dir = tmp_path / "qdrant_db"
    vector_store = KnowledgeVectorStore(qdrant_dir)

    now = datetime(2026, 8, 31, 13, 0, 0, tzinfo=UTC)

    service = KnowledgeLibraryService(repository=repo, now=lambda: now)
    indexer = KnowledgeIndexer(
        repository=repo,
        embedder=embedder,
        vector_store=vector_store,
        now=lambda: now,
    )
    retriever = KnowledgeRetriever(
        repository=repo,
        embedder=embedder,
        vector_store=vector_store,
        now=lambda: now,
    )

    run_submission = RunSubmissionService(
        conversations=conv_repo,
        run_starter=_UnusedRunStarter(),
        now=lambda: now,
        new_run_id=lambda: RunId("run_1"),
        new_message_id=lambda: MessageId("msg_1"),
    )

    app = create_app(
        access_token=_TOKEN,
        conversations=conv_repo,
        runs=run_repo,
        run_submission=run_submission,
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
        knowledge_repository=repo,
        knowledge_service=service,
        knowledge_indexer=indexer,
        knowledge_retriever=retriever,
        clock=lambda: now,
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {_TOKEN.value}"},
    ) as client:
        yield client, repo, conv_repo, tmp_path, app

    vector_store.close()
    await run_repo.aclose()
    await conv_repo.aclose()
    await repo.aclose()


async def test_list_and_create_libraries(
    knowledge_client: tuple[
        httpx.AsyncClient,
        SqliteKnowledgeRepository,
        SqliteConversationRepository,
        Path,
        object,
    ],
) -> None:
    client, _repo, _conv_repo, _tmp_path, _app = knowledge_client

    # Initial list -> auto ensures default library "Research Papers"
    response = await client.get("/api/v1/knowledge/libraries")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Research Papers"

    # Create new library
    response = await client.post(
        "/api/v1/knowledge/libraries",
        json={"name": "Machine Learning Research"},
    )
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Machine Learning Research"
    assert created["status"] == "active"

    # Duplicate name should conflict (409)
    response = await client.post(
        "/api/v1/knowledge/libraries",
        json={"name": "machine learning research"},
    )
    assert response.status_code == 409


async def test_stream_library_index_progress_over_sse(
    knowledge_client: tuple[
        httpx.AsyncClient,
        SqliteKnowledgeRepository,
        SqliteConversationRepository,
        Path,
        object,
    ],
) -> None:
    client, _repo, _conv_repo, _tmp_path, app = knowledge_client
    libraries = (await client.get("/api/v1/knowledge/libraries")).json()
    library_id = libraries[0]["library_id"]
    server = LocalApiServer(cast(FastAPI, app), port=0)
    ready = await server.start()

    try:
        async with httpx.AsyncClient(
            base_url=f"http://{ready.host}:{ready.port}",
            headers={"Authorization": f"Bearer {_TOKEN.value}"},
        ) as tcp_client:
            async with tcp_client.stream(
                "GET", f"/api/v1/knowledge/libraries/{library_id}/events"
            ) as stream:
                assert stream.status_code == 200
                assert stream.headers["content-type"].startswith("text/event-stream")
                lines = stream.aiter_lines()
                assert await anext(lines) == "event: knowledge_index_progress"
                data_line = await anext(lines)
                assert '"library_id":"' + library_id + '"' in data_line
                assert '"status":"empty"' in data_line
    finally:
        await server.close()


async def test_rename_and_delete_library(
    knowledge_client: tuple[
        httpx.AsyncClient,
        SqliteKnowledgeRepository,
        SqliteConversationRepository,
        Path,
        object,
    ],
) -> None:
    client, _repo, _conv_repo, _tmp_path, _app = knowledge_client

    # Ensure default library exists
    await client.get("/api/v1/knowledge/libraries")

    response = await client.post(
        "/api/v1/knowledge/libraries",
        json={"name": "Temp Library"},
    )
    assert response.status_code == 201
    lib_id = response.json()["library_id"]

    # Rename
    response = await client.patch(
        f"/api/v1/knowledge/libraries/{lib_id}",
        json={"name": "Renamed Library"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Library"

    # Delete
    response = await client.delete(f"/api/v1/knowledge/libraries/{lib_id}")
    assert response.status_code == 204

    # Fetch deleted library
    response = await client.get(f"/api/v1/knowledge/libraries/{lib_id}")
    assert response.status_code == 404


async def test_add_and_detach_source(
    knowledge_client: tuple[
        httpx.AsyncClient,
        SqliteKnowledgeRepository,
        SqliteConversationRepository,
        Path,
        object,
    ],
) -> None:
    client, _repo, _conv_repo, tmp_path, _app = knowledge_client

    libs = (await client.get("/api/v1/knowledge/libraries")).json()
    lib_id = libs[0]["library_id"]

    source_dir = tmp_path / "my_docs"
    source_dir.mkdir()

    # Add source
    response = await client.post(
        f"/api/v1/knowledge/libraries/{lib_id}/sources",
        json={"path": str(source_dir)},
    )
    assert response.status_code == 201
    source_data = response.json()
    assert source_data["display_path"] == str(source_dir)
    source_id = source_data["source_id"]

    # Detach source
    response = await client.delete(f"/api/v1/knowledge/sources/{source_id}")
    assert response.status_code == 204


async def test_index_source_and_search(
    knowledge_client: tuple[
        httpx.AsyncClient,
        SqliteKnowledgeRepository,
        SqliteConversationRepository,
        Path,
        object,
    ],
) -> None:
    client, _repo, _conv_repo, tmp_path, _app = knowledge_client

    libs = (await client.get("/api/v1/knowledge/libraries")).json()
    lib_id = libs[0]["library_id"]

    source_dir = tmp_path / "rag_papers"
    source_dir.mkdir()
    doc_file = source_dir / "sqlite_concurrency.md"
    doc_file.write_text(
        "# SQLite Write-Ahead Logging\n\n"
        "WAL mode allows multiple readers to read concurrently while a writer writes to WAL.\n",
        encoding="utf-8",
    )

    source_res = await client.post(
        f"/api/v1/knowledge/libraries/{lib_id}/sources",
        json={"path": str(source_dir)},
    )
    source_id = source_res.json()["source_id"]

    # Trigger indexing
    index_res = await client.post(f"/api/v1/knowledge/sources/{source_id}/index")
    assert index_res.status_code == 202
    job_id = index_res.json()["job_id"]

    # Read SSE progress events until completion
    job_completed = False
    async with client.stream(
        "GET", f"/api/v1/knowledge/jobs/{job_id}/events"
    ) as stream:
        async for line in stream.aiter_lines():
            if line.startswith("data: "):
                import json

                payload = json.loads(line[6:])
                if payload["status"] == "completed":
                    job_completed = True
                    assert payload["processed_files"] == 1
                    assert payload["indexed_chunks"] > 0
                    break

    assert job_completed

    # Search in library
    search_res = await client.post(
        f"/api/v1/knowledge/libraries/{lib_id}/search",
        json={
            "query": "How does WAL mode achieve concurrency between readers and writers?"
        },
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert len(search_data["hits"]) > 0
    assert "[S1]" in search_data["formatted_context"]
    assert "sqlite_concurrency.md" in search_data["formatted_context"]


async def test_conversation_library_binding(
    knowledge_client: tuple[
        httpx.AsyncClient,
        SqliteKnowledgeRepository,
        SqliteConversationRepository,
        Path,
        object,
    ],
) -> None:
    client, _repo, _conv_repo, _tmp_path, _app = knowledge_client

    libs = (await client.get("/api/v1/knowledge/libraries")).json()
    lib_id = libs[0]["library_id"]

    # Create a knowledge conversation
    conv_res = await client.post(
        "/api/v1/knowledge/conversations",
        json={"library_id": lib_id},
    )
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["conversation_id"]

    # A Knowledge conversation is atomically associated with its Library.
    bind_res = await client.get(f"/api/v1/conversations/{conv_id}/library")
    assert bind_res.status_code == 200
    assert bind_res.json()["library_id"] == lib_id

    # Bind library
    bind_res = await client.put(
        f"/api/v1/conversations/{conv_id}/library",
        json={"library_id": lib_id},
    )
    assert bind_res.status_code == 200
    assert bind_res.json()["library_id"] == lib_id
    assert bind_res.json()["library_name"] == "Research Papers"

    # Unbind library
    unbind_res = await client.delete(f"/api/v1/conversations/{conv_id}/library")
    assert unbind_res.status_code == 204

    bind_res = await client.get(f"/api/v1/conversations/{conv_id}/library")
    assert bind_res.status_code == 200
    assert bind_res.json()["library_id"] is None
