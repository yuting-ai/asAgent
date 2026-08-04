from typing import Protocol, runtime_checkable

from ragent.core.run_event import RunEvent


@runtime_checkable
class EventPublisher(Protocol):
    async def publish(self, event: RunEvent) -> None: ...
