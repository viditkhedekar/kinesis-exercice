"""Deterministic biomechanics fault engine + per-rep scoring.

Every fault is produced purely from pose data — joint angles, positions,
movement paths, and timing compared against exercise-specific thresholds. No AI
decides what is wrong; the AI (elsewhere) only *explains* what this engine finds.

Each detection carries: the measured value (+unit) for transparency, the exact
frames where it occurs, the affected landmark indices (highlighted in the UI), a
confidence from landmark visibility, a severity derived from how far the
measurement exceeds the threshold, a concise explanation, and one coaching tip.

Rule types (each a small registered, generic evaluator):
- ``metric_threshold_at_phase``  a metric crosses a threshold at top/bottom/whole
- ``metric_aggregate``           an aggregate (range/max/min/mean/std) of a metric
- ``insufficient_rom``           range of a metric over the rep is too small
- ``asymmetry``                  left/right of a sided metric diverge
- ``rom_asymmetry``              left/right range-of-motion differs
- ``timing_asymmetry``           one side reaches its extreme later than the other
- ``landmark_drift``             a landmark drifts (vs a reference) along an axis
- ``velocity_order``             one landmark moves faster than another in a phase
- ``tempo``                      rep duration outside an allowed band
- ``tempo_consistency``          rep-to-rep tempo varies too much (session-level)

Adding a fault type = registering one function. Adding an exercise = one config.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from app.exercises import ExerciseConfig, RuleConfig
from app.services.pose.landmarks import LANDMARK_INDEX, SIDED, resolve
from app.services.reps import RepWindow

EPS = 1e-9
# Score points removed per fault instance, by severity. Minor faults barely
# matter; severe faults dominate. (Session scoring further weights by prevalence.)
SEV_PENALTY = {"minor": 4.0, "moderate": 10.0, "severe": 20.0}
SESSION_LEVEL = {"tempo_consistency"}


@dataclass
class EvalContext:
    metrics: dict[str, np.ndarray]
    landmarks: np.ndarray  # (F, 33, 4): x, y, z, visibility
    fps: float
    config: ExerciseConfig
    body_scale: float = 0.25     # robust torso length (normalized units)
    view: str = "oblique"        # "front" | "side" | "oblique"


@dataclass
class FaultDetection:
    type: str
    severity: str
    message: str
    tip: str
    start_frame: int
    end_frame: int
    value: float | None
    unit: str
    confidence: float
    joints: list[int] = field(default_factory=list)


@dataclass
class ScoredRep:
    rep: RepWindow
    score: float
    faults: list[FaultDetection]


Evaluator = Callable[[RuleConfig, RepWindow, EvalContext], FaultDetection | None]
_REGISTRY: dict[str, Evaluator] = {}


def rule(type_name: str) -> Callable[[Evaluator], Evaluator]:
    def deco(fn: Evaluator) -> Evaluator:
        _REGISTRY[type_name] = fn
        return fn
    return deco


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

def resolve_joint_names(names: list[str]) -> list[int]:
    """Resolve config joint names to landmark indices (generic joints -> both)."""
    out: list[int] = []
    for name in names:
        if name in SIDED:
            out.extend(SIDED[name])
        elif name in LANDMARK_INDEX:
            out.append(LANDMARK_INDEX[name])
    return out


def _exceedance(value: float, threshold: float, comparator: str) -> float:
    denom = max(abs(threshold), 1e-6)
    if comparator == "lt":
        return max(0.0, (threshold - value) / denom)
    return max(0.0, (value - threshold) / denom)


def classify_severity(
    value: float, threshold: float, comparator: str, params: dict, override: str | None
) -> str:
    """Severity from explicit, biomechanically-meaningful cut points where the
    config provides them (``moderate_at`` / ``severe_at`` in the measurement's
    own units); otherwise a conservative margin fallback. Severe is deliberately
    hard to reach so a normal set rarely contains many severe findings."""
    if override:
        return override
    md = params.get("moderate_at")
    sv = params.get("severe_at")
    if md is not None or sv is not None:
        if comparator == "gt":
            if sv is not None and value >= sv:
                return "severe"
            if md is not None and value >= md:
                return "moderate"
            return "minor"
        # lt: smaller value is worse
        if sv is not None and value <= sv:
            return "severe"
        if md is not None and value <= md:
            return "moderate"
        return "minor"
    # Fallback: relative margin past the trigger threshold (conservative bands).
    e = _exceedance(value, threshold, comparator)
    if e < 0.5:
        return "minor"
    if e < 1.5:
        return "moderate"
    return "severe"


def _plane_factor(plane: str | None, view: str) -> float:
    """How well the detected camera angle observes a fault's plane of motion.

    Faults in a plane the camera can't see well (e.g. knee valgus — a frontal
    issue — filmed from the side) get a confidence discount."""
    if not plane or plane == "any":
        return 1.0
    table = {
        "sagittal": {"side": 1.0, "oblique": 0.85, "front": 0.55},
        "frontal": {"front": 1.0, "oblique": 0.8, "side": 0.45},
    }
    return table.get(plane, {}).get(view, 0.8)


def _confidence(ctx: EvalContext, joints: list[int], s: int, e: int, plane: str | None) -> float:
    """Realistic confidence from measurement quality:

    - **visibility/occlusion**: the 25th-percentile of the *weakest* involved
      joint per frame — intermittent occlusion or low tracking drags it down.
    - **camera angle**: discount if the fault's plane is poorly observed.
    Capped below 1.0 — the system never claims certainty.
    """
    if joints:
        win = ctx.landmarks[s : e + 1][:, joints, 3].astype(float)  # (T, J) visibility
        if win.size:
            per_frame_min = np.nanmin(win, axis=1)
            valid = per_frame_min[~np.isnan(per_frame_min)]
            vis = float(np.percentile(valid, 25)) if valid.size else 0.3
        else:
            vis = 0.3
    else:
        vis = 0.7
    conf = vis * _plane_factor(plane, ctx.view)
    return round(max(0.05, min(0.95, conf)), 2)


def _detect(
    rc: RuleConfig,
    ctx: EvalContext,
    *,
    value: float,
    threshold: float,
    comparator: str,
    unit: str,
    start: int,
    end: int,
    joints: list[int],
) -> FaultDetection:
    plane = rc.params.get("plane")
    return FaultDetection(
        type=rc.id,
        severity=classify_severity(value, threshold, comparator, rc.params, rc.severity),
        message=rc.message,
        tip=rc.tip,
        start_frame=int(start),
        end_frame=int(end),
        value=round(float(value), 2),
        unit=unit,
        confidence=_confidence(ctx, joints, start, end, plane),
        joints=joints,
    )


def _seg(metric: np.ndarray, rep: RepWindow) -> np.ndarray:
    return metric[rep.start : rep.end + 1]


def _phase_frame(phase: str, rep: RepWindow) -> int:
    return {"top": rep.start, "bottom": rep.bottom, "end": rep.end}.get(phase, rep.bottom)


def _axis(name: str) -> int:
    return 0 if name == "x" else 1


def _coord(ctx: EvalContext, idx: int, axis: int) -> np.ndarray:
    return ctx.landmarks[:, idx, axis].astype(float)


def _avg_coord(ctx: EvalContext, name: str, axis: int) -> np.ndarray:
    if name in SIDED:
        a, b = SIDED[name]
        return np.nanmean(np.vstack([_coord(ctx, a, axis), _coord(ctx, b, axis)]), axis=0)
    return _coord(ctx, LANDMARK_INDEX[name], axis)


def _agg(series: np.ndarray, how: str) -> float:
    if series.size == 0 or np.all(np.isnan(series)):
        return float("nan")
    if how == "range":
        return float(np.nanmax(series) - np.nanmin(series))
    return float(getattr(np, f"nan{how}")(series))  # max/min/mean/std


# --------------------------------------------------------------------------- #
# Evaluators
# --------------------------------------------------------------------------- #

@rule("metric_threshold_at_phase")
def _metric_threshold_at_phase(rc, rep, ctx):
    p = rc.params
    metric = ctx.metrics.get(p["metric"])
    if metric is None:
        return None
    phase = p.get("phase", "bottom")
    aggregate = p.get("aggregate", "value_at")
    if aggregate == "value_at":
        frame = _phase_frame(phase, rep)
        value = float(metric[frame])
        fstart = fend = frame
    else:
        value = _agg(_seg(metric, rep), aggregate)
        fstart, fend = rep.start, rep.end
    if math.isnan(value):
        return None
    comparator = p.get("comparator", "gt")
    threshold = p["threshold"]
    triggered = (comparator == "gt" and value > threshold) or (
        comparator == "lt" and value < threshold
    )
    if not triggered:
        return None
    return _detect(
        rc, ctx, value=value, threshold=threshold, comparator=comparator,
        unit=p.get("unit", "deg"), start=fstart, end=fend,
        joints=resolve_joint_names(rc.joints),
    )


@rule("metric_aggregate")
def _metric_aggregate(rc, rep, ctx):
    p = rc.params
    metric = ctx.metrics.get(p["metric"])
    if metric is None:
        return None
    value = _agg(_seg(metric, rep), p.get("aggregate", "range"))
    if math.isnan(value):
        return None
    comparator = p.get("comparator", "gt")
    threshold = p["threshold"]
    triggered = (comparator == "gt" and value > threshold) or (
        comparator == "lt" and value < threshold
    )
    if not triggered:
        return None
    return _detect(
        rc, ctx, value=value, threshold=threshold, comparator=comparator,
        unit=p.get("unit", "deg"), start=rep.start, end=rep.end,
        joints=resolve_joint_names(rc.joints),
    )


@rule("insufficient_rom")
def _insufficient_rom(rc, rep, ctx):
    p = rc.params
    metric = ctx.metrics.get(p["metric"])
    if metric is None:
        return None
    rom = _agg(_seg(metric, rep), "range")
    if math.isnan(rom) or rom >= p["min_rom"]:
        return None
    return _detect(
        rc, ctx, value=rom, threshold=p["min_rom"], comparator="lt",
        unit=p.get("unit", "deg"), start=rep.start, end=rep.end,
        joints=resolve_joint_names(rc.joints),
    )


@rule("asymmetry")
def _asymmetry(rc, rep, ctx):
    p = rc.params
    base = p["metric"]
    left, right = ctx.metrics.get(f"{base}_left"), ctx.metrics.get(f"{base}_right")
    if left is None or right is None:
        return None
    diff = np.abs(_seg(left, rep) - _seg(right, rep))
    value = _agg(diff, p.get("aggregate", "max"))
    if math.isnan(value):
        return None
    unit = p.get("unit", "deg")
    if p.get("normalize_body"):  # convert a coordinate difference to % of body
        value = value / max(ctx.body_scale, 1e-3) * 100.0
        unit = "%body"
    if value <= p["max_diff"]:
        return None
    return _detect(
        rc, ctx, value=value, threshold=p["max_diff"], comparator="gt",
        unit=unit, start=rep.start, end=rep.end,
        joints=resolve_joint_names(rc.joints),
    )


@rule("rom_asymmetry")
def _rom_asymmetry(rc, rep, ctx):
    p = rc.params
    base = p["metric"]
    left, right = ctx.metrics.get(f"{base}_left"), ctx.metrics.get(f"{base}_right")
    if left is None or right is None:
        return None
    rl, rr = _agg(_seg(left, rep), "range"), _agg(_seg(right, rep), "range")
    if math.isnan(rl) or math.isnan(rr):
        return None
    value = abs(rl - rr)
    if value <= p["max_diff"]:
        return None
    return _detect(
        rc, ctx, value=value, threshold=p["max_diff"], comparator="gt",
        unit=p.get("unit", "deg"), start=rep.start, end=rep.end,
        joints=resolve_joint_names(rc.joints),
    )


@rule("timing_asymmetry")
def _timing_asymmetry(rc, rep, ctx):
    p = rc.params
    base = p["metric"]
    left, right = ctx.metrics.get(f"{base}_left"), ctx.metrics.get(f"{base}_right")
    if left is None or right is None:
        return None
    ls, rs = _seg(left, rep), _seg(right, rep)
    if np.isnan(ls).all() or np.isnan(rs).all():
        return None
    pick = np.nanargmin if p.get("direction", "valley") == "valley" else np.nanargmax
    fl, fr = int(pick(ls)), int(pick(rs))
    diff_frames = abs(fl - fr)
    value = diff_frames / ctx.fps if ctx.fps else 0.0
    if value <= p["max_seconds"]:
        return None
    return _detect(
        rc, ctx, value=value, threshold=p["max_seconds"], comparator="gt",
        unit="s", start=rep.start + min(fl, fr), end=rep.start + max(fl, fr),
        joints=resolve_joint_names(rc.joints),
    )


@rule("landmark_drift")
def _landmark_drift(rc, rep, ctx):
    """Displacement of a landmark (optionally relative to a reference) along an
    axis, aggregated over the rep. Covers elbow drift, bar-path drift, shoulder
    shrug, heel lift, upper-arm movement, etc."""
    p = rc.params
    axis = _axis(p.get("axis", "x"))
    sides = ["left", "right"] if p.get("sided", False) else [None]
    best: FaultDetection | None = None
    best_val = -math.inf
    for side in sides:
        try:
            lidx = resolve(p["landmark"], side)
            ridx = resolve(p["reference"], side) if p.get("reference") else None
        except KeyError:
            continue
        s, e = rep.start, rep.end
        series = _coord(ctx, lidx, axis)[s : e + 1].copy()
        if ridx is not None:
            series = series - _coord(ctx, ridx, axis)[s : e + 1]
        if np.isnan(series).all():
            continue
        agg = p.get("aggregate", "range")
        baseline = float(np.nanmean(series[:3])) if len(series) >= 1 else 0.0
        if agg == "range":
            raw = float(np.nanmax(series) - np.nanmin(series))
            fstart = s + int(np.nanargmin(series))
            fend = s + int(np.nanargmax(series))
        elif agg == "net_up":  # axis y: rises => y decreases
            raw = float(baseline - np.nanmin(series))
            fstart, fend = s, s + int(np.nanargmin(series))
        elif agg == "net_down":
            raw = float(np.nanmax(series) - baseline)
            fstart, fend = s, s + int(np.nanargmax(series))
        else:  # maxabs
            dev = np.abs(series - baseline)
            raw = float(np.nanmax(dev))
            fstart, fend = s, s + int(np.nanargmax(dev))
        # Convert pixel displacement to a meaningful "% of body" using the
        # robust per-video torso length, not the unstable per-frame hip width.
        value = raw / max(ctx.body_scale, 1e-3) * 100.0
        if math.isnan(value) or value <= p["threshold"]:
            continue
        if value > best_val:
            best_val = value
            joints = resolve_joint_names([p["landmark"]] if side is None else [])
            if side is not None:
                joints = [resolve(p["landmark"], side)]
                if ridx is not None:
                    joints.append(ridx)
            joints = joints or resolve_joint_names(rc.joints)
            best = _detect(
                rc, ctx, value=value, threshold=p["threshold"], comparator="gt",
                unit=p.get("unit", "%body"), start=min(fstart, fend), end=max(fstart, fend),
                joints=joints,
            )
    return best


@rule("velocity_order")
def _velocity_order(rc, rep, ctx):
    """How many times faster one landmark moves than another during a phase —
    e.g. hips rising ~1.8x faster than the shoulders out of the bottom. Reported
    as a ratio (intuitive and view-robust)."""
    p = rc.params
    axis = _axis(p.get("axis", "y"))
    phase = p.get("phase", "ascent")
    if phase == "ascent":
        s, e = rep.bottom, rep.end
    elif phase == "descent":
        s, e = rep.start, rep.bottom
    else:
        s, e = rep.start, rep.end
    if e - s < 2:
        return None
    a = _avg_coord(ctx, p["landmark_a"], axis)[s : e + 1]
    b = _avg_coord(ctx, p["landmark_b"], axis)[s : e + 1]
    speed_a = float(np.nanmean(np.abs(np.diff(a))))
    speed_b = float(np.nanmean(np.abs(np.diff(b))))
    if math.isnan(speed_a) or math.isnan(speed_b):
        return None
    moved = 0.02 * ctx.body_scale  # ignore near-static noise
    if speed_a < moved and speed_b < moved:
        return None
    ratio = min(5.0, speed_a / (speed_b + 1e-6))
    threshold = p.get("ratio_threshold", p.get("margin", 1.6))
    if ratio <= threshold:
        return None
    joints = resolve_joint_names([p["landmark_a"], p["landmark_b"]]) or resolve_joint_names(rc.joints)
    return _detect(
        rc, ctx, value=ratio, threshold=threshold, comparator="gt",
        unit="x", start=s, end=e, joints=joints,
    )


@rule("tempo")
def _tempo(rc, rep, ctx):
    p = rc.params
    duration = (rep.end - rep.start) / ctx.fps if ctx.fps else 0.0
    min_s, max_s = p.get("min_seconds"), p.get("max_seconds")
    if min_s is not None and duration < min_s:
        threshold, comparator = min_s, "lt"
    elif max_s is not None and duration > max_s:
        threshold, comparator = max_s, "gt"
    else:
        return None
    return _detect(
        rc, ctx, value=duration, threshold=threshold, comparator=comparator,
        unit="s", start=rep.start, end=rep.end, joints=resolve_joint_names(rc.joints),
    )


# --------------------------------------------------------------------------- #
# Session-level evaluation
# --------------------------------------------------------------------------- #

def _tempo_consistency(rc: RuleConfig, reps: list[RepWindow], ctx: EvalContext) -> tuple[int, FaultDetection] | None:
    if len(reps) < 3 or not ctx.fps:
        return None
    durations = np.array([(r.end - r.start) / ctx.fps for r in reps])
    mean = float(np.mean(durations))
    if mean <= 0:
        return None
    cv = float(np.std(durations) / mean)
    value = cv * 100.0  # percent
    if value <= rc.params["max_cv"]:
        return None
    worst = int(np.argmax(np.abs(durations - mean)))
    det = _detect(
        rc, ctx, value=value, threshold=rc.params["max_cv"], comparator="gt",
        unit="%", start=reps[worst].start, end=reps[worst].end,
        joints=resolve_joint_names(rc.joints),
    )
    return worst, det


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def _rep_score(faults: list[FaultDetection], base: float) -> float:
    """Per-rep score: each fault costs points by severity (minor << severe),
    scaled by the fault's confidence so a poorly-observed fault (occluded joint or
    a plane the camera can't see well) costs less than a clearly-seen one."""
    score = base - sum(SEV_PENALTY.get(f.severity, 10.0) * f.confidence for f in faults)
    return max(0.0, round(score, 1))


