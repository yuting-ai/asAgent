from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

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
    ChunkStatus,
    DocumentFileType,
    DocumentStatus,
    EmbeddingStatus,
    IndexJobKind,
    IndexJobStatus,
    IndexProfileStatus,
    KnowledgeChunk,
    KnowledgeChunkEmbedding,
    KnowledgeDocument,
    KnowledgeIndexJob,
    KnowledgeIndexProfile,
    KnowledgeLibrary,
    KnowledgeRetrievalHit,
    KnowledgeSource,
    LibraryStatus,
    SourceScanStatus,
    SourceStatus,
)
from asagent.storage.sqlite.connection import create_sqlite_async_engine
from asagent.storage.sqlite.schema import (
    knowledge_chunk_embeddings,
    knowledge_chunks,
    knowledge_conversations,
    knowledge_documents,
    knowledge_index_jobs,
    knowledge_index_profiles,
    knowledge_libraries,
    knowledge_retrieval_hits,
    knowledge_sources,
    users,
)


class SqliteKnowledgeRepository:
    def __init__(self, database_path: Path) -> None:
        self._engine = create_sqlite_async_engine(database_path)

    async def aclose(self) -> None:
        await self._engine.dispose()

    # -------------------------------------------------------------------------
    # 1. Library operations
    # -------------------------------------------------------------------------

    async def get_library(self, library_id: LibraryId) -> KnowledgeLibrary | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_libraries).where(
                    knowledge_libraries.c.library_id == str(library_id),
                    knowledge_libraries.c.status == "active",
                )
            )
            row = result.mappings().one_or_none()
        if row is None:
            return None
        return _to_library(dict(row))

    async def list_libraries_for_user(
        self, user_id: UserId
    ) -> tuple[KnowledgeLibrary, ...]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_libraries)
                .where(
                    knowledge_libraries.c.user_id == str(user_id),
                    knowledge_libraries.c.status == "active",
                )
                .order_by(
                    knowledge_libraries.c.created_at.asc(),
                    knowledge_libraries.c.library_id.asc(),
                )
            )
            rows = result.mappings().all()
        return tuple(_to_library(dict(row)) for row in rows)

    async def save_library(self, library: KnowledgeLibrary) -> None:
        async with self._engine.begin() as connection:
            # Ensure user exists
            await connection.execute(
                sqlite_insert(users)
                .values(
                    user_id=str(library.user_id),
                    created_at=_to_utc(library.created_at),
                )
                .on_conflict_do_nothing(index_elements=[users.c.user_id])
            )
            await connection.execute(
                sqlite_insert(knowledge_libraries)
                .values(
                    library_id=str(library.library_id),
                    user_id=str(library.user_id),
                    name=library.name,
                    normalized_name=library.normalized_name,
                    status=library.status,
                    created_at=_to_utc(library.created_at),
                    updated_at=_to_utc(library.updated_at),
                )
                .on_conflict_do_update(
                    index_elements=[knowledge_libraries.c.library_id],
                    set_={
                        "user_id": str(library.user_id),
                        "name": library.name,
                        "normalized_name": library.normalized_name,
                        "status": library.status,
                        "created_at": _to_utc(library.created_at),
                        "updated_at": _to_utc(library.updated_at),
                    },
                )
            )

    async def count_libraries_for_user(self, user_id: UserId) -> int:
        async with self._engine.connect() as connection:
            result = await connection.scalar(
                select(func.count())
                .select_from(knowledge_libraries)
                .where(
                    knowledge_libraries.c.user_id == str(user_id),
                    knowledge_libraries.c.status == "active",
                )
            )
        return int(result or 0)

    async def delete_library(self, library_id: LibraryId) -> bool:
        async with self._engine.begin() as connection:
            await connection.execute(
                delete(knowledge_conversations).where(
                    knowledge_conversations.c.library_id == str(library_id)
                )
            )
            await connection.execute(
                update(knowledge_sources)
                .where(knowledge_sources.c.library_id == str(library_id))
                .values(status="detached", scan_status="idle")
            )
            result = await connection.execute(
                update(knowledge_libraries)
                .where(
                    knowledge_libraries.c.library_id == str(library_id),
                    knowledge_libraries.c.status == "active",
                )
                .values(
                    status="deleting",
                    normalized_name=(
                        knowledge_libraries.c.normalized_name
                        + "#deleted#"
                        + knowledge_libraries.c.library_id
                    ),
                    updated_at=datetime.now(UTC),
                )
            )
            return bool(result.rowcount and result.rowcount > 0)

    # -------------------------------------------------------------------------
    # 2. Source operations
    # -------------------------------------------------------------------------

    async def get_source(self, source_id: SourceId) -> KnowledgeSource | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_sources).where(
                    knowledge_sources.c.source_id == str(source_id)
                )
            )
            row = result.mappings().one_or_none()
        if row is None:
            return None
        return _to_source(dict(row))

    async def get_source_by_canonical_path(
        self, library_id: LibraryId, canonical_path: str
    ) -> KnowledgeSource | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_sources).where(
                    knowledge_sources.c.library_id == str(library_id),
                    knowledge_sources.c.canonical_path == canonical_path,
                )
            )
            row = result.mappings().one_or_none()
        if row is None:
            return None
        return _to_source(dict(row))

    async def list_sources_for_library(
        self, library_id: LibraryId
    ) -> tuple[KnowledgeSource, ...]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_sources)
                .where(knowledge_sources.c.library_id == str(library_id))
                .order_by(
                    knowledge_sources.c.created_at.asc(),
                    knowledge_sources.c.source_id.asc(),
                )
            )
            rows = result.mappings().all()
        return tuple(_to_source(dict(row)) for row in rows)

    async def get_source_content_counts(
        self, library_id: LibraryId
    ) -> dict[SourceId, tuple[int, int]]:
        document_counts = (
            select(
                knowledge_documents.c.source_id.label("source_id"),
                func.count().label("document_count"),
            )
            .where(knowledge_documents.c.status == "active")
            .group_by(knowledge_documents.c.source_id)
            .subquery()
        )
        chunk_counts = (
            select(
                knowledge_documents.c.source_id.label("source_id"),
                func.count().label("chunk_count"),
            )
            .select_from(
                knowledge_documents.join(
                    knowledge_chunks,
                    knowledge_chunks.c.document_id == knowledge_documents.c.document_id,
                )
            )
            .where(
                knowledge_documents.c.status == "active",
                knowledge_chunks.c.status == "active",
            )
            .group_by(knowledge_documents.c.source_id)
            .subquery()
        )
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(
                    knowledge_sources.c.source_id,
                    func.coalesce(document_counts.c.document_count, 0),
                    func.coalesce(chunk_counts.c.chunk_count, 0),
                )
                .outerjoin(
                    document_counts,
                    document_counts.c.source_id == knowledge_sources.c.source_id,
                )
                .outerjoin(
                    chunk_counts,
                    chunk_counts.c.source_id == knowledge_sources.c.source_id,
                )
                .where(knowledge_sources.c.library_id == str(library_id))
            )
            rows = result.all()
        return {
            SourceId(str(source_id)): (int(document_count), int(chunk_count))
            for source_id, document_count, chunk_count in rows
        }

    async def save_source(self, source: KnowledgeSource) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                sqlite_insert(knowledge_sources)
                .values(
                    source_id=str(source.source_id),
                    library_id=str(source.library_id),
                    display_path=source.display_path,
                    canonical_path=source.canonical_path,
                    status=source.status,
                    scan_status=source.scan_status,
                    last_scanned_at=_to_optional_utc(source.last_scanned_at),
                    detached_at=_to_optional_utc(source.detached_at),
                    created_at=_to_utc(source.created_at),
                    updated_at=_to_utc(source.updated_at),
                )
                .on_conflict_do_update(
                    index_elements=[knowledge_sources.c.source_id],
                    set_={
                        "library_id": str(source.library_id),
                        "display_path": source.display_path,
                        "canonical_path": source.canonical_path,
                        "status": source.status,
                        "scan_status": source.scan_status,
                        "last_scanned_at": _to_optional_utc(source.last_scanned_at),
                        "detached_at": _to_optional_utc(source.detached_at),
                        "created_at": _to_utc(source.created_at),
                        "updated_at": _to_utc(source.updated_at),
                    },
                )
            )

    async def update_source_status(
        self,
        source_id: SourceId,
        status: SourceStatus,
        detached_at: datetime | None = None,
    ) -> None:
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "status": status,
            "updated_at": now,
        }
        if detached_at is not None:
            values["detached_at"] = _to_utc(detached_at)
        async with self._engine.begin() as connection:
            await connection.execute(
                update(knowledge_sources)
                .where(knowledge_sources.c.source_id == str(source_id))
                .values(**values)
            )

    async def update_source_scan_status(
        self,
        source_id: SourceId,
        scan_status: SourceScanStatus,
        last_scanned_at: datetime | None = None,
    ) -> None:
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "scan_status": scan_status,
            "updated_at": now,
        }
        if last_scanned_at is not None:
            values["last_scanned_at"] = _to_utc(last_scanned_at)
        async with self._engine.begin() as connection:
            await connection.execute(
                update(knowledge_sources)
                .where(knowledge_sources.c.source_id == str(source_id))
                .values(**values)
            )

    # -------------------------------------------------------------------------
    # 3. Document operations
    # -------------------------------------------------------------------------

    async def get_document(self, document_id: DocumentId) -> KnowledgeDocument | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_documents).where(
                    knowledge_documents.c.document_id == str(document_id)
                )
            )
            row = result.mappings().one_or_none()
        if row is None:
            return None
        return _to_document(dict(row))

    async def get_document_by_relative_path(
        self, source_id: SourceId, relative_path: str
    ) -> KnowledgeDocument | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_documents).where(
                    knowledge_documents.c.source_id == str(source_id),
                    knowledge_documents.c.relative_path == relative_path,
                )
            )
            row = result.mappings().one_or_none()
        if row is None:
            return None
        return _to_document(dict(row))

    async def list_documents_for_source(
        self, source_id: SourceId
    ) -> tuple[KnowledgeDocument, ...]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_documents)
                .where(knowledge_documents.c.source_id == str(source_id))
                .order_by(
                    knowledge_documents.c.relative_path.asc(),
                    knowledge_documents.c.document_id.asc(),
                )
            )
            rows = result.mappings().all()
        return tuple(_to_document(dict(row)) for row in rows)

    async def save_document(self, document: KnowledgeDocument) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                sqlite_insert(knowledge_documents)
                .values(
                    document_id=str(document.document_id),
                    source_id=str(document.source_id),
                    relative_path=document.relative_path,
                    file_type=document.file_type,
                    status=document.status,
                    size_bytes=document.size_bytes,
                    mtime_ns=document.mtime_ns,
                    content_hash=document.content_hash,
                    parser_version=document.parser_version,
                    current_chunker_version=document.current_chunker_version,
                    last_indexed_at=_to_optional_utc(document.last_indexed_at),
                    last_error_code=document.last_error_code,
                    created_at=_to_utc(document.created_at),
                    updated_at=_to_utc(document.updated_at),
                )
                .on_conflict_do_update(
                    index_elements=[knowledge_documents.c.document_id],
                    set_={
                        "source_id": str(document.source_id),
                        "relative_path": document.relative_path,
                        "file_type": document.file_type,
                        "status": document.status,
                        "size_bytes": document.size_bytes,
                        "mtime_ns": document.mtime_ns,
                        "content_hash": document.content_hash,
                        "parser_version": document.parser_version,
                        "current_chunker_version": (document.current_chunker_version),
                        "last_indexed_at": _to_optional_utc(document.last_indexed_at),
                        "last_error_code": document.last_error_code,
                        "created_at": _to_utc(document.created_at),
                        "updated_at": _to_utc(document.updated_at),
                    },
                )
            )

    async def update_document_status(
        self,
        document_id: DocumentId,
        status: DocumentStatus,
        last_error_code: str | None = None,
    ) -> None:
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "status": status,
            "updated_at": now,
        }
        if last_error_code is not None:
            values["last_error_code"] = last_error_code
        async with self._engine.begin() as connection:
            await connection.execute(
                update(knowledge_documents)
                .where(knowledge_documents.c.document_id == str(document_id))
                .values(**values)
            )

    # -------------------------------------------------------------------------
    # 4. Chunk operations
    # -------------------------------------------------------------------------

    async def get_chunk(self, chunk_id: ChunkId) -> KnowledgeChunk | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_chunks).where(
                    knowledge_chunks.c.chunk_id == str(chunk_id)
                )
            )
            row = result.mappings().one_or_none()
        if row is None:
            return None
        return _to_chunk(dict(row))

    async def get_chunks_batch(
        self, chunk_ids: Sequence[ChunkId]
    ) -> tuple[KnowledgeChunk, ...]:
        if not chunk_ids:
            return ()
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_chunks).where(
                    knowledge_chunks.c.chunk_id.in_([str(c) for c in chunk_ids])
                )
            )
            rows = result.mappings().all()
        chunks_map = {r["chunk_id"]: _to_chunk(dict(r)) for r in rows}
        return tuple(
            chunks_map[str(cid)] for cid in chunk_ids if str(cid) in chunks_map
        )

    async def list_active_chunks_for_document(
        self, document_id: DocumentId
    ) -> tuple[KnowledgeChunk, ...]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_chunks)
                .where(
                    knowledge_chunks.c.document_id == str(document_id),
                    knowledge_chunks.c.status == "active",
                )
                .order_by(knowledge_chunks.c.chunk_index.asc())
            )
            rows = result.mappings().all()
        return tuple(_to_chunk(dict(row)) for row in rows)

    async def save_chunks(self, chunks: Sequence[KnowledgeChunk]) -> None:
        if not chunks:
            return
        async with self._engine.begin() as connection:
            for chk in chunks:
                await connection.execute(
                    sqlite_insert(knowledge_chunks)
                    .values(
                        chunk_id=str(chk.chunk_id),
                        document_id=str(chk.document_id),
                        document_content_hash=chk.document_content_hash,
                        chunk_index=chk.chunk_index,
                        text=chk.text,
                        token_count=chk.token_count,
                        page_start=chk.page_start,
                        page_end=chk.page_end,
                        section_title=chk.section_title,
                        content_hash=chk.content_hash,
                        chunker_version=chk.chunker_version,
                        status=chk.status,
                        created_at=_to_utc(chk.created_at),
                        superseded_at=_to_optional_utc(chk.superseded_at),
                    )
                    .on_conflict_do_update(
                        index_elements=[knowledge_chunks.c.chunk_id],
                        set_={
                            "document_id": str(chk.document_id),
                            "document_content_hash": chk.document_content_hash,
                            "chunk_index": chk.chunk_index,
                            "text": chk.text,
                            "token_count": chk.token_count,
                            "page_start": chk.page_start,
                            "page_end": chk.page_end,
                            "section_title": chk.section_title,
                            "content_hash": chk.content_hash,
                            "chunker_version": chk.chunker_version,
                            "status": chk.status,
                            "created_at": _to_utc(chk.created_at),
                            "superseded_at": _to_optional_utc(chk.superseded_at),
                        },
                    )
                )

    async def supersede_chunks(
        self, chunk_ids: Sequence[ChunkId], superseded_at: datetime
    ) -> None:
        if not chunk_ids:
            return
        async with self._engine.begin() as connection:
            await connection.execute(
                update(knowledge_chunks)
                .where(knowledge_chunks.c.chunk_id.in_([str(c) for c in chunk_ids]))
                .values(
                    status="superseded",
                    superseded_at=_to_utc(superseded_at),
                )
            )

    # -------------------------------------------------------------------------
    # 5. Index Profile operations
    # -------------------------------------------------------------------------

    async def get_profile(self, profile_id: ProfileId) -> KnowledgeIndexProfile | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_index_profiles).where(
                    knowledge_index_profiles.c.profile_id == str(profile_id)
                )
            )
            row = result.mappings().one_or_none()
        if row is None:
            return None
        return _to_profile(dict(row))

    async def get_active_profile(self) -> KnowledgeIndexProfile | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_index_profiles)
                .where(knowledge_index_profiles.c.status == "active")
                .order_by(knowledge_index_profiles.c.created_at.desc())
            )
            row = result.mappings().first()
        if row is None:
            return None
        return _to_profile(dict(row))

    async def save_profile(self, profile: KnowledgeIndexProfile) -> None:
        async with self._engine.begin() as connection:
            if profile.status == "active":
                await connection.execute(
                    update(knowledge_index_profiles)
                    .where(
                        knowledge_index_profiles.c.status == "active",
                        knowledge_index_profiles.c.profile_id
                        != str(profile.profile_id),
                    )
                    .values(status="retired")
                )
            await connection.execute(
                sqlite_insert(knowledge_index_profiles)
                .values(
                    profile_id=str(profile.profile_id),
                    embedding_model=profile.embedding_model,
                    embedding_revision=profile.embedding_revision,
                    embedding_dimension=profile.embedding_dimension,
                    embedding_normalized=1 if profile.embedding_normalized else 0,
                    chunker_version=profile.chunker_version,
                    qdrant_collection=profile.qdrant_collection,
                    status=profile.status,
                    created_at=_to_utc(profile.created_at),
                    activated_at=_to_optional_utc(profile.activated_at),
                )
                .on_conflict_do_update(
                    index_elements=[knowledge_index_profiles.c.profile_id],
                    set_={
                        "embedding_model": profile.embedding_model,
                        "embedding_revision": profile.embedding_revision,
                        "embedding_dimension": profile.embedding_dimension,
                        "embedding_normalized": (
                            1 if profile.embedding_normalized else 0
                        ),
                        "chunker_version": profile.chunker_version,
                        "qdrant_collection": profile.qdrant_collection,
                        "status": profile.status,
                        "created_at": _to_utc(profile.created_at),
                        "activated_at": _to_optional_utc(profile.activated_at),
                    },
                )
            )

    # -------------------------------------------------------------------------
    # 6. Chunk Embedding operations
    # -------------------------------------------------------------------------

    async def get_chunk_embedding(
        self, chunk_id: ChunkId, profile_id: ProfileId
    ) -> KnowledgeChunkEmbedding | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_chunk_embeddings).where(
                    knowledge_chunk_embeddings.c.chunk_id == str(chunk_id),
                    knowledge_chunk_embeddings.c.profile_id == str(profile_id),
                )
            )
            row = result.mappings().one_or_none()
        if row is None:
            return None
        return _to_chunk_embedding(dict(row))

    async def save_chunk_embeddings(
        self, embeddings: Sequence[KnowledgeChunkEmbedding]
    ) -> None:
        if not embeddings:
            return
        async with self._engine.begin() as connection:
            for emb in embeddings:
                await connection.execute(
                    sqlite_insert(knowledge_chunk_embeddings)
                    .values(
                        chunk_id=str(emb.chunk_id),
                        profile_id=str(emb.profile_id),
                        point_id=emb.point_id,
                        status=emb.status,
                        retry_count=emb.retry_count,
                        last_error_code=emb.last_error_code,
                        indexed_at=_to_optional_utc(emb.indexed_at),
                        created_at=_to_utc(emb.created_at),
                        updated_at=_to_utc(emb.updated_at),
                    )
                    .on_conflict_do_update(
                        index_elements=[
                            knowledge_chunk_embeddings.c.chunk_id,
                            knowledge_chunk_embeddings.c.profile_id,
                        ],
                        set_={
                            "point_id": emb.point_id,
                            "status": emb.status,
                            "retry_count": emb.retry_count,
                            "last_error_code": emb.last_error_code,
                            "indexed_at": _to_optional_utc(emb.indexed_at),
                            "created_at": _to_utc(emb.created_at),
                            "updated_at": _to_utc(emb.updated_at),
                        },
                    )
                )

    async def update_chunk_embedding_status(
        self,
        chunk_id: ChunkId,
        profile_id: ProfileId,
        status: EmbeddingStatus,
        indexed_at: datetime | None = None,
        last_error_code: str | None = None,
    ) -> None:
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "status": status,
            "updated_at": now,
        }
        if indexed_at is not None:
            values["indexed_at"] = _to_utc(indexed_at)
        if last_error_code is not None:
            values["last_error_code"] = last_error_code
        async with self._engine.begin() as connection:
            await connection.execute(
                update(knowledge_chunk_embeddings)
                .where(
                    knowledge_chunk_embeddings.c.chunk_id == str(chunk_id),
                    knowledge_chunk_embeddings.c.profile_id == str(profile_id),
                )
                .values(**values)
            )

    async def list_pending_chunk_embeddings(
        self, profile_id: ProfileId, limit: int = 100
    ) -> tuple[KnowledgeChunkEmbedding, ...]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_chunk_embeddings)
                .where(
                    knowledge_chunk_embeddings.c.profile_id == str(profile_id),
                    knowledge_chunk_embeddings.c.status.in_(["pending", "error"]),
                )
                .order_by(
                    knowledge_chunk_embeddings.c.retry_count.asc(),
                    knowledge_chunk_embeddings.c.created_at.asc(),
                )
                .limit(limit)
            )
            rows = result.mappings().all()
        return tuple(_to_chunk_embedding(dict(row)) for row in rows)

    # -------------------------------------------------------------------------
    # 7. Index Job operations
    # -------------------------------------------------------------------------

    async def get_index_job(self, job_id: IndexJobId) -> KnowledgeIndexJob | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_index_jobs).where(
                    knowledge_index_jobs.c.job_id == str(job_id)
                )
            )
            row = result.mappings().one_or_none()
        if row is None:
            return None
        return _to_index_job(dict(row))

    async def get_active_index_job_for_source(
        self, source_id: SourceId
    ) -> KnowledgeIndexJob | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_index_jobs)
                .where(
                    knowledge_index_jobs.c.source_id == str(source_id),
                    knowledge_index_jobs.c.status.in_(["queued", "running"]),
                )
                .order_by(knowledge_index_jobs.c.created_at.desc())
            )
            row = result.mappings().first()
        if row is None:
            return None
        return _to_index_job(dict(row))

    async def save_index_job(self, job: KnowledgeIndexJob) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                sqlite_insert(knowledge_index_jobs)
                .values(
                    job_id=str(job.job_id),
                    library_id=str(job.library_id),
                    source_id=str(job.source_id) if job.source_id else None,
                    kind=job.kind,
                    status=job.status,
                    discovered_files=job.discovered_files,
                    processed_files=job.processed_files,
                    skipped_files=job.skipped_files,
                    failed_files=job.failed_files,
                    total_chunks=job.total_chunks,
                    indexed_chunks=job.indexed_chunks,
                    cancel_requested=1 if job.cancel_requested else 0,
                    last_error_code=job.last_error_code,
                    created_at=_to_utc(job.created_at),
                    started_at=_to_optional_utc(job.started_at),
                    updated_at=_to_utc(job.updated_at),
                    completed_at=_to_optional_utc(job.completed_at),
                )
                .on_conflict_do_update(
                    index_elements=[knowledge_index_jobs.c.job_id],
                    set_={
                        "library_id": str(job.library_id),
                        "source_id": (str(job.source_id) if job.source_id else None),
                        "kind": job.kind,
                        "status": job.status,
                        "discovered_files": job.discovered_files,
                        "processed_files": job.processed_files,
                        "skipped_files": job.skipped_files,
                        "failed_files": job.failed_files,
                        "total_chunks": job.total_chunks,
                        "indexed_chunks": job.indexed_chunks,
                        "cancel_requested": 1 if job.cancel_requested else 0,
                        "last_error_code": job.last_error_code,
                        "created_at": _to_utc(job.created_at),
                        "started_at": _to_optional_utc(job.started_at),
                        "updated_at": _to_utc(job.updated_at),
                        "completed_at": _to_optional_utc(job.completed_at),
                    },
                )
            )

    async def update_index_job_progress(
        self,
        job_id: IndexJobId,
        discovered_files: int,
        processed_files: int,
        skipped_files: int,
        failed_files: int,
        total_chunks: int,
        indexed_chunks: int,
    ) -> None:
        now = datetime.now(UTC)
        async with self._engine.begin() as connection:
            await connection.execute(
                update(knowledge_index_jobs)
                .where(knowledge_index_jobs.c.job_id == str(job_id))
                .values(
                    discovered_files=discovered_files,
                    processed_files=processed_files,
                    skipped_files=skipped_files,
                    failed_files=failed_files,
                    total_chunks=total_chunks,
                    indexed_chunks=indexed_chunks,
                    updated_at=now,
                )
            )

    async def request_index_job_cancel(self, job_id: IndexJobId) -> bool:
        now = datetime.now(UTC)
        async with self._engine.begin() as connection:
            result = await connection.execute(
                update(knowledge_index_jobs)
                .where(
                    knowledge_index_jobs.c.job_id == str(job_id),
                    knowledge_index_jobs.c.status.in_(["queued", "running"]),
                )
                .values(cancel_requested=1, updated_at=now)
            )
            return bool(result.rowcount and result.rowcount > 0)

    async def recover_interrupted_jobs(self) -> int:
        now = datetime.now(UTC)
        async with self._engine.begin() as connection:
            interrupted_source_ids = select(knowledge_index_jobs.c.source_id).where(
                knowledge_index_jobs.c.status.in_(["queued", "running"]),
                knowledge_index_jobs.c.source_id.is_not(None),
            )
            await connection.execute(
                update(knowledge_sources)
                .where(knowledge_sources.c.source_id.in_(interrupted_source_ids))
                .values(scan_status="error", updated_at=now)
            )
            result = await connection.execute(
                update(knowledge_index_jobs)
                .where(knowledge_index_jobs.c.status.in_(["queued", "running"]))
                .values(
                    status="interrupted",
                    last_error_code="JOB_INTERRUPTED_ON_RESTART",
                    updated_at=now,
                    completed_at=now,
                )
            )
            return int(result.rowcount or 0)

    # -------------------------------------------------------------------------
    # 8. Retrieval Hits & Conversation binding
    # -------------------------------------------------------------------------

    async def save_retrieval_hits(self, hits: Sequence[KnowledgeRetrievalHit]) -> None:
        if not hits:
            return
        async with self._engine.begin() as connection:
            for hit in hits:
                await connection.execute(
                    sqlite_insert(knowledge_retrieval_hits)
                    .values(
                        run_id=str(hit.run_id),
                        rank=hit.rank,
                        chunk_id=str(hit.chunk_id),
                        profile_id=str(hit.profile_id),
                        score=hit.score,
                        citation_label=hit.citation_label,
                        document_name_snapshot=hit.document_name_snapshot,
                        source_path_snapshot=hit.source_path_snapshot,
                        page_start_snapshot=hit.page_start_snapshot,
                        page_end_snapshot=hit.page_end_snapshot,
                        section_title_snapshot=hit.section_title_snapshot,
                        content_hash_snapshot=hit.content_hash_snapshot,
                        snippet_snapshot=hit.snippet_snapshot,
                        created_at=_to_utc(hit.created_at),
                    )
                    .on_conflict_do_update(
                        index_elements=[
                            knowledge_retrieval_hits.c.run_id,
                            knowledge_retrieval_hits.c.rank,
                        ],
                        set_={
                            "chunk_id": str(hit.chunk_id),
                            "profile_id": str(hit.profile_id),
                            "score": hit.score,
                            "citation_label": hit.citation_label,
                            "document_name_snapshot": (hit.document_name_snapshot),
                            "source_path_snapshot": hit.source_path_snapshot,
                            "page_start_snapshot": hit.page_start_snapshot,
                            "page_end_snapshot": hit.page_end_snapshot,
                            "section_title_snapshot": (hit.section_title_snapshot),
                            "content_hash_snapshot": hit.content_hash_snapshot,
                            "snippet_snapshot": hit.snippet_snapshot,
                            "created_at": _to_utc(hit.created_at),
                        },
                    )
                )

    async def list_retrieval_hits_for_run(
        self, run_id: RunId
    ) -> tuple[KnowledgeRetrievalHit, ...]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(knowledge_retrieval_hits)
                .where(knowledge_retrieval_hits.c.run_id == str(run_id))
                .order_by(knowledge_retrieval_hits.c.rank.asc())
            )
            rows = result.mappings().all()
        return tuple(_to_retrieval_hit(dict(row)) for row in rows)

    async def bind_conversation_library(
        self, conversation_id: ConversationId, library_id: LibraryId
    ) -> None:
        now = datetime.now(UTC)
        async with self._engine.begin() as connection:
            await connection.execute(
                sqlite_insert(knowledge_conversations)
                .values(
                    conversation_id=str(conversation_id),
                    library_id=str(library_id),
                    created_at=now,
                )
                .on_conflict_do_update(
                    index_elements=[knowledge_conversations.c.conversation_id],
                    set_={"library_id": str(library_id)},
                )
            )

    async def get_conversation_library(
        self, conversation_id: ConversationId
    ) -> LibraryId | None:
        async with self._engine.connect() as connection:
            result = await connection.scalar(
                select(knowledge_conversations.c.library_id).where(
                    knowledge_conversations.c.conversation_id == str(conversation_id)
                )
            )
        if result is None:
            return None
        return LibraryId(str(result))

    async def unbind_conversation_library(
        self, conversation_id: ConversationId
    ) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                delete(knowledge_conversations).where(
                    knowledge_conversations.c.conversation_id == str(conversation_id)
                )
            )


