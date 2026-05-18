"""Async SQLAlchemy engine and session factory.

Also exposes a lazily-initialised synchronous session factory
(``get_sync_session``) for code paths that cannot run on the asyncio loop —
most notably Celery ``task_failure`` signal handlers, which fire from the
worker's main thread outside any running event loop. The sync engine is
created on first use so importing this module from async-only contexts
(API, async tasks) does not open an idle psycopg2 pool.
"""

from collections.abc import AsyncGenerator
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
    pool_timeout=30,
    pool_recycle=1800,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# --- Sync session (Celery signal handlers, scripts) --------------------------

_sync_engine = None
_sync_session_factory = None


def _ensure_sync_factory() -> None:
    """Lazily create the sync engine/sessionmaker on first use."""
    global _sync_engine, _sync_session_factory
    if _sync_session_factory is not None:
        return
    sync_url = settings.DATABASE_URL_SYNC or settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
    _sync_engine = create_engine(
        sync_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
    )
    _sync_session_factory = sessionmaker(_sync_engine, expire_on_commit=False, class_=Session)


@contextmanager
def get_sync_session() -> Iterator[Session]:
    """Yield a sync SQLAlchemy Session. Caller commits/rollbacks explicitly.

    Intended for Celery signal handlers and other non-async contexts. The
    Celery worker process is not running an asyncio loop when ``task_failure``
    fires, so we cannot reuse ``async_session_factory`` there.
    """
    _ensure_sync_factory()
    assert _sync_session_factory is not None
    session = _sync_session_factory()
    try:
        yield session
    finally:
        session.close()
