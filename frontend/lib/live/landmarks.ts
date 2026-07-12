// Client-side mirror of the backend landmark constants (app/services/pose/
// landmarks.py). Kept in sync by hand — MediaPipe's canonical 33-landmark order
// is fixed, so this never drifts.

export const NUM_LANDMARKS = 33;

// Generic joint name -> [left index, right index]. Matches backend SIDED.
export const SIDED: Record<string, [number, number]> = {
  shoulder: [11, 12],
  elbow: [13, 14],
  wrist: [15, 16],
  index: [19, 20],
  thumb: [21, 22],
  hip: [23, 24],
  knee: [25, 26],
  ankle: [27, 28],
  heel: [29, 30],
  foot: [31, 32],
  ear: [7, 8],
  eye: [2, 5],
};

export const LANDMARK_INDEX: Record<string, number> = {
  nose: 0,
  left_shoulder: 11, right_shoulder: 12,
  left_elbow: 13, right_elbow: 14,
  left_wrist: 15, right_wrist: 16,
  left_index: 19, right_index: 20,
  left_hip: 23, right_hip: 24,
  left_knee: 25, right_knee: 26,
  left_ankle: 27, right_ankle: 28,
  left_heel: 29, right_heel: 30,
  left_foot_index: 31, right_foot_index: 32,
};

// Skeleton connections drawn as an overlay — identical to backend POSE_EDGES.
export const POSE_EDGES: number[][] = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
  [11, 23], [12, 24], [23, 24],
  [23, 25], [25, 27], [27, 31], [27, 29],
  [24, 26], [26, 28], [28, 32], [28, 30],
  [0, 11], [0, 12],
];

/** Resolve a metric's landmark points to indices for a given side. */
function resolve(name: string, side: "left" | "right"): number | null {
  if (name in SIDED) return SIDED[name][side === "left" ? 0 : 1];
  if (name in LANDMARK_INDEX) return LANDMARK_INDEX[name];
  return null;
}

/** Interior angle (deg) at point b, formed by a-b-c, in image coordinates. */
export function angleDeg(
  a: number[] | undefined,
  b: number[] | undefined,
  c: number[] | undefined,
): number | null {
  if (!a || !b || !c) return null;
  const bax = a[0] - b[0];
  const bay = a[1] - b[1];
  const bcx = c[0] - b[0];
  const bcy = c[1] - b[1];
  const dot = bax * bcx + bay * bcy;
  const nba = Math.hypot(bax, bay);
  const nbc = Math.hypot(bcx, bcy);
  if (nba < 1e-6 || nbc < 1e-6) return null;
  const cos = Math.max(-1, Math.min(1, dot / (nba * nbc)));
  return (Math.acos(cos) * 180) / Math.PI;
}

/**
 * The rep-signal angle for a three-point "angle" metric (e.g. squat knee =
 * hip-knee-ankle) resolved per side. Either side is `null` when its joints are
 * occluded. Used for the live depth gauge, rep counting, and symmetry cues —
 * never scoring (that stays server-authoritative at finish).
 */
export function signalAngleSides(
  landmarks: number[][],
  points: string[],
): { left: number | null; right: number | null } {
  const out: { left: number | null; right: number | null } = { left: null, right: null };
  if (points.length !== 3) return out;
  for (const side of ["left", "right"] as const) {
    const idx = points.map((p) => resolve(p, side));
    if (idx.some((i) => i === null)) continue;
    const [a, b, c] = idx as number[];
    // require the vertex + endpoints to be reasonably visible.
    // Landmark layout is [x, y, z, visibility] — index 3 is visibility (index 2
    // is z-depth, which is small/signed and must NOT be used as a visibility gate).
    const pts = [landmarks[a], landmarks[b], landmarks[c]];
    if (pts.some((p) => !p || p[3] < 0.4)) continue;
    out[side] = angleDeg(pts[0], pts[1], pts[2]);
  }
  return out;
}

/** Both-sides mean of the rep-signal angle (`null` if neither side is visible). */
export function signalAngle(landmarks: number[][], points: string[]): number | null {
  const { left, right } = signalAngleSides(landmarks, points);
  const vals = [left, right].filter((v): v is number => v !== null);
  return vals.length ? vals.reduce((s, v) => s + v, 0) / vals.length : null;
}
