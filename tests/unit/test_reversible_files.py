from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from asagent.core.file_change import FileChange, FileChangeOperation, FileChangeStatus
from asagent.core.ids import FileChangeId, RunId
from asagent.storage.file_change_snapshots import FileChangeSnapshotStore
from asagent.storage.reversible_files import (
    FileChangeConflictError,
    ReversibleFileService,
)
from asagent.workspace.resolver import WorkspaceResolver


class Repository:
    def __init__(self, *, fail_save: bool = False) -> None:
        self.changes: dict[FileChangeId, FileChange] = {}
        self.fail_save = fail_save

    async def get(self, file_change_id: FileChangeId) -> FileChange | None:
        return self.changes.get(file_change_id)

    async def list_for_run(self, run_id: RunId) -> tuple[FileChange, ...]:
        return tuple(
            change for change in self.changes.values() if change.run_id == run_id
        )

    async def save(self, file_change: FileChange) -> None:
        if self.fail_save:
            raise RuntimeError("database failed")
        self.changes[file_change.file_change_id] = file_change


def _service(
    workspace: Path,
    data_dir: Path,
    repository: Repository,
) -> ReversibleFileService:
    times = iter(
        (
            datetime(2026, 8, 15, 10, 0, tzinfo=UTC),
            datetime(2026, 8, 15, 10, 1, tzinfo=UTC),
        )
    )
    return ReversibleFileService(
        WorkspaceResolver(workspace_root=workspace),
        repository,
        FileChangeSnapshotStore(data_dir),
        lambda: FileChangeId("change-1"),
        lambda: next(times),
    )


@pytest.mark.asyncio
async def test_replaces_and_reverts_utf8_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "notes.txt"
    target.write_text("before", encoding="utf-8")
    repository = Repository()
    service = _service(workspace, tmp_path / "data", repository)

    change = await service.replace_text(
        run_id=RunId("run-1"), path=Path("notes.txt"), content="after"
    )
    assert target.read_text(encoding="utf-8") == "after"
    assert change.status is FileChangeStatus.APPLIED

    reverted = await service.revert(change.file_change_id)
    assert target.read_text(encoding="utf-8") == "before"
    assert reverted.status is FileChangeStatus.REVERTED
    assert reverted.updated_at == change.updated_at + timedelta(minutes=1)


@pytest.mark.asyncio
async def test_creates_and_reverts_utf8_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "created.txt"
    repository = Repository()
    service = _service(workspace, tmp_path / "data", repository)

    change = await service.create_text(
        run_id=RunId("run-1"), path=Path("created.txt"), content="created"
    )
    assert target.read_text(encoding="utf-8") == "created"
    assert change.operation is FileChangeOperation.CREATE
    assert change.snapshot_ref is None

    reverted = await service.revert(change.file_change_id)
    assert not target.exists()
    assert reverted.status is FileChangeStatus.REVERTED


@pytest.mark.asyncio
async def test_deletes_and_reverts_utf8_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "deleted.txt"
    target.write_text("deleted content", encoding="utf-8")
    repository = Repository()
    service = _service(workspace, tmp_path / "data", repository)

    change = await service.delete_file(run_id=RunId("run-1"), path=Path("deleted.txt"))
    assert not target.exists()
    assert change.operation is FileChangeOperation.DELETE
    assert change.snapshot_ref == "change-1.before"

    reverted = await service.revert(change.file_change_id)
    assert target.read_text(encoding="utf-8") == "deleted content"
    assert reverted.status is FileChangeStatus.REVERTED


@pytest.mark.asyncio
async def test_deletes_and_reverts_binary_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "installer.dmg"
    binary_data = b"\x00\xff\xfe\x00\x89PNG\r\n\x1a\n" + b"binary data" * 100
    target.write_bytes(binary_data)
    repository = Repository()
    service = _service(workspace, tmp_path / "data", repository)

    change = await service.delete_file(
        run_id=RunId("run-1"), path=Path("installer.dmg")
    )
    assert not target.exists()
    assert change.operation is FileChangeOperation.DELETE
    assert change.snapshot_ref == "change-1.before"

    reverted = await service.revert(change.file_change_id)
    assert target.read_bytes() == binary_data
    assert reverted.status is FileChangeStatus.REVERTED


