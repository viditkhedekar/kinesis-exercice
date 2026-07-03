"""Rep detection: one generic detector driven by the exercise config.

Reads ``config.rep.signal`` (a metric name), smooths it, finds the movement
extrema (valleys for squat/curl/push-up bottoms, peaks for the inverse), and
pairs them into reps ``(start, bottom, end)``. The algorithm is fully
exercise-agnostic — the config selects the signal, direction, and thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks, savgol_filter

from app.exercises import ExerciseConfig

# The exercise YAMLs express rep-detection windows in *frames*, tuned assuming a
# ~30fps source. When pose runs at a lower effective fps (see run_pose), these
# frame counts are rescaled by fps / AUTHOR_FPS so the timing stays equivalent.
AUTHOR_FPS = 30.0


@dataclass
class RepWindow:
    index: int
    start: int
    bottom: int
    end: int
    rom: float  # range of motion of the signal across the rep


def _smooth(signal: np.ndarray, window: int) -> np.ndarray:
    # Interpolate NaNs (missing detections) so the filter stays continuous.
    s = signal.astype(float).copy()
    nans = np.isnan(s)
    if nans.all():
        return s
    if nans.any():
        idx = np.arange(len(s))
        s[nans] = np.interp(idx[nans], idx[~nans], s[~nans])
    if window >= 3 and len(s) >= window:
        win = window if window % 2 == 1 else window + 1
        win = min(win, len(s) if len(s) % 2 == 1 else len(s) - 1)
        if win >= 3:
            s = savgol_filter(s, win, polyorder=2)
    return s


def detect_reps(
    metrics: dict[str, np.ndarray], config: ExerciseConfig, fps: float = AUTHOR_FPS
) -> list[RepWindow]:
    rc = config.rep
    if rc.signal not in metrics:
        return []
    raw = metrics[rc.signal]
    if len(raw) == 0:
        return []

    # Rescale frame-unit tuning to the actual (possibly downsampled) fps.
    scale = (fps / AUTHOR_FPS) if fps and fps > 0 else 1.0
    smooth_window = max(3, round(rc.smooth_window * scale))
    min_distance_frames = max(2, round(rc.min_distance_frames * scale))

    sig = _smooth(raw, smooth_window)

    # Detect "bottoms" of the movement. For a valley-based exercise we invert
    # the signal so find_peaks locates the minima.
    search = -sig if rc.direction == "valley" else sig
    bottoms, _ = find_peaks(
        search, prominence=rc.min_prominence, distance=min_distance_frames
    )
    bottoms = list(bottoms)
    if not bottoms:
        return []

    # The "top" extrema between consecutive bottoms define rep boundaries.
    tops = _find_tops(sig, bottoms, rc.direction)

    reps: list[RepWindow] = []
    for i, bottom in enumerate(bottoms):
        start = tops[i]
        end = tops[i + 1]
        # Optional gating: bottom must pass the bottom_threshold to count as a rep.
        if rc.bottom_threshold is not None:
            if rc.direction == "valley" and sig[bottom] > rc.bottom_threshold:
                continue
            if rc.direction == "peak" and sig[bottom] < rc.bottom_threshold:
                continue
        seg = sig[start : end + 1]
        rom = float(np.nanmax(seg) - np.nanmin(seg)) if len(seg) else 0.0
        reps.append(RepWindow(index=len(reps) + 1, start=int(start), bottom=int(bottom), end=int(end), rom=rom))
    return reps


def _find_tops(sig: np.ndarray, bottoms: list[int], direction: str) -> list[int]:
    """Boundary 'top' frames: before the first bottom, between bottoms, after last."""
    tops: list[int] = []
    # leading boundary
    tops.append(int(np.argmax(sig[: bottoms[0] + 1])) if direction == "valley"
                else int(np.argmin(sig[: bottoms[0] + 1])))
    for a, b in zip(bottoms, bottoms[1:]):
        seg = sig[a : b + 1]
        rel = int(np.argmax(seg)) if direction == "valley" else int(np.argmin(seg))
        tops.append(a + rel)
    # trailing boundary
    last = bottoms[-1]
    seg = sig[last:]
    rel = int(np.argmax(seg)) if direction == "valley" else int(np.argmin(seg))
    tops.append(last + rel)
    return tops
