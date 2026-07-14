"""Coaching: explain the deterministic analysis — never re-derive it.

The coach receives only the structured ``AnalysisReport``. ``EchoCoach`` is a
deterministic template coach: it runs entirely offline with no LLM or external
service call, so the app never sends analysis data anywhere for coaching.
"""
from __future__ import annotations

from typing import Protocol

from app.schemas import AnalysisReport


class CoachingProvider(Protocol):
    name: str

    def explain(self, report: AnalysisReport) -> str: ...


def _priority_faults(report: AnalysisReport) -> list[tuple[str, int, str]]:
    """Rank faults by frequency, carrying one example message. Returns (type, count, message)."""
    counts = report.fault_summary
    examples: dict[str, str] = {}
    for rep in report.reps:
        for f in rep.faults:
            examples.setdefault(f.type, f.message)
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [(t, c, examples.get(t, t)) for t, c in ranked]


class EchoCoach:
    name = "echo"

    def explain(self, report: AnalysisReport) -> str:
        lines: list[str] = []
        lines.append(
            f"Analyzed {report.rep_count} rep(s) of {report.exercise_name}. "
            f"Average technique score: {report.avg_score:.0f}/100."
        )
        faults = _priority_faults(report)
        if not faults:
            lines.append(
                "No technique faults were flagged — reps look clean and consistent. "
                "Keep the same control and consider progressing the load."
            )
            return "\n\n".join(lines)

        top_type, top_count, top_msg = faults[0]
        lines.append(
            f"Top priority ({top_count} of {report.rep_count} reps): {top_msg}"
        )
        if len(faults) > 1:
            secondary = "; ".join(f"{msg} ({count}/{report.rep_count})" for _, count, msg in faults[1:])
            lines.append(f"Also watch: {secondary}")
        lines.append(
            "Fix the top item first — rehearse a few slow, controlled reps focusing only on that cue, "
            "then re-film to confirm the change before adding load."
        )
        return "\n\n".join(lines)


def get_coach() -> CoachingProvider:
    # Coaching is always the deterministic, offline EchoCoach. The app never
    # calls an LLM or external service to explain analyses.
    return EchoCoach()
