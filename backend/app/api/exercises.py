from __future__ import annotations

from fastapi import APIRouter

from app.exercises import available_exercises
from app.schemas import ExerciseOut

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("", response_model=list[ExerciseOut])
def list_exercises() -> list[ExerciseOut]:
    return [ExerciseOut(key=e.key, name=e.name, filming=e.filming) for e in available_exercises()]
