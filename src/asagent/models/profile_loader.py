import json
import tomllib
from pathlib import Path

from pydantic import ValidationError

from asagent.models.config import ProviderProfiles
from asagent.models.errors import ProviderConfigurationError


def load_provider_profiles(config_dir: Path) -> ProviderProfiles:
    """Load non-sensitive provider profiles from config_dir/providers.toml."""

    config_path = config_dir / "providers.toml"

    try:
        with config_path.open("rb") as file:
            data = tomllib.load(file)
    except FileNotFoundError as error:
        raise ProviderConfigurationError(
            "provider profile configuration file is unavailable",
        ) from error
    except tomllib.TOMLDecodeError as error:
        raise ProviderConfigurationError(
            "provider profile configuration is invalid TOML",
        ) from error

    try:
        return ProviderProfiles.model_validate(data)
    except ValidationError as error:
        raise ProviderConfigurationError(
            "provider profile configuration is invalid",
        ) from error


def save_provider_profiles(config_dir: Path, profiles: ProviderProfiles) -> None:
    """Atomically write validated, non-sensitive provider profiles."""

    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "providers.toml"
    temporary_path = config_path.with_suffix(".toml.tmp")
    lines: list[str] = []

    for name, profile in sorted(profiles.providers.items()):
        lines.extend(
            (
                f"[providers.{json.dumps(name)}]",
                f'adapter = "{profile.adapter.value}"',
                f'location = "{profile.location.value}"',
                f"model = {json.dumps(profile.model)}",
                f"base_url = {json.dumps(str(profile.base_url))}",
                *(
                    [f"secret_id = {json.dumps(profile.secret_id)}"]
                    if profile.secret_id is not None
                    else []
                ),
                f"timeout_seconds = {profile.timeout_seconds}",
                "",
            ),
        )

    temporary_path.write_text("\n".join(lines), encoding="utf-8")
    temporary_path.replace(config_path)
