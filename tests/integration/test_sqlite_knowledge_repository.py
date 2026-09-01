from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from asagent.core.ids import (
    ChunkId,
    ConversationId,
    DocumentId,
    IndexJobId,
    LibraryId,
    ProfileId,
    RunId,
    SourceId,
    UserId,
)
from asagent.knowledge.models import (
    KnowledgeChunk,
    KnowledgeChunkEmbedding,
    KnowledgeDocument,
    KnowledgeIndexJob,
    KnowledgeIndexProfile,
    KnowledgeLibrary,
    KnowledgeRetrievalHit,
    KnowledgeSource,
    normalize_library_name,
)
from asagent.knowledge.repository import KnowledgeRepository
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.knowledge_repository import (
    SqliteKnowledgeRepository,
)
from asagent.storage.sqlite.run_repository import (
    SqliteRunRepository,
)


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


@pytest.fixture
async def knowledge_repo(
    tmp_path: Path,
) -> AsyncIterator[SqliteKnowledgeRepository]:
    db_path = tmp_path / "asagent.sqlite3"
    _upgrade(db_path)
    repo = SqliteKnowledgeRepository(db_path)
    try:
        yield repo
    finally:
        await repo.aclose()


def test_repository_protocol_compliance(
    knowledge_repo: SqliteKnowledgeRepository,
) -> None:
    assert isinstance(knowledge_repo, KnowledgeRepository)


