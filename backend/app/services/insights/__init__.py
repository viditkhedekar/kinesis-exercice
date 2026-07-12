"""Insight cards: one or two concise, deterministic observations per session.

These are *not* new analysis — every insight is derived from data the engine has
already produced (per-rep windows, sided metrics, grouped faults, key metrics)
plus the previous session's stored summary for change-over-time. Nothing here is
AI-generated or heuristic guesswork: each card states a measured fact.

Examples of what this surfaces:
- "Your left arm reached each rep's turnaround about 0.18s after your right,
   across 6 of 8 reps."   (per-rep side-timing lag)
- "Depth improved by 9% compared with your previous session."  (cross-session ROM)
- "Squat stops above parallel on 4 of 6 reps, averaging 118°."  (fault prevalence)

Selection: candidates are scored by salience, then the top few are taken with at
most one card per *kind* and a light nudge toward including a positive note so a
good session doesn't read as all-negative.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.exercises import ExerciseConfig

# Joints that read as "arm" vs "leg" for natural side-lag phrasing.
_ARM_SIGNALS = {"elbow", "wrist", "abduction", "shoulder"}
_LEG_SIGNALS = {"knee", "hip", "ankle"}

# Exercises where range-of-motion is naturally described as "depth".
_DEPTH_EXERCISES = {"squat", "pushup"}


@dataclass
class _Candidate:
    kind: str          # dedup key + icon selector
    tone: str          # "positive" | "attention" | "neutral"
    text: str          # the full observation sentence
    emphasis: str | None
    salience: float    # higher = shown first


def _fmt(value: float | None, unit: str) -> str:
    """Mirror the frontend's measured-value formatting for consistency."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    decimals = 2 if unit in {"ratio", "x", "s"} else 0 if unit in {"%CV"} else 1
    n = f"{value:.{decimals}f}"
    if n.endswith(".0"):  # 118.0 -> 118 reads cleaner in a sentence
        n = n[:-2]
    return {
        "deg": f"{n}°",
        "%body": f"{n}% body",
        "x": f"{n}×",
        "ratio": n,
        "%": f"{n}%",
        "%CV": f"{n}%",
        "": n,
    }.get(unit, f"{n} {unit}")


def _limb_word(signal: str) -> str:
    if signal in _ARM_SIGNALS:
        return "arm"
    if signal in _LEG_SIGNALS:
        return "leg"
    return "side"


def _side_timing(reps, metrics, config: ExerciseConfig, fps: float) -> _Candidate | None:
    """Per-rep timing lag between the left and right of the rep-signal joint.

    For each rep we find the frame where each side reaches the movement's
    turnaround (the signal's min for a valley exercise, max for a peak), and
    measure the signed lag. If one side consistently trails across a majority of
    reps by a perceptible margin, that's a genuine, specific observation.
    """
    if not fps or len(reps) < 4:
        return None
    signal = config.rep.signal
    left, right = metrics.get(f"{signal}_left"), metrics.get(f"{signal}_right")
    if left is None or right is None:
        return None
    peak = config.rep.direction == "peak"

    lags: list[float] = []  # +ve => right reaches turnaround later than left
    for r in reps:
        ls, rs = left[r.start : r.end + 1], right[r.start : r.end + 1]
        if ls.size < 2 or np.all(np.isnan(ls)) or np.all(np.isnan(rs)):
            continue
        fl = int(np.nanargmax(ls) if peak else np.nanargmin(ls))
        fr = int(np.nanargmax(rs) if peak else np.nanargmin(rs))
        lags.append((fr - fl) / fps)
    m = len(lags)
    if m < 4:
        return None

    arr = np.array(lags)
    dom = 1.0 if np.median(arr) >= 0 else -1.0
    hits = [abs(l) for l in lags if (l >= 0) == (dom >= 0) and abs(l) >= 0.05]
    n = len(hits)
    if n < max(3, math.ceil(m / 2)):
        return None
    avg_lag = float(np.mean(hits))
    if avg_lag < 0.08:
        return None

    later = "right" if dom > 0 else "left"
    earlier = "left" if dom > 0 else "right"
    limb = _limb_word(signal)
    text = (
        f"Your {later} {limb} reached each rep's turnaround about "
        f"{avg_lag:.2f}s after your {earlier}, across {n} of {m} reps."
    )
    # More reps + bigger lag = more noteworthy.
    salience = 90.0 + min(8.0, n) + min(4.0, avg_lag * 10)
    return _Candidate("timing", "attention", text, f"{avg_lag:.2f}s", salience)


