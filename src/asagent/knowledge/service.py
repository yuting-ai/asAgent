import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from asagent.core.ids import LibraryId, SourceId, UserId
from asagent.knowledge.models import (
    KnowledgeLibrary,
    KnowledgeSource,
    normalize_library_name,
)
from asagent.knowledge.repository import KnowledgeRepository


class KnowledgeError(Exception):
    """Base exception for Knowledge domain errors."""


class LibraryNotFoundError(KnowledgeError):
    """Raised when a specified library is not found or does not belong to the user."""


class DuplicateLibraryNameError(KnowledgeError):
    """Raised when a library with the same normalized name already exists for the user."""


class LastLibraryDeletionError(KnowledgeError):
    """Raised when attempting to delete the only remaining library for a user."""


class SourceNotFoundError(KnowledgeError):
    """Raised when a specified knowledge source is not found."""


class DuplicateSourceError(KnowledgeError):
    """Raised when adding a directory that is already active in the library."""


class InvalidSourcePathError(KnowledgeError):
    """Raised when the specified source path is not a valid accessible directory."""


class KnowledgeLibraryService:
    """Domain service managing Knowledge Libraries and their directory Sources."""

    def __init__(
        self,
        *,
        repository: KnowledgeRepository,
        now: Callable[[], datetime] | None = None,
        new_library_id: Callable[[], LibraryId] | None = None,
        new_source_id: Callable[[], SourceId] | None = None,
    ) -> None:
        self._repository = repository
        self._now = now or (lambda: datetime.now(UTC))
        self._new_library_id = new_library_id or (
            lambda: LibraryId(f"lib_{uuid.uuid4().hex[:12]}")
        )
        self._new_source_id = new_source_id or (
            lambda: SourceId(f"src_{uuid.uuid4().hex[:12]}")
        )

    # -------------------------------------------------------------------------
    # Library Management
    # -------------------------------------------------------------------------

    async def ensure_default_library(
        self, user_id: UserId, default_name: str = "Research Papers"
    ) -> KnowledgeLibrary:
        """Ensure the user has at least one default library."""
        existing = await self._repository.list_libraries_for_user(user_id)
        if existing:
            return existing[0]
        return await self.create_library(user_id=user_id, name=default_name)

    async def create_library(self, user_id: UserId, name: str) -> KnowledgeLibrary:
        """Create a new library for a user with unique name enforcement."""
        stripped_name = name.strip()
        if not stripped_name:
            raise ValueError("Library name cannot be empty")

        norm = normalize_library_name(stripped_name)
        existing = await self._repository.list_libraries_for_user(user_id)
        if any(lib.normalized_name == norm for lib in existing):
            raise DuplicateLibraryNameError(f"Library '{stripped_name}' already exists")

        now = self._now()
        library = KnowledgeLibrary(
            library_id=self._new_library_id(),
            user_id=user_id,
            name=stripped_name,
            normalized_name=norm,
            status="active",
            created_at=now,
            updated_at=now,
        )
        await self._repository.save_library(library)
        return library

    async def rename_library(
        self, user_id: UserId, library_id: LibraryId, new_name: str
    ) -> KnowledgeLibrary:
        """Rename an existing library with uniqueness check."""
        stripped_name = new_name.strip()
        if not stripped_name:
            raise ValueError("Library name cannot be empty")

        library = await self._repository.get_library(library_id)
        if library is None or library.user_id != user_id or library.status != "active":
            raise LibraryNotFoundError(f"Library '{library_id}' not found")

        norm = normalize_library_name(stripped_name)
        if norm != library.normalized_name:
            existing = await self._repository.list_libraries_for_user(user_id)
            if any(
                lib.library_id != library_id and lib.normalized_name == norm
                for lib in existing
            ):
                raise DuplicateLibraryNameError(
                    f"Library '{stripped_name}' already exists"
                )

        now = self._now()
        updated = KnowledgeLibrary(
            library_id=library.library_id,
            user_id=library.user_id,
            name=stripped_name,
            normalized_name=norm,
            status=library.status,
            created_at=library.created_at,
            updated_at=now,
        )
        await self._repository.save_library(updated)
        return updated

    async def delete_library(self, user_id: UserId, library_id: LibraryId) -> None:
        """Delete a library, ensuring it is not the last remaining library for the user."""
        library = await self._repository.get_library(library_id)
        if library is None or library.user_id != user_id or library.status != "active":
            raise LibraryNotFoundError(f"Library '{library_id}' not found")

        count = await self._repository.count_libraries_for_user(user_id)
        if count <= 1:
            raise LastLibraryDeletionError("Cannot delete the last remaining library")

        deleted = await self._repository.delete_library(library_id)
        if not deleted:
            raise LibraryNotFoundError(f"Library '{library_id}' not found")

    async def list_libraries(self, user_id: UserId) -> tuple[KnowledgeLibrary, ...]:
        """List all libraries for a given user."""
        return await self._repository.list_libraries_for_user(user_id)

    async def get_library(self, library_id: LibraryId) -> KnowledgeLibrary | None:
        """Get a single library by ID."""
        return await self._repository.get_library(library_id)

    # -------------------------------------------------------------------------
    # Source Directory Management
    # -------------------------------------------------------------------------

    async def add_source(
        self, user_id: UserId, library_id: LibraryId, path_str: str
    ) -> tuple[KnowledgeSource, bool]:
        """Add a local directory source to a library or reactivate a detached one.

        Returns:
            (source, is_new): tuple of KnowledgeSource and boolean indicating if newly created.
        """
        library = await self._repository.get_library(library_id)
        if library is None or library.user_id != user_id or library.status != "active":
            raise LibraryNotFoundError(f"Library '{library_id}' not found")

        stripped_path = path_str.strip()
        if not stripped_path:
            raise InvalidSourcePathError("Source path cannot be empty")

        try:
            resolved = Path(stripped_path).expanduser().resolve()
        except Exception as exc:
            raise InvalidSourcePathError(
                f"Invalid source path '{stripped_path}': {exc}"
            ) from exc

        if not resolved.exists():
            raise InvalidSourcePathError(
                f"Source directory does not exist: '{stripped_path}'"
            )
        if not resolved.is_dir():
            raise InvalidSourcePathError(
                f"Source path is not a directory: '{stripped_path}'"
            )

        canonical_path = str(resolved)
        existing = await self._repository.get_source_by_canonical_path(
            library_id, canonical_path
        )

        now = self._now()
        if existing is not None:
            if existing.status == "active":
                raise DuplicateSourceError(
                    f"Directory '{stripped_path}' is already added to this library"
                )
            # Reactivate soft-detached source
            await self._repository.update_source_status(existing.source_id, "active")
            await self._repository.update_source_scan_status(
                existing.source_id, "queued"
            )
            reactivated = await self._repository.get_source(existing.source_id)
            if reactivated is None:
                raise SourceNotFoundError("Failed to reload reactivated source")
            return reactivated, False

        # Create new source
        source = KnowledgeSource(
            source_id=self._new_source_id(),
            library_id=library_id,
            display_path=stripped_path,
            canonical_path=canonical_path,
            status="active",
            scan_status="queued",
            created_at=now,
            updated_at=now,
        )
        await self._repository.save_source(source)
        return source, True

    async def detach_source(
        self, user_id: UserId, library_id: LibraryId, source_id: SourceId
    ) -> KnowledgeSource:
        """Soft-remove a source directory from a library."""
        library = await self._repository.get_library(library_id)
        if library is None or library.user_id != user_id or library.status != "active":
            raise LibraryNotFoundError(f"Library '{library_id}' not found")

        source = await self._repository.get_source(source_id)
        if source is None or source.library_id != library_id:
            raise SourceNotFoundError(f"Source '{source_id}' not found")

        now = self._now()
        await self._repository.update_source_status(
            source_id, "detached", detached_at=now
        )
        updated = await self._repository.get_source(source_id)
        if updated is None:
            raise SourceNotFoundError("Failed to reload detached source")
        return updated

    async def list_sources(
        self,
        user_id: UserId,
        library_id: LibraryId,
        include_detached: bool = False,
    ) -> tuple[KnowledgeSource, ...]:
        """List sources in a library with optional detached filtering."""
        library = await self._repository.get_library(library_id)
        if library is None or library.user_id != user_id or library.status != "active":
            raise LibraryNotFoundError(f"Library '{library_id}' not found")

        sources = await self._repository.list_sources_for_library(library_id)
        if include_detached:
            return sources
        return tuple(s for s in sources if s.status == "active")

    async def get_source(self, source_id: SourceId) -> KnowledgeSource | None:
        """Get a source by ID."""
        return await self._repository.get_source(source_id)
