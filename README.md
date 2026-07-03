# Kinesis — Movement Intelligence

Kinesis analyzes gym exercise technique from uploaded video using computer vision
and biomechanics. It estimates body pose frame-by-frame, detects repetitions,
scores every rep against **exercise-specific, config-driven rules**, and explains
the findings with an AI coach. A standout feature — **Ghost Replay** — overlays
your previous best performance as a translucent, phase-aligned skeleton on your
latest video.

The AI never analyzes movement directly: deterministic biomechanics rules produce
every finding, and the AI only *explains* the structured results.

## Architecture

```
Next.js + TypeScript frontend  ──HTTP──►  FastAPI backend ──► Celery worker
                                              │                    │
                                          Postgres             pipeline:
                                          Redis                pose → biomechanics
                                          local/S3 storage     → reps → rules
                                                               → coaching → progress
```

Modular backend services (`backend/app/services/`): **storage**, **pose**
(MediaPipe Pose Landmarker), **biomechanics**, **reps**, **rules**, **coaching**
(provider-agnostic; `echo` template or `claude`), **progress** (+ Ghost Replay).

### Exercises are data, not code

Every exercise is a YAML config in `backend/app/exercises/` describing its metrics,
rep-detection signal, and fault rules. The analysis engine is fully generic —
**adding an exercise is a config file, never an engine change.** Implemented in this
build: **squat**, **bicep_curl**, **pushup**. Starting-point configs for the other
seven exercises live in `backend/app/exercises/_stubs/`.

## Run it

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- API + docs: http://localhost:8000/docs

The backend image downloads the MediaPipe Pose Landmarker model at build time and
creates the database schema on first boot. Upload a clip on **Analyze**, watch the
staged pipeline on the processing page, then explore the interactive report
(skeleton overlay, fault timeline, per-rep scores, AI coaching). Upload a second
clip of the same exercise to unlock **Ghost Replay**.

### Enable the Claude coach (optional)

```bash
ANTHROPIC_API_KEY=sk-ant-... KINESIS_COACH_PROVIDER=claude docker compose up --build
```

The coach then receives the same deterministic report and explains it via
`claude-opus-4-8`; scores and faults are unchanged.

## Develop / test the analysis engine

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest          # biomechanics, rep detection, and rule scoring on synthetic fixtures
```

The tests assert joint angles, rep counts, and specific faults deterministically —
no real video or MediaPipe required.

### Native libraries (MediaPipe)

MediaPipe's native module is linked against OpenGL-ES / EGL and resolves those
libraries at import time **even though pose estimation runs on the CPU**. The
Docker image installs them automatically. If you run the worker directly on a
bare Linux host (no Docker), install them once:

```bash
sudo apt-get install -y libgl1 libglib2.0-0 libgles2 libegl1
```

macOS and Windows wheels bundle their own equivalents — no action needed there.
The pose pipeline pins the **CPU delegate**, so no GPU or display server is
required at runtime.

## Tech

FastAPI · SQLAlchemy 2 · Alembic · Celery · MediaPipe · OpenCV · NumPy · SciPy ·
Pydantic v2 · Next.js 14 · TypeScript · TanStack Query · Tailwind · Recharts.
