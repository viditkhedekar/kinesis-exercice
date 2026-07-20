"""Regression tests for ``_assess_quality`` — the clip-trust gate that decides
whether to warn the user we couldn't see them (``no_subject``) or couldn't find
any reps (``no_reps``).

The load-bearing bug these guard against: the MediaPipe->MoveNet switch. MoveNet
fills only 17 of the 33 MediaPipe landmark slots and leaves the other 16 at
visibility 0. The presence metric used to average over all 33 slots, capping a
*perfect* MoveNet detection at 17/33 = 0.515 and firing ``no_subject`` on normal
videos. Scoring over ``CORE_PRESENCE_LANDMARKS`` (joints every backend emits)
fixes it. These tests pin the threshold boundaries and the NaN handling so the
regression can't silently return.
"""
import numpy as np
import pytest

from app.exercises import load_exercise
from app.services.pipeline import _assess_quality
from app.services.pose.landmarks import CORE_PRESENCE_LANDMARKS, NUM_LANDMARKS
from app.services.pose.movenet import keypoints_to_landmarks

CORE = list(CORE_PRESENCE_LANDMARKS)


@pytest.fixture
def config():
    return load_exercise("squat")


def _frames(n_frames: int, *, core_vis: float, other_vis: float = 0.0,
            core_nan: bool = False) -> np.ndarray:
    """Build an ``(F, 33, 4)`` landmark array with a chosen visibility for the
    core (every-backend) slots and for the remaining slots.

    ``core_nan`` marks the core slots as fully undetected (NaN coords, NaN vis),
    the "no detection this frame" convention the pose service emits.
    """
    lm = np.zeros((n_frames, NUM_LANDMARKS, 4), dtype=np.float32)
    lm[:, :, 3] = other_vis
    if core_nan:
        lm[:, CORE, :] = np.nan
    else:
        lm[:, CORE, 3] = core_vis
    return lm


# --- threshold boundaries ---------------------------------------------------
# _assess_quality flags no_subject when the fraction of frames whose mean core
# visibility is >= 0.5 falls BELOW 0.4. Two nested thresholds: per-frame 0.5,
# then per-clip 0.4.

def test_all_frames_clearly_visible_passes(config):
    lm = _frames(10, core_vis=0.9)
    assert _assess_quality(lm, {}, config, rep_count=3) is None


def test_all_frames_invisible_flags_no_subject(config):
    lm = _frames(10, core_vis=0.0)
    warn = _assess_quality(lm, {}, config, rep_count=3)
    assert warn is not None and warn["kind"] == "no_subject"


def test_per_frame_visibility_just_below_half_flags(config):
    # Every frame at 0.49 mean core vis -> 0 frames "present" -> present_frac 0.
    lm = _frames(10, core_vis=0.49)
    warn = _assess_quality(lm, {}, config, rep_count=3)
    assert warn is not None and warn["kind"] == "no_subject"


def test_per_frame_visibility_exactly_half_passes(config):
    # 0.5 is inclusive (>= 0.5), so every frame counts as present.
    lm = _frames(10, core_vis=0.5)
    assert _assess_quality(lm, {}, config, rep_count=3) is None


def test_clip_fraction_just_below_threshold_flags(config):
    # 3 of 10 frames present (0.30) < 0.40 -> flagged.
    lm = np.zeros((10, NUM_LANDMARKS, 4), dtype=np.float32)
    lm[:3, CORE, 3] = 0.9
    warn = _assess_quality(lm, {}, config, rep_count=3)
    assert warn is not None and warn["kind"] == "no_subject"


def test_clip_fraction_just_above_threshold_passes(config):
    # 5 of 10 frames present (0.50) >= 0.40 -> passes.
    lm = np.zeros((10, NUM_LANDMARKS, 4), dtype=np.float32)
    lm[:5, CORE, 3] = 0.9
    assert _assess_quality(lm, {}, config, rep_count=3) is None


def test_clip_fraction_at_exact_boundary_passes(config):
    # 4 of 10 present -> present_frac 0.40; the check is `< 0.4`, so 0.40 passes.
    lm = np.zeros((10, NUM_LANDMARKS, 4), dtype=np.float32)
    lm[:4, CORE, 3] = 0.9
    assert _assess_quality(lm, {}, config, rep_count=3) is None


# --- the MoveNet regression -------------------------------------------------

