"""physIQal FastAPI application."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import (
    auth_router,
    compare_router,
    exercises_router,
    live_router,
    progress_router,
    sessions_router,
    stats_router,
)
from app.config import get_settings
from app.db import SessionLocal
from app.exercises import available_exercises
from app.models import Exercise


def seed_exercises() -> None:
    """Mirror the YAML exercise configs into the DB (idempotent)."""
    db = SessionLocal()
    try:
        existing = {e.key for e in db.scalars(select(Exercise)).all()}
        for cfg in available_exercises():
            if cfg.key not in existing:
                db.add(Exercise(key=cfg.key, name=cfg.name, config_path=f"{cfg.key}.yaml"))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_exercises()
    yield


app = FastAPI(title="physIQal API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(exercises_router)
app.include_router(live_router)
app.include_router(sessions_router)
app.include_router(progress_router)
app.include_router(compare_router)
app.include_router(stats_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
