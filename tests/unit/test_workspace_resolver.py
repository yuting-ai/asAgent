from pathlib import Path

import pytest

from asagent.workspace.resolver import (
    WorkspacePathOutsideAllowedRootsError,
    WorkspaceResolver,
)


def test_resolver_resolves_relative_and_absolute_paths_inside_workspace(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    resolver = WorkspaceResolver(workspace_root=workspace_root)

    relative = resolver.resolve(Path("files/report.md"))
    absolute = resolver.resolve(workspace_root / "notes" / "today.md")

    assert relative == workspace_root / "files" / "report.md"
    assert absolute == workspace_root / "notes" / "today.md"


def test_resolver_allows_explicit_additional_roots(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    additional_root = tmp_path / "project"
    workspace_root.mkdir()
    additional_root.mkdir()
    resolver = WorkspaceResolver(
        workspace_root=workspace_root,
        additional_roots=(additional_root,),
    )

    resolved = resolver.resolve(additional_root / "README.md")

    assert resolved == additional_root / "README.md"
    assert resolver.allowed_roots == (workspace_root, additional_root)


def test_resolver_allows_an_explicit_file_without_authorizing_its_siblings(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    selected_file = tmp_path / "report.md"
    sibling_file = tmp_path / "private.md"
    workspace_root.mkdir()
    selected_file.write_text("report", encoding="utf-8")
    sibling_file.write_text("private", encoding="utf-8")
    resolver = WorkspaceResolver(
        workspace_root=workspace_root,
        additional_files=(selected_file,),
    )

    assert resolver.resolve(selected_file) == selected_file
    assert resolver.allowed_files == (selected_file,)

    with pytest.raises(WorkspacePathOutsideAllowedRootsError):
        resolver.resolve(sibling_file)


@pytest.mark.parametrize(
    "path",
    [
        Path("../outside.txt"),
        Path("/tmp/outside.txt"),
    ],
)
def test_resolver_rejects_paths_outside_allowed_roots(
    tmp_path: Path,
    path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    resolver = WorkspaceResolver(workspace_root=workspace_root)

    with pytest.raises(WorkspacePathOutsideAllowedRootsError):
        resolver.resolve(path)


def test_resolver_rejects_a_symlink_that_escapes_workspace(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    outside_root = tmp_path / "outside"
    workspace_root.mkdir()
    outside_root.mkdir()
    (workspace_root / "escape").symlink_to(
        outside_root,
        target_is_directory=True,
    )
    resolver = WorkspaceResolver(workspace_root=workspace_root)

    with pytest.raises(WorkspacePathOutsideAllowedRootsError):
        resolver.resolve(Path("escape/private.txt"))


def test_resolver_allows_a_nonexistent_path_within_workspace(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    resolver = WorkspaceResolver(workspace_root=workspace_root)

    resolved = resolver.resolve(Path("new-folder/new-file.txt"))

    assert resolved == workspace_root / "new-folder" / "new-file.txt"


@pytest.mark.parametrize(
    ("workspace_root", "message"),
    [
        (Path("missing"), "must exist"),
        (Path("file.txt"), "must be a directory"),
    ],
)
def test_resolver_rejects_invalid_workspace_roots(
    tmp_path: Path,
    workspace_root: Path,
    message: str,
) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("not a directory", encoding="utf-8")
    resolved_root = (
        file_path if workspace_root.name == "file.txt" else tmp_path / workspace_root
    )

    with pytest.raises(ValueError, match=message):
        WorkspaceResolver(workspace_root=resolved_root)