# =============================================================================
# Helper Row Parsing Functions
# =============================================================================


def _to_library(row: Mapping[str, object]) -> KnowledgeLibrary:
    return KnowledgeLibrary(
        library_id=LibraryId(_required_str(row, "library_id")),
        user_id=UserId(_required_str(row, "user_id")),
        name=_required_str(row, "name"),
        normalized_name=_required_str(row, "normalized_name"),
        status=cast(LibraryStatus, _required_str(row, "status")),
        created_at=_required_datetime(row, "created_at"),
        updated_at=_required_datetime(row, "updated_at"),
    )


def _to_source(row: Mapping[str, object]) -> KnowledgeSource:
    return KnowledgeSource(
        source_id=SourceId(_required_str(row, "source_id")),
        library_id=LibraryId(_required_str(row, "library_id")),
        display_path=_required_str(row, "display_path"),
        canonical_path=_required_str(row, "canonical_path"),
        status=cast(SourceStatus, _required_str(row, "status")),
        scan_status=cast(SourceScanStatus, _required_str(row, "scan_status")),
        last_scanned_at=_optional_datetime(row, "last_scanned_at"),
        detached_at=_optional_datetime(row, "detached_at"),
        created_at=_required_datetime(row, "created_at"),
        updated_at=_required_datetime(row, "updated_at"),
    )


