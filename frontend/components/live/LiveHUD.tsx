"use client";

import { scoreColor } from "@/lib/poseOverlay";
import type { LiveCue } from "@/lib/types";

export interface LiveStats {
  reps: number;
  sets: number;
  elapsed: number; // seconds
  setElapsed: number; // seconds
  avgScore: number | null;
  progress: number; // 0..1 current rep depth
  tracking: boolean;
}

function fmtTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = String(Math.floor(s % 60)).padStart(2, "0");
  return `${m}:${sec}`;
}

function Tile({ label, value, mono = true, color }: { label: string; value: string; mono?: boolean; color?: string }) {
  return (
    <div className="rounded-[8px] border border-border bg-surface/80 px-3 py-2 backdrop-blur">
      <div className="eyebrow">{label}</div>
      <div className={`${mono ? "font-mono" : ""} text-xl font-semibold tabular-nums`} style={color ? { color } : undefined}>
        {value}
      </div>
    </div>
  );
}

export default function LiveHUD({
  stats,
  cue,
  paused,
  onPauseToggle,
  onRest,
  onEnd,
  finishing,
}: {
  stats: LiveStats;
  cue: LiveCue | null;
  paused: boolean;
  onPauseToggle: () => void;
  onRest: () => void;
  onEnd: () => void;
  finishing: boolean;
}) {
  return (
    <>
      {/* Top-left metric tiles */}
      <div className="absolute top-3 left-3 grid grid-cols-2 gap-2 w-[min(60vw,320px)]">
        <Tile label="Reps" value={String(stats.reps)} />
        <Tile
          label="Avg technique"
          value={stats.avgScore === null ? "—" : String(Math.round(stats.avgScore))}
          color={stats.avgScore === null ? undefined : scoreColor(stats.avgScore)}
        />
        <Tile label="Set time" value={fmtTime(stats.setElapsed)} />
        <Tile label="Elapsed · Set" value={`${fmtTime(stats.elapsed)} · ${stats.sets}`} />
      </div>

      {/* Tracking warning */}
      {!stats.tracking && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 rounded-[7px] border border-warn/40 bg-warn/15 px-3 py-1 text-[13px] text-warn backdrop-blur">
          No pose detected — step back so your whole body is in frame
        </div>
      )}

      {/* Depth gauge (right edge) */}
      <div className="absolute top-3 right-3 bottom-24 w-2.5 rounded-full bg-surface/70 border border-border overflow-hidden backdrop-blur">
        <div
          className="absolute bottom-0 left-0 right-0 bg-accent transition-[height] duration-75"
          style={{ height: `${Math.round(stats.progress * 100)}%` }}
        />
      </div>

      {/* Coaching cue (one at a time, above the controls) */}
      {cue && (
        <div className="absolute left-1/2 -translate-x-1/2 bottom-24 w-[min(92vw,560px)] animate-fade-in">
          <div className="rounded-[10px] border border-border-strong bg-surface/95 px-4 py-2.5 backdrop-blur shadow-lg">
            <div className="eyebrow mb-0.5">Coaching cue</div>
            <div className="text-sm text-fg">{cue.tip || cue.message}</div>
          </div>
        </div>
      )}

      {/* Bottom controls */}
      <div className="absolute inset-x-0 bottom-0 p-3 flex items-center justify-center gap-2 bg-gradient-to-t from-black/60 to-transparent">
        <button className="btn-ghost btn-lg" onClick={onPauseToggle} disabled={finishing}>
          {paused ? "Resume" : "Pause"}
        </button>
        <button className="btn-ghost btn-lg" onClick={onRest} disabled={finishing}>
          Rest
        </button>
        <button className="btn-primary btn-lg" onClick={onEnd} disabled={finishing}>
          {finishing ? "Analyzing…" : "End workout"}
        </button>
      </div>
    </>
  );
}
