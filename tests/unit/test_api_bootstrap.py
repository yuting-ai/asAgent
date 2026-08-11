import pytest

from asagent.api.bootstrap import LocalApiBootstrapError, read_local_api_token


def test_reads_a_local_api_token_from_one_bootstrap_json_record() -> None:
    token = read_local_api_token(lambda: '{"token":"test-token"}\n')

    assert token.value == "test-token"


@pytest.mark.parametrize(
    "line",
    (
        "",
        "not-json\n",
        "[]\n",
        '{"token": 1}\n',
        '{"token": ""}\n',
        '{"token": "contains whitespace"}\n',
    ),
)
def test_rejects_missing_or_invalid_bootstrap_input(line: str) -> None:
    with pytest.raises(LocalApiBootstrapError, match="bootstrap input"):
        read_local_api_token(lambda: line)
