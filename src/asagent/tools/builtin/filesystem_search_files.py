import os
from collections.abc import Iterator, Mapping
from pathlib import Path

from asagent.core.tool_definition import ToolDefinition
from asagent.workspace.resolver import WorkspaceResolver


class FilesystemSearchFilesTool:
    """Searches authorized directories for matching file names or UTF-8 text."""

    _DEFAULT_MAX_RESULTS = 20
    _MAX_RESULTS = 20
    _MAX_FILES_SCANNED = 1000
    _MAX_FILE_BYTES = 64 * 1024
    _MAX_SNIPPET_CHARACTERS = 200

    def __init__(self, resolver: WorkspaceResolver) -> None:
        self._resolver = resolver

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="filesystem.search_files",
            display_name="Search files",
            description=(
                "Recursively searches authorized directories for a literal query "
                "in file names and UTF-8 text content. It scans at most 1000 "
                "files and reads at most 65536 bytes from each text file."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "minLength": 1,
                        "description": (
                            "Literal text to find in file names or UTF-8 text "
                            "content. Matching is case-insensitive."
                        ),
                    },
                    "path": {
                        "type": "string",
                        "description": (
                            "An authorized directory to search. When omitted, "
                            "searches all authorized workspace directories."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": self._MAX_RESULTS,
                        "description": ("Maximum matches to return. Defaults to 20."),
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"filesystem.read"}),
            requires_approval=False,
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        query = self._query_from(arguments)
        max_results = self._max_results_from(arguments)
        targets = self._targets_from(arguments)
        query_key = query.casefold()

        results: list[str] = []
        files_scanned = 0
        skipped_files = 0
        stopped_for_scan_limit = False
        stopped_for_result_limit = False

        for target in targets:
            for file_path, display_path in self._files_in_target(target):
                if files_scanned >= self._MAX_FILES_SCANNED:
                    stopped_for_scan_limit = True
                    break

                files_scanned += 1
                match, skipped = self._match_file(
                    file_path=file_path,
                    display_path=display_path,
                    query_key=query_key,
                )
                if skipped:
                    skipped_files += 1
                if match is not None:
                    results.append(match)

                if len(results) >= max_results:
                    stopped_for_result_limit = True
                    break

            if stopped_for_scan_limit or stopped_for_result_limit:
                break

        lines = [
            f"Searched {files_scanned} {'file' if files_scanned == 1 else 'files'}.",
        ]
        if results:
            lines.append(
                f"Found {len(results)} {'match' if len(results) == 1 else 'matches'}:",
            )
            lines.extend(results)
        else:
            lines.append(f'No matches for "{query}".')

        if skipped_files:
            lines.append(
                (
                    f"[Skipped {skipped_files} non-text, unreadable, or oversized "
                    f"{'file' if skipped_files == 1 else 'files'}.]"
                ),
            )
        if stopped_for_result_limit:
            lines.append(
                (
                    f"[Stopped after reaching max_results={max_results}. "
                    "Refine the query or search a specific path.]"
                ),
            )
        if stopped_for_scan_limit:
            lines.append(
                (
                    f"[Stopped after scanning {self._MAX_FILES_SCANNED} files. "
                    "Search a more specific path.]"
                ),
            )

        return "\n".join(lines)

    def _targets_from(self, arguments: Mapping[str, object]) -> tuple[Path, ...]:
        value = arguments.get("path")
        if value is None:
            return self._resolver.allowed_roots
        if not isinstance(value, str):
            raise ValueError("path must be a string")

        directory = self._resolver.resolve(Path(value))
        if not directory.exists():
            raise ValueError("directory does not exist")
        if not directory.is_dir():
            raise ValueError("path must resolve to a directory")

        return (directory,)

    @staticmethod
    def _query_from(arguments: Mapping[str, object]) -> str:
        value = arguments.get("query")
        if not isinstance(value, str):
            raise ValueError("query must be a string")

        query = value.strip()
        if not query:
            raise ValueError("query must not be blank")

        return query

    @classmethod
    def _max_results_from(cls, arguments: Mapping[str, object]) -> int:
        value = arguments.get("max_results", cls._DEFAULT_MAX_RESULTS)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("max_results must be an integer")
        if not 1 <= value <= cls._MAX_RESULTS:
            raise ValueError("max_results must be between 1 and 20")

        return value

    def _files_in_target(self, target: Path) -> Iterator[tuple[Path, str]]:
        for directory_path, directory_names, file_names in os.walk(
            target,
            followlinks=False,
        ):
            directory = Path(directory_path)
            directory_names[:] = sorted(
                name for name in directory_names if not (directory / name).is_symlink()
            )

            for name in sorted(file_names):
                file_path = directory / name
                if file_path.is_symlink():
                    continue

                try:
                    resolved = self._resolver.resolve(file_path)
                except ValueError:
                    continue

                if not resolved.is_file():
                    continue

                yield resolved, str(resolved.relative_to(target))

    def _match_file(
        self,
        *,
        file_path: Path,
        display_path: str,
        query_key: str,
    ) -> tuple[str | None, bool]:
        if query_key in file_path.name.casefold():
            return f"filename: {display_path}", False

        try:
            with file_path.open("rb") as file:
                contents = file.read(self._MAX_FILE_BYTES + 1)
        except OSError:
            return None, True

        if len(contents) > self._MAX_FILE_BYTES:
            return None, True

        try:
            text = contents.decode("utf-8")
        except UnicodeDecodeError:
            return None, True

        for line_number, line in enumerate(text.splitlines(), start=1):
            if query_key in line.casefold():
                return (
                    f"content: {display_path}:{line_number}: {self._snippet(line)}",
                    False,
                )

        return None, False

    @classmethod
    def _snippet(cls, line: str) -> str:
        normalized = " ".join(line.split())
        if len(normalized) <= cls._MAX_SNIPPET_CHARACTERS:
            return normalized
        return normalized[: cls._MAX_SNIPPET_CHARACTERS - 1] + "…"
