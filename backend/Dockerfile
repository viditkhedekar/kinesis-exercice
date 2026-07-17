FROM python:3.11-slim-bookworm

# Native runtime libraries for the CV stack.
#   libgl1, libglib2.0-0  -> OpenCV (opencv-python-headless still needs these)
#   libgles2  -> provides libGLESv2.so.2  (MediaPipe's _framework_bindings.so is
#   libegl1   -> provides libEGL.so.1      linked against GL ES / EGL and the
#                                          dynamic loader resolves them at import,
#                                          even when inference runs on the CPU)
# These are the GLVND dispatch libraries: they satisfy the sonames on headless,
# GPU-less hosts without requiring a real GPU or display server.
# ffmpeg/ffprobe drive the fast video-decode path (decode + downscale + fps
# decimation in C, streamed into MediaPipe); the libGL/EGL libs satisfy the CV stack.
RUN apt-get update && apt-get install -y --no-install-recommends --allow-unauthenticated \
    libgl1 libglib2.0-0 libgles2 libegl1 ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
# Include the optional MoveNet backend (LiteRT/TFLite runtime) so KINESIS_POSE_BACKEND
# can be switched to "movenet" without rebuilding.
RUN pip install --no-cache-dir ".[movenet]"

COPY . .

# Download the MediaPipe Pose Landmarker models at build time. All three
# complexities are fetched so KINESIS_POSE_MODEL_COMPLEXITY (0=lite, 1=full,
# 2=heavy) can be switched without a rebuild, and scripts/benchmark_pose.py can
# compare them. The runtime default is "full" (complexity 1).
ARG MP_BASE=https://storage.googleapis.com/mediapipe-models/pose_landmarker
# -f makes curl FAIL (non-zero) on an HTTP error instead of writing the error page
# into the .task file; -L follows redirects. The verification step then fails the
# build loudly if any model is missing or implausibly small, so a broken download
# can never silently degrade runtime into the wrong (heavier) model.
RUN mkdir -p app/services/pose/models && \
    curl -fL -o app/services/pose/models/pose_landmarker_lite.task \
      ${MP_BASE}/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task && \
    curl -fL -o app/services/pose/models/pose_landmarker_full.task \
      ${MP_BASE}/pose_landmarker_full/float16/latest/pose_landmarker_full.task && \
    curl -fL -o app/services/pose/models/pose_landmarker_heavy.task \
      ${MP_BASE}/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task
RUN set -eu; cd app/services/pose/models; ls -l *.task; \
    for f in pose_landmarker_lite.task pose_landmarker_full.task pose_landmarker_heavy.task; do \
      test -s "$f" || { echo "FATAL: model missing/empty: $f" >&2; exit 1; }; \
      sz=$(wc -c < "$f"); \
      [ "$sz" -gt 1000000 ] || { echo "FATAL: model $f too small ($sz bytes) — download failed" >&2; exit 1; }; \
    done; echo "pose models verified OK"

# MoveNet SinglePose Lightning (int8 TFLite) for the optional "movenet" backend.
# The former tfhub-lite-models GCS download URLs now return HTTP 403, so the model is
# committed to the repo and copied into the image by `COPY . .` above. We only verify
# it here (present + plausibly sized), failing the build clearly if it's missing.
RUN f=app/services/pose/models/movenet_lightning.tflite; \
    [ -s "$f" ] || { echo "FATAL: movenet model missing at $f (expected committed in repo)" >&2; exit 1; }; \
    sz=$(wc -c < "$f"); \
    [ "$sz" -gt 500000 ] || { echo "FATAL: movenet model too small ($sz bytes)" >&2; exit 1; }; \
    echo "movenet model present OK ($sz bytes)"

ENV PYTHONUNBUFFERED=1

# Analysis runs synchronously inside the API process — no separate worker.
CMD ["sh", "-c", "python -m app.init_db && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
