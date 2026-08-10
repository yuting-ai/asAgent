from dataclasses import dataclass
from pathlib import Path


class WorkspacePathOutsideAllowedRootsError(ValueError):
    """Raised when a path resolves outside every allowed filesystem root."""


@dataclass(frozen=True, slots=True)
class WorkspaceResolver:
    """Resolves paths while enforcing the configured workspace boundaries."""

    workspace_root: Path
    additional_roots: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        workspace_root = self._resolve_root(
            self.workspace_root,
            field_name="workspace_root",
        )
        additional_roots = tuple(
            self._resolve_root(
                root,
                field_name="additional_roots",
            )
            for root in self.additional_roots
        )

        object.__setattr__(self, "workspace_root", workspace_root)
        object.__setattr__(
            self,
            "additional_roots",
            tuple(
                root
                for index, root in enumerate(additional_roots)
                if root != workspace_root and root not in additional_roots[:index]
            ),
        )

    @property
    def allowed_roots(self) -> tuple[Path, ...]:
        return (self.workspace_root, *self.additional_roots)

    def resolve(self, path: Path) -> Path:
        candidate = path if path.is_absolute() else self.workspace_root / path
        resolved = candidate.resolve(strict=False)

        if any(self._is_within(resolved, root) for root in self.allowed_roots):
            return resolved

        raise WorkspacePathOutsideAllowedRootsError(
            "path resolves outside the allowed workspace roots",
        )

    @staticmethod
    def _resolve_root(path: Path, *, field_name: str) -> Path:
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError as error:
            raise ValueError(f"{field_name} must exist") from error

        if not resolved.is_dir():
            raise ValueError(f"{field_name} must be a directory")

        return resolved

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True
