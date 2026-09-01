from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

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
    DocumentStatus,
    EmbeddingStatus,
    KnowledgeChunk,
    KnowledgeChunkEmbedding,
    KnowledgeDocument,
    KnowledgeIndexJob,
    KnowledgeIndexProfile,
    KnowledgeLibrary,
    KnowledgeRetrievalHit,
    KnowledgeSource,
    SourceScanStatus,
    SourceStatus,
)


@runtime_checkable
class KnowledgeRepository(Protocol):
    """Core persistence protocol for Knowledge Libraries, Sources, Chunks, Embeddings, and Retrieval."""

    # 1. Library operations
    async def get_library(
        self,
        library_id: LibraryId,
    ) -> KnowledgeLibrary | None: ...

    async def list_libraries_for_user(
        self,
        user_id: UserId,
    ) -> tuple[KnowledgeLibrary, ...]: ...

    async def save_library(
        self,
        library: KnowledgeLibrary,
    ) -> None: ...

    async def count_libraries_for_user(
        self,
        user_id: UserId,
    ) -> int: ...

    async def delete_library(
        self,
        library_id: LibraryId,
    ) -> bool: ...

    # 2. Source operations
    async def get_source(
        self,
        source_id: SourceId,
    ) -> KnowledgeSource | None: ...

    async def get_source_by_canonical_path(
        self,
        library_id: LibraryId,
        canonical_path: str,
    ) -> KnowledgeSource | None: ...

    async def list_sources_for_library(
        self,
        library_id: LibraryId,
    ) -> tuple[KnowledgeSource, ...]: ...

    async def get_source_content_counts(
        self,
        library_id: LibraryId,
    ) -> dict[SourceId, tuple[int, int]]: ...

    async def save_source(
        self,
        source: KnowledgeSource,
    ) -> None: ...

    async def update_source_status(
        self,
        source_id: SourceId,
        status: SourceStatus,
        detached_at: datetime | None = None,
    ) -> None: ...

    async def update_source_scan_status(
        self,
        source_id: SourceId,
        scan_status: SourceScanStatus,
        last_scanned_at: datetime | None = None,
    ) -> None: ...

    # 3. Document operations
    async def get_document(
        self,
        document_id: DocumentId,
    ) -> KnowledgeDocument | None: ...

    async def get_document_by_relative_path(
        self,
        source_id: SourceId,
        relative_path: str,
    ) -> KnowledgeDocument | None: ...

    async def list_documents_for_source(
        self,
        source_id: SourceId,
    ) -> tuple[KnowledgeDocument, ...]: ...

    async def save_document(
        self,
        document: KnowledgeDocument,
    ) -> None: ...

    async def update_document_status(
        self,
        document_id: DocumentId,
        status: DocumentStatus,
        last_error_code: str | None = None,
    ) -> None: ...

    # 4. Chunk operations
    async def get_chunk(
        self,
        chunk_id: ChunkId,
    ) -> KnowledgeChunk | None: ...

    async def get_chunks_batch(
        self,
        chunk_ids: Sequence[ChunkId],
    ) -> tuple[KnowledgeChunk, ...]: ...

    async def list_active_chunks_for_document(
        self,
        document_id: DocumentId,
    ) -> tuple[KnowledgeChunk, ...]: ...

    async def save_chunks(
        self,
        chunks: Sequence[KnowledgeChunk],
    ) -> None: ...

    async def supersede_chunks(
        self,
        chunk_ids: Sequence[ChunkId],
        superseded_at: datetime,
    ) -> None: ...

    # 5. Profile operations
    async def get_profile(
        self,
        profile_id: ProfileId,
    ) -> KnowledgeIndexProfile | None: ...

    async def get_active_profile(
        self,
    ) -> KnowledgeIndexProfile | None: ...

    async def save_profile(
        self,
        profile: KnowledgeIndexProfile,
    ) -> None: ...

    # 6. Chunk Embedding operations
    async def get_chunk_embedding(
        self,
        chunk_id: ChunkId,
        profile_id: ProfileId,
    ) -> KnowledgeChunkEmbedding | None: ...

    async def save_chunk_embeddings(
        self,
        embeddings: Sequence[KnowledgeChunkEmbedding],
    ) -> None: ...

    async def update_chunk_embedding_status(
        self,
        chunk_id: ChunkId,
        profile_id: ProfileId,
        status: EmbeddingStatus,
        indexed_at: datetime | None = None,
        last_error_code: str | None = None,
    ) -> None: ...

    async def list_pending_chunk_embeddings(
        self,
        profile_id: ProfileId,
        limit: int = 100,
    ) -> tuple[KnowledgeChunkEmbedding, ...]: ...

    # 7. Index Job operations
    async def get_index_job(
        self,
        job_id: IndexJobId,
    ) -> KnowledgeIndexJob | None: ...

    async def get_active_index_job_for_source(
        self,
        source_id: SourceId,
    ) -> KnowledgeIndexJob | None: ...

    async def save_index_job(
        self,
        job: KnowledgeIndexJob,
    ) -> None: ...

    async def update_index_job_progress(
        self,
        job_id: IndexJobId,
        discovered_files: int,
        processed_files: int,
        skipped_files: int,
        failed_files: int,
        total_chunks: int,
        indexed_chunks: int,
    ) -> None: ...

    async def request_index_job_cancel(
        self,
        job_id: IndexJobId,
    ) -> bool: ...

    async def recover_interrupted_jobs(
        self,
    ) -> int: ...

    # 8. Retrieval Hits & Conversation binding
    async def save_retrieval_hits(
        self,
        hits: Sequence[KnowledgeRetrievalHit],
    ) -> None: ...

    async def list_retrieval_hits_for_run(
        self,
        run_id: RunId,
    ) -> tuple[KnowledgeRetrievalHit, ...]: ...

    async def bind_conversation_library(
        self,
        conversation_id: ConversationId,
        library_id: LibraryId,
    ) -> None: ...

    async def get_conversation_library(
        self,
        conversation_id: ConversationId,
    ) -> LibraryId | None: ...

    async def unbind_conversation_library(
        self,
        conversation_id: ConversationId,
    ) -> None: ...
