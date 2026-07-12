FROM python:3.11-slim-bookworm

# Native runtime libraries for the CV stack.
#   libgl1, libglib2.0-0  -> OpenCV (opencv-python-headless still needs these)
#   libgles2  -> provides libGLESv2.so.2  (MediaPipe's _framework_bindings.so is
#   libegl1   -> provides libEGL.so.1      linked against GL ES / EGL and the
#                                          dynamic loader resolves them at import,
#                                          even when inference runs on the CPU)
# These are the GLVND dispatch libraries: they satisfy the sonames on headless,
# GPU-less hosts without requiring a real GPU or display server.
RUN apt-get update && apt-get install -y --no-install-recommends --allow-unauthenticated \
    libgl1 libglib2.0-0 libgles2 libegl1 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY . .

# Download the MediaPipe Pose Landmarker model at build time.
RUN mkdir -p app/services/pose/models && \
    curl -L -o app/services/pose/models/pose_landmarker.task \
    https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task

ENV PYTHONUNBUFFERED=1

# Analysis runs synchronously inside the API process — no separate worker.
CMD ["sh", "-c", "python -m app.init_db && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
