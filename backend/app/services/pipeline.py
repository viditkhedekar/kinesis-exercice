"""The analysis pipeline, run synchronously in-process.

``run_pipeline`` runs the full deterministic pipeline for one uploaded video,
persisting results and advancing ``AnalysisJob.stage``/``progress``. It is called
directly from the upload request handler (no task queue / broker) so the completed
analysis is available as soon as the request returns.

``run_pipeline_from_landmarks`` (steps 2–6) is shared with Live Camera Mode.
"""
from __future__ import annotations

from collections import Counter

import numpy as np

from app.config import get_settings
from app.db import SessionLocal
from app.exercises import load_exercise
from app.models import (
    AnalysisArtifact,
    AnalysisJob,
    CoachingNote,
    Fault,
    FaultSeverity,
    JobStage,
    Rep,
    Session,
    SessionStatus,
)
from app.exercises import ExerciseConfig
from app.schemas import AnalysisReport, FaultOut, RepOut
from app.services.biomechanics import camera_view, compute_metrics
from app.services.coaching import get_coach
from app.services.feedback import (
    grade,
    group_faults,
    key_metrics,
    overall_score,
    strengths,
)
from app.services.insights import generate_insights
from app.services.pose import PoseResult, run_pose, save_landmarks
from app.services.progress import upsert_progress
from app.services.reps import RepWindow, detect_reps
from app.services.rules import evaluate_session
from app.services.storage import get_storage


def _set_stage(db, job: AnalysisJob | None, stage: JobStage, progress: float) -> None:
    if job is None:
        return
    job.stage = stage
    job.progress = progress
    db.commit()


def _detect_reps_per_set(
    metrics: dict, config: ExerciseConfig, fps: float, set_bounds: list[tuple[int, int]]
) -> list[tuple[RepWindow, int]]:
    """Run rep detection independently per set slice so a rest gap between sets
    never fuses two reps or invents a spurious one at the boundary.

    Returns ``(global_rep_window, set_index)`` pairs. Frame indices in each
    returned ``RepWindow`` are offset back to the full-buffer coordinate space so
    the downstream engine (which indexes global metrics/landmarks) is unchanged.
    ``rep.index`` is renumbered to be continuous across the whole workout.
    """
    out: list[tuple[RepWindow, int]] = []
    for set_idx, (s, e) in enumerate(set_bounds, start=1):
        sliced = {k: v[s : e + 1] for k, v in metrics.items()}
        for rw in detect_reps(sliced, config, fps=fps):
            global_rw = RepWindow(
                index=len(out) + 1,
                start=rw.start + s,
                bottom=rw.bottom + s,
                end=rw.end + s,
                rom=rw.rom,
            )
            out.append((global_rw, set_idx))
    return out


def _assess_quality(
    landmarks: np.ndarray,
    metrics: dict,
    config: ExerciseConfig,
    rep_count: int,
) -> dict | None:
    """Flag clips that likely can't be trusted, so the report can say so instead
    of presenting confident nonsense.

    Two cases, in priority order:
      1. ``no_subject`` — a person is barely visible (bad framing / lighting /
         nobody in shot). Judged from MediaPipe landmark *visibility*.
      2. ``no_reps`` — a person is visible but no reps of the selected exercise
         were detected. Usually means the wrong exercise was picked, or the
         movement wasn't performed clearly on camera.

    Returns a warning dict (kind/title/message) or ``None`` when the clip looks
    fine. Kept intentionally conservative — it should only fire on clearly bad
    input, never on a merely imperfect set.
    """
    F = len(landmarks)
    if F == 0:
        present_frac = 0.0
    else:
        vis = landmarks[:, :, 3].astype(float)          # (F, 33) visibility, NaN if undetected
        per_frame = np.nan_to_num(np.nanmean(vis, axis=1), nan=0.0)
        present_frac = float(np.mean(per_frame >= 0.5))

    if present_frac < 0.4:
        return {
            "kind": "no_subject",
            "title": "We couldn't clearly see you in this clip",
            "message": (
                "A person was only visible in part of the video, so this analysis may be "
                "unreliable — it looks like the clip wasn't uploaded or filmed properly. "
                "Re-film with your whole body in frame, good lighting, and the camera held "
                "still (see the filming tips on the upload screen)."
            ),
        }

    if rep_count == 0:
        return {
            "kind": "no_reps",
            "title": f"This doesn't look like a {config.name}",
            "message": (
                f"We couldn't detect any {config.name} repetitions. You may have selected the "
                "wrong exercise, or the movement wasn't performed clearly on camera. "
                "Double-check the exercise you picked and re-film using the filming tips."
            ),
        }

    return None


