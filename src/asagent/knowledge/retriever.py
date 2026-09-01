import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from asagent.core.ids import (
    ChunkId,
    DocumentId,
    LibraryId,
    RunId,
    SourceId,
)
from asagent.knowledge.embedder import (
    LocalMiniLMEmbedder,
    ensure_default_profile,
)
from asagent.knowledge.models import (
    KnowledgeChunk,
    KnowledgeCitation,
    KnowledgeDocument,
    KnowledgeRetrievalHit,
    KnowledgeSource,
)
from asagent.knowledge.repository import KnowledgeRepository
from asagent.storage.qdrant import (
    KnowledgeVectorStore,
    VectorSearchResult,
)


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """The complete result of a Knowledge RAG retrieval operation."""

    hits: tuple[KnowledgeRetrievalHit, ...]
    citations: tuple[KnowledgeCitation, ...]
    formatted_context: str


@dataclass(frozen=True, slots=True)
class _HydratedCandidate:
    vector_hit: VectorSearchResult
    chunk: KnowledgeChunk
    document: KnowledgeDocument
    source: KnowledgeSource


def _select_diverse_candidates(
    candidates: Sequence[_HydratedCandidate],
    *,
    limit: int,
) -> tuple[_HydratedCandidate, ...]:
    """Reserve a second result for another document, then preserve score order."""
    if limit <= 0:
        return ()

    selected: list[_HydratedCandidate] = []
    selected_chunks: set[ChunkId] = set()
    selected_documents: set[DocumentId] = set()
    distinct_target = min(
        limit, 2, len({item.document.document_id for item in candidates})
    )

    for candidate in candidates:
        if candidate.document.document_id in selected_documents:
            continue
        selected.append(candidate)
        selected_chunks.add(candidate.chunk.chunk_id)
        selected_documents.add(candidate.document.document_id)
        if len(selected_documents) >= distinct_target:
            break

    for candidate in candidates:
        if candidate.chunk.chunk_id in selected_chunks:
            continue
        selected.append(candidate)
        selected_chunks.add(candidate.chunk.chunk_id)
        if len(selected) >= limit:
            break

    return tuple(selected[:limit])


