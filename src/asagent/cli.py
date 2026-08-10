import argparse
import asyncio
import json
import os
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

from asagent.agent.loop import AgentLoop
from asagent.agent.persistent_runtime import PersistentAgentRuntime
from asagent.bootstrap.environment_secret_provider import (
    EnvironmentSecretProvider,
)
from asagent.bootstrap.provider_factory import create_model_provider
from asagent.chat.service import ChatService
from asagent.core.conversation import Conversation
from asagent.core.event_publisher import EventPublisher
from asagent.core.ids import (
    ConversationId,
    EventId,
    MessageId,
    RunId,
    ToolCallId,
    UserId,
)
from asagent.core.repositories import ConversationRepository
from asagent.core.run_event import RunEvent
from asagent.core.run_status import RunStatus
from asagent.core.tool_call_recorder import ToolCallRecorder
from asagent.models.contracts import (
    ModelEvent,
    ModelMessage,
    ModelMessageRole,
    ModelRequest,
    ModelResponse,
    ModelToolCall,
)
from asagent.models.errors import ProviderConfigurationError
from asagent.models.profile_loader import load_provider_profiles
from asagent.models.provider import ModelProvider
from asagent.models.tool_names import openai_compatible_tool_name
from asagent.paths import AppPaths
from asagent.storage.event_publisher import RepositoryEventPublisher
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.database import upgrade_sqlite_database
from asagent.storage.sqlite.run_finisher import SqliteRunFinisher
from asagent.storage.sqlite.run_repository import SqliteRunRepository
from asagent.storage.sqlite.run_starter import SqliteRunStarter
from asagent.storage.tool_call_recorder import RepositoryToolCallRecorder
from asagent.tools.builtin.calculator import CalculatorTool
from asagent.tools.builtin.current_time import CurrentTimeTool
from asagent.tools.builtin.echo import EchoTool
from asagent.tools.executor import ToolExecutor
from asagent.tools.registry import ToolRegistry
from asagent.tools.snapshot import ToolSnapshot


class _EchoModelProvider:
    async def complete(self, request: ModelRequest) -> ModelResponse:
        content = next(
            (
                message.content
                for message in reversed(request.messages)
                if message.role is ModelMessageRole.USER
            ),
            "",
        )
        return ModelResponse(text=f"Echo: {content}", tool_calls=())

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        response = await self.complete(request)
        if response.text is not None:
            yield ModelEvent(event_type="model.delta", text_delta=response.text)


class DevelopmentToolModelProvider:
    """A deterministic offline Provider for manually exercising the Agent Loop."""

    def __init__(self, tool_snapshot: ToolSnapshot) -> None:
        self._tool_snapshot = tool_snapshot

    async def complete(self, request: ModelRequest) -> ModelResponse:
        last_message = request.messages[-1]
        if last_message.role is ModelMessageRole.TOOL:
            return ModelResponse(
                text=f"Tool result: {last_message.content}",
                tool_calls=(),
            )

        if last_message.role is not ModelMessageRole.USER:
            raise RuntimeError("development agent expected a user or tool message")

        content = last_message.content or ""
        normalized = content.strip().lower()
        if normalized.startswith("calculate "):
            tool_id = "builtin.calculator"
            arguments: dict[str, object] = {
                "expression": content.strip()[len("calculate ") :],
            }
        elif normalized in {"time", "current time", "what time is it?"}:
            tool_id = "builtin.current_time"
            arguments = {}
        else:
            tool_id = "builtin.echo"
            arguments = {"text": content}

        return ModelResponse(
            text=None,
            tool_calls=(
                ModelToolCall(
                    call_id="development_tool_call",
                    name=self._tool_snapshot.provider_name_for(tool_id),
                    arguments=arguments,
                ),
            ),
        )

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        del request
        raise RuntimeError("development agent does not support streaming")


class ConsoleEventPublisher:
    def __init__(self, write_line: Callable[[str], None]) -> None:
        self._write_line = write_line

    async def publish(self, event: RunEvent) -> None:
        data = json.dumps(dict(event.data), ensure_ascii=False, sort_keys=True)
        self._write_line(f"[event {event.sequence}] {event.event_type} {data}")


