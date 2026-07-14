"""Pose estimation: decode video frames and run MediaPipe Pose Landmarker.

Output is a dense per-frame landmark array of shape ``(F, 33, 4)`` where the
last axis is ``(x, y, z, visibility)`` in normalized image coordinates (x, y in
0..1). Frames with no detection are filled with NaN / visibility 0.

MediaPipe and OpenCV are imported lazily so the pure-Python analysis modules
(biomechanics, reps, rules) and their tests don't require the heavy CV stack.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.services.pose.landmarks import NUM_LANDMARKS, POSE_EDGES  # noqa: F401 (re-export)

logger = logging.getLogger("kinesis.pose")


@dataclass
class PoseResult:
    landmarks: np.ndarray  # (F, 33, 4)
    fps: float             # effective (processed) fps
    duration: float
    width: int
    height: int
    source_fps: float = 0.0  # original video fps, before temporal downsampling


# Whether pose has run at least once in this process. The first analysis after a
# server start pays a one-time cost (lazy-importing MediaPipe/OpenCV + loading the
# model), so the UI shows a "preparing the engine" status only while this is False.
_POSE_WARM = False


def is_pose_warm() -> bool:
    return _POSE_WARM


def run_pose(
    video_path: str,
    model_path: str,
    *,
    target_fps: float = 12.0,
    max_dim: int = 640,
    max_frames: int = 600,
    timings: dict[str, float] | None = None,
) -> PoseResult:
    """Estimate pose over a clip, temporally downsampled and spatially downscaled.

    Pose is one CPU inference per processed frame, so runtime is driven by the
    number of processed frames. We therefore sample the source down to
    ``target_fps`` and cap the total at ``max_frames``; the returned ``fps`` is the
    *effective* sampled fps, so every downstream frame index and timestamp (rep
    windows, joint-angle series, the video overlay) maps back to real time as
    ``frame / fps``. Landmark coordinates are normalized (0..1), so downscaling
    frames before inference is lossless for the analysis while cutting per-frame
    pre-processing cost.
    """
    # First analysis in this process pays the cold cost: lazily importing the CV
    # stack (below) + constructing the landmarker graph. On later analyses those
    # modules are reused from ``sys.modules`` (in memory), though the landmarker
    # graph itself is still rebuilt per analysis (a fresh instance keeps the
    # per-request thread safe). We log which case this is so the Render logs show
    # whether a slow analysis paid the cold-start penalty.
    global _POSE_WARM
    cold_start = not _POSE_WARM

    import cv2  # lazy
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision

    if not Path(model_path).exists():
        raise FileNotFoundError(
            f"Pose model not found at {model_path}. Download pose_landmarker.task "
            "(see backend/app/services/pose/models/README.md)."
        )

    _t = time.perf_counter
    _open0 = _t()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    # Apply the container's rotation metadata (phones record portrait clips as
    # landscape + a 90/180° flag). Without this, portrait uploads are analyzed
    # sideways and every vertical-referenced metric (torso lean, hip sag, bar
    # path) is wrong. Frame dimensions are read from the first decoded frame
    # below, after rotation is applied.
    cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1.0)

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if not (src_fps > 0):
        src_fps = 30.0
    width = 0
    height = 0

    # Take every ``step``-th source frame to approximate ``target_fps``.
    step = max(1, round(src_fps / target_fps)) if target_fps > 0 else 1
    effective_fps = src_fps / step
    _video_open_s = _t() - _open0

    # Pin the CPU delegate: this is a headless server with no GPU/display, so we
    # never want MediaPipe to attempt to create an OpenGL/EGL context at runtime.
    # (The native binding still has a load-time dependency on libGLESv2/libEGL —
    # those are provided by the system packages installed in the Dockerfile.)
    options = mp_vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(
            model_asset_path=model_path,
            delegate=mp_python.BaseOptions.Delegate.CPU,
        ),
        running_mode=mp_vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    _init0 = _t()
    landmarker = mp_vision.PoseLandmarker.create_from_options(options)
    _init_s = _t() - _init0

    # Confirm the tracking-enabled path is active. VIDEO running mode carries pose
    # tracking between frames (min_tracking_confidence), so most frames are a cheap
    # track rather than a full re-detection — IMAGE mode would re-detect every frame
    # and be far slower. This line makes it obvious in the Render logs.
    logger.info(
        "pose config: running_mode=VIDEO (tracking on) delegate=CPU num_poses=1 "
        "detect_conf=%.2f track_conf=%.2f model=%s",
        0.5, 0.5, Path(model_path).name,
    )

    if cold_start:
        logger.info(
            "pose model loaded from scratch (COLD start — first analysis in this "
            "process: lazy-imported MediaPipe/OpenCV + built landmarker graph); "
            "graph build %.0fms",
            _init_s * 1000,
        )
    else:
        logger.info(
            "pose model: CV modules reused from memory (process warm); landmarker "
            "graph rebuilt fresh for this analysis in %.0fms",
            _init_s * 1000,
        )

    frames: list[np.ndarray] = []
    decode_s = 0.0    # cumulative grab() — this DECODES each source frame
    extract_s = 0.0   # cumulative retrieve + downscale + colour-convert (kept frames only)
    infer_s = 0.0     # cumulative MediaPipe inference (kept frames only)
    out_w = 0         # analysed (downscaled) frame dims, for logging
    out_h = 0
    try:
        src_idx = 0    # index into the source stream
        grabbed = 0    # source frames decoded (grab): the hidden cost — every frame
        kept = 0       # number of frames actually processed (inference)
        while kept < max_frames:
            # NOTE: for the FFmpeg backend, ``grab`` fully DECODES the frame (it is
            # NOT free); ``retrieve`` only colour-converts/copies the last grabbed
            # frame. So we still pay decode on every source frame even though we only
            # run inference on every ``step``-th one — hence timing this separately.
            _g0 = _t()
            ok_grab = cap.grab()
            decode_s += _t() - _g0
            if not ok_grab:
                break
            grabbed += 1
            if src_idx % step == 0:
                _e0 = _t()
                ok, frame_bgr = cap.retrieve()
                if not ok:
                    break
                # Record true (post-rotation) dimensions from the first real frame.
                if not width:
                    height, width = frame_bgr.shape[:2]
                # Downscale so the longest side is <= max_dim (INTER_AREA for downscale).
                h, w = frame_bgr.shape[:2]
                longest = max(h, w)
                if max_dim and longest > max_dim:
                    scale = max_dim / longest
                    frame_bgr = cv2.resize(
                        frame_bgr, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA
                    )
                if not out_w:
                    out_h, out_w = frame_bgr.shape[:2]
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
                timestamp_ms = int(kept * 1000.0 / effective_fps)
                extract_s += _t() - _e0

                _i0 = _t()
                result = landmarker.detect_for_video(mp_image, timestamp_ms)
                infer_s += _t() - _i0

                frames.append(_extract(result))
                kept += 1
            src_idx += 1
    finally:
        landmarker.close()
        cap.release()

    if timings is not None:
        timings["video_loaded"] = _video_open_s
        timings["pose_model_init"] = _init_s
        timings["frame_decode"] = decode_s
        timings["frame_extraction"] = extract_s
        timings["pose_estimation"] = infer_s

    # Source vs processed sampling + resolution — the levers behind analysis time.
    logger.info(
        "pose sampling: source=%.1ffps → processed=%.1ffps (every %d frame(s), target %.1f); "
        "decoded %d source frames, ran inference on %d; input %dx%d → analysed %dx%d (max_dim=%d)",
        src_fps, effective_fps, step, target_fps,
        grabbed, kept, width, height, out_w, out_h, max_dim,
    )
    # Per-frame costs make the dominant stage obvious at a glance in the Render logs.
    dec_ms = (decode_s / grabbed * 1000.0) if grabbed else 0.0
    inf_ms = (infer_s / kept * 1000.0) if kept else 0.0
    logger.info(
        "pose timing: decode %.1fs (%d frames @ %.0fms, incl. %d skipped) | "
        "extract %.1fs | inference %.1fs (%d frames @ %.0fms)",
        decode_s, grabbed, dec_ms, grabbed - kept,
        extract_s, infer_s, kept, inf_ms,
    )

    # The engine is now warm for the rest of this process's life.
    _POSE_WARM = True

    arr = (
        np.stack(frames)
        if frames
        else np.full((0, NUM_LANDMARKS, 4), np.nan, dtype=np.float32)
    )
    duration = len(frames) / effective_fps if effective_fps else 0.0
    return PoseResult(
        landmarks=arr, fps=effective_fps, duration=duration,
        width=width, height=height, source_fps=src_fps,
    )


def _extract(result) -> np.ndarray:
    out = np.full((NUM_LANDMARKS, 4), np.nan, dtype=np.float32)
    if result.pose_landmarks:
        for i, lm in enumerate(result.pose_landmarks[0]):
            if i >= NUM_LANDMARKS:
                break
            out[i] = (lm.x, lm.y, lm.z, lm.visibility)
    return out


def save_landmarks(path: str, result: PoseResult) -> None:
    np.savez_compressed(
        path,
        landmarks=result.landmarks,
        fps=np.float32(result.fps),
        duration=np.float32(result.duration),
        width=np.int32(result.width),
        height=np.int32(result.height),
    )


def load_landmarks(path: str) -> PoseResult:
    data = np.load(path)
    return PoseResult(
        landmarks=data["landmarks"],
        fps=float(data["fps"]),
        duration=float(data["duration"]),
        width=int(data["width"]),
        height=int(data["height"]),
    )
