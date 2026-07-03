# Pose model

This directory holds the MediaPipe **Pose Landmarker** task bundle used for
server-side pose estimation.

Download the model (the "full" variant is a good default) and place it here as
`pose_landmarker.task`:

```bash
curl -L -o pose_landmarker.task \
  https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task
```

The path is configurable via `KINESIS_POSE_MODEL_PATH`. The backend Docker image
downloads this automatically at build time (see `backend/Dockerfile`).
