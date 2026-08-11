from collections.abc import AsyncIterator
from datetime import UTC, datetime
from itertools import count
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from asagent.agent.loop import AgentLoop
from asagent.agent.persistent_runtime import PersistentAgentRuntime
from asagent.agent.run_submission import RunSubmissionService, SubmittedRun
from asagent.core.conversation import Conversation
from asagent.core.ids import (
    ConversationId,
    EventId,
    MessageId,
    RunId,
    ToolCallId,
    UserId,
)
from asagent.core.messages import UserMessage
from asagent.core.run import Run
from asagent.core.run_lifecycle import RunFinisher, RunStarter
from asagent.core.run_status import RunStatus
from asagent.models.contracts import (
    ModelEvent,
    ModelMessageRole,
    ModelRequest,
    ModelResponse,
    ModelToolCall,
)
from asagent.models.fake_provider import FakeModelProvider
from asagent.models.provider import ModelProvider
from asagent.models.tool_names import openai_compatible_tool_name
from asagent.storage.event_publisher import RepositoryEventPublisher
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.run_finisher import SqliteRunFinisher
from asagent.storage.sqlite.run_repository import SqliteRunRepository
from asagent.storage.sqlite.run_starter import SqliteRunStarter
from asagent.storage.tool_call_recorder import RepositoryToolCallRecorder
from asagent.tools.builtin.echo import EchoTool
from asagent.tools.executor import ToolExecutor
from asagent.tools.registry import ToolRegistry
from asagent.tools.snapshot import ToolSnapshot


class CrashingModelProvider:
    def __init__(self, error: Exception) -> None:
        self.requests: list[ModelRequest] = []
        self._error = error

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        raise self._error

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        del request
        raise AssertionError("stream is not used by PersistentAgentRuntime")


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


def _conversation(conversation_id: ConversationId) -> Conversation:
    created_at = datetime(2026, 8, 10, 17, 0, tzinfo=UTC)
    return Conversation(
        conversation_id=conversation_id,
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
    )


def _clock() -> datetime:
    return datetime(2026, 8, 10, 17, 1, tzinfo=UTC)


def _loop(
    *,
    provider: ModelProvider,
    runs: SqliteRunRepository,
) -> AgentLoop:
    tool = EchoTool()
    registry = ToolRegistry()
    registry.register(tool)
    snapshot = ToolSnapshot.from_definitions(
        registry.definitions(),
        provider_name_for=openai_compatible_tool_name,
    )
    event_numbers = count(1)
    tool_call_numbers = count(1)

    return AgentLoop(
        model=provider,
        executor=ToolExecutor(
            registry,
            granted_permissions=frozenset({"tool.execute"}),
        ),
        tool_snapshot=snapshot,
        event_publisher=RepositoryEventPublisher(runs),
        event_id_factory=lambda: EventId(f"event-{next(event_numbers)}"),
        clock=_clock,
        tool_call_recorder=RepositoryToolCallRecorder(runs),
        tool_call_id_factory=lambda: ToolCallId(
            f"tool-call-{next(tool_call_numbers)}",
        ),
    )


def _runtime(
    *,
    conversations: SqliteConversationRepository,
    runs: SqliteRunRepository,
    starter: SqliteRunStarter,
    finisher: SqliteRunFinisher,
    provider: ModelProvider,
) -> PersistentAgentRuntime:
    message_numbers = count(1)

    return PersistentAgentRuntime(
        conversations=conversations,
        run_submission=RunSubmissionService(
            conversations=conversations,
            run_starter=starter,
            now=_clock,
            new_run_id=lambda: RunId("run-1"),
            new_message_id=lambda: MessageId(f"message-{next(message_numbers)}"),
        ),
        run_finisher=finisher,
        loop=_loop(provider=provider, runs=runs),
        now=_clock,
        new_message_id=lambda: MessageId(f"message-{next(message_numbers)}"),
    )


