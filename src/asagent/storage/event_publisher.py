from asagent.core.repositories import RunRepository
from asagent.core.run_event import RunEvent


class RepositoryEventPublisher:
    def __init__(self, repository: RunRepository) -> None:
        self._repository = repository

    async def publish(self, event: RunEvent) -> None:
        await self._repository.append_event(event)
