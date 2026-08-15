from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from asagent.core.ids import FileChangeId, RunId


class FileChangeOperation(StrEnum):
    CREATE = "create"
    REPLACE = "replace"
    DELETE = "delete"


class FileChangeStatus(StrEnum):
    PREPARED = "prepared"
    APPLIED = "applied"
    REVERTED = "reverted"
    CONFLICTED = "conflicted"


@dataclass(frozen=True, slots=True)
class FileChange:
    """Metadata for one reversible filesystem change initiated by asAgent."""

    file_change_id: FileChangeId
    run_id: RunId
    operation: FileChangeOperation
    status: FileChangeStatus
    root_path: str
    relative_path: str
    before_hash: str | None
    after_hash: str | None
    snapshot_ref: str | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.root_path:
            raise ValueError("root_path must not be empty")
        if not self.relative_path:
            raise ValueError("relative_path must not be empty")

        if self.operation is FileChangeOperation.CREATE:
            if self.before_hash is not None or self.snapshot_ref is not None:
                raise ValueError("create changes cannot have a before hash or snapshot")
            if self.after_hash is None:
                raise ValueError("create changes require an after hash")
        elif self.operation is FileChangeOperation.REPLACE:
            if self.before_hash is None or self.after_hash is None:
                raise ValueError("replace changes require before and after hashes")
            if self.snapshot_ref is None:
                raise ValueError("replace changes require a snapshot")
        elif self.operation is FileChangeOperation.DELETE:
            if self.before_hash is None:
                raise ValueError("delete changes require a before hash")
            if self.after_hash is not None:
                raise ValueError("delete changes cannot have an after hash")
            if self.snapshot_ref is None:
                raise ValueError("delete changes require a snapshot")
