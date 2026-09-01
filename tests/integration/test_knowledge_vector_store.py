import io
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pypdf
import pytest
from alembic.config import Config
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from alembic import command
from asagent.core.ids import (
    DocumentId,
    LibraryId,
    ProfileId,
    SourceId,
    UserId,
)
from asagent.knowledge.embedder import (
    LocalMiniLMEmbedder,
    ensure_default_profile,
)
from asagent.knowledge.indexer import KnowledgeIndexer
from asagent.knowledge.models import (
    KnowledgeLibrary,
    KnowledgeSource,
)
from asagent.storage.qdrant import (
    KnowledgeVectorStore,
    VectorPoint,
)
from asagent.storage.sqlite.knowledge_repository import (
    SqliteKnowledgeRepository,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MODEL_DIR = (
    _PROJECT_ROOT / "app-assets" / "models" / "paraphrase-multilingual-MiniLM-L12-v2"
)


def _make_pdf(pages_text: list[str]) -> bytes:
    writer = pypdf.PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    for text in pages_text:
        page = writer.add_blank_page(width=300, height=300)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        escaped_text = (
            text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        )
        stream.set_data(
            f"BT /F1 12 Tf 50 250 Td ({escaped_text}) Tj ET".encode(
                "latin1", errors="replace"
            )
        )
        page[NameObject("/Contents")] = stream

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


@pytest.fixture
def embedder() -> LocalMiniLMEmbedder:
    return LocalMiniLMEmbedder(_MODEL_DIR)


@pytest.fixture
def vector_store(tmp_path: Path) -> KnowledgeVectorStore:
    qdrant_dir = tmp_path / "qdrant_db"
    store = KnowledgeVectorStore(qdrant_dir)
    try:
        return store
    finally:
        store.close()


def test_vector_store_lifecycle_and_search(
    embedder: LocalMiniLMEmbedder, tmp_path: Path
) -> None:
    qdrant_dir = tmp_path / "qdrant_lifecycle"
    store = KnowledgeVectorStore(qdrant_dir)
    coll_name = "test_chunks_coll"

    try:
        # 1. Ensure collection
        store.ensure_collection(coll_name, dimension=384)
        assert store.count_points(coll_name) == 0

        # 2. Upsert points
        texts = [
            "Deep learning neural networks and backpropagation",
            "Italian culinary pasta recipe with parmesan and olive oil",
            "SQLite database transactions and WAL journal mode",
        ]
        vectors = embedder.encode(texts)

        points = [
            VectorPoint(
                point_id="11111111-1111-1111-1111-111111111111",
                vector=vectors[0].tolist(),
                payload={
                    "chunk_id": "chk_ai",
                    "library_id": "lib_ai",
                    "source_id": "src_1",
                    "document_id": "doc_1",
                    "status": "active",
                },
            ),
            VectorPoint(
                point_id="22222222-2222-2222-2222-222222222222",
                vector=vectors[1].tolist(),
                payload={
                    "chunk_id": "chk_pasta",
                    "library_id": "lib_cooking",
                    "source_id": "src_2",
                    "document_id": "doc_2",
                    "status": "active",
                },
            ),
            VectorPoint(
                point_id="33333333-3333-3333-3333-333333333333",
                vector=vectors[2].tolist(),
                payload={
                    "chunk_id": "chk_db",
                    "library_id": "lib_ai",
                    "source_id": "src_1",
                    "document_id": "doc_3",
                    "status": "active",
                },
            ),
        ]
        store.upsert_points(coll_name, points)
        assert store.count_points(coll_name) == 3

        # 3. Search with library filter
        q_vec = embedder.embed_query("artificial neural networks training")
        hits = store.search(coll_name, q_vec, library_id=LibraryId("lib_ai"), limit=5)
        assert len(hits) == 2
        assert hits[0].chunk_id == "chk_ai"
        assert hits[0].score > 0.60

        # Searching for pasta in lib_ai returns 0 hits because it's in lib_cooking
        q_pasta = embedder.embed_query("how to boil pasta")
        hits_filtered = store.search(
            coll_name, q_pasta, library_id=LibraryId("lib_ai"), limit=5
        )
        assert all(h.chunk_id != "chk_pasta" for h in hits_filtered)

        store.set_source_status(coll_name, SourceId("src_1"), active=False)
        assert (
            store.search(coll_name, q_vec, library_id=LibraryId("lib_ai"), limit=5)
            == ()
        )
        store.set_source_status(coll_name, SourceId("src_1"), active=True)
        assert (
            len(store.search(coll_name, q_vec, library_id=LibraryId("lib_ai"), limit=5))
            == 2
        )

        # 4. Deletion by document
        store.delete_by_document(coll_name, DocumentId("doc_1"))
        hits_after_del = store.search(
            coll_name, q_vec, library_id=LibraryId("lib_ai"), limit=5
        )
        assert len(hits_after_del) == 1
        assert hits_after_del[0].chunk_id == "chk_db"

    finally:
        store.close()


async def test_dual_write_indexing_end_to_end(
    embedder: LocalMiniLMEmbedder, tmp_path: Path
) -> None:
    # 1. Setup SQLite & Qdrant
    db_path = tmp_path / "asagent.sqlite3"
    _upgrade(db_path)
    repo = SqliteKnowledgeRepository(db_path)

    qdrant_dir = tmp_path / "qdrant_e2e"
    vector_store = KnowledgeVectorStore(qdrant_dir)

    now = datetime(2026, 8, 31, 13, 0, 0, tzinfo=UTC)
    indexer = KnowledgeIndexer(
        repository=repo,
        embedder=embedder,
        vector_store=vector_store,
        now=lambda: now,
    )

    user_id = UserId("u_rag")
    lib = KnowledgeLibrary(
        library_id=LibraryId("lib_rag"),
        user_id=user_id,
        name="RAG Library",
        normalized_name="rag library",
        status="active",
        created_at=now,
        updated_at=now,
    )
    await repo.save_library(lib)

    source_dir = tmp_path / "source_docs"
    source_dir.mkdir()

    src = KnowledgeSource(
        source_id=SourceId("src_rag"),
        library_id=LibraryId("lib_rag"),
        display_path=str(source_dir),
        canonical_path=str(source_dir.resolve()),
        status="active",
        scan_status="queued",
        created_at=now,
        updated_at=now,
    )
    await repo.save_source(src)

    # 2. Add files
    md_file = source_dir / "transformers.md"
    md_file.write_text(
        "# Attention Is All You Need\n\n"
        "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.\n\n"
        "## Multi-Head Attention\n\n"
        "Multi-head attention allows the model to jointly attend to information from different representation subspaces.",
        encoding="utf-8",
    )

    pdf_file = source_dir / "sqlite.pdf"
    pdf_file.write_bytes(
        _make_pdf(["SQLite implements ACID transactions with WAL mode."])
    )

    try:
        # 3. Run Indexer with dual-write
        stats = await indexer.index_source(src.source_id)
        assert stats.total_scanned == 2
        assert stats.added_docs == 2
        assert stats.total_chunks >= 2
        assert stats.indexed_chunks == stats.total_chunks

        # 4. Verify SQLite consistency
        profile = await ensure_default_profile(repo, now=now)
        docs = await repo.list_documents_for_source(src.source_id)
        assert len(docs) == 2

        for doc in docs:
            chunks = await repo.list_active_chunks_for_document(doc.document_id)
            assert len(chunks) > 0
            for chk in chunks:
                emb = await repo.get_chunk_embedding(chk.chunk_id, profile.profile_id)
                assert emb is not None
                assert emb.status == "indexed"
                assert emb.indexed_at is not None

        # 5. Verify Qdrant vector search
        query_vec = embedder.embed_query("multi-head self-attention mechanism")
        hits = vector_store.search(
            profile.qdrant_collection,
            query_vec,
            library_id=LibraryId("lib_rag"),
            limit=3,
        )
        assert len(hits) > 0
        assert hits[0].score > 0.60
        assert hits[0].payload.get("document_id") is not None
        assert hits[0].payload.get("library_id") == "lib_rag"

        rebuilt_profile = replace(
            profile,
            profile_id=ProfileId("prof_rebuilt"),
            created_at=now + timedelta(seconds=1),
            activated_at=now + timedelta(seconds=1),
        )
        await repo.save_profile(rebuilt_profile)
        rebuild_stats = await indexer.index_source(src.source_id, kind="rebuild")
        assert rebuild_stats.unchanged_docs == 2
        assert rebuild_stats.indexed_chunks == stats.total_chunks
        rebuilt_hits = vector_store.search(
            rebuilt_profile.qdrant_collection,
            query_vec,
            library_id=LibraryId("lib_rag"),
            profile_id=rebuilt_profile.profile_id,
            limit=3,
        )
        assert rebuilt_hits

    finally:
        vector_store.close()
        await repo.aclose()
