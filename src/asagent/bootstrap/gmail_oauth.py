from base64 import urlsafe_b64encode
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe
from urllib.parse import urlencode, urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_CALLBACK_PATH = "/oauth2/callback"
_GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class GmailOAuthCallbackError(RuntimeError):
    """A Google OAuth callback was malformed or did not match this request."""


class GmailOAuthAuthorizationDeniedError(GmailOAuthCallbackError):
    """The user declined the Google OAuth authorization request."""


class GmailDesktopOAuthConfig(BaseModel):
    """Non-sensitive Google Desktop OAuth configuration."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    client_id: str = Field(min_length=1)

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, client_id: str) -> str:
        if not client_id.endswith(".apps.googleusercontent.com"):
            raise ValueError("Google OAuth client_id is invalid")
        return client_id


@dataclass(slots=True)
class GmailOAuthAuthorizationSession:
    """One in-memory Gmail OAuth authorization request."""

    authorization_url: str
    code_verifier: str
    _state: str
    _completed: bool = False

    def consume_callback(
        self,
        query: Mapping[str, Sequence[str]],
    ) -> str:
        """Validate one callback and return its authorization code."""

        if self._completed:
            raise GmailOAuthCallbackError(
                "Google OAuth callback was already consumed",
            )

        state = _single_query_value(query, "state")
        if state is None or not compare_digest(state, self._state):
            raise GmailOAuthCallbackError(
                "Google OAuth callback state did not match",
            )

        code = _single_query_value(query, "code")
        error = _single_query_value(query, "error")
        if code is not None and error is not None:
            raise GmailOAuthCallbackError(
                "Google OAuth callback is invalid",
            )

        if error is not None:
            self._completed = True
            if error == "access_denied":
                raise GmailOAuthAuthorizationDeniedError(
                    "Google authorization was denied",
                )
            raise GmailOAuthCallbackError(
                "Google OAuth authorization failed",
            )

        if code is None:
            raise GmailOAuthCallbackError(
                "Google OAuth callback did not include an authorization code",
            )

        self._completed = True
        return code


def loopback_redirect_uri(port: int) -> str:
    """Build the only callback URI accepted by the first desktop flow."""

    if isinstance(port, bool) or not 1 <= port <= 65_535:
        raise ValueError("Google OAuth callback port must be between 1 and 65535")

    return f"http://127.0.0.1:{port}{_CALLBACK_PATH}"


def start_gmail_authorization(
    *,
    config: GmailDesktopOAuthConfig,
    redirect_uri: str,
) -> GmailOAuthAuthorizationSession:
    """Create one PKCE-protected Gmail authorization request in memory."""

    _validate_loopback_redirect_uri(redirect_uri)

    state = token_urlsafe(32)
    code_verifier = token_urlsafe(64)
    code_challenge = _code_challenge(code_verifier)
    authorization_url = (
        f"{_AUTHORIZATION_ENDPOINT}?"
        f"{
            urlencode(
                {
                    'access_type': 'offline',
                    'client_id': config.client_id,
                    'code_challenge': code_challenge,
                    'code_challenge_method': 'S256',
                    'include_granted_scopes': 'true',
                    'redirect_uri': redirect_uri,
                    'response_type': 'code',
                    'scope': _GMAIL_READONLY_SCOPE,
                    'state': state,
                },
            )
        }"
    )

    return GmailOAuthAuthorizationSession(
        authorization_url=authorization_url,
        code_verifier=code_verifier,
        _state=state,
    )


def _code_challenge(code_verifier: str) -> str:
    return (
        urlsafe_b64encode(
            sha256(code_verifier.encode("ascii")).digest(),
        )
        .decode("ascii")
        .rstrip("=")
    )


def _single_query_value(
    query: Mapping[str, Sequence[str]],
    name: str,
) -> str | None:
    values = query.get(name)
    if values is None:
        return None
    if isinstance(values, str) or len(values) != 1 or not values[0]:
        raise GmailOAuthCallbackError(
            "Google OAuth callback contains invalid query parameters",
        )
    return values[0]


def _validate_loopback_redirect_uri(redirect_uri: str) -> None:
    parsed = urlparse(redirect_uri)

    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port is None
        or parsed.path != _CALLBACK_PATH
        or parsed.params
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Google OAuth redirect_uri must be a loopback callback")
