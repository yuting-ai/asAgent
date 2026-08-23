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
        inspector = sa.inspect(engine)
        table_names = set(inspector.get_table_names())
        conversation_columns = {
            column["name"] for column in inspector.get_columns("conversations")
        }
    finally:
        engine.dispose()

    assert table_names == {
        "automation_executions",
        "automation_triggers",
        "automations",
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
    assert {"last_page_url", "last_page_title"} <= conversation_columns


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
                            "INSERT INTO conversations "
                            "(conversation_id, user_id, kind, created_at, updated_at) "
                            "VALUES ('conversation-invalid-kind', 'local-user', "
                            "'email', :time, :time)"
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


def test_execution_kind_migration_hides_existing_scheduled_run_conversations(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    config = _alembic_config(database_path)
    command.upgrade(config, "20260820_10")
    timestamp = _utc_timestamp()
    engine = sa.create_engine(f"sqlite+pysqlite:///{database_path}")

    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO users (user_id, created_at) "
                    "VALUES ('local-user', :time)"
                ),
                {"time": timestamp},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO conversations "
                    "(conversation_id, user_id, kind, created_at, updated_at) "
                    "VALUES ('scheduled-conversation', 'local-user', 'chat', :time, :time)"
                ),
                {"time": timestamp},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO runs "
                    "(run_id, conversation_id, status, created_at, updated_at) "
                    "VALUES ('scheduled-run', 'scheduled-conversation', 'created', :time, :time)"
                ),
                {"time": timestamp},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO automations "
                    "(automation_id, user_id, name, plan_summary, "
                    "allowed_capabilities_json, status, created_at, updated_at) "
                    "VALUES ('automation-1', 'local-user', 'Report', 'Read it', "
                    "'[]', 'active', :time, :time)"
                ),
                {"time": timestamp},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO automation_triggers "
                    "(automation_trigger_id, automation_id, kind, timezone, local_time, "
                    "weekday, next_run_at, enabled, created_at, updated_at) "
                    "VALUES ('trigger-1', 'automation-1', 'daily', 'UTC', '09:00', "
                    "NULL, :time, 1, :time, :time)"
                ),
                {"time": timestamp},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO automation_executions "
                    "(automation_execution_id, automation_id, automation_trigger_id, "
                    "scheduled_for, status, claimed_at, run_id, completed_at) "
                    "VALUES ('execution-1', 'automation-1', 'trigger-1', :time, "
                    "'claimed', :time, 'scheduled-run', NULL)"
                ),
                {"time": timestamp},
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    migrated_engine = sa.create_engine(f"sqlite+pysqlite:///{database_path}")
    try:
        with migrated_engine.connect() as connection:
            kind = connection.scalar(
                sa.text(
                    "SELECT kind FROM conversations "
                    "WHERE conversation_id = 'scheduled-conversation'"
                )
            )
    finally:
        migrated_engine.dispose()

    assert kind == "automation_execution"
