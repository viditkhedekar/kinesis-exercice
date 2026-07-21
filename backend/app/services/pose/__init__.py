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
import os
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


# Env vars set (best-effort) to steer CPU inference thread counts. The MediaPipe
# Tasks API does not expose an inference-thread knob, so we can only nudge the
# underlying math libraries via the environment BEFORE MediaPipe/TFLite load.
# XNNPACK (MediaPipe's default float CPU backend) sizes its own pthreadpool and may
# ignore these — the benchmark is what tells us whether they actually move the needle.
_THREAD_ENV_VARS = (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "TFLITE_NUM_THREADS",
)


def configure_inference_threads(num_threads: int) -> None:
    """Best-effort: pin CPU math-library thread counts via env vars. Must run BEFORE
    MediaPipe/TFLite are imported to have any chance of taking effect. ``0`` leaves
    the environment untouched (library defaults)."""
    if not num_threads or num_threads < 1:
        return
    for var in _THREAD_ENV_VARS:
        os.environ.setdefault(var, str(num_threads))
    logger.info("configured inference thread env: %d (%s)", num_threads,
                ", ".join(f"{v}={os.environ.get(v)}" for v in _THREAD_ENV_VARS))


def _read_cpu_stat(path: str) -> dict | None:
    """Parse a cgroup ``cpu.stat`` file into {key: int} (throttling counters)."""
    try:
        with open(path) as fh:
            return {k: int(v) for k, v in (ln.split(None, 1) for ln in fh.read().splitlines() if " " in ln)}
    except (OSError, ValueError):
        return None


def cpu_budget() -> dict:
    """The process's *real* CPU budget — not just ``cpu_count()`` which reports the
    host cores and hides container CPU limits. Reads scheduler affinity, the cgroup
    CFS quota (v2 then v1), and the throttling counters, so the logs reveal a
    fractional-vCPU cap and whether the scheduler is actively throttling us."""
    info: dict = {
        "cpu_count": multiprocessing.cpu_count(),  # host cores (misleading in a container)
        "affinity": None,                          # cores this process may run on
        "cgroup_version": None,
        "cpu_max_raw": None,                       # raw /sys/fs/cgroup/cpu.max
        "cgroup_quota_cpus": None,                 # effective CPU quota, in cores
        "throttling": None,                        # cpu.stat throttling counters
    }
    try:
        info["affinity"] = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        pass

    quota = None
    try:  # cgroup v2
        with open("/sys/fs/cgroup/cpu.max") as fh:
            raw = fh.read().strip()
        info["cgroup_version"] = "v2"
        info["cpu_max_raw"] = raw
        parts = raw.split()
        if len(parts) == 2 and parts[0] != "max":
            quota = int(parts[0]) / int(parts[1])
        info["throttling"] = _read_cpu_stat("/sys/fs/cgroup/cpu.stat")
    except OSError:
        try:  # cgroup v1
            with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us") as fh:
                q = int(fh.read())
            with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us") as fh:
                p = int(fh.read())
            info["cgroup_version"] = "v1"
            info["cpu_max_raw"] = f"{q} {p} (cfs_quota_us cfs_period_us)"
            if q > 0 and p > 0:
                quota = q / p
            info["throttling"] = _read_cpu_stat("/sys/fs/cgroup/cpu/cpu.stat")
        except OSError:
            pass

    info["cgroup_quota_cpus"] = round(quota, 3) if quota is not None else None
    return info


# Snapshot of the CPU budget taken at boot, so post-analysis logging can diff the
# cgroup throttling counters against it. At startup these counters are ~0 (the
# process has barely run), which is exactly why reading them only at boot tells us
# nothing — the interesting question is how much we were throttled *during* the
# CPU-bound decode + inference work.
_startup_cpu_budget: dict | None = None


