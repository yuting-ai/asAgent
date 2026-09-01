from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from asagent.core.ids import (
    ChunkId,
    DocumentId,
    LibraryId,
    ProfileId,
    SourceId,
)


@dataclass(frozen=True, slots=True)
class VectorPoint:
    """A vector embedding point to be indexed in Qdrant."""

    point_id: str
    vector: list[float]
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class VectorSearchResult:
    """A single nearest-neighbor search hit from Qdrant."""

    point_id: str
    score: float
    chunk_id: ChunkId
    payload: dict[str, Any]


class KnowledgeVectorStore:
    """Local embedded Qdrant vector database wrapper for Knowledge chunks."""

    def __init__(self, storage_dir: Path) -> None:
        storage_dir.mkdir(parents=True, exist_ok=True)
        self._storage_dir = storage_dir
        self._client = QdrantClient(path=str(storage_dir))

    def ensure_collection(
        self,
        collection_name: str,
        *,
        dimension: int = 384,
        distance: Distance = Distance.COSINE,
    ) -> None:
        """Create the collection if it does not already exist."""
        if not self._client.collection_exists(collection_name):
            self._client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=dimension,
                    distance=distance,
                ),
            )

    def upsert_points(
        self,
        collection_name: str,
        points: Sequence[VectorPoint],
        *,
        batch_size: int = 64,
    ) -> None:
        """Batch upsert points into a Qdrant collection."""
        if not points:
            return

        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            structs = [
                PointStruct(
                    id=p.point_id,
                    vector=p.vector,
                    payload=p.payload,
                )
                for p in batch
            ]
            self._client.upsert(
                collection_name=collection_name,
                points=structs,
            )

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        *,
        library_id: LibraryId | None = None,
        profile_id: ProfileId | None = None,
        limit: int = 5,
        score_threshold: float | None = None,
    ) -> tuple[VectorSearchResult, ...]:
        """Perform semantic nearest-neighbor search with active status and library filtering."""
        if not self._client.collection_exists(collection_name):
            return ()

        must_conditions: list[Any] = [
            FieldCondition(key="status", match=MatchValue(value="active"))
        ]
        if library_id is not None:
            must_conditions.append(
                FieldCondition(
                    key="library_id", match=MatchValue(value=str(library_id))
                )
            )
        if profile_id is not None:
            must_conditions.append(
                FieldCondition(
                    key="profile_id", match=MatchValue(value=str(profile_id))
                )
            )

        query_filter = Filter(must=must_conditions)
        response = self._client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
        )

        results: list[VectorSearchResult] = []
        for pt in response.points:
            payload = pt.payload or {}
            chunk_id_str = str(payload.get("chunk_id", ""))
            results.append(
                VectorSearchResult(
                    point_id=str(pt.id),
                    score=float(pt.score),
                    chunk_id=ChunkId(chunk_id_str),
                    payload=payload,
                )
            )
        return tuple(results)

    def delete_by_document(
        self,
        collection_name: str,
        document_id: DocumentId,
    ) -> None:
        """Delete points associated with a document ID."""
        if not self._client.collection_exists(collection_name):
            return
        self._client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=str(document_id)),
                    )
                ]
            ),
        )

    def delete_by_source(
        self,
        collection_name: str,
        source_id: SourceId,
    ) -> None:
        """Delete points associated with a source ID."""
        if not self._client.collection_exists(collection_name):
            return
        self._client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="source_id",
                        match=MatchValue(value=str(source_id)),
                    )
                ]
            ),
        )

    def set_source_status(
        self,
        collection_name: str,
        source_id: SourceId,
        *,
        active: bool,
    ) -> None:
        """Activate or deactivate retained source points without recomputing vectors."""
        if not self._client.collection_exists(collection_name):
            return
        self._client.set_payload(
            collection_name=collection_name,
            payload={"status": "active" if active else "detached"},
            points=Filter(
                must=[
                    FieldCondition(
                        key="source_id",
                        match=MatchValue(value=str(source_id)),
                    )
                ]
            ),
        )

    def delete_points(self, collection_name: str, point_ids: Sequence[str]) -> None:
        """Delete exact obsolete points while preserving a document's replacement points."""
        if not point_ids or not self._client.collection_exists(collection_name):
            return
        self._client.delete(
            collection_name=collection_name, points_selector=list(point_ids)
        )

    def delete_by_library(
        self,
        collection_name: str,
        library_id: LibraryId,
    ) -> None:
        """Delete points associated with a library ID."""
        if not self._client.collection_exists(collection_name):
            return
        self._client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="library_id",
                        match=MatchValue(value=str(library_id)),
                    )
                ]
            ),
        )

    def set_library_status(
        self,
        collection_name: str,
        library_id: LibraryId,
        *,
        active: bool,
    ) -> None:
        """Deactivate retained Library points while keeping the index rebuildable."""
        if not self._client.collection_exists(collection_name):
            return
        self._client.set_payload(
            collection_name=collection_name,
            payload={"status": "active" if active else "detached"},
            points=Filter(
                must=[
                    FieldCondition(
                        key="library_id",
                        match=MatchValue(value=str(library_id)),
                    )
                ]
            ),
        )

    def count_points(self, collection_name: str) -> int:
        """Count total points stored in a collection."""
        if not self._client.collection_exists(collection_name):
            return 0
        return int(self._client.count(collection_name=collection_name).count)

    def close(self) -> None:
        """Explicitly close the embedded Qdrant client."""
        self._client.close()
