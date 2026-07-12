// On-device live coaching. The moment a rep completes, its measurements
// (repMetrics) are compared against a priority-ordered list of per-exercise
// checks and the single highest-priority triggered cue is surfaced instantly —
// no network round-trip. These mirror the deterministic rule *tips* in the
// backend exercise YAMLs; the authoritative scored report is still produced
// server-side at finish.
//
// Each exercise ships up to ~10 checks so a real range of coaching appears over
// a set. Thresholds are approximate (2D webcam landmarks) and are the knobs to
// tune if a cue over- or under-fires.
import type { SignalConfig } from "./exerciseSignals";
import { signalFor } from "./exerciseSignals";
import type { RepMetrics } from "./repMetrics";
import type { LiveCue } from "@/lib/types";

const WORK_MARGIN = 15; // deg short of the worked end before "short range" fires
const RESET_MARGIN = 15; // deg short of the reset end before "incomplete" fires
const TEMPO_MIN_S = 0.8; // reps faster than this read as rushed/bouncy

type Sev = LiveCue["severity"];
interface Check {
  id: string;
  severity: Sev;
  message: string;
  tip: string;
  test: (m: RepMetrics, cfg: SignalConfig) => boolean;
}

const C = {
  depth: (tip: string): Check => ({
    id: "depth", severity: "moderate", message: "Short range of motion", tip,
    test: (m, c) => (c.direction === "valley" ? m.workedExtreme > c.bottom + WORK_MARGIN : m.workedExtreme < c.bottom - WORK_MARGIN),
  }),
  lockout: (tip: string): Check => ({
    id: "lockout", severity: "minor", message: "Incomplete range", tip,
    test: (m, c) => (c.direction === "valley" ? m.resetExtreme < c.top - RESET_MARGIN : m.resetExtreme > c.top + RESET_MARGIN),
  }),
  overRaise: (thr: number, tip: string): Check => ({
    id: "over_raise", severity: "minor", message: "Raising too high", tip,
    test: (m) => m.workedExtreme > thr,
  }),
  tempo: (tip: string): Check => ({
    id: "tempo", severity: "minor", message: "Rushed rep", tip,
    test: (m) => m.durationS > 0 && m.durationS < TEMPO_MIN_S,
  }),
  uneven: (tip: string): Check => ({
    id: "uneven", severity: "minor", message: "Left/right uneven", tip,
    test: (m) => m.sideGapBottom != null && m.sideGapBottom > 15,
  }),
  romAsym: (tip: string): Check => ({
    id: "rom_asym", severity: "minor", message: "Uneven range", tip,
    test: (m) => m.romAsym != null && m.romAsym > 18,
  }),
  torsoLean: (thr: number, tip: string): Check => ({
    id: "torso_lean", severity: "moderate", message: "Trunk leaning", tip,
    test: (m) => m.torsoLeanBottom != null && m.torsoLeanBottom > thr,
  }),
  torsoSway: (thr: number, tip: string): Check => ({
    id: "torso_sway", severity: "minor", message: "Body swinging", tip,
    test: (m) => m.torsoLeanRange != null && m.torsoLeanRange > thr,
  }),
  backRound: (thr: number, tip: string): Check => ({
    id: "back_round", severity: "moderate", message: "Back rounding", tip,
    test: (m) => m.backAngleBottom != null && m.backAngleBottom < thr,
  }),
  valgus: (thr: number, tip: string): Check => ({
    id: "valgus", severity: "moderate", message: "Knees caving", tip,
    test: (m) => m.kneeValgusBottom != null && m.kneeValgusBottom < thr,
  }),
  kneeTravel: (thr: number, tip: string): Check => ({
    id: "knee_travel", severity: "minor", message: "Knees driving forward", tip,
    test: (m) => m.kneeTravel != null && m.kneeTravel > thr,
  }),
  heelLift: (thr: number, tip: string): Check => ({
    id: "heel_lift", severity: "minor", message: "Heels lifting", tip,
    test: (m) => m.heelLift != null && m.heelLift > thr,
  }),
  hipRise: (thr: number, tip: string): Check => ({
    id: "hip_rise", severity: "moderate", message: "Hips shooting up", tip,
    test: (m) => m.hipRiseRatio != null && m.hipRiseRatio > thr,
  }),
  upperArm: (thr: number, tip: string): Check => ({
    id: "upper_arm", severity: "minor", message: "Upper arm moving", tip,
    test: (m) => m.upperArmRange != null && m.upperArmRange > thr,
  }),
  elbowDrift: (thr: number, tip: string): Check => ({
    id: "elbow_drift", severity: "minor", message: "Elbows drifting", tip,
    test: (m) => m.elbowDrift != null && m.elbowDrift > thr,
  }),
  barPath: (thr: number, tip: string): Check => ({
    id: "bar_path", severity: "minor", message: "Bar drifting off the body", tip,
    test: (m) => m.wristDrift != null && m.wristDrift > thr,
  }),
  shoulderShrug: (thr: number, tip: string): Check => ({
    id: "shoulder_shrug", severity: "minor", message: "Shoulders shrugging", tip,
    test: (m) => m.shoulderShrug != null && m.shoulderShrug > thr,
  }),
  bodyLine: (thr: number, tip: string): Check => ({
    id: "body_line", severity: "moderate", message: "Hips out of line", tip,
    test: (m) => m.bodyLineMin != null && m.bodyLineMin < thr,
  }),
  armFlare: (thr: number, tip: string): Check => ({
    id: "arm_flare", severity: "minor", message: "Elbows flaring", tip,
    test: (m) => m.armFlareBottom != null && m.armFlareBottom > thr,
  }),
  elbowBend: (thr: number, tip: string): Check => ({
    id: "elbow_bend", severity: "minor", message: "Elbows bending", tip,
    test: (m) => m.elbowBendMin != null && m.elbowBendMin < thr,
  }),
  wristDev: (thr: number, tip: string): Check => ({
    id: "wrist_dev", severity: "minor", message: "Wrists bending", tip,
    test: (m) => m.wristMin != null && m.wristMin < thr,
  }),
};

