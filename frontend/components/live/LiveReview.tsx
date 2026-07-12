"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { scoreColor } from "@/lib/poseOverlay";
import type { ProgressPoint, RepFault } from "@/lib/types";
import { RomBars } from "../charts";
import CoachPanel from "../CoachPanel";
import FaultDeck from "../FaultDeck";
import InsightCards from "../InsightCards";
import Panel from "../Panel";
import { Skeleton } from "../ui";
import LivePlayer from "./LivePlayer";

function fmtDuration(s: number | null): string {
  if (!s) return "—";
  const m = Math.floor(s / 60);
  const sec = String(Math.round(s % 60)).padStart(2, "0");
  return `${m}:${sec}`;
}

function StatBox({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="px-3.5 py-1.5 bg-surface">
      <div className="text-[10px] uppercase tracking-[0.06em] text-faint">{label}</div>
      <div className="text-[15px] font-semibold font-mono tabular-nums capitalize" style={color ? { color } : undefined}>
        {value}
      </div>
    </div>
  );
}

/** Change vs the immediately-preceding completed session of this exercise. */
function progressDelta(series: ProgressPoint[] | undefined, sessionId: number): number | null {
  if (!series || series.length < 2) return null;
  const idx = series.findIndex((p) => p.session_id === sessionId);
  if (idx <= 0) return null;
  return series[idx].avg_score - series[idx - 1].avg_score;
}

