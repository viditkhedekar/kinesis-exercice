"""Pose estimation: decode video frames and run MediaPipe Pose Landmarker.

Output is a dense per-frame landmark array of shape ``(F, 33, 4)`` where the
last axis is ``(x, y, z, visibility)`` in normalized image coordinates (x, y in
0..1). Frames with no detection are filled with NaN / visibility 0.

Frame decoding prefers **FFmpeg**: a single ``ffmpeg`` subprocess decodes,
downscales (longest side <= ``max_dim``) and temporally decimates (to
``target_fps``) the clip in optimised C, then streams the resulting frames over a
pipe one at a time straight into MediaPipe. Compared to the previous OpenCV loop
this (a) does the scale + colour-convert in C on only the frames we keep, and
(b) hands us just the decimated frames — so we no longer pay Python-side
per-frame overhead for the ~2/3 of frames we discard. When ffmpeg/ffprobe are
not on PATH (e.g. local dev) we fall back to the OpenCV decoder, which is
functionally identical (same normalized landmarks).

MediaPipe/OpenCV/ffmpeg are used lazily so the pure-Python analysis modules
(biomechanics, reps, rules) and their tests don't require the heavy CV stack.
"""
from __future__ import annotations

import json
import logging
import multiprocessing
import platform
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.services.pose.landmarks import NUM_LANDMARKS, POSE_EDGES  # noqa: F401 (re-export)

logger = logging.getLogger("kinesis.pose")

# One PoseLandmarker per worker thread, reused across requests (building the graph
# costs ~1-2s). Thread-local avoids sharing a single instance across threads (a
# PoseLandmarker isn't safe for concurrent calls). VIDEO running mode requires
# strictly-increasing timestamps for the life of an instance, so we also carry a
# per-instance monotonic timestamp base across the analyses that reuse it.
_thread_state = threading.local()


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


@dataclass
class _Decoded:
    """Result of walking a clip: the per-frame landmarks plus stage timings and
    frame counts, filled by whichever decoder ran."""
    frames: list[np.ndarray] = field(default_factory=list)
    decode_s: float = 0.0     # time decoding source frames (grab / pipe read)
    extract_s: float = 0.0    # colour-convert / reshape / resize of kept frames
    infer_s: float = 0.0      # MediaPipe inference on kept frames
    grabbed: int = 0          # source frames handled by our process
    kept: int = 0             # frames actually run through inference
    width: int = 0            # source display resolution
    height: int = 0
    out_w: int = 0            # analysed (downscaled) resolution
    out_h: int = 0
    src_fps: float = 0.0
    effective_fps: float = 0.0


def _ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _parse_rate(rate: str | None) -> float:
    if not rate:
        return 0.0
    try:
        if "/" in rate:
            n, d = rate.split("/")
            return float(n) / float(d) if float(d) else 0.0
        return float(rate)
    except (ValueError, ZeroDivisionError):
        return 0.0