// Priority-ordered (most important first) per-exercise check libraries.
const CHECKS: Record<string, Check[]> = {
  squat: [
    C.depth("Sit deeper — break parallel."),
    C.backRound(150, "Keep the chest up and brace the upper back."),
    C.torsoLean(48, "Brace the core and keep the chest proud; don't fold forward."),
    C.valgus(0.82, "Drive the knees out in line with the toes."),
    C.hipRise(1.7, "Drive the hips and chest up together out of the hole."),
    C.kneeTravel(0.34, "Sit back into the hips; keep the shins more vertical."),
    C.heelLift(0.11, "Keep the whole foot planted and grip the floor."),
    C.uneven("Keep the hips level and press both feet evenly."),
    C.lockout("Stand all the way up and squeeze the glutes."),
    C.tempo("Control the descent — about 2 seconds down."),
  ],
  deadlift: [
    C.backRound(150, "Set a tall, neutral spine; keep the chest proud through the pull."),
    C.hipRise(1.7, "Push the floor away; raise the hips and chest together."),
    C.depth("Reach the bar with a full hip hinge."),
    C.lockout("Finish tall — hips through, glutes squeezed."),
    C.barPath(0.1, "Keep the bar dragging up your legs; pull it back into you."),
    C.shoulderShrug(0.11, "Keep the shoulders set; don't shrug the bar up."),
    C.uneven("Grip evenly and drive through both legs equally."),
    C.romAsym("Even out the pull — one side is doing more work."),
    C.tempo("Take the slack out, then pull smoothly — no jerk."),
  ],
  bicep_curl: [
    C.depth("Curl all the way up and squeeze at the top."),
    C.lockout("Lower until the arms are fully straight."),
    C.elbowDrift(0.12, "Pin the elbows to your sides; only the forearms move."),
    C.upperArm(18, "Keep the upper arms still and vertical."),
    C.torsoSway(12, "Stand tall and brace; stop the torso from rocking."),
    C.shoulderShrug(0.1, "Keep the shoulders down; don't shrug at the top."),
    C.wristDev(150, "Keep the wrists neutral and stacked over the forearm."),
    C.uneven("Curl both arms together to the same height."),
    C.romAsym("Match the range on both arms."),
    C.tempo("Slow down — control the weight down."),
  ],
  pushup: [
    C.bodyLine(162, "Squeeze the glutes and brace to hold one straight line."),
    C.depth("Lower until the elbows reach about 90°."),
    C.lockout("Press all the way to straight arms."),
    C.armFlare(78, "Tuck the elbows to about 45° — make an arrow, not a T."),
    C.uneven("Keep the chest square and lower both arms evenly."),
    C.romAsym("Match left and right depth."),
    C.tempo("Take about 1.5 seconds to lower under control."),
  ],
  lateral_raise: [
    C.depth("Raise until the arms are level with your shoulders."),
    C.overRaise(112, "Stop at shoulder height; higher shifts work to the traps."),
    C.elbowBend(150, "Keep a fixed soft bend in the elbows throughout."),
    C.torsoSway(14, "Stand tall and brace; only the arms should move."),
    C.shoulderShrug(0.1, "Depress the shoulders and lead with the elbows."),
    C.uneven("Raise both arms to the same height."),
    C.romAsym("Match the range on both arms."),
    C.lockout("Lower all the way under control between reps."),
    C.tempo("No swinging — about 1 second up, slow down."),
  ],
  chest_press: [
    C.depth("Press all the way out to straight arms."),
    C.lockout("Let the handles come back for a full chest stretch."),
    C.upperArm(24, "Keep the elbows about 45° to the ribs; don't flare."),
    C.torsoSway(12, "Keep your back on the pad; only the arms move."),
    C.uneven("Press both handles out evenly."),
    C.romAsym("Match the range on both arms."),
    C.shoulderShrug(0.1, "Keep the shoulders down and set on the pad."),
    C.tempo("Control the press — own both ends of the range."),
  ],
  cable_row: [
    C.depth("Drive the handle all the way to your torso."),
    C.lockout("Let the arms extend fully in front each rep."),
    C.torsoSway(16, "Keep the torso near-upright; row with the back, not by leaning."),
    C.shoulderShrug(0.1, "Keep the shoulders down; lead with the elbows."),
    C.upperArm(18, "Keep the upper arms tracking close to the body."),
    C.uneven("Pull both arms back evenly."),
    C.romAsym("Match the range on both arms."),
    C.tempo("Control the handle back out — no yanking."),
  ],
  tricep_pushdown: [
    C.depth("Push down to straight arms and squeeze."),
    C.lockout("Let the bar rise past parallel each rep."),
    C.upperArm(18, "Pin the elbows to your sides; only the forearms move."),
    C.torsoSway(14, "Stand tall and brace; drive through the triceps alone."),
    C.elbowDrift(0.12, "Keep the elbows fixed at your sides."),
    C.uneven("Push both sides down evenly."),
    C.romAsym("Match the range on both arms."),
    C.tempo("Resist the bar back up under control."),
  ],
  shoulder_press: [
    C.depth("Press to full overhead lockout."),
    C.lockout("Lower to at least chin height each rep."),
    C.torsoSway(16, "Squeeze the glutes and brace; keep the ribcage down."),
    C.upperArm(24, "Keep the forearms vertical and elbows under the wrists."),
    C.uneven("Press both arms to the same height."),
    C.romAsym("Match the range on both arms."),
    C.shoulderShrug(0.1, "Keep the shoulders packed; don't shrug at the top."),
    C.tempo("No leg drive — press smoothly under control."),
  ],
  lat_pulldown: [
    C.depth("Pull the bar down to your upper chest."),
    C.lockout("Let the arms straighten fully at the top."),
    C.torsoSway(18, "Keep the trunk near-upright; pull with the back, not by rocking."),
    C.shoulderShrug(0.1, "Start each rep by pulling the shoulder blades down."),
    C.upperArm(18, "Drive the elbows down and back."),
    C.uneven("Pull both arms down evenly."),
    C.romAsym("Match the range on both arms."),
    C.tempo("Control the bar back up — no letting it fly."),
  ],
};

/**
 * Evaluate a just-completed rep and return the single highest-priority coaching
 * cue, or `null` if the rep looked clean. Deterministic and instant.
 */
export function evaluateLiveCues(exerciseKey: string, m: RepMetrics): LiveCue | null {
  const cfg = signalFor(exerciseKey);
  const list = CHECKS[exerciseKey];
  if (!cfg || !list) return null;
  for (const c of list) {
    try {
      if (c.test(m, cfg)) return { type: c.id, message: c.message, tip: c.tip, severity: c.severity };
    } catch {
      /* a bad measurement never breaks coaching */
    }
  }
  return null;
}
