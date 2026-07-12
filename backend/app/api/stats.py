from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models import (
    Exercise,
    Fault,
    ProgressSnapshot,
    Rep,
    Session,
    SessionStatus,
    User,
)
from app.schemas import StatBest, StatFault, StatPoint, StatRecent, StatsOut

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=StatsOut)
def get_stats(db: DbSession = Depends(get_db), user: User = Depends(get_current_user)) -> StatsOut:
    names = {e.key: e.name for e in db.scalars(select(Exercise)).all()}

    sessions = db.scalars(
        select(Session).where(Session.user_id == user.id).order_by(Session.created_at.desc())
    ).all()
    completed = [s for s in sessions if s.status == SessionStatus.complete]
    # Completed sessions that actually produced a trustworthy score (untrustworthy
    # clips store NULL and must not drag down or spike averages/trends).
    scored = [s for s in completed if s.overall_score is not None]

    # Recent (any status, so processing sessions show too).
    recent = [
        StatRecent(
            session_id=s.id,
            exercise_key=s.exercise_key,
            exercise_name=names.get(s.exercise_key, s.exercise_key),
            overall_score=s.overall_score,
            grade=(s.summary or {}).get("grade", "") if s.summary else "",
            status=s.status.value,
            created_at=s.created_at,
        )
        for s in sessions[:8]
    ]

    # Score trend over time (oldest -> newest); scoreless sessions are omitted.
    trend = [
        StatPoint(created_at=s.created_at, score=s.overall_score)
        for s in sorted(scored, key=lambda x: x.created_at)
    ]

    # Exercise breakdown.
    breakdown = Counter(s.exercise_key for s in completed)

    # Most common faults across the user's reps.
    fault_rows = db.execute(
        select(Fault.type, func.count(Fault.id))
        .join(Rep, Rep.id == Fault.rep_id)
        .join(Session, Session.id == Rep.session_id)
        .where(Session.user_id == user.id)
        .group_by(Fault.type)
        .order_by(func.count(Fault.id).desc())
        .limit(6)
    ).all()
    common_faults = [StatFault(type=t, count=c) for t, c in fault_rows]

    # Personal best technique score per exercise.
    best_rows = db.execute(
        select(ProgressSnapshot.exercise_key, func.max(ProgressSnapshot.avg_score))
        .join(Session, Session.id == ProgressSnapshot.session_id)
        .where(Session.user_id == user.id)
        .group_by(ProgressSnapshot.exercise_key)
    ).all()
    personal_bests = sorted(
        (
            StatBest(exercise_key=k, exercise_name=names.get(k, k), best_score=round(v, 1))
            for k, v in best_rows
            if v is not None
        ),
        key=lambda b: b.best_score,
        reverse=True,
    )

    # This week (count all completed; average over scored only).
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    week = [s for s in completed if s.created_at and _aware(s.created_at) >= week_ago]
    week_scored = [s for s in week if s.overall_score is not None]
    week_avg = round(sum(s.overall_score for s in week_scored) / len(week_scored), 1) if week_scored else 0.0
    avg = round(sum(s.overall_score for s in scored) / len(scored), 1) if scored else 0.0

    return StatsOut(
        total_sessions=len(sessions),
        completed=len(completed),
        avg_score=avg,
        week_sessions=len(week),
        week_avg=week_avg,
        recent=recent,
        trend=trend,
        exercise_breakdown=dict(breakdown),
        common_faults=common_faults,
        personal_bests=personal_bests,
    )


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
