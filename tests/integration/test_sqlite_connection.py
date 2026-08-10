import asyncio
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import command
from asagent.storage.sqlite.connection import create_sqlite_async_engine
from asagent.storage.sqlite.schema import users


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


async def _insert_user(engine: AsyncEngine, user_id: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            users.insert().values(
                user_id=user_id,
                created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
            ),
        )


@pytest.mark.asyncio
async def test_configures_sqlite_connection_pragmas(tmp_path: Path) -> None:
    engine = create_sqlite_async_engine(tmp_path / "asagent.sqlite3")

    try:
        async with engine.connect() as connection:
            assert await connection.scalar(sa.text("PRAGMA foreign_keys")) == 1
            assert await connection.scalar(sa.text("PRAGMA journal_mode")) == "wal"
            assert await connection.scalar(sa.text("PRAGMA busy_timeout")) == 5_000
            assert await connection.scalar(sa.text("PRAGMA synchronous")) == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_transaction_rolls_back_after_an_exception(tmp_path: Path) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)
    engine = create_sqlite_async_engine(database_path)

    try:
        with pytest.raises(RuntimeError, match="rollback"):
            async with engine.begin() as connection:
                await connection.execute(
                    users.insert().values(
                        user_id="rolled-back-user",
                        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
                    ),
                )
                raise RuntimeError("rollback")

        async with engine.connect() as connection:
            persisted_user = await connection.scalar(
                sa.select(users.c.user_id).where(
                    users.c.user_id == "rolled-back-user",
                ),
            )

        assert persisted_user is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_writer_waits_for_a_short_lived_write_lock(tmp_path: Path) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)
    lock_holder = create_sqlite_async_engine(database_path)
    waiting_writer = create_sqlite_async_engine(database_path)
    write_task: asyncio.Task[None] | None = None

    try:
        async with lock_holder.connect() as locked_connection:
            await locked_connection.execute(sa.text("BEGIN IMMEDIATE"))
            await locked_connection.execute(
                users.insert().values(
                    user_id="lock-holder",
                    created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
                ),
            )

            write_task = asyncio.create_task(
                _insert_user(waiting_writer, "waiting-writer"),
            )
            await asyncio.sleep(0.05)

            assert not write_task.done()

            await locked_connection.commit()
            await asyncio.wait_for(write_task, timeout=1)

        async with waiting_writer.connect() as connection:
            persisted_user = await connection.scalar(
                sa.select(users.c.user_id).where(
                    users.c.user_id == "waiting-writer",
                ),
            )

        assert persisted_user == "waiting-writer"
    finally:
        if write_task is not None and not write_task.done():
            write_task.cancel()
            with suppress(asyncio.CancelledError):
                await write_task

        await lock_holder.dispose()
        await waiting_writer.dispose()
