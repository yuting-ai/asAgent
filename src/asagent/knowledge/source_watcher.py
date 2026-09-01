import asyncio
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from time import monotonic

from asagent.core.ids import SourceId
from asagent.knowledge.models import KnowledgeSource
from asagent.knowledge.scanner import SourceTreeSignature, scan_source_signature


class KnowledgeSourceWatcher:
    """Poll active source metadata and debounce incremental indexing callbacks."""

    def __init__(
        self,
        *,
        list_sources: Callable[[], Awaitable[Sequence[KnowledgeSource]]],
        on_source_changed: Callable[[KnowledgeSource], Awaitable[None]],
        poll_interval_seconds: float = 2.0,
        debounce_seconds: float = 1.5,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._list_sources = list_sources
        self._on_source_changed = on_source_changed
        self._poll_interval_seconds = poll_interval_seconds
        self._debounce_seconds = debounce_seconds
        self._clock = clock
        self._signatures: dict[SourceId, SourceTreeSignature | None] = {}
        self._pending_since: dict[SourceId, float] = {}
        self._has_polled = False

    async def poll_once(self) -> None:
        reconcile_existing_sources = not self._has_polled
        sources = tuple(
            source for source in await self._list_sources() if source.status == "active"
        )
        active_ids = {source.source_id for source in sources}
        for source_id in tuple(self._signatures):
            if source_id not in active_ids:
                self._signatures.pop(source_id, None)
                self._pending_since.pop(source_id, None)

        for source in sources:
            try:
                signature: SourceTreeSignature | None = await asyncio.to_thread(
                    scan_source_signature,
                    Path(source.canonical_path),
                )
            except (OSError, ValueError):
                signature = None

            if source.source_id not in self._signatures:
                self._signatures[source.source_id] = signature
                if reconcile_existing_sources:
                    await self._notify(source)
                continue

            if signature != self._signatures[source.source_id]:
                self._signatures[source.source_id] = signature
                self._pending_since[source.source_id] = self._clock()
                continue

            pending_since = self._pending_since.get(source.source_id)
            if (
                pending_since is not None
                and self._clock() - pending_since >= self._debounce_seconds
            ):
                self._pending_since.pop(source.source_id, None)
                await self._notify(source)
        self._has_polled = True

    async def run(self) -> None:
        while True:
            await self.poll_once()
            await asyncio.sleep(self._poll_interval_seconds)

    async def _notify(self, source: KnowledgeSource) -> None:
        try:
            await self._on_source_changed(source)
        except Exception:
            # A failed or already-running job is reflected by persisted source/job state;
            # the watcher must remain alive for other sources and later changes.
            return
