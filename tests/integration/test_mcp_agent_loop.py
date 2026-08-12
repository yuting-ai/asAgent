import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import pytest

from asagent.agent.loop import AgentLoop
from asagent.core.tool_definition import ToolDefinition
from asagent.models.contracts import (
    ModelMessage,
    ModelMessageRole,
    ModelResponse,
    ModelToolCall,
)
from asagent.models.fake_provider import FakeModelProvider
from asagent.models.tool_names import openai_compatible_tool_name
from asagent.tools.executor import ToolExecutor
from asagent.tools.mcp import McpClient, register_mcp_tools
from asagent.tools.registry import ToolRegistry
from asagent.tools.snapshot import ToolSnapshot

_SERVER_PATH: Final = Path(__file__).parents[1] / "fixtures" / "mcp_test_server.py"
_SERVER_COMMAND: Final = (
    sys.executable,
    "-u",
    str(_SERVER_PATH),
)


class ApprovingPolicy:
    async def approve(
        self,
        definition: ToolDefinition,
        arguments: Mapping[str, object],
    ) -> bool:
        return True


@pytest.mark.asyncio
async def test_agent_loop_exposes_and_executes_registered_mcp_tool() -> None:
    client = McpClient(command=_SERVER_COMMAND)
    registry = ToolRegistry()

    try:
        await client.start()
        await register_mcp_tools(
            registry,
            client,
            server_name="test-server",
        )

        snapshot = ToolSnapshot.from_definitions(
            registry.definitions(),
            provider_name_for=openai_compatible_tool_name,
        )
        tool_id = next(
            definition.tool_id
            for definition in registry.definitions()
            if definition.tool_id.startswith("mcp:test-server:add:")
        )
        provider_tool_name = snapshot.provider_name_for(tool_id)
        tool_call = ModelToolCall(
            call_id="call-add",
            name=provider_tool_name,
            arguments={"left": 2, "right": 3},
        )
        model = FakeModelProvider(
            responses=(
                ModelResponse(text=None, tool_calls=(tool_call,)),
                ModelResponse(text="The result is 5.", tool_calls=()),
            ),
        )
        loop = AgentLoop(
            model=model,
            executor=ToolExecutor(
                registry,
                granted_permissions=frozenset({"mcp.execute"}),
                approval_policy=ApprovingPolicy(),
            ),
            tool_snapshot=snapshot,
        )

        result = await loop.run(
            model_name="fake-model",
            system_prompt="Use tools when useful.",
            messages=(
                ModelMessage(
                    role=ModelMessageRole.USER,
                    content="Add 2 and 3.",
                ),
            ),
        )

        assert result.text == "The result is 5."
        assert model.requests[0].tools == snapshot.model_tools
        assert model.requests[1].messages[-1] == ModelMessage(
            role=ModelMessageRole.TOOL,
            content="5",
            tool_call_id="call-add",
        )
    finally:
        await client.aclose()
