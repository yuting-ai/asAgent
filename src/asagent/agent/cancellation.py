from dataclasses import dataclass, field

from asagent.core.ids import RunId


@dataclass(slots=True)
class RunCancellationToken:
    run_id: RunId
    _cancelled: bool = field(default=False, init=False, repr=False)

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled
