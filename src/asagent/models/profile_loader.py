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
