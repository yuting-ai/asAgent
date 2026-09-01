from datetime import UTC, datetime
from pathlib import Path

import pytest

from asagent.core.ids import LibraryId, SourceId
from asagent.knowledge.models import KnowledgeSource
from asagent.knowledge.source_watcher import KnowledgeSourceWatcher


def _source(root: Path) -> KnowledgeSource:
    now = datetime(2026, 8, 31, 16, 0, tzinfo=UTC)
    return KnowledgeSource(
        source_id=SourceId("source-watched"),
        library_id=LibraryId("library-watched"),
        display_path=str(root),
        canonical_path=str(root.resolve()),
        status="active",
        scan_status="ready",
        created_at=now,
        updated_at=now,
        last_scanned_at=now,
    )


@pytest.mark.asyncio
async def test_source_watcher_reconciles_startup_and_debounces_changes(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path)
    paper = tmp_path / "paper.pdf"
    paper.write_bytes(b"first version")
    clock_value = [0.0]
    notifications: list[SourceId] = []

    async def list_sources() -> tuple[KnowledgeSource, ...]:
        return (source,)

    async def on_changed(changed: KnowledgeSource) -> None:
        notifications.append(changed.source_id)

    watcher = KnowledgeSourceWatcher(
        list_sources=list_sources,
        on_source_changed=on_changed,
        debounce_seconds=1.5,
        clock=lambda: clock_value[0],
    )

    await watcher.poll_once()
    await watcher.poll_once()
    assert notifications == [source.source_id]

    paper.write_bytes(b"second and longer version")
    await watcher.poll_once()
    assert notifications == [source.source_id]

    clock_value[0] = 1.6
    await watcher.poll_once()
    assert notifications == [source.source_id, source.source_id]
