# Pose model

This directory holds the MediaPipe **Pose Landmarker** task bundles used for
server-side pose estimation.

The Tasks API selects model "complexity" by *which `.task` file it loads* — there
is no runtime complexity flag. Three variants map to complexity 0/1/2:

| complexity | file                          | speed    | accuracy |
|-----------:|-------------------------------|----------|----------|
| 0 (lite)   | `pose_landmarker_lite.task`   | fastest  | good     |
| 1 (full)   | `pose_landmarker_full.task`   | balanced | better   |
| 2 (heavy)  | `pose_landmarker_heavy.task`  | slowest  | best     |

Select one at runtime with `KINESIS_POSE_MODEL_COMPLEXITY=0|1|2` (default `0`,
lite — inference dominates analysis time on the CPU-only deployment, and lite
preserves the joint-angle accuracy rep/form scoring needs), or point
`KINESIS_POSE_MODEL_PATH` at a specific file. The backend Docker image downloads
all three at build time (see `backend/Dockerfile`).

Benchmark them on a representative clip to pick the fastest that stays accurate:

```bash
python -m scripts.benchmark_pose path/to/clip.mp4
```

For local (non-Docker) dev you only need one file. Download the default "full":

```bash
curl -L -o pose_landmarker_full.task \
  https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task
```

The loader also accepts a legacy generic `pose_landmarker.task` here as a
fallback when no complexity-named file is present.

## Alternative backend: MoveNet (opt-in)

`KINESIS_POSE_BACKEND=movenet` swaps in **MoveNet SinglePose Lightning** (TFLite),
loaded from `movenet_lightning.tflite` in this directory (config
`KINESIS_MOVENET_MODEL_PATH`). It's faster per frame, but emits **17 COCO
keypoints** which `pose/movenet.py` adapts onto the 33-slot MediaPipe layout the
biomechanics engine expects (x/y + confidence preserved; z=0; a 2D model).

MoveNet has **no feet, hands, or mouth** keypoints, so those slots stay NaN and a
few checks won't fire — notably squat `heels_lift` (heel/foot) and bicep-curl wrist
angle (uses `index`). Everything using shoulder/elbow/wrist/hip/knee/ankle/ear works.

Compare backends before switching:

```bash
python -m scripts.benchmark_pose clip.mp4 --backends mediapipe,movenet
```

The int8 Lightning model is downloaded at Docker build; for local dev drop your own
`movenet_lightning.tflite` here and `pip install ".[movenet]"`.
