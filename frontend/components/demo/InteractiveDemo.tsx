"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AngleChart } from "@/components/charts";
import GroupedFaultList from "@/components/GroupedFaultList";
import ScoreHero from "@/components/ScoreHero";
import Strengths from "@/components/Strengths";
import { scoreColor } from "@/lib/poseOverlay";
import { loadDemos, type DemoExample } from "@/lib/demoData";
import type { AnalysisMetrics } from "@/lib/types";
import DemoSkeleton from "./DemoSkeleton";

type Phase = "idle" | "processing" | "report";
const STAGES = ["Pose estimation", "Joint angles", "Rep detection", "Fault analysis", "Scoring"];

export default function InteractiveDemo({ initialPhase = "idle" }: { initialPhase?: Phase }) {
  const [examples, setExamples] = useState<DemoExample[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [phase, setPhase] = useState<Phase>(initialPhase);
  const [idx, setIdx] = useState(0);
  const [autoplay, setAutoplay] = useState(true);
  const [stage, setStage] = useState(0);

  useEffect(() => {
    let alive = true;
    loadDemos()
      .then((ex) => alive && setExamples(ex))
      .catch(() => alive && setLoadError(true));
    return () => {
      alive = false;
    };
  }, []);

  const ex = examples?.[idx];

  // While idle and untouched, cycle through the examples.
  useEffect(() => {
    if (phase !== "idle" || !autoplay || !examples) return;
    const t = setInterval(() => setIdx((i) => (i + 1) % examples.length), 4200);
    return () => clearInterval(t);
  }, [phase, autoplay, examples]);

  // Staged "analysis" animation before revealing the report.
  useEffect(() => {
    if (phase !== "processing") return;
    setStage(0);
    const timers = STAGES.map((_, i) => setTimeout(() => setStage(i + 1), (i + 1) * 460));
    const done = setTimeout(() => setPhase("report"), STAGES.length * 460 + 400);
    return () => {
      timers.forEach(clearTimeout);
      clearTimeout(done);
    };
  }, [phase]);

  const analysisMetrics: AnalysisMetrics | null = useMemo(
    () =>
      ex
        ? { fps: ex.fps, frames: ex.frames.length, stride: ex.stride, rep_bounds: ex.rep_bounds, series: ex.series }
        : null,
    [ex],
  );

  if (loadError) {
    return (
      <div className="card p-8 text-center text-sm text-muted">
        Couldn’t load the demo data. <Link href="/signup" className="text-fg underline">Sign up</Link> to analyze your own video.
      </div>
    );
  }
  if (!ex) {
    return (
      <div className="card p-4 sm:p-6">
        <div className="grid lg:grid-cols-2 gap-6 items-center">
          <div className="skeleton aspect-square rounded-xl" />
          <div className="space-y-3">
            <div className="skeleton h-5 w-2/3" />
            <div className="skeleton h-3 w-full" />
            <div className="skeleton h-3 w-4/5" />
            <div className="skeleton h-8 w-40" />
          </div>
        </div>
      </div>
    );
  }

  const pick = (i: number) => {
    setIdx(i);
    setAutoplay(false);
  };

  return (
    <div className="card p-4 sm:p-6">
      {/* Exercise selector — the examples the demo cycles through */}
      {phase !== "report" && (
        <div className="flex flex-wrap items-center gap-1.5 mb-5">
          {examples!.map((e, i) => (
            <button
              key={e.key}
              onClick={() => pick(i)}
              disabled={phase === "processing"}
              className={`rounded-[7px] border px-2.5 h-7 text-[12px] font-medium transition disabled:opacity-60 ${
                i === idx
                  ? "border-border-strong bg-surface-2 text-fg"
                  : "border-border text-muted hover:text-fg hover:bg-surface-2"
              }`}
            >
              {e.name}
            </button>
          ))}
          {autoplay && phase === "idle" && (
            <span className="ml-1 flex items-center gap-1.5 text-[11px] text-faint">
              <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
              cycling examples
            </span>
          )}
        </div>
      )}

      {phase === "report" ? (
        <div className="space-y-5">
          <div className="grid lg:grid-cols-2 gap-6">
            <div className="space-y-3">
              <DemoSkeleton frames={ex.frames} edges={ex.edges} fps={ex.fps} aspect={ex.aspect} highlight={ex.highlight} />
              <div className="flex items-center justify-between">
                <span className="label">Pose overlay · {ex.name} · {ex.reps} reps · {ex.view} view</span>
                <button className="btn-subtle" onClick={() => setPhase("idle")}>↻ Try another</button>
              </div>
            </div>
            <div className="space-y-4">
              <ScoreHero score={ex.score} grade={ex.grade} metrics={ex.metrics} />
              {analysisMetrics && ex.series.length > 0 && (
                <div className="panel">
                  <div className="panel-head"><span className="panel-title">{ex.series[0].label} over time</span>
                    <span className="text-[11px] text-faint">dashed = rep boundaries</span>
                  </div>
                  <div className="panel-body">
                    <AngleChart metrics={analysisMetrics} seriesKey={ex.series[0].key} currentFrame={-1} height={150} />
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <GroupedFaultList title="Top priorities" faults={ex.priorities} fps={ex.fps} onSeek={() => {}} />
            <div className="panel">
              <div className="panel-head"><span className="panel-title">Per-rep breakdown</span></div>
              <table className="tbl">
                <thead>
                  <tr><th>Rep</th><th>Score</th><th>ROM</th><th>Faults</th></tr>
                </thead>
                <tbody>
                  {ex.rep_breakdown.map((r) => (
                    <tr key={r.index}>
                      <td className="text-muted">{r.index}</td>
                      <td className="font-mono tabular-nums" style={{ color: scoreColor(r.score) }}>{r.score.toFixed(0)}</td>
                      <td className="font-mono tabular-nums">{r.rom.toFixed(0)}°</td>
                      <td className="text-faint">{r.fault_count === 0 ? "clean" : `${r.fault_count}`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <GroupedFaultList
            title="All detected issues"
            faults={ex.fault_groups}
            fps={ex.fps}
            onSeek={() => {}}
            emptyText="No technique faults detected — clean, consistent reps."
          />
          <Strengths items={ex.strengths} />
          <Link href="/signup" className="btn-primary w-full">Analyze your own video</Link>
        </div>
      ) : (
        <div className="grid lg:grid-cols-2 gap-6 items-center">
          <DemoSkeleton frames={ex.frames} edges={ex.edges} fps={ex.fps} aspect={ex.aspect} scanning={phase === "processing"} />
          <div>
            {phase === "idle" ? (
              <>
                <div className="label">{ex.name} · {ex.reps} reps · {ex.view} view</div>
                <h3 className="text-lg font-semibold mt-1">Real pose analysis, from a real set</h3>
                <p className="text-muted text-sm mt-2">
                  Each preview is genuine MediaPipe pose estimation on a filmed set — only the tracked
                  landmarks, no video. Pick an exercise above, then run the analysis to see the full
                  frame-by-frame report.
                </p>
                <button className="btn-primary mt-4" onClick={() => setPhase("processing")}>
                  ▶ Analyze {ex.name}
                </button>
              </>
            ) : (
              <>
                <h3 className="text-lg font-semibold">Analyzing {ex.name}…</h3>
                <ol className="mt-4 space-y-2.5">
                  {STAGES.map((label, i) => {
                    const done = stage > i;
                    const active = stage === i;
                    return (
                      <li key={label} className="flex items-center gap-3 text-sm">
                        <span
                          className={`grid h-5 w-5 place-items-center rounded-full text-[10px] ${
                            done ? "bg-good text-accent-fg" : active ? "bg-accent text-accent-fg" : "bg-surface-2 text-muted"
                          }`}
                        >
                          {done ? "✓" : i + 1}
                        </span>
                        <span className={done || active ? "text-fg" : "text-muted"}>{label}</span>
                      </li>
                    );
                  })}
                </ol>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
