"""Unit tests for the expanded fault-rule library.

Each new rule type is exercised directly with crafted metrics/landmarks so the
measured value, affected joints, confidence, severity, and NaN-safety are all
asserted deterministically.
"""
import numpy as np

from app.exercises import ExerciseConfig, RepConfig, RuleConfig
from app.services.pose.landmarks import LANDMARK_INDEX
from app.services.reps import RepWindow
from app.services.rules import evaluate_session

FPS = 10.0


def make_config(rules: list[RuleConfig]) -> ExerciseConfig:
    return ExerciseConfig(
        key="t", name="T", metrics={}, rep=RepConfig(signal="m"), rules=rules, score_base=100.0
    )


def base_landmarks(F: int) -> np.ndarray:
    lm = np.zeros((F, 33, 4), dtype=float)
    lm[:, :, 0] = 0.5  # x
    lm[:, :, 1] = 0.5  # y
    lm[:, :, 3] = 1.0  # visibility
    return lm


def only_fault(rules, metrics, landmarks, reps):
    scored = evaluate_session(reps, metrics, landmarks, make_config(rules), FPS)
    return [f for sr in scored for f in sr.faults]


def test_metric_aggregate_range_fires_with_value_and_joints():
    F = 20
    rep = RepWindow(1, 0, 10, 19, rom=0.0)
    torso = np.concatenate([np.linspace(0, 30, 10), np.linspace(30, 0, 10)])  # range 30
    rule = RuleConfig(
        id="body_swing", type="metric_aggregate", weight=18, message="swing", tip="brace",
        joints=["hip", "shoulder"],
        params={"metric": "torso", "aggregate": "range", "comparator": "gt", "threshold": 15, "unit": "deg"},
    )
    faults = only_fault([rule], {"torso": torso}, base_landmarks(F), [rep])
    assert len(faults) == 1
    f = faults[0]
    assert f.type == "body_swing" and abs(f.value - 30.0) < 1e-6 and f.unit == "deg"
    assert f.severity == "moderate"        # fallback band: (30-15)/15 = 1.0 -> moderate
    assert f.confidence > 0.9              # joints fully visible, no plane discount
    assert set(f.joints) == {LANDMARK_INDEX[n] for n in ("left_hip", "right_hip", "left_shoulder", "right_shoulder")}


def test_rom_asymmetry():
    rep = RepWindow(1, 0, 10, 19, rom=0.0)
    left = np.concatenate([np.linspace(40, 160, 10), np.linspace(160, 40, 10)])   # range 120
    right = np.concatenate([np.linspace(100, 160, 10), np.linspace(160, 100, 10)])  # range 60
    rule = RuleConfig(
        id="rom_asym", type="rom_asymmetry", message="m", joints=["elbow"],
        params={"metric": "elbow", "max_diff": 20, "unit": "deg"},
    )
    faults = only_fault([rule], {"elbow_left": left, "elbow_right": right}, base_landmarks(20), [rep])
    assert len(faults) == 1 and abs(faults[0].value - 60.0) < 1e-6


def test_timing_asymmetry_measures_seconds():
    rep = RepWindow(1, 0, 10, 19, rom=0.0)
    left = np.ones(20) * 160.0
    right = np.ones(20) * 160.0
    left[2] = 40.0   # left valley at frame 2
    right[10] = 40.0  # right valley at frame 10 -> 8 frames / 10fps = 0.8s
    rule = RuleConfig(
        id="timing", type="timing_asymmetry", message="m", joints=["elbow"],
        params={"metric": "elbow", "direction": "valley", "max_seconds": 0.25},
    )
    faults = only_fault([rule], {"elbow_left": left, "elbow_right": right}, base_landmarks(20), [rep])
    assert len(faults) == 1 and abs(faults[0].value - 0.8) < 1e-6 and faults[0].unit == "s"


def test_landmark_drift_reports_side_joint():
    F = 20
    rep = RepWindow(1, 0, 10, 19, rom=0.0)
    lm = base_landmarks(F)
    le = LANDMARK_INDEX["left_elbow"]
    lm[:, le, 0] = np.linspace(0.5, 0.75, F)  # left elbow drifts +0.25 in x
    rule = RuleConfig(
        id="elbow_drift", type="landmark_drift", message="m",
        params={"landmark": "elbow", "reference": "hip", "axis": "x", "aggregate": "range",
                "threshold": 0.1, "sided": True, "unit": "norm"},
    )
    faults = only_fault([rule], {}, lm, [rep])
    assert len(faults) == 1
    assert le in faults[0].joints           # the offending side is highlighted
    assert faults[0].value > 0.1


def test_velocity_order_hips_faster_than_shoulders():
    F = 20
    rep = RepWindow(1, 0, 5, 19, rom=0.0)  # ascent = frames 5..19
    lm = base_landmarks(F)
    lh = LANDMARK_INDEX["left_hip"]
    lm[:, lh, 1] = np.linspace(0.5, 0.1, F)  # hip rises fast; shoulder stays put
    rule = RuleConfig(
        id="hips_fast", type="velocity_order", message="m", joints=["hip", "shoulder"],
        params={"landmark_a": "left_hip", "landmark_b": "left_shoulder", "phase": "ascent",
                "axis": "y", "margin": 0.1, "unit": "/s"},
    )
    faults = only_fault([rule], {}, lm, [rep])
    assert len(faults) == 1 and faults[0].value > 0.1


def test_tempo_consistency_session_level():
    reps = [RepWindow(1, 0, 5, 10, 0.0), RepWindow(2, 10, 15, 20, 0.0), RepWindow(3, 20, 35, 50, 0.0)]
    rule = RuleConfig(
        id="tempo_inconsistent", type="tempo_consistency", message="m", joints=["elbow"],
        params={"max_cv": 25},
    )
    faults = only_fault([rule], {}, base_landmarks(60), reps)
    assert len(faults) == 1 and faults[0].unit == "%"


def test_low_visibility_lowers_confidence():
    rep = RepWindow(1, 0, 10, 19, rom=0.0)
    lm = base_landmarks(20)
    for n in ("left_hip", "right_hip", "left_shoulder", "right_shoulder"):
        lm[:, LANDMARK_INDEX[n], 3] = 0.2  # poorly visible
    torso = np.concatenate([np.linspace(0, 30, 10), np.linspace(30, 0, 10)])
    rule = RuleConfig(
        id="body_swing", type="metric_aggregate", message="m", joints=["hip", "shoulder"],
        params={"metric": "torso", "aggregate": "range", "comparator": "gt", "threshold": 15},
    )
    faults = only_fault([rule], {"torso": torso}, lm, [rep])
    assert len(faults) == 1 and faults[0].confidence < 0.3


def test_nan_metric_does_not_fire():
    rep = RepWindow(1, 0, 10, 19, rom=0.0)
    torso = np.full(20, np.nan)
    rule = RuleConfig(
        id="body_swing", type="metric_aggregate", message="m",
        params={"metric": "torso", "aggregate": "range", "comparator": "gt", "threshold": 15},
    )
    faults = only_fault([rule], {"torso": torso}, base_landmarks(20), [rep])
    assert faults == []
