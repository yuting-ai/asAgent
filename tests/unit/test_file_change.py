from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from asagent.core.file_change import (
    FileChange,
    FileChangeOperation,
    FileChangeStatus,
)
from asagent.core.ids import FileChangeId, RunId


def test_file_change_preserves_reversible_change_metadata() -> None:
    created_at = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    updated_at = datetime(2026, 8, 15, 10, 1, tzinfo=UTC)

    file_change = FileChange(
        file_change_id=FileChangeId("change_123"),
        run_id=RunId("run_123"),
        operation=FileChangeOperation.REPLACE,
        status=FileChangeStatus.APPLIED,
        root_path="/workspace",
        relative_path="notes/today.txt",
        before_hash="before-sha256",
        after_hash="after-sha256",
        snapshot_ref="file-changes/change_123.before",
        created_at=created_at,
        updated_at=updated_at,
    )

    assert file_change.file_change_id == "change_123"
    assert file_change.run_id == "run_123"
    assert file_change.operation is FileChangeOperation.REPLACE
    assert file_change.status is FileChangeStatus.APPLIED
    assert file_change.root_path == "/workspace"
    assert file_change.relative_path == "notes/today.txt"
    assert file_change.before_hash == "before-sha256"
    assert file_change.after_hash == "after-sha256"
    assert file_change.snapshot_ref == "file-changes/change_123.before"
    assert file_change.created_at == created_at
    assert file_change.updated_at == updated_at


def test_file_change_operation_and_status_values_are_stable() -> None:
    assert [operation.value for operation in FileChangeOperation] == [
        "create",
        "replace",
        "delete",
    ]
    assert [status.value for status in FileChangeStatus] == [
        "prepared",
        "applied",
        "reverted",
        "conflicted",
    ]


@pytest.mark.parametrize(
    ("operation", "before_hash", "after_hash", "snapshot_ref"),
    [
        (FileChangeOperation.CREATE, None, "after-sha256", None),
        (
            FileChangeOperation.REPLACE,
            "before-sha256",
            "after-sha256",
            "file-changes/change_123.before",
        ),
        (
            FileChangeOperation.DELETE,
            "before-sha256",
            None,
            "file-changes/change_123.before",
        ),
    ],
)
def test_file_change_accepts_operation_specific_metadata(
    operation: FileChangeOperation,
    before_hash: str | None,
    after_hash: str | None,
    snapshot_ref: str | None,
) -> None:
    file_change = FileChange(
        file_change_id=FileChangeId("change_123"),
        run_id=RunId("run_123"),
        operation=operation,
        status=FileChangeStatus.PREPARED,
        root_path="/workspace",
        relative_path="notes.txt",
        before_hash=before_hash,
        after_hash=after_hash,
        snapshot_ref=snapshot_ref,
        created_at=datetime(2026, 8, 15, 10, 0, tzinfo=UTC),
        updated_at=datetime(2026, 8, 15, 10, 0, tzinfo=UTC),
    )

    assert file_change.operation is operation


@pytest.mark.parametrize(
    ("operation", "before_hash", "after_hash", "snapshot_ref", "message"),
    [
        (
            FileChangeOperation.CREATE,
            "before-sha256",
            "after-sha256",
            None,
            "create changes cannot have a before hash or snapshot",
        ),
        (
            FileChangeOperation.REPLACE,
            None,
            "after-sha256",
            "file-changes/change_123.before",
            "replace changes require before and after hashes",
        ),
        (
            FileChangeOperation.DELETE,
            "before-sha256",
            "after-sha256",
            "file-changes/change_123.before",
            "delete changes cannot have an after hash",
        ),
    ],
)
def test_file_change_rejects_invalid_operation_metadata(
    operation: FileChangeOperation,
    before_hash: str | None,
    after_hash: str | None,
    snapshot_ref: str | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        FileChange(
            file_change_id=FileChangeId("change_123"),
            run_id=RunId("run_123"),
            operation=operation,
            status=FileChangeStatus.PREPARED,
            root_path="/workspace",
            relative_path="notes.txt",
            before_hash=before_hash,
            after_hash=after_hash,
            snapshot_ref=snapshot_ref,
            created_at=datetime(2026, 8, 15, 10, 0, tzinfo=UTC),
            updated_at=datetime(2026, 8, 15, 10, 0, tzinfo=UTC),
        )


def test_file_change_is_immutable() -> None:
    file_change = FileChange(
        file_change_id=FileChangeId("change_123"),
        run_id=RunId("run_123"),
        operation=FileChangeOperation.CREATE,
        status=FileChangeStatus.PREPARED,
        root_path="/workspace",
        relative_path="notes.txt",
        before_hash=None,
        after_hash="after-sha256",
        snapshot_ref=None,
        created_at=datetime(2026, 8, 15, 10, 0, tzinfo=UTC),
        updated_at=datetime(2026, 8, 15, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(FrozenInstanceError):
        file_change.status = FileChangeStatus.APPLIED  # type: ignore[misc]
