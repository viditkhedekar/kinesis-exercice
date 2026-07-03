"""Exercise config schema + loader.

Each exercise is a YAML file describing metrics, rep-detection, and fault rules.
The analysis engine consumes these configs; adding a new exercise is a config
file, never an engine change.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from app.config import get_settings


class MetricConfig(BaseModel):
    """A scalar time-series derived from landmarks.

    type:
      - ``angle``: interior angle at points[1] formed by points[0..2] (degrees)
      - ``segment_vertical_angle``: angle of segment points[0]->points[1] from
        the vertical axis (degrees; 0 = perfectly vertical)
      - ``horizontal_offset``: signed normalized x(points[0]) - x(points[1])
    ``sided`` metrics resolve generic joints to left/right and also emit a mean.
    """
    type: str
    points: list[str]
    sided: bool = False
    axis: str | None = None          # "x"|"y" for the ``coordinate`` metric type
    normalize_by: str | None = None  # metric name to divide by (e.g. hip width)


class RepConfig(BaseModel):
    signal: str                       # metric name driving rep detection
    direction: str = "valley"         # "valley" (min at bottom) or "peak"
    smooth_window: int = 7
    min_prominence: float = 15.0      # degrees
    min_distance_frames: int = 8
    top_threshold: float | None = None
    bottom_threshold: float | None = None


class RuleConfig(BaseModel):
    """A declarative fault rule. ``type`` selects a registered evaluator."""
    id: str
    type: str
    # If omitted, severity is computed from how far the measurement exceeds the
    # threshold (margin bands). Set explicitly to pin a fixed severity.
    severity: str | None = None       # minor | moderate | severe
    weight: float = 20.0              # base points deducted from rep score
    message: str                      # concise explanation shown to the athlete
    tip: str = ""                     # one actionable coaching tip
    # MediaPipe landmark names highlighted in the UI while the fault occurs.
    # Generic joints (e.g. "knee") expand to both sides; explicit names
    # (e.g. "left_elbow") resolve directly. Sided rules may override at runtime.
    joints: list[str] = Field(default_factory=list)
    # rule-type-specific params (validated loosely; evaluators read what they need)
    params: dict = Field(default_factory=dict)


class ExerciseConfig(BaseModel):
    key: str
    name: str
    metrics: dict[str, MetricConfig]
    rep: RepConfig
    rules: list[RuleConfig] = Field(default_factory=list)
    score_base: float = 100.0


def _load_file(path: Path) -> ExerciseConfig:
    data = yaml.safe_load(path.read_text())
    return ExerciseConfig(**data)


@lru_cache
def load_exercise(key: str) -> ExerciseConfig:
    path = Path(get_settings().exercises_dir) / f"{key}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No exercise config for {key!r} at {path}")
    return _load_file(path)


def available_exercises() -> list[ExerciseConfig]:
    """All fully-implemented exercises (top-level YAMLs, excluding _stubs/)."""
    d = Path(get_settings().exercises_dir)
    out: list[ExerciseConfig] = []
    for p in sorted(d.glob("*.yaml")):
        try:
            out.append(_load_file(p))
        except Exception:  # noqa: BLE001 — a malformed stub shouldn't break listing
            continue
    return out