@pytest.mark.asyncio
async def test_persists_completed_run_message_and_events(tmp_path: Path) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    finisher = SqliteRunFinisher(database_path)
    provider = FakeModelProvider(
        responses=(ModelResponse(text="Hello!", tool_calls=()),),
    )

    try:
        await conversations.save(_conversation(conversation_id))
        starter_protocol: RunStarter = starter
        finisher_protocol: RunFinisher = finisher
        assert isinstance(starter_protocol, RunStarter)
        assert isinstance(finisher_protocol, RunFinisher)

        result = await _runtime(
            conversations=conversations,
            runs=runs,
            starter=starter,
            finisher=finisher,
            provider=provider,
        ).run(
            conversation_id=conversation_id,
            content="Hello",
            model_name="fake-model",
            system_prompt="Be helpful.",
        )

        assert result.run.status is RunStatus.COMPLETED
        assert result.assistant_message is not None
        assert result.assistant_message.content == "Hello!"
        assert result.error is None
        assert result.steps_used == 1
        assert len(provider.requests) == 1

        assert await runs.get(result.run.run_id) == result.run
        assert tuple(
            message.content
            for message in await conversations.list_messages(
                conversation_id,
            )
        ) == ("Hello", "Hello!")
        assert tuple(
            event.event_type for event in await runs.list_events(result.run.run_id)
        ) == (
            "run.started",
            "model.requested",
            "model.completed",
            "run.completed",
        )
    finally:
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_persists_tool_call_and_final_answer(tmp_path: Path) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    finisher = SqliteRunFinisher(database_path)
    provider = FakeModelProvider(
        responses=(
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="model-call-1",
                        name="builtin_echo",
                        arguments={"text": "hello"},
                    ),
                ),
            ),
            ModelResponse(text="Echo completed.", tool_calls=()),
        ),
    )

    try:
        await conversations.save(_conversation(conversation_id))

        result = await _runtime(
            conversations=conversations,
            runs=runs,
            starter=starter,
            finisher=finisher,
            provider=provider,
        ).run(
            conversation_id=conversation_id,
            content="Please echo hello.",
            model_name="fake-model",
            system_prompt="Be helpful.",
        )

        assert result.run.status is RunStatus.COMPLETED
        assert result.assistant_message is not None
        assert result.assistant_message.content == "Echo completed."

        (tool_call,) = await runs.list_tool_calls(result.run.run_id)
        assert tool_call.model_call_id == "model-call-1"
        assert tool_call.tool_id == "builtin.echo"
        assert dict(tool_call.arguments) == {"text": "hello"}
        assert tool_call.result == "Echo: hello"
        assert tool_call.error is None
    finally:
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_persists_failed_run_without_assistant_message(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    finisher = SqliteRunFinisher(database_path)
    provider = FakeModelProvider(
        responses=(ModelResponse(text=None, tool_calls=()),),
    )

    try:
        await conversations.save(_conversation(conversation_id))

        result = await _runtime(
            conversations=conversations,
            runs=runs,
            starter=starter,
            finisher=finisher,
            provider=provider,
        ).run(
            conversation_id=conversation_id,
            content="Please help.",
            model_name="fake-model",
            system_prompt="Be helpful.",
        )

        assert result.run.status is RunStatus.FAILED
        assert result.assistant_message is None
        assert result.error == "model response contained no text or tool calls"
        assert tuple(
            message.content
            for message in await conversations.list_messages(
                conversation_id,
            )
        ) == ("Please help.",)
    finally:
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_rejects_unknown_conversation_before_model_call(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("missing-conversation")
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    finisher = SqliteRunFinisher(database_path)
    provider = FakeModelProvider()

    try:
        with pytest.raises(ValueError, match="unknown conversation"):
            await _runtime(
                conversations=conversations,
                runs=runs,
                starter=starter,
                finisher=finisher,
                provider=provider,
            ).run(
                conversation_id=conversation_id,
                content="Hello",
                model_name="fake-model",
                system_prompt="Be helpful.",
            )

        assert provider.requests == ()
        assert await runs.get(RunId("run-1")) is None
    finally:
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_executes_an_existing_submission_without_creating_a_second_run(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    finisher = SqliteRunFinisher(database_path)
    provider = FakeModelProvider(
        responses=(ModelResponse(text="Hello!", tool_calls=()),),
    )
    message_numbers = count(1)
    run_submission = RunSubmissionService(
        conversations=conversations,
        run_starter=starter,
        now=_clock,
        new_run_id=lambda: RunId("run-1"),
        new_message_id=lambda: MessageId(f"message-{next(message_numbers)}"),
    )
    runtime = PersistentAgentRuntime(
        conversations=conversations,
        run_submission=run_submission,
        run_finisher=finisher,
        loop=_loop(provider=provider, runs=runs),
        now=_clock,
        new_message_id=lambda: MessageId(f"message-{next(message_numbers)}"),
    )

    try:
        await conversations.save(_conversation(conversation_id))
        submission = await run_submission.submit(
            conversation_id=conversation_id,
            content="Hello",
        )

        result = await runtime.execute_submitted(
            submission=submission,
            model_name="fake-model",
            system_prompt="Be helpful.",
        )

        assert result.run.status is RunStatus.COMPLETED
        assert result.assistant_message is not None
        assert result.assistant_message.content == "Hello!"
        assert await runs.list_for_conversation(conversation_id) == (result.run,)
        assert tuple(
            message.content
            for message in await conversations.list_messages(conversation_id)
        ) == ("Hello", "Hello!")
        assert provider.requests[0].messages[-1].content == "Hello"
        assert provider.requests[0].messages[-1].role is ModelMessageRole.USER
        assert await conversations.list_messages(conversation_id) == (
            submission.user_message,
            result.assistant_message,
        )
    finally:
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_execute_submitted_rejects_non_created_runs(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    finisher = SqliteRunFinisher(database_path)
    provider = FakeModelProvider()
    created_at = _clock()
    submission = SubmittedRun(
        user_message=UserMessage(
            message_id=MessageId("message-1"),
            conversation_id=conversation_id,
            content="Hello",
            created_at=created_at,
        ),
        run=Run(
            run_id=RunId("run-1"),
            conversation_id=conversation_id,
            status=RunStatus.COMPLETED,
            created_at=created_at,
            updated_at=created_at,
        ),
    )

    try:
        await conversations.save(_conversation(conversation_id))

        with pytest.raises(ValueError, match="can only execute a created run"):
            await _runtime(
                conversations=conversations,
                runs=runs,
                starter=starter,
                finisher=finisher,
                provider=provider,
            ).execute_submitted(
                submission=submission,
                model_name="fake-model",
                system_prompt="Be helpful.",
            )

        assert provider.requests == ()
        assert await runs.list_for_conversation(conversation_id) == ()
        assert await conversations.list_messages(conversation_id) == ()
    finally:
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_persists_failed_run_when_unexpected_execution_error_escapes_loop(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    finisher = SqliteRunFinisher(database_path)
    expected_error = RuntimeError("model crashed")
    provider = CrashingModelProvider(expected_error)

    try:
        await conversations.save(_conversation(conversation_id))

        with pytest.raises(RuntimeError) as captured:
            await _runtime(
                conversations=conversations,
                runs=runs,
                starter=starter,
                finisher=finisher,
                provider=provider,
            ).run(
                conversation_id=conversation_id,
                content="Hello",
                model_name="fake-model",
                system_prompt="Be helpful.",
            )

        assert captured.value is expected_error
        assert len(provider.requests) == 1
        assert await runs.get(RunId("run-1")) == Run(
            run_id=RunId("run-1"),
            conversation_id=conversation_id,
            status=RunStatus.FAILED,
            created_at=_clock(),
            updated_at=_clock(),
        )
        assert tuple(
            message.content
            for message in await conversations.list_messages(conversation_id)
        ) == ("Hello",)
    finally:
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()