export default function LiveReview({ sessionId }: { sessionId: number }) {
  const [showGhost, setShowGhost] = useState(false);

  const report = useQuery({ queryKey: ["report", sessionId], queryFn: () => api.report(sessionId) });
  const landmarks = useQuery({ queryKey: ["landmarks", sessionId], queryFn: () => api.landmarks(sessionId) });
  const ghost = useQuery({ queryKey: ["ghost", sessionId], queryFn: () => api.ghost(sessionId) });
  const progress = useQuery({
    queryKey: ["progress", report.data?.session.exercise_key],
    queryFn: () => api.progress(report.data!.session.exercise_key),
    enabled: !!report.data,
  });

  if (report.isLoading) return <ReviewSkeleton />;
  if (report.isError || !report.data) return <p className="text-bad">Failed to load session review.</p>;

  const r = report.data;
  const lm = landmarks.data;
  const fps = lm?.fps ?? 15;
  const ghostAvailable = ghost.data?.available ?? false;

  const faults: RepFault[] = r.reps.flatMap((rep) => rep.faults.map((f) => ({ ...f, rep_index: rep.index })));
  const romData = r.reps.map((rep) => ({ rep: `${rep.index}`, rom: Math.round(rep.rom ?? 0), color: scoreColor(rep.score) }));

  const sorted = [...r.reps].sort((a, b) => b.score - a.score);
  const bestRep = sorted[0] ?? null;
  const worstRep = sorted.length > 1 ? sorted[sorted.length - 1] : null;

  const delta = progressDelta(progress.data, sessionId);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <Link href="/history" className="btn-subtle px-2 -ml-2">←</Link>
          <div>
            <div className="eyebrow capitalize">
              Live · {r.session.exercise_key.replace(/_/g, " ")}
            </div>
            <h1 className="t-h3">Session review</h1>
          </div>
        </div>
        <div className="flex items-stretch divide-x divide-border rounded-[8px] border border-border overflow-hidden flex-wrap">
          <StatBox label="Score" value={r.overall_score.toFixed(0)} color={scoreColor(r.overall_score)} />
          <StatBox label="Grade" value={r.grade || "—"} />
          <StatBox label="Reps" value={`${r.reps.length}`} />
          <StatBox label="Sets" value={`${r.sets.length || 1}`} />
          <StatBox label="Duration" value={fmtDuration(r.duration_s)} />
          <StatBox label="Time under tension" value={fmtDuration(r.time_under_tension)} />
        </div>
      </div>

      {r.insights.length > 0 && <InsightCards insights={r.insights} />}

      <div className="grid lg:grid-cols-3 gap-4">
        {/* Left: skeleton playback */}
        <div className="lg:col-span-2 space-y-3">
          {lm ? (
            <LivePlayer landmarks={lm} reps={r.reps} faults={faults} ghost={ghost.data ?? null} showGhost={showGhost} />
          ) : (
            <Skeleton className="aspect-video" />
          )}
          <label className={`inline-flex items-center gap-2 text-[13px] cursor-pointer ${!ghostAvailable ? "opacity-40 pointer-events-none" : ""}`}>
            <input type="checkbox" className="accent-accent" checked={showGhost} onChange={(e) => setShowGhost(e.target.checked)} />
            <span>Ghost Replay</span>
            {ghostAvailable && ghost.data?.source_score != null && (
              <span className="text-faint">best #{ghost.data.source_session_id} · {ghost.data.source_score.toFixed(0)}</span>
            )}
          </label>

          {/* Best & worst rep */}
          <div className="grid sm:grid-cols-2 gap-3">
            <RepCallout label="Best rep" rep={bestRep} />
            <RepCallout label="Needs work" rep={worstRep} />
          </div>
        </div>

        {/* Right rail */}
        <div className="space-y-4">
          {r.key_metrics && (
            <Panel title="Technique">
              <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                <KV label="Range of motion" value={`${r.key_metrics.rom.toFixed(0)}°`} />
                <KV label="Symmetry" value={r.key_metrics.symmetry === null ? "—" : `${r.key_metrics.symmetry.toFixed(1)}°`} sub={r.key_metrics.symmetry_label} />
                <KV label="Tempo" value={`${r.key_metrics.tempo.toFixed(1)}s`} />
                <KV label="Consistency" value={r.key_metrics.consistency ? `${r.key_metrics.consistency.toFixed(0)}%` : "—"} sub={r.key_metrics.consistency_label} />
              </div>
              {delta !== null && (
                <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-[13px]">
                  <span className="text-muted">vs previous session</span>
                  <span className={`font-mono tabular-nums ${delta >= 0 ? "text-good" : "text-bad"}`}>
                    {delta >= 0 ? "+" : ""}{delta.toFixed(1)}
                  </span>
                </div>
              )}
              {r.strengths.length > 0 && (
                <ul className="mt-3 pt-3 border-t border-border space-y-1.5">
                  {r.strengths.map((s) => (
                    <li key={s} className="flex items-center gap-2 text-[13px]"><span className="text-good">✓</span>{s}</li>
                  ))}
                </ul>
              )}
            </Panel>
          )}
          <FaultDeck
            title="Coaching priorities"
            tabs={[{ key: "priorities", label: "Priorities", faults: r.priorities, emptyText: "No priority issues — nice work." }]}
            fps={fps}
          />
          <CoachPanel report={r} />
        </div>
      </div>

      {/* Per-set breakdown */}
      {r.sets.length > 0 && (
        <Panel title="Sets" bodyClass="">
          <table className="tbl">
            <thead>
              <tr><th>Set</th><th>Reps</th><th>Avg score</th><th>Duration</th></tr>
            </thead>
            <tbody>
              {r.sets.map((s) => (
                <tr key={s.set_index}>
                  <td className="font-medium">{s.set_index}</td>
                  <td className="font-mono tabular-nums text-muted">{s.rep_count}</td>
                  <td className="font-mono tabular-nums" style={{ color: scoreColor(s.avg_score) }}>{s.avg_score.toFixed(0)}</td>
                  <td className="font-mono tabular-nums text-muted">{fmtDuration(s.duration_s)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}

      {/* ROM per rep */}
      <Panel title="Range of motion — per rep">
        {romData.length > 0 ? <RomBars data={romData} /> : <p className="t-caption">No reps detected.</p>}
      </Panel>

      <FaultDeck
        title="Detected issues"
        tabs={[
          { key: "priorities", label: "Priorities", faults: r.priorities, emptyText: "No priority issues — nice work." },
          { key: "all", label: "All issues", faults: r.fault_groups, emptyText: "No technique faults detected — clean, consistent reps." },
        ]}
        fps={fps}
      />
    </div>
  );
}

function RepCallout({ label, rep }: { label: string; rep: { index: number; score: number; faults: unknown[] } | null }) {
  if (!rep) return <div className="card p-4 text-[13px] text-muted">{label}: —</div>;
  return (
    <div className="card p-4">
      <div className="eyebrow mb-1">{label}</div>
      <div className="flex items-baseline justify-between">
        <span className="text-sm">Rep {rep.index}</span>
        <span className="font-mono text-xl font-semibold tabular-nums" style={{ color: scoreColor(rep.score) }}>
          {rep.score.toFixed(0)}
        </span>
      </div>
      <div className="text-[12px] text-faint mt-1">{rep.faults.length} fault{rep.faults.length === 1 ? "" : "s"}</div>
    </div>
  );
}

function KV({ label, value, sub }: { label: string; value: string; sub?: string }) {
  const subColor = sub === "good" ? "text-good" : sub === "poor" ? "text-bad" : sub === "fair" ? "text-warn" : "text-faint";
  return (
    <div>
      <div className="text-[11px] text-faint">{label}</div>
      <div className="text-[15px] font-mono tabular-nums mt-0.5">{value} {sub && <span className={`text-[11px] ${subColor}`}>{sub}</span>}</div>
    </div>
  );
}

function ReviewSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-56" />
      <div className="grid lg:grid-cols-3 gap-4">
        <Skeleton className="lg:col-span-2 aspect-video" />
        <div className="space-y-4"><Skeleton className="h-40" /><Skeleton className="h-40" /></div>
      </div>
    </div>
  );
}