def test_movenet_perfect_detection_is_not_flagged(config):
    """A perfect MoveNet detection (all 17 keypoints @ high score, the other 16
    MediaPipe slots left at visibility 0) must NOT be flagged. This is the exact
    case the old all-33 average failed."""
    kps = np.zeros((17, 3), dtype=np.float32)
    kps[:, 2] = 0.95  # every COCO keypoint confidently detected
    frame = keypoints_to_landmarks(kps)          # (33, 4), 16 slots at vis 0
    lm = np.stack([frame] * 10)                  # (10, 33, 4)

    # Sanity: this array really is the MoveNet shape (16 slots at visibility 0).
    assert float(np.mean(lm[0, :, 3] == 0.0)) > 0.4

    assert _assess_quality(lm, {}, config, rep_count=3) is None


def test_all33_average_would_have_flagged_movenet(config):
    """Documents *why* the fix matters: the old all-33 mean of a perfect MoveNet
    detection lands at 17/33, right at the 0.5 per-frame line, and any realistic
    sub-1.0 confidence drops it below — reproducing the false ``no_subject``."""
    kps = np.zeros((17, 3), dtype=np.float32)
    kps[:, 2] = 0.75
    frame = keypoints_to_landmarks(kps)
    old_metric = float(np.nan_to_num(np.nanmean(frame[:, 3].astype(float)), nan=0.0))
    new_metric = float(np.nanmean(frame[CORE, 3].astype(float)))
    assert old_metric < 0.5   # old: frame would count as "absent"
    assert new_metric >= 0.5  # new: frame correctly counts as "present"


# --- NaN handling -----------------------------------------------------------

def test_nan_core_landmarks_flag_no_subject(config):
    """Undetected frames come through as NaN. nanmean over an all-NaN row is NaN,
    which nan_to_num turns into 0 -> absent. Must flag, not crash or pass."""
    lm = _frames(10, core_vis=0.0, core_nan=True)
    with np.errstate(invalid="ignore"):  # nanmean warns on all-NaN slices
        warn = _assess_quality(lm, {}, config, rep_count=3)
    assert warn is not None and warn["kind"] == "no_subject"


def test_mixed_nan_and_visible_frames(config):
    # 6 clearly-visible frames, 4 fully-undetected (NaN) -> 0.60 present -> passes.
    good = _frames(6, core_vis=0.9)
    bad = _frames(4, core_vis=0.0, core_nan=True)
    lm = np.concatenate([good, bad], axis=0)
    with np.errstate(invalid="ignore"):
        assert _assess_quality(lm, {}, config, rep_count=3) is None


def test_empty_landmarks_flags_no_subject(config):
    lm = np.zeros((0, NUM_LANDMARKS, 4), dtype=np.float32)
    warn = _assess_quality(lm, {}, config, rep_count=3)
    assert warn is not None and warn["kind"] == "no_subject"


# --- indexing correctness (the static-analysis assumption) ------------------

def test_core_indexing_selects_expected_columns(config):
    """Pin the exact NumPy indexing the fix relies on: list() fancy-indexing must
    select the 13 core columns from axis 1 — not be misread as a multi-axis index.
    A frame visible ONLY on core slots must pass; noise on non-core slots is
    irrelevant to the verdict."""
    lm = np.zeros((10, NUM_LANDMARKS, 4), dtype=np.float32)
    lm[:, CORE, 3] = 0.9                 # core visible
    # Non-core slots stay at 0; if indexing were wrong and averaged all 33,
    # this could dip results. Confirm the selected sub-array is exactly (F, 13).
    selected = lm[:, list(CORE_PRESENCE_LANDMARKS), 3]
    assert selected.shape == (10, len(CORE))
    assert _assess_quality(lm, {}, config, rep_count=3) is None


# --- no_reps precedence -----------------------------------------------------

def test_visible_but_zero_reps_flags_no_reps(config):
    lm = _frames(10, core_vis=0.9)
    warn = _assess_quality(lm, {}, config, rep_count=0)
    assert warn is not None and warn["kind"] == "no_reps"


def test_no_subject_takes_precedence_over_no_reps(config):
    # Invisible AND zero reps -> no_subject wins (checked first).
    lm = _frames(10, core_vis=0.0)
    warn = _assess_quality(lm, {}, config, rep_count=0)
    assert warn is not None and warn["kind"] == "no_subject"
