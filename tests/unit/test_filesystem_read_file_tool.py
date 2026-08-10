from collections.abc import Mapping
from pathlib import Path

import pytest

from asagent.core.tool import Tool
from asagent.tools.builtin.filesystem_read_file import FilesystemReadFileTool
from asagent.workspace.resolver import (
    WorkspacePathOutsideAllowedRootsError,
    WorkspaceResolver,
)


def _tool(workspace_root: Path) -> FilesystemReadFileTool:
    return FilesystemReadFileTool(
        WorkspaceResolver(workspace_root=workspace_root),
    )


def test_filesystem_read_file_tool_satisfies_protocol_and_describes_input(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    tool: Tool = _tool(workspace_root)

    assert isinstance(tool, Tool)
    assert tool.definition.tool_id == "filesystem.read_file"
    assert tool.definition.required_permissions == frozenset({"filesystem.read"})
    assert tool.definition.requires_approval is False
    properties = tool.definition.input_schema["properties"]

    assert isinstance(properties, Mapping)
    assert properties["path"] == {
        "type": "string",
        "description": "A file path inside an authorized workspace root.",
    }
    assert tool.definition.input_schema["required"] == ["path"]


@pytest.mark.asyncio
async def test_filesystem_read_file_tool_reads_utf8_text(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    notes = workspace_root / "notes.md"
    notes.write_text("# Plan\n\n你好，asAgent。\n", encoding="utf-8")

    result = await _tool(workspace_root).execute({"path": "notes.md"})

    assert result == "# Plan\n\n你好，asAgent。\n"


@pytest.mark.asyncio
async def test_filesystem_read_file_tool_returns_empty_text_for_empty_file(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "empty.txt").write_text("", encoding="utf-8")

    result = await _tool(workspace_root).execute({"path": "empty.txt"})

    assert result == ""


@pytest.mark.asyncio
async def test_filesystem_read_file_tool_rejects_outside_missing_and_directory_paths(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "folder").mkdir()
    tool = _tool(workspace_root)

    with pytest.raises(WorkspacePathOutsideAllowedRootsError):
        await tool.execute({"path": "../outside.txt"})

    with pytest.raises(ValueError, match="file does not exist"):
        await tool.execute({"path": "missing.txt"})

    with pytest.raises(ValueError, match="must resolve to a file"):
        await tool.execute({"path": "folder"})


@pytest.mark.asyncio
async def test_filesystem_read_file_tool_rejects_oversized_files(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    tool = _tool(workspace_root)
    (workspace_root / "large.txt").write_bytes(
        b"x" * (tool._MAX_FILE_BYTES + 1),
    )

    with pytest.raises(ValueError, match="exceeds the 65536 byte read limit"):
        await tool.execute({"path": "large.txt"})


@pytest.mark.asyncio
async def test_filesystem_read_file_tool_rejects_non_utf8_content(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "binary.dat").write_bytes(b"\xff")

    with pytest.raises(ValueError, match="must contain valid UTF-8 text"):
        await _tool(workspace_root).execute({"path": "binary.dat"})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"path": 1},
    ],
)
async def test_filesystem_read_file_tool_rejects_invalid_direct_arguments(
    tmp_path: Path,
    arguments: dict[str, object],
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    with pytest.raises(ValueError, match="path must be a string"):
        await _tool(workspace_root).execute(arguments)
