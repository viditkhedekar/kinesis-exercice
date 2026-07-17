"""Application settings, loaded from environment variables.

Everything that differs between local dev, docker-compose, and production lives
here so the rest of the codebase never reads ``os.environ`` directly.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# MediaPipe pose "complexity" -> Tasks model bundle filename (0=lite, 1=full, 2=heavy).
_POSE_MODEL_FILES = {
    0: "pose_landmarker_lite.task",
    1: "pose_landmarker_full.task",
    2: "pose_landmarker_heavy.task",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KINESIS_", env_file=".env", extra="ignore")

    # --- Infrastructure ---
    database_url: str = "postgresql+psycopg2://kinesis:kinesis@localhost:5432/kinesis"

    # --- Storage ---
    # Root directory for uploaded videos and analysis artifacts (FS storage backend).
    storage_dir: Path = Path("/data/kinesis")

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
    # Pose runs one CPU inference per processed frame — the dominant cost. To keep
    # analysis to ~tens of seconds regardless of clip length or camera settings, we
    # temporally downsample to a target fps, downscale each frame, and cap the total
    # number of processed frames. These are plenty of temporal/spatial resolution
    # for rep detection and joint-angle measurement.
    # ~8 fps keeps enough temporal resolution for rep counting and technique while
    # minimising decoded/processed frames.
    pose_target_fps: float = 5.0      # sample the source down to ~this fps
    # Longest side is capped to this before inference. 640 => ~640x360 for 16:9.
    # MediaPipe rescales internally to ~256px, so this is lossless for the analysis
    # while cutting decode/preprocess work. Never modifies the original upload.
    pose_max_dim: int = 640           # downscale so the longest side is <= this
    pose_max_frames: int = 600        # hard cap on processed frames (bounds runtime)
    # Video decoder: "ffmpeg" (default; single C subprocess does decode+scale+fps
    # decimation and streams frames into MediaPipe — far faster than decoding every
    # frame in Python) with automatic fallback to OpenCV when ffmpeg isn't on PATH.
    # Set "cv2" to force the OpenCV decoder.
    pose_decoder: str = "ffmpeg"
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
    pose_num_threads: int = 0

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
