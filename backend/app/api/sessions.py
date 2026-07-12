from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.db import get_db
from app.exercises import available_exercises
from app.models import (
    AnalysisArtifact,
    AnalysisJob,
    CoachingNote,
    JobStage,
    Session,
    SessionStatus,
    User,
    Video,
)
from app.schemas import (
    AnalysisWarningOut,
    GhostOut,
    GroupedFaultOut,
    InsightOut,
    JobStatusOut,
    KeyMetricsOut,
    LandmarksOut,
    MetricSeries,
    MetricsOut,
    QuotaOut,
    RepBound,
    ReportOut,
    RepOut,
    SessionOut,
    SetSummaryOut,
    VideoOut,
)
from app.services.feedback import group_faults
from app.services.pose import load_landmarks
from app.services.pose.landmarks import POSE_EDGES
from app.services.progress import build_ghost
from app.services.storage import get_storage

router = APIRouter(prefix="/sessions", tags=["sessions"])

# --- History storage quota -------------------------------------------------
# Each user gets a budget of HISTORY_LIMIT "video slots". A session with its raw
# clip costs a full slot; deleting the video but keeping the analysis (which still
# powers the report and Ghost Replay) drops it to a quarter slot. Uploading needs
# a full free slot.
HISTORY_LIMIT = 10.0
VIDEO_SLOT = 1.0
ANALYSIS_SLOT = 0.25


def _session_slots(s: Session) -> float:
    if s.has_video:
        return VIDEO_SLOT
    if s.has_analysis:
        return ANALYSIS_SLOT
    return 0.0


def _used_slots(db: DbSession, user: User) -> float:
    sessions = db.scalars(select(Session).where(Session.user_id == user.id)).all()
    return round(sum(_session_slots(s) for s in sessions), 2)


def _valid_exercise_keys() -> set[str]:
    return {e.key for e in available_exercises()}


