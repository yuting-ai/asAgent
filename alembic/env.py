from sqlalchemy import create_engine, pool

from alembic import context
from asagent.storage.sqlite.schema import metadata

config = context.config
target_metadata = metadata


def _database_url() -> str:
    database_url = config.get_main_option("sqlalchemy.url")
    if not database_url:
        raise RuntimeError("Alembic requires an explicit sqlalchemy.url")
    return database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="schema_migrations",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)

    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                version_table="schema_migrations",
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
