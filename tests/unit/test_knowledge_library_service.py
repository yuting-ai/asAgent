from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from asagent.core.ids import LibraryId, UserId
from asagent.knowledge.service import (
    DuplicateLibraryNameError,
    DuplicateSourceError,
    InvalidSourcePathError,
    KnowledgeLibraryService,
    LastLibraryDeletionError,
    LibraryNotFoundError,
)
from asagent.storage.sqlite.knowledge_repository import (
    SqliteKnowledgeRepository,
)


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


@pytest.fixture
async def library_service(
    tmp_path: Path,
) -> AsyncIterator[KnowledgeLibraryService]:
    db_path = tmp_path / "asagent.sqlite3"
    _upgrade(db_path)
    repo = SqliteKnowledgeRepository(db_path)
    fixed_now = datetime(2026, 8, 31, 12, 0, 0, tzinfo=UTC)
    service = KnowledgeLibraryService(
        repository=repo,
        now=lambda: fixed_now,
    )
    try:
        yield service
    finally:
        await repo.aclose()


async def test_ensure_default_library(
    library_service: KnowledgeLibraryService,
) -> None:
    user_id = UserId("u1")
    # First call creates "Research Papers"
    lib1 = await library_service.ensure_default_library(user_id)
    assert lib1.name == "Research Papers"
    assert lib1.status == "active"

    # Second call returns the existing default
    lib2 = await library_service.ensure_default_library(user_id)
    assert lib2.library_id == lib1.library_id


async def test_create_library_validation_and_uniqueness(
    library_service: KnowledgeLibraryService,
) -> None:
    user_id = UserId("u1")

    # Empty name
    with pytest.raises(ValueError, match="cannot be empty"):
        await library_service.create_library(user_id, "   ")

    # Valid creation
    lib1 = await library_service.create_library(user_id, "  Deep Learning  ")
    assert lib1.name == "Deep Learning"
    assert lib1.normalized_name == "deep learning"

    # Duplicate name (case/whitespace insensitive)
    with pytest.raises(DuplicateLibraryNameError):
        await library_service.create_library(user_id, "deep learning")

    with pytest.raises(DuplicateLibraryNameError):
        await library_service.create_library(user_id, "  DEEP LEARNING  ")

    # Different user can have the same library name
    lib_u2 = await library_service.create_library(UserId("u2"), "Deep Learning")
    assert lib_u2.user_id == "u2"


async def test_rename_library(
    library_service: KnowledgeLibraryService,
) -> None:
    user_id = UserId("u1")
    lib1 = await library_service.create_library(user_id, "Lib One")
    _lib2 = await library_service.create_library(user_id, "Lib Two")

    # Empty name
    with pytest.raises(ValueError, match="cannot be empty"):
        await library_service.rename_library(user_id, lib1.library_id, "")

    # Non-existent library
    with pytest.raises(LibraryNotFoundError):
        await library_service.rename_library(
            user_id, LibraryId("lib_unknown"), "New Name"
        )

    # Renaming to existing other library name
    with pytest.raises(DuplicateLibraryNameError):
        await library_service.rename_library(user_id, lib1.library_id, "LIB TWO")

    # Renaming self with casing change
    renamed = await library_service.rename_library(user_id, lib1.library_id, "lib one")
    assert renamed.name == "lib one"

    # Valid rename
    renamed_final = await library_service.rename_library(
        user_id, lib1.library_id, "Artificial Intelligence"
    )
    assert renamed_final.name == "Artificial Intelligence"
    assert renamed_final.normalized_name == "artificial intelligence"


async def test_delete_library_protection(
    library_service: KnowledgeLibraryService,
) -> None:
    user_id = UserId("u1")
    lib1 = await library_service.create_library(user_id, "Only Lib")

    # Cannot delete last remaining library
    with pytest.raises(LastLibraryDeletionError):
        await library_service.delete_library(user_id, lib1.library_id)

    # Create second library, then deletion succeeds
    lib2 = await library_service.create_library(user_id, "Second Lib")
    await library_service.delete_library(user_id, lib1.library_id)

    remaining = await library_service.list_libraries(user_id)
    assert len(remaining) == 1
    assert remaining[0].library_id == lib2.library_id

    # Now lib2 is the only library and cannot be deleted
    with pytest.raises(LastLibraryDeletionError):
        await library_service.delete_library(user_id, lib2.library_id)


async def test_source_management_lifecycle(
    library_service: KnowledgeLibraryService, tmp_path: Path
) -> None:
    user_id = UserId("u1")
    lib = await library_service.create_library(user_id, "Source Test Lib")

    # Prepare directories on disk
    dir_a = tmp_path / "papers_a"
    dir_a.mkdir()
    file_b = tmp_path / "file_b.txt"
    file_b.write_text("not a directory")

    # Invalid paths
    with pytest.raises(InvalidSourcePathError, match="cannot be empty"):
        await library_service.add_source(user_id, lib.library_id, "  ")

    with pytest.raises(InvalidSourcePathError, match="does not exist"):
        await library_service.add_source(
            user_id, lib.library_id, str(tmp_path / "non_existent")
        )

    with pytest.raises(InvalidSourcePathError, match="not a directory"):
        await library_service.add_source(user_id, lib.library_id, str(file_b))

    # Valid add source
    src_a, is_new = await library_service.add_source(
        user_id, lib.library_id, str(dir_a)
    )
    assert is_new is True
    assert src_a.status == "active"
    assert src_a.scan_status == "queued"
    assert src_a.canonical_path == str(dir_a.resolve())

    # Duplicate active source
    with pytest.raises(DuplicateSourceError):
        await library_service.add_source(user_id, lib.library_id, str(dir_a))

    # Detach source (soft remove)
    detached = await library_service.detach_source(
        user_id, lib.library_id, src_a.source_id
    )
    assert detached.status == "detached"
    assert detached.detached_at is not None

    # List sources (active only by default)
    active_sources = await library_service.list_sources(
        user_id, lib.library_id, include_detached=False
    )
    assert len(active_sources) == 0

    all_sources = await library_service.list_sources(
        user_id, lib.library_id, include_detached=True
    )
    assert len(all_sources) == 1
    assert all_sources[0].status == "detached"

    # Re-adding detached source reactivates it
    reactivated, is_new2 = await library_service.add_source(
        user_id, lib.library_id, str(dir_a)
    )
    assert is_new2 is False
    assert reactivated.source_id == src_a.source_id
    assert reactivated.status == "active"
    assert reactivated.scan_status == "queued"

    active_sources_after = await library_service.list_sources(
        user_id, lib.library_id, include_detached=False
    )
    assert len(active_sources_after) == 1