def evaluate_session(
    reps: list[RepWindow],
    metrics: dict[str, np.ndarray],
    landmarks: np.ndarray,
    config: ExerciseConfig,
    fps: float,
) -> list[ScoredRep]:
    from app.services.biomechanics import body_scale, camera_view

    ctx = EvalContext(
        metrics=metrics,
        landmarks=landmarks,
        fps=fps,
        config=config,
        body_scale=body_scale(landmarks),
        view=camera_view(landmarks),
    )

    # Per-rep rules.
    rep_faults: list[list[FaultDetection]] = [[] for _ in reps]
    per_rep_rules = [rc for rc in config.rules if rc.type not in SESSION_LEVEL]
    for i, rep in enumerate(reps):
        for rc in per_rep_rules:
            evaluator = _REGISTRY.get(rc.type)
            if evaluator is None:
                continue
            det = evaluator(rc, rep, ctx)
            if det is not None:
                rep_faults[i].append(det)

    # Session-level rules (attach to the most-evident rep).
    for rc in config.rules:
        if rc.type == "tempo_consistency":
            result = _tempo_consistency(rc, reps, ctx)
            if result is not None:
                idx, det = result
                rep_faults[idx].append(det)

    return [
        ScoredRep(rep=rep, score=_rep_score(faults, config.score_base), faults=faults)
        for rep, faults in zip(reps, rep_faults)
    ]


# Single-rep convenience (used in tests).
def evaluate_rep(
    rep: RepWindow,
    metrics: dict[str, np.ndarray],
    landmarks: np.ndarray,
    config: ExerciseConfig,
    fps: float,
) -> ScoredRep:
    return evaluate_session([rep], metrics, landmarks, config, fps)[0]
