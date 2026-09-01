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
from asagent.agent.loop import AgentLoop
from asagent.api.auth import LocalApiToken
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
    ModelResponse,
)
from asagent.models.fake_provider import FakeModelProvider
from asagent.storage.qdrant import KnowledgeVectorStore
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.knowledge_repository import (
    SqliteKnowledgeRepository,
)
from asagent.storage.sqlite.run_finisher import SqliteRunFinisher
from asagent.storage.sqlite.run_repository import SqliteRunRepository
from asagent.storage.sqlite.run_starter import SqliteRunStarter
from asagent.tools.executor import ToolExecutor
from asagent.tools.registry import ToolRegistry
from asagent.tools.snapshot import ToolSnapshot

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MODEL_DIR = (
    _PROJECT_ROOT / "app-assets" / "models" / "paraphrase-multilingual-MiniLM-L12-v2"
)
_TOKEN = LocalApiToken("e2e-token")


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


@pytest.fixture
def embedder() -> LocalMiniLMEmbedder:
    return LocalMiniLMEmbedder(_MODEL_DIR)


async def test_knowledge_end_to_end_flow(
    embedder: LocalMiniLMEmbedder, tmp_path: Path
) -> None:
    """Complete end-to-end integration test of the Knowledge RAG system.

    Flow:
    1. Initialize SQLite, Qdrant vector store, ONNX miniLM embedder, indexer, retriever, and augmenter.
    2. Create library via API.
    3. Add document folder with factual Markdown files.
    4. Run indexing pipeline (scan -> parse -> chunk -> ONNX embedding -> Qdrant upsert -> SQLite consistency).
    5. Search / retrieve relevant knowledge passages.
    6. Augment system prompt and verify [S1] citations and token budgeting.
    7. Execute Agent run and verify retrieval hit persistence.
    """
    db_path = tmp_path / "asagent.sqlite3"
    _upgrade(db_path)
    repo = SqliteKnowledgeRepository(db_path)
    conv_repo = SqliteConversationRepository(db_path)
    run_repo = SqliteRunRepository(db_path)
    starter = SqliteRunStarter(db_path)
    finisher = SqliteRunFinisher(db_path)

    qdrant_dir = tmp_path / "qdrant_db"
    vector_store = KnowledgeVectorStore(qdrant_dir)

    now = datetime(2026, 8, 31, 14, 0, 0, tzinfo=UTC)

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
    augmenter = KnowledgeContextAugmenter(
        repository=repo,
        retriever=retriever,
    )

    # 1. Create source folder and knowledge document
    source_dir = tmp_path / "research_papers"
    source_dir.mkdir()
    paper_file = source_dir / "sqlite_concurrency.md"
    paper_file.write_text(
        "# SQLite Concurrency with Write-Ahead Logging\n\n"
        "In WAL mode, changes are written into a separate WAL file rather than overwriting the main database file. "
        "This architectural separation allows readers to access the main database file without blocking writers, "
        "and writers to append new transactions without blocking readers. Concurrent transactions operate with high throughput.\n",
        encoding="utf-8",
    )

    # 2. Setup library and source in database
    lib_id = LibraryId("lib_systems")
    user_id = UserId("local-user")
    lib = KnowledgeLibrary(
        library_id=lib_id,
        user_id=user_id,
        name="Systems & Database Research",
        normalized_name="systems and database research",
        status="active",
        created_at=now,
        updated_at=now,
    )
    await repo.save_library(lib)

    src_id = SourceId("src_papers")
    src = KnowledgeSource(
        source_id=src_id,
        library_id=lib_id,
        display_path=str(source_dir),
        canonical_path=str(source_dir.resolve()),
        status="active",
        scan_status="queued",
        created_at=now,
        updated_at=now,
    )
    await repo.save_source(src)

    # 3. Execute Indexing Pipeline
    stats = await indexer.index_source(src_id)
    assert stats.total_scanned == 1
    assert stats.added_docs == 1
    assert stats.total_chunks > 0
    assert stats.indexed_chunks > 0

    # Verify SQLite chunks and embeddings are stored
    docs = await repo.list_documents_for_source(src_id)
    assert len(docs) == 1
    assert docs[0].file_type == "markdown"
    assert docs[0].status == "active"

    active_chunks = await repo.list_active_chunks_for_document(docs[0].document_id)
    assert len(active_chunks) > 0

    # 4. Create Knowledge Conversation and Bind
    conv_id = ConversationId("conv_rag_e2e")
    conv = Conversation(
        conversation_id=conv_id,
        user_id=user_id,
        created_at=now,
        updated_at=now,
        kind="knowledge",
    )
    await conv_repo.save(conv)
    await repo.bind_conversation_library(conv_id, lib_id)

    # 5. Semantic Retrieval & Prompt Augmentation
    user_query = "How does Write-Ahead Logging allow readers and writers to operate concurrently?"
    run_id = RunId("run_e2e_1")
    run = Run(
        run_id=run_id,
        conversation_id=conv_id,
        status=RunStatus.EXECUTING_TOOLS,
        created_at=now,
        updated_at=now,
    )
    await run_repo.save(run)

    aug = await augmenter.augment_system_prompt(
        conversation_id=conv_id,
        base_system_prompt="You are an expert AI database assistant.",
        user_query=user_query,
        run_id=run_id,
    )

    assert aug.library_id == lib_id
    assert aug.retrieval_result is not None
    assert len(aug.retrieval_result.hits) > 0
    assert "[S1] sqlite_concurrency.md" in aug.system_prompt
    assert "separate WAL file" in aug.system_prompt
    assert "Explicitly cite sources using their bracketed labels" in aug.system_prompt

    # 6. Context Builder & Token Budget Verification
    budget = ContextBudget(
        max_input_tokens=4096,
        reserved_output_tokens=1024,
    ).resolve(ModelContextCapabilities(context_window_tokens=8192))
    estimator = ConservativeUtf8TokenEstimator()
    builder = ContextBuilder(budget=budget, estimator=estimator)

    messages = (
        ModelMessage(
            role=ModelMessageRole.USER,
            content=user_query,
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

    # 7. Model Execution & Hit Snapshot Verification
    fake_model = FakeModelProvider(
        responses=[
            ModelResponse(
                text="Based on [S1], SQLite WAL mode allows concurrent access because changes are written to a separate WAL file instead of the main database.",
                tool_calls=(),
            )
        ]
    )

    loop = AgentLoop(
        model=fake_model,
        executor=ToolExecutor(ToolRegistry()),
        tool_snapshot=ToolSnapshot(bindings=()),
        context_builder=builder,
    )

    result = await loop.run(
        model_name="fake-gpt",
        system_prompt=aug.system_prompt,
        messages=messages,
        run_id=run_id,
        conversation_id=conv_id,
    )

    assert result.status == RunStatus.COMPLETED
    assert "Based on [S1]" in (result.text or "")

    # 8. Verify SQLite persistence of retrieval hit snapshots
    saved_hits = await repo.list_retrieval_hits_for_run(run_id)
    assert len(saved_hits) == len(aug.retrieval_result.hits)
    assert saved_hits[0].citation_label == "S1"
    assert saved_hits[0].document_name_snapshot == "sqlite_concurrency.md"

    # Cleanup
    vector_store.close()
    await starter.aclose()
    await finisher.aclose()
    await run_repo.aclose()
    await conv_repo.aclose()
    await repo.aclose()
