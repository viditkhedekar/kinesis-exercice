"""SQLAlchemy engine, session factory, and declarative base.

Production runs against **Neon** (serverless Postgres). Neon's compute
auto-suspends after an idle period and cold-starts on the next connection, which
breaks two assumptions a naive pool makes: that a checked-in connection is still
alive, and that connecting is instant. The engine below is configured for that —
see ``_engine_kwargs``. SQLite (tests) takes a separate, minimal path.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

DATABASE_URL = settings.normalized_database_url()


def _engine_kwargs(url: str) -> dict:
    """Engine options for the resolved database URL.

    ``pool_pre_ping`` issues a cheap liveness check on checkout so a connection
    dropped by Neon's auto-suspend is transparently replaced instead of raising
    mid-request. ``pool_recycle`` retires connections well before that idle
    timeout so the pre-ping rarely has to. The libpq keepalive settings stop a
    long-running analysis (a single request can hold a connection for tens of
    seconds) from having its idle connection reaped by an intermediate NAT.
    """
    kwargs: dict = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        return kwargs
    kwargs.update(
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
        connect_args={
            "connect_timeout": settings.db_connect_timeout,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
            "application_name": "kinesis-backend",
        },
    )
    return kwargs


engine = create_engine(DATABASE_URL, **_engine_kwargs(DATABASE_URL))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
