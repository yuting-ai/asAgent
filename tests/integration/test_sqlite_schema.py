from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command


def _alembic_config(database_path: Path) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    return config


def _upgrade(database_path: Path) -> sa.Engine:
    command.upgrade(_alembic_config(database_path), "head")
    return sa.create_engine(f"sqlite+pysqlite:///{database_path}")


def _utc_timestamp() -> str:
    return "2026-08-09T12:00:00+00:00"


def test_upgrade_from_empty_database_creates_initial_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "asagent.sqlite3"

    command.upgrade(_alembic_config(database_path), "head")
    command.upgrade(_alembic_config(database_path), "head")

    engine = sa.create_engine(f"sqlite+pysqlite:///{database_path}")
    try:
        table_names = set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert table_names == {
        "connections",
        "conversation_file_scopes",
        "conversations",
        "file_changes",
        "messages",
        "run_events",
        "runs",
        "schema_migrations",
        "tool_calls",
        "users",
    }


def test_initial_schema_enforces_foreign_keys_and_invariants(tmp_path: Path) -> None:
    engine = _upgrade(tmp_path / "asagent.sqlite3")
    timestamp = _utc_timestamp()

    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys = ON")

            with pytest.raises(sa.exc.IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        sa.text(
                            "INSERT INTO conversations "
                            "(conversation_id, user_id, created_at, updated_at) "
                            "VALUES ('conversation-missing-user', 'missing-user', :time, :time)"
                        ),
                        {"time": timestamp},
                    )

            connection.execute(
                sa.text(
                    "INSERT INTO users (user_id, created_at) "
                    "VALUES ('local-user', :time)"
                ),
                {"time": timestamp},
            )

            with pytest.raises(sa.exc.IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        sa.text(
                            "INSERT INTO connections "
                            "(connection_id, user_id, service_id, account_label, "
                            "granted_scopes_json, status, created_at, updated_at) "
                            "VALUES ('connection-missing-user', 'missing-user', "
                            "'gmail', 'Primary', '[]', 'active', :time, :time)"
                        ),
                        {"time": timestamp},
                    )

            with pytest.raises(sa.exc.IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        sa.text(
                            "INSERT INTO connections "
                            "(connection_id, user_id, service_id, account_label, "
                            "granted_scopes_json, status, created_at, updated_at) "
                            "VALUES ('connection-invalid-status', 'local-user', "
                            "'gmail', 'Primary', '[]', 'revoked', :time, :time)"
                        ),
                        {"time": timestamp},
                    )
            connection.execute(
                sa.text(
                    "INSERT INTO conversations "
                    "(conversation_id, user_id, created_at, updated_at) "
                    "VALUES ('conversation-1', 'local-user', :time, :time)"
                ),
                {"time": timestamp},
            )

            with pytest.raises(sa.exc.IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        sa.text(
                            "INSERT INTO conversation_file_scopes "
                            "(conversation_id, additional_roots_json, "
                            "additional_files_json) "
                            "VALUES ('missing-conversation', '[]', '[]')"
                        ),
                    )

            connection.execute(
                sa.text(
                    "INSERT INTO runs "
                    "(run_id, conversation_id, status, created_at, updated_at) "
                    "VALUES ('run-1', 'conversation-1', 'created', :time, :time)"
                ),
                {"time": timestamp},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO messages "
                    "(message_id, conversation_id, sequence, role, content, created_at) "
                    "VALUES ('message-1', 'conversation-1', 1, 'user', 'hello', :time)"
                ),
                {"time": timestamp},
            )

            with pytest.raises(sa.exc.IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        sa.text(
                            "INSERT INTO messages "
                            "(message_id, conversation_id, sequence, role, content, created_at) "
                            "VALUES ('message-2', 'conversation-1', 1, 'assistant', 'hi', :time)"
                        ),
                        {"time": timestamp},
                    )

            connection.execute(
                sa.text(
                    "INSERT INTO run_events "
                    "(event_id, run_id, sequence, event_type, created_at, data_json) "
                    "VALUES ('event-1', 'run-1', 1, 'run.started', :time, '{}')"
                ),
                {"time": timestamp},
            )

            with pytest.raises(sa.exc.IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        sa.text(
                            "INSERT INTO run_events "
                            "(event_id, run_id, sequence, event_type, created_at, data_json) "
                            "VALUES ('event-2', 'run-1', 1, 'run.started', :time, '{}')"
                        ),
                        {"time": timestamp},
                    )

            with pytest.raises(sa.exc.IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        sa.text(
                            "INSERT INTO tool_calls "
                            "(tool_call_id, run_id, model_call_id, tool_id, arguments_json, "
                            "result, error, created_at, completed_at) "
                            "VALUES ('tool-call-1', 'run-1', 'model-call-1', 'builtin.echo', "
                            "'{}', 'result', 'error', :time, :time)"
                        ),
                        {"time": timestamp},
                    )
    finally:
        engine.dispose()
