import os
import stat
import tempfile
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from asagent.core.file_change import FileChange, FileChangeOperation, FileChangeStatus
from asagent.core.ids import FileChangeId, RunId
from asagent.core.repositories import FileChangeRepository
from asagent.storage.file_change_snapshots import FileChangeSnapshotStore
from asagent.workspace.resolver import WorkspaceResolver


class FileChangeConflictError(RuntimeError):
    """Raised when a recorded change no longer matches the current file."""


class FileChangeNotFoundError(LookupError):
    """Raised when a requested FileChange does not exist."""


class ReversibleFileService:
    """Applies and safely reverts small authorized UTF-8 file changes."""

    max_content_bytes = 64 * 1024

    def __init__(
        self,
        resolver: WorkspaceResolver,
        repository: FileChangeRepository,
        snapshots: FileChangeSnapshotStore,
        change_id_factory: Callable[[], FileChangeId],
        clock: Callable[[], datetime],
    ) -> None:
        self._resolver = resolver
        self._repository = repository
        self._snapshots = snapshots
        self._change_id_factory = change_id_factory
        self._clock = clock

    async def create_text(
        self,
        *,
        run_id: RunId,
        path: Path,
        content: str,
    ) -> FileChange:
        target = self._resolver.resolve(path)
        if target.exists():
            raise ValueError("path already exists")
        if not target.parent.is_dir():
            raise ValueError("parent directory does not exist")
        after = self._encode_content(content)
        root, relative = self._path_metadata(target)
        now = self._clock()
        change = FileChange(
            file_change_id=self._change_id_factory(),
            run_id=run_id,
            operation=FileChangeOperation.CREATE,
            status=FileChangeStatus.APPLIED,
            root_path=str(root),
            relative_path=relative.as_posix(),
            before_hash=None,
            after_hash=_hash(after),
            snapshot_ref=None,
            created_at=now,
            updated_at=now,
        )

        self._exclusive_create(target, after)
        if _hash(target.read_bytes()) != change.after_hash:
            target.unlink(missing_ok=True)
            raise RuntimeError("creation hash verification failed")
        try:
            await self._repository.save(change)
        except Exception:
            if target.is_file() and _hash(target.read_bytes()) == change.after_hash:
                target.unlink()
            raise
        return change

    async def replace_text(
        self,
        *,
        run_id: RunId,
        path: Path,
        content: str,
    ) -> FileChange:
        target = self._resolver.resolve(path)
        before = self._read_utf8_file(target)
        after = self._encode_content(content)
        change_id = self._change_id_factory()
        snapshot_ref = self._snapshots.save(change_id, before)
        root, relative = self._path_metadata(target)
        now = self._clock()
        change = FileChange(
            file_change_id=change_id,
            run_id=run_id,
            operation=FileChangeOperation.REPLACE,
            status=FileChangeStatus.APPLIED,
            root_path=str(root),
            relative_path=relative.as_posix(),
            before_hash=_hash(before),
            after_hash=_hash(after),
            snapshot_ref=snapshot_ref,
            created_at=now,
            updated_at=now,
        )

        self._atomic_replace(target, after)
        if _hash(target.read_bytes()) != change.after_hash:
            self._atomic_replace(target, before)
            self._snapshots.delete(snapshot_ref)
            raise RuntimeError("replacement hash verification failed")

        try:
            await self._repository.save(change)
        except Exception:
            self._atomic_replace(target, before)
            self._snapshots.delete(snapshot_ref)
            raise
        return change

    async def delete_file(
        self,
        *,
        run_id: RunId,
        path: Path,
    ) -> FileChange:
        target = self._resolver.resolve(path)
        before = self._read_utf8_file(target)
        change_id = self._change_id_factory()
        snapshot_ref = self._snapshots.save(change_id, before)
        root, relative = self._path_metadata(target)
        now = self._clock()
        change = FileChange(
            file_change_id=change_id,
            run_id=run_id,
            operation=FileChangeOperation.DELETE,
            status=FileChangeStatus.APPLIED,
            root_path=str(root),
            relative_path=relative.as_posix(),
            before_hash=_hash(before),
            after_hash=None,
            snapshot_ref=snapshot_ref,
            created_at=now,
            updated_at=now,
        )

        if _hash(target.read_bytes()) != change.before_hash:
            self._snapshots.delete(snapshot_ref)
            raise FileChangeConflictError("file changed while deletion was prepared")
        target.unlink()
        if target.exists():
            self._snapshots.delete(snapshot_ref)
            raise RuntimeError("file deletion verification failed")
        try:
            await self._repository.save(change)
        except Exception:
            self._exclusive_create(target, before)
            self._snapshots.delete(snapshot_ref)
            raise
        return change

    async def revert(
        self,
        file_change_id: FileChangeId,
        *,
        expected_path: Path | None = None,
    ) -> FileChange:
        change = await self._repository.get(file_change_id)
        if change is None:
            raise FileChangeNotFoundError(f"file change not found: {file_change_id}")
        if change.status is not FileChangeStatus.APPLIED:
            raise ValueError("only applied file changes can be reverted")

        target = self._resolver.resolve(
            Path(change.root_path) / Path(change.relative_path)
        )
        if expected_path is not None:
            approved_target = self._resolver.resolve(expected_path)
            if approved_target != target:
                raise ValueError(
                    "approved path does not match the recorded file change"
                )
        applied_content = target.read_bytes() if target.is_file() else None
        if change.operation is FileChangeOperation.CREATE:
            await self._revert_create(change, target)
        elif change.operation is FileChangeOperation.REPLACE:
            await self._revert_replace(change, target)
        else:
            await self._revert_delete(change, target)
        reverted = replace(
            change,
            status=FileChangeStatus.REVERTED,
            updated_at=self._clock(),
        )
        try:
            await self._repository.save(reverted)
        except Exception:
            self._restore_applied_state(change, target, applied_content)
            raise
        return reverted

    async def _revert_create(self, change: FileChange, target: Path) -> None:
        if not target.is_file() or _hash(target.read_bytes()) != change.after_hash:
            await self._conflict(change, "created file changed after it was recorded")
        target.unlink()
        if target.exists():
            raise RuntimeError("created file could not be removed")

    async def _revert_replace(self, change: FileChange, target: Path) -> None:
        if not target.is_file() or _hash(target.read_bytes()) != change.after_hash:
            await self._conflict(change, "file changed after the recorded replacement")
        before = self._snapshot(change)
        self._atomic_replace(target, before)
        if _hash(target.read_bytes()) != change.before_hash:
            raise RuntimeError("replacement revert hash verification failed")

    async def _revert_delete(self, change: FileChange, target: Path) -> None:
        if target.exists():
            await self._conflict(change, "deleted path was recreated after deletion")
        before = self._snapshot(change)
        self._exclusive_create(target, before)
        if _hash(target.read_bytes()) != change.before_hash:
            raise RuntimeError("deletion revert hash verification failed")

    def _restore_applied_state(
        self,
        change: FileChange,
        target: Path,
        applied_content: bytes | None,
    ) -> None:
        if change.operation is FileChangeOperation.CREATE:
            if applied_content is None:
                raise RuntimeError(
                    "created file content was unavailable for compensation"
                )
            self._exclusive_create(target, applied_content)
        elif change.operation is FileChangeOperation.REPLACE:
            if applied_content is None:
                raise RuntimeError(
                    "replacement content was unavailable for compensation"
                )
            self._atomic_replace(target, applied_content)
        elif target.is_file() and _hash(target.read_bytes()) == change.before_hash:
            target.unlink()

    async def _conflict(self, change: FileChange, message: str) -> None:
        await self._repository.save(
            replace(
                change,
                status=FileChangeStatus.CONFLICTED,
                updated_at=self._clock(),
            )
        )
        raise FileChangeConflictError(message)

    def _snapshot(self, change: FileChange) -> bytes:
        if change.snapshot_ref is None:
            raise RuntimeError("file change is missing its snapshot reference")
        before = self._snapshots.read(change.snapshot_ref)
        if _hash(before) != change.before_hash:
            raise RuntimeError("file change snapshot hash does not match metadata")
        return before

    def _path_metadata(self, target: Path) -> tuple[Path, Path]:
        for root in sorted(
            self._resolver.allowed_roots,
            key=lambda candidate: len(candidate.parts),
            reverse=True,
        ):
            try:
                return root, target.relative_to(root)
            except ValueError:
                continue
        if target in self._resolver.allowed_files:
            return target.parent, Path(target.name)
        raise ValueError("target is not represented by an authorized root or file")

    def _read_utf8_file(self, target: Path) -> bytes:
        if not target.exists():
            raise ValueError("path must resolve to an existing file")
        if not target.is_file():
            raise ValueError("path must resolve to a regular file")
        content = target.read_bytes()
        if len(content) > self.max_content_bytes:
            raise ValueError("file exceeds the 65536 byte replace limit")
        try:
            content.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise ValueError("file must contain valid UTF-8 text") from error
        return content

    def _encode_content(self, content: str) -> bytes:
        try:
            encoded = content.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise ValueError("content must be valid UTF-8 text") from error
        if len(encoded) > self.max_content_bytes:
            raise ValueError("content exceeds the 65536 byte replace limit")
        return encoded

    @staticmethod
    def _atomic_replace(target: Path, content: bytes) -> None:
        mode = stat.S_IMODE(target.stat().st_mode)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".asagent-tmp",
            dir=target.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            temporary.chmod(mode)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _exclusive_create(target: Path, content: bytes) -> None:
        try:
            with target.open("xb") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
        except FileExistsError as error:
            raise FileChangeConflictError(
                "path was created before the operation"
            ) from error


def _hash(content: bytes) -> str:
    return sha256(content).hexdigest()
