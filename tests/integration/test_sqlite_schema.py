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
        knowledge_document_checks = inspector.get_check_constraints(
            "knowledge_documents"
        )
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
        "knowledge_chunk_embeddings",
        "knowledge_chunks",
        "knowledge_conversations",
        "knowledge_documents",
        "knowledge_index_jobs",
        "knowledge_index_profiles",
        "knowledge_libraries",
        "knowledge_retrieval_hits",
        "knowledge_sources",
        "messages",
        "run_events",
        "runs",
        "schema_migrations",
        "tool_calls",
        "users",
    }
    assert {"last_page_url", "last_page_title"} <= conversation_columns
    file_type_check = next(
        constraint["sqltext"]
        for constraint in knowledge_document_checks
        if constraint["name"] == "knowledge_document_file_type_valid"
    )
    assert "'docx'" in file_type_check
    assert "'html'" in file_type_check


def test_docx_html_migration_preserves_existing_knowledge_documents(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    config = _alembic_config(database_path)
    command.upgrade(config, "20260831_12")
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
                    "INSERT INTO knowledge_libraries "
                    "(library_id, user_id, name, normalized_name, status, "
                    "created_at, updated_at) VALUES "
                    "('library-1', 'local-user', 'Research', 'research', 'active', "
                    ":time, :time)"
                ),
                {"time": timestamp},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO knowledge_sources "
                    "(source_id, library_id, display_path, canonical_path, status, "
                    "scan_status, created_at, updated_at) VALUES "
                    "('source-1', 'library-1', '/Research', '/Research', 'active', "
                    "'ready', :time, :time)"
                ),
                {"time": timestamp},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO knowledge_documents "
                    "(document_id, source_id, relative_path, file_type, status, "
                    "size_bytes, mtime_ns, content_hash, parser_version, "
                    "current_chunker_version, created_at, updated_at) VALUES "
                    "('document-text', 'source-1', 'notes.txt', 'text', 'active', "
                    "10, 1, 'hash-text', 'v1', 'v1', :time, :time)"
                ),
                {"time": timestamp},
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = sa.create_engine(f"sqlite+pysqlite:///{database_path}")
    try:
        with engine.begin() as connection:
            for document_id, relative_path, file_type in (
                ("document-docx", "report.docx", "docx"),
                ("document-html", "article.html", "html"),
            ):
                connection.execute(
                    sa.text(
                        "INSERT INTO knowledge_documents "
                        "(document_id, source_id, relative_path, file_type, status, "
                        "size_bytes, mtime_ns, content_hash, parser_version, "
                        "current_chunker_version, created_at, updated_at) VALUES "
                        "(:document_id, 'source-1', :relative_path, :file_type, "
                        "'active', 10, 1, :content_hash, 'v2', 'v1', :time, :time)"
                    ),
                    {
                        "document_id": document_id,
                        "relative_path": relative_path,
                        "file_type": file_type,
                        "content_hash": f"hash-{file_type}",
                        "time": timestamp,
                    },
                )
            rows = connection.execute(
                sa.text(
                    "SELECT document_id, file_type FROM knowledge_documents "
                    "ORDER BY document_id"
                )
            ).all()
    finally:
        engine.dispose()

    assert [(row[0], row[1]) for row in rows] == [
        ("document-docx", "docx"),
        ("document-html", "html"),
        ("document-text", "text"),
    ]


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
