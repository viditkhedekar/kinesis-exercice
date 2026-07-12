// Browser-side rep tracker. It watches the rep-signal joint angle, drives the
// live depth gauge (0..1 `progress`), and fires once per completed rep with the
// rep's frame window + basic shape. A companion pass (repMetrics) turns that
// window into a full battery of biomechanical measurements for on-device
// coaching. This is the authoritative *live* rep counter; the end-of-session
// review re-derives counts/scores server-side for the report.
//
// Reps are detected by extrema (top -> bottom -> top) with hysteresis, and each
// rep is finalized at its *true* top so the window spans the full movement.
import type { SignalConfig } from "./exerciseSignals";
import { signalAngleSides } from "./landmarks";

const REACH_BOTTOM = 0.6; // must pass this depth for a rep to be valid (forgiving)
const RETURN_TOP = 0.35; // "at the top" band — must come back into it to complete
const HYST = 0.08; // reversal hysteresis so jitter doesn't split a rep
const TOP_DWELL_MS = 150; // finalize a held top this soon (keeps the counter snappy)

export interface RepBounds {
  /** Buffer indices delimiting the rep (top -> bottom -> top). */
  startIdx: number;
  bottomIdx: number;
  endIdx: number;
  /** Fully-worked extreme (min angle for a valley exercise, max for a peak). */
  workedExtreme: number;
  /** Reset/extended extreme actually reached at the top of the rep. */
  resetExtreme: number;
  /** Full top-to-top rep duration in seconds. */
  durationS: number;
}

export class RepEngine {
  private cfg: SignalConfig;
  private started = false;
  private state: "seekBottom" | "seekTop" = "seekBottom";
  private prevTopMs = 0;
  private prevTopIdx = 0;
  private repMin = Infinity;
  private repMax = -Infinity;
  // seekBottom
  private hi = 0;
  private hiIdx = 0;
  private bottomReached = false;
  // seekTop
  private lo = 1;
  private loAngle = 0;
  private loMs = 0;
  private loIdx = 0;
  private topSinceMs: number | null = null;
  /** 0 (reset/top) .. 1 (fully worked/bottom) for the current position. */
  progress = 0;

  constructor(cfg: SignalConfig) {
    this.cfg = cfg;
    this.loAngle = cfg.top;
  }

  private normalize(angle: number): number {
    const { bottom, top } = this.cfg;
    return Math.max(0, Math.min(1, (angle - top) / (bottom - top)));
  }

  /**
   * Feed one frame's landmarks, capture time (ms), and its buffer index. Returns
   * `RepBounds` on the frame a rep finalizes (at its top), else `null`. Frames
   * with no usable signal are ignored.
   */
  update(landmarks: number[][], tsMs: number, frameIdx: number): RepBounds | null {
    const { left, right } = signalAngleSides(landmarks, this.cfg.points);
    const vals = [left, right].filter((v): v is number => v !== null);
    if (!vals.length) return null;
    const angle = vals.reduce((s, v) => s + v, 0) / vals.length;
    this.progress = this.normalize(angle);

    if (!this.started) {
      this.started = true;
      this.prevTopMs = tsMs;
      this.prevTopIdx = frameIdx;
      this.repMin = angle;
      this.repMax = angle;
      this.hi = this.progress;
      this.hiIdx = frameIdx;
      this.bottomReached = this.progress >= REACH_BOTTOM;
      this.state = "seekBottom";
      return null;
    }

    this.repMin = Math.min(this.repMin, angle);
    this.repMax = Math.max(this.repMax, angle);

    if (this.state === "seekBottom") {
      if (this.progress > this.hi) {
        this.hi = this.progress;
        this.hiIdx = frameIdx;
      }
      if (this.progress >= REACH_BOTTOM) this.bottomReached = true;
      // Bottom passed once we've been deep and started rising back up.
      if (this.bottomReached && this.progress <= this.hi - HYST) {
        this.state = "seekTop";
        this.lo = this.progress;
        this.loAngle = angle;
        this.loMs = tsMs;
        this.loIdx = frameIdx;
        this.topSinceMs = this.progress <= RETURN_TOP ? tsMs : null;
      }
      return null;
    }

    // seekTop: track the highest point (min progress) and finalize at the top.
    if (this.progress < this.lo) {
      this.lo = this.progress;
      this.loAngle = angle;
      this.loMs = tsMs;
      this.loIdx = frameIdx;
    }
    const atTop = this.progress <= RETURN_TOP;
    if (atTop && this.topSinceMs === null) this.topSinceMs = tsMs;
    if (!atTop) this.topSinceMs = null;

    const nextDescent = this.progress >= this.lo + HYST && this.lo <= RETURN_TOP;
    const dwelled = this.topSinceMs !== null && tsMs - this.topSinceMs >= TOP_DWELL_MS;

    if (this.lo <= RETURN_TOP && (nextDescent || dwelled)) {
      const valley = this.cfg.direction === "valley";
      const bounds: RepBounds = {
        startIdx: this.prevTopIdx,
        bottomIdx: this.hiIdx,
        endIdx: this.loIdx,
        workedExtreme: valley ? this.repMin : this.repMax,
        resetExtreme: this.loAngle,
        durationS: Math.max(0, (this.loMs - this.prevTopMs) / 1000),
      };
      // Re-arm for the next rep from this top.
      this.prevTopMs = this.loMs;
      this.prevTopIdx = this.loIdx;
      this.state = "seekBottom";
      this.hi = this.progress;
      this.hiIdx = frameIdx;
      this.bottomReached = this.progress >= REACH_BOTTOM;
      this.repMin = angle;
      this.repMax = angle;
      return bounds;
    }
    return null;
  }

  /** Reset between sets (next frame re-initialises the tracker). */
  reset() {
    this.started = false;
    this.state = "seekBottom";
    this.bottomReached = false;
    this.progress = 0;
  }
}
