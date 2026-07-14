"""Benchmark MediaPipe pose model complexity (lite / full / heavy) on a real clip.

Run this on the deployment (or anywhere MediaPipe + OpenCV are installed) to pick
the fastest model that still tracks landmarks accurately enough for the analysis:

    python -m scripts.benchmark_pose path/to/video.mp4
    python -m scripts.benchmark_pose clip.mp4 --fps 10 --max-dim 640 --complexities 0,1,2

For each complexity it reports the per-stage timing (video load, model init, frame
extraction, pose inference, total) and, as an accuracy proxy, the mean landmark
deviation vs the "heavy" model (the most accurate), computed over frames where
heavy sees a confident pose. Pick the lowest complexity whose deviation stays
small (roughly < 0.01–0.02 of frame size), then set:

    KINESIS_POSE_MODEL_COMPLEXITY=<n>

Missing model files are downloaded next to this package's models dir.
"""
from __future__ import annotations

import argparse
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video", help="Path to a representative exercise clip")
    s = get_settings()
    ap.add_argument("--fps", type=float, default=s.pose_target_fps)
    ap.add_argument("--max-dim", type=int, default=s.pose_max_dim)
    ap.add_argument("--max-frames", type=int, default=s.pose_max_frames)
    ap.add_argument("--complexities", default="0,1,2",
                    help="Comma list of complexities to test (default 0,1,2)")
    args = ap.parse_args()

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