def _register_builtin_tools() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(CalculatorTool())
    registry.register(CurrentTimeTool())
    return registry


def build_agent_loop(
    *,
    model: ModelProvider,
    event_publisher: EventPublisher,
    tool_call_recorder: ToolCallRecorder | None = None,
) -> AgentLoop:
    registry = _register_builtin_tools()
    snapshot = ToolSnapshot.from_definitions(
        registry.definitions(),
        provider_name_for=openai_compatible_tool_name,
    )
    return AgentLoop(
        model=model,
        executor=ToolExecutor(
            registry,
            granted_permissions=frozenset({"tool.execute"}),
        ),
        tool_snapshot=snapshot,
        event_publisher=event_publisher,
        event_id_factory=new_event_id,
        clock=now,
        tool_call_recorder=tool_call_recorder,
        tool_call_id_factory=(
            new_tool_call_id if tool_call_recorder is not None else None
        ),
    )


def build_development_agent_loop(
    *,
    event_publisher: EventPublisher,
    tool_call_recorder: ToolCallRecorder | None = None,
) -> AgentLoop:
    registry = _register_builtin_tools()
    snapshot = ToolSnapshot.from_definitions(
        registry.definitions(),
        provider_name_for=openai_compatible_tool_name,
    )
    return AgentLoop(
        model=DevelopmentToolModelProvider(snapshot),
        executor=ToolExecutor(
            registry,
            granted_permissions=frozenset({"tool.execute"}),
        ),
        tool_snapshot=snapshot,
        event_publisher=event_publisher,
        event_id_factory=new_event_id,
        clock=now,
        tool_call_recorder=tool_call_recorder,
        tool_call_id_factory=new_tool_call_id,
    )


async def run_agent_chat(
    *,
    agent_loop: AgentLoop,
    conversation_id: ConversationId,
    model_name: str,
    system_prompt: str,
    read_line: Callable[[str], str],
    write_line: Callable[[str], None],
    new_run_id: Callable[[], RunId],
) -> None:
    history: list[ModelMessage] = []
    write_line("asAgent development agent. Type 'exit' to quit.")

    while True:
        try:
            content = read_line("You: ")
        except EOFError:
            return

        if content.strip().lower() in {"exit", "quit"}:
            return
        if not content.strip():
            continue

        history.append(
            ModelMessage(role=ModelMessageRole.USER, content=content),
        )
        try:
            result = await agent_loop.run(
                model_name=model_name,
                system_prompt=system_prompt,
                messages=tuple(history),
                run_id=new_run_id(),
                conversation_id=conversation_id,
            )
        except Exception as error:
            write_line(f"Error: {error}")
            continue

        history = list(result.messages)
        if result.status is RunStatus.COMPLETED and result.text is not None:
            write_line(f"asAgent: {result.text}")
        elif result.error is not None:
            write_line(f"Error: {result.error}")
        else:
            write_line(f"Run ended: {result.status.value}")


async def run_chat(
    *,
    chat_service: ChatService,
    conversation: Conversation,
    model_name: str,
    system_prompt: str,
    read_line: Callable[[str], str],
    write_line: Callable[[str], None],
) -> None:
    write_line("asAgent development chat. Type 'exit' to quit.")

    while True:
        try:
            content = read_line("You: ")
        except EOFError:
            return

        if content.strip().lower() in {"exit", "quit"}:
            return
        if not content.strip():
            continue

        try:
            reply = await chat_service.send(
                conversation=conversation,
                content=content,
                model_name=model_name,
                system_prompt=system_prompt,
            )
        except Exception as error:
            write_line(f"Error: {error}")
            continue

        write_line(f"asAgent: {reply.content}")


def now() -> datetime:
    return datetime.now(UTC)


def new_conversation_id() -> ConversationId:
    return ConversationId(f"conv_{uuid4().hex}")


def new_event_id() -> EventId:
    return EventId(f"evt_{uuid4().hex}")


