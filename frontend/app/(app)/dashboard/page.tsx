"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { Sparkline, TrendArea } from "@/components/charts";
import Panel from "@/components/Panel";
import { EmptyState, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { scoreColor } from "@/lib/poseOverlay";

const human = (s: string) => s.replace(/_/g, " ");

export default function DashboardPage() {
  const { user } = useAuth();
  const { data: stats, isLoading } = useQuery({ queryKey: ["stats"], queryFn: api.stats });
  const [q, setQ] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const recent = useMemo(
    () => (stats?.recent ?? []).filter((s) => s.exercise_name.toLowerCase().includes(q.toLowerCase())),
    [stats, q],
  );
  const trend = (stats?.trend ?? []).map((p, i) => ({ i, v: p.score }));
  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  return (
    <div className="space-y-4">
      {/* Top bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="mr-auto">
          <div className="eyebrow">{greet}</div>
          <h1 className="t-h3">{user?.name?.split(" ")[0] || "Athlete"}</h1>
        </div>
        <div className="relative">
          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-faint text-sm">⌕</span>
          <input
            ref={searchRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search analyses"
            className="input h-8 w-48 pl-7 text-[13px]"
          />
          <span className="kbd absolute right-2 top-1/2 -translate-y-1/2 hidden sm:flex">/</span>
        </div>
        <Link href="/upload" className="btn-primary">Upload</Link>
        <div className="hidden sm:flex items-center gap-2 pl-2 border-l border-border">
          <span className="grid h-7 w-7 place-items-center rounded-full bg-surface-2 text-[13px] font-medium">
            {(user?.name || "A").charAt(0).toUpperCase()}
          </span>
        </div>
      </div>

      {isLoading ? (
        <div className="grid lg:grid-cols-[7fr_3fr] gap-4">
          <div className="space-y-4"><Skeleton className="h-56" /><Skeleton className="h-48" /></div>
          <div className="space-y-4"><Skeleton className="h-32" /><Skeleton className="h-40" /></div>
        </div>
      ) : !stats || stats.total_sessions === 0 ? (
        <EmptyState title="No analyses yet" description="Upload your first lift to start building technique history and trends." action={{ label: "Upload a clip", href: "/upload" }} />
      ) : (
        <div className="grid lg:grid-cols-[7fr_3fr] gap-4 items-start">
          {/* Left 70% */}
          <div className="space-y-4">
            <Panel
              title="Progress"
              action={<span className="t-caption tabular-nums">avg {stats.avg_score.toFixed(0)} · {stats.completed} sessions</span>}
            >
              {trend.length >= 2 ? <TrendArea data={trend} /> : <p className="t-caption">Analyze a few sessions to see your trend.</p>}
            </Panel>

            <Panel title="Recent analyses" bodyClass="">
              <table className="tbl">
                <thead><tr><th>Exercise</th><th>Date</th><th>Status</th><th className="text-right pr-3">Score</th></tr></thead>
                <tbody>
                  {recent.map((s) => (
                    <tr key={s.session_id} className="hover:bg-surface-2">
                      <td>
                        <Link href={s.status === "complete" ? `/sessions/${s.session_id}` : `/sessions/${s.session_id}/processing`} className="font-medium capitalize hover:text-accent">
                          {s.exercise_name}
                        </Link>
                      </td>
                      <td className="text-muted tabular-nums">{new Date(s.created_at).toLocaleDateString()}</td>
                      <td className="text-muted capitalize">{s.status}</td>
                      <td className="text-right pr-3 font-mono tabular-nums" style={{ color: s.status === "complete" && s.overall_score != null ? scoreColor(s.overall_score) : undefined }}>
                        {s.status !== "complete" ? "—" : s.overall_score != null ? s.overall_score.toFixed(0) : "--"}
                      </td>
                    </tr>
                  ))}
                  {recent.length === 0 && <tr><td colSpan={4} className="text-muted text-[13px]">No matches.</td></tr>}
                </tbody>
              </table>
            </Panel>

            <Panel title="Exercise breakdown" bodyClass="">
              <table className="tbl">
                <tbody>
                  {Object.entries(stats.exercise_breakdown).sort((a, b) => b[1] - a[1]).map(([k, v]) => {
                    const max = Math.max(...Object.values(stats.exercise_breakdown));
                    return (
                      <tr key={k}>
                        <td className="capitalize w-40">{human(k)}</td>
                        <td>
                          <div className="h-1.5 rounded bg-surface-2 overflow-hidden"><div className="h-full bg-accent/70" style={{ width: `${(v / max) * 100}%` }} /></div>
                        </td>
                        <td className="text-right pr-3 tabular-nums text-muted w-10">{v}</td>
                      </tr>
                    );
                  })}
                  {Object.keys(stats.exercise_breakdown).length === 0 && <tr><td className="text-muted text-[13px]">No completed sessions.</td></tr>}
                </tbody>
              </table>
            </Panel>
          </div>

          {/* Right 30% */}
          <div className="space-y-4">
            <Panel title="Technique summary">
              <div className="flex items-end justify-between">
                <div>
                  <div className="text-[32px] font-semibold font-mono tabular-nums leading-none" style={{ color: scoreColor(stats.avg_score) }}>
                    {stats.avg_score.toFixed(0)}
                  </div>
                  <div className="t-caption mt-1">avg technique score</div>
                </div>
                <div className="w-28"><Sparkline data={(stats.trend.length ? stats.trend : [{ score: 0 }, { score: 0 }]).map((p) => p.score)} /></div>
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4 pt-3 border-t border-border">
                <div><div className="text-[11px] text-faint">This week</div><div className="font-mono tabular-nums mt-0.5">{stats.week_sessions} <span className="text-faint text-[12px]">sessions</span></div></div>
                <div><div className="text-[11px] text-faint">Week avg</div><div className="font-mono tabular-nums mt-0.5">{stats.week_avg ? stats.week_avg.toFixed(0) : "—"}</div></div>
              </div>
            </Panel>

            <Panel title="Most common faults" bodyClass="panel-body space-y-2.5">
              {stats.common_faults.length === 0 ? (
                <p className="text-good text-[13px]">No faults logged — clean work.</p>
              ) : (
                stats.common_faults.map((f) => {
                  const max = stats.common_faults[0].count;
                  return (
                    <div key={f.type}>
                      <div className="flex justify-between text-[13px] mb-1"><span className="capitalize">{human(f.type)}</span><span className="text-faint tabular-nums">{f.count}</span></div>
                      <div className="h-1 rounded bg-surface-2 overflow-hidden"><div className="h-full bg-muted/60" style={{ width: `${(f.count / max) * 100}%` }} /></div>
                    </div>
                  );
                })
              )}
            </Panel>

            <Panel title="Personal bests" bodyClass="">
              <table className="tbl">
                <tbody>
                  {stats.personal_bests.map((b) => (
                    <tr key={b.exercise_key}>
                      <td className="capitalize">{b.exercise_name}</td>
                      <td className="text-right pr-3 font-mono tabular-nums" style={{ color: scoreColor(b.best_score) }}>{b.best_score.toFixed(0)}</td>
                    </tr>
                  ))}
                  {stats.personal_bests.length === 0 && <tr><td className="text-muted text-[13px]">—</td></tr>}
                </tbody>
              </table>
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}
