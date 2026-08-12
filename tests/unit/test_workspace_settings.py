import json
from pathlib import Path

import pytest

from asagent.workspace.settings import (
    WorkspaceSettings,
    WorkspaceSettingsConfigurationError,
)


def test_workspace_settings_save_normalizes_and_persists_additional_roots(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    selected_root = tmp_path / "selected"
    workspace_root.mkdir()
    selected_root.mkdir()
    settings = WorkspaceSettings(
        config_dir=tmp_path / "config",
        workspace_root=workspace_root,
    )

    saved = settings.save(additional_roots=(selected_root / ".", selected_root))

    assert saved.workspace_root == workspace_root.resolve()
    assert saved.additional_roots == (selected_root.resolve(),)
    assert settings.get_status() == saved
    assert json.loads((tmp_path / "config" / "workspace.json").read_text()) == {
        "additional_roots": [str(selected_root.resolve())],
    }


def test_workspace_settings_rejects_a_missing_or_non_directory_root(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    settings = WorkspaceSettings(
        config_dir=tmp_path / "config",
        workspace_root=workspace_root,
    )

    with pytest.raises(ValueError, match="additional_roots must exist"):
        settings.save(additional_roots=(tmp_path / "missing",))

    file_path = tmp_path / "file.txt"
    file_path.write_text("not a directory", encoding="utf-8")
    with pytest.raises(ValueError, match="additional_roots must be a directory"):
        settings.save(additional_roots=(file_path,))


def test_workspace_settings_rejects_invalid_saved_configuration(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    config_dir = tmp_path / "config"
    workspace_root.mkdir()
    config_dir.mkdir()
    (config_dir / "workspace.json").write_text('{"unexpected": []}', encoding="utf-8")
    settings = WorkspaceSettings(config_dir=config_dir, workspace_root=workspace_root)

    with pytest.raises(WorkspaceSettingsConfigurationError, match="invalid"):
        settings.get_status()