def new_message_id() -> MessageId:
    return MessageId(f"msg_{uuid4().hex}")


def new_run_id() -> RunId:
    return RunId(f"run_{uuid4().hex}")


def new_tool_call_id() -> ToolCallId:
    return ToolCallId(f"tool_{uuid4().hex}")


def _alembic_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "alembic.ini"


def build_persistent_agent_runtime(
    *,
    model: ModelProvider,
    conversations: SqliteConversationRepository,
    runs: SqliteRunRepository,
    starter: SqliteRunStarter,
    finisher: SqliteRunFinisher,
) -> PersistentAgentRuntime:
    return PersistentAgentRuntime(
        conversations=conversations,
        run_starter=starter,
        run_finisher=finisher,
        loop=build_agent_loop(
            model=model,
            event_publisher=RepositoryEventPublisher(runs),
            tool_call_recorder=RepositoryToolCallRecorder(runs),
        ),
        now=now,
        new_run_id=new_run_id,
        new_message_id=new_message_id,
    )


def build_persistent_development_runtime(
    *,
    conversations: SqliteConversationRepository,
    runs: SqliteRunRepository,
    starter: SqliteRunStarter,
    finisher: SqliteRunFinisher,
) -> PersistentAgentRuntime:
    return PersistentAgentRuntime(
        conversations=conversations,
        run_starter=starter,
        run_finisher=finisher,
        loop=build_development_agent_loop(
            event_publisher=RepositoryEventPublisher(runs),
            tool_call_recorder=RepositoryToolCallRecorder(runs),
        ),
        now=now,
        new_run_id=new_run_id,
        new_message_id=new_message_id,
    )


async def get_or_create_persistent_conversation(
    *,
    conversations: ConversationRepository,
    conversation_id: ConversationId | None,
) -> Conversation:
    if conversation_id is not None:
        conversation = await conversations.get(conversation_id)
        if conversation is None:
            raise ValueError("requested conversation is unavailable")
        return conversation

    created_at = now()
    conversation = Conversation(
        conversation_id=new_conversation_id(),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
    )
    await conversations.save(conversation)
    return conversation


async def run_persistent_agent_chat(
    *,
    runtime: PersistentAgentRuntime,
    conversation_id: ConversationId,
    model_name: str,
    system_prompt: str,
    read_line: Callable[[str], str],
    write_line: Callable[[str], None],
) -> None:
    write_line(
        "asAgent persistent agent. "
        f"Conversation: {conversation_id}. Type 'exit' to quit.",
    )

    while True:
        try:
            content = read_line("You: ")
        except EOFError:
            return

        if content.strip().lower() in {"exit", "quit"}:
            return
        if not content.strip():
            continue

        try:
            result = await runtime.run(
                conversation_id=conversation_id,
                content=content,
                model_name=model_name,
                system_prompt=system_prompt,
            )
        except Exception as error:
            write_line(f"Error: {error}")
            continue

        if result.assistant_message is not None:
            write_line(f"asAgent: {result.assistant_message.content}")
        elif result.error is not None:
            write_line(f"Error: {result.error}")
        else:
            write_line(f"Run ended: {result.run.status.value}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the asAgent development CLI.")
    parser.add_argument(
        "--profile",
        help="Use the named local Provider Profile instead of the offline provider.",
    )
    parser.add_argument(
        "--secret-env",
        help="Development-only environment variable bound to the selected Profile secret.",
    )
    parser.add_argument(
        "--app-home",
        type=Path,
        default=Path(".local-data"),
        help="Root containing config/providers.toml for a real Provider Profile.",
    )
    parser.add_argument(
        "--persistent",
        action="store_true",
        help="Persist conversations and Runs in SQLite.",
    )
    parser.add_argument(
        "--conversation-id",
        help="Reuse an existing Conversation in --persistent mode.",
    )
    return parser.parse_args(argv)


