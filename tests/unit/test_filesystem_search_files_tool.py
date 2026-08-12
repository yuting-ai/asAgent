from pathlib import Path

import pytest

from asagent.core.tool import Tool
from asagent.tools.builtin.filesystem_search_files import (
    FilesystemSearchFilesTool,
)
from asagent.workspace.resolver import (
    WorkspacePathOutsideAllowedRootsError,
    WorkspaceResolver,
)


def _tool(workspace_root: Path) -> FilesystemSearchFilesTool:
    return FilesystemSearchFilesTool(
        WorkspaceResolver(workspace_root=workspace_root),
    )


def test_filesystem_search_files_tool_describes_a_safe_read_only_search(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    tool: Tool = _tool(workspace_root)

    assert isinstance(tool, Tool)
    assert tool.definition.tool_id == "filesystem.search_files"
    assert tool.definition.required_permissions == frozenset({"filesystem.read"})
    assert tool.definition.requires_approval is False
    assert tool.definition.timeout_seconds == 10.0


@pytest.mark.asyncio
async def test_search_files_finds_names_and_utf8_content_recursively(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "Budget-plan.md").write_text(
        "A private plan.\n",
        encoding="utf-8",
    )
    nested = workspace_root / "notes"
    nested.mkdir()
    (nested / "today.txt").write_text(
        "Prepare the BUDGET review.\n",
        encoding="utf-8",
    )

    result = await _tool(workspace_root).execute({"query": "budget"})

    assert result == "\n".join(
        (
            "Searched 2 files.",
            "Found 2 matches:",
            "filename: Budget-plan.md",
            "content: notes/today.txt:1: Prepare the BUDGET review.",
        ),
    )


@pytest.mark.asyncio
async def test_search_files_limits_results_and_reports_that_it_stopped(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    for name in ("alpha.txt", "beta.txt", "gamma.txt"):
        (workspace_root / name).write_text("match", encoding="utf-8")

    result = await _tool(workspace_root).execute(
        {"query": "match", "max_results": 2},
    )

    assert result == "\n".join(
        (
            "Searched 2 files.",
            "Found 2 matches:",
            "content: alpha.txt:1: match",
            "content: beta.txt:1: match",
            (
                "[Stopped after reaching max_results=2. "
                "Refine the query or search a specific path.]"
            ),
        ),
    )


@pytest.mark.asyncio
async def test_search_files_skips_binary_oversized_and_symlinked_files(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("needle", encoding="utf-8")
    (workspace_root / "binary.dat").write_bytes(b"\xff")
    (workspace_root / "large.txt").write_bytes(
        b"x" * (FilesystemSearchFilesTool._MAX_FILE_BYTES + 1),
    )
    (workspace_root / "outside-link.txt").symlink_to(outside_file)
    (workspace_root / "valid.txt").write_text("needle", encoding="utf-8")

    result = await _tool(workspace_root).execute({"query": "needle"})

    assert result == "\n".join(
        (
            "Searched 3 files.",
            "Found 1 match:",
            "content: valid.txt:1: needle",
            "[Skipped 2 non-text, unreadable, or oversized files.]",
        ),
    )


@pytest.mark.asyncio
async def test_search_files_rejects_workspace_escape_and_file_target(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "document.txt").write_text("content", encoding="utf-8")
    tool = _tool(workspace_root)

    with pytest.raises(WorkspacePathOutsideAllowedRootsError):
        await tool.execute({"query": "content", "path": "../outside"})

    with pytest.raises(ValueError, match="path must resolve to a directory"):
        await tool.execute({"query": "content", "path": "document.txt"})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({}, "query must be a string"),
        ({"query": "   "}, "query must not be blank"),
        ({"query": 1}, "query must be a string"),
        ({"query": "x", "path": 1}, "path must be a string"),
        ({"query": "x", "max_results": True}, "max_results must be an integer"),
        (
            {"query": "x", "max_results": 0},
            "max_results must be between 1 and 20",
        ),
        (
            {"query": "x", "max_results": 21},
            "max_results must be between 1 and 20",
        ),
    ],
)
async def test_search_files_rejects_invalid_direct_arguments(
    tmp_path: Path,
    arguments: dict[str, object],
    message: str,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    with pytest.raises(ValueError, match=message):
        await _tool(workspace_root).execute(arguments)