def log_cpu_budget_delta(label: str = "analysis") -> None:
    """Re-read the CPU budget after CPU-bound work and log the *delta* in throttling
    counters against the startup snapshot.

    This is the measurement that actually answers "are we being throttled?". The
    boot-time counters are near-zero by construction; only the delta over an
    analysis shows what fraction of scheduling periods the kernel capped us in."""
    now = cpu_budget()
    start = _startup_cpu_budget
    t_now = now.get("throttling") or {}
    t_start = (start or {}).get("throttling") or {}

    if not t_now:
        logger.info("cpu budget after %s: no cgroup throttling counters available "
                    "(quota=%s)", label, now.get("cgroup_quota_cpus"))
        return

    def delta(key: str) -> int:
        return int(t_now.get(key, 0)) - int(t_start.get(key, 0))

    periods, throttled = delta("nr_periods"), delta("nr_throttled")
    # v2 reports throttled_usec; v1 reports throttled_time (ns).
    thr_s = (delta("throttled_usec") / 1e6 if "throttled_usec" in t_now
             else delta("throttled_time") / 1e9)
    pct = (100.0 * throttled / periods) if periods else 0.0

    logger.info(
        "cpu budget after %s: quota=%s cpus | during this run: nr_periods=+%d "
        "nr_throttled=+%d (%.0f%% of periods) throttled=+%.2fs "
        "[startup totals: nr_periods=%s nr_throttled=%s]",
        label, now.get("cgroup_quota_cpus"), periods, throttled, pct, thr_s,
        t_start.get("nr_periods", 0), t_start.get("nr_throttled", 0),
    )
    if periods and pct >= 20.0:
        logger.warning(
            "CPU THROTTLED DURING %s: the kernel capped this container in %.0f%% of "
            "scheduling periods (%.2fs stalled waiting for quota). This is the direct "
            "cause of slow frame_decode / inference — not the model choice.",
            label.upper(), pct, thr_s,
        )


def log_cpu_diagnostics(num_threads: int = 0) -> None:
    """Log the container's real CPU budget + a throttling verdict, and the configured
    TFLite inference thread count. Answers 'is this container throttled despite
    reporting N cores?' directly in the deployed logs."""
    global _startup_cpu_budget
    b = cpu_budget()
    _startup_cpu_budget = b  # baseline for log_cpu_budget_delta() after each analysis
    quota, cores = b["cgroup_quota_cpus"], b["cpu_count"]

    logger.info(
        "cpu diagnostics: cpu_count(host)=%s affinity=%s | cgroup=%s cpu.max=%r | "
        "effective_quota_cpus=%s",
        cores, b["affinity"], b["cgroup_version"], b["cpu_max_raw"], quota,
    )
    if b["throttling"]:
        t = b["throttling"]
        # v2 reports throttled_usec; v1 reports throttled_time (ns).
        thr = t.get("throttled_usec")
        thr_s = (thr / 1e6) if thr is not None else (t.get("throttled_time", 0) / 1e9)
        periods, nr_thr = t.get("nr_periods", 0), t.get("nr_throttled", 0)
        pct = (100.0 * nr_thr / periods) if periods else 0.0
        logger.info(
            "cpu throttling: nr_periods=%d nr_throttled=%d (%.0f%% of periods) throttled_total=%.1fs",
            periods, nr_thr, pct, thr_s,
        )

    if quota is not None and quota < cores:
        logger.warning(
            "CPU THROTTLED: this container is limited to ~%.2f CPU(s) by its cgroup quota, "
            "even though cpu_count() reports %s host cores. Pose decode + inference are "
            "CPU-bound, so they run ~%.0fx slower than the reported core count suggests. "
            "The durable fix is a Render plan with more CPU.",
            quota, cores, (cores / quota) if quota else 0,
        )
    elif quota is None:
        logger.info("cpu diagnostics: no cgroup CPU quota found — not CFS-throttled (or cgroup unreadable).")
    else:
        logger.info("cpu diagnostics: cgroup quota (%.2f) >= host cores — not throttled.", quota)

    # TFLite/XNNPACK inference threads. The MediaPipe Tasks API has no thread knob;
    # MoveNet/TFLite honours num_threads directly. 0 = library default (typically 1).
    threads_note = (
        "single-threaded (library default; set KINESIS_POSE_NUM_THREADS to use more, "
        "but only helps if quota permits >1 core)"
        if not num_threads else f"{num_threads} (KINESIS_POSE_NUM_THREADS)"
    )
    logger.info("tflite inference threads: configured=%s", threads_note)


