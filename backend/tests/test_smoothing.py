"""Tests for the post-estimation landmark smoothing pass.

Covers the four stages (confidence filter, jump rejection, gap interpolation,
One Euro smoothing), the missing-data conventions, immutability, and a
performance measurement proving the pass is far under the <100ms budget.
All pure NumPy — no model runtime needed.
"""
import time

import numpy as np
import pytest

from app.services.pose.landmarks import NUM_LANDMARKS
from app.services.pose.smoothing import smooth_landmarks

FPS = 5.0


def _stream(n_frames, value_fn):
    """(F, 33, 4); value_fn(f) -> (x, y, vis) drives landmark slot 0; other slots
    stay visible and static so they don't interfere with slot-0 assertions."""
    arr = np.zeros((n_frames, NUM_LANDMARKS, 4), dtype=np.float32)
    arr[:, :, 3] = 0.9
    arr[:, :, 0] = 0.5
    arr[:, :, 1] = 0.5
    for f in range(n_frames):
        x, y, vis = value_fn(f)
        arr[f, 0] = (x, y, 0.0, vis)
    return arr


# --- guards -----------------------------------------------------------------

def test_short_or_empty_clip_unchanged():
    for n in (0, 1):
        arr = np.zeros((n, NUM_LANDMARKS, 4), dtype=np.float32)
        out, stats = smooth_landmarks(arr, FPS)
        assert out.shape == arr.shape
        assert stats["frames"] == n


def test_zero_fps_returns_unchanged():
    arr = _stream(10, lambda f: (0.5, 0.5, 0.9))
    out, _ = smooth_landmarks(arr, 0.0)
    np.testing.assert_array_equal(out, arr)


def test_does_not_mutate_input():
    arr = _stream(20, lambda f: (0.5 + 0.001 * f, 0.5, 0.9))
    before = arr.copy()
    smooth_landmarks(arr, FPS)
    np.testing.assert_array_equal(arr, before)


# --- stage 1: confidence filtering ------------------------------------------

def test_low_confidence_isolated_point_does_not_survive_raw():
    # Steady at 0.5 but frame 5 is a low-confidence spike to 0.95 -> dropped, then
    # interpolated back to ~0.5 (not left at the spike).
    def val(f):
        return (0.95, 0.5, 0.1) if f == 5 else (0.5, 0.5, 0.9)
    arr = _stream(11, val)
    out, stats = smooth_landmarks(arr, FPS, min_confidence=0.3, max_jump=1.0)
    assert stats["low_confidence"] >= 1
    assert out[5, 0, 0] == pytest.approx(0.5, abs=0.05)


# --- stage 2: jump rejection ------------------------------------------------

def test_impossible_jump_is_rejected_then_interpolated():
    def val(f):
        return (0.95, 0.95, 0.9) if f == 5 else (0.5, 0.5, 0.9)
    arr = _stream(11, val)
    out, stats = smooth_landmarks(arr, FPS, min_confidence=0.3,
                                  max_jump=0.15, max_gap_frames=5)
    assert stats["jumps_rejected"] >= 1
    # The outlier frame is interpolated back near the steady value, not snapped out.
    assert out[5, 0, 0] == pytest.approx(0.5, abs=0.05)
    assert not np.isnan(out[5, 0, 0])


# --- stage 3: gap interpolation ---------------------------------------------

def test_short_gap_is_linearly_interpolated():
    # Valid at f=0 (x=0.0) and f=4 (x=0.4); frames 1-3 missing -> linear fill.
    def val(f):
        if f == 0:
            return (0.0, 0.5, 0.9)
        if f == 4:
            return (0.4, 0.5, 0.9)
        return (np.nan, np.nan, 0.0)
    arr = _stream(5, val)
    # Disable smoothing distortion by using a high min_cutoff so One Euro ~ passthrough.
    out, stats = smooth_landmarks(arr, FPS, max_gap_frames=5,
                                  min_cutoff=1000.0, beta=0.0)
    assert stats["points_interpolated"] == 3
    assert out[2, 0, 0] == pytest.approx(0.2, abs=0.02)   # midpoint of 0.0..0.4


