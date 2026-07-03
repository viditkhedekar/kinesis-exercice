"""Progress aggregation + Ghost Replay (personal-best phase-aligned skeleton)."""
from __future__ import annotations

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models import (
    AnalysisArtifact,
    ProgressSnapshot,
    Rep,
    Session,
    SessionStatus,
)
from app.schemas import GhostOut, ProgressPoint
from app.services.pose import load_landmarks
from app.services.pose.landmarks import NUM_LANDMARKS, POSE_EDGES

GHOST_PHASE_SAMPLES = 100


def upsert_progress(db: DbSession, session_id: int) -> ProgressSnapshot:
    reps = db.scalars(select(Rep).where(Rep.session_id == session_id)).all()
    session = db.get(Session, session_id)
    scores = [r.score for r in reps]
    snap = db.scalar(select(ProgressSnapshot).where(ProgressSnapshot.session_id == session_id))
    if snap is None:
        snap = ProgressSnapshot(session_id=session_id, exercise_key=session.exercise_key)
        db.add(snap)
    snap.exercise_key = session.exercise_key
    snap.rep_count = len(reps)
    # Track the overall technique score (grouped/prevalence-weighted), not the
    # raw per-rep mean, so progress reflects how the report scores the session.
    snap.avg_score = session.overall_score or (round(float(np.mean(scores)), 1) if scores else 0.0)
    snap.best_score = round(float(np.max(scores)), 1) if scores else 0.0
    db.flush()
    return snap


def progress_series(
    db: DbSession, exercise_key: str | None, user_id: int | None = None
) -> list[ProgressPoint]:
    stmt = (
        select(ProgressSnapshot, Session)
        .join(Session, Session.id == ProgressSnapshot.session_id)
        .where(Session.status == SessionStatus.complete)
        .order_by(Session.created_at)
    )
    if user_id is not None:
        stmt = stmt.where(Session.user_id == user_id)
    if exercise_key:
        stmt = stmt.where(ProgressSnapshot.exercise_key == exercise_key)
    out: list[ProgressPoint] = []
    for snap, sess in db.execute(stmt).all():
        out.append(
            ProgressPoint(
                session_id=snap.session_id,
                created_at=sess.created_at,
                avg_score=snap.avg_score,
                best_score=snap.best_score,
                rep_count=snap.rep_count,
            )
        )
    return out


def personal_best_session(
    db: DbSession, exercise_key: str, exclude_session_id: int
) -> Session | None:
    """Highest best-score completed session for this exercise, excluding one."""
    stmt = (
        select(Session)
        .join(ProgressSnapshot, ProgressSnapshot.session_id == Session.id)
        .where(
            Session.exercise_key == exercise_key,
            Session.status == SessionStatus.complete,
            Session.id != exclude_session_id,
        )
        .order_by(ProgressSnapshot.best_score.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def build_ghost(db: DbSession, current_session_id: int) -> GhostOut:
    current = db.get(Session, current_session_id)
    if current is None:
        return GhostOut(available=False)

    best = personal_best_session(db, current.exercise_key, current_session_id)
    if best is None:
        return GhostOut(available=False)

    # Best-scoring rep of the personal-best session.
    best_rep = db.scalar(
        select(Rep).where(Rep.session_id == best.id).order_by(Rep.score.desc()).limit(1)
    )
    artifact = db.scalar(
        select(AnalysisArtifact).where(AnalysisArtifact.session_id == best.id)
    )
    if best_rep is None or artifact is None:
        return GhostOut(available=False)

    pose = load_landmarks(artifact.landmarks_path)
    frames = _phase_normalize(pose.landmarks, best_rep.start_frame, best_rep.end_frame)

    best_snap = db.scalar(
        select(ProgressSnapshot).where(ProgressSnapshot.session_id == best.id)
    )
    return GhostOut(
        available=True,
        source_session_id=best.id,
        source_score=best_snap.best_score if best_snap else best_rep.score,
        edges=POSE_EDGES,
        frames=frames,
    )


def _phase_normalize(
    landmarks: np.ndarray, start: int, end: int, samples: int = GHOST_PHASE_SAMPLES
) -> list[list[list[float]]]:
    """Resample one rep's landmarks onto a common 0..100% phase axis.

    Returns ``samples`` frames, each a list of 33 [x, y, visibility] triplets.
    NaN landmarks (missing detections) become visibility 0 so the overlay skips them.
    """
    seg = landmarks[start : end + 1]
    if len(seg) < 2:
        return []
    src_phase = np.linspace(0.0, 1.0, len(seg))
    dst_phase = np.linspace(0.0, 1.0, samples)

    out = np.zeros((samples, NUM_LANDMARKS, 3), dtype=float)
    for j in range(NUM_LANDMARKS):
        for c in range(2):  # x, y
            col = seg[:, j, c]
            mask = ~np.isnan(col)
            if mask.sum() >= 2:
                out[:, j, c] = np.interp(dst_phase, src_phase[mask], col[mask])
        vis = seg[:, j, 3]
        vmask = ~np.isnan(vis)
        if vmask.sum() >= 2:
            out[:, j, 2] = np.interp(dst_phase, src_phase[vmask], vis[vmask])
    return [[[round(float(v), 4) for v in lm] for lm in frame] for frame in out]
