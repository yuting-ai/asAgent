import json
from dataclasses import dataclass
from pathlib import Path

from asagent.workspace.resolver import WorkspaceResolver

_CONFIGURATION_FILE_NAME = "workspace.json"


class WorkspaceSettingsConfigurationError(RuntimeError):
    """Raised when the saved workspace scope configuration is unusable."""


@dataclass(frozen=True, slots=True)
class WorkspaceSettingsStatus:
    workspace_root: Path
    additional_roots: tuple[Path, ...]


class WorkspaceSettings:
    """Persists the user-selected filesystem roots without reading their contents."""

    def __init__(self, *, config_dir: Path, workspace_root: Path) -> None:
        self._config_dir = config_dir
        self._workspace_root = workspace_root

    def get_status(self) -> WorkspaceSettingsStatus:
        additional_roots = self._load_additional_roots()
        return WorkspaceSettingsStatus(
            workspace_root=self._workspace_root.resolve(strict=False),
            additional_roots=additional_roots,
        )

    def save(self, *, additional_roots: tuple[Path, ...]) -> WorkspaceSettingsStatus:
        resolver = WorkspaceResolver(
            workspace_root=self._workspace_root,
            additional_roots=additional_roots,
        )
        saved_roots = resolver.additional_roots
        self._config_dir.mkdir(parents=True, exist_ok=True)
        configuration_path = self._configuration_path
        temporary_path = configuration_path.with_suffix(".json.tmp")
        serialized = (
            json.dumps(
                {"additional_roots": [str(root) for root in saved_roots]},
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )

        try:
            temporary_path.write_text(serialized, encoding="utf-8")
            temporary_path.replace(configuration_path)
        except OSError as error:
            raise WorkspaceSettingsConfigurationError(
                "workspace settings file is unavailable",
            ) from error
        finally:
            temporary_path.unlink(missing_ok=True)

        return WorkspaceSettingsStatus(
            workspace_root=resolver.workspace_root,
            additional_roots=saved_roots,
        )

    @property
    def _configuration_path(self) -> Path:
        return self._config_dir / _CONFIGURATION_FILE_NAME

    def _load_additional_roots(self) -> tuple[Path, ...]:
        try:
            serialized = self._configuration_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ()
        except OSError as error:
            raise WorkspaceSettingsConfigurationError(
                "workspace settings file is unavailable",
            ) from error

        try:
            payload: object = json.loads(serialized)
        except json.JSONDecodeError as error:
            raise WorkspaceSettingsConfigurationError(
                "workspace settings are invalid JSON",
            ) from error

        if not isinstance(payload, dict) or set(payload) != {"additional_roots"}:
            raise WorkspaceSettingsConfigurationError("workspace settings are invalid")
        roots = payload["additional_roots"]
        if not isinstance(roots, list) or any(
            not isinstance(root, str) or not Path(root).is_absolute() for root in roots
        ):
            raise WorkspaceSettingsConfigurationError("workspace settings are invalid")

        return tuple(Path(root) for root in roots)
