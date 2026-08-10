from collections.abc import Mapping
from pathlib import Path

from asagent.core.tool_definition import ToolDefinition
from asagent.workspace.resolver import WorkspaceResolver


class FilesystemReadFileTool:
    """Reads one UTF-8 text file inside an authorized workspace root."""

    _MAX_FILE_BYTES = 64 * 1024

    def __init__(self, resolver: WorkspaceResolver) -> None:
        self._resolver = resolver

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="filesystem.read_file",
            display_name="Read file",
            description=(
                "Reads the UTF-8 text content of one authorized file. "
                "Files larger than 65536 bytes are rejected."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "A file path inside an authorized workspace root."
                        ),
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"filesystem.read"}),
            requires_approval=False,
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        path = self._path_from(arguments)
        file_path = self._resolver.resolve(path)

        if not file_path.exists():
            raise ValueError("file does not exist")
        if not file_path.is_file():
            raise ValueError("path must resolve to a file")

        contents = self._read_bounded_bytes(file_path)

        try:
            return contents.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("file must contain valid UTF-8 text") from error

    @classmethod
    def _path_from(cls, arguments: Mapping[str, object]) -> Path:
        value = arguments.get("path")

        if not isinstance(value, str):
            raise ValueError("path must be a string")

        return Path(value)

    @classmethod
    def _read_bounded_bytes(cls, file_path: Path) -> bytes:
        try:
            with file_path.open("rb") as file:
                contents = file.read(cls._MAX_FILE_BYTES + 1)
        except OSError as error:
            raise ValueError("file cannot be read") from error

        if len(contents) > cls._MAX_FILE_BYTES:
            raise ValueError("file exceeds the 65536 byte read limit")

        return contents
