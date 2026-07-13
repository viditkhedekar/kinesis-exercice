"""Pydantic schemas: API request/response shapes + the shared AnalysisReport.

The ``AnalysisReport`` is deliberately the *only* thing handed to the AI coach —
it is fully structured, deterministic output. The coach explains it; it never
sees raw video or landmarks.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    name: str
    filming: list[str] = []  # "how to film this" pointers for the upload screen


# --- Auth ---


class RegisterIn(BaseModel):
    email: str
    name: str = ""
    password: str


class RegisterOut(BaseModel):
    """Registration succeeds but does not log the user in — they must verify first."""
    email: str
    verification_required: bool = True
    message: str


class LoginIn(BaseModel):
    email: str
    password: str
    remember: bool = False


class VerifyEmailIn(BaseModel):
    token: str


class ResendVerificationIn(BaseModel):
    email: str


class ResendOut(BaseModel):
    sent: bool
    retry_after: int = 0   # seconds to wait before another resend is allowed
    message: str


class ForgotIn(BaseModel):
    email: str


class ResetIn(BaseModel):
    token: str
    password: str


class PrefsIn(BaseModel):
    name: str | None = None
    prefs: dict | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str
    email_verified: bool = True
    prefs: dict | None = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    exercise_key: str
    status: str
    created_at: datetime
    mode: str = "upload"
    overall_score: float | None = None  # NULL = no trustworthy score ("--" in UI)
    has_video: bool = False   # raw clip still stored (1 history slot)
    has_analysis: bool = False  # analysis/Ghost data retained (¼ slot when video gone)


class QuotaOut(BaseModel):
    """Per-user history storage budget, in 'video slots'."""
    used: float
    limit: float
    video_count: int            # sessions still holding their raw clip (1 slot each)
    analysis_only_count: int    # video-deleted sessions kept for analysis (¼ slot each)


class JobStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    stage: str
    progress: float
    error: str | None = None


class FaultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    type: str
    severity: str
    message: str            # concise explanation
    tip: str = ""           # actionable coaching tip
    start_frame: int
    end_frame: int
    value: float | None = None  # measured value (transparency)
    unit: str = ""
    confidence: float = 1.0     # 0..1 from landmark visibility
    joints: list[int] = []      # affected landmark indices to highlight


class RepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    index: int
    start_frame: int
    bottom_frame: int
    end_frame: int
    score: float
    rom: float | None = None
    faults: list[FaultOut] = []


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    filename: str
    fps: float | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None


class GroupedFaultOut(BaseModel):
    """A fault aggregated across all reps where it occurs."""
    type: str
    message: str
    tip: str
    severity: str
    unit: str
    count: int
    affected_reps: list[int]
    avg_value: float | None = None
    worst_value: float | None = None
    worst_rep: int | None = None
    confidence: float
    side: str | None = None
    start_frame: int


class InsightOut(BaseModel):
    """A single concise, data-grounded observation surfaced as a card."""
    kind: str                    # timing | progress | prevalence | clean | symmetry | consistency
    tone: str                    # positive | attention | neutral
    text: str
    emphasis: str | None = None  # short highlighted figure, e.g. "+9%", "0.18s"


class KeyMetricsOut(BaseModel):
    rom: float = 0.0
    rom_unit: str = "deg"
    symmetry: float | None = None
    symmetry_unit: str = "deg"
    symmetry_label: str = "n/a"
    tempo: float = 0.0
    tempo_unit: str = "s/rep"
    consistency: float = 0.0
    consistency_unit: str = "%CV"
    consistency_label: str = "n/a"
    view: str = "oblique"
    rep_count: int = 0


class AnalysisWarningOut(BaseModel):
    """A data-quality flag surfaced prominently at the top of the report when the
    clip likely can't be trusted — e.g. no visible subject, or a movement that
    doesn't match the selected exercise (wrong exercise / bad upload)."""
    kind: str          # "no_subject" | "no_reps"
    title: str
    message: str


class ReportOut(BaseModel):
    """Full interactive-report payload returned to the frontend."""
    session: SessionOut
    video: VideoOut | None = None
    warning: AnalysisWarningOut | None = None  # data-quality / wrong-exercise flag
    reps: list[RepOut] = []                 # per-rep breakdown (+ faults for overlay)
    overall_score: float | None = 0.0       # NULL = no trustworthy score ("--" in UI)
    grade: str = ""
    key_metrics: KeyMetricsOut | None = None
    strengths: list[str] = []
    insights: list[InsightOut] = []         # 1–2 concise per-session observations
    priorities: list[GroupedFaultOut] = []  # top 3 grouped faults
    fault_groups: list[GroupedFaultOut] = []
    coaching: str | None = None
    coaching_provider: str | None = None
    # Live Camera Mode extras (absent/empty for uploaded-video sessions).
    sets: list[SetSummaryOut] = []
    time_under_tension: float | None = None
    duration_s: float | None = None


