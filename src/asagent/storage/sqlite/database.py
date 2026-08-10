from pathlib import Path

from alembic.config import Config

from alembic import command


def upgrade_sqlite_database(
    *,
    database_path: Path,
    alembic_config_path: Path,
) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)

    config = Config(str(alembic_config_path))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite+pysqlite:///{database_path.resolve()}",
    )
    command.upgrade(config, "head")
