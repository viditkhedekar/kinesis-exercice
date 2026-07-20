"""Lightweight post-processing to de-jitter the per-frame landmark stream.

MediaPipe (even in VIDEO/tracking mode) leaves visible frame-to-frame jitter,
occasional low-confidence points that jump, and brief dropouts. This module
cleans the assembled ``(F, 33, 4)`` array *after* pose estimation — it never
touches the model, the input resolution, or the processed fps, so it adds no
inference cost. It is pure NumPy and independently unit-testable.

Four stages, per landmark across the time axis:

1. **Confidence filtering** — a reading below ``min_confidence`` is dropped
   (treated as missing) so a flickering low-confidence point can't yank the
   overlay around.
2. **Velocity / jump rejection** — a reading that moves more than ``max_jump``
   (normalized image units) from the last accepted position in one frame is an
   impossible move for a body joint; it's rejected as a misdetection.
3. **Gap interpolation** — missing/rejected points are linearly interpolated in
   time from their neighbours (not snapped and not held), so a briefly occluded
   joint glides through the gap. Gaps longer than ``max_gap_frames`` are left
   missing rather than inventing a long straight-line path.
4. **Zero-phase One Euro smoothing** — the filled signal is passed through a One
   Euro filter (Casiez et al. 2012), applied *forward and backward and averaged*.
   One Euro's cutoff adapts to speed: strong smoothing when a joint is nearly still
   (removes jitter), light when it moves fast (avoids the lag a fixed-alpha EMA
   would add). Running it zero-phase (we have the whole clip) cancels the residual
   causal lag, so the smoothed skeleton doesn't trail the person.

Missing landmarks that can't be anchored (never confidently seen, or inside an
over-long gap) stay NaN with visibility 0 — the pipeline's existing convention.
"""
from __future__ import annotations

import math

import numpy as np


def _one_euro(signal: np.ndarray, present: np.ndarray, dt: float,
              min_cutoff: float, beta: float, d_cutoff: float) -> np.ndarray:
    """One Euro filter over ``signal`` (F, S) with a per-element ``present`` mask.

    Runs S independent scalar filters in parallel (vectorized across the S columns)
    with one sequential pass over the F frames. Absent samples pass through as NaN
    and reset that column's filter state so smoothing never blends across a real gap.
    """
    F, S = signal.shape
    out = np.full((F, S), np.nan, dtype=np.float64)

    def alpha(cutoff: np.ndarray) -> np.ndarray:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    a_d = 1.0 / (1.0 + (1.0 / (2.0 * math.pi * d_cutoff)) / dt)  # scalar

    have = np.zeros(S, dtype=bool)          # is there prior state for this column?
    x_prev = np.zeros(S, dtype=np.float64)  # last raw value
    x_hat = np.zeros(S, dtype=np.float64)   # last smoothed value
    dx_hat = np.zeros(S, dtype=np.float64)  # last smoothed derivative

    for f in range(F):
        cur = signal[f]
        p = present[f]
        first = p & ~have          # first accepted sample for this column
        cont = p & have            # continuing an existing track

        # Derivative + adaptive cutoff for continuing columns.
        dx = np.zeros(S, dtype=np.float64)
        dx[cont] = (cur[cont] - x_prev[cont]) / dt
        dxh = a_d * dx + (1.0 - a_d) * dx_hat
        cutoff = min_cutoff + beta * np.abs(dxh)
        a = alpha(cutoff)

        new_hat = x_hat.copy()
        new_hat[cont] = a[cont] * cur[cont] + (1.0 - a[cont]) * x_hat[cont]
        new_hat[first] = cur[first]           # seed the filter with the first value

        # Emit.
        out[f, first] = cur[first]
        out[f, cont] = new_hat[cont]

        # Update state: advance where present, reset where absent (gap -> fresh start).
        x_hat = np.where(p, new_hat, 0.0)
        x_prev = np.where(p, cur, 0.0)
        dx_hat = np.where(cont, dxh, 0.0)   # first-appearance derivative seeds at 0
        have = p
    return out


def _one_euro_zerophase(signal: np.ndarray, present: np.ndarray, dt: float,
                        min_cutoff: float, beta: float, d_cutoff: float) -> np.ndarray:
    """Zero-phase One Euro: filter forward and backward, then average.

    A causal One Euro necessarily lags the true signal (it only sees the past),
    which shows up as the overlay skeleton trailing the person. Because we process
    the *whole clip offline*, we can run the filter both directions and average —
    the forward pass lags, the backward pass leads by the same amount, so the two
    cancel and the result has no net temporal shift. ``present`` positions are the
    same in both directions, so where either pass is NaN the average is NaN too.
    """
    fwd = _one_euro(signal, present, dt, min_cutoff, beta, d_cutoff)
    bwd = _one_euro(signal[::-1], present[::-1], dt, min_cutoff, beta, d_cutoff)[::-1]
    return 0.5 * (fwd + bwd)


