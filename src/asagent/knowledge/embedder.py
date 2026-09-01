import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]
from tokenizers import Tokenizer

from asagent.core.ids import (
    ChunkId,
    ProfileId,
)
from asagent.knowledge.chunker import CHUNKER_VERSION
from asagent.knowledge.models import (
    KnowledgeChunk,
    KnowledgeChunkEmbedding,
    KnowledgeIndexProfile,
)
from asagent.knowledge.repository import KnowledgeRepository

DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_EMBEDDING_REVISION = "e8f8c21"
DEFAULT_EMBEDDING_DIMENSION = 384
DEFAULT_QDRANT_COLLECTION = "knowledge_chunks_v1"
DEFAULT_MAX_SEQ_LENGTH = 256

_POINT_ID_NAMESPACE = uuid.UUID("a82f3c01-7b89-4d1e-8e56-123456789abc")


def generate_point_id(profile_id: ProfileId, chunk_id: ChunkId) -> str:
    """Generate a deterministic UUID string for a (profile_id, chunk_id) point."""
    return str(uuid.uuid5(_POINT_ID_NAMESPACE, f"{profile_id}:{chunk_id}"))


class LocalMiniLMEmbedder:
    """Offline ONNX Runtime + Tokenizers embedding engine for multilingual MiniLM."""

    def __init__(
        self,
        model_dir: Path,
        *,
        num_threads: int = 4,
        max_seq_length: int = DEFAULT_MAX_SEQ_LENGTH,
    ) -> None:
        tokenizer_path = model_dir / "tokenizer.json"
        model_path = model_dir / "model.onnx"

        if not tokenizer_path.exists():
            raise FileNotFoundError(f"Tokenizer file not found: {tokenizer_path}")
        if not model_path.exists():
            raise FileNotFoundError(f"ONNX model file not found: {model_path}")

        self._tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self._tokenizer.enable_truncation(max_length=max_seq_length)
        self._tokenizer.enable_padding(length=None, pad_id=0, pad_token="[PAD]")

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = num_threads
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._session = ort.InferenceSession(
            str(model_path),
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )
        self._input_names = [inp.name for inp in self._session.get_inputs()]

    def count_tokens(self, text: str) -> int:
        """Count tokens for text using the embedded tokenizer."""
        return len(self._tokenizer.encode(text).ids)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Encode a sequence of texts into (N, 384) L2-normalized float32 vectors."""
        if not texts:
            return np.empty((0, DEFAULT_EMBEDDING_DIMENSION), dtype=np.float32)

        encodings = self._tokenizer.encode_batch(list(texts))
        input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
        token_type_ids = np.array([e.type_ids for e in encodings], dtype=np.int64)

        feed_dict: dict[str, Any] = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        if "token_type_ids" in self._input_names:
            feed_dict["token_type_ids"] = token_type_ids

        outputs = self._session.run(None, feed_dict)
        token_embeddings = outputs[0]  # [batch_size, seq_len, 384]

        # Attention-mask Mean Pooling
        mask_expanded = np.broadcast_to(
            np.expand_dims(attention_mask, -1), token_embeddings.shape
        ).astype(np.float32)
        sum_embeddings = np.sum(token_embeddings * mask_expanded, axis=1)
        sum_mask = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
        mean_pooled = sum_embeddings / sum_mask

        # L2 Normalization
        norms = np.linalg.norm(mean_pooled, ord=2, axis=1, keepdims=True)
        norms = np.clip(norms, a_min=1e-12, a_max=None)
        normalized = mean_pooled / norms
        return normalized.astype(np.float32)

    def embed_texts(self, texts: Sequence[str]) -> tuple[list[float], ...]:
        """Embed texts and return list of standard Python float vectors."""
        matrix = self.encode(texts)
        return tuple([float(x) for x in matrix[i]] for i in range(len(texts)))

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query text."""
        matrix = self.encode([query])
        return [float(x) for x in matrix[0]]


async def ensure_default_profile(
    repository: KnowledgeRepository,
    *,
    now: datetime | None = None,
    profile_id: ProfileId | None = None,
) -> KnowledgeIndexProfile:
    """Ensure the default active Index Profile exists in SQLite."""
    current_time = now or datetime.now(UTC)
    active = await repository.get_active_profile()
    if (
        active is not None
        and active.embedding_model == DEFAULT_EMBEDDING_MODEL
        and active.embedding_revision == DEFAULT_EMBEDDING_REVISION
        and active.embedding_dimension == DEFAULT_EMBEDDING_DIMENSION
        and active.embedding_normalized
        and active.chunker_version == CHUNKER_VERSION
        and active.status == "active"
    ):
        return active

    eff_id = profile_id or ProfileId(f"prof_{uuid.uuid4().hex[:12]}")
    profile = KnowledgeIndexProfile(
        profile_id=eff_id,
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        embedding_revision=DEFAULT_EMBEDDING_REVISION,
        embedding_dimension=DEFAULT_EMBEDDING_DIMENSION,
        embedding_normalized=True,
        chunker_version=CHUNKER_VERSION,
        qdrant_collection=DEFAULT_QDRANT_COLLECTION,
        status="active",
        created_at=current_time,
        activated_at=current_time,
    )
    await repository.save_profile(profile)
    return profile


def create_pending_embeddings_for_chunks(
    chunks: Sequence[KnowledgeChunk],
    profile_id: ProfileId,
    *,
    now: datetime | None = None,
) -> tuple[KnowledgeChunkEmbedding, ...]:
    """Create pending KnowledgeChunkEmbedding records for a sequence of chunks."""
    current_time = now or datetime.now(UTC)
    records: list[KnowledgeChunkEmbedding] = []
    for chunk in chunks:
        point_id = generate_point_id(profile_id, chunk.chunk_id)
        records.append(
            KnowledgeChunkEmbedding(
                chunk_id=chunk.chunk_id,
                profile_id=profile_id,
                point_id=point_id,
                status="pending",
                retry_count=0,
                created_at=current_time,
                updated_at=current_time,
            )
        )
    return tuple(records)