def _previous_session(db, session: Session) -> Session | None:
    """The athlete's most recent *completed* session of the same exercise, for
    change-over-time insights. Falls back to any user when the session has none
    (e.g. single-user/live fixtures). The in-progress current session is excluded
    naturally by the ``complete`` filter."""
    from sqlalchemy import select

    stmt = (
        select(Session)
        .where(
            Session.exercise_key == session.exercise_key,
            Session.id != session.id,
            Session.status == SessionStatus.complete,
        )
        .order_by(Session.created_at.desc(), Session.id.desc())
        .limit(1)
    )
    if session.user_id is not None:
        stmt = stmt.where(Session.user_id == session.user_id)
    return db.scalar(stmt)


def run_pipeline(session_id: int) -> None:
    settings = get_settings()
    storage = get_storage()
    db = SessionLocal()
    try:
        session = db.get(Session, session_id)
        if session is None:
            return
        job = session.job
        session.status = SessionStatus.processing
        db.commit()

        # 1. Pose estimation (temporally downsampled + downscaled for speed)
        _set_stage(db, job, JobStage.pose, 0.1)
        pose = run_pose(
            session.video.path,
            str(settings.pose_model_path),
            target_fps=settings.pose_target_fps,
            max_dim=settings.pose_max_dim,
            max_frames=settings.pose_max_frames,
        )
        session.video.fps = pose.fps
        session.video.duration = pose.duration
        session.video.width = pose.width
        session.video.height = pose.height
        landmarks_path = storage.artifact_path(session_id, "landmarks.npz")
        save_landmarks(landmarks_path, pose)
        if session.artifact is None:
            db.add(AnalysisArtifact(session_id=session_id, landmarks_path=landmarks_path))
        db.commit()

        config = load_exercise(session.exercise_key)

        # Steps 2–6 are pure and landmark-driven — shared with Live Camera Mode.
        run_pipeline_from_landmarks(db, session, pose, config, job=job)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        session = db.get(Session, session_id)
        if session is not None:
            session.status = SessionStatus.failed
            if session.job is not None:
                session.job.stage = JobStage.failed
                session.job.error = str(exc)
        db.commit()
        raise
    finally:
        db.close()


