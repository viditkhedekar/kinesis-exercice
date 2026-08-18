"""Application settings, loaded from environment variables.

Everything that differs between local dev, docker-compose, and production lives
here so the rest of the codebase never reads ``os.environ`` directly.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# MediaPipe pose "complexity" -> Tasks model bundle filename (0=lite, 1=full, 2=heavy).
_POSE_MODEL_FILES = {
    0: "pose_landmarker_lite.task",
    1: "pose_landmarker_full.task",
    2: "pose_landmarker_heavy.task",
}


# Hosts treated as "local" when deciding whether to force TLS on the database
# connection. Anything else (Neon, RDS, ...) gets ``sslmode=require`` added.
_LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1", ""}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KINESIS_", env_file=".env", extra="ignore", populate_by_name=True
    )

    # --- Infrastructure ---
    # Managed Postgres (Neon in production). Accepts any of the shapes Neon hands
    # out — ``postgres://``, ``postgresql://``, or an explicit ``+psycopg2`` driver —
    # and is normalised for SQLAlchemy by ``normalized_database_url()``.
    database_url: str = "postgresql+psycopg2://kinesis:kinesis@localhost:5432/kinesis"
    # Neon's serverless compute auto-suspends when idle, which silently kills pooled
    # connections. ``pool_pre_ping`` catches a dead connection on checkout; recycling
    # well under the idle timeout keeps us from handing one out in the first place.
    db_pool_recycle: int = 300      # seconds; recycle connections older than this
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_connect_timeout: int = 10    # seconds for the initial TCP/TLS handshake

    # --- Storage ---
    # Which Storage implementation serves uploads/artifacts:
    #   "auto"       -> SupabaseStorage when SUPABASE_URL + service-role key are set,
    #                   FileSystemStorage otherwise (the default: local dev and tests
    #                   need no Supabase account, production just sets the env vars)
    #   "supabase"   -> always Supabase (raises at startup if unconfigured)
    #   "filesystem" -> always the local filesystem
    storage_backend: str = "auto"
    # Root directory for the FileSystemStorage backend. On Render this is EPHEMERAL —
    # it is only ever used for local dev, tests, and the temp files that the CV
    # pipeline needs; production durable storage is Supabase.
    storage_dir: Path = Path("/data/kinesis")

    # --- Supabase Storage ---
    # Read from the un-prefixed SUPABASE_* names Supabase itself documents (the
    # KINESIS_-prefixed spellings are accepted too, for consistency with the rest
    # of this file). The service-role key is server-side only and must NEVER be
    # exposed to the frontend — it bypasses row-level security.
    supabase_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_URL", "KINESIS_SUPABASE_URL"),
    )
    supabase_service_role_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SUPABASE_SERVICE_ROLE_KEY", "KINESIS_SUPABASE_SERVICE_ROLE_KEY"
        ),
    )
    supabase_storage_bucket: str = Field(
        default="kinesis-media",
        validation_alias=AliasChoices(
            "SUPABASE_STORAGE_BUCKET", "KINESIS_SUPABASE_STORAGE_BUCKET"
        ),
    )
    # Lifetime of the signed URLs handed to the browser for video playback. Short
    # enough that a leaked link expires quickly, long enough to watch a clip.
    supabase_signed_url_ttl: int = 3600  # seconds
    supabase_timeout: float = 120.0      # HTTP timeout for storage calls (uploads are big)

    # --- Exercise configs ---
    # Directory holding one YAML config per exercise (the extensibility surface).
    exercises_dir: Path = Path(__file__).parent / "exercises"

    # --- Pose model ---
    # Directory holding the MediaPipe PoseLandmarker .task bundles.
    pose_models_dir: Path = Path(__file__).parent / "services" / "pose" / "models"
    # Model "complexity" is selected by which .task file is loaded (the Tasks API
    # has no runtime complexity flag): 0=lite (fastest), 1=full, 2=heavy (most
    # accurate, slowest). Inference is the dominant cost on the CPU-only deployment,
    # so we default to lite — it keeps the joint-angle fidelity that rep detection
    # and form scoring depend on while cutting per-frame inference ~2-3x vs full.
    # Verify/compare with scripts/benchmark_pose.py; set KINESIS_POSE_MODEL_COMPLEXITY
    # to 1 or 2 to revert to a heavier model.
    pose_model_complexity: int = 0
    # Explicit model-file override. When unset, the path is derived from the
    # complexity above (falling back to the legacy ``pose_landmarker.task`` name).
    pose_model_path: Path | None = None

    # --- Pose estimation performance ---
    # Pose runs one CPU inference per processed frame, and the ffmpeg decode/scale of
    # those frames. To keep analysis to ~tens of seconds regardless of clip length or
    # camera settings we (a) temporally downsample to a target fps — DECODE FEWER
    # FRAMES — and (b) downscale each frame close to the model's working size — DECODE
    # CLOSER TO THE MODEL OUTPUT — and cap the total processed frames.
    #
    # DECODE FEWER FRAMES: 4 fps is the floor that still resolves a fast rep's
    # peak/valley (~4 samples/sec). Lower risks miscounting fast reps; raise toward
    # 5-6 if rep detection suffers. Note: the H.264 *decode* of source frames is
    # largely fixed by clip length/resolution — lowering this mainly cuts per-kept-
    # frame scale/pipe/inference work, not the raw decode.
    pose_target_fps: float = 4.0      # sample the source down to ~this fps
    # DECODE CLOSER TO THE MODEL OUTPUT: MediaPipe's landmarker works on a ~256px ROI
    # crop, so decoding at 640 just produces pixels it immediately shrinks. 384 sits
    # ~1.5x above the model size — enough headroom for the ROI crop to stay sharp for
    # a full-body subject — while cutting per-frame scale/pipe/NumPy/resize cost to
    # ~36% of 640's (area 384^2 vs 640^2). Raise toward 512-640 if landmark precision
    # drops for subjects that fill only part of the frame. Never modifies the upload.
    pose_max_dim: int = 384           # downscale so the longest side is <= this
    pose_max_frames: int = 600        # hard cap on processed frames (bounds runtime)
    # Video decoder: "ffmpeg" (default; single C subprocess does decode+scale+fps
    # decimation and streams frames into MediaPipe — far faster than decoding every
    # frame in Python) with automatic fallback to OpenCV when ffmpeg isn't on PATH.
    # Set "cv2" to force the OpenCV decoder.
    pose_decoder: str = "ffmpeg"
    # Fast ffmpeg decode: skip the H.264 in-loop deblocking filter and use a faster
    # downscale during preprocessing. ~10-20% cheaper decode (the dominant cost); the
    # tiny quality loss is irrelevant after downscaling to <=max_dim for pose. Set
    # False for bit-faithful decoding.
    pose_ffmpeg_fast_decode: bool = True
    # Reuse one PoseLandmarker per worker thread across requests instead of building
    # a fresh graph every analysis (saves the ~1-2s init). Set False to force a fresh
    # landmarker per analysis (the previous behaviour).
    pose_reuse_model: bool = True
    # PoseLandmarker running mode: "video" (tracking between frames, default) or
    # "image" (independent full detection per frame, no tracking). Benchmark both
    # with scripts/benchmark_pose.py before changing.
    pose_running_mode: str = "video"
    # Best-effort CPU inference thread hint (0 = library default). The MediaPipe Tasks
    # API has no thread knob, so this only sets math-lib env vars before load and may
    # be ignored by XNNPACK — benchmark to confirm it does anything on your host.
    # (The MoveNet/TFLite backend DOES honour this directly.)
    pose_num_threads: int = 0
    # Pose detection backend:
    #   "mediapipe" -> always MediaPipe (33 landmarks) — the default
    #   "movenet"   -> MoveNet Lightning TFLite (17 keypoints adapted to the 33-slot
    #                  layout — faster, but no feet/hands so a few checks won't fire);
    #                  falls back to MediaPipe at runtime if it can't initialise
    #   "auto"      -> use MoveNet if its model is present, else MediaPipe
    # Default is "mediapipe": the MoveNet experiment is kept opt-in (the code and
    # model remain) but MediaPipe runs as it did before the switch.
    pose_backend: str = "mediapipe"
    # MoveNet SinglePose Lightning .tflite model (used only when pose_backend="movenet").
    movenet_model_path: Path = Path(__file__).parent / "services" / "pose" / "models" / "movenet_lightning.tflite"

    # --- Landmark smoothing (post-estimation de-jitter) ---
    # Lightweight NumPy pass applied to the assembled landmark array AFTER pose
    # estimation. It does NOT change the model, input resolution, or processed fps —
    # it only cleans jitter/lag/drift in the output. Adds ~single-digit ms per clip.
    # Stages: confidence filter -> velocity/jump rejection -> gap interpolation ->
    # One Euro smoothing (adaptive: kills jitter when still, avoids lag when fast).
    pose_smoothing: bool = True
    pose_smooth_min_confidence: float = 0.3   # readings below this visibility are dropped
    pose_smooth_max_jump: float = 0.15        # max normalized move/frame before rejecting
    pose_smooth_max_gap_frames: int = 5       # gaps longer than this stay missing (no interp)
    # One Euro parameters. min_cutoff sets the baseline smoothing (lower = smoother but
    # more lag); beta sets how fast the cutoff opens up with speed (higher = less lag on
    # fast motion). Defaults are conservative starting points — tune on real clips.
    pose_smooth_min_cutoff: float = 1.0
    pose_smooth_beta: float = 0.5
    pose_smooth_d_cutoff: float = 1.0

    # --- Auth ---
    auth_secret: str = "dev-insecure-change-me"   # HMAC signing key for session tokens
    auth_cookie: str = "kinesis_session"
    auth_cookie_secure: bool = False              # set True behind HTTPS in production
    # SameSite policy for the session cookie. When the frontend and backend are
    # served from different sites (e.g. *.vercel.app calling *.onrender.com), the
    # browser only attaches the cookie to cross-site fetch/XHR requests when this
    # is "none" — and "none" additionally REQUIRES Secure=true. Use "lax" only when
    # the two share a site (local dev on localhost). Set KINESIS_AUTH_COOKIE_SAMESITE=none
    # and KINESIS_AUTH_COOKIE_SECURE=true in the cross-site production deployment.
    auth_cookie_samesite: str = "lax"             # "lax" | "none" | "strict"
    session_days: int = 7                         # default session lifetime
    remember_days: int = 30                       # "remember me" lifetime

    # --- Email verification ---
    # New accounts must confirm their email before they can log in. Disable only
    # for local flows/tests where email delivery isn't wanted.
    require_email_verification: bool = True
    email_verification_ttl_hours: int = 24        # link lifetime
    email_resend_cooldown_seconds: int = 60       # min gap between verification emails
    # Public base URL of the frontend, used to build the link in the email
    # (e.g. https://kinesis-exercice.vercel.app -> {frontend_url}/verify?token=...).
    frontend_url: str = "http://localhost:3000"

    # --- Email delivery ---
    # Provider: "resend" (default) | "sendgrid" | "smtp" | "console". When the
    # selected provider has no credentials configured, delivery falls back to
    # "console" (the link is logged) so the flow still works in local dev.
    email_provider: str = "resend"
    email_from: str = "physIQal <onboarding@resend.dev>"
    resend_api_key: str | None = None
    sendgrid_api_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True

    # --- API ---
    cors_origins: list[str] = ["http://localhost:3000"]

    def normalized_database_url(self) -> str:
        """The connection string in the form SQLAlchemy + psycopg2 expect.

        Neon (and most managed providers) hand out ``postgresql://...`` — or the
        legacy ``postgres://`` — with no driver, which SQLAlchemy resolves to the
        default psycopg2 dialect anyway, but being explicit keeps the behaviour
        pinned. We also force TLS for non-local hosts: Neon *requires* it, and
        libpq would otherwise happily negotiate down. SQLite (tests) passes through
        untouched.
        """
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]
        if not url.startswith("postgresql+psycopg2://"):
            return url  # sqlite:// and friends
        if "sslmode=" not in url:
            host = (urlsplit(url).hostname or "").lower()
            # Bare service names (docker-compose's "postgres") and loopback run
            # without TLS; anything with a real domain is remote and must use it.
            if host not in _LOCAL_DB_HOSTS and "." in host:
                url += ("&" if "?" in url else "?") + "sslmode=require"
        return url

    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    def resolve_storage_backend(self) -> str:
        """Resolve ``storage_backend="auto"`` against the Supabase configuration."""
        backend = self.storage_backend.lower().strip()
        if backend == "auto":
            return "supabase" if self.supabase_configured() else "filesystem"
        return backend

    def pose_model_file(self) -> str:
        """Resolve the pose model path: explicit override, else the file for the
        configured complexity, else the legacy generic ``pose_landmarker.task``
        (kept for existing installs / the committed dev model)."""
        if self.pose_model_path is not None:
            return str(self.pose_model_path)
        name = _POSE_MODEL_FILES.get(self.pose_model_complexity, _POSE_MODEL_FILES[1])
        candidate = self.pose_models_dir / name
        if candidate.exists():
            return str(candidate)
        legacy = self.pose_models_dir / "pose_landmarker.task"
        return str(legacy if legacy.exists() else candidate)

    def resolve_backend(self) -> str:
        """Resolve the configured backend to a concrete one. "auto" prefers MoveNet
        when its model file is present (final init/runtime fallback still happens in
        run_pose), otherwise MediaPipe."""
        b = self.pose_backend.lower()
        if b == "auto":
            return "movenet" if Path(self.movenet_model_path).exists() else "mediapipe"
        return b

    def active_pose_model_file(self) -> str:
        """Model path for the *resolved* backend: the MoveNet .tflite when MoveNet is
        selected, otherwise the MediaPipe .task."""
        if self.resolve_backend() == "movenet":
            return str(self.movenet_model_path)
        return self.pose_model_file()


@lru_cache
def get_settings() -> Settings:
    return Settings()