def _to_document(row: Mapping[str, object]) -> KnowledgeDocument:
    return KnowledgeDocument(
        document_id=DocumentId(_required_str(row, "document_id")),
        source_id=SourceId(_required_str(row, "source_id")),
        relative_path=_required_str(row, "relative_path"),
        file_type=cast(DocumentFileType, _required_str(row, "file_type")),
        status=cast(DocumentStatus, _required_str(row, "status")),
        size_bytes=_required_int(row, "size_bytes"),
        mtime_ns=_required_int(row, "mtime_ns"),
        content_hash=_required_str(row, "content_hash"),
        parser_version=_required_str(row, "parser_version"),
        current_chunker_version=_required_str(row, "current_chunker_version"),
        last_indexed_at=_optional_datetime(row, "last_indexed_at"),
        last_error_code=_optional_str(row, "last_error_code"),
        created_at=_required_datetime(row, "created_at"),
        updated_at=_required_datetime(row, "updated_at"),
    )


def _to_chunk(row: Mapping[str, object]) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=ChunkId(_required_str(row, "chunk_id")),
        document_id=DocumentId(_required_str(row, "document_id")),
        document_content_hash=_required_str(row, "document_content_hash"),
        chunk_index=_required_int(row, "chunk_index"),
        text=_required_str(row, "text"),
        token_count=_required_int(row, "token_count"),
        content_hash=_required_str(row, "content_hash"),
        chunker_version=_required_str(row, "chunker_version"),
        status=cast(ChunkStatus, _required_str(row, "status")),
        created_at=_required_datetime(row, "created_at"),
        page_start=_optional_int(row, "page_start"),
        page_end=_optional_int(row, "page_end"),
        section_title=_optional_str(row, "section_title"),
        superseded_at=_optional_datetime(row, "superseded_at"),
    )


