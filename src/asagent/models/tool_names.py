import re

_INVALID_NAME_CHARACTERS = re.compile(r"[^A-Za-z0-9_-]")
_VALID_OPENAI_COMPATIBLE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def openai_compatible_tool_name(tool_id: str) -> str:
    provider_name = _INVALID_NAME_CHARACTERS.sub("_", tool_id)

    if _VALID_OPENAI_COMPATIBLE_NAME.fullmatch(provider_name) is None:
        raise ValueError(
            "tool_id cannot be converted to an OpenAI-compatible tool name",
        )

    return provider_name
