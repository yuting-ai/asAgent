from collections.abc import Callable, Iterable
from dataclasses import dataclass

from asagent.core.tool_definition import ToolDefinition
from asagent.models.contracts import ModelToolDefinition

ToolNameMapper = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class ToolBinding:
    tool_id: str
    provider_name: str
    definition: ToolDefinition


@dataclass(frozen=True, slots=True)
class ToolSnapshot:
    bindings: tuple[ToolBinding, ...]

    def __post_init__(self) -> None:
        tool_ids: set[str] = set()
        provider_names: set[str] = set()

        for binding in self.bindings:
            if binding.definition.tool_id != binding.tool_id:
                raise ValueError(
                    "binding definition tool_id must match binding tool_id"
                )
            if binding.tool_id in tool_ids:
                raise ValueError("tool snapshot contains a duplicate tool_id")
            if binding.provider_name in provider_names:
                raise ValueError(
                    "tool snapshot contains a duplicate provider_name",
                )

            tool_ids.add(binding.tool_id)
            provider_names.add(binding.provider_name)

    @classmethod
    def from_definitions(
        cls,
        definitions: Iterable[ToolDefinition],
        *,
        provider_name_for: ToolNameMapper,
    ) -> "ToolSnapshot":
        return cls(
            bindings=tuple(
                ToolBinding(
                    tool_id=definition.tool_id,
                    provider_name=provider_name_for(definition.tool_id),
                    definition=definition,
                )
                for definition in definitions
            ),
        )

    def provider_name_for(self, tool_id: str) -> str:
        for binding in self.bindings:
            if binding.tool_id == tool_id:
                return binding.provider_name

        raise KeyError(f"tool_id is not in snapshot: {tool_id}")

    def tool_id_for(self, provider_name: str) -> str:
        for binding in self.bindings:
            if binding.provider_name == provider_name:
                return binding.tool_id

        raise KeyError(f"provider_name is not in snapshot: {provider_name}")

    def definition_for(self, tool_id: str) -> ToolDefinition:
        for binding in self.bindings:
            if binding.tool_id == tool_id:
                return binding.definition

        raise KeyError(f"tool_id is not in snapshot: {tool_id}")

    @property
    def model_tools(self) -> tuple[ModelToolDefinition, ...]:
        return tuple(
            ModelToolDefinition(
                name=binding.provider_name,
                description=binding.definition.description,
                input_schema=binding.definition.input_schema,
            )
            for binding in self.bindings
        )
