from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Session, User
from app.schemas import CompareOut, CompareRequest, CompareSide

router = APIRouter(prefix="/compare", tags=["compare"])


def _side(db: DbSession, session_id: int, user: User) -> CompareSide:
    session = db.get(Session, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(404, f"Session {session_id} not found")
    scores = [r.score for r in session.reps]
    fault_counter: Counter[str] = Counter()
    for rep in session.reps:
        for f in rep.faults:
            fault_counter[f.type] += 1
    return CompareSide(
        session_id=session_id,
        exercise_key=session.exercise_key,
        avg_score=round(sum(scores) / len(scores), 1) if scores else 0.0,
        rep_count=len(session.reps),
        fault_summary=dict(fault_counter),
    )


@router.post("", response_model=CompareOut)
def compare(
    req: CompareRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CompareOut:
    return CompareOut(a=_side(db, req.session_a, user), b=_side(db, req.session_b, user))
