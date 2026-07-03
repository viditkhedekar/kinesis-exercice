"""Live Camera Mode API.

Pose estimation + the skeleton overlay run in the browser (MediaPipe); this API
is the authoritative scoring surface. It reuses the exact same deterministic
engine as the video-upload path — the only difference is the pose *source*.

The endpoints are stateless: the browser owns the growing landmark buffer (it
needs it for the overlay and the final submission anyway), so there is no live
server session state or Redis. ``/live/score`` is a pure computation over the
current set's frames; ``/live/finish`` persists the whole workout through the
shared ``run_pipeline_from_landmarks``.
"""
from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.db import get_db
from app.exercises import available_exercises, load_exercise
from app.models import (
    AnalysisArtifact,
    AnalysisJob,
    JobStage,
    Session,
    SessionStatus,
    User,
)
from app.schemas import (
    FaultOut,
    LiveCreateIn,
    LiveCue,
    LiveFinishIn,
    LiveFinishOut,
    LiveScoreIn,
    LiveScoreOut,
    RepOut,
    SessionOut,
)
from app.services.biomechanics import compute_metrics
from app.services.pose import PoseResult, save_landmarks
from app.services.pose.landmarks import NUM_LANDMARKS
from app.services.reps import detect_reps
from app.services.rules import evaluate_session
from app.services.storage import get_storage
from app.workers.tasks import run_pipeline_from_landmarks

router = APIRouter(prefix="/sessions/live", tags=["live"])

# The browser scores per completed rep, so per-set buffers are small. We resample
# the finish buffer onto this uniform grid so the exercises' frame-unit rep tuning
# (authored at ~30fps, rescaled by the engine) behaves as it does for uploads.
FINISH_TARGET_FPS = 15.0
# Severity → penalty order, for picking the cue to surface.
_SEV_RANK = {"minor": 0, "moderate": 1, "severe": 2}


def _valid_exercise_keys() -> set[str]:
    return {e.key for e in available_exercises()}


def _owned_live(db: DbSession, session_id: int, user: User) -> Session:
    session = db.get(Session, session_id)
    if session is None or session.user_id != user.id or session.mode != "live":
        raise HTTPException(404, "Live session not found")
    return session


def _to_array(frames: list[list[list[float]]]) -> np.ndarray:
    """Browser frames → ``(F, 33, 4)`` float array, tolerant of short/empty rows.

    Missing landmarks become NaN with visibility 0, matching the pose service so
    the biomechanics/rules code (which already handles NaN) is unchanged."""
    F = len(frames)
    arr = np.full((F, NUM_LANDMARKS, 4), np.nan, dtype=np.float32)
    for i, frame in enumerate(frames):
        for j, lm in enumerate(frame[:NUM_LANDMARKS]):
            if lm is None or len(lm) < 4:
                continue
            arr[i, j, 0] = lm[0]
            arr[i, j, 1] = lm[1]
            arr[i, j, 2] = lm[2]
            arr[i, j, 3] = lm[3]
    return arr


def _resample_uniform(
    landmarks: np.ndarray, timestamps: list[float], target_fps: float
) -> tuple[np.ndarray, np.ndarray | None]:
    """Resample variable-fps capture onto a uniform ``target_fps`` time grid.

    Returns ``(resampled_landmarks, src_time)`` where ``src_time`` is the
    original per-frame times (zeroed) so the caller can remap set boundaries
    (expressed in source frame indices) onto the resampled grid. If timestamps
    are missing/degenerate, returns the input unchanged with ``src_time=None``.
    """
    F = len(landmarks)
    if F < 2 or len(timestamps) != F:
        return landmarks, None
    t = np.asarray(timestamps, dtype=float) - float(timestamps[0])
    total = float(t[-1])
    if total <= 0:
        return landmarks, None
    n_out = max(2, int(round(total * target_fps)) + 1)
    dst_t = np.linspace(0.0, total, n_out)

    out = np.full((n_out, NUM_LANDMARKS, 4), np.nan, dtype=np.float32)
    for j in range(NUM_LANDMARKS):
        for c in range(4):
            col = landmarks[:, j, c]
            mask = ~np.isnan(col)
            if mask.sum() >= 2:
                out[:, j, c] = np.interp(dst_t, t[mask], col[mask])
    return out, t


