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
Next.js / Vercel
       │  HTTP
       ▼
FastAPI / Render ──── analysis pipeline (in-process, synchronous):
   │        │         pose → biomechanics → reps → rules → coaching → progress
   ▼        ▼
 Neon     Supabase Storage
Postgres  videos + artifacts
```

Postgres holds **structured data only** — users, sessions, reps, faults, scores,
and *storage keys*. Video bytes and analysis artifacts live in a private Supabase
Storage bucket; the database never stores a file, an absolute path, or an expiring
signed URL.

Modular backend services (`backend/app/services/`): **storage**, **pose**
(MediaPipe Pose Landmarker), **biomechanics**, **reps**, **rules**, **coaching**
(provider-agnostic; `echo` template or `claude`), **progress** (+ Ghost Replay).

### Storage

```
Storage (protocol)
├── FileSystemStorage   local dev + tests
└── SupabaseStorage     production
```

Application code deals only in **storage keys** and never learns which backend is
behind them:

```
sessions/<session_id>/source_<filename>
sessions/<session_id>/artifacts/<artifact_name>
```

`KINESIS_STORAGE_BACKEND=auto` (the default) picks Supabase when `SUPABASE_URL`
and `SUPABASE_SERVICE_ROLE_KEY` are set, and the filesystem otherwise — so local
dev and the test suite need no Supabase account.

The CV pipeline needs a real filesystem path for ffmpeg/OpenCV, so an analysis
runs **Supabase → temp file → processing → artifacts → Supabase → temp file
deleted**. The temp file is removed in a `finally`, so a failed analysis cleans up
exactly like a successful one. Render's disk is only ever used for those temps.

Playback is authorized server-side: `GET /sessions/{id}/video` checks that the
caller owns the session, then redirects to a short-lived signed URL (also
available as JSON from `/sessions/{id}/video/url`). Bytes go straight from
Supabase to the browser — with native HTTP Range support, so seeking works — and
the service-role key never leaves the backend.

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

## Production deployment

The backend runs on **Render**, the database on **Neon**, and files in **Supabase
Storage**. Render's filesystem is ephemeral — wiped on every deploy and restart —
so nothing durable may be written to it.

### Environment variables (Render → Environment)

| Variable | Value |
| --- | --- |
| `KINESIS_DATABASE_URL` | Neon pooled connection string |
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service-role key (**server-side only**) |
| `SUPABASE_STORAGE_BUCKET` | `kinesis-media` |
| `KINESIS_STORAGE_BACKEND` | `auto` (or `supabase` to fail fast if unconfigured) |

`postgres://`, `postgresql://` and `postgresql+psycopg2://` are all accepted;
the URL is normalised for psycopg2 and `sslmode=require` is added for remote
hosts. The engine is configured for Neon's auto-suspending compute
(`pool_pre_ping`, a 5-minute `pool_recycle`, and TCP keepalives).

### Supabase bucket

Create one **private** bucket named `kinesis-media`. Leave it private: every read
goes through the backend, which signs a short-lived URL only after checking that
the caller owns the session. No storage RLS policies are needed — the backend
uses the service-role key.

### Migrating existing local files

```bash
cd backend
python -m scripts.migrate_storage_to_supabase --dry-run   # report only
python -m scripts.migrate_storage_to_supabase             # upload + verify + fix DB refs
```

It walks `KINESIS_STORAGE_DIR`, uploads each file under the same logical key,
verifies the stored size, and rewrites absolute paths in `videos.path` /
`analysis_artifacts.landmarks_path` to keys. Safe to re-run: matching objects are
skipped. Originals are never deleted unless you pass `--delete-local`.

## Tech

FastAPI · SQLAlchemy 2 · Alembic · Neon Postgres · Supabase Storage · MediaPipe ·
OpenCV · NumPy · SciPy · Pydantic v2 · Next.js 14 · TypeScript · TanStack Query ·
Tailwind · Recharts.
