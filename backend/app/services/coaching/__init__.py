"""AI coaching: explain the deterministic analysis — never re-derive it.

The coach receives only the structured ``AnalysisReport``. ``EchoCoach`` is a
deterministic template coach (no LLM, always available). ``ClaudeCoach`` sends
the report to Anthropic's API with a system prompt that forbids independent
movement analysis. The provider is chosen by ``settings.coach_provider``.
"""
from __future__ import annotations

from typing import Protocol

from app.config import get_settings
from app.schemas import AnalysisReport

SYSTEM_PROMPT = (
    "You are a strength & conditioning coach explaining an automated biomechanics "
    "report to an athlete. The report was produced by deterministic rules from "
    "video pose analysis. Your job is ONLY to explain and prioritize the findings "
    "that are given to you and suggest concrete drills or cues to fix them. "
    "Do NOT invent faults, scores, or measurements that are not in the data, and do "
    "NOT claim to have watched the video. Be specific, encouraging, and concise. "
    "Lead with the single most important thing to work on."
)


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


class ClaudeCoach:
    name = "claude"

    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.coach_model
        self._api_key = settings.anthropic_api_key

    def explain(self, report: AnalysisReport) -> str:
        import anthropic  # lazy

        client = anthropic.Anthropic(api_key=self._api_key)
        user_payload = report.model_dump_json(indent=2)
        response = client.messages.create(
            model=self._model,
            max_tokens=1500,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Here is the structured biomechanics report (JSON). Explain the "
                        "findings and give the athlete a prioritized action plan with drills:\n\n"
                        f"{user_payload}"
                    ),
                }
            ],
        )
        return "".join(b.text for b in response.content if b.type == "text").strip()


def get_coach() -> CoachingProvider:
    provider = get_settings().coach_provider.lower()
    if provider == "claude":
        return ClaudeCoach()
    return EchoCoach()
