from collections import deque
from collections.abc import AsyncIterator, Iterable

from ragent.models.contracts import ModelEvent, ModelRequest, ModelResponse


class FakeModelProvider:
    def __init__(
        self,
        *,
        responses: Iterable[ModelResponse] = (),
        streams: Iterable[Iterable[ModelEvent]] = (),
    ) -> None:
        self._responses = deque(responses)
        self._streams = deque(tuple(events) for events in streams)
        self._requests: list[ModelRequest] = []

    @property
    def requests(self) -> tuple[ModelRequest, ...]:
        return tuple(self._requests)

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self._requests.append(request)

        if not self._responses:
            raise RuntimeError("no scripted response available")

        return self._responses.popleft()

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        self._requests.append(request)

        if not self._streams:
            raise RuntimeError("no scripted stream available")

        for event in self._streams.popleft():
            yield event
