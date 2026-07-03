"use client";

import { useEffect, useRef, useState } from "react";
import { renderOverlay } from "@/lib/poseOverlay";
import type { Ghost, Landmarks, Rep, RepFault } from "@/lib/types";

/**
 * Skeleton-only playback for a finished live session (there's no recorded
 * video). Reuses the report overlay renderer — live skeleton, fault highlights
 * and phase-aligned Ghost Replay — driven by a transport bar instead of a
 * `<video>` element.
 */
export default function LivePlayer({
  landmarks,
  reps,
  faults,
  ghost,
  showGhost,
}: {
  landmarks: Landmarks;
  reps: Rep[];
  faults: RepFault[];
  ghost: Ghost | null;
  showGhost: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const total = landmarks.frames.length;
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(true);
  const frameRef = useRef(0);
  frameRef.current = frame;

  // Playback clock at the capture fps.
  useEffect(() => {
    if (!playing || total === 0) return;
    const fps = landmarks.fps || 15;
    const id = setInterval(() => {
      setFrame((f) => (f + 1) % total);
    }, 1000 / fps);
    return () => clearInterval(id);
  }, [playing, total, landmarks.fps]);

  // Draw the current frame whenever it (or overlay inputs) change.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    renderOverlay(ctx, canvas.width, canvas.height, landmarks, frame, ghost, reps, showGhost, faults);
  }, [frame, landmarks, ghost, reps, showGhost, faults]);

  const aspect = landmarks.width && landmarks.height ? landmarks.width / landmarks.height : 16 / 9;

  return (
    <div className="space-y-2">
      <div className="relative w-full bg-black rounded-[10px] overflow-hidden border border-border" style={{ aspectRatio: aspect }}>
        <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />
      </div>
      <div className="flex items-center gap-3">
        <button className="btn-ghost px-2" onClick={() => setPlaying((p) => !p)}>
          {playing ? "❚❚" : "▶"}
        </button>
        <input
          type="range"
          min={0}
          max={Math.max(0, total - 1)}
          value={frame}
          onChange={(e) => {
            setPlaying(false);
            setFrame(Number(e.target.value));
          }}
          className="flex-1 accent-accent"
        />
        <span className="text-faint text-[12px] tabular-nums w-20 text-right">
          {frame} / {Math.max(0, total - 1)}
        </span>
      </div>
    </div>
  );
}
