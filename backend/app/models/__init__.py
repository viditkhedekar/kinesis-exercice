"""SQLAlchemy ORM models for Kinesis.

Single implicit user (no auth in this build). The graph:

    Exercise 1──* Session 1──1 Video
                       │
                       ├──1 AnalysisJob          (async pipeline status)
                       ├──1 AnalysisArtifact      (landmark/metrics file refs)
                       ├──* Rep 1──* Fault        (per-rep scores + detected faults)
                       ├──* CoachingNote
                       └──1 ProgressSnapshot       (feeds charts + personal-best)
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    complete = "complete"
    failed = "failed"


class JobStage(str, enum.Enum):
    queued = "queued"
    pose = "pose"
    biomechanics = "biomechanics"
    reps = "reps"
    rules = "rules"
    coaching = "coaching"
    progress = "progress"
    done = "done"
    failed = "failed"


class FaultSeverity(str, enum.Enum):
    minor = "minor"
    moderate = "moderate"
    severe = "severe"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    password_hash: Mapped[str] = mapped_column(String(256))
    # Onboarding + preferences: {onboarded: bool, goals: [...], exercises: [...]}
    prefs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Exercise(Base):
    __tablename__ = "exercises"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. "squat"
    name: Mapped[str] = mapped_column(String(128))
    config_path: Mapped[str] = mapped_column(String(256))

    sessions: Mapped[list[Session]] = relationship(back_populates="exercise")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    exercise_key: Mapped[str] = mapped_column(ForeignKey("exercises.key"))
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), default=SessionStatus.uploaded
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    # "upload" = analyzed from an uploaded video; "live" = Live Camera Mode
    # (browser MediaPipe; may contain multiple sets separated by rest timers).
    mode: Mapped[str] = mapped_column(String(16), default="upload")
    # Overall technique score (0..100) + a JSON summary (key metrics, strengths,
    # grade, view) computed at analysis time and rendered on the report. Live
    # sessions additionally store sets/time_under_tension/duration_s here.
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    exercise: Mapped[Exercise] = relationship(back_populates="sessions")
    video: Mapped[Video | None] = relationship(
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    job: Mapped[AnalysisJob | None] = relationship(
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    artifact: Mapped[AnalysisArtifact | None] = relationship(
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    reps: Mapped[list[Rep]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Rep.index"
    )
    coaching_notes: Mapped[list[CoachingNote]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    progress: Mapped[ProgressSnapshot | None] = relationship(
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), unique=True)
    path: Mapped[str] = mapped_column(String(512))
    filename: Mapped[str] = mapped_column(String(256))
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session: Mapped[Session] = relationship(back_populates="video")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), unique=True)
    stage: Mapped[JobStage] = mapped_column(Enum(JobStage), default=JobStage.queued)
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    session: Mapped[Session] = relationship(back_populates="job")


class AnalysisArtifact(Base):
    __tablename__ = "analysis_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), unique=True)
    landmarks_path: Mapped[str] = mapped_column(String(512))  # .npz of per-frame landmarks
    metrics_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    session: Mapped[Session] = relationship(back_populates="artifact")


class Rep(Base):
    __tablename__ = "reps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    index: Mapped[int] = mapped_column(Integer)  # 1-based rep number
    start_frame: Mapped[int] = mapped_column(Integer)
    bottom_frame: Mapped[int] = mapped_column(Integer)
    end_frame: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float, default=100.0)
    rom: Mapped[float | None] = mapped_column(Float, nullable=True)  # primary-signal ROM
    # 1-based set number for Live Camera Mode (NULL for single-set upload sessions).
    set_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session: Mapped[Session] = relationship(back_populates="reps")
    faults: Mapped[list[Fault]] = relationship(
        back_populates="rep", cascade="all, delete-orphan"
    )


class Fault(Base):
    __tablename__ = "faults"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rep_id: Mapped[int] = mapped_column(ForeignKey("reps.id"))
    type: Mapped[str] = mapped_column(String(64))  # rule id, e.g. "insufficient_depth"
    severity: Mapped[FaultSeverity] = mapped_column(Enum(FaultSeverity))
    message: Mapped[str] = mapped_column(Text)            # concise explanation
    tip: Mapped[str] = mapped_column(Text, default="")    # actionable coaching tip
    start_frame: Mapped[int] = mapped_column(Integer)
    end_frame: Mapped[int] = mapped_column(Integer)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)  # measured value
    unit: Mapped[str] = mapped_column(String(16), default="")          # e.g. "deg", "s", "%"
    confidence: Mapped[float] = mapped_column(Float, default=1.0)      # 0..1 (visibility)
    # Affected MediaPipe landmark indices, highlighted red in the UI during the fault.
    joints: Mapped[list[int]] = mapped_column(JSON, default=list)

    rep: Mapped[Rep] = relationship(back_populates="faults")


class CoachingNote(Base):
    __tablename__ = "coaching_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    provider: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    session: Mapped[Session] = relationship(back_populates="coaching_notes")


class ProgressSnapshot(Base):
    __tablename__ = "progress_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), unique=True)
    exercise_key: Mapped[str] = mapped_column(ForeignKey("exercises.key"))
    rep_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_score: Mapped[float] = mapped_column(Float, default=0.0)
    best_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    session: Mapped[Session] = relationship(back_populates="progress")
