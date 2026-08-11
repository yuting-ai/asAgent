from dataclasses import dataclass
from secrets import compare_digest, token_urlsafe
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_BEARER_SECURITY = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class LocalApiToken:
    value: str

    def __post_init__(self) -> None:
        if not self.value or any(character.isspace() for character in self.value):
            raise ValueError(
                "local API token must be a non-empty non-whitespace string"
            )

    @classmethod
    def generate(cls) -> "LocalApiToken":
        return cls(token_urlsafe(32))

    def matches(self, candidate: str) -> bool:
        return compare_digest(self.value, candidate)


class BearerTokenAuthenticator:
    def __init__(self, expected_token: LocalApiToken) -> None:
        self._expected_token = expected_token

    async def __call__(
        self,
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Depends(_BEARER_SECURITY),
        ],
    ) -> None:
        candidate = None if credentials is None else credentials.credentials

        if candidate is None or not self._expected_token.matches(candidate):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid local API credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
