from collections.abc import Mapping
from pathlib import Path

import pytest

from asagent.core.tool import Tool
from asagent.tools.builtin.filesystem_list import FilesystemListTool
from asagent.workspace.resolver import (
    WorkspacePathOutsideAllowedRootsError,
    WorkspaceResolver,
)


def _tool(workspace_root: Path) -> FilesystemListTool:
    return FilesystemListTool(
        WorkspaceResolver(workspace_root=workspace_root),
    )


def test_filesystem_list_tool_satisfies_protocol_and_describes_input(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    tool: Tool = _tool(workspace_root)

    assert isinstance(tool, Tool)
    assert tool.definition.tool_id == "filesystem.list"
    assert tool.definition.required_permissions == frozenset({"filesystem.read"})
    assert tool.definition.requires_approval is False
    properties = tool.definition.input_schema["properties"]

    assert isinstance(properties, Mapping)
    assert properties["path"] == {
        "type": "string",
        "description": (
            "A path inside an authorized workspace root. "
            "Defaults to the workspace root."
        ),
    }
    assert properties["offset"] == {
        "type": "integer",
        "minimum": 0,
        "description": (
            "Number of sorted directory entries to skip before returning a page. "
            "Defaults to 0."
        ),
    }


@pytest.mark.asyncio
async def test_filesystem_list_tool_lists_sorted_entry_kinds(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "zeta.txt").write_text("zeta", encoding="utf-8")
    (workspace_root / "alpha").mkdir()
    (workspace_root / "middle-link").symlink_to(
        workspace_root / "zeta.txt",
    )

    result = await _tool(workspace_root).execute({})

    assert result == "\n".join(
        (
            "Directory contains 3 entries. Showing 1-3:",
            "directory: alpha",
            "symlink: middle-link",
            "file: zeta.txt",
        ),
    )


@pytest.mark.asyncio
async def test_filesystem_list_tool_paginates_and_reports_total_entries(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    for name in ("alpha.txt", "beta.txt", "gamma.txt"):
        (workspace_root / name).write_text(name, encoding="utf-8")

    result = await _tool(workspace_root).execute({"max_entries": 2})

    assert result == "\n".join(
        (
            "Directory contains 3 entries. Showing 1-2:",
            "file: alpha.txt",
            "file: beta.txt",
            "[1 additional entry available. Call again with offset=2.]",
        ),
    )

    next_page = await _tool(workspace_root).execute(
        {"offset": 2, "max_entries": 2},
    )

    assert next_page == "\n".join(
        (
            "Directory contains 3 entries. Showing 3-3:",
            "file: gamma.txt",
        ),
    )


@pytest.mark.asyncio
async def test_filesystem_list_tool_reports_an_empty_page_without_hiding_total(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "alpha.txt").write_text("alpha", encoding="utf-8")

    result = await _tool(workspace_root).execute({"offset": 1})

    assert result == "Directory contains 1 entries. No entries at offset 1."


@pytest.mark.asyncio
async def test_filesystem_list_tool_returns_an_empty_directory_message(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    result = await _tool(workspace_root).execute({})

    assert result == "Directory is empty."


@pytest.mark.asyncio
async def test_filesystem_list_tool_rejects_workspace_escape_and_files(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "document.txt").write_text("content", encoding="utf-8")
    tool = _tool(workspace_root)

    with pytest.raises(WorkspacePathOutsideAllowedRootsError):
        await tool.execute({"path": "../outside"})

    with pytest.raises(ValueError, match="must resolve to a directory"):
        await tool.execute({"path": "document.txt"})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"path": 1}, "path must be a string"),
        ({"max_entries": True}, "max_entries must be an integer"),
        ({"max_entries": 0}, "max_entries must be between 1 and 100"),
        ({"max_entries": 101}, "max_entries must be between 1 and 100"),
        ({"offset": True}, "offset must be an integer"),
        ({"offset": -1}, "offset must not be negative"),
    ],
)
async def test_filesystem_list_tool_rejects_invalid_direct_arguments(
    tmp_path: Path,
    arguments: dict[str, object],
    message: str,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    with pytest.raises(ValueError, match=message):
        await _tool(workspace_root).execute(arguments)
