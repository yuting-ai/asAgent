import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from asagent.knowledge.models import DocumentFileType

IGNORED_DIR_NAMES = {
    ".git",
    ".svn",
    ".hg",
    ".venv",
    "venv",
    "env",
    ".env",
    "__pycache__",
    "node_modules",
    "target",
    "build",
    "dist",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

MAX_DEFAULT_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MiB

EXTENSION_TO_FILE_TYPE: dict[str, DocumentFileType] = {
    ".pdf": "pdf",
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".text": "text",
    ".rst": "text",
    ".docx": "docx",
    ".html": "html",
    ".htm": "html",
}


@dataclass(frozen=True, slots=True)
class ScannedFile:
    """A file discovered during local source directory scanning."""

    relative_path: str
    absolute_path: Path
    file_type: DocumentFileType
    size_bytes: int
    mtime_ns: int
    content_hash: str


SourceTreeSignature = tuple[tuple[str, int, int], ...]


def _iter_supported_files(
    root_dir: Path,
    *,
    max_file_size_bytes: int,
) -> Iterator[tuple[Path, tuple[str, ...], DocumentFileType, int, int]]:
    resolved_root = root_dir.expanduser().resolve()
    if not resolved_root.exists() or not resolved_root.is_dir():
        raise ValueError(f"Root path is not an existing directory: {root_dir}")

    for path in sorted(resolved_root.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(resolved_root).parts
        if any(part.startswith(".") or part in IGNORED_DIR_NAMES for part in rel_parts):
            continue
        if path.is_symlink():
            try:
                if not path.resolve().is_relative_to(resolved_root):
                    continue
            except (OSError, ValueError):
                continue
        file_type = EXTENSION_TO_FILE_TYPE.get(path.suffix.lower())
        if file_type is None:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_size > max_file_size_bytes or stat.st_size == 0:
            continue
        yield path, rel_parts, file_type, stat.st_size, stat.st_mtime_ns


def compute_file_sha256(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file in streaming chunks."""
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def scan_directory(
    root_dir: Path,
    *,
    max_file_size_bytes: int = MAX_DEFAULT_FILE_SIZE_BYTES,
) -> tuple[ScannedFile, ...]:
    """Recursively scan a directory for supported document files, ignoring hidden and system files."""
    scanned: list[ScannedFile] = []
    for path, rel_parts, file_type, size_bytes, mtime_ns in _iter_supported_files(
        root_dir,
        max_file_size_bytes=max_file_size_bytes,
    ):
        try:
            content_hash = compute_file_sha256(path)
        except OSError:
            continue

        relative_path_str = "/".join(rel_parts)
        scanned.append(
            ScannedFile(
                relative_path=relative_path_str,
                absolute_path=path,
                file_type=file_type,
                size_bytes=size_bytes,
                mtime_ns=mtime_ns,
                content_hash=content_hash,
            )
        )

    return tuple(scanned)


def scan_source_signature(
    root_dir: Path,
    *,
    max_file_size_bytes: int = MAX_DEFAULT_FILE_SIZE_BYTES,
) -> SourceTreeSignature:
    """Return a cheap recursive metadata signature for supported source files."""
    return tuple(
        ("/".join(rel_parts), size_bytes, mtime_ns)
        for _path, rel_parts, _file_type, size_bytes, mtime_ns in _iter_supported_files(
            root_dir,
            max_file_size_bytes=max_file_size_bytes,
        )
    )
