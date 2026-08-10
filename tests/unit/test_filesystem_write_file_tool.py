from collections.abc import Mapping
from pathlib import Path

import pytest

from asagent.core.tool import Tool
from asagent.core.tool_definition import ToolDefinition
from asagent.tools.builtin.filesystem_write_file import FilesystemWriteFileTool
from asagent.tools.errors import (
    ToolApprovalDeniedError,
    ToolPermissionDeniedError,
)
from asagent.tools.executor import ToolExecutor
from asagent.tools.registry import ToolRegistry
from asagent.workspace.resolver import (
    WorkspacePathOutsideAllowedRootsError,
    WorkspaceResolver,
)


class ApprovingPolicy:
    async def approve(
        self,
        definition: ToolDefinition,
        arguments: Mapping[str, object],
    ) -> bool:
        return True


def _tool(workspace_root: Path) -> FilesystemWriteFileTool:
    return FilesystemWriteFileTool(
        WorkspaceResolver(workspace_root=workspace_root),
    )


def test_filesystem_write_file_tool_satisfies_protocol_and_describes_input(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    tool: Tool = _tool(workspace_root)

    assert isinstance(tool, Tool)
    assert tool.definition.tool_id == "filesystem.write_file"
    assert tool.definition.risk_level == "high"
    assert tool.definition.required_permissions == frozenset(
        {"filesystem.write"},
    )
    assert tool.definition.requires_approval is True
    properties = tool.definition.input_schema["properties"]

    assert isinstance(properties, Mapping)
    assert properties["path"] == {
        "type": "string",
        "description": "A new file path inside an authorized workspace root.",
    }
    assert tool.definition.input_schema["required"] == ["path", "content"]


@pytest.mark.asyncio
async def test_filesystem_write_file_tool_creates_utf8_text(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    result = await _tool(workspace_root).execute(
        {
            "path": "notes.md",
            "content": "# Plan\n\n你好，asAgent。\n",
        },
    )

    assert result == "File created."
    assert (workspace_root / "notes.md").read_text(
        encoding="utf-8",
    ) == "# Plan\n\n你好，asAgent。\n"


@pytest.mark.asyncio
async def test_filesystem_write_file_tool_never_overwrites_an_existing_file(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    target = workspace_root / "notes.md"
    target.write_text("original", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="already exists and cannot be overwritten",
    ):
        await _tool(workspace_root).execute(
            {"path": "notes.md", "content": "replacement"},
        )

    assert target.read_text(encoding="utf-8") == "original"


@pytest.mark.asyncio
async def test_filesystem_write_file_tool_rejects_invalid_target_paths(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "directory").mkdir()
    (workspace_root / "not-a-directory").write_text(
        "content",
        encoding="utf-8",
    )
    tool = _tool(workspace_root)

    with pytest.raises(WorkspacePathOutsideAllowedRootsError):
        await tool.execute({"path": "../outside.txt", "content": "content"})

    with pytest.raises(ValueError, match="must not resolve to a directory"):
        await tool.execute({"path": "directory", "content": "content"})

    with pytest.raises(ValueError, match="parent directory does not exist"):
        await tool.execute(
            {"path": "missing/notes.md", "content": "content"},
        )

    with pytest.raises(
        ValueError,
        match="parent path must resolve to a directory",
    ):
        await tool.execute(
            {"path": "not-a-directory/notes.md", "content": "content"},
        )


@pytest.mark.asyncio
async def test_filesystem_write_file_tool_rejects_oversized_content(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    tool = _tool(workspace_root)

    with pytest.raises(
        ValueError,
        match="content exceeds the 65536 byte write limit",
    ):
        await tool.execute(
            {
                "path": "large.txt",
                "content": "x" * (tool._MAX_CONTENT_BYTES + 1),
            },
        )

    assert not (workspace_root / "large.txt").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"path": 1, "content": "content"},
        {"path": "notes.txt", "content": 1},
    ],
)
async def test_filesystem_write_file_tool_rejects_invalid_direct_arguments(
    tmp_path: Path,
    arguments: dict[str, object],
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    with pytest.raises(ValueError):
        await _tool(workspace_root).execute(arguments)


@pytest.mark.asyncio
async def test_executor_requires_permission_and_approval_before_creating_file(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    target = workspace_root / "notes.md"
    tool = _tool(workspace_root)
    registry = ToolRegistry()
    registry.register(tool)
    arguments = {"path": "notes.md", "content": "content"}

    without_permission = ToolExecutor(registry)

    with pytest.raises(ToolPermissionDeniedError):
        await without_permission.execute(tool.definition.tool_id, arguments)

    assert not target.exists()

    without_approval = ToolExecutor(
        registry,
        granted_permissions=frozenset({"filesystem.write"}),
    )

    with pytest.raises(ToolApprovalDeniedError):
        await without_approval.execute(tool.definition.tool_id, arguments)

    assert not target.exists()

    approved = ToolExecutor(
        registry,
        granted_permissions=frozenset({"filesystem.write"}),
        approval_policy=ApprovingPolicy(),
    )

    result = await approved.execute(tool.definition.tool_id, arguments)

    assert result == "File created."
    assert target.read_text(encoding="utf-8") == "content"