# --- Live Camera Mode ---


class LiveCreateIn(BaseModel):
    exercise_key: str


class LiveScoreIn(BaseModel):
    """The current set's landmark buffer, scored on demand (usually once per
    completed rep). ``frames`` is one entry per captured frame: 33 landmarks of
    ``[x, y, z, visibility]`` in normalized image coordinates. Values may be
    ``null`` — the browser serialises NaN (undetected pose) as JSON null."""
    fps: float
    frames: list[list[list[float | None]]]


class LiveCue(BaseModel):
    type: str
    message: str
    tip: str
    severity: str


class LiveScoreOut(BaseModel):
    reps: list[RepOut] = []
    rep_count: int = 0
    running_score: float = 0.0      # mean per-rep score so far (this set)
    latest_cue: LiveCue | None = None


class SetBound(BaseModel):
    start: int
    end: int


class LiveFinishIn(BaseModel):
    """Full workout buffer submitted when the athlete ends the session.

    ``timestamps`` are per-frame capture times in seconds (variable browser fps);
    the server resamples to a uniform grid so the frame-unit rep tuning applies.
    ``sets`` are frame-index ranges into ``frames`` (one per set). Landmark values
    may be ``null`` (the browser serialises NaN from undetected poses as null)."""
    frames: list[list[list[float | None]]]
    timestamps: list[float] = []
    sets: list[SetBound] = []
    width: int = 0        # camera frame dimensions (for correct overlay aspect)
    height: int = 0


class SetSummaryOut(BaseModel):
    set_index: int
    rep_count: int
    avg_score: float
    duration_s: float


class LiveFinishOut(BaseModel):
    session_id: int


# --- Landmark / overlay payloads ---


class LandmarksOut(BaseModel):
    """Per-frame skeleton data for the canvas overlay.

    ``frames`` is a list (one per frame) of 33 [x, y, visibility] triplets in
    normalized image coordinates (0..1). ``edges`` are landmark index pairs.
    """
    fps: float
    width: int
    height: int
    edges: list[list[int]]
    frames: list[list[list[float]]]


class MetricSeries(BaseModel):
    key: str
    label: str
    unit: str
    values: list[float | None]  # per-frame (downsampled); None where undetected


class RepBound(BaseModel):
    index: int
    start: int
    bottom: int
    end: int


class MetricsOut(BaseModel):
    """Per-frame joint-angle series + rep boundaries for the analysis graphs."""
    fps: float
    frames: int
    stride: int  # downsample stride (1 = every frame)
    rep_bounds: list[RepBound]
    series: list[MetricSeries]


class GhostOut(BaseModel):
    """Personal-best rep, phase-normalized for overlay against the current video."""
    available: bool
    source_session_id: int | None = None
    source_score: float | None = None
    edges: list[list[int]] = []
    # phase-normalized frames: one entry per phase sample (0..100%)
    frames: list[list[list[float]]] = []


# --- Coaching (internal, fed to provider) ---


class AnalysisReport(BaseModel):
    """Deterministic structured result. This is the coach's *only* input."""
    exercise_key: str
    exercise_name: str
    rep_count: int
    avg_score: float
    reps: list[RepOut]
    # aggregate fault counts by type, for quick prioritization by the coach
    fault_summary: dict[str, int] = {}


# --- Progress / history / compare ---


class ProgressPoint(BaseModel):
    session_id: int
    created_at: datetime
    avg_score: float
    best_score: float
    rep_count: int


class CompareRequest(BaseModel):
    session_a: int
    session_b: int


class CompareSide(BaseModel):
    session_id: int
    exercise_key: str
    avg_score: float
    rep_count: int
    fault_summary: dict[str, int]


class CompareOut(BaseModel):
    a: CompareSide
    b: CompareSide


# --- Dashboard stats ---


class StatRecent(BaseModel):
    session_id: int
    exercise_key: str
    exercise_name: str
    overall_score: float | None = None  # NULL = no trustworthy score ("--" in UI)
    grade: str
    status: str
    created_at: datetime


class StatPoint(BaseModel):
    created_at: datetime
    score: float


class StatFault(BaseModel):
    type: str
    count: int


class StatBest(BaseModel):
    exercise_key: str
    exercise_name: str
    best_score: float


class StatsOut(BaseModel):
    total_sessions: int = 0
    completed: int = 0
    avg_score: float = 0.0
    week_sessions: int = 0
    week_avg: float = 0.0
    recent: list[StatRecent] = []
    trend: list[StatPoint] = []
    exercise_breakdown: dict[str, int] = {}
    common_faults: list[StatFault] = []
    personal_bests: list[StatBest] = []
