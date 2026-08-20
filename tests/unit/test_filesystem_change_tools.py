import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from asagent.core.file_change import FileChange
from asagent.core.ids import FileChangeId, RunId
from asagent.storage.file_change_snapshots import FileChangeSnapshotStore
from asagent.storage.reversible_files import ReversibleFileService
from asagent.tools.builtin.filesystem_changes import (
    FilesystemCreateFileTool,
    FilesystemDeleteFileTool,
    FilesystemReplaceFileTool,
)
from asagent.workspace.resolver import WorkspaceResolver


class MemoryFileChanges:
    def __init__(self) -> None:
        self.items: dict[FileChangeId, FileChange] = {}

    async def get(self, file_change_id: FileChangeId) -> FileChange | None:
        return self.items.get(file_change_id)

    async def list_for_run(self, run_id: RunId) -> tuple[FileChange, ...]:
        return tuple(
            change for change in self.items.values() if change.run_id == run_id
        )

    async def save(self, file_change: FileChange) -> None:
        self.items[file_change.file_change_id] = file_change


@pytest.mark.asyncio
async def test_filesystem_change_tools_apply_reversible_run_linked_changes(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    existing = workspace / "existing.txt"
    existing.write_text("before", encoding="utf-8")
    repository = MemoryFileChanges()
    ids = iter(
        (FileChangeId("create-1"), FileChangeId("replace-1"), FileChangeId("delete-1"))
    )
    service = ReversibleFileService(
        WorkspaceResolver(workspace_root=workspace),
        repository,
        FileChangeSnapshotStore(tmp_path / "data"),
        lambda: next(ids),
        lambda: datetime(2026, 8, 15, 14, 0, tzinfo=UTC),
    )
    run_id = RunId("run-1")
    create = FilesystemCreateFileTool(service, run_id)
    replace = FilesystemReplaceFileTool(service, run_id)
    delete = FilesystemDeleteFileTool(service, run_id)

    assert {tool.definition.tool_id for tool in (create, replace, delete)} == {
        "filesystem.create_file",
        "filesystem.replace_file",
        "filesystem.delete_file",
    }
    assert all(
        tool.definition.required_permissions == frozenset({"filesystem.write"})
        for tool in (create, replace, delete)
    )
    assert create.definition.requires_approval is True
    assert replace.definition.requires_approval is True
    assert delete.definition.requires_approval is False

    created = json.loads(
        await create.execute({"path": str(workspace / "created.txt"), "content": "new"})
    )
    replaced = json.loads(
        await replace.execute({"path": str(existing), "content": "after"})
    )
    deleted = json.loads(await delete.execute({"path": str(existing)}))

    assert [created["change_id"], replaced["change_id"], deleted["change_id"]] == [
        "create-1",
        "replace-1",
        "delete-1",
    ]
    assert len(await repository.list_for_run(run_id)) == 3
    assert (workspace / "created.txt").read_text(encoding="utf-8") == "new"
    assert not existing.exists()
