from pathlib import Path

from asagent.core.ids import FileChangeId


class FileChangeSnapshotStore:
    """Private, bounded storage for FileChange pre-operation snapshots."""

    max_snapshot_bytes = 20 * 1024 * 1024
    max_total_bytes = 200 * 1024 * 1024

    def __init__(self, data_dir: Path) -> None:
        self._root = data_dir / "file-changes"

    def save(self, file_change_id: FileChangeId, content: bytes) -> str:
        if len(content) > self.max_snapshot_bytes:
            raise ValueError("snapshot exceeds the 20 MiB limit")
        self._root.mkdir(parents=True, exist_ok=True)
        snapshot_path = self._root / f"{file_change_id}.before"
        total_size = sum(
            path.stat().st_size for path in self._root.iterdir() if path.is_file()
        )
        if total_size + len(content) > self.max_total_bytes:
            raise ValueError("snapshot storage exceeds the 200 MiB limit")
        try:
            with snapshot_path.open("xb") as snapshot:
                snapshot.write(content)
        except FileExistsError as error:
            raise ValueError("snapshot already exists") from error
        return snapshot_path.name

    def read(self, snapshot_ref: str) -> bytes:
        return self._path_for(snapshot_ref).read_bytes()

    def delete(self, snapshot_ref: str) -> bool:
        path = self._path_for(snapshot_ref)
        if not path.exists():
            return False
        path.unlink()
        return True

    def get_usage(self) -> tuple[int, int]:
        """Return (total_bytes, snapshot_count) for all stored snapshots."""
        if not self._root.exists():
            return 0, 0
        total_size = 0
        count = 0
        for path in self._root.iterdir():
            if path.is_file():
                total_size += path.stat().st_size
                count += 1
        return total_size, count

    def clear(self) -> tuple[int, int]:
        """Delete all stored snapshots. Return (freed_bytes, deleted_count)."""
        if not self._root.exists():
            return 0, 0
        freed = 0
        count = 0
        for path in list(self._root.iterdir()):
            if path.is_file():
                try:
                    freed += path.stat().st_size
                    path.unlink()
                    count += 1
                except OSError:
                    continue
        return freed, count

    def prune(self, max_age_days: int) -> int:
        """Delete snapshots older than max_age_days. Return pruned count."""
        if max_age_days <= 0 or not self._root.exists():
            return 0
        import time

        cutoff = time.time() - (max_age_days * 86400)
        pruned_count = 0
        for path in list(self._root.iterdir()):
            if path.is_file():
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                        pruned_count += 1
                except OSError:
                    continue
        return pruned_count

    def _path_for(self, snapshot_ref: str) -> Path:
        path = self._root / snapshot_ref
        if not snapshot_ref or path.parent != self._root:
            raise ValueError("snapshot reference must name one private snapshot file")
        return path
