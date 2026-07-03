// Per-exercise rep-signal descriptors for the browser live gauge + rep-completion
// trigger. This mirrors the `rep:` block of each backend exercise YAML. It drives
// ONLY the instant on-screen depth gauge and the "a rep just finished, ask the
// server to score" trigger — never any scoring, which stays server-authoritative.

export interface SignalConfig {
  // three-point angle metric (generic joint names, resolved per side client-side)
  points: [string, string, string];
  direction: "valley" | "peak"; // valley = bottom is a minimum angle
  bottom: number; // angle at the fully-worked position (deg)
  top: number; // angle at the reset/extended position (deg)
}

// bottom/top are the ends of the gauge; they need only be roughly right — the
// gauge normalizes progress between them and the trigger uses hysteresis.
export const EXERCISE_SIGNALS: Record<string, SignalConfig> = {
  squat: { points: ["hip", "knee", "ankle"], direction: "valley", bottom: 85, top: 170 },
  deadlift: { points: ["shoulder", "hip", "knee"], direction: "valley", bottom: 95, top: 175 },
  bicep_curl: { points: ["shoulder", "elbow", "wrist"], direction: "valley", bottom: 50, top: 160 },
  pushup: { points: ["shoulder", "elbow", "wrist"], direction: "valley", bottom: 80, top: 165 },
  lateral_raise: { points: ["hip", "shoulder", "elbow"], direction: "peak", bottom: 100, top: 20 },
  chest_press: { points: ["shoulder", "elbow", "wrist"], direction: "peak", bottom: 160, top: 90 },
  cable_row: { points: ["shoulder", "elbow", "wrist"], direction: "valley", bottom: 70, top: 165 },
  tricep_pushdown: { points: ["shoulder", "elbow", "wrist"], direction: "peak", bottom: 165, top: 90 },
  shoulder_press: { points: ["shoulder", "elbow", "wrist"], direction: "peak", bottom: 165, top: 90 },
  lat_pulldown: { points: ["shoulder", "elbow", "wrist"], direction: "valley", bottom: 70, top: 165 },
};

export function signalFor(exerciseKey: string): SignalConfig | null {
  return EXERCISE_SIGNALS[exerciseKey] ?? null;
}
