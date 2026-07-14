"""Turn per-rep faults into a sports-science report: grouped issues, key
metrics, strengths, priorities, and an overall technique score.

Design goals (from coaching realism review):
- One repeated mistake is ONE grouped issue, not N penalties.
- Overall score weights severity and prevalence; good reps lift the score.
- Severe is rare — group severity is the *median* of instances, not the worst.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.exercises import ExerciseConfig
from app.services.pose.landmarks import SIDED
from app.services.rules import SEV_PENALTY

_SEV_RANK = {"minor": 0, "moderate": 1, "severe": 2}
_RANK_SEV = {0: "minor", 1: "moderate", 2: "severe"}

LEFT_IDS = {pair[0] for pair in SIDED.values()}
RIGHT_IDS = {pair[1] for pair in SIDED.values()}


@dataclass
class GroupedFault:
    type: str
    message: str
    tip: str
    severity: str
    unit: str
    count: int
    affected_reps: list[int]
    avg_value: float | None
    worst_value: float | None
    worst_rep: int | None
    confidence: float
    side: str | None
    start_frame: int  # jump target (worst rep)


def _side_of(joints: list[int]) -> str | None:
    js = set(joints)
    if js and js <= LEFT_IDS:
        return "left"
    if js and js <= RIGHT_IDS:
        return "right"
    return None


def group_faults(rep_faults: list[tuple[int, object]]) -> list[GroupedFault]:
    """Group ``(rep_index, fault)`` pairs by fault type.

    ``fault`` is any object exposing type/message/tip/severity/value/unit/
    confidence/joints/start_frame (works for both engine detections and ORM rows).
    """
    by_type: dict[str, list[tuple[int, object]]] = {}
    for rep_idx, f in rep_faults:
        by_type.setdefault(f.type, []).append((rep_idx, f))

    groups: list[GroupedFault] = []
    for ftype, items in by_type.items():
        faults = [f for _, f in items]
        reps = sorted({rep for rep, _ in items})
        values = [f.value for f in faults if f.value is not None]
        severities = sorted(_SEV_RANK.get(_sev(f), 1) for f in faults)
        group_sev = _RANK_SEV[severities[(len(severities) - 1) // 2]]  # median (lower mid)

        avg_value = round(float(np.mean(values)), 1) if values else None
        # Worst instance = furthest from the mean (most extreme deviation).
        worst_rep = worst_value = None
        if values:
            mean = float(np.mean(values))
            worst_idx = max(
                range(len(items)),
                key=lambda i: abs((faults[i].value if faults[i].value is not None else mean) - mean),
            )
            worst_rep = items[worst_idx][0]
            worst_value = round(float(faults[worst_idx].value), 1)
            start_frame = int(faults[worst_idx].start_frame)
        else:
            start_frame = int(faults[0].start_frame)

        sides = {_side_of(list(f.joints)) for f in faults}
        side = next(iter(sides)) if len(sides) == 1 else None

        groups.append(
            GroupedFault(
                type=ftype,
                message=faults[0].message,
                tip=faults[0].tip,
                severity=group_sev,
                unit=faults[0].unit,
                count=len(items),
                affected_reps=reps,
                avg_value=avg_value,
                worst_value=worst_value,
                worst_rep=worst_rep,
                confidence=round(max(float(f.confidence) for f in faults), 2),
                side=side,
                start_frame=start_frame,
            )
        )

    # Order by impact: severity, then prevalence, then confidence.
    groups.sort(
        key=lambda g: (_SEV_RANK[g.severity], len(g.affected_reps), g.confidence), reverse=True
    )
    return groups


def _sev(f) -> str:
    s = f.severity
    return s.value if hasattr(s, "value") else s


def overall_score(groups: list[GroupedFault], n_reps: int) -> float:
    """100 minus severity-, prevalence- and confidence-weighted penalties.

    A repeated fault is charged once (prevalence scales 0.5x for one rep up to
    1.0x for all reps). Crucially the penalty is also scaled by the fault's
    *confidence*: a fault the system can only observe poorly — e.g. a frontal-plane
    issue (knee cave, weight shift, L/R asymmetry) measured from a side-on view
    where the far side is occluded — is uncertain, so it should not sink the score
    the way a clearly-observed fault does. Without this weighting the recommended
    side-on view for squats/deadlifts stacks several low-confidence frontal faults
    and pushes otherwise-solid sets down into the 30s."""
    score = 100.0
    n = max(1, n_reps)
    for g in groups:
        prevalence = 0.5 + 0.5 * (len(g.affected_reps) / n)
        score -= SEV_PENALTY.get(g.severity, 10.0) * prevalence * g.confidence
    return max(0.0, round(score, 1))


def grade(score: float) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 80:
        return "Strong"
    if score >= 70:
        return "Solid"
    if score >= 55:
        return "Developing"
    return "Needs work"


def _rom(metrics: dict[str, np.ndarray], signal: str, reps) -> float:
    if signal not in metrics or not reps:
        return 0.0
    vals = []
    for r in reps:
        seg = metrics[signal][r.start : r.end + 1]
        if seg.size and not np.all(np.isnan(seg)):
            vals.append(float(np.nanmax(seg) - np.nanmin(seg)))
    return round(float(np.mean(vals)), 1) if vals else 0.0


def _symmetry(metrics: dict[str, np.ndarray], signal: str, reps) -> float | None:
    """Left/right symmetry as the mean per-rep difference in *range of motion*
    (degrees each side travels), not a pointwise ``|left - right|``.

    Pointwise difference is dominated by camera perspective (in a side view the far
    limb sits at a different apparent angle) and by any timing lag between the two
    sides, so a perfectly symmetric athlete can read as "poor". How far each side
    *moves* is far more robust to viewing angle, and is what asymmetry actually
    means here — one side doing less work than the other."""
    left, right = metrics.get(f"{signal}_left"), metrics.get(f"{signal}_right")
    if left is None or right is None or not reps:
        return None
    diffs = []
    for r in reps:
        ls, rs = left[r.start : r.end + 1], right[r.start : r.end + 1]
        if ls.size == 0 or np.all(np.isnan(ls)) or np.all(np.isnan(rs)):
            continue
        rom_l = float(np.nanmax(ls) - np.nanmin(ls))
        rom_r = float(np.nanmax(rs) - np.nanmin(rs))
        diffs.append(abs(rom_l - rom_r))
    return round(float(np.mean(diffs)), 1) if diffs else None


def key_metrics(
    reps, metrics: dict[str, np.ndarray], config: ExerciseConfig, fps: float, view: str
) -> dict:
    signal = config.rep.signal
    durations = [(r.end - r.start) / fps for r in reps] if fps else []
    tempo = round(float(np.mean(durations)), 2) if durations else 0.0
    # Coefficient of variation of rep duration. Needs >=3 reps to be meaningful —
    # with 1-2 reps it's either undefined or dominated by frame-timing noise, so we
    # report n/a (0.0) rather than a misleading number.
    consistency = (
        round(float(np.std(durations) / np.mean(durations) * 100), 0)
        if len(durations) >= 3 and np.mean(durations) > 0
        else 0.0
    )
    sym = _symmetry(metrics, signal, reps)
    return {
        "rom": _rom(metrics, signal, reps),
        "rom_unit": "deg",
        "symmetry": sym,
        "symmetry_unit": "deg",
        "symmetry_label": _sym_label(sym),
        "tempo": tempo,
        "tempo_unit": "s/rep",
        "consistency": consistency,
        "consistency_unit": "%CV",
        "consistency_label": _cv_label(consistency),
        "view": view,
        "rep_count": len(reps),
    }


def _sym_label(sym: float | None) -> str:
    if sym is None:
        return "n/a"
    if sym <= 6:
        return "good"
    if sym <= 14:
        return "fair"
    return "poor"


def _cv_label(cv: float) -> str:
    # Rep-to-rep tempo naturally varies; ~15% CV is still a controlled, even set.
    # "poor" is aligned with the ~28% CV where the engine flags inconsistent tempo,
    # so the label and the fault don't contradict each other.
    if cv == 0:
        return "n/a"
    if cv <= 15:
        return "good"
    if cv <= 28:
        return "fair"
    return "poor"


def strengths(groups: list[GroupedFault], km: dict, config: ExerciseConfig) -> list[str]:
    fault_types = {g.type for g in groups}
    out: list[str] = []
    if not any(g.severity == "severe" for g in groups):
        out.append("No high-risk faults detected")
    if km.get("symmetry_label") == "good" and not (
        {"weight_shift", "arm_height_asymmetry", "asymmetric_pull", "rom_asymmetry", "timing_asymmetry"}
        & fault_types
    ):
        out.append("Balanced left/right symmetry")
    if km.get("consistency_label") == "good":
        out.append("Consistent rep tempo")
    depth_faults = {"insufficient_depth", "incomplete_rom", "short_rom", "incomplete_extension", "incomplete_contraction"}
    if not (depth_faults & fault_types):
        out.append("Full range of motion")
    if not groups:
        out.append("Clean, controlled reps")
    return out[:4]
