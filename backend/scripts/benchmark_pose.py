"""Benchmark MediaPipe pose: model complexity, CPU inference threads, and running mode.

Run on the deployment (or anywhere MediaPipe + OpenCV are installed).

Model-complexity sweep (default) — pick the fastest model that stays accurate:

    python -m scripts.benchmark_pose path/to/video.mp4
    python -m scripts.benchmark_pose clip.mp4 --fps 5 --max-dim 640 --complexities 0,1

Runtime sweep — compare CPU thread counts and VIDEO vs IMAGE running mode:

    python -m scripts.benchmark_pose clip.mp4 --runtime --sweep-threads 1,4,8 --modes video,image

The runtime sweep re-spawns a fresh subprocess per thread count (TFLite reads its
thread env once at load), each comparing the running modes at a fixed complexity.
It reports total pose-estimation time, avg inference ms/frame, and — for IMAGE mode
— the mean landmark deviation vs VIDEO (the accuracy baseline). Then set e.g.:

    KINESIS_POSE_NUM_THREADS=<n>   KINESIS_POSE_RUNNING_MODE=video|image
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

# Allow running as `python scripts/benchmark_pose.py` from the backend dir.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import _POSE_MODEL_FILES, get_settings  # noqa: E402
from app.services.pose import run_pose  # noqa: E402

_MP_BASE = "https://storage.googleapis.com/mediapipe-models/pose_landmarker"
_COMPLEXITY_NAMES = {0: "lite", 1: "full", 2: "heavy"}


def _ensure_model(complexity: int, models_dir: Path) -> Path:
    """Return the model path for a complexity, downloading it if absent."""
    name = _POSE_MODEL_FILES[complexity]
    path = models_dir / name
    if path.exists():
        return path
    variant = _COMPLEXITY_NAMES[complexity]
    url = f"{_MP_BASE}/pose_landmarker_{variant}/float16/latest/{name}"
    models_dir.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {variant} model → {path} ...", flush=True)
    urllib.request.urlretrieve(url, path)
    return path


def _mean_landmark_deviation(a: np.ndarray, ref: np.ndarray) -> float:
    """Mean Euclidean (x,y) distance between two landmark stacks over landmarks the
    reference sees confidently. Both are (F, 33, 4); returns normalized-coord units."""
    if a.shape != ref.shape or a.size == 0:
        return float("nan")
    vis = ref[:, :, 3] >= 0.5
    if not vis.any():
        return float("nan")
    d = np.linalg.norm(a[:, :, :2] - ref[:, :, :2], axis=2)  # (F, 33)
    return float(np.nanmean(d[vis]))


def _set_thread_env(n: int) -> None:
    """Force CPU math-lib thread env vars (must precede MediaPipe/TFLite load)."""
    if n and n > 0:
        for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                  "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "TFLITE_NUM_THREADS"):
            os.environ[v] = str(n)


def _run_pose_once(video, model_path, mode, args) -> dict:
    timings: dict = {}
    t0 = time.perf_counter()
    pose = run_pose(
        video, str(model_path), target_fps=args.fps, max_dim=args.max_dim,
        max_frames=args.max_frames, running_mode=mode, num_threads=args.threads or 0,
        reuse_model=False, timings=timings,
    )
    total = time.perf_counter() - t0
    frames = len(pose.landmarks)
    infer = timings.get("pose_estimation", 0.0)
    return {
        "total": total, "infer": infer, "frames": frames,
        "per_frame_ms": (infer / frames * 1000.0) if frames else 0.0,
        "landmarks": pose.landmarks,
    }


def _runtime_sweep(args) -> None:
    """Compare CPU thread counts and VIDEO vs IMAGE running mode. Threads are swept by
    re-spawning a subprocess per count (TFLite reads its thread env once at load)."""
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    if args.sweep_threads:
        for n in (int(x) for x in args.sweep_threads.split(",") if x.strip()):
            print(f"\n===== threads={n} =====", flush=True)
            subprocess.run(
                [sys.executable, os.path.abspath(__file__), args.video, "--runtime",
                 "--threads", str(n), "--modes", args.modes, "--complexity", str(args.complexity),
                 "--fps", str(args.fps), "--max-dim", str(args.max_dim),
                 "--max-frames", str(args.max_frames)],
                check=False,
            )
        return

    _set_thread_env(args.threads)  # before the first run_pose (MediaPipe not yet imported)
    model_path = _ensure_model(args.complexity, get_settings().pose_models_dir)
    print(f"\n{'mode':<8}{'threads':>8}{'total':>9}{'pose_est':>10}{'/frame':>10}{'dev_vs_video':>14}")
    print("-" * 59)
    baseline = None
    for mode in modes:
        r = _run_pose_once(args.video, model_path, mode, args)
        if mode == "video":
            baseline = r["landmarks"]
        dev = (_mean_landmark_deviation(r["landmarks"], baseline)
               if baseline is not None and mode != "video" else float("nan"))
        print(f"{mode:<8}{(args.threads or 'default'):>8}{r['total']:>7.1f}s"
              f"{r['infer']:>8.1f}s{r['per_frame_ms']:>8.0f}ms{dev:>14.5f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video", help="Path to a representative exercise clip")
    s = get_settings()
    ap.add_argument("--fps", type=float, default=s.pose_target_fps)
    ap.add_argument("--max-dim", type=int, default=s.pose_max_dim)
    ap.add_argument("--max-frames", type=int, default=s.pose_max_frames)
    ap.add_argument("--complexities", default="0,1,2",
                    help="Comma list of complexities to test (default 0,1,2)")
    # Runtime sweep (threads x running-mode) instead of the complexity sweep.
    ap.add_argument("--runtime", action="store_true",
                    help="Benchmark CPU threads and VIDEO vs IMAGE mode instead of model complexity")
    ap.add_argument("--sweep-threads", default=None,
                    help="Comma list of thread counts to sweep, e.g. 1,4,8 (implies --runtime)")
    ap.add_argument("--threads", type=int, default=0, help="CPU inference threads for a single runtime run")
    ap.add_argument("--modes", default="video,image", help="Running modes to compare (default video,image)")
    ap.add_argument("--complexity", type=int, default=0, help="Model complexity for the runtime sweep")
    args = ap.parse_args()

    if args.runtime or args.sweep_threads:
        _runtime_sweep(args)
        return

    complexities = [int(x) for x in args.complexities.split(",") if x.strip() != ""]
    models_dir = s.pose_models_dir

    print(f"Benchmarking {args.video}  (fps={args.fps}, max_dim={args.max_dim})\n")
    results: dict[int, dict] = {}
    landmarks_by_c: dict[int, np.ndarray] = {}

    for c in complexities:
        model_path = _ensure_model(c, models_dir)
        timings: dict[str, float] = {}
        t0 = time.perf_counter()
        pose = run_pose(
            args.video, str(model_path),
            target_fps=args.fps, max_dim=args.max_dim, max_frames=args.max_frames,
            timings=timings,
        )
        total = time.perf_counter() - t0
        frames = len(pose.landmarks)
        infer = timings.get("pose_estimation", 0.0)
        results[c] = {
            "total": total,
            "video_loaded": timings.get("video_loaded", 0.0),
            "model_init": timings.get("pose_model_init", 0.0),
            "frame_extraction": timings.get("frame_extraction", 0.0),
            "pose_estimation": infer,
            "frames": frames,
            "per_frame_ms": (infer / frames * 1000.0) if frames else 0.0,
            "source_fps": pose.source_fps,
            "processed_fps": pose.fps,
        }
        landmarks_by_c[c] = pose.landmarks

    ref = landmarks_by_c.get(max(complexities))  # heavy if present, else the most complex tested

    header = f"{'complexity':<12}{'total':>9}{'extract':>10}{'inference':>11}{'/frame':>10}{'dev vs '+_COMPLEXITY_NAMES[max(complexities)]:>16}"
    print("\n" + header)
    print("-" * len(header))
    for c in complexities:
        r = results[c]
        dev = _mean_landmark_deviation(landmarks_by_c[c], ref) if ref is not None else float("nan")
        name = f"{c} ({_COMPLEXITY_NAMES[c]})"
        print(
            f"{name:<12}{r['total']:>7.1f}s{r['frame_extraction']:>8.1f}s"
            f"{r['pose_estimation']:>9.1f}s{r['per_frame_ms']:>8.1f}ms{dev:>16.5f}"
        )

    first = results[complexities[0]]
    print(
        f"\nProcessed {first['frames']} frames "
        f"(source {first['source_fps']:.1f}fps → {first['processed_fps']:.1f}fps).\n"
        "Pick the lowest complexity whose 'dev' stays small, then set "
        "KINESIS_POSE_MODEL_COMPLEXITY to it."
    )


if __name__ == "__main__":
    main()
