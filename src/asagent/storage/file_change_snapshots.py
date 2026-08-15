from pathlib import Path

from asagent.core.ids import FileChangeId


class FileChangeSnapshotStore:
    """Private, bounded storage for FileChange pre-operation snapshots."""

    max_snapshot_bytes = 5 * 1024 * 1024
    max_total_bytes = 100 * 1024 * 1024

    def __init__(self, data_dir: Path) -> None:
        self._root = data_dir / "file-changes"

    def save(self, file_change_id: FileChangeId, content: bytes) -> str:
        if len(content) > self.max_snapshot_bytes:
            raise ValueError("snapshot exceeds the 5 MiB limit")
        self._root.mkdir(parents=True, exist_ok=True)
        snapshot_path = self._root / f"{file_change_id}.before"
        total_size = sum(
            path.stat().st_size for path in self._root.iterdir() if path.is_file()
        )
        if total_size + len(content) > self.max_total_bytes:
            raise ValueError("snapshot storage exceeds the 100 MiB limit")
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

    def _path_for(self, snapshot_ref: str) -> Path:
        path = self._root / snapshot_ref
        if not snapshot_ref or path.parent != self._root:
            raise ValueError("snapshot reference must name one private snapshot file")
        return path
