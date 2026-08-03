from pathlib import Path

import pytest

from ragent.paths import AppPaths


def test_app_paths_from_root_uses_a_stable_directory_layout(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_root(tmp_path)

    assert paths.config_dir == tmp_path / "config"
    assert paths.data_dir == tmp_path / "data"
    assert paths.log_dir == tmp_path / "logs"
    assert paths.cache_dir == tmp_path / "cache"
    assert paths.workspace_dir == tmp_path / "workspace"
    assert paths.temp_dir == tmp_path / "temp"


def test_app_paths_can_be_explicitly_constructed(tmp_path: Path) -> None:
    paths = AppPaths(
        config_dir=tmp_path / "custom-config",
        data_dir=tmp_path / "custom-data",
        log_dir=tmp_path / "custom-logs",
        cache_dir=tmp_path / "custom-cache",
        workspace_dir=tmp_path / "custom-workspace",
        temp_dir=tmp_path / "custom-temp",
    )

    assert paths.data_dir == tmp_path / "custom-data"


def test_app_paths_from_root_does_not_create_directories(tmp_path: Path) -> None:
    root = tmp_path / "app-home"

    AppPaths.from_root(root)

    assert not root.exists()


def test_app_paths_are_immutable(tmp_path: Path) -> None:
    paths = AppPaths.from_root(tmp_path)

    with pytest.raises(AttributeError):
        paths.data_dir = tmp_path / "other-data"  # type: ignore[misc]
