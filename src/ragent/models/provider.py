from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from ragent.models.contracts import ModelEvent, ModelRequest, ModelResponse


@runtime_checkable
class ModelProvider(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse: ...

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]: ...
