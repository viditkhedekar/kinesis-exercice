"use client";

import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
} from "react";
import { signalFor } from "@/lib/live/exerciseSignals";
import { POSE_EDGES } from "@/lib/live/landmarks";
import { closePoseLandmarker, detectFrame, getPoseLandmarker } from "@/lib/live/mediapipe";
import { RepEngine } from "@/lib/live/repEngine";
import { computeRepMetrics, type RepMetrics } from "@/lib/live/repMetrics";
import { renderLiveFrame } from "@/lib/poseOverlay";
import type { PoseFrame } from "@/lib/types";

export interface LiveCameraHandle {
  /** Open a new set at the current buffer position (resets the rep tracker). */
  beginSet: () => void;
  /** Close the current set boundary. Safe to call when none is open. */
  endSet: () => void;
  /** Full workout buffer + set boundaries + camera dims, for POST /live/finish. */
  getFinishPayload: () => {
    frames: PoseFrame[];
    timestamps: number[];
    sets: { start: number; end: number }[];
    width: number;
    height: number;
  };
  /** The current (in-progress) set's frames + estimated fps, for /live/score. */
  getCurrentSetFrames: () => { frames: PoseFrame[]; fps: number };
}

interface Props {
  exerciseKey: string;
  /** When true, append frames + advance the rep tracker (false = paused). */
  capturing: boolean;
  mirror?: boolean;
  onReady?: () => void;
  onError?: (message: string) => void;
  /** Throttled: current rep depth 0..1 and whether a pose is tracked. */
  onTick?: (progress: number, tracking: boolean) => void;
  /** Fired when a rep completes, with that rep's measurements for instant coaching. */
  onRepComplete?: (metrics: RepMetrics) => void;
}

const LiveCamera = forwardRef<LiveCameraHandle, Props>(function LiveCamera(
  { exerciseKey, capturing, mirror = true, onReady, onError, onTick, onRepComplete },
  ref,
) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Hot-loop state kept in refs so the rAF loop never triggers React renders.
  const framesRef = useRef<PoseFrame[]>([]);
  const timesRef = useRef<number[]>([]);
  const setsRef = useRef<{ start: number; end: number }[]>([]);
  const setStartRef = useRef<number | null>(null);
  const repEngineRef = useRef<RepEngine | null>(null);
  const capturingRef = useRef(capturing);
  const lastTsRef = useRef(0);
  const lastTickRef = useRef(0);
  const callbacks = useRef({ onTick, onRepComplete });
  callbacks.current = { onTick, onRepComplete };

  // `capturing` only gates appending/rep-tracking (pause). Set boundaries are
  // opened/closed explicitly by the parent (pause keeps the set open; rest ends it).
  useEffect(() => {
    capturingRef.current = capturing;
  }, [capturing]);

  useImperativeHandle(ref, () => ({
    beginSet: () => {
      setStartRef.current = framesRef.current.length;
      repEngineRef.current?.reset();
    },
    endSet: () => {
      if (setStartRef.current === null) return;
      const end = framesRef.current.length - 1;
      if (end >= setStartRef.current) setsRef.current.push({ start: setStartRef.current, end });
      setStartRef.current = null;
    },
    getFinishPayload: () => {
      // Include any still-open set (End Workout mid-set).
      const sets = [...setsRef.current];
      if (setStartRef.current !== null) {
        const end = framesRef.current.length - 1;
        if (end >= setStartRef.current) sets.push({ start: setStartRef.current, end });
      }
      const v = videoRef.current;
      return {
        frames: framesRef.current,
        timestamps: timesRef.current,
        sets,
        width: v?.videoWidth ?? 0,
        height: v?.videoHeight ?? 0,
      };
    },
    getCurrentSetFrames: () => {
      const start = setStartRef.current ?? 0;
      const frames = framesRef.current.slice(start);
      const times = timesRef.current.slice(start);
      let fps = 15;
      if (times.length >= 2) {
        const elapsed = times[times.length - 1] - times[0];
        if (elapsed > 0) fps = Math.min(60, Math.max(5, (times.length - 1) / elapsed));
      }
      return { frames, fps };
    },
  }));

  useEffect(() => {
    const sig = signalFor(exerciseKey);
    repEngineRef.current = sig ? new RepEngine(sig) : null;

    let raf = 0;
    let stream: MediaStream | null = null;
    let cancelled = false;

    async function start() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        });
        if (cancelled) return;
        const video = videoRef.current!;
        video.srcObject = stream;
        await video.play();

        const landmarker = await getPoseLandmarker();
        if (cancelled) return;
        onReady?.();

        const ctx = canvasRef.current!.getContext("2d")!;

        const loop = () => {
          raf = requestAnimationFrame(loop);
          const v = videoRef.current;
          const canvas = canvasRef.current;
          if (!v || !canvas || v.readyState < 2) return;

          // Match the canvas backing store to its displayed size.
          const rectW = canvas.clientWidth;
          const rectH = canvas.clientHeight;
          if (canvas.width !== rectW || canvas.height !== rectH) {
            canvas.width = rectW;
            canvas.height = rectH;
          }

          // Strictly increasing timestamps are required by detectForVideo.
          let ts = performance.now();
          if (ts <= lastTsRef.current) ts = lastTsRef.current + 1;
          lastTsRef.current = ts;

          let frame: PoseFrame;
          try {
            frame = detectFrame(landmarker, v, ts);
          } catch {
            return;
          }

          renderLiveFrame(
            ctx, canvas.width, canvas.height, v.videoWidth, v.videoHeight,
            frame, POSE_EDGES, mirror,
          );

          const tracking = frame.some((p) => p[3] >= 0.4);

          if (capturingRef.current) {
            framesRef.current.push(frame);
            timesRef.current.push(ts / 1000);
            const bounds = repEngineRef.current?.update(frame, ts, framesRef.current.length - 1);
            if (bounds) {
              try {
                const metrics = computeRepMetrics(exerciseKey, framesRef.current, bounds);
                callbacks.current.onRepComplete?.(metrics);
              } catch {
                /* a metrics failure must never break the capture loop */
              }
            }
          }

          // Throttle the React-facing tick to ~12 Hz.
          if (ts - lastTickRef.current > 80) {
            lastTickRef.current = ts;
            callbacks.current.onTick?.(repEngineRef.current?.progress ?? 0, tracking);
          }
        };
        raf = requestAnimationFrame(loop);
      } catch (e) {
        onError?.(
          e instanceof DOMException && e.name === "NotAllowedError"
            ? "Camera permission denied. Enable it and reload to start."
            : "Couldn't start the camera.",
        );
      }
    }

    start();

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      stream?.getTracks().forEach((t) => t.stop());
      closePoseLandmarker();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [exerciseKey]);

  return (
    <div className="relative w-full h-full bg-black overflow-hidden">
      <video
        ref={videoRef}
        playsInline
        muted
        className="absolute inset-0 w-full h-full object-contain"
        style={{ transform: mirror ? "scaleX(-1)" : undefined }}
      />
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none" />
    </div>
  );
});

export default LiveCamera;
