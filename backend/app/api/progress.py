from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import ProgressPoint
from app.services.progress import progress_series

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=list[ProgressPoint])
def get_progress(
    exercise: str | None = None,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProgressPoint]:
    return progress_series(db, exercise, user_id=user.id)
