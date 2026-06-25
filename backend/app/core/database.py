"""Async database engine + session + declarative base.

Foundation for all persisted domains (currently: booking). Reuses the
DATABASE_URL wired in app.core.config. Exposes:

  - `engine`     : the async SQLAlchemy engine
  - `AsyncSessionLocal` : async sessionmaker factory
  - `Base`       : declarative base every model inherits from
  - `get_db()`   : FastAPI dependency yielding an AsyncSession
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.core.config import Config

engine = create_async_engine(Config.DATABASE_URL, echo=False, future=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Shared declarative base. Import this in every feature's models.py, then
# Base.metadata.create_all is invoked from app.main on startup.
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a scoped async session and rolls back
    on error. Inject with `session: AsyncSession = Depends(get_db)`.

    Note: For database-modifying endpoints, the endpoint is responsible for
    `await session.commit()` after its changes; this dependency only commits
    on clean exit if you set `autocommit_on_success`. By convention we do
    explicit commits in service.py.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