def _probe(video_path: str) -> tuple[int, int, float]:
    """Return ``(display_width, display_height, source_fps)`` via ffprobe, applying
    rotation metadata so portrait clips report upright dimensions — matching what
    ffmpeg's autorotation emits, so our computed scale dims line up with the pipe."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams",
         "-of", "json", video_path],
        capture_output=True, text=True, timeout=60,
    )
    streams = (json.loads(out.stdout or "{}").get("streams") or [])
    if not streams:
        raise RuntimeError("ffprobe found no video stream")
    st = streams[0]
    w, h = int(st["width"]), int(st["height"])
    rot = 0
    for sd in st.get("side_data_list", []):
        if "rotation" in sd:
            rot = int(round(float(sd["rotation"])))
            break
    if rot == 0:
        tag = (st.get("tags") or {}).get("rotate")
        if tag is not None:
            rot = int(round(float(tag)))
    if abs(rot) % 180 == 90:  # 90/270 => portrait/landscape swap
        w, h = h, w
    fps = _parse_rate(st.get("avg_frame_rate")) or _parse_rate(st.get("r_frame_rate"))
    return w, h, fps


def _scaled_dims(dw: int, dh: int, max_dim: int) -> tuple[int, int]:
    """Downscale so the longest side is <= ``max_dim`` (preserving aspect), with
    even dimensions (rawvideo / most codecs require even width & height)."""
    longest = max(dw, dh)
    if max_dim and longest > max_dim:
        sf = max_dim / longest
        sw, sh = int(round(dw * sf)), int(round(dh * sf))
    else:
        sw, sh = dw, dh
    sw -= sw % 2
    sh -= sh % 2
    return max(2, sw), max(2, sh)


def _video_meta(video_path: str) -> dict:
    """Read-only clip metadata for diagnostics: display width/height (rotation
    applied), source fps, duration (s) and frame count. Prefers ffprobe; falls back
    to OpenCV capture *properties* (no frame decoding). Best-effort — unknown fields
    come back as 0. Does not touch the analysis path."""
    meta = {"width": 0, "height": 0, "fps": 0.0, "duration": 0.0, "frames": 0, "source": "none"}
    if _ffmpeg_available():
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_streams", "-show_format", "-of", "json", video_path],
                capture_output=True, text=True, timeout=60,
            )
            data = json.loads(out.stdout or "{}")
            st = (data.get("streams") or [{}])[0]
            w, h = int(st.get("width") or 0), int(st.get("height") or 0)
            rot = 0
            for sd in st.get("side_data_list", []):
                if "rotation" in sd:
                    rot = int(round(float(sd["rotation"])))
                    break
            if rot == 0 and (st.get("tags") or {}).get("rotate") is not None:
                rot = int(round(float(st["tags"]["rotate"])))
            if abs(rot) % 180 == 90:
                w, h = h, w
            fps = _parse_rate(st.get("avg_frame_rate")) or _parse_rate(st.get("r_frame_rate"))
            dur = float(st.get("duration") or (data.get("format") or {}).get("duration") or 0.0)
            nb = int(st.get("nb_frames") or 0)
            if not nb and fps and dur:
                nb = round(fps * dur)
            meta.update(width=w, height=h, fps=fps, duration=dur, frames=nb, source="ffprobe")
            return meta
        except Exception:  # noqa: BLE001 — diagnostics must never break analysis
            pass
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1.0)
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            nb = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            meta.update(width=w, height=h, fps=fps, duration=(nb / fps if fps else 0.0),
                        frames=nb, source="cv2")
        cap.release()
    except Exception:  # noqa: BLE001
        pass
    return meta


def _complexity_of(model_path: str, model_complexity: int | None) -> str:
    """The configured MediaPipe complexity, or inferred from the model filename."""
    if model_complexity is not None:
        return str(model_complexity)
    name = Path(model_path).name.lower()
    for c, tag in ((0, "lite"), (1, "full"), (2, "heavy")):
        if tag in name:
            return f"{c} ({tag})"
    return "unknown"


def _log_pose_diagnostics(
    video_path: str, model_path: str, *,
    target_fps: float, max_dim: int, max_frames: int, model_complexity: int | None,
) -> None:
    """Emit a single once-per-analysis diagnostic block BEFORE pose estimation, to
    localise the bottleneck (frame count vs resolution vs config vs CPU)."""
    m = _video_meta(video_path)
    w, h, src_fps, dur, frames = m["width"], m["height"], m["fps"], m["duration"], m["frames"]
    out_w, out_h = _scaled_dims(w, h, max_dim) if (w and h) else (0, 0)
    # Estimated frames MediaPipe will process (actual count is logged after decode).
    if dur > 0:
        est = round(dur * target_fps)
    elif frames and src_fps:
        est = round(frames * target_fps / src_fps)
    else:
        est = 0
    est = min(max_frames, est) if est else 0

    logger.info(
        "pose diagnostics [video]: duration=%.2fs source_fps=%.2f source_frames=%d "
        "resolution=%dx%d (meta via %s)",
        dur, src_fps, frames, w, h, m["source"],
    )
    logger.info(
        "pose diagnostics [plan]: target_fps=%.1f est_frames_to_process=%d (cap=%d) "
        "mediapipe_input=%dx%d model_complexity=%s static_image_mode=False(running_mode=VIDEO,tracking on)",
        target_fps, est, max_frames, out_w, out_h,
        _complexity_of(model_path, model_complexity),
    )
    logger.info(
        "pose diagnostics [host]: cpu_count=%d machine=%s processor=%s",
        multiprocessing.cpu_count(), platform.machine() or "?", platform.processor() or "?",
    )


def _read_exact(stream, n: int) -> bytes:
    """Read exactly ``n`` bytes from a pipe (a single ``read`` can return short)."""
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            break
        buf += chunk
    return bytes(buf)


def _extract(result) -> np.ndarray:
    out = np.full((NUM_LANDMARKS, 4), np.nan, dtype=np.float32)
    if result.pose_landmarks:
        for i, lm in enumerate(result.pose_landmarks[0]):
            if i >= NUM_LANDMARKS:
                break
            out[i] = (lm.x, lm.y, lm.z, lm.visibility)
    return out


def _decode_ffmpeg(video_path, landmarker, *, target_fps, max_dim, max_frames, ts_base=0) -> _Decoded:
    """Stream decoded+downscaled+decimated RGB frames from a single ffmpeg process
    straight into MediaPipe, one frame at a time (never holding the whole clip)."""
    import mediapipe as mp
    _t = time.perf_counter

    dw, dh, src_fps = _probe(video_path)
    out_w, out_h = _scaled_dims(dw, dh, max_dim)
    eff = float(target_fps) if target_fps and target_fps > 0 else (src_fps or 30.0)

    # ffmpeg autorotates by default; ``fps`` decimates and ``scale`` downsizes, both
    # in C, and we only receive the kept frames as raw RGB. This is where "reduced
    # FPS reduces the frames we decode/handle" actually happens: ffmpeg emits ~eff
    # fps, so our loop touches only those frames (grabbed == kept), instead of the
    # OpenCV path that must step through every source frame.
    cmd = [
        "ffmpeg", "-nostdin", "-loglevel", "error", "-i", video_path,
        "-an", "-sn",
        "-vf", f"fps={eff:g},scale={out_w}:{out_h}",
        "-map", "0:v:0", "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
    ]
    d = _Decoded(width=dw, height=dh, out_w=out_w, out_h=out_h,
                 src_fps=src_fps, effective_fps=eff)
    frame_bytes = out_w * out_h * 3
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=frame_bytes,
    )
    try:
        while d.kept < max_frames:
            _g0 = _t()
            buf = _read_exact(proc.stdout, frame_bytes)
            d.decode_s += _t() - _g0
            if len(buf) < frame_bytes:
                break
            d.grabbed += 1
            _e0 = _t()
            rgb = np.frombuffer(buf, dtype=np.uint8).reshape(out_h, out_w, 3)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
            ts_ms = ts_base + int(d.kept * 1000.0 / eff)
            d.extract_s += _t() - _e0
            _i0 = _t()
            result = landmarker.detect_for_video(image, ts_ms)
            d.infer_s += _t() - _i0
            d.frames.append(_extract(result))
            d.kept += 1
    finally:
        try:
            if proc.stdout:
                proc.stdout.close()
        except OSError:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    if d.kept == 0:
        raise RuntimeError("ffmpeg produced no frames")
    return d


def _decode_cv2(video_path, landmarker, *, target_fps, max_dim, max_frames, ts_base=0) -> _Decoded:
    """OpenCV fallback: decode every source frame (``grab``), run inference on every
    ``step``-th one. Functionally identical output; kept for hosts without ffmpeg."""
    import cv2
    import mediapipe as mp
    _t = time.perf_counter

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    # Apply the container's rotation metadata (phones record portrait as landscape
    # + a 90/180° flag) so vertical-referenced metrics aren't analyzed sideways.
    cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1.0)

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if not (src_fps > 0):
        src_fps = 30.0
    step = max(1, round(src_fps / target_fps)) if target_fps > 0 else 1
    eff = src_fps / step
    d = _Decoded(src_fps=src_fps, effective_fps=eff)
    try:
        src_idx = 0
        while d.kept < max_frames:
            # NOTE: for the FFmpeg backend ``grab`` fully DECODES each frame; only
            # ``retrieve`` (below) colour-converts the kept ones. So we pay decode on
            # every source frame — the reason the ffmpeg path above is preferred.
            _g0 = _t()
            ok_grab = cap.grab()
            d.decode_s += _t() - _g0
            if not ok_grab:
                break
            d.grabbed += 1
            if src_idx % step == 0:
                _e0 = _t()
                ok, frame_bgr = cap.retrieve()
                if not ok:
                    break
                if not d.width:
                    d.height, d.width = frame_bgr.shape[:2]
                h, w = frame_bgr.shape[:2]
                longest = max(h, w)
                if max_dim and longest > max_dim:
                    sf = max_dim / longest
                    frame_bgr = cv2.resize(
                        frame_bgr, (round(w * sf), round(h * sf)), interpolation=cv2.INTER_AREA
                    )
                if not d.out_w:
                    d.out_h, d.out_w = frame_bgr.shape[:2]
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
                ts_ms = ts_base + int(d.kept * 1000.0 / eff)
                d.extract_s += _t() - _e0
                _i0 = _t()
                result = landmarker.detect_for_video(image, ts_ms)
                d.infer_s += _t() - _i0
                d.frames.append(_extract(result))
                d.kept += 1
            src_idx += 1
    finally:
        cap.release()
    return d


def _acquire_landmarker(model_path, make_fn, reuse):
    """Return ``(landmarker, ts_base, reused)``. With ``reuse`` we cache one
    landmarker per thread per model and carry a per-instance monotonic timestamp
    base so VIDEO-mode timestamps keep increasing across the analyses that reuse it."""
    if not reuse:
        return make_fn(), 0, False
    cache = getattr(_thread_state, "landmarkers", None)
    if cache is None:
        cache = _thread_state.landmarkers = {}
        _thread_state.ts_base = {}
    lm = cache.get(model_path)
    if lm is not None:
        return lm, _thread_state.ts_base.get(model_path, 0), True
    lm = cache[model_path] = make_fn()
    _thread_state.ts_base[model_path] = 0
    return lm, 0, False


def _cache_landmarker(model_path, lm):
    """Install ``lm`` as this thread's cached instance (after a fallback rebuild)."""
    cache = getattr(_thread_state, "landmarkers", None)
    if cache is None:
        cache = _thread_state.landmarkers = {}
        _thread_state.ts_base = {}
    cache[model_path] = lm
    _thread_state.ts_base[model_path] = 0


