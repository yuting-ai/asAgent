from pathlib import Path

import pytest
import sqlalchemy as sa

from alembic import command
from asagent.paths import AppPaths
from asagent.storage.sqlite import database


def _alembic_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "alembic.ini"


def test_upgrade_creates_database_in_app_data_directory_and_is_repeatable(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app-home")
    database_path = paths.data_dir / "asagent.sqlite3"

    database.upgrade_sqlite_database(
        database_path=database_path,
        alembic_config_path=_alembic_config_path(),
    )
    database.upgrade_sqlite_database(
        database_path=database_path,
        alembic_config_path=_alembic_config_path(),
    )

    assert database_path.is_file()

    engine = sa.create_engine(f"sqlite+pysqlite:///{database_path}")
    try:
        inspector = sa.inspect(engine)
        assert {
            "users",
            "conversations",
            "messages",
            "runs",
            "run_events",
            "tool_calls",
            "connections",
            "schema_migrations",
        }.issubset(inspector.get_table_names())

        with engine.connect() as connection:
            revisions = (
                connection.execute(
                    sa.text("SELECT version_num FROM schema_migrations"),
                )
                .scalars()
                .all()
            )

        assert len(revisions) == 1
    finally:
        engine.dispose()


def test_upgrade_propagates_migration_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "data" / "asagent.sqlite3"

    def fail_upgrade(config: object, revision: str) -> None:
        del config, revision
        raise RuntimeError("migration failed")

    monkeypatch.setattr(command, "upgrade", fail_upgrade)

    with pytest.raises(RuntimeError, match="migration failed"):
        database.upgrade_sqlite_database(
            database_path=database_path,
            alembic_config_path=_alembic_config_path(),
        )

    assert database_path.parent.is_dir()
