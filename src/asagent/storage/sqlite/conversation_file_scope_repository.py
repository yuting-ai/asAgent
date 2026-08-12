import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from asagent.core.conversation_file_scope import ConversationFileScope
from asagent.core.ids import ConversationId
from asagent.storage.sqlite.connection import create_sqlite_async_engine
from asagent.storage.sqlite.schema import conversation_file_scopes, conversations


class SqliteConversationFileScopeRepository:
    def __init__(self, database_path: Path) -> None:
        self._engine = create_sqlite_async_engine(database_path)

    async def aclose(self) -> None:
        await self._engine.dispose()

    async def get(self, conversation_id: ConversationId) -> ConversationFileScope:
        async with self._engine.connect() as database_connection:
            result = await database_connection.execute(
                select(conversation_file_scopes).where(
                    conversation_file_scopes.c.conversation_id == str(conversation_id),
                ),
            )
            row = result.mappings().one_or_none()

        if row is None:
            return ConversationFileScope(conversation_id=conversation_id)
        return _to_scope(dict(row))

    async def save(self, scope: ConversationFileScope) -> None:
        async with self._engine.begin() as database_connection:
            conversation_exists = await database_connection.scalar(
                select(conversations.c.conversation_id).where(
                    conversations.c.conversation_id == str(scope.conversation_id),
                ),
            )
            if conversation_exists is None:
                raise ValueError("cannot save a file scope for an unknown conversation")

            if not scope.additional_roots and not scope.additional_files:
                await database_connection.execute(
                    conversation_file_scopes.delete().where(
                        conversation_file_scopes.c.conversation_id
                        == str(scope.conversation_id),
                    ),
                )
                return

            await database_connection.execute(
                sqlite_insert(conversation_file_scopes)
                .values(
                    conversation_id=str(scope.conversation_id),
                    additional_roots_json=_serialize_paths(scope.additional_roots),
                    additional_files_json=_serialize_paths(scope.additional_files),
                )
                .on_conflict_do_update(
                    index_elements=[conversation_file_scopes.c.conversation_id],
                    set_={
                        "additional_roots_json": _serialize_paths(
                            scope.additional_roots
                        ),
                        "additional_files_json": _serialize_paths(
                            scope.additional_files
                        ),
                    },
                ),
            )


def _to_scope(row: Mapping[str, object]) -> ConversationFileScope:
    return ConversationFileScope(
        conversation_id=ConversationId(_required_str(row, "conversation_id")),
        additional_roots=_deserialize_paths(
            _required_str(row, "additional_roots_json"),
        ),
        additional_files=_deserialize_paths(
            _required_str(row, "additional_files_json"),
        ),
    )


def _serialize_paths(paths: tuple[Path, ...]) -> str:
    return json.dumps([str(path) for path in paths], separators=(",", ":"))


def _deserialize_paths(serialized: str) -> tuple[Path, ...]:
    try:
        values: object = json.loads(serialized)
    except json.JSONDecodeError as error:
        raise RuntimeError("persisted conversation file scope is invalid") from error

    if not isinstance(values, list) or any(
        not isinstance(value, str) for value in values
    ):
        raise RuntimeError("persisted conversation file scope is invalid")
    return tuple(Path(cast(str, value)) for value in values)


def _required_str(row: Mapping[str, object], name: str) -> str:
    value = row.get(name)
    if not isinstance(value, str):
        raise RuntimeError(
            f"persisted conversation file scope field is invalid: {name}"
        )
    return value
