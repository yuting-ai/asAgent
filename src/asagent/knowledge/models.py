from dataclasses import dataclass
from datetime import datetime
from typing import Literal

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

LibraryStatus = Literal["active", "deleting"]
SourceStatus = Literal["active", "detached", "missing", "deleting"]
SourceScanStatus = Literal["idle", "queued", "scanning", "indexing", "ready", "error"]
DocumentFileType = Literal["pdf", "markdown", "text", "docx", "html"]
DocumentStatus = Literal["active", "missing", "unsupported", "parse_error"]
ChunkStatus = Literal["active", "superseded"]
IndexProfileStatus = Literal["building", "active", "retired", "failed"]
EmbeddingStatus = Literal["pending", "embedding", "indexed", "error", "deleting"]
IndexJobKind = Literal["initial", "rescan", "reactivate", "rebuild", "delete"]
IndexJobStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    "interrupted",
]


def normalize_library_name(name: str) -> str:
    """Normalize a library name for uniqueness checks (stripped and lower-cased)."""
    return name.strip().lower()


@dataclass(frozen=True, slots=True)
class KnowledgeLibrary:
    """A top-level isolated Knowledge Library containing sources, documents, and conversations."""

    library_id: LibraryId
    user_id: UserId
    name: str
    normalized_name: str
    status: LibraryStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class KnowledgeSource:
    """A local directory source added to a Knowledge Library."""

    source_id: SourceId
    library_id: LibraryId
    display_path: str
    canonical_path: str
    status: SourceStatus
    scan_status: SourceScanStatus
    created_at: datetime
    updated_at: datetime
    last_scanned_at: datetime | None = None
    detached_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """A scanned and tracked file within a Knowledge Source."""

    document_id: DocumentId
    source_id: SourceId
    relative_path: str
    file_type: DocumentFileType
    status: DocumentStatus
    size_bytes: int
    mtime_ns: int
    content_hash: str
    parser_version: str
    current_chunker_version: str
    created_at: datetime
    updated_at: datetime
    last_indexed_at: datetime | None = None
    last_error_code: str | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    """An immutable text chunk generated from a Knowledge Document."""

    chunk_id: ChunkId
    document_id: DocumentId
    document_content_hash: str
    chunk_index: int
    text: str
    token_count: int
    content_hash: str
    chunker_version: str
    status: ChunkStatus
    created_at: datetime
    page_start: int | None = None
    page_end: int | None = None
    section_title: str | None = None
    superseded_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeIndexProfile:
    """Defines an embedding model revision, chunking parameters, and Qdrant collection."""

    profile_id: ProfileId
    embedding_model: str
    embedding_revision: str
    embedding_dimension: int
    embedding_normalized: bool
    chunker_version: str
    qdrant_collection: str
    status: IndexProfileStatus
    created_at: datetime
    activated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeChunkEmbedding:
    """The embedding indexing status of a chunk for a specific Index Profile."""

    chunk_id: ChunkId
    profile_id: ProfileId
    point_id: str
    status: EmbeddingStatus
    retry_count: int
    created_at: datetime
    updated_at: datetime
    last_error_code: str | None = None
    indexed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeIndexJob:
    """A background indexing job for scanning, parsing, chunking, and embedding."""

    job_id: IndexJobId
    library_id: LibraryId
    kind: IndexJobKind
    status: IndexJobStatus
    discovered_files: int
    processed_files: int
    skipped_files: int
    failed_files: int
    total_chunks: int
    indexed_chunks: int
    cancel_requested: bool
    created_at: datetime
    updated_at: datetime
    source_id: SourceId | None = None
    last_error_code: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalHit:
    """An immutable record of a chunk retrieved and used in a specific RAG Run."""

    run_id: RunId
    rank: int
    chunk_id: ChunkId
    profile_id: ProfileId
    score: float
    citation_label: str
    document_name_snapshot: str
    source_path_snapshot: str
    content_hash_snapshot: str
    snippet_snapshot: str
    created_at: datetime
    page_start_snapshot: int | None = None
    page_end_snapshot: int | None = None
    section_title_snapshot: str | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeCitation:
    """A structured citation rendered in UI alongside or within assistant responses."""

    label: str
    document_name: str
    source_path: str
    snippet: str
    score: float
    page_start: int | None = None
    page_end: int | None = None
    section_title: str | None = None
