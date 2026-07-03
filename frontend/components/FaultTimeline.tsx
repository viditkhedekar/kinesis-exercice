"use client";

import type { Rep } from "@/lib/types";
import { scoreColor } from "@/lib/poseOverlay";

interface Props {
  reps: Rep[];
  totalFrames: number;
  fps: number;
  currentFrame: number;
  onSeek: (timeSeconds: number) => void;
}

const SEV_COLOR: Record<string, string> = {
  minor: "#fbbf24",
  moderate: "#fb923c",
  severe: "#f87171",
};

export default function FaultTimeline({
  reps,
  totalFrames,
  fps,
  currentFrame,
  onSeek,
}: Props) {
  const pct = (frame: number) => `${(frame / Math.max(1, totalFrames - 1)) * 100}%`;

  // Drag anywhere on the track to scrub — the video, skeleton and joint graphs
  // all follow the cursor live. This is the interaction the product is built
  // around, so it's a continuous pointer drag, not just a click-to-seek.
  const scrubTo = (clientX: number, el: HTMLElement) => {
    const rect = el.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    onSeek((ratio * (totalFrames - 1)) / fps);
  };

  return (
    <div className="space-y-2">
      <div className="label">Timeline — drag to scrub · rep windows &amp; detected faults</div>
      <div
        className="relative h-12 rounded-lg bg-edge/60 cursor-ew-resize overflow-hidden touch-none select-none"
        onPointerDown={(e) => {
          (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
          scrubTo(e.clientX, e.currentTarget);
        }}
        onPointerMove={(e) => {
          if (e.buttons === 1) scrubTo(e.clientX, e.currentTarget);
        }}
      >
        {/* rep bands */}
        {reps.map((r) => (
          <div
            key={r.index}
            className="absolute top-0 bottom-0 border-x border-edge"
            style={{
              left: pct(r.start_frame),
              width: `${((r.end_frame - r.start_frame) / Math.max(1, totalFrames - 1)) * 100}%`,
              background: `${scoreColor(r.score)}1a`,
            }}
            title={`Rep ${r.index} — ${r.score.toFixed(0)}/100`}
          />
        ))}
        {/* fault markers */}
        {reps.flatMap((r) =>
          r.faults.map((f, i) => (
            <div
              key={`${r.index}-${i}`}
              className="absolute top-1 bottom-1 w-1 rounded"
              style={{ left: pct(f.start_frame), background: SEV_COLOR[f.severity] ?? "#f87171" }}
              title={f.message}
            />
          )),
        )}
        {/* playhead + scrub handle */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-white pointer-events-none"
          style={{ left: pct(currentFrame) }}
        >
          <span className="absolute -top-1 left-1/2 -translate-x-1/2 h-2.5 w-2.5 rounded-full bg-white shadow ring-2 ring-black/20" />
        </div>
      </div>
    </div>
  );
}