async def test_library_lifecycle_and_uniqueness(
    knowledge_repo: SqliteKnowledgeRepository,
) -> None:
    user_id = UserId("user_test")
    now = datetime.now(UTC)

    lib1 = KnowledgeLibrary(
        library_id=LibraryId("lib_1"),
        user_id=user_id,
        name="Research Papers",
        normalized_name=normalize_library_name("Research Papers"),
        status="active",
        created_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_library(lib1)

    fetched = await knowledge_repo.get_library(LibraryId("lib_1"))
    assert fetched is not None
    assert fetched.name == "Research Papers"
    assert fetched.normalized_name == "research papers"

    count = await knowledge_repo.count_libraries_for_user(user_id)
    assert count == 1

    lib2 = KnowledgeLibrary(
        library_id=LibraryId("lib_2"),
        user_id=user_id,
        name="Books",
        normalized_name=normalize_library_name("Books"),
        status="active",
        created_at=now + timedelta(seconds=1),
        updated_at=now + timedelta(seconds=1),
    )
    await knowledge_repo.save_library(lib2)

    libs = await knowledge_repo.list_libraries_for_user(user_id)
    assert len(libs) == 2
    assert [lib.library_id for lib in libs] == ["lib_1", "lib_2"]

    # Delete library
    deleted = await knowledge_repo.delete_library(LibraryId("lib_2"))
    assert deleted
    assert await knowledge_repo.get_library(LibraryId("lib_2")) is None
    await knowledge_repo.save_library(
        KnowledgeLibrary(
            library_id=LibraryId("lib_3"),
            user_id=user_id,
            name="Books",
            normalized_name=normalize_library_name("Books"),
            status="active",
            created_at=now + timedelta(seconds=2),
            updated_at=now + timedelta(seconds=2),
        )
    )
    assert await knowledge_repo.get_library(LibraryId("lib_3")) is not None
    assert await knowledge_repo.count_libraries_for_user(user_id) == 2


async def test_sources_lifecycle(
    knowledge_repo: SqliteKnowledgeRepository,
) -> None:
    user_id = UserId("user_src")
    now = datetime.now(UTC)

    lib = KnowledgeLibrary(
        library_id=LibraryId("lib_src"),
        user_id=user_id,
        name="My Docs",
        normalized_name="my docs",
        status="active",
        created_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_library(lib)

    src = KnowledgeSource(
        source_id=SourceId("src_1"),
        library_id=LibraryId("lib_src"),
        display_path="~/Documents/AI",
        canonical_path="/Users/user/Documents/AI",
        status="active",
        scan_status="idle",
        created_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_source(src)

    fetched = await knowledge_repo.get_source(SourceId("src_1"))
    assert fetched is not None
    assert fetched.canonical_path == "/Users/user/Documents/AI"

    by_path = await knowledge_repo.get_source_by_canonical_path(
        LibraryId("lib_src"), "/Users/user/Documents/AI"
    )
    assert by_path is not None
    assert by_path.source_id == "src_1"

    # Update scan status
    scan_time = now + timedelta(seconds=5)
    await knowledge_repo.update_source_scan_status(
        SourceId("src_1"), "indexing", last_scanned_at=scan_time
    )
    updated_src = await knowledge_repo.get_source(SourceId("src_1"))
    assert updated_src is not None
    assert updated_src.scan_status == "indexing"
    assert updated_src.last_scanned_at is not None

    # Update source status (soft detach)
    detach_time = now + timedelta(seconds=10)
    await knowledge_repo.update_source_status(
        SourceId("src_1"), "detached", detached_at=detach_time
    )
    detached_src = await knowledge_repo.get_source(SourceId("src_1"))
    assert detached_src is not None
    assert detached_src.status == "detached"
    assert detached_src.detached_at is not None


async def test_document_and_chunks_lifecycle(
    knowledge_repo: SqliteKnowledgeRepository,
) -> None:
    user_id = UserId("user_doc")
    now = datetime.now(UTC)

    lib = KnowledgeLibrary(
        library_id=LibraryId("lib_doc"),
        user_id=user_id,
        name="Doc Lib",
        normalized_name="doc lib",
        status="active",
        created_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_library(lib)

    src = KnowledgeSource(
        source_id=SourceId("src_doc"),
        library_id=LibraryId("lib_doc"),
        display_path="~/Docs",
        canonical_path="/Users/user/Docs",
        status="active",
        scan_status="ready",
        created_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_source(src)

    doc = KnowledgeDocument(
        document_id=DocumentId("doc_1"),
        source_id=SourceId("src_doc"),
        relative_path="papers/rag.pdf",
        file_type="pdf",
        status="active",
        size_bytes=2048,
        mtime_ns=1700000000,
        content_hash="hash_v1",
        parser_version="pypdf-v1",
        current_chunker_version="chunker-v1",
        created_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_document(doc)

    fetched_doc = await knowledge_repo.get_document(DocumentId("doc_1"))
    assert fetched_doc is not None
    assert fetched_doc.relative_path == "papers/rag.pdf"

    by_rel = await knowledge_repo.get_document_by_relative_path(
        SourceId("src_doc"), "papers/rag.pdf"
    )
    assert by_rel is not None
    assert by_rel.document_id == "doc_1"

    # Save chunks
    chk1 = KnowledgeChunk(
        chunk_id=ChunkId("chk_1"),
        document_id=DocumentId("doc_1"),
        document_content_hash="hash_v1",
        chunk_index=0,
        text="Section 1 of RAG",
        token_count=5,
        content_hash="chkhash_1",
        chunker_version="chunker-v1",
        status="active",
        created_at=now,
        page_start=1,
        page_end=1,
    )
    chk2 = KnowledgeChunk(
        chunk_id=ChunkId("chk_2"),
        document_id=DocumentId("doc_1"),
        document_content_hash="hash_v1",
        chunk_index=1,
        text="Section 2 of RAG",
        token_count=5,
        content_hash="chkhash_2",
        chunker_version="chunker-v1",
        status="active",
        created_at=now,
        page_start=2,
        page_end=2,
    )
    await knowledge_repo.save_chunks([chk1, chk2])

    active_chunks = await knowledge_repo.list_active_chunks_for_document(
        DocumentId("doc_1")
    )
    assert len(active_chunks) == 2
    assert [c.chunk_id for c in active_chunks] == ["chk_1", "chk_2"]

    batch_chunks = await knowledge_repo.get_chunks_batch(
        [ChunkId("chk_2"), ChunkId("chk_1")]
    )
    assert len(batch_chunks) == 2
    assert [c.chunk_id for c in batch_chunks] == ["chk_2", "chk_1"]

    # Supersede chk1
    superseded_time = now + timedelta(minutes=1)
    await knowledge_repo.supersede_chunks(
        [ChunkId("chk_1")], superseded_at=superseded_time
    )
    active_after = await knowledge_repo.list_active_chunks_for_document(
        DocumentId("doc_1")
    )
    assert len(active_after) == 1
    assert active_after[0].chunk_id == "chk_2"

    chk1_fetched = await knowledge_repo.get_chunk(ChunkId("chk_1"))
    assert chk1_fetched is not None
    assert chk1_fetched.status == "superseded"
    assert chk1_fetched.superseded_at is not None


async def test_index_profile_and_embeddings(
    knowledge_repo: SqliteKnowledgeRepository,
) -> None:
    user_id = UserId("user_prof")
    now = datetime.now(UTC)

    lib = KnowledgeLibrary(
        library_id=LibraryId("lib_p"),
        user_id=user_id,
        name="Profile Lib",
        normalized_name="profile lib",
        status="active",
        created_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_library(lib)
    src = KnowledgeSource(
        source_id=SourceId("src_p"),
        library_id=LibraryId("lib_p"),
        display_path="~/P",
        canonical_path="/Users/user/P",
        status="active",
        scan_status="ready",
        created_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_source(src)
    doc = KnowledgeDocument(
        document_id=DocumentId("doc_p"),
        source_id=SourceId("src_p"),
        relative_path="f.txt",
        file_type="text",
        status="active",
        size_bytes=100,
        mtime_ns=100,
        content_hash="h",
        parser_version="v1",
        current_chunker_version="v1",
        created_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_document(doc)
    chk = KnowledgeChunk(
        chunk_id=ChunkId("chk_p"),
        document_id=DocumentId("doc_p"),
        document_content_hash="h",
        chunk_index=0,
        text="text",
        token_count=1,
        content_hash="chkh",
        chunker_version="v1",
        status="active",
        created_at=now,
    )
    await knowledge_repo.save_chunks([chk])

    prof = KnowledgeIndexProfile(
        profile_id=ProfileId("prof_minilm_v1"),
        embedding_model="paraphrase-multilingual-MiniLM-L12-v2",
        embedding_revision="e8f8c21",
        embedding_dimension=384,
        embedding_normalized=True,
        chunker_version="chunker-v1",
        qdrant_collection="knowledge_chunks_v1",
        status="active",
        created_at=now,
        activated_at=now,
    )
    await knowledge_repo.save_profile(prof)

    active_prof = await knowledge_repo.get_active_profile()
    assert active_prof is not None
    assert active_prof.profile_id == "prof_minilm_v1"
    assert active_prof.embedding_normalized is True

    emb = KnowledgeChunkEmbedding(
        chunk_id=ChunkId("chk_p"),
        profile_id=ProfileId("prof_minilm_v1"),
        point_id="pt-123",
        status="pending",
        retry_count=0,
        created_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_chunk_embeddings([emb])

    pending = await knowledge_repo.list_pending_chunk_embeddings(
        ProfileId("prof_minilm_v1")
    )
    assert len(pending) == 1
    assert pending[0].chunk_id == "chk_p"

    # Update embedding status to indexed
    idx_time = now + timedelta(seconds=2)
    await knowledge_repo.update_chunk_embedding_status(
        ChunkId("chk_p"),
        ProfileId("prof_minilm_v1"),
        status="indexed",
        indexed_at=idx_time,
    )

    emb_fetched = await knowledge_repo.get_chunk_embedding(
        ChunkId("chk_p"), ProfileId("prof_minilm_v1")
    )
    assert emb_fetched is not None
    assert emb_fetched.status == "indexed"
    assert emb_fetched.indexed_at is not None

    pending_after = await knowledge_repo.list_pending_chunk_embeddings(
        ProfileId("prof_minilm_v1")
    )
    assert len(pending_after) == 0


async def test_index_jobs_lifecycle_and_interruption_recovery(
    knowledge_repo: SqliteKnowledgeRepository,
) -> None:
    user_id = UserId("user_job")
    now = datetime.now(UTC)

    lib = KnowledgeLibrary(
        library_id=LibraryId("lib_j"),
        user_id=user_id,
        name="Job Lib",
        normalized_name="job lib",
        status="active",
        created_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_library(lib)
    src = KnowledgeSource(
        source_id=SourceId("src_j"),
        library_id=LibraryId("lib_j"),
        display_path="~/J",
        canonical_path="/Users/user/J",
        status="active",
        scan_status="idle",
        created_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_source(src)

    job = KnowledgeIndexJob(
        job_id=IndexJobId("job_1"),
        library_id=LibraryId("lib_j"),
        source_id=SourceId("src_j"),
        kind="initial",
        status="running",
        discovered_files=20,
        processed_files=5,
        skipped_files=0,
        failed_files=0,
        total_chunks=100,
        indexed_chunks=25,
        cancel_requested=False,
        created_at=now,
        started_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_index_job(job)

    active_job = await knowledge_repo.get_active_index_job_for_source(SourceId("src_j"))
    assert active_job is not None
    assert active_job.job_id == "job_1"

    # Progress update
    await knowledge_repo.update_index_job_progress(
        IndexJobId("job_1"),
        discovered_files=20,
        processed_files=10,
        skipped_files=0,
        failed_files=0,
        total_chunks=100,
        indexed_chunks=50,
    )
    updated_job = await knowledge_repo.get_index_job(IndexJobId("job_1"))
    assert updated_job is not None
    assert updated_job.processed_files == 10
    assert updated_job.indexed_chunks == 50

    # Request cancel
    assert await knowledge_repo.request_index_job_cancel(IndexJobId("job_1"))
    canceled_job = await knowledge_repo.get_index_job(IndexJobId("job_1"))
    assert canceled_job is not None
    assert canceled_job.cancel_requested is True

    # Interruption recovery
    recovered_count = await knowledge_repo.recover_interrupted_jobs()
    assert recovered_count == 1
    interrupted_job = await knowledge_repo.get_index_job(IndexJobId("job_1"))
    assert interrupted_job is not None
    assert interrupted_job.status == "interrupted"
    assert interrupted_job.last_error_code == "JOB_INTERRUPTED_ON_RESTART"


async def test_retrieval_hits_and_conversation_binding(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "asagent.sqlite3"
    _upgrade(db_path)
    knowledge_repo = SqliteKnowledgeRepository(db_path)
    conv_repo = SqliteConversationRepository(db_path)
    run_repo = SqliteRunRepository(db_path)

    user_id = UserId("user_rag")
    now = datetime.now(UTC)

    # 1. Setup Library, Source, Document, Chunk, Profile
    lib = KnowledgeLibrary(
        library_id=LibraryId("lib_r"),
        user_id=user_id,
        name="RAG Lib",
        normalized_name="rag lib",
        status="active",
        created_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_library(lib)

    src = KnowledgeSource(
        source_id=SourceId("src_r"),
        library_id=LibraryId("lib_r"),
        display_path="~/R",
        canonical_path="/Users/user/R",
        status="active",
        scan_status="ready",
        created_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_source(src)

    doc = KnowledgeDocument(
        document_id=DocumentId("doc_r"),
        source_id=SourceId("src_r"),
        relative_path="note.md",
        file_type="markdown",
        status="active",
        size_bytes=100,
        mtime_ns=100,
        content_hash="ch",
        parser_version="v1",
        current_chunker_version="v1",
        created_at=now,
        updated_at=now,
    )
    await knowledge_repo.save_document(doc)

    chk = KnowledgeChunk(
        chunk_id=ChunkId("chk_r"),
        document_id=DocumentId("doc_r"),
        document_content_hash="ch",
        chunk_index=0,
        text="Knowledge content",
        token_count=2,
        content_hash="chkh",
        chunker_version="v1",
        status="active",
        created_at=now,
    )
    await knowledge_repo.save_chunks([chk])

    prof = KnowledgeIndexProfile(
        profile_id=ProfileId("prof_r"),
        embedding_model="paraphrase-multilingual-MiniLM-L12-v2",
        embedding_revision="e8f8c21",
        embedding_dimension=384,
        embedding_normalized=True,
        chunker_version="v1",
        qdrant_collection="c_r",
        status="active",
        created_at=now,
    )
    await knowledge_repo.save_profile(prof)

    # 2. Setup Conversation & Run
    from asagent.core.conversation import Conversation
    from asagent.core.run import Run

    conv = Conversation(
        conversation_id=ConversationId("conv_rag"),
        user_id=user_id,
        created_at=now,
        updated_at=now,
        title="Knowledge Conversation",
        kind="knowledge",
    )
    await conv_repo.save(conv)

    await knowledge_repo.bind_conversation_library(
        ConversationId("conv_rag"), LibraryId("lib_r")
    )
    bound_lib = await knowledge_repo.get_conversation_library(
        ConversationId("conv_rag")
    )
    assert bound_lib == "lib_r"

    from asagent.core.run_status import RunStatus

    run = Run(
        run_id=RunId("run_rag"),
        conversation_id=ConversationId("conv_rag"),
        status=RunStatus.COMPLETED,
        created_at=now,
        updated_at=now,
    )
    await run_repo.save(run)

    # 3. Save & list retrieval hits
    hit1 = KnowledgeRetrievalHit(
        run_id=RunId("run_rag"),
        rank=1,
        chunk_id=ChunkId("chk_r"),
        profile_id=ProfileId("prof_r"),
        score=0.954,
        citation_label="S1",
        document_name_snapshot="note.md",
        source_path_snapshot="/Users/user/R",
        content_hash_snapshot="chkh",
        snippet_snapshot="Knowledge content snippet",
        created_at=now,
        page_start_snapshot=1,
        page_end_snapshot=1,
        section_title_snapshot="Overview",
    )
    await knowledge_repo.save_retrieval_hits([hit1])

    hits = await knowledge_repo.list_retrieval_hits_for_run(RunId("run_rag"))
    assert len(hits) == 1
    assert hits[0].rank == 1
    assert hits[0].citation_label == "S1"
    assert hits[0].score == 0.954
    assert hits[0].document_name_snapshot == "note.md"

    await knowledge_repo.aclose()
    await conv_repo.aclose()
    await run_repo.aclose()
