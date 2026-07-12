"""Live Camera Mode: the landmark-driven pipeline reused from the upload path.

These assert that ``run_pipeline_from_landmarks`` (a) reproduces the pure-engine
scores when run over a single set, and (b) attributes reps to the correct set
when given multiple set slices. No real video or MediaPipe is required — the
same synthetic squat landmarks used by the engine tests drive everything.
"""
from __future__ import annotations

import numpy as np

from app.exercises import load_exercise
from app.models import Exercise, Rep, Session, SessionStatus
from app.services.biomechanics import compute_metrics
from app.services.pose import PoseResult
from app.services.reps import detect_reps
from app.services.rules import evaluate_session
from app.services.pipeline import run_pipeline_from_landmarks
from tests.synthetic import knee_series, squat_landmarks

FPS = 30.0


def _pose(landmarks: np.ndarray) -> PoseResult:
    return PoseResult(
        landmarks=landmarks,
        fps=FPS,
        duration=len(landmarks) / FPS,
        width=640,
        height=360,
    )


def _seed_session(db, exercise_key="squat", mode="live") -> Session:
    db.add(Exercise(key=exercise_key, name=exercise_key.title(), config_path=f"{exercise_key}.yaml"))
    session = Session(exercise_key=exercise_key, status=SessionStatus.processing, mode=mode)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def test_single_set_matches_pure_engine(db):
    """One set through the DB pipeline == the stateless engine, rep-for-rep."""
    config = load_exercise("squat")
    lm = squat_landmarks(knee_series(3, bottom=85.0))

    # Ground truth from the pure engine.
    metrics = compute_metrics(lm, config)
    expected = evaluate_session(detect_reps(metrics, config, fps=FPS), metrics, lm, config, FPS)

    session = _seed_session(db)
    run_pipeline_from_landmarks(db, session, _pose(lm), config)

    reps = db.query(Rep).filter(Rep.session_id == session.id).order_by(Rep.index).all()
    assert len(reps) == len(expected) == 3
    for rep_row, sr in zip(reps, expected):
        assert rep_row.score == sr.score
        assert rep_row.set_index == 1  # single set defaults to set 1
    assert session.status == SessionStatus.complete


def test_multi_set_tags_reps_with_set_index(db):
    """Two sets (2 then 3 reps) with a rest gap are detected independently and
    tagged with the correct set_index; no spurious rep spans the gap."""
    config = load_exercise("squat")
    set_a = squat_landmarks(knee_series(2, bottom=85.0))
    rest = squat_landmarks([165.0] * 20)  # standing still during rest
    set_b = squat_landmarks(knee_series(3, bottom=85.0))
    lm = np.concatenate([set_a, rest, set_b])

    a_end = len(set_a) - 1
    b_start = len(set_a) + len(rest)
    set_bounds = [(0, a_end), (b_start, len(lm) - 1)]

    session = _seed_session(db)
    run_pipeline_from_landmarks(
        db,
        session,
        _pose(lm),
        config,
        set_bounds=set_bounds,
        extra_summary={"sets": [{"start": 0, "end": a_end}, {"start": b_start, "end": len(lm) - 1}]},
    )

    reps = db.query(Rep).filter(Rep.session_id == session.id).order_by(Rep.index).all()
    set_counts = {}
    for r in reps:
        set_counts[r.set_index] = set_counts.get(r.set_index, 0) + 1
    assert set_counts == {1: 2, 2: 3}
    assert [r.index for r in reps] == [1, 2, 3, 4, 5]  # continuous across sets
    assert session.summary["sets"][1]["start"] == b_start
    assert session.overall_score == 100.0  # clean deep squats


def test_finalize_produces_valid_report_shape(db):
    """The persisted session yields the fields the report/review UI reads."""
    config = load_exercise("squat")
    lm = squat_landmarks(knee_series(2, bottom=120.0))  # shallow -> a fault group

    session = _seed_session(db)
    run_pipeline_from_landmarks(db, session, _pose(lm), config)

    assert session.summary["grade"]
    assert session.summary["key_metrics"]["rep_count"] == 2
    reps = db.query(Rep).filter(Rep.session_id == session.id).all()
    assert any(r.faults for r in reps)  # shallow squats flag insufficient_depth
