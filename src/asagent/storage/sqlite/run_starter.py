from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from asagent.core.conversation import Conversation
from asagent.core.messages import UserMessage
from asagent.core.run import Run
from asagent.storage.sqlite.connection import create_sqlite_async_engine
from asagent.storage.sqlite.schema import conversations, messages, runs


class SqliteRunStarter:
    def __init__(self, database_path: Path) -> None:
        self._engine = create_sqlite_async_engine(database_path)

    async def aclose(self) -> None:
        await self._engine.dispose()

    async def start(
        self,
        *,
        conversation: Conversation,
        user_message: UserMessage,
        run: Run,
    ) -> None:
        if (
            conversation.conversation_id != user_message.conversation_id
            or conversation.conversation_id != run.conversation_id
        ):
            raise ValueError(
                "conversation, user message, and run must belong together",
            )

        next_sequence = (
            select(func.coalesce(func.max(messages.c.sequence), 0) + 1)
            .where(messages.c.conversation_id == str(run.conversation_id))
            .scalar_subquery()
        )

        async with self._engine.begin() as connection:
            conversation_exists = await connection.scalar(
                select(conversations.c.conversation_id).where(
                    conversations.c.conversation_id == str(run.conversation_id),
                ),
            )
            if conversation_exists is None:
                raise ValueError("cannot start a run for an unknown conversation")

            await connection.execute(
                conversations.update()
                .where(
                    conversations.c.conversation_id
                    == str(conversation.conversation_id),
                )
                .values(
                    title=conversation.title,
                    last_page_url=conversation.last_page_url,
                    last_page_title=conversation.last_page_title,
                    updated_at=_to_utc(conversation.updated_at),
                ),
            )
            await connection.execute(
                messages.insert().values(
                    message_id=str(user_message.message_id),
                    conversation_id=str(user_message.conversation_id),
                    sequence=next_sequence,
                    role="user",
                    content=user_message.content,
                    created_at=_to_utc(user_message.created_at),
                ),
            )
            await connection.execute(
                runs.insert().values(
                    run_id=str(run.run_id),
                    conversation_id=str(run.conversation_id),
                    status=run.status.value,
                    created_at=_to_utc(run.created_at),
                    updated_at=_to_utc(run.updated_at),
                ),
            )


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
