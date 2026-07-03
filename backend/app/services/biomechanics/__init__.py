"""Biomechanics: derive scalar metric time-series from landmark arrays.

Pure NumPy. Given a landmark array ``(F, 33, 4)`` and an ``ExerciseConfig``,
produce ``{metric_name: ndarray(F)}``. Sided metrics additionally emit
``<name>_left`` and ``<name>_right``; the bare ``<name>`` is their per-frame mean.

Metric primitives:
- ``angle``                  interior angle at points[1] (degrees, 0..180)
- ``segment_vertical_angle`` deviation of segment points[0]->points[1] from
                             vertical (degrees, 0 = vertical)
- ``horizontal_offset``      signed x(points[0]) - x(points[1]) (normalized units)
- ``distance``               euclidean distance between points[0] and points[1]
- ``coordinate``             a single landmark's x or y (axis), for L/R position checks

All functions tolerate NaN landmarks (missing detections) and propagate NaN.
"""
from __future__ import annotations

import numpy as np

from app.exercises import ExerciseConfig, MetricConfig
from app.services.pose.landmarks import SIDED, resolve

EPS = 1e-9


def _xy(landmarks: np.ndarray, index: int) -> np.ndarray:
    """Return (F, 2) image-space x,y for a landmark index."""
    return landmarks[:, index, :2]


def angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Interior angle at b formed by a-b-c, per frame, in degrees."""
    ba = a - b
    bc = c - b
    dot = (ba * bc).sum(axis=1)
    nba = np.linalg.norm(ba, axis=1)
    nbc = np.linalg.norm(bc, axis=1)
    cos = np.clip(dot / (nba * nbc + EPS), -1.0, 1.0)
    return np.degrees(np.arccos(cos))


def segment_vertical_angle(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Deviation of segment a->b from the vertical axis, in degrees (0..90)."""
    v = b - a
    horizontal = np.abs(v[:, 0])
    vertical = np.abs(v[:, 1])
    return np.degrees(np.arctan2(horizontal, vertical + EPS))


def horizontal_offset(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Signed normalized horizontal offset x(a) - x(b)."""
    return a[:, 0] - b[:, 0]


def _points_for_side(points: list[str], side: str | None, landmarks: np.ndarray) -> list[np.ndarray]:
    return [_xy(landmarks, resolve(name, side)) for name in points]


def _eval_metric(mc: MetricConfig, side: str | None, landmarks: np.ndarray) -> np.ndarray:
    pts = _points_for_side(mc.points, side, landmarks)
    if mc.type == "angle":
        return angle(pts[0], pts[1], pts[2])
    if mc.type == "segment_vertical_angle":
        return segment_vertical_angle(pts[0], pts[1])
    if mc.type == "horizontal_offset":
        return horizontal_offset(pts[0], pts[1])
    if mc.type == "distance":
        return np.linalg.norm(pts[0] - pts[1], axis=1)
    if mc.type == "coordinate":
        axis = 0 if mc.axis == "x" else 1
        return pts[0][:, axis]
    raise ValueError(f"Unknown metric type: {mc.type!r}")


def compute_metrics(landmarks: np.ndarray, config: ExerciseConfig) -> dict[str, np.ndarray]:
    metrics: dict[str, np.ndarray] = {}
    for name, mc in config.metrics.items():
        if mc.sided:
            left = _eval_metric(mc, "left", landmarks)
            right = _eval_metric(mc, "right", landmarks)
            metrics[f"{name}_left"] = left
            metrics[f"{name}_right"] = right
            metrics[name] = np.nanmean(np.vstack([left, right]), axis=0)
        else:
            metrics[name] = _eval_metric(mc, None, landmarks)

    # Apply normalization (divide by another already-computed metric) as a 2nd pass.
    for name, mc in config.metrics.items():
        if mc.normalize_by and mc.normalize_by in metrics:
            denom = metrics[mc.normalize_by]
            for key in ([name, f"{name}_left", f"{name}_right"] if mc.sided else [name]):
                if key in metrics:
                    metrics[key] = metrics[key] / (np.abs(denom) + EPS)
    return metrics


def hip_width(landmarks: np.ndarray) -> np.ndarray:
    """Convenience derived scale: distance between hips per frame (normalized)."""
    lh = _xy(landmarks, SIDED["hip"][0])
    rh = _xy(landmarks, SIDED["hip"][1])
    return np.linalg.norm(lh - rh, axis=1)


def _center(landmarks: np.ndarray, joint: str) -> np.ndarray:
    """Midpoint of a sided joint per frame, shape (F, 2)."""
    a, b = SIDED[joint]
    return (_xy(landmarks, a) + _xy(landmarks, b)) / 2.0


def body_scale(landmarks: np.ndarray) -> float:
    """A robust per-video length scale: median torso length (shoulder-centre to
    hip-centre) over reasonably-visible frames, in normalized image units.

    Torso length is view-stable — unlike hip/shoulder *width*, it does not
    collapse toward zero in a side view (where left/right landmarks overlap),
    so it is a reliable denominator for turning pixel displacements into
    meaningful "% of body" measurements.
    """
    if len(landmarks) == 0:
        return 0.25
    shoulder_c = _center(landmarks, "shoulder")
    hip_c = _center(landmarks, "hip")
    torso = np.linalg.norm(shoulder_c - hip_c, axis=1)
    torso = torso[~np.isnan(torso)]
    if torso.size == 0:
        return 0.25
    scale = float(np.median(torso))
    return scale if scale > 1e-3 else 0.25


def camera_view(landmarks: np.ndarray) -> str:
    """Estimate the filming angle from shoulder-width / torso-length ratio.

    Front-on: shoulders appear wide relative to torso. Side-on: shoulders
    overlap so the ratio is small. Used to discount confidence for faults whose
    plane is poorly observed from the detected angle.
    """
    if len(landmarks) == 0:
        return "oblique"
    ls = _xy(landmarks, SIDED["shoulder"][0])
    rs = _xy(landmarks, SIDED["shoulder"][1])
    sw = np.linalg.norm(ls - rs, axis=1)
    sw = sw[~np.isnan(sw)]
    scale = body_scale(landmarks)
    if sw.size == 0 or scale <= 0:
        return "oblique"
    ratio = float(np.median(sw)) / scale
    if ratio >= 0.55:
        return "front"
    if ratio <= 0.28:
        return "side"
    return "oblique"