def _evict_landmarker(model_path):
    if getattr(_thread_state, "landmarkers", None) is not None:
        _thread_state.landmarkers.pop(model_path, None)
        getattr(_thread_state, "ts_base", {}).pop(model_path, None)


def _advance_ts(model_path, last_ts_ms):
    base = getattr(_thread_state, "ts_base", None)
    if base is not None and model_path in base:
        base[model_path] = last_ts_ms + 1000  # gap keeps the next reuse monotonic


def run_pose(
    video_path: str,
    model_path: str,
    *,
    target_fps: float = 8.0,
    max_dim: int = 640,
    max_frames: int = 600,
    decoder: str = "auto",
    model_complexity: int | None = None,
    reuse_model: bool = True,
    timings: dict[str, float] | None = None,
) -> PoseResult:
    """Estimate pose over a clip, temporally downsampled and spatially downscaled.

    Runtime is driven by frame decoding (dominant) and one CPU inference per kept
    frame. We downsample to ``target_fps`` and cap at ``max_frames``; the returned
    ``fps`` is the *effective* sampled fps so every downstream frame index/timestamp
    (rep windows, joint-angle series, overlay) maps back to real time as ``frame/fps``.
    ``decoder``: "auto"/"ffmpeg" prefer the ffmpeg pipe (fall back to OpenCV), "cv2"
    forces OpenCV.
    """
    global _POSE_WARM
    cold_start = not _POSE_WARM

    import mediapipe as mp  # noqa: F401 (imported so cold-start import cost is counted)
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision

    if not Path(model_path).exists():
        raise FileNotFoundError(
            f"Pose model not found at {model_path}. Download the model bundle "
            "(see backend/app/services/pose/models/README.md)."
        )

    _t = time.perf_counter

    def make_landmarker():
        # Pin the CPU delegate (headless, no GPU/display). VIDEO running mode
        # (== static_image_mode False) carries tracking between frames so most frames
        # are a cheap track, not a full detection. Segmentation masks are explicitly
        # disabled — we never use them and they add real per-frame compute.
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
            output_segmentation_masks=False,
        )
        return mp_vision.PoseLandmarker.create_from_options(options)

    _init0 = _t()
    landmarker, ts_base, reused = _acquire_landmarker(model_path, make_landmarker, reuse_model)
    _init_s = _t() - _init0

    # Surface a silent model fallback: if the requested complexity's variant file is
    # missing, pose_model_file() falls back to another model and MediaPipe silently
    # runs the wrong (usually slower) one. This warning makes that obvious in the logs.
    _expected = {0: "lite", 1: "full", 2: "heavy"}.get(model_complexity)
    if _expected and _expected not in Path(model_path).name.lower():
        logger.warning(
            "requested model_complexity=%s (%s) but loaded model file is '%s' — the "
            "'%s' variant is missing, so a DIFFERENT model is running. Rebuild the "
            "image so pose_landmarker_%s.task is present.",
            model_complexity, _expected, Path(model_path).name, _expected, _expected,
        )

    logger.info(
        "pose config: running_mode=VIDEO (static_image_mode=False, tracking on) "
        "delegate=CPU num_poses=1 detect_conf=0.50 track_conf=0.50 segmentation=off "
        "model=%s complexity=%s",
        Path(model_path).name, _complexity_of(model_path, model_complexity),
    )
    if reused:
        logger.info("pose model: reused cached landmarker (no graph build this analysis)")
    else:
        logger.info(
            "pose model: built landmarker graph in %.0fms (%s)", _init_s * 1000,
            "cold start — first analysis in this process" if cold_start else "new worker thread / first use",
        )

    # Once-per-analysis diagnostics, emitted BEFORE any pose estimation runs, so the
    # logs pin down whether the time is frame count, resolution, config, or CPU limits.
    _log_pose_diagnostics(
        video_path, model_path,
        target_fps=target_fps, max_dim=max_dim, max_frames=max_frames,
        model_complexity=model_complexity,
    )

    prefer_ffmpeg = decoder in ("auto", "ffmpeg")
    used = "opencv"
    try:
        if prefer_ffmpeg and _ffmpeg_available():
            try:
                d = _decode_ffmpeg(
                    video_path, landmarker, ts_base=ts_base,
                    target_fps=target_fps, max_dim=max_dim, max_frames=max_frames,
                )
                used = "ffmpeg"
            except Exception as exc:  # noqa: BLE001 — any ffmpeg failure => safe fallback
                logger.warning(
                    "ffmpeg decode failed (%s); rebuilding landmarker and falling "
                    "back to the OpenCV decoder", exc,
                )
                # The instance may have been fed partial frames; use a fresh one (ts 0)
                # so VIDEO-mode timestamps stay clean, and re-cache it for reuse.
                landmarker.close()
                landmarker = make_landmarker()
                if reuse_model:
                    _cache_landmarker(model_path, landmarker)
                ts_base = 0
                d = _decode_cv2(
                    video_path, landmarker, ts_base=ts_base,
                    target_fps=target_fps, max_dim=max_dim, max_frames=max_frames,
                )
        else:
            if prefer_ffmpeg:
                logger.info("ffmpeg/ffprobe not on PATH; using OpenCV decoder")
            d = _decode_cv2(
                video_path, landmarker, ts_base=ts_base,
                target_fps=target_fps, max_dim=max_dim, max_frames=max_frames,
            )
    except Exception:
        # A failed analysis may have left the cached instance mid-stream; drop it so
        # the next request rebuilds cleanly. (When not reusing, just close it.)
        if reuse_model:
            _evict_landmarker(model_path)
        landmarker.close()
        raise

    if reuse_model:
        last_ts = ts_base + int(max(0, d.kept - 1) * 1000.0 / d.effective_fps) if d.effective_fps else ts_base
        _advance_ts(model_path, last_ts)
    else:
        landmarker.close()

    if timings is not None:
        timings["pose_model_init"] = _init_s
        timings["frame_decode"] = d.decode_s
        timings["frame_extraction"] = d.extract_s
        timings["pose_estimation"] = d.infer_s

    logger.info(
        "pose decoder=%s | source=%.1ffps → processed=%.1ffps; handled %d source "
        "frames, inference on %d; source %dx%d → INTO MediaPipe %dx%d (max_dim=%d, target_fps=%.1f)",
        used, d.src_fps, d.effective_fps, d.grabbed, d.kept,
        d.width, d.height, d.out_w, d.out_h, max_dim, target_fps,
    )
    dec_ms = (d.decode_s / d.grabbed * 1000.0) if d.grabbed else 0.0
    inf_ms = (d.infer_s / d.kept * 1000.0) if d.kept else 0.0
    logger.info(
        "pose timing: mediapipe_input=%dx%d model_complexity=%s | frame_decode %.1fs "
        "(%d frames @ %.0fms) | frame_extraction %.1fs | pose_estimation %.1fs "
        "(%d frames @ %.0fms/frame avg)",
        d.out_w, d.out_h, _complexity_of(model_path, model_complexity),
        d.decode_s, d.grabbed, dec_ms, d.extract_s, d.infer_s, d.kept, inf_ms,
    )

    _POSE_WARM = True
    arr = (
        np.stack(d.frames)
        if d.frames
        else np.full((0, NUM_LANDMARKS, 4), np.nan, dtype=np.float32)
    )
    duration = len(d.frames) / d.effective_fps if d.effective_fps else 0.0
    return PoseResult(
        landmarks=arr, fps=d.effective_fps, duration=duration,
        width=d.width, height=d.height, source_fps=d.src_fps,
    )


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
