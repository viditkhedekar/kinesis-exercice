"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const STAGES: [string, string][] = [
  ["pose", "Pose estimation"],
  ["biomechanics", "Joint angles & velocity"],
  ["reps", "Rep detection"],
  ["rules", "Fault analysis & scoring"],
  ["coaching", "AI coaching"],
  ["progress", "Progress tracking"],
];

// Reassuring messages that cycle so the screen always feels alive, even while a
// stage takes a while (first run loads the pose model).
const MESSAGES = [
  "Decoding video frames…",
  "Warming up the pose model…",
  "Locating 33 body landmarks…",
  "Tracking landmarks frame by frame…",
  "Measuring joint angles and ranges of motion…",
  "Estimating the camera angle…",
  "Segmenting the set into repetitions…",
  "Tracking each repetition…",
  "Scoring range of motion per rep…",
  "Checking symmetry between left and right…",
  "Grading tempo and consistency…",
  "Comparing against coaching thresholds…",
  "Grouping recurring faults…",
  "Writing your coaching notes…",
  "Almost there — assembling your report…",
];

export default function ProcessingPage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const router = useRouter();
  const [msg, setMsg] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  const { data, isError } = useQuery({
    queryKey: ["status", id],
    queryFn: () => api.status(id),
    refetchInterval: (q) => (["done", "failed"].includes(q.state.data?.stage ?? "") ? false : 900),
  });

  // Rotate the loading message + count elapsed seconds.
  useEffect(() => {
    const m = setInterval(() => setMsg((i) => (i + 1) % MESSAGES.length), 2200);
    const e = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => {
      clearInterval(m);
      clearInterval(e);
    };
  }, []);

  useEffect(() => {
    if (data?.stage === "done") {
      const t = setTimeout(() => router.replace(`/sessions/${id}`), 500);
      return () => clearTimeout(t);
    }
  }, [data?.stage, id, router]);

  const stage = data?.stage;
  const failed = stage === "failed";
  const queued = !stage || stage === "queued" || stage === "uploaded";
  const currentIdx = STAGES.findIndex(([k]) => k === stage);
  const progress = Math.round((data?.progress ?? 0) * 100);

  if (failed) {
    return (
      <div className="max-w-lg mx-auto">
        <div className="card p-8 text-center">
          <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-xl bg-bad/10 text-bad">!</div>
          <h1 className="text-lg font-semibold">Analysis failed</h1>
          <p className="text-muted text-sm mt-2">{data?.error ?? "Something went wrong while analyzing this clip."}</p>
          <p className="text-muted text-xs mt-3">
            Tip: use a clear clip of a single person, filmed side-on for squats/deadlifts and front-on for curls/raises.
          </p>
          <div className="flex items-center justify-center gap-2 mt-5">
            <Link href="/upload" className="btn-primary">Try another clip</Link>
            <Link href="/dashboard" className="btn-ghost">Dashboard</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto">
      <div className="card p-8">
        {/* Live status */}
        <div className="flex items-center gap-3 mb-6">
          <span className="relative grid h-9 w-9 place-items-center">
            <span className="absolute inset-0 rounded-full border-2 border-border" />
            <span className="absolute inset-0 rounded-full border-2 border-transparent border-t-accent animate-spin" />
          </span>
          <div className="min-w-0">
            <div className="text-sm font-medium truncate animate-fade-in" key={msg}>
              {MESSAGES[msg]}
            </div>
            <div className="label mt-0.5">
              {queued ? "Queued" : "Analyzing"} · {elapsed}s elapsed
            </div>
          </div>
        </div>

        {/* Progress */}
        <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden mb-6">
          {queued ? (
            <div className="h-full w-1/3 bg-accent/60 skeleton" />
          ) : (
            <div className="h-full bg-accent transition-all duration-500" style={{ width: `${Math.max(8, progress)}%` }} />
          )}
        </div>

        {/* Stage checklist */}
        <ol className="space-y-2.5">
          {STAGES.map(([key, label], i) => {
            const done = currentIdx > i || stage === "done";
            const active = currentIdx === i;
            return (
              <li key={key} className="flex items-center gap-3 text-sm">
                <span
                  className={`grid h-5 w-5 place-items-center rounded-full text-[10px] transition ${
                    done ? "bg-good text-accent-fg" : active ? "bg-accent text-accent-fg" : "bg-surface-2 text-muted"
                  }`}
                >
                  {done ? "✓" : active ? <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" /> : i + 1}
                </span>
                <span className={done || active ? "text-fg" : "text-muted"}>{label}</span>
              </li>
            );
          })}
        </ol>

        {isError && (
          <p className="text-warn text-xs mt-5">Reconnecting to the analysis service…</p>
        )}
        {queued && elapsed > 12 && (
          <p className="text-muted text-xs mt-5">
            Still queued — the first analysis after startup can take a little longer while the model loads.
          </p>
        )}
      </div>
    </div>
  );
}
