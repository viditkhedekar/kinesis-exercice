"""All ten exercises are fully configured and engine-ready.

Guards against a malformed YAML or a rule/metric that references a metric name
or landmark the engine can't resolve. Uses generic landmarks so every exercise's
metrics + rules evaluate without raising, independent of movement specifics.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.exercises import available_exercises, load_exercise
from app.services.biomechanics import compute_metrics
from app.services.reps import RepWindow, detect_reps
from app.services.rules import evaluate_session

EXPECTED = {
    "squat", "deadlift", "bicep_curl", "lateral_raise", "pushup",
    "chest_press", "cable_row", "tricep_pushdown", "shoulder_press", "lat_pulldown",
}


def _generic_landmarks(F: int = 40) -> np.ndarray:
    lm = np.zeros((F, 33, 4), dtype=float)
    lm[:, :, 0] = 0.5
    lm[:, :, 1] = 0.5
    lm[:, :, 3] = 1.0
    return lm


def test_all_ten_exercises_available():
    keys = {e.key for e in available_exercises()}
    assert EXPECTED <= keys, f"missing: {EXPECTED - keys}"


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_config_metrics_and_rules_evaluate(key):
    config = load_exercise(key)
    lm = _generic_landmarks()

    # Every metric referenced by a rule must exist in the computed metric set.
    metrics = compute_metrics(lm, config)
    for rule in config.rules:
        m = rule.params.get("metric")
        if m is not None:
            assert m in metrics or f"{m}_left" in metrics, (
                f"{key}: rule {rule.id} references unknown metric {m!r}"
            )

    # detect_reps + evaluate_session must run without raising on generic data.
    reps = detect_reps(metrics, config, fps=15.0)
    dummy = [RepWindow(1, 0, len(lm) // 2, len(lm) - 1, rom=0.0)]
    evaluate_session(reps or dummy, metrics, lm, config, 15.0)
