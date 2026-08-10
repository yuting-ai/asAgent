from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select, update

from asagent.core.messages import AssistantMessage
from asagent.core.run import Run
from asagent.storage.sqlite.connection import create_sqlite_async_engine
from asagent.storage.sqlite.schema import conversations, messages, runs


class SqliteRunFinisher:
    def __init__(self, database_path: Path) -> None:
        self._engine = create_sqlite_async_engine(database_path)

    async def aclose(self) -> None:
        await self._engine.dispose()

    async def finish(
        self,
        *,
        run: Run,
        assistant_message: AssistantMessage | None,
    ) -> None:
        if not run.status.is_terminal:
            raise ValueError("a finished run must have a terminal status")

        if (
            assistant_message is not None
            and assistant_message.conversation_id != run.conversation_id
        ):
            raise ValueError(
                "assistant message and run must belong to the same conversation",
            )

        next_sequence = (
            select(func.coalesce(func.max(messages.c.sequence), 0) + 1)
            .where(messages.c.conversation_id == str(run.conversation_id))
            .scalar_subquery()
        )

        async with self._engine.begin() as connection:
            persisted_conversation_id = await connection.scalar(
                select(runs.c.conversation_id).where(
                    runs.c.run_id == str(run.run_id),
                ),
            )
            if persisted_conversation_id is None:
                raise ValueError("cannot finish an unknown run")
            if persisted_conversation_id != str(run.conversation_id):
                raise ValueError(
                    "run conversation_id does not match the persisted run",
                )

            if assistant_message is not None:
                conversation_exists = await connection.scalar(
                    select(conversations.c.conversation_id).where(
                        conversations.c.conversation_id
                        == str(assistant_message.conversation_id),
                    ),
                )
                if conversation_exists is None:
                    raise ValueError(
                        "cannot append a message to an unknown conversation",
                    )

                await connection.execute(
                    messages.insert().values(
                        message_id=str(assistant_message.message_id),
                        conversation_id=str(assistant_message.conversation_id),
                        sequence=next_sequence,
                        role="assistant",
                        content=assistant_message.content,
                        created_at=_to_utc(assistant_message.created_at),
                    ),
                )

            await connection.execute(
                update(runs)
                .where(runs.c.run_id == str(run.run_id))
                .values(
                    status=run.status.value,
                    updated_at=_to_utc(run.updated_at),
                ),
            )


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
