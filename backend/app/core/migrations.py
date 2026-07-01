"""Run Alembic migrations programmatically.

Used by `app.main` lifespan to keep the DB schema current on container
startup, instead of leaving ops teams to manually run `alembic upgrade head`
in a sidecar container. This reuses the same `alembic.ini` + `alembic/env.py`
the operator would use directly.

For local dev that does not need migrations, set `USE_CREATE_ALL=true` in env
to fall back to `Base.metadata.create_all` (faster, but cannot evolve the
schema of existing tables).
"""
import concurrent.futures
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig

from app.core.config import Config as AppConfig

log = logging.getLogger("alembic.runtime")


def _make_alembic_cfg() -> AlembicConfig:
    """Build an Alembic Config pointing at our alembic.ini + project root."""
    # alembic.ini lives at backend/alembic.ini and the package is run from
    # backend/ (fastapi run is invoked from there per Dockerfile).
    ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    cfg = AlembicConfig(str(ini_path))
    # Python's ConfigParser treats `%` as an interpolation marker.  URL-encoded
    # characters in a password (e.g. `%40` for `@`) trigger interpolation errors.
    # Escaping `%` → `%%` tells ConfigParser to keep a literal `%`.
    cfg.set_main_option("sqlalchemy.url", AppConfig.DATABASE_URL.replace("%", "%%"))
    return cfg


def upgrade_head() -> None:
    """Run `alembic upgrade head` in a thread-safe way.

    `command.upgrade` eventually causes `env.py` to call `asyncio.run()`,
    which fails if called inside an already-running event loop (e.g. from
    FastAPI's async lifespan).  Running it in a thread provides a clean
    thread with no existing loop.
    """
    cfg = _make_alembic_cfg()
    log.info("Running Alembic `upgrade head` ...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(command.upgrade, cfg, "head").result()
    log.info("Alembic migrations complete.")
