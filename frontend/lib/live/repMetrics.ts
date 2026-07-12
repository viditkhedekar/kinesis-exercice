// Per-rep biomechanical measurements, computed on-device from a rep's buffered
// landmark frames. These mirror (a lightweight subset of) the backend metrics so
// the live coach can flag a *range* of faults instantly. Everything is null when
// the required joints aren't visible, so a check simply doesn't fire rather than
// firing wrongly. Approximate by design — the authoritative scored report is
// still produced server-side at finish.
import { signalFor } from "./exerciseSignals";
import { angleDeg, LANDMARK_INDEX, SIDED } from "./landmarks";
import type { RepBounds } from "./repEngine";

type Frame = number[][]; // 33 x [x, y, z, visibility]
type XY = [number, number];
type Side = "left" | "right";
const VIS = 0.4;

export interface RepMetrics {
  workedExtreme: number;
  resetExtreme: number;
  durationS: number;
  sideGapBottom: number | null; // |L-R| rep-signal angle at the bottom (deg)
  romAsym: number | null; // |romL - romR| of the rep signal (deg)
  torsoLeanBottom: number | null; // trunk lean from vertical at the bottom (deg)
  torsoLeanRange: number | null; // trunk sway across the rep (deg)
  backAngleBottom: number | null; // ear-shoulder-hip at the bottom (deg; small = rounded)
  bodyLineMin: number | null; // shoulder-hip-ankle min (deg; <180 = hips broke the plank line)
  upperArmRange: number | null; // upper-arm sway from vertical across the rep (deg)
  elbowDrift: number | null; // horizontal elbow travel vs hip, as a fraction of torso length
  wristDrift: number | null; // horizontal wrist/bar travel vs hip (fraction of torso)
  shoulderShrug: number | null; // upward shoulder travel vs hip (fraction of torso)
  heelLift: number | null; // upward heel travel vs foot (fraction of torso)
  kneeValgusBottom: number | null; // knee-separation / ankle-separation at bottom (ratio; <1 = caving)
  kneeTravel: number | null; // forward knee travel over the ankle (fraction of torso)
  hipRiseRatio: number | null; // hip vs shoulder vertical speed on the ascent (ratio)
  armFlareBottom: number | null; // elbow-shoulder-hip at bottom (deg; large = elbows flared)
  elbowBendMin: number | null; // min shoulder-elbow-wrist over the rep (deg)
  wristMin: number | null; // min elbow-wrist-index over the rep (deg)
}

function jointIdx(name: string, side: Side): number | null {
  if (name in SIDED) return SIDED[name][side === "left" ? 0 : 1];
  const explicit = `${side}_${name}`;
  return explicit in LANDMARK_INDEX ? LANDMARK_INDEX[explicit] : null;
}

function pt(f: Frame, idx: number | null): XY | null {
  if (idx === null) return null;
  const p = f[idx];
  return p && p[3] >= VIS ? [p[0], p[1]] : null;
}

function center(f: Frame, name: string): XY | null {
  const l = pt(f, jointIdx(name, "left"));
  const r = pt(f, jointIdx(name, "right"));
  if (l && r) return [(l[0] + r[0]) / 2, (l[1] + r[1]) / 2];
  return l ?? r;
}

/** Deviation of segment a->b from vertical, in degrees (0 = vertical). */
function segVert(a: XY | null, b: XY | null): number | null {
  if (!a || !b) return null;
  return (Math.atan2(Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1]) + 1e-9) * 180) / Math.PI;
}
function distp(a: XY | null, b: XY | null): number | null {
  return a && b ? Math.hypot(a[0] - b[0], a[1] - b[1]) : null;
}
function angp(a: XY | null, b: XY | null, c: XY | null): number | null {
  return a && b && c ? angleDeg(a, b, c) : null;
}
function avgSides(f: Frame, fn: (f: Frame, s: Side) => number | null): number | null {
  const v = [fn(f, "left"), fn(f, "right")].filter((x): x is number => x !== null);
  return v.length ? v.reduce((s, x) => s + x, 0) / v.length : null;
}

