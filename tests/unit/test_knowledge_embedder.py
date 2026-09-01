from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from alembic.config import Config

from alembic import command
from asagent.core.ids import ChunkId, DocumentId, ProfileId
from asagent.knowledge.chunker import CHUNKER_VERSION
from asagent.knowledge.embedder import (
    DEFAULT_EMBEDDING_DIMENSION,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_REVISION,
    LocalMiniLMEmbedder,
    create_pending_embeddings_for_chunks,
    ensure_default_profile,
    generate_point_id,
)
from asagent.knowledge.models import (
    KnowledgeChunk,
    KnowledgeIndexProfile,
)
from asagent.storage.sqlite.knowledge_repository import (
    SqliteKnowledgeRepository,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MODEL_DIR = (
    _PROJECT_ROOT / "app-assets" / "models" / "paraphrase-multilingual-MiniLM-L12-v2"
)


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


@pytest.fixture
async def sqlite_repo(
    tmp_path: Path,
) -> AsyncIterator[SqliteKnowledgeRepository]:
    db_path = tmp_path / "asagent.sqlite3"
    _upgrade(db_path)
    repo = SqliteKnowledgeRepository(db_path)
    try:
        yield repo
    finally:
        await repo.aclose()


def test_embedder_inference_and_cross_lingual_similarity() -> None:
    embedder = LocalMiniLMEmbedder(_MODEL_DIR)

    # 1. Tokenizer count
    tok_en = embedder.count_tokens("Hello world")
    tok_zh = embedder.count_tokens("你好，世界！")
    assert tok_en > 0
    assert tok_zh > 0

    # 2. Batch encode shape and L2 normalization
    texts = [
        "What is the capital of France?",
        "Paris is the capital of France.",
        "法国的首都是巴黎。",
        "How to make pasta with olive oil.",
    ]
    vectors = embedder.encode(texts)
    assert vectors.shape == (4, DEFAULT_EMBEDDING_DIMENSION)

    for i in range(len(texts)):
        norm = float(np.linalg.norm(vectors[i]))
        assert pytest.approx(norm, abs=1e-5) == 1.0

    # 3. Semantic similarity
    def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b))

    sim_en = cosine_sim(vectors[0], vectors[1])
    sim_zh = cosine_sim(vectors[0], vectors[2])
    sim_unrelated = cosine_sim(vectors[0], vectors[3])

    assert sim_en > 0.70, f"Expected EN match > 0.70, got {sim_en}"
    assert sim_zh > 0.75, f"Expected cross-lingual ZH match > 0.75, got {sim_zh}"
    assert sim_unrelated < 0.25, f"Expected unrelated < 0.25, got {sim_unrelated}"
    assert sim_zh > sim_unrelated

    # 4. embed_query
    q_vec = embedder.embed_query("Query string")
    assert len(q_vec) == DEFAULT_EMBEDDING_DIMENSION


def test_embedder_missing_model_raises(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        LocalMiniLMEmbedder(empty_dir)


async def test_ensure_default_profile(
    sqlite_repo: SqliteKnowledgeRepository,
) -> None:
    # First call creates the profile
    p1 = await ensure_default_profile(sqlite_repo)
    assert p1.embedding_model == DEFAULT_EMBEDDING_MODEL
    assert p1.embedding_dimension == 384
    assert p1.status == "active"

    # Second call reuses existing active profile
    p2 = await ensure_default_profile(sqlite_repo)
    assert p2.profile_id == p1.profile_id


async def test_profile_revision_change_activates_new_profile(
    sqlite_repo: SqliteKnowledgeRepository,
) -> None:
    now = datetime(2026, 8, 31, 13, 0, tzinfo=UTC)
    old_profile = KnowledgeIndexProfile(
        profile_id=ProfileId("prof_old"),
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        embedding_revision="older-revision",
        embedding_dimension=DEFAULT_EMBEDDING_DIMENSION,
        embedding_normalized=True,
        chunker_version=CHUNKER_VERSION,
        qdrant_collection="knowledge_chunks_v1",
        status="active",
        created_at=now,
        activated_at=now,
    )
    await sqlite_repo.save_profile(old_profile)

    active = await ensure_default_profile(
        sqlite_repo, now=now, profile_id=ProfileId("prof_current")
    )

    assert active.profile_id == "prof_current"
    assert active.embedding_revision == DEFAULT_EMBEDDING_REVISION
    retired = await sqlite_repo.get_profile(ProfileId("prof_old"))
    assert retired is not None
    assert retired.status == "retired"


def test_pending_embeddings_generation() -> None:
    now = datetime(2026, 8, 31, 13, 0, 0, tzinfo=UTC)
    doc_id = DocumentId("doc_1")
    prof_id = ProfileId("prof_1")

    chunk1 = KnowledgeChunk(
        chunk_id=ChunkId("chk_1"),
        document_id=doc_id,
        document_content_hash="h1",
        chunk_index=0,
        text="Chunk one",
        token_count=2,
        content_hash="chkhash1",
        chunker_version="v1",
        status="active",
        created_at=now,
    )
    chunk2 = KnowledgeChunk(
        chunk_id=ChunkId("chk_2"),
        document_id=doc_id,
        document_content_hash="h1",
        chunk_index=1,
        text="Chunk two",
        token_count=2,
        content_hash="chkhash2",
        chunker_version="v1",
        status="active",
        created_at=now,
    )

    pending = create_pending_embeddings_for_chunks([chunk1, chunk2], prof_id, now=now)
    assert len(pending) == 2
    assert pending[0].status == "pending"
    assert pending[0].point_id == generate_point_id(prof_id, ChunkId("chk_1"))
    assert pending[1].point_id == generate_point_id(prof_id, ChunkId("chk_2"))
