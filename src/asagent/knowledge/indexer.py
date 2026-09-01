import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from asagent.core.ids import (
    ChunkId,
    DocumentId,
    IndexJobId,
    LibraryId,
    SourceId,
)
from asagent.knowledge.chunker import (
    CHUNKER_VERSION,
    chunk_document,
)
from asagent.knowledge.embedder import (
    LocalMiniLMEmbedder,
    create_pending_embeddings_for_chunks,
    ensure_default_profile,
)
from asagent.knowledge.models import (
    IndexJobKind,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIndexJob,
    KnowledgeIndexProfile,
    KnowledgeSource,
)
from asagent.knowledge.parser import (
    PARSER_VERSION,
    parse_file,
)
from asagent.knowledge.repository import KnowledgeRepository
from asagent.knowledge.scanner import scan_directory
from asagent.storage.qdrant import (
    KnowledgeVectorStore,
    VectorPoint,
)


@dataclass(frozen=True, slots=True)
class IndexSourceStats:
    """Statistics summarizing the result of a source incremental indexing run."""

    total_scanned: int
    added_docs: int
    modified_docs: int
    unchanged_docs: int
    deleted_docs: int
    total_chunks: int
    new_chunks: int
    indexed_chunks: int = 0


class KnowledgeIndexer:
    """Coordinates directory scanning, incremental diffing, parsing, chunking, embedding, and vector persistence."""

    def __init__(
        self,
        *,
        repository: KnowledgeRepository,
        embedder: LocalMiniLMEmbedder | None = None,
        vector_store: KnowledgeVectorStore | None = None,
        now: Callable[[], datetime] | None = None,
        new_document_id: Callable[[], DocumentId] | None = None,
        new_chunk_id: Callable[[], ChunkId] | None = None,
        new_job_id: Callable[[], IndexJobId] | None = None,
    ) -> None:
        self._repository = repository
        self._embedder = embedder
        self._vector_store = vector_store
        self._now = now or (lambda: datetime.now(UTC))
        self._new_document_id = new_document_id or (
            lambda: DocumentId(f"doc_{uuid.uuid4().hex[:12]}")
        )
        self._new_chunk_id = new_chunk_id or (
            lambda: ChunkId(f"chk_{uuid.uuid4().hex[:12]}")
        )
        self._new_job_id = new_job_id or (
            lambda: IndexJobId(f"job_{uuid.uuid4().hex[:12]}")
        )

    async def _embed_and_index_chunks(
        self,
        source: KnowledgeSource,
        chunks: tuple[KnowledgeChunk, ...],
        profile: KnowledgeIndexProfile,
    ) -> int:
        """Compute embeddings and dual-write to Qdrant and SQLite."""
        if not chunks or self._embedder is None or self._vector_store is None:
            return 0

        await asyncio.to_thread(
            self._vector_store.ensure_collection,
            profile.qdrant_collection,
            dimension=profile.embedding_dimension,
        )

        now = self._now()
        pending = create_pending_embeddings_for_chunks(
            chunks, profile.profile_id, now=now
        )
        await self._repository.save_chunk_embeddings(pending)

        try:
            vectors = await asyncio.to_thread(
                self._embedder.embed_texts, [c.text for c in chunks]
            )
            points = [
                VectorPoint(
                    point_id=rec.point_id,
                    vector=vec,
                    payload={
                        "chunk_id": str(chk.chunk_id),
                        "document_id": str(chk.document_id),
                        "source_id": str(source.source_id),
                        "library_id": str(source.library_id),
                        "profile_id": str(profile.profile_id),
                        "status": "active",
                        "content_hash": chk.content_hash,
                    },
                )
                for chk, rec, vec in zip(chunks, pending, vectors, strict=True)
            ]
            await asyncio.to_thread(
                self._vector_store.upsert_points,
                profile.qdrant_collection,
                points,
            )
        except Exception as exc:
            for rec in pending:
                await self._repository.update_chunk_embedding_status(
                    rec.chunk_id,
                    profile.profile_id,
                    "error",
                    last_error_code=type(exc).__name__,
                )
            raise

        for rec in pending:
            await self._repository.update_chunk_embedding_status(
                rec.chunk_id,
                profile.profile_id,
                "indexed",
                indexed_at=now,
            )

        return len(points)

    async def _chunks_needing_embedding(
        self,
        chunks: tuple[KnowledgeChunk, ...],
        profile: KnowledgeIndexProfile,
    ) -> tuple[KnowledgeChunk, ...]:
        pending: list[KnowledgeChunk] = []
        for chunk in chunks:
            embedding = await self._repository.get_chunk_embedding(
                chunk.chunk_id, profile.profile_id
            )
            if embedding is None or embedding.status != "indexed":
                pending.append(chunk)
        return tuple(pending)

    async def set_source_active(self, source_id: SourceId, *, active: bool) -> None:
        """Keep retained Qdrant payload state aligned with a soft-detached Source."""
        if self._vector_store is None:
            return
        profile = await self._repository.get_active_profile()
        if profile is None:
            return
        await asyncio.to_thread(
            self._vector_store.set_source_status,
            profile.qdrant_collection,
            source_id,
            active=active,
        )

    async def set_library_active(self, library_id: LibraryId, *, active: bool) -> None:
        """Keep retained Qdrant payload state aligned with Library lifecycle state."""
        if self._vector_store is None:
            return
        profile = await self._repository.get_active_profile()
        if profile is None:
            return
        await asyncio.to_thread(
            self._vector_store.set_library_status,
            profile.qdrant_collection,
            library_id,
            active=active,
        )

    async def index_source(
        self,
        source_id: SourceId,
        *,
        kind: IndexJobKind = "initial",
        job_id: IndexJobId | None = None,
    ) -> IndexSourceStats:
        """Scan a source folder and perform incremental diffing, chunking, and vector embedding."""
        source = await self._repository.get_source(source_id)
        if source is None or source.status != "active":
            raise ValueError(f"Active knowledge source '{source_id}' not found")

        now = self._now()
        effective_job_id = job_id or self._new_job_id()

        existing_job = await self._repository.get_index_job(effective_job_id)
        if existing_job is None:
            job = KnowledgeIndexJob(
                job_id=effective_job_id,
                library_id=source.library_id,
                kind=kind,
                status="running",
                discovered_files=0,
                processed_files=0,
                skipped_files=0,
                failed_files=0,
                total_chunks=0,
                indexed_chunks=0,
                cancel_requested=False,
                created_at=now,
                updated_at=now,
                source_id=source_id,
                last_error_code=None,
                started_at=now,
                completed_at=None,
            )
            await self._repository.save_index_job(job)
        else:
            job = KnowledgeIndexJob(
                job_id=existing_job.job_id,
                library_id=existing_job.library_id,
                kind=existing_job.kind,
                status="running",
                discovered_files=existing_job.discovered_files,
                processed_files=existing_job.processed_files,
                skipped_files=existing_job.skipped_files,
                failed_files=existing_job.failed_files,
                total_chunks=existing_job.total_chunks,
                indexed_chunks=existing_job.indexed_chunks,
                cancel_requested=existing_job.cancel_requested,
                created_at=existing_job.created_at,
                updated_at=now,
                source_id=existing_job.source_id,
                last_error_code=existing_job.last_error_code,
                started_at=existing_job.started_at or now,
                completed_at=None,
            )
            await self._repository.save_index_job(job)

        await self._repository.update_source_scan_status(source_id, "scanning")

        try:
            profile = await ensure_default_profile(self._repository, now=self._now())
            root_path = Path(source.canonical_path)
            scanned_files = await asyncio.to_thread(scan_directory, root_path)

            discovered_count = len(scanned_files)
            await self._repository.update_index_job_progress(
                effective_job_id,
                discovered_files=discovered_count,
                processed_files=0,
                skipped_files=0,
                failed_files=0,
                total_chunks=0,
                indexed_chunks=0,
            )

            existing_docs = await self._repository.list_documents_for_source(source_id)
            existing_by_rel_path = {
                d.relative_path: d for d in existing_docs if d.status == "active"
            }

            added_docs = 0
            modified_docs = 0
            unchanged_docs = 0
            deleted_docs = 0
            total_chunks = 0
            new_chunks_count = 0
            indexed_chunks_count = 0
            processed_docs = 0
            failed_docs = 0
            last_file_error: str | None = None

            for scanned in scanned_files:
                # Check for cancellation request
                cur_job = await self._repository.get_index_job(effective_job_id)
                if cur_job is not None and cur_job.cancel_requested:
                    cancelled_job = KnowledgeIndexJob(
                        job_id=cur_job.job_id,
                        library_id=cur_job.library_id,
                        kind=cur_job.kind,
                        status="cancelled",
                        discovered_files=discovered_count,
                        processed_files=processed_docs,
                        skipped_files=unchanged_docs,
                        failed_files=failed_docs,
                        total_chunks=total_chunks,
                        indexed_chunks=indexed_chunks_count,
                        cancel_requested=True,
                        created_at=cur_job.created_at,
                        updated_at=self._now(),
                        source_id=cur_job.source_id,
                        last_error_code=None,
                        started_at=cur_job.started_at,
                        completed_at=self._now(),
                    )
                    await self._repository.save_index_job(cancelled_job)
                    await self._repository.update_source_scan_status(source_id, "ready")
                    return IndexSourceStats(
                        total_scanned=discovered_count,
                        added_docs=added_docs,
                        modified_docs=modified_docs,
                        unchanged_docs=unchanged_docs,
                        deleted_docs=deleted_docs,
                        total_chunks=total_chunks,
                        new_chunks=new_chunks_count,
                        indexed_chunks=indexed_chunks_count,
                    )

                try:
                    if scanned.relative_path in existing_by_rel_path:
                        existing = existing_by_rel_path[scanned.relative_path]
                        if existing.content_hash == scanned.content_hash:
                            # 100% unchanged, reuse existing document & chunks
                            unchanged_docs += 1
                            active_chunks = (
                                await self._repository.list_active_chunks_for_document(
                                    existing.document_id
                                )
                            )
                            total_chunks += len(active_chunks)
                            retry_chunks = await self._chunks_needing_embedding(
                                active_chunks, profile
                            )
                            indexed_chunks_count += await self._embed_and_index_chunks(
                                source, retry_chunks, profile
                            )
                        else:
                            # Build the replacement before changing the active version.
                            modified_docs += 1
                            old_chunks = (
                                await self._repository.list_active_chunks_for_document(
                                    existing.document_id
                                )
                            )
                            updated_doc = KnowledgeDocument(
                                document_id=existing.document_id,
                                source_id=source_id,
                                relative_path=scanned.relative_path,
                                file_type=scanned.file_type,
                                status="active",
                                size_bytes=scanned.size_bytes,
                                mtime_ns=scanned.mtime_ns,
                                content_hash=scanned.content_hash,
                                parser_version=PARSER_VERSION,
                                current_chunker_version=CHUNKER_VERSION,
                                created_at=existing.created_at,
                                updated_at=self._now(),
                            )
                            parsed = await asyncio.to_thread(
                                parse_file, scanned.absolute_path, scanned.file_type
                            )
                            new_chunks = chunk_document(
                                document_id=existing.document_id,
                                document_content_hash=scanned.content_hash,
                                parsed_doc=parsed,
                                new_chunk_id=self._new_chunk_id,
                                now=self._now,
                            )
                            if not new_chunks:
                                raise ValueError(
                                    "document did not contain extractable text"
                                )
                            await self._repository.save_chunks(new_chunks)
                            total_chunks += len(new_chunks)
                            new_chunks_count += len(new_chunks)

                            indexed_n = await self._embed_and_index_chunks(
                                source, new_chunks, profile
                            )
                            indexed_chunks_count += indexed_n
                            await self._repository.save_document(updated_doc)
                            if old_chunks:
                                await self._repository.supersede_chunks(
                                    [c.chunk_id for c in old_chunks],
                                    superseded_at=self._now(),
                                )
                                if self._vector_store is not None:
                                    old_point_ids: list[str] = []
                                    for old_chunk in old_chunks:
                                        embedding = (
                                            await self._repository.get_chunk_embedding(
                                                old_chunk.chunk_id, profile.profile_id
                                            )
                                        )
                                        if embedding is not None:
                                            old_point_ids.append(embedding.point_id)
                                    await asyncio.to_thread(
                                        self._vector_store.delete_points,
                                        profile.qdrant_collection,
                                        old_point_ids,
                                    )
                    else:
                        # New document
                        added_docs += 1
                        doc_id = self._new_document_id()
                        now_doc = self._now()
                        new_doc = KnowledgeDocument(
                            document_id=doc_id,
                            source_id=source_id,
                            relative_path=scanned.relative_path,
                            file_type=scanned.file_type,
                            status="active",
                            size_bytes=scanned.size_bytes,
                            mtime_ns=scanned.mtime_ns,
                            content_hash=scanned.content_hash,
                            parser_version=PARSER_VERSION,
                            current_chunker_version=CHUNKER_VERSION,
                            created_at=now_doc,
                            updated_at=now_doc,
                        )
                        parsed = await asyncio.to_thread(
                            parse_file, scanned.absolute_path, scanned.file_type
                        )
                        new_chunks = chunk_document(
                            document_id=doc_id,
                            document_content_hash=scanned.content_hash,
                            parsed_doc=parsed,
                            new_chunk_id=self._new_chunk_id,
                            now=self._now,
                        )
                        if not new_chunks:
                            raise ValueError(
                                "document did not contain extractable text"
                            )
                        await self._repository.save_document(new_doc)
                        await self._repository.save_chunks(new_chunks)
                        total_chunks += len(new_chunks)
                        new_chunks_count += len(new_chunks)

                        indexed_n = await self._embed_and_index_chunks(
                            source, new_chunks, profile
                        )
                        indexed_chunks_count += indexed_n

                except Exception as exc:
                    failed_docs += 1
                    last_file_error = f"{type(exc).__name__}: {exc}"

                processed_docs += 1
                await self._repository.update_index_job_progress(
                    effective_job_id,
                    discovered_files=discovered_count,
                    processed_files=processed_docs,
                    skipped_files=unchanged_docs,
                    failed_files=failed_docs,
                    total_chunks=total_chunks,
                    indexed_chunks=indexed_chunks_count,
                )

            # Handle deleted files
            scanned_rel_paths = {s.relative_path for s in scanned_files}
            for rel_path, existing in existing_by_rel_path.items():
                if rel_path not in scanned_rel_paths:
                    deleted_docs += 1
                    old_chunks = await self._repository.list_active_chunks_for_document(
                        existing.document_id
                    )
                    if old_chunks:
                        await self._repository.supersede_chunks(
                            [c.chunk_id for c in old_chunks],
                            superseded_at=self._now(),
                        )
                        if self._vector_store is not None:
                            self._vector_store.delete_by_document(
                                profile.qdrant_collection,
                                existing.document_id,
                            )
                    await self._repository.update_document_status(
                        existing.document_id, "missing"
                    )

            finish_now = self._now()
            await self._repository.update_source_scan_status(
                source_id, "ready", last_scanned_at=finish_now
            )

            completed_job = KnowledgeIndexJob(
                job_id=job.job_id,
                library_id=job.library_id,
                kind=job.kind,
                status="completed",
                discovered_files=discovered_count,
                processed_files=processed_docs,
                skipped_files=unchanged_docs,
                failed_files=failed_docs,
                total_chunks=total_chunks,
                indexed_chunks=indexed_chunks_count,
                cancel_requested=False,
                created_at=job.created_at,
                updated_at=finish_now,
                source_id=job.source_id,
                last_error_code=last_file_error,
                started_at=job.started_at,
                completed_at=finish_now,
            )
            await self._repository.save_index_job(completed_job)

            return IndexSourceStats(
                total_scanned=discovered_count,
                added_docs=added_docs,
                modified_docs=modified_docs,
                unchanged_docs=unchanged_docs,
                deleted_docs=deleted_docs,
                total_chunks=total_chunks,
                new_chunks=new_chunks_count,
                indexed_chunks=indexed_chunks_count,
            )

        except Exception as exc:
            finish_now = self._now()
            await self._repository.update_source_scan_status(source_id, "error")
            current_job = await self._repository.get_index_job(job.job_id)
            progress_job = current_job or job
            failed_job = KnowledgeIndexJob(
                job_id=job.job_id,
                library_id=job.library_id,
                kind=job.kind,
                status="failed",
                discovered_files=progress_job.discovered_files,
                processed_files=progress_job.processed_files,
                skipped_files=progress_job.skipped_files,
                failed_files=max(1, progress_job.failed_files),
                total_chunks=progress_job.total_chunks,
                indexed_chunks=progress_job.indexed_chunks,
                cancel_requested=False,
                created_at=job.created_at,
                updated_at=finish_now,
                source_id=job.source_id,
                last_error_code=str(exc),
                started_at=job.started_at,
                completed_at=finish_now,
            )
            await self._repository.save_index_job(failed_job)
            raise

    async def index_library(
        self,
        library_id: LibraryId,
    ) -> tuple[IndexSourceStats, ...]:
        """Index all active sources belonging to a library."""
        sources = await self._repository.list_sources_for_library(library_id)
        results: list[IndexSourceStats] = []
        for src in sources:
            if src.status == "active":
                stats = await self.index_source(src.source_id)
                results.append(stats)
        return tuple(results)
