from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_RETENTION_DAYS = 7
ALLOWED_RETENTION_DAYS = (1, 3, 7, 30, 0)  # 0 means never delete
STORAGE_SETTINGS_FILE_NAME = "storage.toml"


@dataclass(frozen=True, slots=True)
class StorageSettings:
    """Non-sensitive storage and snapshot retention settings."""

    snapshot_retention_days: int = DEFAULT_RETENTION_DAYS

    def __post_init__(self) -> None:
        if isinstance(self.snapshot_retention_days, bool) or not isinstance(
            self.snapshot_retention_days, int
        ):
            raise ValueError("snapshot_retention_days must be an integer")
        if self.snapshot_retention_days not in ALLOWED_RETENTION_DAYS:
            raise ValueError(
                f"snapshot_retention_days must be one of {ALLOWED_RETENTION_DAYS}",
            )


class StorageSettingsStore:
    """Load and save StorageSettings from config_dir/storage.toml."""

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = config_dir
        self._path = config_dir / STORAGE_SETTINGS_FILE_NAME

    def get(self) -> StorageSettings:
        try:
            with self._path.open("rb") as file:
                data = tomllib.load(file)
        except FileNotFoundError:
            return StorageSettings()
        except tomllib.TOMLDecodeError as error:
            raise ValueError("storage settings are invalid TOML") from error

        if not isinstance(data, dict):
            raise ValueError("storage settings are invalid")

        retention_days = data.get("snapshot_retention_days", DEFAULT_RETENTION_DAYS)
        try:
            return StorageSettings(snapshot_retention_days=retention_days)
        except ValueError as error:
            raise ValueError("storage settings are invalid") from error

    def save(self, settings: StorageSettings) -> StorageSettings:
        validated = StorageSettings(
            snapshot_retention_days=settings.snapshot_retention_days
        )
        self._config_dir.mkdir(parents=True, exist_ok=True)
        temporary_path = self._path.with_suffix(".toml.tmp")
        payload = f"snapshot_retention_days = {validated.snapshot_retention_days}\n"
        temporary_path.write_text(payload, encoding="utf-8")
        temporary_path.replace(self._path)
        return validated
