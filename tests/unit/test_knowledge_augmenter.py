from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from asagent.agent.context_budget import (
    ConservativeUtf8TokenEstimator,
    ContextBudget,
    ModelContextCapabilities,
)
from asagent.agent.context_builder import ContextBuilder
from asagent.core.conversation import Conversation
from asagent.core.ids import (
    ConversationId,
    LibraryId,
    RunId,
    SourceId,
    UserId,
)
from asagent.core.run import Run
from asagent.core.run_status import RunStatus
from asagent.knowledge.augmenter import KnowledgeContextAugmenter
from asagent.knowledge.embedder import LocalMiniLMEmbedder
from asagent.knowledge.indexer import KnowledgeIndexer
from asagent.knowledge.models import (
    KnowledgeLibrary,
    KnowledgeSource,
)
from asagent.knowledge.retriever import KnowledgeRetriever
from asagent.models.contracts import (
    ModelMessage,
    ModelMessageRole,
)
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


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


@pytest.fixture
def embedder() -> LocalMiniLMEmbedder:
    return LocalMiniLMEmbedder(_MODEL_DIR)


@pytest.fixture
async def setup_augmenter(
    embedder: LocalMiniLMEmbedder, tmp_path: Path
) -> AsyncIterator[
    tuple[
        KnowledgeContextAugmenter,
        SqliteKnowledgeRepository,
        ConversationId,
        LibraryId,
        RunId,
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
    lib_id = LibraryId("lib_rag")
    user_id = UserId("u_rag")
    conv_id = ConversationId("conv_rag")
    run_id = RunId("run_rag_1")

    conv = Conversation(
        conversation_id=conv_id,
        user_id=user_id,
        created_at=now,
        updated_at=now,
        kind="knowledge",
    )
    await conv_repo.save(conv)

    run = Run(
        run_id=run_id,
        conversation_id=conv_id,
        status=RunStatus.EXECUTING_TOOLS,
        created_at=now,
        updated_at=now,
    )
    await run_repo.save(run)

    lib = KnowledgeLibrary(
        library_id=lib_id,
        user_id=user_id,
        name="AI & Systems Research",
        normalized_name="ai and systems research",
        status="active",
        created_at=now,
        updated_at=now,
    )
    await repo.save_library(lib)

    # Bind conversation to library
    await repo.bind_conversation_library(conv_id, lib_id)

    source_dir = tmp_path / "docs"
    source_dir.mkdir()

    src = KnowledgeSource(
        source_id=SourceId("src_docs"),
        library_id=lib_id,
        display_path=str(source_dir),
        canonical_path=str(source_dir.resolve()),
        status="active",
        scan_status="queued",
        created_at=now,
        updated_at=now,
    )
    await repo.save_source(src)

    doc_file = source_dir / "sqlite_wal.md"
    doc_file.write_text(
        "# Write-Ahead Logging in SQLite\n\n"
        "WAL provides more concurrency as readers do not block writers and a writer does not block readers. "
        "Reading and writing can proceed concurrently.",
        encoding="utf-8",
    )

    indexer = KnowledgeIndexer(
        repository=repo,
        embedder=embedder,
        vector_store=vector_store,
        now=lambda: now,
    )
    await indexer.index_source(src.source_id)

    retriever = KnowledgeRetriever(
        repository=repo,
        embedder=embedder,
        vector_store=vector_store,
        now=lambda: now,
    )
    augmenter = KnowledgeContextAugmenter(
        repository=repo,
        retriever=retriever,
    )

    try:
        yield augmenter, repo, conv_id, lib_id, run_id
    finally:
        vector_store.close()
        await run_repo.aclose()
        await conv_repo.aclose()
        await repo.aclose()


async def test_augment_unbound_conversation(
    setup_augmenter: tuple[
        KnowledgeContextAugmenter,
        SqliteKnowledgeRepository,
        ConversationId,
        LibraryId,
        RunId,
    ],
) -> None:
    augmenter, _repo, _conv_id, _lib_id, _run_id = setup_augmenter
    unbound_conv = ConversationId("conv_unbound")

    aug = await augmenter.augment_system_prompt(
        conversation_id=unbound_conv,
        base_system_prompt="Base prompt.",
        user_query="How does WAL work?",
    )
    assert aug.system_prompt == "Base prompt."
    assert aug.library_id is None
    assert aug.retrieval_result is None


async def test_augment_empty_query(
    setup_augmenter: tuple[
        KnowledgeContextAugmenter,
        SqliteKnowledgeRepository,
        ConversationId,
        LibraryId,
        RunId,
    ],
) -> None:
    augmenter, _repo, conv_id, lib_id, _run_id = setup_augmenter

    aug = await augmenter.augment_system_prompt(
        conversation_id=conv_id,
        base_system_prompt="Base prompt.",
        user_query="   ",
    )
    assert "Base prompt." in aug.system_prompt
    assert "## Knowledge Library: AI & Systems Research" in aug.system_prompt
    assert aug.library_id == lib_id
    assert aug.retrieval_result is None


async def test_augment_matching_query_and_citations(
    setup_augmenter: tuple[
        KnowledgeContextAugmenter,
        SqliteKnowledgeRepository,
        ConversationId,
        LibraryId,
        RunId,
    ],
) -> None:
    augmenter, repo, conv_id, lib_id, run_id = setup_augmenter

    aug = await augmenter.augment_system_prompt(
        conversation_id=conv_id,
        base_system_prompt="You are a helpful assistant.",
        user_query="How does SQLite WAL mode achieve concurrency between readers and writers?",
        run_id=run_id,
    )
    assert aug.library_id == lib_id
    assert aug.retrieval_result is not None
    assert len(aug.retrieval_result.hits) > 0

    assert (
        "## Knowledge Library: AI & Systems Research (Retrieved Sources)"
        in aug.system_prompt
    )
    assert "contains 1 active indexed document(s): sqlite_wal.md" in aug.system_prompt
    assert (
        "Never claim that a document or the workspace is missing" in aug.system_prompt
    )
    assert "separate from the general Agent Workspace" in aug.system_prompt
    assert "Do not inspect, discuss, or report on Workspace files" in aug.system_prompt
    assert "[S1] sqlite_wal.md" in aug.system_prompt
    assert "Write-Ahead Logging" in aug.system_prompt
    assert "Explicitly cite sources using their bracketed labels" in aug.system_prompt

    # Check persistence in SQLite
    saved_hits = await repo.list_retrieval_hits_for_run(run_id)
    assert len(saved_hits) == len(aug.retrieval_result.hits)


async def test_context_builder_with_augmented_prompt(
    setup_augmenter: tuple[
        KnowledgeContextAugmenter,
        SqliteKnowledgeRepository,
        ConversationId,
        LibraryId,
        RunId,
    ],
) -> None:
    augmenter, _repo, conv_id, _lib_id, run_id = setup_augmenter

    aug = await augmenter.augment_system_prompt(
        conversation_id=conv_id,
        base_system_prompt="Base system prompt.",
        user_query="Explain SQLite WAL mode",
        run_id=run_id,
    )

    budget = ContextBudget(
        max_input_tokens=4096,
        reserved_output_tokens=1024,
    ).resolve(ModelContextCapabilities(context_window_tokens=8192))
    estimator = ConservativeUtf8TokenEstimator()
    builder = ContextBuilder(budget=budget, estimator=estimator)

    messages = (
        ModelMessage(
            role=ModelMessageRole.USER,
            content="Explain SQLite WAL mode",
        ),
    )

    snapshot = builder.build(
        model="gpt-4o",
        system_prompt=aug.system_prompt,
        history=messages,
        tools=(),
    )

    assert snapshot.usage.is_within_budget
    assert snapshot.usage.system_prompt_tokens > 0
    assert snapshot.request.system_prompt == aug.system_prompt
