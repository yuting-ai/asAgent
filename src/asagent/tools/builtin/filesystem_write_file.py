from collections.abc import Mapping
from pathlib import Path

from asagent.core.tool_definition import ToolDefinition
from asagent.workspace.resolver import WorkspaceResolver


class FilesystemWriteFileTool:
    """Creates one new UTF-8 text file inside an authorized workspace root."""

    _MAX_CONTENT_BYTES = 64 * 1024

    def __init__(self, resolver: WorkspaceResolver) -> None:
        self._resolver = resolver

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="filesystem.write_file",
            display_name="Create file",
            description=(
                "Creates one new UTF-8 text file inside an authorized workspace "
                "root. Existing files are never overwritten."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "A new file path inside an authorized workspace root."
                        ),
                    },
                    "content": {
                        "type": "string",
                        "description": (
                            "UTF-8 text content to write. "
                            "The encoded content must not exceed 65536 bytes."
                        ),
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
            risk_level="high",
            required_permissions=frozenset({"filesystem.write"}),
            requires_approval=True,
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        path = self._path_from(arguments)
        content = self._content_from(arguments)
        file_path = self._resolver.resolve(path)

        if file_path.exists():
            if file_path.is_dir():
                raise ValueError("path must not resolve to a directory")
            raise ValueError("file already exists and cannot be overwritten")

        if not file_path.parent.exists():
            raise ValueError("parent directory does not exist")
        if not file_path.parent.is_dir():
            raise ValueError("parent path must resolve to a directory")

        try:
            with file_path.open("xb") as file:
                file.write(content)
        except FileExistsError as error:
            raise ValueError(
                "file already exists and cannot be overwritten",
            ) from error
        except OSError as error:
            raise ValueError("file cannot be created") from error

        return "File created."

    @classmethod
    def _path_from(cls, arguments: Mapping[str, object]) -> Path:
        value = arguments.get("path")

        if not isinstance(value, str):
            raise ValueError("path must be a string")

        return Path(value)

    @classmethod
    def _content_from(cls, arguments: Mapping[str, object]) -> bytes:
        value = arguments.get("content")

        if not isinstance(value, str):
            raise ValueError("content must be a string")

        try:
            content = value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError("content must be valid UTF-8 text") from error

        if len(content) > cls._MAX_CONTENT_BYTES:
            raise ValueError("content exceeds the 65536 byte write limit")

        return content
