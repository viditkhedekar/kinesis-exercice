"""Insight cards are deterministic, data-grounded observations.

Each generator is exercised with crafted inputs so the produced sentence, tone,
and emphasis figure are asserted exactly — no real video or MediaPipe needed.
"""
from __future__ import annotations

import numpy as np

from app.exercises import ExerciseConfig, RepConfig
from app.services.feedback import GroupedFault
from app.services.insights import generate_insights
from app.services.reps import RepWindow


def _cfg(key="bicep_curl", signal="elbow", direction="valley") -> ExerciseConfig:
    return ExerciseConfig(
        key=key, name=key.title(), metrics={},
        rep=RepConfig(signal=signal, direction=direction), rules=[],
    )


def _km(**over) -> dict:
    base = {
        "rom": 0.0, "symmetry": None, "symmetry_label": "n/a",
        "tempo": 2.0, "consistency": 0.0, "consistency_label": "n/a",
        "view": "side", "rep_count": 0,
    }
    base.update(over)
    return base


def test_side_timing_insight_names_the_lagging_side():
    # 6 reps of 20 frames; left reaches its valley 2 frames before right → right lags.
    F, R = 120, 6
    left = np.full(F, 170.0)
    right = np.full(F, 170.0)
    reps = []
    for i in range(R):
        s = i * 20
        left[s + 8] = 40.0   # left turnaround at local frame 8
        right[s + 10] = 40.0  # right turnaround at local frame 10 → 2 frames later
        reps.append(RepWindow(i + 1, s, s + 9, s + 19, rom=130.0))

    out = generate_insights(
        reps=reps, metrics={"elbow_left": left, "elbow_right": right},
        config=_cfg(), fps=10.0, groups=[], km=_km(rep_count=R),
        overall=100.0, prev_km=None, prev_overall=None,
    )
    timing = next(i for i in out if i["kind"] == "timing")
    assert "right arm" in timing["text"] and "after your left" in timing["text"]
    assert "6 of 6 reps" in timing["text"]
    assert timing["emphasis"] == "0.20s"


def test_progress_insight_reports_percent_change_vs_previous():
    reps = [RepWindow(i + 1, i * 10, i * 10 + 5, i * 10 + 9, rom=100.0) for i in range(3)]
    out = generate_insights(
        reps=reps, metrics={}, config=_cfg(key="squat", signal="knee"), fps=10.0,
        groups=[], km=_km(rom=100.0, rep_count=3),
        overall=88.0, prev_km=_km(rom=91.7), prev_overall=88.0,
    )
    prog = next(i for i in out if i["kind"] == "progress")
    assert "improved by 9%" in prog["text"]
    assert prog["tone"] == "positive" and prog["emphasis"] == "+9%"


def test_prevalence_insight_states_reps_and_average():
    g = GroupedFault(
        type="insufficient_depth",
        message="Squat stops above parallel — the hip crease stays higher than the knee.",
        tip="Sit the hips down and back.", severity="moderate", unit="deg",
        count=4, affected_reps=[1, 2, 4, 5], avg_value=118.0, worst_value=135.0,
        worst_rep=5, confidence=0.85, side=None, start_frame=40,
    )
    reps = [RepWindow(i + 1, i * 10, i * 10 + 5, i * 10 + 9, rom=80.0) for i in range(6)]
    out = generate_insights(
        reps=reps, metrics={}, config=_cfg(key="squat", signal="knee"), fps=10.0,
        groups=[g], km=_km(rep_count=6), overall=70.0, prev_km=None, prev_overall=None,
    )
    prev = next(i for i in out if i["kind"] == "prevalence")
    assert "Squat stops above parallel on 4 of 6 reps" in prev["text"]
    assert "118°" in prev["text"] and prev["emphasis"] == "4/6 reps"


def test_clean_session_yields_a_positive_card():
    reps = [RepWindow(i + 1, i * 10, i * 10 + 5, i * 10 + 9, rom=90.0) for i in range(5)]
    out = generate_insights(
        reps=reps, metrics={}, config=_cfg(), fps=10.0, groups=[],
        km=_km(rep_count=5, consistency=8.0, consistency_label="good"),
        overall=100.0, prev_km=None, prev_overall=None,
    )
    assert out, "expected at least one insight"
    assert any(i["tone"] == "positive" for i in out)
