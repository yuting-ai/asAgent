from collections.abc import Mapping
from pathlib import Path

from asagent.core.tool_definition import ToolDefinition
from asagent.workspace.resolver import WorkspaceResolver


class FilesystemListTool:
    """Lists one authorized directory level without reading file contents."""

    _DEFAULT_MAX_ENTRIES = 50
    _MAX_ENTRIES = 100

    def __init__(self, resolver: WorkspaceResolver) -> None:
        self._resolver = resolver

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="filesystem.list",
            display_name="List files",
            description=(
                "Lists files, directories, and symbolic links in one authorized "
                "directory without reading file contents. "
                "Path must resolve to a directory, not a file."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "A path inside an authorized workspace root. "
                            "Defaults to the workspace root."
                        ),
                    },
                    "max_entries": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": self._MAX_ENTRIES,
                        "description": (
                            "Maximum number of directory entries to return. "
                            "Defaults to 50."
                        ),
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 0,
                        "description": (
                            "Number of sorted directory entries to skip before "
                            "returning a page. Defaults to 0."
                        ),
                    },
                },
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"filesystem.read"}),
            requires_approval=False,
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        path = self._path_from(arguments)
        max_entries = self._max_entries_from(arguments)
        offset = self._offset_from(arguments)
        directory = self._resolver.resolve(path)

        if not directory.exists():
            raise ValueError("directory does not exist")
        if not directory.is_dir():
            raise ValueError("path must resolve to a directory")

        try:
            entries = sorted(directory.iterdir(), key=lambda entry: entry.name)
        except OSError as error:
            raise ValueError("directory cannot be listed") from error

        if not entries:
            return "Directory is empty."

        page = entries[offset : offset + max_entries]
        if not page:
            return (
                f"Directory contains {len(entries)} entries. "
                f"No entries at offset {offset}."
            )

        lines = [
            (
                f"Directory contains {len(entries)} entries. "
                f"Showing {offset + 1}-{offset + len(page)}:"
            ),
            *[f"{self._entry_kind(entry)}: {entry.name}" for entry in page],
        ]
        remaining_entries = len(entries) - (offset + len(page))
        if remaining_entries:
            lines.append(
                (
                    f"[{remaining_entries} additional "
                    f"{'entry' if remaining_entries == 1 else 'entries'} "
                    f"available. Call again with offset={offset + len(page)}.]"
                ),
            )

        return "\n".join(lines)

    @classmethod
    def _path_from(cls, arguments: Mapping[str, object]) -> Path:
        value = arguments.get("path", ".")

        if not isinstance(value, str):
            raise ValueError("path must be a string")

        return Path(value)

    @classmethod
    def _max_entries_from(cls, arguments: Mapping[str, object]) -> int:
        value = arguments.get("max_entries", cls._DEFAULT_MAX_ENTRIES)

        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("max_entries must be an integer")
        if not 1 <= value <= cls._MAX_ENTRIES:
            raise ValueError("max_entries must be between 1 and 100")

        return value

    @staticmethod
    def _offset_from(arguments: Mapping[str, object]) -> int:
        value = arguments.get("offset", 0)

        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("offset must be an integer")
        if value < 0:
            raise ValueError("offset must not be negative")

        return value

    @staticmethod
    def _entry_kind(entry: Path) -> str:
        if entry.is_symlink():
            return "symlink"
        if entry.is_dir():
            return "directory"
        return "file"
