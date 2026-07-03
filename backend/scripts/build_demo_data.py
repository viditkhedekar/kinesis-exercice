"""Precompute the landing-page interactive-demo data from real clips.

Runs the FULL Kinesis pipeline (MediaPipe pose -> biomechanics -> reps -> rules
-> feedback) on a handful of sample videos and writes the result to
``frontend/public/demo/demos.json``. The landing demo renders these landmark
frames as blue nodes on black (no video/person is ever stored) and shows the
real analysis when a visitor clicks "Analyze".

Run from the backend dir in an environment that has the CV stack + model:

    pip install mediapipe opencv-python            # if not already present
    # model auto-downloads in Docker; locally:
    curl -L -o app/services/pose/models/pose_landmarker.task \
      https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task
    python scripts/build_demo_data.py

Edit CLIPS to point at your own recordings (one clear clip per exercise).
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.exercises import load_exercise  # noqa: E402
from app.services.biomechanics import camera_view, compute_metrics  # noqa: E402
from app.services.feedback import grade, group_faults, key_metrics, overall_score, strengths  # noqa: E402
from app.services.pose import run_pose  # noqa: E402
from app.services.pose.landmarks import POSE_EDGES  # noqa: E402
from app.services.reps import detect_reps  # noqa: E402
from app.services.rules import evaluate_session  # noqa: E402

# (source video, exercise config key, display name)
CLIPS = [
    (os.path.expanduser("~/Downloads/IMG_2749.MOV"), "pushup",        "Push-Up"),
    (os.path.expanduser("~/Downloads/IMG_2751.MOV"), "bicep_curl",    "Bicep Curl"),
    (os.path.expanduser("~/Downloads/IMG_2753.MOV"), "lateral_raise", "Lateral Raise"),
    (os.path.expanduser("~/Downloads/IMG_2754.MOV"), "deadlift",      "Deadlift"),
]

TARGET_FPS = 12.0
MAX_DIM = 640
MAX_FRAMES = 240  # ~20s — several reps, small payload
KEEP = sorted({i for e in POSE_EDGES for i in e})  # only drawn landmarks are stored

DEST = Path(__file__).resolve().parents[2] / "frontend" / "public" / "demo" / "demos.json"


def compact_frames(landmarks: np.ndarray) -> list:
    arr = np.nan_to_num(landmarks[:, :, [0, 1, 3]].astype(float), nan=0.0)  # x, y, visibility
    out = []
    for frame in arr:
        row = [[0.0, 0.0, 0.0] for _ in range(33)]
        for i in KEEP:
            x, y, v = frame[i]
            if v >= 0.4:
                row[i] = [round(float(x), 3), round(float(y), 3), round(float(v), 2)]
        out.append(row)
    return out


def series_for(metrics, config, reps, n) -> dict:
    stride = max(1, n // 300)

    def ds(a):
        return [None if np.isnan(v) else round(float(v), 1) for v in a[::stride]]

    angle_keys = [k for k, m in config.metrics.items() if m.type == "angle"]
    ordered = ([config.rep.signal] if config.rep.signal in angle_keys else []) + [
        k for k in angle_keys if k != config.rep.signal
    ]
    series = [
        {"key": k, "label": k.replace("_", " ").title(), "unit": "deg", "values": ds(metrics[k])}
        for k in ordered[:3] if k in metrics
    ]
    rep_bounds = [{"index": r.index, "start": r.start, "bottom": r.bottom, "end": r.end} for r in reps]
    return {"stride": stride, "rep_bounds": rep_bounds, "series": series}


def process(video, key, name) -> dict:
    print(f"\n=== {name} ({key}) — {video} ===", flush=True)
    config = load_exercise(key)
    model = str(get_settings().pose_model_path)
    pose = run_pose(video, model, target_fps=TARGET_FPS, max_dim=MAX_DIM, max_frames=MAX_FRAMES)
    lm = pose.landmarks
    metrics = compute_metrics(lm, config)
    reps = detect_reps(metrics, config, fps=pose.fps)
    scored = evaluate_session(reps, metrics, lm, config, pose.fps)

    pairs = [(sr.rep.index, f) for sr in scored for f in sr.faults]
    groups = group_faults(pairs)
    view = camera_view(lm)
    km = key_metrics(reps, metrics, config, pose.fps, view)
    overall = overall_score(groups, len(reps))

    highlight: list[int] = []
    if groups:
        for _, f in pairs:
            if f.type == groups[0].type and getattr(f, "joints", None):
                highlight = [int(j) for j in f.joints]
                break

    print(f"frames={len(lm)} fps={pose.fps:.2f} reps={len(reps)} score={overall} "
          f"grade={grade(overall)} view={view} priorities={[g.type for g in groups[:3]]}", flush=True)

    return {
        "key": key, "name": name, "reps": len(reps), "view": view,
        "fps": round(float(pose.fps), 3),
        "aspect": round((pose.width / pose.height) if pose.height else 0.5625, 4),
        "edges": POSE_EDGES,
        "frames": compact_frames(lm),
        "highlight": highlight,
        "score": overall, "grade": grade(overall),
        "metrics": km,
        "strengths": strengths(groups, km, config),
        "priorities": [dataclasses.asdict(g) for g in groups[:3]],
        "fault_groups": [dataclasses.asdict(g) for g in groups],
        "rep_breakdown": [
            {"index": sr.rep.index, "start": sr.rep.start, "bottom": sr.rep.bottom,
             "end": sr.rep.end, "score": round(float(sr.score), 1),
             "rom": round(float(sr.rep.rom), 1), "fault_count": len(sr.faults)}
            for sr in scored
        ],
        **series_for(metrics, config, reps, len(lm)),
    }


def main() -> None:
    examples = [process(v, k, n) for v, k, n in CLIPS]
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps({"generatedAt": "static", "examples": examples}, separators=(",", ":")))
    print(f"\nwrote {DEST} ({DEST.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