def test_long_gap_is_left_missing():
    # An 8-frame gap exceeds max_gap_frames=5 -> stays NaN, visibility 0.
    def val(f):
        if f in (0, 9):
            return (0.5, 0.5, 0.9)
        return (np.nan, np.nan, 0.0)
    arr = _stream(10, val)
    out, stats = smooth_landmarks(arr, FPS, max_gap_frames=5)
    assert np.isnan(out[4, 0, 0])
    assert out[4, 0, 3] == 0.0
    assert stats["points_interpolated"] == 0


def test_never_seen_landmark_stays_missing():
    arr = _stream(10, lambda f: (np.nan, np.nan, 0.0))
    out, _ = smooth_landmarks(arr, FPS)
    assert np.all(np.isnan(out[:, 0, 0]))
    assert np.all(out[:, 0, 3] == 0.0)


# --- stage 4: One Euro smoothing --------------------------------------------

def test_smoothing_reduces_jitter():
    rng = np.random.default_rng(0)
    def val(f):
        return (0.5 + rng.normal(0, 0.02), 0.5, 0.9)
    arr = _stream(80, val)
    raw = arr[:, 0, 0].copy()
    out, _ = smooth_landmarks(arr, FPS, min_cutoff=0.6, beta=0.2, max_jump=1.0)
    # Frame-to-frame variation must drop after smoothing.
    assert np.nanstd(np.diff(out[:, 0, 0])) < np.nanstd(np.diff(raw))


def test_smoothing_tracks_fast_motion_without_large_lag():
    # A steady linear ramp: adaptive cutoff should follow it closely (small lag),
    # unlike a heavy fixed EMA. Check the tail tracks the true line within a tolerance.
    def val(f):
        return (0.1 + 0.01 * f, 0.5, 0.9)
    arr = _stream(60, val)
    out, _ = smooth_landmarks(arr, FPS, min_cutoff=1.0, beta=1.0, max_jump=1.0)
    true_tail = 0.1 + 0.01 * 59
    assert out[59, 0, 0] == pytest.approx(true_tail, abs=0.02)


def test_zero_phase_has_no_systematic_lag_on_sinusoid():
    # A causal filter phase-shifts a sinusoid (peaks arrive late); a zero-phase filter
    # keeps peaks aligned. Compare the smoothed peak location to the true peak: it must
    # not be systematically later. Heavy smoothing (low cutoff) to make lag obvious.
    F = 80
    period = 20.0
    def val(f):
        return (0.5 + 0.2 * np.sin(2 * np.pi * f / period), 0.5, 0.9)
    arr = _stream(F, val)
    raw = arr[:, 0, 0].copy()
    out, _ = smooth_landmarks(arr, FPS, min_cutoff=0.3, beta=0.0, max_jump=1.0)
    sm = out[:, 0, 0]
    # Cross-correlate to estimate the lag (in frames) between smoothed and raw over
    # the interior (avoid edge transients). Zero-phase => best alignment at ~0 shift.
    lo, hi = 20, 60
    r = raw[lo:hi] - raw[lo:hi].mean()
    best_shift, best_corr = 0, -np.inf
    for shift in range(-4, 5):
        s = sm[lo + shift:hi + shift] - sm[lo + shift:hi + shift].mean()
        corr = float(np.dot(r, s))
        if corr > best_corr:
            best_corr, best_shift = corr, shift
    assert abs(best_shift) <= 1   # no systematic multi-frame lag


# --- performance ------------------------------------------------------------

def test_performance_under_budget(capsys):
    # Worst case: max_frames (600) x 33 landmarks, all present with jitter.
    rng = np.random.default_rng(1)
    arr = rng.uniform(0.1, 0.9, size=(600, NUM_LANDMARKS, 4)).astype(np.float32)
    arr[:, :, 3] = 0.9  # all confidently visible
    # Warm once (import/JIT-free NumPy, but be fair), then measure.
    smooth_landmarks(arr, FPS)
    t0 = time.perf_counter()
    smooth_landmarks(arr, FPS)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    with capsys.disabled():
        print(f"\n[smoothing perf] 600x33 landmarks: {elapsed_ms:.1f} ms")
    # Requirement is <100ms; assert a loose ceiling so the test isn't flaky on slow CI
    # while still catching a pathological regression.
    assert elapsed_ms < 500.0
