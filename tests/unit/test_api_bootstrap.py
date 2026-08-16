import pytest

from asagent.api.bootstrap import (
    LocalApiBootstrapError,
    read_local_api_bootstrap,
    read_local_api_token,
)


def test_reads_a_local_api_token_from_one_bootstrap_json_record() -> None:
    token = read_local_api_token(lambda: '{"token":"test-token"}\n')

    assert token.value == "test-token"


def test_reads_optional_browser_bridge_from_bootstrap_json_record() -> None:
    bootstrap = read_local_api_bootstrap(
        lambda: (
            '{"token":"test-token","browser_bridge":'
            '{"base_url":"http://127.0.0.1:43124","token":"bridge-token"}}\n'
        ),
    )

    assert bootstrap.token.value == "test-token"
    assert bootstrap.browser_bridge is not None
    assert bootstrap.browser_bridge.base_url == "http://127.0.0.1:43124"
    assert bootstrap.browser_bridge.token == "bridge-token"


@pytest.mark.parametrize(
    "line",
    (
        "",
        "not-json\n",
        "[]\n",
        '{"token": 1}\n',
        '{"token": ""}\n',
        '{"token": "contains whitespace"}\n',
        '{"token":"test-token","browser_bridge":[]}\n',
        '{"token":"test-token","browser_bridge":{"base_url":1,"token":"x"}}\n',
        '{"token":"test-token","browser_bridge":'
        '{"base_url":"http://example.com:80","token":"x"}}\n',
        '{"token":"test-token","browser_bridge":'
        '{"base_url":"http://127.0.0.1:80","token":"has space"}}\n',
        '{"token":"test-token","browser_bridge":'
        '{"base_url":"http://user:pass@127.0.0.1:80","token":"x"}}\n',
    ),
)
def test_rejects_missing_or_invalid_bootstrap_input(line: str) -> None:
    with pytest.raises(LocalApiBootstrapError, match="bootstrap input"):
        read_local_api_bootstrap(lambda: line)