def _to_profile(row: Mapping[str, object]) -> KnowledgeIndexProfile:
    return KnowledgeIndexProfile(
        profile_id=ProfileId(_required_str(row, "profile_id")),
        embedding_model=_required_str(row, "embedding_model"),
        embedding_revision=_required_str(row, "embedding_revision"),
        embedding_dimension=_required_int(row, "embedding_dimension"),
        embedding_normalized=bool(row["embedding_normalized"]),
        chunker_version=_required_str(row, "chunker_version"),
        qdrant_collection=_required_str(row, "qdrant_collection"),
        status=cast(IndexProfileStatus, _required_str(row, "status")),
        created_at=_required_datetime(row, "created_at"),
        activated_at=_optional_datetime(row, "activated_at"),
    )


def _to_chunk_embedding(row: Mapping[str, object]) -> KnowledgeChunkEmbedding:
    return KnowledgeChunkEmbedding(
        chunk_id=ChunkId(_required_str(row, "chunk_id")),
        profile_id=ProfileId(_required_str(row, "profile_id")),
        point_id=_required_str(row, "point_id"),
        status=cast(EmbeddingStatus, _required_str(row, "status")),
        retry_count=_required_int(row, "retry_count"),
        last_error_code=_optional_str(row, "last_error_code"),
        indexed_at=_optional_datetime(row, "indexed_at"),
        created_at=_required_datetime(row, "created_at"),
        updated_at=_required_datetime(row, "updated_at"),
    )


