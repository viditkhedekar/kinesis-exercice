"""Shared pytest fixtures.

Provides an in-memory SQLite database session for the pipeline/API tests that
need persistence (Live Camera Mode). Pure-engine tests don't use these.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401 — register models on Base.metadata
from app.db import Base


@pytest.fixture()
def db():
    # StaticPool + check_same_thread=False so the single in-memory DB is shared
    # across the TestClient's worker threads (FastAPI runs sync deps in a pool).
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
