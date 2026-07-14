"""The analysis pipeline, run synchronously in-process.

``run_pipeline`` runs the full deterministic pipeline for one uploaded video,
persisting results and advancing ``AnalysisJob.stage``/``progress``. It is called
directly from the upload request handler (no task queue / broker) so the completed
analysis is available as soon as the request returns.

``run_pipeline_from_landmarks`` (steps 2–6) is shared with Live Camera Mode.
"""
from __future__ import annotations

from collections import Counter
from contextlib import nullcontext

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
from app.services.pose import PoseResult, is_pose_warm, run_pose, save_landmarks
from app.services.progress import upsert_progress
from app.services.reps import RepWindow, detect_reps
from app.services.rules import evaluate_session
from app.services.storage import get_storage
from app.services.timing import StageTimer


def _timed(timer: StageTimer | None, name: str):
    """Time a block when a timer is present; a no-op context otherwise."""
    return timer.stage(name) if timer is not None else nullcontext()


def _set_stage(job: AnalysisJob | None, stage: JobStage, progress: float) -> None:
    """Advance the job's recorded stage/progress in memory. Analysis is synchronous
    (nothing polls this mid-run any more), so we intentionally do NOT commit here —
    the value is persisted by the pipeline's own end-of-run commit. This removes a
    handful of per-analysis Postgres round-trips."""
    if job is None:
        return
    job.stage = stage
    job.progress = progress


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


def run_pipeline(session_id: int, timer: StageTimer | None = None) -> None:
    settings = get_settings()
    storage = get_storage()
    db = SessionLocal()
    try:
        session = db.get(Session, session_id)
        if session is None:
            return
        job = session.job
        session.status = SessionStatus.processing
        _set_stage(job, JobStage.pose, 0.1)

        # 1. Pose estimation (temporally downsampled + downscaled for speed). The
        #    sub-stage timings (video load, model init, frame extraction, inference)
        #    are filled into ``pose_timings`` and merged into the report.
        pose_timings: dict[str, float] = {}
        # Captured before run_pose (which flips the warm flag) so the summary shows
        # whether this analysis paid the cold model/import cost or reused a warm engine.
        pose_engine_cold = not is_pose_warm()
        pose = run_pose(
            session.video.path,
            settings.pose_model_file(),
            target_fps=settings.pose_target_fps,
            max_dim=settings.pose_max_dim,
            max_frames=settings.pose_max_frames,
            decoder=settings.pose_decoder,
            timings=pose_timings,
        )
        if timer is not None:
            timer.merge(pose_timings)
            timer.note("frames", len(pose.landmarks))
            timer.note("source_fps", round(pose.source_fps, 1))
            timer.note("processed_fps", round(pose.fps, 1))
            timer.note("resolution", f"{pose.width}x{pose.height}")
            timer.note("pose_engine", "cold (loaded from scratch)" if pose_engine_cold else "warm (reused)")

        session.video.fps = pose.fps
        session.video.duration = pose.duration
        session.video.width = pose.width
        session.video.height = pose.height
        landmarks_path = storage.artifact_path(session_id, "landmarks.npz")
        with _timed(timer, "save_landmarks"):
            save_landmarks(landmarks_path, pose)
        if session.artifact is None:
            db.add(AnalysisArtifact(session_id=session_id, landmarks_path=landmarks_path))
        # One durable commit here so the expensive pose result survives any later
        # (cheap) error, rather than committing at every stage.
        with _timed(timer, "db_write_pose"):
            db.commit()

        config = load_exercise(session.exercise_key)

        # Steps 2–6 are pure and landmark-driven — shared with Live Camera Mode.
        run_pipeline_from_landmarks(db, session, pose, config, job=job, timer=timer)
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
    timer: StageTimer | None = None,
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
    _set_stage(job, JobStage.biomechanics, 0.4)
    with _timed(timer, "biomechanics"):
        metrics = compute_metrics(landmarks, config)

    # 3. Rep detection — per set slice, offset back to global frame indices.
    _set_stage(job, JobStage.reps, 0.6)
    with _timed(timer, "rep_detection"):
        rep_pairs = _detect_reps_per_set(metrics, config, fps, bounds)
        rep_windows = [rw for rw, _ in rep_pairs]
        set_of_rep = {rw.index: si for rw, si in rep_pairs}

    # 4. Rule evaluation + scoring (per-rep rules are global; session-level rules
    #    span the whole workout).
    _set_stage(job, JobStage.rules, 0.75)
    with _timed(timer, "scoring"):
        scored = evaluate_session(rep_windows, metrics, landmarks, config, fps)
    fault_counter: Counter[str] = Counter()
    rep_outs: list[RepOut] = []
    for sr in scored:
        # Attach faults via the relationship so the whole rep + its faults insert
        # in one batched flush — no per-rep flush round-trip to fetch the id.
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
        rep_row.faults = [
            Fault(
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
            for f in sr.faults
        ]
        db.add(rep_row)
        fault_outs: list[FaultOut] = []
        for f in sr.faults:
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
    # Flush (not commit) so the reps are visible to the progress query below;
    # the whole transaction is committed once at the end.
    with _timed(timer, "db_write_reps"):
        db.flush()

    # 4b. Aggregate into a sports-science summary.
    with _timed(timer, "aggregation"):
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

    # 5. AI coaching (explains the structured report only).
    _set_stage(job, JobStage.coaching, 0.9)
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
    with _timed(timer, "ai_feedback"):
        try:
            text = coach.explain(report)
        except Exception as exc:  # noqa: BLE001 — coaching must never fail the pipeline
            text = f"(Coaching unavailable: {exc})"
    db.add(CoachingNote(session_id=session_id, provider=coach.name, text=text))

    # 6. Progress aggregation.
    _set_stage(job, JobStage.progress, 0.97)
    with _timed(timer, "progress"):
        upsert_progress(db, session_id)

    session.status = SessionStatus.complete
    _set_stage(job, JobStage.done, 1.0)

    # Single end-of-run commit persists reps, faults, summary, coaching, progress
    # and the final job stage together — one round-trip instead of ~6.
    with _timed(timer, "db_commit"):
        db.commit()