class KnowledgeRetriever:
    """Retrieves relevant knowledge chunks using vector search, filters, and metadata enrichment."""

    def __init__(
        self,
        *,
        repository: KnowledgeRepository,
        embedder: LocalMiniLMEmbedder,
        vector_store: KnowledgeVectorStore,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._embedder = embedder
        self._vector_store = vector_store
        self._now = now or (lambda: datetime.now(UTC))

    def format_citations_context(self, citations: Sequence[KnowledgeCitation]) -> str:
        """Format a list of citations into a clean Markdown block for LLM prompting."""
        if not citations:
            return ""

        parts: list[str] = []
        for cit in citations:
            loc_parts: list[str] = []
            if cit.page_start is not None:
                if cit.page_end is not None and cit.page_end != cit.page_start:
                    loc_parts.append(f"p.{cit.page_start}-{cit.page_end}")
                else:
                    loc_parts.append(f"p.{cit.page_start}")
            if cit.section_title:
                loc_parts.append(f"#{cit.section_title}")

            loc_str = f" ({', '.join(loc_parts)})" if loc_parts else ""
            header = f"[{cit.label}] {cit.document_name}{loc_str}"
            parts.append(f"{header}:\n{cit.snippet.strip()}")

        return "\n\n".join(parts)

    async def _filename_candidates(
        self,
        *,
        query: str,
        library_id: LibraryId,
    ) -> tuple[_HydratedCandidate, ...]:
        normalized_query = query.casefold()
        candidates: list[_HydratedCandidate] = []
        sources = await self._repository.list_sources_for_library(library_id)
        for source in sources:
            if source.status != "active":
                continue
            documents = await self._repository.list_documents_for_source(
                source.source_id
            )
            for document in documents:
                if document.status != "active":
                    continue
                relative_path = document.relative_path.casefold()
                file_name = Path(document.relative_path).name.casefold()
                if (
                    relative_path not in normalized_query
                    and file_name not in normalized_query
                ):
                    continue
                for chunk in await self._repository.list_active_chunks_for_document(
                    document.document_id
                ):
                    candidates.append(
                        _HydratedCandidate(
                            vector_hit=VectorSearchResult(
                                point_id=f"filename:{chunk.chunk_id}",
                                score=1.0,
                                chunk_id=chunk.chunk_id,
                                payload={"match": "filename"},
                            ),
                            chunk=chunk,
                            document=document,
                            source=source,
                        )
                    )
        return tuple(candidates)

    async def retrieve(
        self,
        *,
        query: str,
        library_id: LibraryId,
        run_id: RunId | None = None,
        limit: int = 5,
        min_score: float = 0.35,
        save_hits: bool = True,
    ) -> RetrievalResult:
        """Retrieve top-k relevant knowledge chunks for a query from a specific library."""
        if not query.strip():
            return RetrievalResult(hits=(), citations=(), formatted_context="")

        now = self._now()
        profile = await ensure_default_profile(self._repository, now=now)

        candidates = list(
            await self._filename_candidates(query=query, library_id=library_id)
        )
        if not candidates:
            query_vec = await asyncio.to_thread(self._embedder.embed_query, query)
            raw_hits: tuple[VectorSearchResult, ...] = await asyncio.to_thread(
                self._vector_store.search,
                profile.qdrant_collection,
                query_vec,
                library_id=library_id,
                profile_id=profile.profile_id,
                limit=max(limit * 8, 20),
                score_threshold=min_score,
            )

            if not raw_hits:
                return RetrievalResult(hits=(), citations=(), formatted_context="")

            # Batch load active chunks from SQLite
            chunk_ids = [h.chunk_id for h in raw_hits]
            chunks = await self._repository.get_chunks_batch(chunk_ids)
            chunk_map = {c.chunk_id: c for c in chunks if c.status == "active"}

            # Cache documents and sources
            doc_cache: dict[DocumentId, KnowledgeDocument] = {}
            src_cache: dict[SourceId, KnowledgeSource] = {}

            for hit in raw_hits:
                chunk = chunk_map.get(hit.chunk_id)
                if chunk is None:
                    continue

                # Load document
                if chunk.document_id not in doc_cache:
                    doc = await self._repository.get_document(chunk.document_id)
                    if doc is None or doc.status != "active":
                        continue
                    doc_cache[chunk.document_id] = doc
                doc = doc_cache[chunk.document_id]

                # Load source
                if doc.source_id not in src_cache:
                    src = await self._repository.get_source(doc.source_id)
                    if src is None or src.status != "active":
                        continue
                    src_cache[doc.source_id] = src
                src = src_cache[doc.source_id]

                candidates.append(
                    _HydratedCandidate(
                        vector_hit=hit,
                        chunk=chunk,
                        document=doc,
                        source=src,
                    )
                )

        selected_candidates = _select_diverse_candidates(candidates, limit=limit)
        hits: list[KnowledgeRetrievalHit] = []
        citations: list[KnowledgeCitation] = []
        effective_run_id = run_id or RunId("run_retrieval_preview")

        for rank, candidate in enumerate(selected_candidates, start=1):
            hit = candidate.vector_hit
            chunk = candidate.chunk
            doc = candidate.document
            src = candidate.source

            label = f"S{rank}"
            retrieval_hit = KnowledgeRetrievalHit(
                run_id=effective_run_id,
                rank=rank,
                chunk_id=chunk.chunk_id,
                profile_id=profile.profile_id,
                score=hit.score,
                citation_label=label,
                document_name_snapshot=doc.relative_path,
                source_path_snapshot=src.display_path,
                content_hash_snapshot=chunk.content_hash,
                snippet_snapshot=chunk.text,
                created_at=now,
                page_start_snapshot=chunk.page_start,
                page_end_snapshot=chunk.page_end,
                section_title_snapshot=chunk.section_title,
            )
            hits.append(retrieval_hit)

            citation = KnowledgeCitation(
                label=label,
                document_name=doc.relative_path,
                source_path=src.display_path,
                snippet=chunk.text,
                score=hit.score,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                section_title=chunk.section_title,
            )
            citations.append(citation)

        if hits and save_hits and run_id is not None:
            await self._repository.save_retrieval_hits(hits)

        formatted_context = self.format_citations_context(citations)
        return RetrievalResult(
            hits=tuple(hits),
            citations=tuple(citations),
            formatted_context=formatted_context,
        )
