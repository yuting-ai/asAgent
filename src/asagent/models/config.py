from enum import StrEnum

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


class ProviderAdapter(StrEnum):
    OPENAI_COMPATIBLE = "openai_compatible"
    ANTHROPIC_MESSAGES = "anthropic_messages"


class ProviderConfig(BaseModel):
    """A non-sensitive, named model-provider profile."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    adapter: ProviderAdapter
    model: str = Field(min_length=1)
    base_url: AnyHttpUrl
    secret_id: str = Field(min_length=1)
    timeout_seconds: float = Field(default=30.0, gt=0)


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
