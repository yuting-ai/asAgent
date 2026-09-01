from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from asagent.core.ids import (
    ChunkId,
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
    KnowledgeCitation,
    KnowledgeDocument,
    KnowledgeIndexJob,
    KnowledgeIndexProfile,
    KnowledgeLibrary,
    KnowledgeRetrievalHit,
    KnowledgeSource,
    normalize_library_name,
)
from asagent.knowledge.repository import KnowledgeRepository


def test_normalize_library_name() -> None:
    assert normalize_library_name("  Research Papers  ") == "research papers"
    assert normalize_library_name("Deep Learning 2026") == "deep learning 2026"
    assert normalize_library_name("   ") == ""


def test_knowledge_library_immutability() -> None:
    now = datetime.now(UTC)
    lib = KnowledgeLibrary(
        library_id=LibraryId("lib_1"),
        user_id=UserId("user_1"),
        name="Research Papers",
        normalized_name="research papers",
        status="active",
        created_at=now,
        updated_at=now,
    )
    assert lib.library_id == "lib_1"
    assert lib.status == "active"
    with pytest.raises(FrozenInstanceError):
        lib.name = "New Name"  # type: ignore[misc]


def test_knowledge_source_immutability_and_defaults() -> None:
    now = datetime.now(UTC)
    src = KnowledgeSource(
        source_id=SourceId("src_1"),
        library_id=LibraryId("lib_1"),
        display_path="~/Papers",
        canonical_path="/Users/user/Papers",
        status="active",
        scan_status="ready",
        created_at=now,
        updated_at=now,
    )
    assert src.last_scanned_at is None
    assert src.detached_at is None
    with pytest.raises(FrozenInstanceError):
        src.status = "detached"  # type: ignore[misc]


def test_knowledge_document_and_chunk_immutability() -> None:
    now = datetime.now(UTC)
    doc = KnowledgeDocument(
        document_id=DocumentId("doc_1"),
        source_id=SourceId("src_1"),
        relative_path="ai/transformer.pdf",
        file_type="pdf",
        status="active",
        size_bytes=102400,
        mtime_ns=1700000000000000000,
        content_hash="abc123hash",
        parser_version="pypdf-v1",
        current_chunker_version="minilm-token-v1",
        created_at=now,
        updated_at=now,
    )
    assert doc.last_indexed_at is None
    assert doc.last_error_code is None

    chk = KnowledgeChunk(
        chunk_id=ChunkId("chk_1"),
        document_id=DocumentId("doc_1"),
        document_content_hash="abc123hash",
        chunk_index=0,
        text="Attention is all you need.",
        token_count=6,
        content_hash="chunkhash1",
        chunker_version="minilm-token-v1",
        status="active",
        created_at=now,
        page_start=1,
        page_end=1,
        section_title="Introduction",
    )
    assert chk.superseded_at is None
    with pytest.raises(FrozenInstanceError):
        chk.status = "superseded"  # type: ignore[misc]


def test_knowledge_index_profile_and_embedding() -> None:
    now = datetime.now(UTC)
    profile = KnowledgeIndexProfile(
        profile_id=ProfileId("prof_1"),
        embedding_model="paraphrase-multilingual-MiniLM-L12-v2",
        embedding_revision="e8f8c21",
        embedding_dimension=384,
        embedding_normalized=True,
        chunker_version="minilm-token-v1",
        qdrant_collection="knowledge_chunks_prof_1",
        status="active",
        created_at=now,
        activated_at=now,
    )
    assert profile.embedding_dimension == 384

    emb = KnowledgeChunkEmbedding(
        chunk_id=ChunkId("chk_1"),
        profile_id=ProfileId("prof_1"),
        point_id="550e8400-e29b-41d4-a716-446655440000",
        status="indexed",
        retry_count=0,
        created_at=now,
        updated_at=now,
        indexed_at=now,
    )
    assert emb.status == "indexed"


def test_knowledge_index_job() -> None:
    now = datetime.now(UTC)
    job = KnowledgeIndexJob(
        job_id=IndexJobId("job_1"),
        library_id=LibraryId("lib_1"),
        kind="initial",
        status="running",
        discovered_files=10,
        processed_files=5,
        skipped_files=2,
        failed_files=0,
        total_chunks=50,
        indexed_chunks=40,
        cancel_requested=False,
        created_at=now,
        updated_at=now,
    )
    assert job.source_id is None
    assert not job.cancel_requested


def test_knowledge_retrieval_hit_and_citation() -> None:
    now = datetime.now(UTC)
    hit = KnowledgeRetrievalHit(
        run_id=RunId("run_1"),
        rank=1,
        chunk_id=ChunkId("chk_1"),
        profile_id=ProfileId("prof_1"),
        score=0.9123,
        citation_label="S1",
        document_name_snapshot="transformer.pdf",
        source_path_snapshot="/Users/user/Papers",
        content_hash_snapshot="chunkhash1",
        snippet_snapshot="Attention is all you need...",
        created_at=now,
        page_start_snapshot=1,
        page_end_snapshot=2,
        section_title_snapshot="Architecture",
    )
    assert hit.rank == 1
    assert hit.citation_label == "S1"

    cit = KnowledgeCitation(
        label="S1",
        document_name="transformer.pdf",
        source_path="/Users/user/Papers",
        snippet="Attention is all you need...",
        score=0.9123,
        page_start=1,
        page_end=2,
        section_title="Architecture",
    )
    assert cit.label == "S1"


def test_knowledge_repository_protocol_runtime_checkable() -> None:
    class DummyRepo:
        pass

    assert not isinstance(DummyRepo(), KnowledgeRepository)


def test_core_does_not_import_database_or_web_frameworks() -> None:
    import ast
    from pathlib import Path

    knowledge_dir = (
        Path(__file__).resolve().parents[2] / "src" / "asagent" / "knowledge"
    )
    for py_file in knowledge_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    for forbidden in [
                        "sqlalchemy",
                        "qdrant_client",
                        "fastapi",
                        "electron",
                    ]:
                        assert not name.name.startswith(forbidden), (
                            f"Forbidden import {name.name} in {py_file.name}"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                for forbidden in [
                    "sqlalchemy",
                    "qdrant_client",
                    "fastapi",
                    "electron",
                ]:
                    assert not node.module.startswith(forbidden), (
                        f"Forbidden import from {node.module} in {py_file.name}"
                    )
