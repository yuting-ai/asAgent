from pathlib import Path

import pytest

from asagent.bootstrap.agent_settings import (
    DEFAULT_MAX_STEPS,
    MAX_MAX_STEPS,
    MIN_MAX_STEPS,
    AgentSettings,
    AgentSettingsStore,
)


def test_agent_settings_defaults_to_twenty() -> None:
    settings = AgentSettings()
    assert settings.max_steps == DEFAULT_MAX_STEPS == 20


@pytest.mark.parametrize("max_steps", [MIN_MAX_STEPS, 20, MAX_MAX_STEPS])
def test_agent_settings_accepts_valid_bounds(max_steps: int) -> None:
    assert AgentSettings(max_steps=max_steps).max_steps == max_steps


@pytest.mark.parametrize("max_steps", [0, -1, 51, True, 1.5, "20"])
def test_agent_settings_rejects_invalid_values(max_steps: object) -> None:
    with pytest.raises(ValueError):
        AgentSettings(max_steps=max_steps)  # type: ignore[arg-type]


def test_store_returns_defaults_when_file_missing(tmp_path: Path) -> None:
    store = AgentSettingsStore(tmp_path / "config")
    assert store.get() == AgentSettings()


def test_store_round_trips_max_steps(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    store = AgentSettingsStore(config_dir)

    saved = store.save(AgentSettings(max_steps=30))
    assert saved.max_steps == 30
    assert (config_dir / "agent.toml").read_text(encoding="utf-8") == "max_steps = 30\n"
    assert store.get() == AgentSettings(max_steps=30)


def test_store_rejects_invalid_toml(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "agent.toml").write_text("max_steps = \n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid TOML"):
        AgentSettingsStore(config_dir).get()


def test_store_rejects_out_of_range_file_values(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "agent.toml").write_text("max_steps = 99\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid"):
        AgentSettingsStore(config_dir).get()
