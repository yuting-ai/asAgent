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


def test_snapshots_usage_clear_and_prune(tmp_path: Path) -> None:
    import os
    import time

    store = FileChangeSnapshotStore(tmp_path / "data")
    assert store.get_usage() == (0, 0)
    assert store.clear() == (0, 0)
    assert store.prune(7) == 0

    ref1 = store.save(FileChangeId("c1"), b"hello")
    ref2 = store.save(FileChangeId("c2"), b"world123")
    assert ref2 == "c2.before"
    total_bytes, count = store.get_usage()
    assert total_bytes == 13
    assert count == 2

    # Set c1 to 10 days ago
    path1 = tmp_path / "data" / "file-changes" / ref1
    old_time = time.time() - (10 * 86400)
    os.utime(path1, (old_time, old_time))

    # Prune 7 days
    pruned = store.prune(7)
    assert pruned == 1
    total_bytes, count = store.get_usage()
    assert total_bytes == 8
    assert count == 1

    # Clear all
    freed, deleted = store.clear()
    assert freed == 8
    assert deleted == 1
    assert store.get_usage() == (0, 0)