def log_model_inventory(models_dir, resolved_path, complexity) -> None:
    """Log which pose-model bundles exist on disk (name + size), which one the
    configured complexity resolves to, and whether that's a silent fallback to a
    different model. Called at startup so the deployed logs immediately reveal
    whether the intended (lite) model is actually present in the image."""
    p = Path(models_dir)
    files = sorted(p.glob("*.task")) + sorted(p.glob("*.tflite")) if p.exists() else []
    listing = ", ".join(f"{f.name}={f.stat().st_size // 1024}KB" for f in files) or "(none)"
    logger.info("pose model inventory: dir=%s | files=[%s]", p, listing)

    rp = Path(resolved_path)
    if rp.exists():
        logger.info("pose model resolved: complexity=%s -> %s (%dKB)",
                    complexity, rp, rp.stat().st_size // 1024)
    else:
        logger.warning("pose model resolved: complexity=%s -> %s (FILE MISSING)", complexity, rp)

    expected = {0: "lite", 1: "full", 2: "heavy"}.get(complexity)
    if expected and expected not in rp.name.lower():
        logger.warning(
            "SILENT FALLBACK DETECTED: complexity=%s expects the '%s' model but resolved "
            "file is '%s' — MediaPipe is running a DIFFERENT (likely heavier/slower) model. "
            "Ensure pose_landmarker_%s.task is present in the image (rebuild so the "
            "Dockerfile download runs).", complexity, expected, rp.name, expected,
        )


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


def _fit_max_dim(rgb: np.ndarray, max_dim: int) -> tuple[np.ndarray, int, int]:
    """Hard guarantee that the frame's longest side is <= ``max_dim`` right before it
    enters MediaPipe (a safety net independent of the decoder). Preserves aspect,
    works for portrait and landscape. Returns ``(rgb, width, height)`` of the array
    actually handed to MediaPipe."""
    h, w = rgb.shape[:2]
    if max_dim and max(h, w) > max_dim:
        import cv2
        sf = max_dim / max(h, w)
        rgb = cv2.resize(
            rgb, (max(2, round(w * sf)), max(2, round(h * sf))), interpolation=cv2.INTER_AREA
        )
        h, w = rgb.shape[:2]
    return rgb, w, h


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


class _MediaPipeBackend:
    """Adapter wrapping MediaPipe PoseLandmarker behind the common backend contract
    ``infer(rgb, ts_ms) -> (33, 4)`` / ``close()``. Behaviour is identical to the
    previous inline path — this just lets the decode loop be model-agnostic so
    MoveNet (or any future model) can be dropped in via the same interface."""

    name = "mediapipe"

    def __init__(self, landmarker, mp, image_mode: bool) -> None:
        self._lm = landmarker
        self._mp = mp
        self._image_mode = image_mode

    def infer(self, rgb: np.ndarray, ts_ms: int = 0) -> np.ndarray:
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB,
                               data=np.ascontiguousarray(rgb))
        result = self._lm.detect(image) if self._image_mode else self._lm.detect_for_video(image, ts_ms)
        return _extract(result)

    def close(self) -> None:
        self._lm.close()