def run_pipeline_from_landmarks(
    db,
    session: Session,
    pose: PoseResult,
    config: ExerciseConfig,
    *,
    job: AnalysisJob | None = None,
    set_bounds: list[tuple[int, int]] | None = None,
    extra_summary: dict | None = None,
) -> None:
    """Steps 2–6 of the analysis pipeline, driven purely by a landmark array.

    Shared by the video-upload handler and Live Camera Mode. The only difference
    for live sessions is ``set_bounds`` (rep detection is run per set slice) and
    ``extra_summary`` (live-only fields — sets, time-under-tension, duration —
    merged into ``Session.summary``). With no ``set_bounds`` the whole buffer is
    one set, reproducing the upload path exactly.
    """
    session_id = session.id
    landmarks = pose.landmarks
    fps = pose.fps
    F = len(landmarks)
    bounds = set_bounds or [(0, max(0, F - 1))]

    # 2. Biomechanics (computed once over the full buffer; global-aligned).
    _set_stage(db, job, JobStage.biomechanics, 0.4)
    metrics = compute_metrics(landmarks, config)

    # 3. Rep detection — per set slice, offset back to global frame indices.
    _set_stage(db, job, JobStage.reps, 0.6)
    rep_pairs = _detect_reps_per_set(metrics, config, fps, bounds)
    rep_windows = [rw for rw, _ in rep_pairs]
    set_of_rep = {rw.index: si for rw, si in rep_pairs}

    # 4. Rule evaluation + scoring (per-rep rules are global; session-level rules
    #    span the whole workout).
    _set_stage(db, job, JobStage.rules, 0.75)
    scored = evaluate_session(rep_windows, metrics, landmarks, config, fps)
    fault_counter: Counter[str] = Counter()
    rep_outs: list[RepOut] = []
    for sr in scored:
        rep_row = Rep(
            session_id=session_id,
            index=sr.rep.index,
            start_frame=sr.rep.start,
            bottom_frame=sr.rep.bottom,
            end_frame=sr.rep.end,
            score=sr.score,
            rom=round(sr.rep.rom, 2),
            set_index=set_of_rep.get(sr.rep.index),
        )
        db.add(rep_row)
        db.flush()
        fault_outs: list[FaultOut] = []
        for f in sr.faults:
            db.add(
                Fault(
                    rep_id=rep_row.id,
                    type=f.type,
                    severity=FaultSeverity(f.severity),
                    message=f.message,
                    tip=f.tip,
                    start_frame=f.start_frame,
                    end_frame=f.end_frame,
                    value=f.value,
                    unit=f.unit,
                    confidence=f.confidence,
                    joints=f.joints,
                )
            )
            fault_counter[f.type] += 1
            fault_outs.append(FaultOut(**f.__dict__))
        rep_outs.append(
            RepOut(
                index=sr.rep.index,
                start_frame=sr.rep.start,
                bottom_frame=sr.rep.bottom,
                end_frame=sr.rep.end,
                score=sr.score,
                rom=round(sr.rep.rom, 2),
                faults=fault_outs,
            )
        )
    db.commit()

    # 4b. Aggregate into a sports-science summary.
    rep_fault_pairs = [(sr.rep.index, f) for sr in scored for f in sr.faults]
    groups = group_faults(rep_fault_pairs)
    view = camera_view(landmarks)
    km = key_metrics(rep_windows, metrics, config, fps, view)
    overall = overall_score(groups, len(rep_windows))

    # When the clip can't be trusted (wrong exercise / no subject) there's no
    # meaningful technique score — a scoreless report reads "--" rather than a
    # misleading 100. Otherwise store the computed score.
    warning = _assess_quality(landmarks, metrics, config, len(rep_windows))
    trustworthy = warning is None
    session.overall_score = overall if trustworthy else None

    # Concise, data-grounded observations (incl. change vs the previous session).
    prev = _previous_session(db, session)
    prev_summary = (prev.summary or {}) if prev else {}
    try:
        insights = generate_insights(
            reps=rep_windows, metrics=metrics, config=config, fps=fps,
            groups=groups, km=km, overall=overall,
            prev_km=prev_summary.get("key_metrics"),
            prev_overall=prev.overall_score if prev else None,
        )
    except Exception:  # noqa: BLE001 — insights must never fail the pipeline
        insights = []

    summary: dict = {
        "grade": grade(overall) if trustworthy else "",
        "key_metrics": km,
        "strengths": strengths(groups, km, config) if trustworthy else [],
        "insights": insights,
    }
    if warning:
        summary["analysis_warning"] = warning
    if extra_summary:
        summary.update(extra_summary)
    session.summary = summary
    db.commit()

    # 5. AI coaching (explains the structured report only).
    _set_stage(db, job, JobStage.coaching, 0.9)
    avg_score = round(sum(r.score for r in rep_outs) / len(rep_outs), 1) if rep_outs else 0.0
    report = AnalysisReport(
        exercise_key=config.key,
        exercise_name=config.name,
        rep_count=len(rep_outs),
        avg_score=avg_score,
        reps=rep_outs,
        fault_summary=dict(fault_counter),
    )
    coach = get_coach()
    try:
        text = coach.explain(report)
    except Exception as exc:  # noqa: BLE001 — coaching must never fail the pipeline
        text = f"(Coaching unavailable: {exc})"
    db.add(CoachingNote(session_id=session_id, provider=coach.name, text=text))
    db.commit()

    # 6. Progress aggregation.
    _set_stage(db, job, JobStage.progress, 0.97)
    upsert_progress(db, session_id)

    session.status = SessionStatus.complete
    _set_stage(db, job, JobStage.done, 1.0)
