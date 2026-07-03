from app.exercises import load_exercise
from app.services.biomechanics import compute_metrics
from app.services.reps import detect_reps
from app.services.rules import evaluate_session
from tests.synthetic import knee_series, squat_landmarks

FPS = 30.0


def _run(knee_angles, lean_deg=0.0, asym_deg=0.0):
    config = load_exercise("squat")
    lm = squat_landmarks(knee_angles, lean_deg=lean_deg, asym_deg=asym_deg)
    metrics = compute_metrics(lm, config)
    reps = detect_reps(metrics, config)
    scored = evaluate_session(reps, metrics, lm, config, FPS)
    return reps, scored


def test_detects_correct_rep_count():
    reps, _ = _run(knee_series(3, bottom=85.0))
    assert len(reps) == 3


def test_deep_clean_squat_scores_full():
    _, scored = _run(knee_series(2, bottom=85.0))
    assert scored, "expected at least one rep"
    for sr in scored:
        assert not sr.faults, f"unexpected faults: {[f.type for f in sr.faults]}"
        assert sr.score == 100.0


def test_shallow_squat_flags_depth():
    _, scored = _run(knee_series(2, bottom=120.0))  # bottom angle > 100 threshold
    assert scored
    for sr in scored:
        fault_types = {f.type for f in sr.faults}
        assert "insufficient_depth" in fault_types
        assert sr.score < 100.0


def test_torso_lean_flagged():
    _, scored = _run(knee_series(2, bottom=85.0), lean_deg=55.0)
    assert any("excessive_torso_lean" in {f.type for f in sr.faults} for sr in scored)


def test_weight_shift_flagged_on_asymmetric_squat():
    # One knee bending more than the other drops the pelvis unevenly -> weight shift.
    _, scored = _run(knee_series(2, bottom=85.0), asym_deg=30.0)
    assert any("weight_shift" in {f.type for f in sr.faults} for sr in scored)