def _decode_ffmpeg(video_path, backend, *, target_fps, max_dim, max_frames, ts_base=0,
                   fast_decode=True) -> _Decoded:
    """Stream decoded+downscaled+decimated RGB frames from a single ffmpeg process
    straight into the pose ``backend``, one frame at a time (never holding the clip).

    ALL preprocessing (decode, autorotate, fps decimation, downscale to <=max_dim,
    RGB conversion) happens inside ffmpeg in C; Python only ever receives the small,
    already-scaled frames — it never touches the full-resolution source."""
    _t = time.perf_counter

    dw, dh, src_fps = _probe(video_path)
    out_w, out_h = _scaled_dims(dw, dh, max_dim)
    eff = float(target_fps) if target_fps and target_fps > 0 else (src_fps or 30.0)
    scale_flags = "fast_bilinear" if fast_decode else "bilinear"

    # Input (decode) options come BEFORE -i. ``-threads 0`` = auto multi-threaded
    # decode; ``-skip_loop_filter all`` skips H.264 deblocking (the main safe decode
    # speedup — irrelevant to landmarks after downscaling). ``fps`` runs before
    # ``scale`` so scaling only touches the kept frames. We receive ~eff fps frames,
    # so grabbed == kept (no wasted Python-side handling of dropped frames).
    in_opts = ["-threads", "0"]
    if fast_decode:
        in_opts += ["-skip_loop_filter", "all"]
    cmd = [
        "ffmpeg", "-nostdin", "-loglevel", "error", *in_opts, "-i", video_path,
        "-an", "-sn",
        "-vf", f"fps={eff:g},scale={out_w}:{out_h}:flags={scale_flags}",
        "-map", "0:v:0", "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
    ]
    # Surface how much we cut per frame (pixels) and per second (fps) vs the source,
    # so the deploy logs directly show the decode-workload reduction.
    src_px, out_px = dw * dh, out_w * out_h
    px_ratio = (out_px / src_px) if src_px else 1.0
    fps_ratio = (eff / src_fps) if src_fps else 1.0
    logger.info(
        "ffmpeg preprocess: source %dx%d @ %.1ffps -> output %dx%d @ %.1ffps rgb24 "
        "(fast_decode=%s) | per-frame pixels %.0f%% of source, fps %.0f%% of source "
        "(target model input ~256px); cmd: %s",
        dw, dh, src_fps, out_w, out_h, eff, fast_decode,
        px_ratio * 100.0, fps_ratio * 100.0, " ".join(cmd),
    )
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
            rgb, fw, fh = _fit_max_dim(rgb, max_dim)  # safety net; ffmpeg already scaled
            if d.kept == 0:
                d.out_w, d.out_h = fw, fh
                # Confirms Python received a pre-scaled frame from ffmpeg — NOT the
                # full-resolution source. fw/fh should equal the ffmpeg output dims.
                logger.info(
                    "decoded frame resolution (into Python/MoveNet): %dx%d "
                    "(ffmpeg already downscaled from source %dx%d; max_dim=%d)",
                    fw, fh, dw, dh, max_dim,
                )
            ts_ms = ts_base + int(d.kept * 1000.0 / eff)
            d.extract_s += _t() - _e0
            _i0 = _t()
            d.frames.append(backend.infer(rgb, ts_ms))
            d.infer_s += _t() - _i0
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
    # Decode confirmation: resolution Python received, frame count, decode time and
    # throughput. decode_s is the wall time blocked on ffmpeg producing these frames.
    thr = (d.kept / d.decode_s) if d.decode_s > 0 else 0.0
    logger.info(
        "ffmpeg decode done: %d frames @ %dx%d in %.1fs (%.0fms/frame, %.1f frames/s); "
        "Python decoded 0 full-res frames (all decode+scale in ffmpeg)",
        d.kept, d.out_w, d.out_h, d.decode_s,
        (d.decode_s / d.kept * 1000.0) if d.kept else 0.0, thr,
    )
    if d.kept == 0:
        raise RuntimeError("ffmpeg produced no frames")
    return d


