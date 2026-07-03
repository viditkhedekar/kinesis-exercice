"""Synthetic landmark builders for deterministic pipeline tests.

We place a side-view skeleton so that the knee angle (hip-knee-ankle) equals a
prescribed value per frame, and the torso (hip->shoulder) leans by a prescribed
amount. This lets us assert rep counts, scores, and specific faults without any
real video or MediaPipe.
"""
from __future__ import annotations

import numpy as np

from app.services.pose.landmarks import LANDMARK_INDEX, NUM_LANDMARKS

THIGH = 0.30
TORSO = 0.30
SHANK_Y = 0.30


def _side_points(knee_angle_deg: float, lean_deg: float, x_off: float):
    t = np.radians(knee_angle_deg)
    lean = np.radians(lean_deg)
    ankle = np.array([0.5 + x_off, 0.90])
    knee = np.array([0.5 + x_off, 0.90 - SHANK_Y])
    hip = knee + THIGH * np.array([-np.sin(t), np.cos(t)])  # angle(hip,knee,ankle)=t
    shoulder = hip + TORSO * np.array([-np.sin(lean), -np.cos(lean)])  # lean from vertical
    return hip, knee, ankle, shoulder


def squat_landmarks(
    knee_angles: list[float], lean_deg: float = 0.0, asym_deg: float = 0.0
) -> np.ndarray:
    """Build (F, 33, 4) landmarks. ``asym_deg`` offsets the right knee angle."""
    frames = []
    for ang in knee_angles:
        lm = np.full((NUM_LANDMARKS, 4), np.nan, dtype=np.float32)
        for side, x_off, extra in (("left", -0.05, 0.0), ("right", 0.05, asym_deg)):
            hip, knee, ankle, shoulder = _side_points(ang + extra, lean_deg, x_off)
            for name, pt in (
                (f"{side}_hip", hip),
                (f"{side}_knee", knee),
                (f"{side}_ankle", ankle),
                (f"{side}_shoulder", shoulder),
            ):
                idx = LANDMARK_INDEX[name]
                lm[idx, 0], lm[idx, 1], lm[idx, 3] = pt[0], pt[1], 1.0
        frames.append(lm)
    return np.stack(frames)


def knee_series(n_reps: int, top: float = 165.0, bottom: float = 85.0, ramp: int = 25) -> list[float]:
    """A clean rep signal: ``top`` -> ``bottom`` -> ``top`` repeated ``n_reps`` times.

    ``ramp`` of 25 frames per phase makes a rep ~1.7s at 30fps — a controlled,
    realistic tempo that shouldn't trip the 'rushed' tempo rule."""
    series: list[float] = [top] * 5
    for _ in range(n_reps):
        series += list(np.linspace(top, bottom, ramp))
        series += list(np.linspace(bottom, top, ramp))
    series += [top] * 5
    return series