function range(xs: (number | null)[]): number | null {
  const v = xs.filter((x): x is number => x !== null);
  if (v.length < 2) return null;
  return Math.max(...v) - Math.min(...v);
}
function median(xs: number[]): number {
  const v = [...xs].sort((a, b) => a - b);
  return v.length ? v[Math.floor(v.length / 2)] : 0;
}
/** Value at index `i`, else the nearest non-null within ±3 frames. */
function valueAt(xs: (number | null)[], i: number): number | null {
  if (xs[i] != null) return xs[i];
  for (let d = 1; d <= 3; d++) {
    if (xs[i - d] != null) return xs[i - d];
    if (xs[i + d] != null) return xs[i + d];
  }
  return null;
}
function meanAbsDiff(xs: (number | null)[]): number | null {
  const diffs: number[] = [];
  for (let i = 1; i < xs.length; i++) {
    if (xs[i] != null && xs[i - 1] != null) diffs.push(Math.abs((xs[i] as number) - (xs[i - 1] as number)));
  }
  return diffs.length ? diffs.reduce((s, x) => s + x, 0) / diffs.length : null;
}
function netUp(xs: (number | null)[]): number | null {
  // Upward travel (y decreases) relative to the rep's starting value.
  const v = xs.filter((x): x is number => x !== null);
  if (v.length < 2) return null;
  return Math.max(0, v[0] - Math.min(...v));
}

