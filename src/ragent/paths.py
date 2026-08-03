from dataclasses import dataclass
from pathlib import Path
from typing import Self


@dataclass(frozen=True, slots=True)
class AppPaths:
    config_dir: Path
    data_dir: Path
    log_dir: Path
    cache_dir: Path
    workspace_dir: Path
    temp_dir: Path

    @classmethod
    def from_root(cls, root: Path) -> Self:
        return cls(
            config_dir=root / "config",
            data_dir=root / "data",
            log_dir=root / "logs",
            cache_dir=root / "cache",
            workspace_dir=root / "workspace",
            temp_dir=root / "temp",
        )