def _to_index_job(row: Mapping[str, object]) -> KnowledgeIndexJob:
    return KnowledgeIndexJob(
        job_id=IndexJobId(_required_str(row, "job_id")),
        library_id=LibraryId(_required_str(row, "library_id")),
        source_id=(
            SourceId(_required_str(row, "source_id"))
            if row.get("source_id") is not None
            else None
        ),
        kind=cast(IndexJobKind, _required_str(row, "kind")),
        status=cast(IndexJobStatus, _required_str(row, "status")),
        discovered_files=_required_int(row, "discovered_files"),
        processed_files=_required_int(row, "processed_files"),
        skipped_files=_required_int(row, "skipped_files"),
        failed_files=_required_int(row, "failed_files"),
        total_chunks=_required_int(row, "total_chunks"),
        indexed_chunks=_required_int(row, "indexed_chunks"),
        cancel_requested=bool(row["cancel_requested"]),
        last_error_code=_optional_str(row, "last_error_code"),
        created_at=_required_datetime(row, "created_at"),
        started_at=_optional_datetime(row, "started_at"),
        updated_at=_required_datetime(row, "updated_at"),
        completed_at=_optional_datetime(row, "completed_at"),
    )


def _to_retrieval_hit(row: Mapping[str, object]) -> KnowledgeRetrievalHit:
    return KnowledgeRetrievalHit(
        run_id=RunId(_required_str(row, "run_id")),
        rank=_required_int(row, "rank"),
        chunk_id=ChunkId(_required_str(row, "chunk_id")),
        profile_id=ProfileId(_required_str(row, "profile_id")),
        score=_required_float(row, "score"),
        citation_label=_required_str(row, "citation_label"),
        document_name_snapshot=_required_str(row, "document_name_snapshot"),
        source_path_snapshot=_required_str(row, "source_path_snapshot"),
        content_hash_snapshot=_required_str(row, "content_hash_snapshot"),
        snippet_snapshot=_required_str(row, "snippet_snapshot"),
        created_at=_required_datetime(row, "created_at"),
        page_start_snapshot=_optional_int(row, "page_start_snapshot"),
        page_end_snapshot=_optional_int(row, "page_end_snapshot"),
        section_title_snapshot=_optional_str(row, "section_title_snapshot"),
    )


