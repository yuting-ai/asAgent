import json
from collections.abc import Mapping
from pathlib import Path

from asagent.core.file_change import FileChange
from asagent.core.ids import RunId
from asagent.core.tool_definition import ToolDefinition
from asagent.storage.reversible_files import ReversibleFileService


class FilesystemCreateFileTool:
    """Creates one reversible UTF-8 file for the current Run."""

    def __init__(self, service: ReversibleFileService, run_id: RunId) -> None:
        self._service = service
        self._run_id = run_id

    @property
    def definition(self) -> ToolDefinition:
        return _definition(
            tool_id="filesystem.create_file",
            display_name="Create file",
            description=(
                "Create one new UTF-8 text file at an authorized path. The parent "
                "directory must already exist, and the change can be undone by the user."
            ),
            include_content=True,
            risk_level="medium",
            requires_approval=False,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        change = await self._service.create_text(
            run_id=self._run_id,
            path=_path(arguments),
            content=_content(arguments),
        )
        return _result(change)


class FilesystemReplaceFileTool:
    """Replaces one reversible UTF-8 file for the current Run."""

    def __init__(self, service: ReversibleFileService, run_id: RunId) -> None:
        self._service = service
        self._run_id = run_id

    @property
    def definition(self) -> ToolDefinition:
        return _definition(
            tool_id="filesystem.replace_file",
            display_name="Replace file",
            description=(
                "Replace one existing UTF-8 text file at an authorized path. A private "
                "snapshot is saved so the user can undo the change safely."
            ),
            include_content=True,
            risk_level="medium",
            requires_approval=False,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        change = await self._service.replace_text(
            run_id=self._run_id,
            path=_path(arguments),
            content=_content(arguments),
        )
        return _result(change)


class FilesystemDeleteFileTool:
    """Deletes one reversible UTF-8 file for the current Run."""

    def __init__(self, service: ReversibleFileService, run_id: RunId) -> None:
        self._service = service
        self._run_id = run_id

    @property
    def definition(self) -> ToolDefinition:
        return _definition(
            tool_id="filesystem.delete_file",
            display_name="Delete file",
            description=(
                "Delete one existing file at an authorized path. The file is safely "
                "moved to the Trash and a snapshot is saved so the user can undo the "
                "deletion safely."
            ),
            include_content=False,
            risk_level="medium",
            requires_approval=False,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        change = await self._service.delete_file(
            run_id=self._run_id,
            path=_path(arguments),
        )
        return _result(change)


def _definition(
    *,
    tool_id: str,
    display_name: str,
    description: str,
    include_content: bool,
    risk_level: str = "high",
    requires_approval: bool = True,
) -> ToolDefinition:
    properties: dict[str, object] = {
        "path": {
            "type": "string",
            "description": "The exact file path inside this conversation's authorized scope.",
        }
    }
    required = ["path"]
    if include_content:
        properties["content"] = {
            "type": "string",
            "description": "The complete UTF-8 content, limited to 65536 encoded bytes.",
        }
        required.append("content")

    return ToolDefinition(
        tool_id=tool_id,
        display_name=display_name,
        description=description,
        input_schema={
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        risk_level=risk_level,
        required_permissions=frozenset({"filesystem.write"}),
        requires_approval=requires_approval,
        timeout_seconds=10.0,
    )


def _path(arguments: Mapping[str, object]) -> Path:
    value = arguments.get("path")
    if not isinstance(value, str) or not value:
        raise ValueError("path must be a non-empty string")
    return Path(value)


def _content(arguments: Mapping[str, object]) -> str:
    value = arguments.get("content")
    if not isinstance(value, str):
        raise ValueError("content must be a string")
    return value


def _result(change: FileChange) -> str:
    return json.dumps(
        {
            "change_id": str(change.file_change_id),
            "operation": change.operation.value,
            "path": str(Path(change.root_path) / change.relative_path),
            "status": change.status.value,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