def _decode_cv2(video_path, backend, *, target_fps, max_dim, max_frames, ts_base=0) -> _Decoded:
    """OpenCV fallback: decode every source frame (``grab``), run inference on every
    ``step``-th one. Functionally identical output; kept for hosts without ffmpeg."""
    import cv2
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
                frame_rgb, fw, fh = _fit_max_dim(frame_rgb, max_dim)  # safety net
                if d.kept == 0:
                    d.out_w, d.out_h = fw, fh
                    logger.info(
                        "pose input frame resolution: %dx%d (source %dx%d, max_dim=%d, via opencv)",
                        fw, fh, d.width, d.height, max_dim,
                    )
                ts_ms = ts_base + int(d.kept * 1000.0 / eff)
                d.extract_s += _t() - _e0
                _i0 = _t()
                d.frames.append(backend.infer(frame_rgb, ts_ms))
                d.infer_s += _t() - _i0
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
    running_mode: str = "video",
    num_threads: int = 0,
    pose_backend: str = "mediapipe",
    mediapipe_model_path: str | None = None,
    ffmpeg_fast_decode: bool = True,
    smoothing: bool = False,
    smooth_min_confidence: float = 0.3,
    smooth_max_jump: float = 0.15,
    smooth_max_gap_frames: int = 5,
    smooth_min_cutoff: float = 1.0,
    smooth_beta: float = 0.5,
    smooth_d_cutoff: float = 1.0,
    timings: dict[str, float] | None = None,
) -> PoseResult:
    """Estimate pose over a clip, temporally downsampled and spatially downscaled.

    Runtime is driven by frame decoding (dominant) and one CPU inference per kept
    frame. We downsample to ``target_fps`` and cap at ``max_frames``; the returned
    ``fps`` is the *effective* sampled fps so every downstream frame index/timestamp
    (rep windows, joint-angle series, overlay) maps back to real time as ``frame/fps``.
    ``decoder``: "auto"/"ffmpeg" prefer the ffmpeg pipe (fall back to OpenCV), "cv2"
    forces OpenCV. ``running_mode``: "video" (tracking) or "image" (detect per frame).
    ``pose_backend``: "mediapipe" (default) or "movenet". Both emit the same 33-slot
    landmark array via a backend adapter, so the analysis pipeline is untouched.
    ``num_threads``: CPU inference thread hint (honoured directly by MoveNet/TFLite;
    best-effort env-only for MediaPipe). ``smoothing``: run the lightweight
    post-estimation de-jitter pass (confidence filter + jump rejection + gap
    interpolation + One Euro smoothing) on the assembled landmark array; pure
    NumPy, no extra inference cost, timed into ``timings["pose_smoothing"]``.
    """
    global _POSE_WARM
    cold_start = not _POSE_WARM
    requested_backend = pose_backend.lower()
    backend_name = requested_backend

    # Apply the thread hint before MediaPipe/TFLite import (its only chance to matter).
    configure_inference_threads(num_threads)

    _t = time.perf_counter
    image_mode = running_mode.lower() == "image"

    def make_backend():
        # Reads backend_name/model_path at CALL time so the runtime fallback below can
        # switch them and rebuild. Any init failure raises -> caller decides fallback.
        if backend_name == "movenet":
            from app.services.pose.movenet import MoveNetBackend
            return MoveNetBackend(model_path, num_threads=num_threads)
        # MediaPipe. Imported here so cold-start import cost is counted and MoveNet-only
        # deployments don't need MediaPipe.
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"MediaPipe model not found at {model_path}. See "
                "backend/app/services/pose/models/README.md."
            )
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        mp_mode = mp_vision.RunningMode.IMAGE if image_mode else mp_vision.RunningMode.VIDEO
        options = mp_vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(
                model_asset_path=model_path,
                delegate=mp_python.BaseOptions.Delegate.CPU,
            ),
            running_mode=mp_mode,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_segmentation_masks=False,  # never used; disabled to save compute
        )
        return _MediaPipeBackend(mp_vision.PoseLandmarker.create_from_options(options), mp, image_mode)

    # The cached backend is bound to model+mode+backend, so key on all three.
    cache_key = f"{backend_name}|{model_path}|{running_mode.lower()}"
    _init0 = _t()
    try:
        backend, ts_base, reused = _acquire_landmarker(cache_key, make_backend, reuse_model)
    except Exception as exc:  # noqa: BLE001
        # Keep MediaPipe as a runtime fallback: if MoveNet can't initialise (model
        # missing, no LiteRT/TFLite runtime, bad load), switch to MediaPipe so the
        # analysis still runs rather than failing the request.
        if backend_name == "movenet" and mediapipe_model_path:
            logger.warning(
                "MoveNet backend failed to initialise (%s: %s) — falling back to MediaPipe",
                type(exc).__name__, exc,
            )
            backend_name = "mediapipe"
            model_path = mediapipe_model_path
            cache_key = f"{backend_name}|{model_path}|{running_mode.lower()}"
            backend, ts_base, reused = _acquire_landmarker(cache_key, make_backend, reuse_model)
        else:
            raise
    _init_s = _t() - _init0

    # Surface a silent MediaPipe model fallback (only meaningful for that backend).
    _expected = {0: "lite", 1: "full", 2: "heavy"}.get(model_complexity)
    if backend_name == "mediapipe" and _expected and _expected not in Path(model_path).name.lower():
        logger.warning(
            "requested model_complexity=%s (%s) but loaded model file is '%s' — the "
            "'%s' variant is missing, so a DIFFERENT model is running. Rebuild the "
            "image so pose_landmarker_%s.task is present.",
            model_complexity, _expected, Path(model_path).name, _expected, _expected,
        )

    fell_back = backend_name != requested_backend
    logger.info(
        "pose config: backend=%s (requested=%s%s) running_mode=%s (tracking %s) "
        "num_threads=%s cpu_count=%d model=%s",
        backend_name, requested_backend,
        " -> FELL BACK" if fell_back else "",
        "IMAGE" if image_mode else "VIDEO",
        "off" if (image_mode or backend_name == "movenet") else "on",
        num_threads or "default", multiprocessing.cpu_count(), Path(model_path).name,
    )
    if reused:
        logger.info("pose backend: reused cached %s backend (initialised earlier, OK)", backend_name)
    else:
        logger.info(
            "pose backend: %s initialised OK in %.0fms (%s)", backend_name, _init_s * 1000,
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
                    video_path, backend, ts_base=ts_base,
                    target_fps=target_fps, max_dim=max_dim, max_frames=max_frames,
                    fast_decode=ffmpeg_fast_decode,
                )
                used = "ffmpeg"
            except Exception as exc:  # noqa: BLE001 — any ffmpeg failure => safe fallback
                logger.warning(
                    "ffmpeg decode failed (%s); rebuilding backend and falling "
                    "back to the OpenCV decoder", exc,
                )
                # The backend may have been fed partial frames; use a fresh one (ts 0)
                # so VIDEO-mode timestamps stay clean, and re-cache it for reuse.
                backend.close()
                backend = make_backend()
                if reuse_model:
                    _cache_landmarker(cache_key, backend)
                ts_base = 0
                d = _decode_cv2(
                    video_path, backend, ts_base=ts_base,
                    target_fps=target_fps, max_dim=max_dim, max_frames=max_frames,
                )
        else:
            if prefer_ffmpeg:
                logger.info("ffmpeg/ffprobe not on PATH; using OpenCV decoder")
            d = _decode_cv2(
                video_path, backend, ts_base=ts_base,
                target_fps=target_fps, max_dim=max_dim, max_frames=max_frames,
            )
    except Exception:
        # A failed analysis may have left the cached instance mid-stream; drop it so
        # the next request rebuilds cleanly. (When not reusing, just close it.)
        if reuse_model:
            _evict_landmarker(cache_key)
        backend.close()
        raise

    if reuse_model:
        # IMAGE/MoveNet are stateless per frame; only MediaPipe VIDEO needs monotonic ts.
        last_ts = ts_base + int(max(0, d.kept - 1) * 1000.0 / d.effective_fps) if d.effective_fps else ts_base
        _advance_ts(cache_key, last_ts)
    else:
        backend.close()

    if timings is not None:
        timings["pose_model_init"] = _init_s
        timings["frame_decode"] = d.decode_s
        timings["frame_extraction"] = d.extract_s
        timings["pose_estimation"] = d.infer_s

    logger.info(
        "pose decoder=%s backend=%s | source=%.1ffps → processed=%.1ffps; handled %d "
        "source frames, inference on %d; source %dx%d → INTO model %dx%d (max_dim=%d, target_fps=%.1f)",
        used, backend_name, d.src_fps, d.effective_fps, d.grabbed, d.kept,
        d.width, d.height, d.out_w, d.out_h, max_dim, target_fps,
    )
    dec_ms = (d.decode_s / d.grabbed * 1000.0) if d.grabbed else 0.0
    inf_ms = (d.infer_s / d.kept * 1000.0) if d.kept else 0.0
    logger.info(
        "pose timing: backend=%s running_mode=%s num_threads=%s model_input=%dx%d | "
        "frame_decode %.1fs (%d frames @ %.0fms) | frame_extraction %.1fs | "
        "pose_estimation %.1fs (%d frames @ %.0fms/frame avg)  [compare backends here]",
        backend_name, "IMAGE" if image_mode else "VIDEO", num_threads or "default",
        d.out_w, d.out_h,
        d.decode_s, d.grabbed, dec_ms, d.extract_s, d.infer_s, d.kept, inf_ms,
    )

    _POSE_WARM = True
    arr = (
        np.stack(d.frames)
        if d.frames
        else np.full((0, NUM_LANDMARKS, 4), np.nan, dtype=np.float32)
    )

    # Lightweight post-processing to de-jitter the landmark stream. Operates on the
    # already-assembled array (no model/resolution/fps change), so it adds no
    # inference cost — only a few ms of NumPy. Timed explicitly to prove that.
    if smoothing and arr.shape[0] > 1:
        from app.services.pose.smoothing import smooth_landmarks

        _s0 = _t()
        arr, sm_stats = smooth_landmarks(
            arr, d.effective_fps,
            min_confidence=smooth_min_confidence, max_jump=smooth_max_jump,
            max_gap_frames=smooth_max_gap_frames, min_cutoff=smooth_min_cutoff,
            beta=smooth_beta, d_cutoff=smooth_d_cutoff,
        )
        _sm_s = _t() - _s0
        if timings is not None:
            timings["pose_smoothing"] = _sm_s
        logger.info(
            "pose smoothing: %d frames x %d landmarks in %.1fms (%.3fms/frame) | "
            "low_confidence_dropped=%d jumps_rejected=%d points_interpolated=%d "
            "(one-euro min_cutoff=%.2f beta=%.2f | max_jump=%.2f max_gap=%d)",
            sm_stats["frames"], NUM_LANDMARKS, _sm_s * 1000.0,
            (_sm_s * 1000.0 / sm_stats["frames"]) if sm_stats["frames"] else 0.0,
            sm_stats["low_confidence"], sm_stats["jumps_rejected"],
            sm_stats["points_interpolated"], smooth_min_cutoff, smooth_beta,
            smooth_max_jump, smooth_max_gap_frames,
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
