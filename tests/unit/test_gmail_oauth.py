from base64 import urlsafe_b64encode
from hashlib import sha256
from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import ValidationError

from asagent.bootstrap.gmail_oauth import (
    GmailDesktopOAuthConfig,
    GmailOAuthAuthorizationDeniedError,
    GmailOAuthCallbackError,
    loopback_redirect_uri,
    start_gmail_authorization,
)

_CLIENT_ID = "1234567890-test.apps.googleusercontent.com"


def test_start_gmail_authorization_uses_pkce_and_gmail_readonly_scope() -> None:
    session = start_gmail_authorization(
        config=GmailDesktopOAuthConfig(client_id=_CLIENT_ID),
        redirect_uri=loopback_redirect_uri(43127),
    )
    parsed = urlparse(session.authorization_url)
    parameters = parse_qs(parsed.query, strict_parsing=True)

    expected_challenge = (
        urlsafe_b64encode(
            sha256(session.code_verifier.encode("ascii")).digest(),
        )
        .decode("ascii")
        .rstrip("=")
    )

    assert parsed.scheme == "https"
    assert parsed.netloc == "accounts.google.com"
    assert parsed.path == "/o/oauth2/v2/auth"
    assert parameters["client_id"] == [_CLIENT_ID]
    assert parameters["response_type"] == ["code"]
    assert parameters["redirect_uri"] == [
        "http://127.0.0.1:43127/oauth2/callback",
    ]
    assert parameters["scope"] == [
        "https://www.googleapis.com/auth/gmail.readonly",
    ]
    assert parameters["access_type"] == ["offline"]
    assert parameters["code_challenge_method"] == ["S256"]
    assert parameters["code_challenge"] == [expected_challenge]
    assert len(parameters["state"][0]) >= 43
    assert "client_secret" not in parameters


def test_authorization_session_accepts_one_matching_callback() -> None:
    session = start_gmail_authorization(
        config=GmailDesktopOAuthConfig(client_id=_CLIENT_ID),
        redirect_uri=loopback_redirect_uri(43127),
    )
    state = parse_qs(urlparse(session.authorization_url).query)["state"][0]

    assert (
        session.consume_callback(
            {"code": ("authorization-code",), "state": (state,)},
        )
        == "authorization-code"
    )

    with pytest.raises(GmailOAuthCallbackError, match="already consumed"):
        session.consume_callback(
            {"code": ("another-code",), "state": (state,)},
        )


def test_authorization_session_rejects_a_mismatched_state() -> None:
    session = start_gmail_authorization(
        config=GmailDesktopOAuthConfig(client_id=_CLIENT_ID),
        redirect_uri=loopback_redirect_uri(43127),
    )

    with pytest.raises(GmailOAuthCallbackError, match="state did not match"):
        session.consume_callback(
            {"code": ("authorization-code",), "state": ("wrong-state",)},
        )


def test_authorization_session_reports_a_user_denial_without_details() -> None:
    session = start_gmail_authorization(
        config=GmailDesktopOAuthConfig(client_id=_CLIENT_ID),
        redirect_uri=loopback_redirect_uri(43127),
    )
    state = parse_qs(urlparse(session.authorization_url).query)["state"][0]

    with pytest.raises(
        GmailOAuthAuthorizationDeniedError,
        match="authorization was denied",
    ):
        session.consume_callback(
            {"error": ("access_denied",), "state": (state,)},
        )


@pytest.mark.parametrize(
    ("client_id", "redirect_uri"),
    [
        (
            "not-a-google-client",
            "http://127.0.0.1:43127/oauth2/callback",
        ),
        (
            _CLIENT_ID,
            "http://localhost:43127/oauth2/callback",
        ),
        (
            _CLIENT_ID,
            "http://127.0.0.1:43127/not-the-callback",
        ),
    ],
)
def test_authorization_rejects_invalid_non_sensitive_configuration(
    client_id: str,
    redirect_uri: str,
) -> None:
    if client_id == _CLIENT_ID:
        config = GmailDesktopOAuthConfig(client_id=client_id)

        with pytest.raises(ValueError, match="loopback callback"):
            start_gmail_authorization(
                config=config,
                redirect_uri=redirect_uri,
            )
    else:
        with pytest.raises(ValidationError, match="client_id is invalid"):
            GmailDesktopOAuthConfig(client_id=client_id)


@pytest.mark.parametrize("port", [0, 65_536, True])
def test_loopback_redirect_uri_rejects_invalid_ports(port: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 65535"):
        loopback_redirect_uri(port)