@pytest.mark.asyncio
async def test_revert_detects_later_user_change(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "notes.txt"
    target.write_text("before", encoding="utf-8")
    repository = Repository()
    service = _service(workspace, tmp_path / "data", repository)
    change = await service.replace_text(
        run_id=RunId("run-1"), path=Path("notes.txt"), content="after"
    )
    target.write_text("user changed this", encoding="utf-8")

    with pytest.raises(FileChangeConflictError):
        await service.revert(change.file_change_id)

    assert target.read_text(encoding="utf-8") == "user changed this"
    assert (
        repository.changes[change.file_change_id].status is FileChangeStatus.CONFLICTED
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "delete"])
async def test_create_and_delete_reverts_detect_conflicts(
    tmp_path: Path,
    operation: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "notes.txt"
    repository = Repository()
    service = _service(workspace, tmp_path / "data", repository)

    if operation == "create":
        change = await service.create_text(
            run_id=RunId("run-1"), path=Path("notes.txt"), content="created"
        )
        target.write_text("changed later", encoding="utf-8")
    else:
        target.write_text("before delete", encoding="utf-8")
        change = await service.delete_file(
            run_id=RunId("run-1"), path=Path("notes.txt")
        )
        target.write_text("recreated later", encoding="utf-8")

    with pytest.raises(FileChangeConflictError):
        await service.revert(change.file_change_id)

    assert (
        repository.changes[change.file_change_id].status is FileChangeStatus.CONFLICTED
    )


@pytest.mark.asyncio
async def test_repository_failure_restores_original_and_removes_snapshot(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "notes.txt"
    target.write_text("before", encoding="utf-8")
    service = _service(workspace, tmp_path / "data", Repository(fail_save=True))

    with pytest.raises(RuntimeError, match="database failed"):
        await service.replace_text(
            run_id=RunId("run-1"), path=Path("notes.txt"), content="after"
        )

    assert target.read_text(encoding="utf-8") == "before"
    assert not (tmp_path / "data" / "file-changes" / "change-1.before").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "delete"])
async def test_create_and_delete_repository_failures_restore_disk(
    tmp_path: Path,
    operation: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "notes.txt"
    service = _service(workspace, tmp_path / "data", Repository(fail_save=True))

    if operation == "delete":
        target.write_text("before", encoding="utf-8")
        operation_call = service.delete_file(
            run_id=RunId("run-1"), path=Path("notes.txt")
        )
    else:
        operation_call = service.create_text(
            run_id=RunId("run-1"), path=Path("notes.txt"), content="created"
        )

    with pytest.raises(RuntimeError, match="database failed"):
        await operation_call

    if operation == "delete":
        assert target.read_text(encoding="utf-8") == "before"
        assert not (tmp_path / "data" / "file-changes" / "change-1.before").exists()
    else:
        assert not target.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "replace", "delete"])
async def test_revert_status_failure_restores_applied_disk_state(
    tmp_path: Path,
    operation: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "notes.txt"
    repository = Repository()
    service = _service(workspace, tmp_path / "data", repository)

    if operation == "create":
        change = await service.create_text(
            run_id=RunId("run-1"), path=Path("notes.txt"), content="created"
        )
        expected_content: str | None = "created"
    elif operation == "replace":
        target.write_text("before", encoding="utf-8")
        change = await service.replace_text(
            run_id=RunId("run-1"), path=Path("notes.txt"), content="after"
        )
        expected_content = "after"
    else:
        target.write_text("before delete", encoding="utf-8")
        change = await service.delete_file(
            run_id=RunId("run-1"), path=Path("notes.txt")
        )
        expected_content = None

    repository.fail_save = True
    with pytest.raises(RuntimeError, match="database failed"):
        await service.revert(change.file_change_id)

    if expected_content is None:
        assert not target.exists()
    else:
        assert target.read_text(encoding="utf-8") == expected_content


@pytest.mark.asyncio
async def test_rejects_files_outside_scope_and_non_utf8_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "binary.dat").write_bytes(b"\xff")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    service = _service(workspace, tmp_path / "data", Repository())

    with pytest.raises(ValueError, match="UTF-8"):
        await service.replace_text(
            run_id=RunId("run-1"), path=Path("binary.dat"), content="after"
        )
    with pytest.raises(ValueError, match="outside"):
        await service.replace_text(run_id=RunId("run-1"), path=outside, content="after")
