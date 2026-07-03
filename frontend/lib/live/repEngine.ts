// Lightweight, browser-side rep-phase tracker. Given the current rep-signal
// angle, it reports a 0..1 "depth" for the live gauge and fires a callback each
// time a rep *completes* (bottom reached, then returned toward the top). That
// callback is the trigger to ask the server to score the set — the server owns
// the authoritative rep count and scoring; this only decides *when* to ask and
// how full the current rep looks *right now*.
import type { SignalConfig } from "./exerciseSignals";
import { signalAngle } from "./landmarks";

const REACH_BOTTOM = 0.8; // progress past which we consider the bottom reached
const RETURN_TOP = 0.2; // progress back below which a rep counts as completed

export class RepEngine {
  private cfg: SignalConfig;
  private reachedBottom = false;
  private minAngleSeen = Infinity;
  private maxAngleSeen = -Infinity;
  /** 0 (reset/top) .. 1 (fully worked/bottom) for the current position. */
  progress = 0;

  constructor(cfg: SignalConfig) {
    this.cfg = cfg;
  }

  /** Normalized progress of an angle between the reset (top) and worked (bottom) ends. */
  private normalize(angle: number): number {
    const { bottom, top } = this.cfg;
    const p = (angle - top) / (bottom - top);
    return Math.max(0, Math.min(1, p));
  }

  /**
   * Feed one frame's landmarks. Returns `true` on the frame a rep completes.
   * Frames with no usable signal (occluded joints) are ignored.
   */
  update(landmarks: number[][]): boolean {
    const angle = signalAngle(landmarks, this.cfg.points);
    if (angle === null) return false;

    this.progress = this.normalize(angle);
    this.minAngleSeen = Math.min(this.minAngleSeen, angle);
    this.maxAngleSeen = Math.max(this.maxAngleSeen, angle);

    if (this.progress >= REACH_BOTTOM) {
      this.reachedBottom = true;
      return false;
    }
    if (this.reachedBottom && this.progress <= RETURN_TOP) {
      this.reachedBottom = false;
      return true; // a rep just finished
    }
    return false;
  }

  /** Reset between sets. */
  reset() {
    this.reachedBottom = false;
    this.minAngleSeen = Infinity;
    this.maxAngleSeen = -Infinity;
    this.progress = 0;
  }
}