def _required_str(row: Mapping[str, object], field: str) -> str:
    value = row[field]
    if not isinstance(value, str):
        raise RuntimeError(f"persisted {field} must be a string")
    return value


def _optional_str(row: Mapping[str, object], field: str) -> str | None:
    value = row[field]
    if value is None:
        return None
    if not isinstance(value, str):
        raise RuntimeError(f"persisted {field} must be a string or null")
    return value


def _required_int(row: Mapping[str, object], field: str) -> int:
    value = row[field]
    if not isinstance(value, int):
        raise RuntimeError(f"persisted {field} must be an int")
    return value


def _optional_int(row: Mapping[str, object], field: str) -> int | None:
    value = row[field]
    if value is None:
        return None
    if not isinstance(value, int):
        raise RuntimeError(f"persisted {field} must be an int or null")
    return value


def _required_float(row: Mapping[str, object], field: str) -> float:
    value = row[field]
    if not isinstance(value, (float, int)):
        raise RuntimeError(f"persisted {field} must be a float")
    return float(value)


def _required_datetime(row: Mapping[str, object], field: str) -> datetime:
    value = row[field]
    if not isinstance(value, datetime):
        raise RuntimeError(f"persisted {field} must be a datetime")
    return _to_utc(value)


def _optional_datetime(row: Mapping[str, object], field: str) -> datetime | None:
    value = row[field]
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise RuntimeError(f"persisted {field} must be a datetime or null")
    return _to_utc(value)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _to_optional_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return _to_utc(value)
