"""Lightweight stage timing for the analysis pipeline.

``StageTimer`` records the wall-clock duration of each named stage and logs a
single, readable breakdown per analysis (durations, cumulative offsets from the
request being received, and each stage's share of the total). It's intentionally
dependency-free and cheap enough to leave on in production.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone

logger = logging.getLogger("kinesis.timing")


class StageTimer:
    def __init__(self, label: str) -> None:
        self.label = label
        self._t0 = time.perf_counter()
        self._entries: list[tuple[str, float]] = []
        self._notes: dict[str, str] = {}
        self.started_at = datetime.now(timezone.utc)

    @contextmanager
    def stage(self, name: str):
        """Time a block: ``with timer.stage("biomechanics"): ...``."""
        start = time.perf_counter()
        try:
            yield
        finally:
            self.add(name, time.perf_counter() - start)

    def add(self, name: str, seconds: float) -> None:
        """Record an externally-measured stage duration (seconds)."""
        self._entries.append((name, float(seconds)))

    def merge(self, timings: dict[str, float]) -> None:
        """Fold in a dict of {stage: seconds} (e.g. sub-stages from run_pose)."""
        for name, seconds in timings.items():
            self.add(name, seconds)

    def note(self, key: str, value: object) -> None:
        """Attach a non-timing datapoint to the report, e.g. frames processed."""
        self._notes[key] = str(value)

    def total(self) -> float:
        return time.perf_counter() - self._t0

    def breakdown(self) -> str:
        total = self.total()
        cum = 0.0
        head = f"    {'stage':<26}{'dur':>10}{'elapsed':>11}{'share':>8}"
        lines = [
            f"⏱  {self.label} — started {self.started_at.isoformat(timespec='milliseconds')}",
            head,
        ]
        for name, dur in self._entries:
            cum += dur
            share = (dur / total * 100.0) if total else 0.0
            lines.append(f"    {name:<26}{dur * 1000:8.1f}ms{cum * 1000:9.1f}ms{share:7.1f}%")
        lines.append(f"    {'TOTAL':<26}{total * 1000:8.1f}ms")
        if self._notes:
            lines.append("    " + "  ".join(f"{k}={v}" for k, v in self._notes.items()))
        return "\n".join(lines)

    def log(self) -> None:
        logger.info(self.breakdown())