def _interp_gaps(y: np.ndarray, valid: np.ndarray, max_gap: int) -> np.ndarray:
    """Linearly interpolate invalid entries of 1-D ``y`` from valid neighbours,
    leaving runs of invalid samples longer than ``max_gap`` as NaN."""
    F = y.shape[0]
    out = y.astype(np.float64).copy()
    vidx = np.flatnonzero(valid)
    if vidx.size == 0:
        out[:] = np.nan
        return out
    # np.interp fills interior gaps and holds the edge value beyond the ends.
    filled = np.interp(np.arange(F), vidx, y[vidx])
    out[:] = filled
    # Blank any maximal invalid run longer than max_gap (interior or edge).
    inv = ~valid
    i = 0
    while i < F:
        if inv[i]:
            j = i
            while j < F and inv[j]:
                j += 1
            if (j - i) > max_gap:
                out[i:j] = np.nan
            i = j
        else:
            i += 1
    return out


def smooth_landmarks(
    landmarks: np.ndarray,
    fps: float,
    *,
    min_confidence: float = 0.3,
    max_jump: float = 0.15,
    max_gap_frames: int = 5,
    min_cutoff: float = 1.0,
    beta: float = 0.5,
    d_cutoff: float = 1.0,
) -> tuple[np.ndarray, dict]:
    """Return ``(smoothed (F, 33, 4), stats)``. Input is not mutated.

    ``stats`` reports how much cleanup happened (low-confidence drops, jumps
    rejected, gaps interpolated) — useful signal on framing/lighting quality.
    A clip shorter than 2 frames, or ``fps <= 0``, is returned unchanged.
    """
    arr = np.asarray(landmarks, dtype=np.float32)
    F = arr.shape[0]
    L = arr.shape[1] if arr.ndim == 3 else 0
    stats = {"frames": int(F), "low_confidence": 0, "jumps_rejected": 0,
             "points_interpolated": 0}
    if F < 2 or fps <= 0:
        return arr.copy(), stats

    out = arr.copy()
    xy = out[:, :, :2]              # (F, L, 2) view into out
    vis = out[:, :, 3]             # (F, L) view into out
    dt = 1.0 / float(fps)

    # 1. Confidence filter. A NaN coord already means "no detection".
    valid = (vis >= min_confidence) & ~np.isnan(xy[:, :, 0]) & ~np.isnan(xy[:, :, 1])
    stats["low_confidence"] = int(np.count_nonzero(
        ~valid & ~np.isnan(arr[:, :, 0]) & (arr[:, :, 3] < min_confidence)))

    # 2. Velocity / jump rejection — sequential over frames, vectorized over L.
    #    ``max_jump`` is a per-FRAME speed cap, so the allowed displacement scales
    #    with the number of frames since the last accepted reading. Comparing raw
    #    distance without that scaling would falsely reject a joint that legitimately
    #    moved across a multi-frame gap.
    last = np.full((L, 2), np.nan, dtype=np.float64)   # last accepted position
    last_f = np.full(L, -1, dtype=np.int64)            # frame of last accepted (-1 = none)
    for f in range(F):
        v = valid[f]
        both = v & (last_f >= 0)
        if np.any(both):
            idx = np.flatnonzero(both)
            d = np.linalg.norm(xy[f][idx] - last[idx], axis=1)
            elapsed = (f - last_f[idx]).astype(np.float64)   # >= 1
            reject = np.zeros(L, dtype=bool)
            reject[idx[d > max_jump * elapsed]] = True
            if np.any(reject):
                stats["jumps_rejected"] += int(np.count_nonzero(reject))
                valid[f][reject] = False
                v = valid[f]
        last[v] = xy[f][v].astype(np.float64)
        last_f[v] = f
        # last/last_f are held (not cleared) across gaps, so the reference persists.

    # 3. Interpolate gaps (per landmark, per axis) + carry visibility through them.
    for j in range(L):
        col_valid = valid[:, j]
        if col_valid.all() or not col_valid.any():
            if not col_valid.any():
                xy[:, j, :] = np.nan
                vis[:, j] = 0.0
            continue
        xy[:, j, 0] = _interp_gaps(xy[:, j, 0], col_valid, max_gap_frames)
        xy[:, j, 1] = _interp_gaps(xy[:, j, 1], col_valid, max_gap_frames)
        vis[:, j] = _interp_gaps(vis[:, j], col_valid, max_gap_frames)
        # After interp, a point is "filled" where it wasn't valid but now has coords.
        filled_now = (~col_valid) & ~np.isnan(xy[:, j, 0])
        stats["points_interpolated"] += int(np.count_nonzero(filled_now))
        # Points still NaN (over-long gaps / unanchored) -> visibility 0.
        still_missing = np.isnan(xy[:, j, 0])
        vis[still_missing, j] = 0.0

    # 4. Zero-phase One Euro smoothing over the filled signal (present = has coords).
    #    Zero-phase so the smoothing itself adds NO lag — the overlay must not trail
    #    the person.
    present = ~np.isnan(xy[:, :, 0])
    flat = xy.reshape(F, L * 2)
    pres_flat = np.repeat(present, 2, axis=1)
    smoothed = _one_euro_zerophase(flat, pres_flat, dt, min_cutoff, beta, d_cutoff)
    xy[:, :, :] = smoothed.reshape(F, L, 2).astype(np.float32)

    return out, stats
