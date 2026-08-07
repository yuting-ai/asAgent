import asyncio
import os
from pathlib import Path

import httpx

from ragent.bootstrap.environment_secret_provider import (
    EnvironmentSecretProvider,
)
from ragent.bootstrap.provider_factory import create_model_provider
from ragent.models.contracts import (
    ModelMessage,
    ModelMessageRole,
    ModelRequest,
)
from ragent.models.errors import ProviderError
from ragent.models.profile_loader import load_provider_profiles


async def run_check() -> int:
    config_dir = Path(".local-data/config")
    profiles = load_provider_profiles(config_dir)
    profile_name = "deepseek"
    profile = profiles.providers[profile_name]

    secrets = EnvironmentSecretProvider(
        environment=dict(os.environ),
        bindings={
            profile.secret_id: "RAGENT_DEEPSEEK_API_KEY",
        },
    )

    try:
        async with httpx.AsyncClient() as client:
            provider = create_model_provider(
                profiles=profiles,
                profile_name=profile_name,
                secrets=secrets,
                http_client=client,
            )
            response = await provider.complete(
                ModelRequest(
                    model=profile.model,
                    system_prompt="Reply with exactly: Ragent connectivity confirmed.",
                    messages=(
                        ModelMessage(
                            role=ModelMessageRole.USER,
                            content="Confirm connectivity.",
                        ),
                    ),
                    tools=(),
                ),
            )
    except ProviderError as error:
        print(f"DeepSeek connectivity check failed: {error}")
        return 1

    print("DeepSeek connectivity check succeeded.")
    print(f"Response: {response.text}")
    print(f"Input tokens: {response.input_tokens}")
    print(f"Output tokens: {response.output_tokens}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_check()))