def _owned(db: DbSession, session_id: int, user: User) -> Session:
    """Fetch a session the current user owns, or 404 (don't leak existence)."""
    session = db.get(Session, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(404, "Session not found")
    return session


@router.post("", response_model=SessionOut, status_code=201)
def create_session(
    exercise_key: str = Form(...),
    file: UploadFile = File(...),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionOut:
    if exercise_key not in _valid_exercise_keys():
        raise HTTPException(400, f"Unknown exercise: {exercise_key}")

    # Enforce the per-user history quota before storing anything new.
    if _used_slots(db, user) + VIDEO_SLOT > HISTORY_LIMIT:
        raise HTTPException(
            409,
            f"Your history is full ({int(HISTORY_LIMIT)} videos). Free a slot from your history: "
            "fully delete a session, or delete a few videos while keeping their analysis "
            "(each kept analysis, incl. Ghost Replay, still uses a quarter slot).",
        )

    session = Session(exercise_key=exercise_key, status=SessionStatus.uploaded, user_id=user.id)
    db.add(session)
    db.flush()  # assign id

    storage = get_storage()
    path = storage.save_upload(session.id, file.filename or "video.mp4", file.file)
    db.add(Video(session_id=session.id, path=path, filename=file.filename or "video.mp4"))
    db.add(AnalysisJob(session_id=session.id, stage=JobStage.queued, progress=0.0))
    db.commit()

    # Run the analysis pipeline synchronously, in-process — no task queue. The
    # request blocks until the full report is persisted, then returns the
    # completed session so the client can render the analysis immediately.
    from app.services.pipeline import run_pipeline

    try:
        run_pipeline(session.id)
    except Exception as exc:  # noqa: BLE001
        # run_pipeline has already marked the session/job failed in its own
        # transaction; surface the failure to the client.
        raise HTTPException(500, f"Analysis failed: {exc}")

    db.refresh(session)
    return SessionOut.model_validate(session)


@router.get("", response_model=list[SessionOut])
def list_sessions(
    exercise: str | None = None,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SessionOut]:
    stmt = select(Session).where(Session.user_id == user.id).order_by(Session.created_at.desc())
    if exercise:
        stmt = stmt.where(Session.exercise_key == exercise)
    return [SessionOut.model_validate(s) for s in db.scalars(stmt).all()]


@router.get("/quota", response_model=QuotaOut)
def get_quota(db: DbSession = Depends(get_db), user: User = Depends(get_current_user)) -> QuotaOut:
    sessions = db.scalars(select(Session).where(Session.user_id == user.id)).all()
    video_count = sum(1 for s in sessions if s.has_video)
    analysis_only = sum(1 for s in sessions if not s.has_video and s.has_analysis)
    return QuotaOut(
        used=round(video_count * VIDEO_SLOT + analysis_only * ANALYSIS_SLOT, 2),
        limit=HISTORY_LIMIT,
        video_count=video_count,
        analysis_only_count=analysis_only,
    )


@router.delete("/{session_id}/video", response_model=SessionOut)
def delete_video(
    session_id: int,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionOut:
    """Free a history slot by deleting the raw clip while keeping the analysis
    (report, metrics, and Ghost Replay landmarks). Drops the session to ¼ slot."""
    session = _owned(db, session_id, user)
    if session.video is not None:
        get_storage().delete(session.video.path)
        db.delete(session.video)
        db.commit()
        db.refresh(session)
    return SessionOut.model_validate(session)


@router.delete("/{session_id}", status_code=204)
def delete_session(
    session_id: int,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Delete a session outright — video, analysis, and all artifacts."""
    session = _owned(db, session_id, user)
    get_storage().delete_session(session_id)
    db.delete(session)  # cascades to video/artifact/reps/faults/coaching/progress/job
    db.commit()


@router.get("/{session_id}/status", response_model=JobStatusOut)
def get_status(
    session_id: int,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobStatusOut:
    _owned(db, session_id, user)
    job = db.scalar(select(AnalysisJob).where(AnalysisJob.session_id == session_id))
    if job is None:
        raise HTTPException(404, "Session not found")
    return JobStatusOut.model_validate(job)


@router.get("/{session_id}/report", response_model=ReportOut)
def get_report(
    session_id: int,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReportOut:
    session = _owned(db, session_id, user)
    reps = [RepOut.model_validate(r) for r in session.reps]
    note = db.scalar(
        select(CoachingNote)
        .where(CoachingNote.session_id == session_id)
        .order_by(CoachingNote.created_at.desc())
        .limit(1)
    )

    # Group repeated faults across reps (one issue, many affected reps).
    pairs = [(rep.index, f) for rep in session.reps for f in rep.faults]
    groups = [GroupedFaultOut(**g.__dict__) for g in group_faults(pairs)]

    summary = session.summary or {}
    key_metrics = KeyMetricsOut(**summary["key_metrics"]) if summary.get("key_metrics") else None
    warning = (
        AnalysisWarningOut(**summary["analysis_warning"]) if summary.get("analysis_warning") else None
    )

    # Live Camera Mode extras: per-set breakdown derived from reps + stored bounds.
    set_summaries = _build_set_summaries(session, summary)

    return ReportOut(
        session=SessionOut.model_validate(session),
        video=VideoOut.model_validate(session.video) if session.video else None,
        warning=warning,
        reps=reps,
        overall_score=session.overall_score,
        grade=summary.get("grade", ""),
        key_metrics=key_metrics,
        strengths=summary.get("strengths", []),
        insights=[InsightOut(**i) for i in summary.get("insights", [])],
        priorities=groups[:3],
        fault_groups=groups,
        coaching=note.text if note else None,
        coaching_provider=note.provider if note else None,
        sets=set_summaries,
        time_under_tension=summary.get("time_under_tension"),
        duration_s=summary.get("duration_s"),
    )


def _build_set_summaries(session: Session, summary: dict) -> list[SetSummaryOut]:
    """Aggregate persisted reps into per-set rows for the live review. Uploaded
    (single-set) sessions leave ``set_index`` NULL and return an empty list."""
    if session.mode != "live" or not summary.get("sets"):
        return []
    by_set: dict[int, list] = {}
    for r in session.reps:
        by_set.setdefault(r.set_index or 1, []).append(r)
    bounds = summary.get("sets", [])
    out: list[SetSummaryOut] = []
    for i, b in enumerate(bounds, start=1):
        rs = by_set.get(i, [])
        avg = round(sum(x.score for x in rs) / len(rs), 1) if rs else 0.0
        # Set duration in seconds ≈ frame span / effective fps (15) used at finish.
        dur = round((b.get("end", 0) - b.get("start", 0)) / 15.0, 1)
        out.append(SetSummaryOut(set_index=i, rep_count=len(rs), avg_score=avg, duration_s=dur))
    return out


@router.get("/{session_id}/video")
def get_video(
    session_id: int,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    session = _owned(db, session_id, user)
    if session.video is None:
        raise HTTPException(404, "Video not found")
    return FileResponse(session.video.path, filename=session.video.filename)


@router.get("/{session_id}/landmarks", response_model=LandmarksOut)
def get_landmarks(
    session_id: int,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LandmarksOut:
    _owned(db, session_id, user)
    artifact = db.scalar(
        select(AnalysisArtifact).where(AnalysisArtifact.session_id == session_id)
    )
    if artifact is None:
        raise HTTPException(404, "No landmarks for this session yet")
    pose = load_landmarks(artifact.landmarks_path)
    # x, y, visibility per landmark; NaN -> 0 with visibility 0 so the overlay skips it.
    arr = pose.landmarks[:, :, [0, 1, 3]].astype(float)
    arr = np.nan_to_num(arr, nan=0.0)
    frames = [[[round(v, 4) for v in lm] for lm in frame] for frame in arr]
    return LandmarksOut(
        fps=pose.fps, width=pose.width, height=pose.height, edges=POSE_EDGES, frames=frames
    )


@router.get("/{session_id}/metrics", response_model=MetricsOut)
def get_metrics(
    session_id: int,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MetricsOut:
    """Recompute per-frame joint-angle series from stored landmarks for the
    analysis graphs (angle-over-time + per-rep range of motion)."""
    session = _owned(db, session_id, user)
    artifact = db.scalar(
        select(AnalysisArtifact).where(AnalysisArtifact.session_id == session_id)
    )
    if artifact is None:
        raise HTTPException(404, "No analysis for this session yet")

    from app.exercises import load_exercise
    from app.services.biomechanics import compute_metrics

    pose = load_landmarks(artifact.landmarks_path)
    config = load_exercise(session.exercise_key)
    metrics = compute_metrics(pose.landmarks, config)

    n = len(pose.landmarks)
    stride = max(1, n // 500)  # cap payload at ~500 points

    def ds(arr: np.ndarray) -> list[float | None]:
        out = arr[::stride]
        return [None if np.isnan(v) else round(float(v), 1) for v in out]

    # Angle metrics only (skip ratios/distances/coordinates), primary signal first.
    angle_keys = [k for k, m in config.metrics.items() if m.type == "angle"]
    ordered = ([config.rep.signal] if config.rep.signal in angle_keys else []) + [
        k for k in angle_keys if k != config.rep.signal
    ]
    series = [
        MetricSeries(
            key=k,
            label=k.replace("_", " ").title(),
            unit="deg",
            values=ds(metrics[k]),
        )
        for k in ordered[:3]
        if k in metrics
    ]

    rep_bounds = [
        RepBound(index=r.index, start=r.start_frame, bottom=r.bottom_frame, end=r.end_frame)
        for r in session.reps
    ]
    return MetricsOut(
        fps=pose.fps, frames=n, stride=stride, rep_bounds=rep_bounds, series=series
    )


@router.get("/{session_id}/ghost", response_model=GhostOut)
def get_ghost(
    session_id: int,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GhostOut:
    _owned(db, session_id, user)
    return build_ghost(db, session_id)
