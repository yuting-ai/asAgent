import ipaddress
from enum import StrEnum

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class ProviderAdapter(StrEnum):
    OPENAI_COMPATIBLE = "openai_compatible"
    ANTHROPIC_MESSAGES = "anthropic_messages"


class ProviderLocation(StrEnum):
    LOCAL = "local"
    EXTERNAL = "external"


class ProviderConfig(BaseModel):
    """A non-sensitive, named model-provider profile."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    adapter: ProviderAdapter
    location: ProviderLocation = ProviderLocation.EXTERNAL
    model: str = Field(min_length=1)
    base_url: AnyHttpUrl
    secret_id: str | None = Field(default=None, min_length=1)
    timeout_seconds: float = Field(default=180.0, gt=0)

    @model_validator(mode="after")
    def validate_location(self) -> "ProviderConfig":
        if self.location is ProviderLocation.EXTERNAL and self.secret_id is None:
            raise ValueError("external provider profiles require a secret_id")
        if self.location is ProviderLocation.LOCAL and not _is_loopback_host(
            self.base_url.host
        ):
            raise ValueError("local provider base_url must use a loopback host")
        return self


class ProviderProfiles(BaseModel):
    """All named provider profiles loaded from future configuration."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    providers: dict[str, ProviderConfig]

    @field_validator("providers")
    @classmethod
    def validate_provider_names(
        cls,
        providers: dict[str, ProviderConfig],
    ) -> dict[str, ProviderConfig]:
        if not providers:
            raise ValueError("at least one provider profile is required")

        if any(not name.strip() for name in providers):
            raise ValueError("provider profile names must not be empty")

        return providers


def _is_loopback_host(host: str | None) -> bool:
    if host is None:
        return False
    normalized = host.removeprefix("[").removesuffix("]")
    if normalized.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False
