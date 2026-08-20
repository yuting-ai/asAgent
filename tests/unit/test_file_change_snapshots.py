from pathlib import Path

import pytest

from asagent.core.ids import FileChangeId
from asagent.storage.file_change_snapshots import FileChangeSnapshotStore


def test_saves_reads_and_deletes_private_snapshot(tmp_path: Path) -> None:
    store = FileChangeSnapshotStore(tmp_path / "data")
    ref = store.save(FileChangeId("change-1"), b"before")
    assert ref == "change-1.before"
    assert store.read(ref) == b"before"
    assert store.delete(ref) is True
    assert store.delete(ref) is False


def test_rejects_oversized_snapshot(tmp_path: Path) -> None:
    store = FileChangeSnapshotStore(tmp_path)
    with pytest.raises(ValueError, match="20 MiB"):
        store.save(FileChangeId("change-1"), b"x" * (store.max_snapshot_bytes + 1))


def test_rejects_snapshot_reference_escape(tmp_path: Path) -> None:
    store = FileChangeSnapshotStore(tmp_path)
    with pytest.raises(ValueError, match="private snapshot"):
        store.read("../outside")
