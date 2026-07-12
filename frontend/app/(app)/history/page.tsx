"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import SessionCard from "@/components/SessionCard";
import { useToast } from "@/components/Toaster";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { SessionSummary } from "@/lib/types";

type Tab = "history" | "progress";

export default function HistoryPage() {
  const [tab, setTab] = useState<Tab>("history");
  const [exercise, setExercise] = useState("");
  const { data: exercises } = useQuery({ queryKey: ["exercises"], queryFn: api.exercises });

  // Honour ?exercise= from the ⌘K command palette.
  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("exercise");
    if (fromUrl) setExercise(fromUrl);
  }, []);

  return (
    <div>
      <PageHeader title="History & Progress" subtitle="Every analysis, and how your technique trends over time.">
        <select value={exercise} onChange={(e) => setExercise(e.target.value)} className="input w-auto">
          <option value="">All exercises</option>
          {exercises?.map((e) => (
            <option key={e.key} value={e.key}>{e.name}</option>
          ))}
        </select>
      </PageHeader>

      <div className="inline-flex rounded-lg border border-border p-0.5 mb-6">
        {(["history", "progress"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-md text-sm capitalize transition ${
              tab === t ? "bg-surface-2 text-fg font-medium" : "text-muted hover:text-fg"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "history" ? <HistoryTab exercise={exercise} /> : <ProgressTab exercise={exercise} />}
    </div>
  );
}

function HistoryTab({ exercise }: { exercise: string }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const { data, isLoading } = useQuery({
    queryKey: ["sessions", exercise],
    queryFn: () => api.sessions(exercise || undefined),
  });
  const quota = useQuery({ queryKey: ["quota"], queryFn: api.quota });

  // Deletions touch history, the quota meter, progress and dashboard stats.
  const refresh = () => {
    for (const k of [["sessions"], ["quota"], ["progress"], ["stats"]]) {
      qc.invalidateQueries({ queryKey: k });
    }
  };
  const onError = (e: unknown) => toast(e instanceof ApiError ? e.message : "Delete failed", "error");

  const deleteVideo = useMutation({ mutationFn: (id: number) => api.deleteVideo(id), onSuccess: refresh, onError });
  const deleteSession = useMutation({ mutationFn: (id: number) => api.deleteSession(id), onSuccess: refresh, onError });
  const busy = deleteVideo.isPending || deleteSession.isPending;

  const handleDeleteVideo = (s: SessionSummary) => {
    if (window.confirm(`Delete the video for session #${s.id}? The analysis and Ghost Replay are kept (drops to a ¼ slot).`))
      deleteVideo.mutate(s.id);
  };
  const handleDeleteSession = (s: SessionSummary) => {
    if (window.confirm(`Permanently delete session #${s.id}? This removes the video and its analysis.`))
      deleteSession.mutate(s.id);
  };

  if (isLoading)
    return (
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
      </div>
    );
  if (!data || data.length === 0)
    return (
      <EmptyState
        title="Your biomechanics history starts here"
        description="Upload your first set to begin tracking movement quality — every rep scored, every fault timed, session over session."
        action={{ label: "Upload a set", href: "/upload" }}
      />
    );

  return (
    <div className="space-y-4">
      {quota.data && <QuotaMeter used={quota.data.used} limit={quota.data.limit} analysisOnly={quota.data.analysis_only_count} />}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {data.map((s) => (
          <SessionCard
            key={s.id}
            s={s}
            busy={busy}
            onDeleteVideo={handleDeleteVideo}
            onDeleteSession={handleDeleteSession}
          />
        ))}
      </div>
    </div>
  );
}

function QuotaMeter({ used, limit, analysisOnly }: { used: number; limit: number; analysisOnly: number }) {
  const pct = Math.min(100, Math.round((used / limit) * 100));
  const full = used + 1 > limit;
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-medium">History storage</span>
        <span className="font-mono tabular-nums text-muted">
          {used.toFixed(2).replace(/\.00$/, "")} / {limit} slots
        </span>
      </div>
      <div className="mt-2 h-2 rounded-full bg-surface-2 overflow-hidden">
        <div className={`h-full ${full ? "bg-bad" : "bg-accent"} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-muted mt-2">
        Each video uses 1 slot; deleting a video but keeping its analysis (incl. Ghost Replay) uses ¼ slot.
        {analysisOnly > 0 && ` ${analysisOnly} analysis-only kept.`}
        {full && " Your history is full — delete a session or a few videos to upload more."}
      </p>
    </div>
  );
}

function ProgressTab({ exercise }: { exercise: string }) {
  const { data } = useQuery({
    queryKey: ["progress", exercise],
    queryFn: () => api.progress(exercise || undefined),
  });
  const c = useThemeColors();
  const chart = data?.map((p, i) => ({ name: `#${p.session_id}`, idx: i + 1, avg: p.avg_score, best: p.best_score })) ?? [];

  return (
    <div className="card p-6">
      {chart.length === 0 ? (
        <EmptyState
          title="Your progress chart starts here"
          description="Analyze a few clips of the same lift and physIQal will chart how your technique and best rep trend over time."
          action={{ label: "Upload a set", href: "/upload" }}
        />
      ) : (
        <ResponsiveContainer width="100%" height={340}>
          <LineChart data={chart} margin={{ top: 10, right: 16, bottom: 0, left: -12 }}>
            <CartesianGrid stroke={c.grid} vertical={false} />
            <XAxis dataKey="name" stroke={c.axis} fontSize={12} tickLine={false} axisLine={{ stroke: c.grid }} />
            <YAxis domain={[0, 100]} stroke={c.axis} fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={{ background: c.surface, border: `1px solid ${c.grid}`, borderRadius: 8, fontSize: 12 }} labelStyle={{ color: c.axis }} itemStyle={{ color: c.fg }} />
            <Line type="monotone" dataKey="avg" name="Technique" stroke={c.accent} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
            <Line type="monotone" dataKey="best" name="Best rep" stroke={c.good} strokeWidth={2} strokeDasharray="4 3" dot={{ r: 2 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

// Reads the active design tokens so charts theme with light/dark like the rest.
function useThemeColors() {
  const [c, setC] = useState({
    grid: "rgb(42 42 42)", axis: "rgb(110 110 110)", fg: "rgb(237 237 237)",
    surface: "rgb(22 22 22)", accent: "rgb(235 235 235)", good: "rgb(61 191 138)",
  });
  useEffect(() => {
    const s = getComputedStyle(document.documentElement);
    const v = (n: string) => `rgb(${s.getPropertyValue(n).trim() || "128 128 128"})`;
    setC({ grid: v("--border"), axis: v("--faint"), fg: v("--fg"), surface: v("--surface"), accent: v("--accent"), good: v("--good") });
  }, []);
  return c;
}
