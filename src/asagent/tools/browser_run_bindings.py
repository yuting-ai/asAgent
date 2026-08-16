from threading import Lock

from asagent.core.ids import RunId


class BrowserRunBindings:
    """One-shot in-process map from Run ID to the Renderer tab for that Run."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._bindings: dict[RunId, str] = {}

    def bind(self, run_id: RunId, tab_id: str) -> None:
        tab = tab_id.strip()
        if not tab:
            raise ValueError("tab_id must not be blank")
        with self._lock:
            self._bindings[run_id] = tab

    def take(self, run_id: RunId) -> str | None:
        with self._lock:
            return self._bindings.pop(run_id, None)