def _progress(km: dict, overall: float, prev_km: dict | None, prev_overall: float | None,
              config: ExerciseConfig) -> _Candidate | None:
    """The most notable change versus the previous session (ROM/depth first,
    then overall technique score). One progress card at most."""
    best: _Candidate | None = None

    if prev_km:
        cur_rom, prev_rom = km.get("rom") or 0.0, prev_km.get("rom") or 0.0
        if cur_rom > 0 and prev_rom > 0:
            pct = (cur_rom - prev_rom) / prev_rom * 100.0
            if abs(pct) >= 4:
                word = "Depth" if config.key in _DEPTH_EXERCISES else "Range of motion"
                verb = "improved by" if pct > 0 else "dropped by"
                tone = "positive" if pct > 0 else "attention"
                text = f"{word} {verb} {abs(pct):.0f}% compared with your previous session."
                emphasis = f"{'+' if pct > 0 else '−'}{abs(pct):.0f}%"
                best = _Candidate("progress", tone, text, emphasis, 70.0 + min(25.0, abs(pct)))

    if prev_overall is not None and overall is not None:
        delta = overall - prev_overall
        if abs(delta) >= 3 and (best is None or abs(delta) > (best.salience - 68.0)):
            tone = "positive" if delta > 0 else "attention"
            verb = "up" if delta > 0 else "down"
            text = (
                f"Overall technique {verb} {abs(delta):.0f} points from your previous "
                f"session ({prev_overall:.0f} → {overall:.0f})."
            )
            emphasis = f"{'+' if delta > 0 else '−'}{abs(delta):.0f} pts"
            cand = _Candidate("progress", tone, text, emphasis, 68.0 + min(25.0, abs(delta)))
            # Prefer whichever change is more salient.
            if best is None or cand.salience > best.salience:
                best = cand
    return best


def _prevalence(groups, n_reps: int) -> _Candidate | None:
    """The most impactful recurring fault, phrased as a measured observation."""
    for g in groups:
        k = len(g.affected_reps)
        if k < 2:
            continue
        clause = g.message.split("—")[0].split(". ")[0].strip().rstrip(".")
        if len(clause) > 96:
            clause = clause[:93].rstrip() + "…"
        detail = f", averaging {_fmt(g.avg_value, g.unit)}" if g.avg_value is not None else ""
        text = f"{clause} on {k} of {n_reps} reps{detail}."
        emphasis = f"{k}/{n_reps} reps"
        sev_rank = {"minor": 0, "moderate": 1, "severe": 2}.get(g.severity, 1)
        return _Candidate("prevalence", "attention", text, emphasis, 50.0 + k * 3 + sev_rank * 5)
    return None


def _positives(groups, km: dict, n_reps: int, has_timing: bool) -> list[_Candidate]:
    out: list[_Candidate] = []
    if not groups and n_reps > 0:
        out.append(_Candidate(
            "clean", "positive",
            f"No technique faults across all {n_reps} reps — clean, controlled execution.",
            f"{n_reps}/{n_reps} clean", 46.0,
        ))
    # Don't claim "balanced" if a side-timing lag was just reported.
    if not has_timing and km.get("symmetry_label") == "good" and km.get("symmetry") is not None:
        out.append(_Candidate(
            "symmetry", "positive",
            f"Left and right stayed balanced within {km['symmetry']:.1f}° through the set.",
            f"{km['symmetry']:.1f}°", 40.0,
        ))
    if km.get("consistency_label") == "good" and n_reps >= 3 and km.get("consistency"):
        out.append(_Candidate(
            "consistency", "positive",
            f"Rep tempo held steady (CV {km['consistency']:.0f}%) across all {n_reps} reps.",
            f"{km['consistency']:.0f}% CV", 38.0,
        ))
    return out


def generate_insights(
    *,
    reps,
    metrics: dict,
    config: ExerciseConfig,
    fps: float,
    groups,
    km: dict,
    overall: float,
    prev_km: dict | None,
    prev_overall: float | None,
    max_cards: int = 2,
) -> list[dict]:
    """Produce up to ``max_cards`` insight dicts (``kind``/``tone``/``text``/``emphasis``)."""
    n_reps = len(reps)
    if n_reps == 0:
        return []

    timing = _side_timing(reps, metrics, config, fps)
    candidates: list[_Candidate] = [c for c in (
        timing,
        _progress(km, overall, prev_km, prev_overall, config),
        _prevalence(groups, n_reps),
    ) if c is not None]
    candidates += _positives(groups, km, n_reps, has_timing=timing is not None)

    candidates.sort(key=lambda c: c.salience, reverse=True)

    picked: list[_Candidate] = []
    seen_kinds: set[str] = set()
    for c in candidates:
        if c.kind in seen_kinds:
            continue
        picked.append(c)
        seen_kinds.add(c.kind)
        if len(picked) == max_cards:
            break

    # Nudge toward one encouraging note: if everything picked is "attention" and a
    # positive candidate exists, swap the weakest pick for the best positive.
    if picked and all(c.tone == "attention" for c in picked):
        pos = next((c for c in candidates if c.tone == "positive" and c.kind not in seen_kinds), None)
        if pos is not None and len(picked) >= 2:
            picked[-1] = pos

    return [{"kind": c.kind, "tone": c.tone, "text": c.text, "emphasis": c.emphasis} for c in picked]