@router.post("", response_model=SessionOut, status_code=201)
def create_live_session(
    body: LiveCreateIn,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionOut:
    if body.exercise_key not in _valid_exercise_keys():
        raise HTTPException(400, f"Unknown exercise: {body.exercise_key}")
    session = Session(
        exercise_key=body.exercise_key,
        status=SessionStatus.processing,
        mode="live",
        user_id=user.id,
    )
    db.add(session)
    db.flush()
    db.add(AnalysisJob(session_id=session.id, stage=JobStage.pose, progress=0.0))
    db.commit()
    db.refresh(session)
    return SessionOut.model_validate(session)


@router.post("/{session_id}/score", response_model=LiveScoreOut)
def score_live_set(
    session_id: int,
    body: LiveScoreIn,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LiveScoreOut:
    """Score the current set's buffer with the real engine. No DB writes — this
    is called repeatedly during a set (typically once per completed rep)."""
    session = _owned_live(db, session_id, user)
    config = load_exercise(session.exercise_key)

    landmarks = _to_array(body.frames)
    if len(landmarks) < 3:
        return LiveScoreOut()

    metrics = compute_metrics(landmarks, config)
    reps = detect_reps(metrics, config, fps=body.fps or FINISH_TARGET_FPS)
    if not reps:
        return LiveScoreOut()
    scored = evaluate_session(reps, metrics, landmarks, config, body.fps or FINISH_TARGET_FPS)

    rep_outs = [
        RepOut(
            index=sr.rep.index,
            start_frame=sr.rep.start,
            bottom_frame=sr.rep.bottom,
            end_frame=sr.rep.end,
            score=sr.score,
            rom=round(sr.rep.rom, 2),
            faults=[FaultOut(**f.__dict__) for f in sr.faults],
        )
        for sr in scored
    ]
    running = round(sum(r.score for r in rep_outs) / len(rep_outs), 1)

    # Cue = the highest-severity fault on the most recent rep (one at a time).
    latest_cue = None
    last_faults = scored[-1].faults
    if last_faults:
        top = max(last_faults, key=lambda f: (_SEV_RANK.get(f.severity, 1), f.confidence))
        latest_cue = LiveCue(type=top.type, message=top.message, tip=top.tip, severity=top.severity)

    return LiveScoreOut(
        reps=rep_outs, rep_count=len(rep_outs), running_score=running, latest_cue=latest_cue
    )


@router.post("/{session_id}/finish", response_model=LiveFinishOut)
def finish_live_session(
    session_id: int,
    body: LiveFinishIn,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LiveFinishOut:
    """Persist the whole workout: resample → save landmarks → run the shared
    pipeline per set → write live-only summary extras → mark complete."""
    session = _owned_live(db, session_id, user)
    config = load_exercise(session.exercise_key)

    landmarks = _to_array(body.frames)
    if len(landmarks) < 3:
        raise HTTPException(400, "Not enough frames to analyze")

    # Set boundaries in *source* frame indices (fall back to a single set).
    src_bounds = (
        [(s.start, s.end) for s in body.sets]
        if body.sets
        else [(0, len(landmarks) - 1)]
    )

    resampled, src_t = _resample_uniform(landmarks, body.timestamps, FINISH_TARGET_FPS)
    if src_t is not None:
        # Remap source-frame set bounds onto the resampled uniform grid via time.
        total = float(src_t[-1])
        n_out = len(resampled)

        def _to_grid(i: int) -> int:
            frac = float(src_t[min(i, len(src_t) - 1)]) / total if total > 0 else 0.0
            return int(round(frac * (n_out - 1)))

        set_bounds = [(_to_grid(a), _to_grid(b)) for a, b in src_bounds]
        landmarks = resampled
    else:
        set_bounds = src_bounds

    eff_fps = FINISH_TARGET_FPS
    duration_s = float(len(landmarks) / eff_fps) if eff_fps else 0.0
    pose = PoseResult(
        landmarks=landmarks, fps=eff_fps, duration=duration_s,
        width=body.width, height=body.height,
    )

    # Persist landmarks so /landmarks, /metrics and Ghost Replay work for live too.
    storage = get_storage()
    landmarks_path = storage.artifact_path(session.id, "landmarks.npz")
    save_landmarks(landmarks_path, pose)
    if session.artifact is None:
        db.add(AnalysisArtifact(session_id=session.id, landmarks_path=landmarks_path))
    db.commit()

    # Time under tension = summed rep durations; computed inside the pipeline via
    # reps, so we pass set bounds and derive TUT/sets from the persisted reps after.
    extra = {
        "sets": [{"start": a, "end": b} for a, b in set_bounds],
        "duration_s": round(duration_s, 1),
    }
    run_pipeline_from_landmarks(
        db, session, pose, config, job=session.job, set_bounds=set_bounds, extra_summary=extra
    )

    # Time under tension: sum of rep durations across the workout.
    from app.models import Rep  # local import to avoid a cycle at module load

    reps = db.query(Rep).filter(Rep.session_id == session.id).all()
    tut = round(sum((r.end_frame - r.start_frame) / eff_fps for r in reps), 1) if eff_fps else 0.0
    summary = dict(session.summary or {})
    summary["time_under_tension"] = tut
    session.summary = summary
    db.commit()

    return LiveFinishOut(session_id=session.id)
