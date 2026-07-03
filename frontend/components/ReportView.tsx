"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { scoreColor } from "@/lib/poseOverlay";
import type { RepFault } from "@/lib/types";
import { AngleChart, RomBars } from "./charts";
import CoachPanel from "./CoachPanel";
import FaultTimeline from "./FaultTimeline";
import GroupedFaultList from "./GroupedFaultList";
import Panel from "./Panel";
import PlayerOverlay from "./PlayerOverlay";
import { Skeleton } from "./ui";

const SEV_DOT: Record<string, string> = {
  severe: "bg-bad",
  moderate: "bg-warn",
  minor: "bg-accent",
};

export default function ReportView({ sessionId }: { sessionId: number }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [frame, setFrame] = useState(0);
  const [showGhost, setShowGhost] = useState(false);
  const [seriesKey, setSeriesKey] = useState<string>("");

  const report = useQuery({ queryKey: ["report", sessionId], queryFn: () => api.report(sessionId) });
  const landmarks = useQuery({ queryKey: ["landmarks", sessionId], queryFn: () => api.landmarks(sessionId) });
  const metrics = useQuery({ queryKey: ["metrics", sessionId], queryFn: () => api.metrics(sessionId) });
  const ghost = useQuery({ queryKey: ["ghost", sessionId], queryFn: () => api.ghost(sessionId) });

  if (report.isLoading || landmarks.isLoading) return <ReportSkeleton />;
  if (report.isError || !report.data) return <p className="text-bad">Failed to load analysis.</p>;

  const r = report.data;
  const lm = landmarks.data;
  const km = r.key_metrics;
  const fps = lm?.fps ?? 30;
  const totalFrames = lm?.frames.length ?? 0;
  const ghostAvailable = ghost.data?.available ?? false;
  const activeSeries = seriesKey || metrics.data?.series[0]?.key || "";

  const faults: RepFault[] = r.reps.flatMap((rep) => rep.faults.map((f) => ({ ...f, rep_index: rep.index })));
  const romData = r.reps.map((rep) => ({ rep: `${rep.index}`, rom: Math.round(rep.rom ?? 0), color: scoreColor(rep.score) }));

  const seek = (t: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = t;
      videoRef.current.pause();
    }
  };

  return (
    <div className="space-y-4">
      {/* Header bar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <Link href="/history" className="btn-subtle px-2 -ml-2">←</Link>
          <div>
            <div className="eyebrow capitalize">{r.session.exercise_key.replace("_", " ")}</div>
            <h1 className="t-h3">Session #{r.session.id}</h1>
          </div>
        </div>
        <div className="flex items-stretch divide-x divide-border rounded-[8px] border border-border overflow-hidden">
          <Metric label="Score" value={r.overall_score.toFixed(0)} color={scoreColor(r.overall_score)} />
          <Metric label="Grade" value={r.grade || "—"} />
          <Metric label="Reps" value={`${r.reps.length}`} />
          {km && <Metric label="View" value={km.view} />}
        </div>
      </div>

      {/* Video + analysis panel */}
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-3">
          {lm && (
            <PlayerOverlay
              sessionId={sessionId}
              landmarks={lm}
              reps={r.reps}
              faults={faults}
              ghost={ghost.data ?? null}
              showGhost={showGhost}
              videoRef={videoRef}
              onFrame={setFrame}
            />
          )}
          <div className="flex items-center justify-between text-[13px]">
            <label className={`inline-flex items-center gap-2 cursor-pointer ${!ghostAvailable ? "opacity-40 pointer-events-none" : ""}`}>
              <input type="checkbox" className="accent-accent" checked={showGhost} onChange={(e) => setShowGhost(e.target.checked)} />
              <span>Ghost Replay</span>
              {ghostAvailable && ghost.data?.source_score != null && (
                <span className="text-faint">best #{ghost.data.source_session_id} · {ghost.data.source_score.toFixed(0)}</span>
              )}
            </label>
            <span className="text-faint tabular-nums">frame {frame} / {Math.max(0, totalFrames - 1)}</span>
          </div>
          {lm && <FaultTimeline reps={r.reps} totalFrames={totalFrames} fps={fps} currentFrame={frame} onSeek={seek} />}
        </div>

        {/* Right analysis rail */}
        <div className="space-y-4">
          {km && (
            <Panel title="Technique">
              <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                <KV label="Range of motion" value={`${km.rom.toFixed(0)}°`} />
                <KV label="Symmetry" value={km.symmetry === null ? "—" : `${km.symmetry.toFixed(1)}°`} sub={km.symmetry_label} />
                <KV label="Tempo" value={`${km.tempo.toFixed(1)}s`} />
                <KV label="Consistency" value={km.consistency ? `${km.consistency.toFixed(0)}%` : "—"} sub={km.consistency_label} />
              </div>
              {r.strengths.length > 0 && (
                <ul className="mt-4 pt-3 border-t border-border space-y-1.5">
                  {r.strengths.map((s) => (
                    <li key={s} className="flex items-center gap-2 text-[13px]"><span className="text-good">✓</span>{s}</li>
                  ))}
                </ul>
              )}
            </Panel>
          )}
          <GroupedFaultList title="Priorities" faults={r.priorities} fps={fps} onSeek={seek} />
          <CoachPanel report={r} />
        </div>
      </div>

      {/* Graphs */}
      <div className="grid lg:grid-cols-2 gap-4">
        <Panel
          title="Joint angle"
          action={
            metrics.data && metrics.data.series.length > 1 ? (
              <div className="flex gap-0.5">
                {metrics.data.series.map((s) => (
                  <button
                    key={s.key}
                    onClick={() => setSeriesKey(s.key)}
                    className={`px-2 h-6 rounded-[6px] text-[12px] transition ${
                      activeSeries === s.key ? "bg-surface-2 text-fg" : "text-muted hover:text-fg"
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            ) : null
          }
        >
          {metrics.data && metrics.data.series.length > 0 ? (
            <AngleChart metrics={metrics.data} seriesKey={activeSeries} currentFrame={frame} onScrub={(f) => seek(f / fps)} />
          ) : (
            <p className="t-caption">No angle series available.</p>
          )}
        </Panel>
        <Panel title="Range of motion — per rep">
          {romData.length > 0 ? <RomBars data={romData} /> : <p className="t-caption">No reps detected.</p>}
        </Panel>
      </div>

      {/* Rep table */}
      <Panel title="Repetitions" bodyClass="">
        <table className="tbl">
          <thead>
            <tr>
              <th>Rep</th>
              <th>Score</th>
              <th>ROM</th>
              <th>Faults</th>
              <th className="w-1/2">Detected</th>
            </tr>
          </thead>
          <tbody>
            {r.reps.map((rep) => (
              <tr key={rep.index} className="hover:bg-surface-2 cursor-pointer" onClick={() => seek(rep.bottom_frame / fps)}>
                <td className="font-medium">{rep.index}</td>
                <td className="font-mono tabular-nums" style={{ color: scoreColor(rep.score) }}>{rep.score.toFixed(0)}</td>
                <td className="font-mono tabular-nums text-muted">{Math.round(rep.rom ?? 0)}°</td>
                <td className="tabular-nums text-muted">{rep.faults.length}</td>
                <td>
                  {rep.faults.length === 0 ? (
                    <span className="text-good text-[13px]">clean</span>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      {rep.faults.map((f, i) => (
                        <span key={i} className="badge border-border text-muted">
                          <span className={`h-1.5 w-1.5 rounded-full ${SEV_DOT[f.severity] ?? "bg-accent"}`} />
                          {f.type.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {r.reps.length === 0 && (
              <tr><td colSpan={5} className="text-muted text-[13px]">No repetitions detected in this clip.</td></tr>
            )}
          </tbody>
        </table>
      </Panel>

      <GroupedFaultList title="All detected issues" faults={r.fault_groups} fps={fps} onSeek={seek} emptyText="No technique faults detected — clean, consistent reps." />
    </div>
  );
}

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="px-3.5 py-1.5 bg-surface">
      <div className="text-[10px] uppercase tracking-[0.06em] text-faint">{label}</div>
      <div className="text-[15px] font-semibold font-mono tabular-nums capitalize" style={color ? { color } : undefined}>{value}</div>
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

function ReportSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-56" />
      <div className="grid lg:grid-cols-3 gap-4">
        <Skeleton className="lg:col-span-2 aspect-video" />
        <div className="space-y-4">
          <Skeleton className="h-40" /><Skeleton className="h-40" />
        </div>
      </div>
      <div className="grid lg:grid-cols-2 gap-4"><Skeleton className="h-48" /><Skeleton className="h-48" /></div>
    </div>
  );
}
