from dataclasses import dataclass
from pathlib import Path


class WorkspacePathOutsideAllowedRootsError(ValueError):
    """Raised when a path resolves outside every allowed filesystem root."""


@dataclass(frozen=True, slots=True)
class WorkspaceResolver:
    """Resolves paths while enforcing the configured workspace boundaries."""

    workspace_root: Path
    additional_roots: tuple[Path, ...] = ()
    additional_files: tuple[Path, ...] = ()

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
        additional_files = tuple(
            self._resolve_file(
                file_path,
                field_name="additional_files",
            )
            for file_path in self.additional_files
        )
        normalized_roots = tuple(
            root
            for index, root in enumerate(additional_roots)
            if root != workspace_root and root not in additional_roots[:index]
        )
        allowed_roots = (workspace_root, *normalized_roots)

        object.__setattr__(self, "workspace_root", workspace_root)
        object.__setattr__(self, "additional_roots", normalized_roots)
        object.__setattr__(
            self,
            "additional_files",
            tuple(
                file_path
                for index, file_path in enumerate(additional_files)
                if file_path not in additional_files[:index]
                and not any(self._is_within(file_path, root) for root in allowed_roots)
            ),
        )

    @property
    def allowed_roots(self) -> tuple[Path, ...]:
        return (self.workspace_root, *self.additional_roots)

    @property
    def allowed_files(self) -> tuple[Path, ...]:
        return self.additional_files

    def resolve(self, path: Path) -> Path:
        candidate = path if path.is_absolute() else self.workspace_root / path
        resolved = candidate.resolve(strict=False)

        if (
            any(self._is_within(resolved, root) for root in self.allowed_roots)
            or resolved in self.allowed_files
        ):
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
    def _resolve_file(path: Path, *, field_name: str) -> Path:
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError as error:
            raise ValueError(f"{field_name} must exist") from error

        if not resolved.is_file():
            raise ValueError(f"{field_name} must be a file")

        return resolved

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True
