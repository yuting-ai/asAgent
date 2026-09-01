from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
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
from asagent.knowledge.embedder import LocalMiniLMEmbedder
from asagent.knowledge.indexer import KnowledgeIndexer
from asagent.knowledge.models import (
    KnowledgeLibrary,
    KnowledgeSource,
)
from asagent.knowledge.retriever import KnowledgeRetriever
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
async def setup_retriever(
    embedder: LocalMiniLMEmbedder, tmp_path: Path
) -> AsyncIterator[
    tuple[KnowledgeRetriever, SqliteKnowledgeRepository, LibraryId, RunId]
]:
    db_path = tmp_path / "asagent.sqlite3"
    _upgrade(db_path)
    repo = SqliteKnowledgeRepository(db_path)
    conv_repo = SqliteConversationRepository(db_path)
    run_repo = SqliteRunRepository(db_path)

    qdrant_dir = tmp_path / "qdrant_db"
    vector_store = KnowledgeVectorStore(qdrant_dir)

    now = datetime(2026, 8, 31, 13, 0, 0, tzinfo=UTC)
    lib_id = LibraryId("lib_ai")
    user_id = UserId("u_ai")
    conv_id = ConversationId("conv_ai")
    run_id = RunId("run_test_rag")

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
        name="AI Research",
        normalized_name="ai research",
        status="active",
        created_at=now,
        updated_at=now,
    )
    await repo.save_library(lib)

    source_dir = tmp_path / "papers"
    source_dir.mkdir()

    src = KnowledgeSource(
        source_id=SourceId("src_papers"),
        library_id=lib_id,
        display_path=str(source_dir),
        canonical_path=str(source_dir.resolve()),
        status="active",
        scan_status="queued",
        created_at=now,
        updated_at=now,
    )
    await repo.save_source(src)

    # Add test documents
    doc1 = source_dir / "transformers.md"
    doc1.write_text(
        "# Attention Is All You Need\n\n"
        "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.\n\n"
        "## Multi-Head Attention\n\n"
        "Multi-head attention allows the model to jointly attend to information from different representation subspaces.",
        encoding="utf-8",
    )

    doc2 = source_dir / "sqlite.md"
    doc2.write_text(
        "# SQLite Architecture\n\n"
        "SQLite is a C-language library that implements a small, fast, self-contained, high-reliability, full-featured, SQL database engine.",
        encoding="utf-8",
    )

    # Index
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

    try:
        yield retriever, repo, lib_id, run_id
    finally:
        vector_store.close()
        await run_repo.aclose()
        await conv_repo.aclose()
        await repo.aclose()


async def test_retriever_ranking_and_context_formatting(
    setup_retriever: tuple[
        KnowledgeRetriever, SqliteKnowledgeRepository, LibraryId, RunId
    ],
) -> None:
    retriever, repo, lib_id, run_id = setup_retriever

    # 1. Retrieve for transformers query
    result = await retriever.retrieve(
        query="Explain multi-head self attention mechanism in neural networks",
        library_id=lib_id,
        run_id=run_id,
        limit=2,
    )

    assert len(result.hits) > 0
    assert len(result.citations) == len(result.hits)

    top_hit = result.hits[0]
    assert top_hit.rank == 1
    assert top_hit.citation_label == "S1"
    assert "transformers.md" in top_hit.document_name_snapshot
    assert top_hit.score > 0.60

    top_citation = result.citations[0]
    assert top_citation.label == "S1"
    assert top_citation.document_name == "transformers.md"
    assert top_citation.section_title is not None

    # Check formatted context
    assert "[S1] transformers.md" in result.formatted_context
    assert "Multi-Head Attention" in result.formatted_context

    # 2. Check persistence in SQLite
    persisted_hits = await repo.list_retrieval_hits_for_run(run_id)
    assert len(persisted_hits) == len(result.hits)
    assert persisted_hits[0].chunk_id == top_hit.chunk_id


async def test_retriever_cross_lingual_chinese_query(
    setup_retriever: tuple[
        KnowledgeRetriever, SqliteKnowledgeRepository, LibraryId, RunId
    ],
) -> None:
    retriever, _repo, lib_id, _run_id = setup_retriever

    # Query in Chinese for English document
    result = await retriever.retrieve(
        query="多头注意力机制如何工作？",
        library_id=lib_id,
        limit=1,
    )

    assert len(result.hits) == 1
    assert result.hits[0].citation_label == "S1"
    assert result.hits[0].document_name_snapshot == "transformers.md"
    assert result.hits[0].score > 0.60


async def test_retriever_prioritizes_an_explicit_indexed_filename(
    setup_retriever: tuple[
        KnowledgeRetriever, SqliteKnowledgeRepository, LibraryId, RunId
    ],
) -> None:
    retriever, _repo, lib_id, _run_id = setup_retriever

    result = await retriever.retrieve(
        query="sqlite.md 里面是什么内容？",
        library_id=lib_id,
        limit=2,
        min_score=0.99,
    )

    assert result.hits
    assert {hit.document_name_snapshot for hit in result.hits} == {"sqlite.md"}
    assert all(hit.score == 1.0 for hit in result.hits)
    assert "SQLite is a C-language library" in result.formatted_context


async def test_retriever_reserves_results_for_a_second_relevant_document(
    setup_retriever: tuple[
        KnowledgeRetriever, SqliteKnowledgeRepository, LibraryId, RunId
    ],
) -> None:
    retriever, _repo, lib_id, _run_id = setup_retriever

    result = await retriever.retrieve(
        query="Summarize and compare every indexed research document",
        library_id=lib_id,
        limit=2,
        min_score=0.0,
    )

    assert {hit.document_name_snapshot for hit in result.hits} == {
        "sqlite.md",
        "transformers.md",
    }


async def test_retriever_empty_and_unrelated_queries(
    setup_retriever: tuple[
        KnowledgeRetriever, SqliteKnowledgeRepository, LibraryId, RunId
    ],
) -> None:
    retriever, _repo, lib_id, _run_id = setup_retriever

    # Empty query
    r_empty = await retriever.retrieve(query="   ", library_id=lib_id)
    assert len(r_empty.hits) == 0
    assert r_empty.formatted_context == ""

    # Unrelated query with high min_score
    r_unrelated = await retriever.retrieve(
        query="Italian pasta baking recipes",
        library_id=lib_id,
        min_score=0.85,
    )
    assert len(r_unrelated.hits) == 0