async def _run_main(args: argparse.Namespace) -> None:
    system_prompt = (
        "You are asAgent's development assistant. Use the supplied tools when "
        "they help answer the user."
    )

    if (args.profile is None) != (args.secret_env is None):
        raise ProviderConfigurationError(
            "--profile and --secret-env must be provided together",
        )

    if args.conversation_id is not None and not args.persistent:
        raise ProviderConfigurationError(
            "--conversation-id requires --persistent",
        )

    if args.persistent:
        paths = AppPaths.from_root(args.app_home)
        database_path = paths.data_dir / "asagent.sqlite3"
        upgrade_sqlite_database(
            database_path=database_path,
            alembic_config_path=_alembic_config_path(),
        )

        conversations = SqliteConversationRepository(database_path)
        runs = SqliteRunRepository(database_path)
        starter = SqliteRunStarter(database_path)
        finisher = SqliteRunFinisher(database_path)

        try:
            conversation = await get_or_create_persistent_conversation(
                conversations=conversations,
                conversation_id=(
                    ConversationId(args.conversation_id)
                    if args.conversation_id is not None
                    else None
                ),
            )

            if args.profile is None:
                runtime = build_persistent_development_runtime(
                    conversations=conversations,
                    runs=runs,
                    starter=starter,
                    finisher=finisher,
                )
                model_name = "development-tools"
                await run_persistent_agent_chat(
                    runtime=runtime,
                    conversation_id=conversation.conversation_id,
                    model_name=model_name,
                    system_prompt=system_prompt,
                    read_line=input,
                    write_line=print,
                )
                return

            profiles = load_provider_profiles(paths.config_dir)
            try:
                profile = profiles.providers[args.profile]
            except KeyError as error:
                raise ProviderConfigurationError(
                    "requested provider profile is unavailable",
                ) from error

            secrets = EnvironmentSecretProvider(
                environment=dict(os.environ),
                bindings={profile.secret_id: args.secret_env},
            )
            async with httpx.AsyncClient() as client:
                provider = create_model_provider(
                    profiles=profiles,
                    profile_name=args.profile,
                    secrets=secrets,
                    http_client=client,
                )
                await run_persistent_agent_chat(
                    runtime=build_persistent_agent_runtime(
                        model=provider,
                        conversations=conversations,
                        runs=runs,
                        starter=starter,
                        finisher=finisher,
                    ),
                    conversation_id=conversation.conversation_id,
                    model_name=profile.model,
                    system_prompt=system_prompt,
                    read_line=input,
                    write_line=print,
                )
        finally:
            await finisher.aclose()
            await starter.aclose()
            await runs.aclose()
            await conversations.aclose()
        return

    publisher = ConsoleEventPublisher(print)
    conversation_id = new_conversation_id()

    if args.profile is None and args.secret_env is None:
        agent_loop = build_development_agent_loop(event_publisher=publisher)
        await run_agent_chat(
            agent_loop=agent_loop,
            conversation_id=conversation_id,
            model_name="development-tools",
            system_prompt=system_prompt,
            read_line=input,
            write_line=print,
            new_run_id=new_run_id,
        )
        return

    profiles = load_provider_profiles(AppPaths.from_root(args.app_home).config_dir)
    try:
        profile = profiles.providers[args.profile]
    except KeyError as error:
        raise ProviderConfigurationError(
            "requested provider profile is unavailable",
        ) from error
    secrets = EnvironmentSecretProvider(
        environment=dict(os.environ),
        bindings={profile.secret_id: args.secret_env},
    )
    async with httpx.AsyncClient() as client:
        provider = create_model_provider(
            profiles=profiles,
            profile_name=args.profile,
            secrets=secrets,
            http_client=client,
        )
        await run_agent_chat(
            agent_loop=build_agent_loop(
                model=provider,
                event_publisher=publisher,
            ),
            conversation_id=conversation_id,
            model_name=profile.model,
            system_prompt=system_prompt,
            read_line=input,
            write_line=print,
            new_run_id=new_run_id,
        )


def main(argv: Sequence[str] | None = None) -> None:
    try:
        asyncio.run(_run_main(parse_args(argv)))
    except ProviderConfigurationError as error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()
