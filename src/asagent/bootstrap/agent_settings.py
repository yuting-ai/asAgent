from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAX_STEPS = 20
MIN_MAX_STEPS = 1
MAX_MAX_STEPS = 50
AGENT_SETTINGS_FILE_NAME = "agent.toml"


@dataclass(frozen=True, slots=True)
class AgentSettings:
    """Non-sensitive global Agent runtime settings shared by Chat and Browser."""

    max_steps: int = DEFAULT_MAX_STEPS

    def __post_init__(self) -> None:
        if isinstance(self.max_steps, bool) or not isinstance(self.max_steps, int):
            raise ValueError("max_steps must be an integer")
        if self.max_steps < MIN_MAX_STEPS or self.max_steps > MAX_MAX_STEPS:
            raise ValueError(
                f"max_steps must be between {MIN_MAX_STEPS} and {MAX_MAX_STEPS}",
            )


class AgentSettingsStore:
    """Load and save AgentSettings from config_dir/agent.toml."""

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = config_dir
        self._path = config_dir / AGENT_SETTINGS_FILE_NAME

    def get(self) -> AgentSettings:
        try:
            with self._path.open("rb") as file:
                data = tomllib.load(file)
        except FileNotFoundError:
            return AgentSettings()
        except tomllib.TOMLDecodeError as error:
            raise ValueError("agent settings are invalid TOML") from error

        if not isinstance(data, dict):
            raise ValueError("agent settings are invalid")

        max_steps = data.get("max_steps", DEFAULT_MAX_STEPS)
        try:
            return AgentSettings(max_steps=max_steps)
        except ValueError as error:
            raise ValueError("agent settings are invalid") from error

    def save(self, settings: AgentSettings) -> AgentSettings:
        validated = AgentSettings(max_steps=settings.max_steps)
        self._config_dir.mkdir(parents=True, exist_ok=True)
        temporary_path = self._path.with_suffix(".toml.tmp")
        payload = f"max_steps = {validated.max_steps}\n"
        temporary_path.write_text(payload, encoding="utf-8")
        temporary_path.replace(self._path)
        return validated
