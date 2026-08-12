from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, MessageId, UserId
from asagent.core.messages import AssistantMessage, UserMessage
from asagent.storage.sqlite.connection import create_sqlite_async_engine
from asagent.storage.sqlite.schema import (
    conversation_file_scopes,
    conversations,
    messages,
    run_events,
    runs,
    tool_calls,
    users,
)


class SqliteConversationRepository:
    def __init__(self, database_path: Path) -> None:
        self._engine = create_sqlite_async_engine(database_path)

    async def aclose(self) -> None:
        await self._engine.dispose()

    async def get(
        self,
        conversation_id: ConversationId,
    ) -> Conversation | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(conversations).where(
                    conversations.c.conversation_id == str(conversation_id),
                ),
            )
            row = result.mappings().one_or_none()

        if row is None:
            return None

        return _to_conversation(dict(row))

    async def list_for_user(self, user_id: UserId) -> tuple[Conversation, ...]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(conversations)
                .where(conversations.c.user_id == str(user_id))
                .order_by(
                    conversations.c.updated_at.desc(),
                    conversations.c.conversation_id.desc(),
                ),
            )
            rows = result.mappings().all()

        return tuple(_to_conversation(dict(row)) for row in rows)

    async def save(self, conversation: Conversation) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                sqlite_insert(users)
                .values(
                    user_id=str(conversation.user_id),
                    created_at=_to_utc(conversation.created_at),
                )
                .on_conflict_do_nothing(index_elements=[users.c.user_id]),
            )
            await connection.execute(
                sqlite_insert(conversations)
                .values(
                    conversation_id=str(conversation.conversation_id),
                    user_id=str(conversation.user_id),
                    title=conversation.title,
                    created_at=_to_utc(conversation.created_at),
                    updated_at=_to_utc(conversation.updated_at),
                )
                .on_conflict_do_update(
                    index_elements=[conversations.c.conversation_id],
                    set_={
                        "user_id": str(conversation.user_id),
                        "title": conversation.title,
                        "created_at": _to_utc(conversation.created_at),
                        "updated_at": _to_utc(conversation.updated_at),
                    },
                ),
            )

    async def list_messages(
        self,
        conversation_id: ConversationId,
    ) -> tuple[UserMessage | AssistantMessage, ...]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(messages)
                .where(messages.c.conversation_id == str(conversation_id))
                .order_by(messages.c.sequence.asc()),
            )
            rows = result.mappings().all()

        return tuple(_to_message(dict(row)) for row in rows)

    async def append_message(
        self,
        message: UserMessage | AssistantMessage,
    ) -> None:
        role = "user" if isinstance(message, UserMessage) else "assistant"
        next_sequence = (
            select(func.coalesce(func.max(messages.c.sequence), 0) + 1)
            .where(messages.c.conversation_id == str(message.conversation_id))
            .scalar_subquery()
        )

        async with self._engine.begin() as connection:
            conversation_exists = await connection.scalar(
                select(conversations.c.conversation_id).where(
                    conversations.c.conversation_id == str(message.conversation_id),
                ),
            )
            if conversation_exists is None:
                raise ValueError("cannot append a message to an unknown conversation")

            await connection.execute(
                sqlite_insert(messages).values(
                    message_id=str(message.message_id),
                    conversation_id=str(message.conversation_id),
                    sequence=next_sequence,
                    role=role,
                    content=message.content,
                    created_at=_to_utc(message.created_at),
                ),
            )

    async def delete(self, conversation_id: ConversationId) -> bool:
        async with self._engine.begin() as connection:
            exists = await connection.scalar(
                select(conversations.c.conversation_id).where(
                    conversations.c.conversation_id == str(conversation_id),
                ),
            )
            if exists is None:
                return False

            run_ids = (
                await connection.scalars(
                    select(runs.c.run_id).where(
                        runs.c.conversation_id == str(conversation_id),
                    ),
                )
            ).all()

            if run_ids:
                await connection.execute(
                    delete(tool_calls).where(tool_calls.c.run_id.in_(run_ids)),
                )
                await connection.execute(
                    delete(run_events).where(run_events.c.run_id.in_(run_ids)),
                )
                await connection.execute(
                    delete(runs).where(
                        runs.c.conversation_id == str(conversation_id),
                    ),
                )

            await connection.execute(
                delete(messages).where(
                    messages.c.conversation_id == str(conversation_id),
                ),
            )
            await connection.execute(
                delete(conversation_file_scopes).where(
                    conversation_file_scopes.c.conversation_id
                    == str(conversation_id),
                ),
            )
            await connection.execute(
                delete(conversations).where(
                    conversations.c.conversation_id == str(conversation_id),
                ),
            )

        return True


def _to_conversation(row: Mapping[str, object]) -> Conversation:
    return Conversation(
        conversation_id=ConversationId(_required_str(row, "conversation_id")),
        user_id=UserId(_required_str(row, "user_id")),
        created_at=_required_datetime(row, "created_at"),
        updated_at=_required_datetime(row, "updated_at"),
        title=_optional_str(row, "title"),
    )


def _to_message(row: Mapping[str, object]) -> UserMessage | AssistantMessage:
    message_id = MessageId(_required_str(row, "message_id"))
    conversation_id = ConversationId(_required_str(row, "conversation_id"))
    content = _required_str(row, "content")
    created_at = _required_datetime(row, "created_at")
    role = _required_str(row, "role")

    if role == "user":
        return UserMessage(
            message_id=message_id,
            conversation_id=conversation_id,
            content=content,
            created_at=created_at,
        )
    if role == "assistant":
        return AssistantMessage(
            message_id=message_id,
            conversation_id=conversation_id,
            content=content,
            created_at=created_at,
        )

    raise RuntimeError(f"unknown persisted message role: {role}")


def _required_str(row: Mapping[str, object], field: str) -> str:
    value = row[field]
    if not isinstance(value, str):
        raise RuntimeError(f"persisted {field} must be a string")
    return value


def _optional_str(row: Mapping[str, object], field: str) -> str | None:
    value = row[field]
    if value is None:
        return None
    if not isinstance(value, str):
        raise RuntimeError(f"persisted {field} must be a string or null")
    return value


def _required_datetime(row: Mapping[str, object], field: str) -> datetime:
    value = row[field]
    if not isinstance(value, datetime):
        raise RuntimeError(f"persisted {field} must be a datetime")
    return _to_utc(value)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
