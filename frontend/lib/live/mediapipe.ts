// Browser MediaPipe Pose Landmarker wrapper. The wasm runtime + the .task model
// are self-hosted under /public/mediapipe (no CDN round-trip, works offline).
//
// Runs in VIDEO mode on the GPU delegate: one inference per animation frame,
// which is what lets the overlay hold ~30 FPS.
import type { PoseLandmarker as PoseLandmarkerType } from "@mediapipe/tasks-vision";
import { NUM_LANDMARKS } from "./landmarks";

let landmarkerPromise: Promise<PoseLandmarkerType> | null = null;

/** Lazily create (and cache) a single PoseLandmarker instance. */
export async function getPoseLandmarker(): Promise<PoseLandmarkerType> {
  if (!landmarkerPromise) {
    landmarkerPromise = (async () => {
      const vision = await import("@mediapipe/tasks-vision");
      const { FilesetResolver, PoseLandmarker } = vision;
      const fileset = await FilesetResolver.forVisionTasks("/mediapipe/wasm");
      return PoseLandmarker.createFromOptions(fileset, {
        baseOptions: {
          modelAssetPath: "/mediapipe/pose_landmarker.task",
          delegate: "GPU",
        },
        runningMode: "VIDEO",
        numPoses: 1,
        minPoseDetectionConfidence: 0.5,
        minPosePresenceConfidence: 0.5,
        minTrackingConfidence: 0.5,
      });
    })();
  }
  return landmarkerPromise;
}

/**
 * Run detection on the current video frame and return a `(33, 4)` landmark
 * frame: `[x, y, z, visibility]` per landmark in normalized image coords, NaN /
 * visibility 0 where no pose is detected — matching the backend pose format.
 */
export function detectFrame(
  landmarker: PoseLandmarkerType,
  video: HTMLVideoElement,
  timestampMs: number,
): number[][] {
  const out: number[][] = Array.from({ length: NUM_LANDMARKS }, () => [NaN, NaN, NaN, 0]);
  const result = landmarker.detectForVideo(video, timestampMs);
  const lms = result.landmarks?.[0];
  if (lms) {
    for (let i = 0; i < Math.min(lms.length, NUM_LANDMARKS); i++) {
      const lm = lms[i];
      out[i] = [lm.x, lm.y, lm.z, lm.visibility ?? 1];
    }
  }
  return out;
}

/** Release the cached landmarker (e.g. on navigating away from live mode). */
export function closePoseLandmarker() {
  if (landmarkerPromise) {
    landmarkerPromise.then((l) => l.close()).catch(() => {});
    landmarkerPromise = null;
  }
}
