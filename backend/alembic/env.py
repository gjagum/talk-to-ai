"""Async Alembic environment for the Talk-to-AI backend.

Wires Alembic to the same SQLAlchemy async engine + declarative Base that the
app uses. The DB URL comes from `app.core.config.Config.DATABASE_URL` (env
driven) so prod secrets never need to live in `alembic.ini`.

IMPORTANT: every feature's `models` module must be imported below so its
tables register on `Base.metadata` before `target_metadata` is captured.
Forgetting an import is the #1 cause of autogenerate missing tables.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# App wiring — must be importable (run from backend/ dir or with -m app.main).
from app.core.config import Config
from app.core.database import Base

# Import every models module so their tables register on Base.metadata.
# (Each module is a noqa since the import side-effect is what we want.)
import app.features.booking.models  # noqa: F401
import app.features.menu.models  # noqa: F401
# These two land in Phase 2/3 — uncomment/keep as they're created:
import app.features.auth.models  # noqa: F401
import app.features.agent_management.models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject DB URL from app config (single source of truth).
# Escaping `%` → `%%` so ConfigParser interpolation doesn't choke on
# URL-encoded characters in the password (e.g. `%40` for `@`).
config.set_main_option("sqlalchemy.url", Config.DATABASE_URL.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout, no DB connection).

    Used for `alembic upgrade head --sql`. URL must be the sync form for the
    offline dialect renderer, but our URL is asyncpg. We strip the `+asyncpg`
    driver so offline rendering uses plain postgresql.
    """
    url = Config.DATABASE_URL.replace("+asyncpg", "")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode against the live DB via async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