/** Turn a rep's frame window into a battery of measurements. */
export function computeRepMetrics(exerciseKey: string, frames: Frame[], b: RepBounds): RepMetrics {
  const s = Math.max(0, Math.min(b.startIdx, frames.length - 1));
  const e = Math.max(s, Math.min(b.endIdx, frames.length - 1));
  const sub = frames.slice(s, e + 1);
  const botLocal = Math.max(0, Math.min(b.bottomIdx - s, sub.length - 1));

  const base: RepMetrics = {
    workedExtreme: b.workedExtreme,
    resetExtreme: b.resetExtreme,
    durationS: b.durationS,
    sideGapBottom: null, romAsym: null, torsoLeanBottom: null, torsoLeanRange: null,
    backAngleBottom: null, bodyLineMin: null, upperArmRange: null, elbowDrift: null,
    wristDrift: null, shoulderShrug: null, heelLift: null, kneeValgusBottom: null,
    kneeTravel: null, hipRiseRatio: null, armFlareBottom: null, elbowBendMin: null, wristMin: null,
  };
  if (sub.length < 2) return base;

  // Robust torso length for normalising pixel displacements to "% of body".
  const torsoLens = sub
    .map((f) => distp(center(f, "shoulder"), center(f, "hip")))
    .filter((d): d is number => d != null && d > 1e-3);
  const bodyScale = torsoLens.length ? median(torsoLens) : 0.25;

  // Per-frame series.
  const torso = sub.map((f) => avgSides(f, (g, side) => segVert(pt(g, jointIdx("hip", side)), pt(g, jointIdx("shoulder", side)))));
  const bodyLine = sub.map((f) => avgSides(f, (g, side) => angp(pt(g, jointIdx("shoulder", side)), pt(g, jointIdx("hip", side)), pt(g, jointIdx("ankle", side)))));
  const upperArm = sub.map((f) => avgSides(f, (g, side) => segVert(pt(g, jointIdx("shoulder", side)), pt(g, jointIdx("elbow", side)))));
  const backAngle = sub.map((f) => avgSides(f, (g, side) => angp(pt(g, jointIdx("ear", side)), pt(g, jointIdx("shoulder", side)), pt(g, jointIdx("hip", side)))));
  const armFlare = sub.map((f) => avgSides(f, (g, side) => angp(pt(g, jointIdx("elbow", side)), pt(g, jointIdx("shoulder", side)), pt(g, jointIdx("hip", side)))));
  const elbowBend = sub.map((f) => avgSides(f, (g, side) => angp(pt(g, jointIdx("shoulder", side)), pt(g, jointIdx("elbow", side)), pt(g, jointIdx("wrist", side)))));
  const wristAng = sub.map((f) => avgSides(f, (g, side) => angp(pt(g, jointIdx("elbow", side)), pt(g, jointIdx("wrist", side)), pt(g, jointIdx("index", side)))));
  const elbowRelX = sub.map((f) => avgSides(f, (g, side) => { const a = pt(g, jointIdx("elbow", side)), h = pt(g, jointIdx("hip", side)); return a && h ? a[0] - h[0] : null; }));
  const wristRelX = sub.map((f) => avgSides(f, (g, side) => { const a = pt(g, jointIdx("wrist", side)), h = pt(g, jointIdx("hip", side)); return a && h ? a[0] - h[0] : null; }));
  const shoulderRelY = sub.map((f) => avgSides(f, (g, side) => { const a = pt(g, jointIdx("shoulder", side)), h = pt(g, jointIdx("hip", side)); return a && h ? a[1] - h[1] : null; }));
  const heelRelY = sub.map((f) => avgSides(f, (g, side) => { const a = pt(g, jointIdx("heel", side)), h = pt(g, jointIdx("foot", side)); return a && h ? a[1] - h[1] : null; }));
  const lKneeRelX = sub.map((f) => { const k = pt(f, jointIdx("knee", "left")), a = pt(f, jointIdx("ankle", "left")); return k && a ? k[0] - a[0] : null; });
  const rKneeRelX = sub.map((f) => { const k = pt(f, jointIdx("knee", "right")), a = pt(f, jointIdx("ankle", "right")); return k && a ? k[0] - a[0] : null; });
  const hipY = sub.map((f) => { const c = center(f, "hip"); return c ? c[1] : null; });
  const shoulderY = sub.map((f) => { const c = center(f, "shoulder"); return c ? c[1] : null; });

  base.torsoLeanBottom = valueAt(torso, botLocal);
  base.torsoLeanRange = range(torso);
  base.bodyLineMin = (() => { const v = bodyLine.filter((x): x is number => x != null); return v.length ? Math.min(...v) : null; })();
  base.upperArmRange = range(upperArm);
  base.backAngleBottom = valueAt(backAngle, botLocal);
  base.armFlareBottom = valueAt(armFlare, botLocal);
  base.elbowBendMin = (() => { const v = elbowBend.filter((x): x is number => x != null); return v.length ? Math.min(...v) : null; })();
  base.wristMin = (() => { const v = wristAng.filter((x): x is number => x != null); return v.length ? Math.min(...v) : null; })();

  const eDrift = range(elbowRelX);
  base.elbowDrift = eDrift != null ? eDrift / bodyScale : null;
  const wDrift = range(wristRelX);
  base.wristDrift = wDrift != null ? wDrift / bodyScale : null;
  const shrug = netUp(shoulderRelY);
  base.shoulderShrug = shrug != null ? shrug / bodyScale : null;
  const heel = netUp(heelRelY);
  base.heelLift = heel != null ? heel / bodyScale : null;
  const kt = Math.max(range(lKneeRelX) ?? 0, range(rKneeRelX) ?? 0);
  base.kneeTravel = kt > 0 ? kt / bodyScale : null;

  // Knee valgus at the bottom: knee separation vs ankle separation.
  const botFrame = sub[botLocal];
  const kneeSep = distp(pt(botFrame, jointIdx("knee", "left")), pt(botFrame, jointIdx("knee", "right")));
  const ankleSep = distp(pt(botFrame, jointIdx("ankle", "left")), pt(botFrame, jointIdx("ankle", "right")));
  base.kneeValgusBottom = kneeSep != null && ankleSep != null && ankleSep > 1e-3 ? kneeSep / ankleSep : null;

  // Hips-rise-faster: vertical speed ratio on the ascent (bottom -> top).
  const asc = { hip: hipY.slice(botLocal), sh: shoulderY.slice(botLocal) };
  const hs = meanAbsDiff(asc.hip), ss = meanAbsDiff(asc.sh);
  base.hipRiseRatio = hs != null && ss != null && ss > 1e-5 ? Math.min(5, hs / ss) : null;

  // Rep-signal per side, for symmetry + range asymmetry.
  const cfg = signalFor(exerciseKey);
  if (cfg) {
    const sig = (f: Frame, side: Side): number | null => {
      const [a, bJ, c] = cfg.points.map((p) => pt(f, jointIdx(p, side)));
      return angp(a, bJ, c);
    };
    const sigL = sub.map((f) => sig(f, "left"));
    const sigR = sub.map((f) => sig(f, "right"));
    const l = valueAt(sigL, botLocal), r = valueAt(sigR, botLocal);
    base.sideGapBottom = l != null && r != null ? Math.abs(l - r) : null;
    const rl = range(sigL), rr = range(sigR);
    base.romAsym = rl != null && rr != null ? Math.abs(rl - rr) : null;
  }

  return base;
}
