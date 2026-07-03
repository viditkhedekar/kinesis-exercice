import numpy as np

from app.exercises import load_exercise
from app.services.biomechanics import angle, compute_metrics, segment_vertical_angle
from tests.synthetic import squat_landmarks


def test_angle_right_angle():
    a = np.array([[0.0, 1.0]])
    b = np.array([[0.0, 0.0]])
    c = np.array([[1.0, 0.0]])
    assert abs(angle(a, b, c)[0] - 90.0) < 1e-3


def test_segment_vertical_angle_zero_when_vertical():
    a = np.array([[0.5, 0.9]])
    b = np.array([[0.5, 0.4]])  # directly above
    assert segment_vertical_angle(a, b)[0] < 1e-3


def test_compute_metrics_recovers_knee_angle():
    config = load_exercise("squat")
    lm = squat_landmarks([90.0, 90.0, 90.0])
    metrics = compute_metrics(lm, config)
    assert np.allclose(metrics["knee"], 90.0, atol=1.0)
    assert "knee_left" in metrics and "knee_right" in metrics


def test_torso_lean_metric_tracks_lean():
    config = load_exercise("squat")
    lm = squat_landmarks([120.0], lean_deg=30.0)
    metrics = compute_metrics(lm, config)
    assert abs(metrics["torso"][0] - 30.0) < 2.0
