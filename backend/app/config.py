"""Application settings, loaded from environment variables.

Everything that differs between local dev, docker-compose, and production lives
here so the rest of the codebase never reads ``os.environ`` directly.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KINESIS_", env_file=".env", extra="ignore")

    # --- Infrastructure ---
    database_url: str = "postgresql+psycopg2://kinesis:kinesis@localhost:5432/kinesis"
    redis_url: str = "redis://localhost:6379/0"

    # --- Storage ---
    # Root directory for uploaded videos and analysis artifacts (FS storage backend).
    storage_dir: Path = Path("/data/kinesis")

    # --- Exercise configs ---
    # Directory holding one YAML config per exercise (the extensibility surface).
    exercises_dir: Path = Path(__file__).parent / "exercises"

    # --- Pose model ---
    # Path to the MediaPipe PoseLandmarker .task model file.
    pose_model_path: Path = Path(__file__).parent / "services" / "pose" / "models" / "pose_landmarker.task"

    # --- Pose estimation performance ---
    # Pose runs one CPU inference per processed frame — the dominant cost. To keep
    # analysis to ~tens of seconds regardless of clip length or camera settings, we
    # temporally downsample to a target fps, downscale each frame, and cap the total
    # number of processed frames. These are plenty of temporal/spatial resolution
    # for rep detection and joint-angle measurement.
    pose_target_fps: float = 12.0     # sample the source down to ~this fps
    pose_max_dim: int = 640           # downscale so the longest side is <= this
    pose_max_frames: int = 600        # hard cap on processed frames (bounds runtime)

    # --- AI coaching ---
    # "echo" = deterministic template coach (no LLM). "claude" = Anthropic LLM.
    coach_provider: str = "echo"
    anthropic_api_key: str | None = None
    coach_model: str = "claude-opus-4-8"

    # --- Auth ---
    auth_secret: str = "dev-insecure-change-me"   # HMAC signing key for session tokens
    auth_cookie: str = "kinesis_session"
    auth_cookie_secure: bool = False              # set True behind HTTPS in production
    session_days: int = 7                         # default session lifetime
    remember_days: int = 30                       # "remember me" lifetime

    # --- API ---
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
