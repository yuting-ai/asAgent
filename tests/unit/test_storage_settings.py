from pathlib import Path

import pytest

from asagent.bootstrap.storage_settings import (
    DEFAULT_RETENTION_DAYS,
    StorageSettings,
    StorageSettingsStore,
)


def test_storage_settings_defaults() -> None:
    settings = StorageSettings()
    assert settings.snapshot_retention_days == DEFAULT_RETENTION_DAYS


def test_storage_settings_validations() -> None:
    assert StorageSettings(snapshot_retention_days=1).snapshot_retention_days == 1
    assert StorageSettings(snapshot_retention_days=3).snapshot_retention_days == 3
    assert StorageSettings(snapshot_retention_days=7).snapshot_retention_days == 7
    assert StorageSettings(snapshot_retention_days=30).snapshot_retention_days == 30
    assert StorageSettings(snapshot_retention_days=0).snapshot_retention_days == 0

    with pytest.raises(ValueError, match="must be an integer"):
        StorageSettings(snapshot_retention_days=True)

    with pytest.raises(ValueError, match="must be one of"):
        StorageSettings(snapshot_retention_days=15)


def test_storage_settings_store_lifecycle(tmp_path: Path) -> None:
    store = StorageSettingsStore(tmp_path)
    # Default when file not found
    assert store.get().snapshot_retention_days == DEFAULT_RETENTION_DAYS

    # Save and reload
    saved = store.save(StorageSettings(snapshot_retention_days=3))
    assert saved.snapshot_retention_days == 3
    assert store.get().snapshot_retention_days == 3

    # Invalid TOML
    (tmp_path / "storage.toml").write_text("invalid = [toml", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid TOML"):
        store.get()
