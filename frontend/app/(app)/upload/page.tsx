"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import Dropzone from "@/components/Dropzone";
import GuidePopup from "@/components/GuidePopup";
import { useToast } from "@/components/Toaster";
import { PageHeader } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { allGuides } from "@/lib/guides";
import { takePendingFile } from "@/lib/pendingUpload";
import { markUploadDone, useUploadGuide } from "@/lib/uploadGuide";

export default function UploadPage() {
  const router = useRouter();
  const { user } = useAuth();
  const { toast } = useToast();
  const { data: exercises } = useQuery({ queryKey: ["exercises"], queryFn: api.exercises });

  const [exerciseKey, setExerciseKey] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  // Whether the user has actively picked an exercise (vs. the pre-selected
  // default). During the first-runs guide, the filming tips are "revealed" on
  // that first click, matching the guide's wording.
  const [touched, setTouched] = useState(false);
  const [guideDismissed, setGuideDismissed] = useState(false);
  const { active: guideActive } = useUploadGuide();

  // Default exercise = first of the user's preferred, else first available.
  const preferred = user?.prefs?.exercises ?? [];
  const selected = exerciseKey || preferred[0] || exercises?.[0]?.key || "";
  const selectedExercise = exercises?.find((e) => e.key === selected);
  const selectedName = selectedExercise?.name ?? "exercise";
  const filming = selectedExercise?.filming ?? [];
  // Reveal the filming tips once an exercise is chosen (always, once the guide is
  // done — otherwise only after the first click so the guide can point it out).
  const showFilming = filming.length > 0 && (touched || !guideActive);

  // Pick up a file dropped on the dashboard, and an exercise passed via ?exercise=
  // (e.g. from the ⌘K command palette).
  useEffect(() => {
    const pending = takePendingFile();
    if (pending) setFile(pending);
    const fromUrl = new URLSearchParams(window.location.search).get("exercise");
    if (fromUrl) setExerciseKey(fromUrl);
  }, []);

  async function submit() {
    if (!file || !selected) return;
    setBusy(true);
    try {
      // Analysis now runs synchronously on the backend: this request blocks
      // until the full report is ready, then we go straight to it (no polling).
      const session = await api.upload(selected, file);
      markUploadDone();
      // Pop-up confirmation — persists across the navigation to the report.
      toast(`${selectedName} analysis complete — opening your report.`, "success");
      router.replace(`/sessions/${session.id}`);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Analysis failed", "error");
      setBusy(false);
    }
  }

  // While the analysis request is in flight, show a waiting screen with an
  // estimate instead of a queued-job poller.
  if (busy) return <Analyzing exerciseName={selectedName} exerciseKey={selected} />;

  return (
    <div className="max-w-2xl">
      <PageHeader title="New analysis" subtitle="Upload a clip and physIQal scores every rep against biomechanics rules." />

      <div className="card p-5 sm:p-6 space-y-6">
        <div>
          <div className="label mb-2">Exercise</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {exercises?.map((e) => (
              <button
                key={e.key}
                onClick={() => {
                  setExerciseKey(e.key);
                  setTouched(true);
                }}
                className={`px-3 py-2 rounded-lg border text-sm text-left transition ${
                  selected === e.key ? "border-accent bg-accent/10 text-fg" : "border-border text-muted hover:text-fg hover:bg-surface-2"
                }`}
              >
                {e.name}
              </button>
            ))}
          </div>

          {/* Per-exercise filming pointers. */}
          {showFilming && (
            <div className="mt-3 rounded-xl border border-accent/40 bg-accent/[0.04] p-3.5 animate-fade-in">
              <div className="label mb-2">How to film your {selectedName}</div>
              <ul className="space-y-1.5">
                {filming.map((tip) => (
                  <li key={tip} className="flex items-start gap-2 text-[13px]">
                    <span className="text-accent mt-px">•</span>
                    <span>{tip}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div>
          <div className="label mb-2">Video</div>
          {file ? (
            <div className="flex items-center justify-between rounded-xl border border-border p-4">
              <div className="flex items-center gap-3 min-w-0">
                <span className="grid h-9 w-9 place-items-center rounded-lg bg-accent/10 text-accent shrink-0">▶</span>
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{file.name}</div>
                  <div className="label">{(file.size / 1_000_000).toFixed(1)} MB</div>
                </div>
              </div>
              <button className="btn-subtle" onClick={() => setFile(null)}>Change</button>
            </div>
          ) : (
            <Dropzone onFile={setFile} />
          )}
        </div>

        <button className="btn-primary w-full" disabled={!file || busy} onClick={submit}>
          {busy ? "Uploading…" : "Run analysis"}
        </button>
        <p className="text-xs text-muted text-center">
          Film side-on for squats/deadlifts and front-on for curls/raises for the most reliable results.
        </p>
      </div>

      {/* First-runs guide pop-up — advances as the athlete picks an exercise then a file. */}
      {guideActive && !guideDismissed && !file && (
        touched ? (
          <GuidePopup
            step={2}
            total={3}
            title="Upload your clip"
            onDismiss={() => setGuideDismissed(true)}
          >
            Drag &amp; drop or click to upload a video of your set.
          </GuidePopup>
        ) : (
          <GuidePopup
            step={1}
            total={3}
            title="Pick your exercise"
            onDismiss={() => setGuideDismissed(true)}
          >
            Click an exercise to reveal guidelines on how to film your video.
          </GuidePopup>
        )
      )}
    </div>
  );
}

const PREPARING = "Preparing the analysis engine…";
const PREPARING_NOTE = "This only happens the first time after the server starts.";
const CORE_STAGES = [
  "Uploading video",
  "Detecting body landmarks",
  "Tracking movement",
  "Evaluating technique",
  "Generating coaching feedback",
] as const;

// Shown while the synchronous analysis request is in flight. Since the request
// blocks until the whole report is ready, we can't stream true per-stage progress
// from it — but we DO detect a real cold start (engine not yet warm) and walk the
// user through the actual pipeline stages on a calibrated timeline, holding on the
// last stage until the response arrives and the page navigates away.
function Analyzing({ exerciseName, exerciseKey }: { exerciseName: string; exerciseKey?: string }) {
  const [elapsed, setElapsed] = useState(0);
  // Cold start = the pose engine hasn't warmed up since the server booted. Ask the
  // backend once; on unknown/failure assume warm so we never falsely claim cold.
  const [cold, setCold] = useState(false);

  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    let alive = true;
    api
      .health()
      .then((h) => {
        if (alive) setCold(!h.pose_warm);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  // Stage timeline. A cold start leads with the engine-warming status and stretches
  // the pose stages (model load); the final stage's duration is effectively infinite
  // so it holds until the request resolves.
  const stages: { label: string; note?: string; secs: number }[] = cold
    ? [
        { label: PREPARING, note: PREPARING_NOTE, secs: 8 },
        { label: CORE_STAGES[0], secs: 3 },
        { label: CORE_STAGES[1], secs: 9 },
        { label: CORE_STAGES[2], secs: 9 },
        { label: CORE_STAGES[3], secs: 5 },
        { label: CORE_STAGES[4], secs: 9000 },
      ]
    : [
        { label: CORE_STAGES[0], secs: 3 },
        { label: CORE_STAGES[1], secs: 7 },
        { label: CORE_STAGES[2], secs: 8 },
        { label: CORE_STAGES[3], secs: 5 },
        { label: CORE_STAGES[4], secs: 9000 },
      ];

  // Current stage from elapsed seconds (never past the last).
  let acc = 0;
  let idx = stages.length - 1;
  for (let i = 0; i < stages.length; i++) {
    acc += stages[i].secs;
    if (elapsed < acc) {
      idx = i;
      break;
    }
  }
  const active = stages[idx];
  const scheduled = stages.slice(0, -1).reduce((s, st) => s + st.secs, 0);
  const pct = scheduled > 0 ? Math.min(96, (elapsed / scheduled) * 100) : 0;
  const checklist = stages.filter((s) => s.label !== PREPARING);

  // Surface a few technique guides to read while the analysis runs — the one that
  // matches this exercise first. Opened in a new tab so the analysis keeps running.
  const guides = allGuides();
  const suggested = [
    ...guides.filter((g) => g.exerciseKey === exerciseKey),
    ...guides.filter((g) => g.exerciseKey !== exerciseKey),
  ].slice(0, 4);

  return (
    <div className="max-w-lg mx-auto">
      <div className="card p-8">
        <div className="flex items-center gap-3 mb-1">
          <span className="relative grid h-9 w-9 place-items-center">
            <span className="absolute inset-0 rounded-full border-2 border-border" />
            <span className="absolute inset-0 rounded-full border-2 border-transparent border-t-accent animate-spin" />
          </span>
          <div className="min-w-0">
            <div key={active.label} className="text-sm font-medium truncate animate-fade-in">
              {active.label}
            </div>
            <div className="label mt-0.5">Analyzing your {exerciseName} · {elapsed}s</div>
          </div>
        </div>
        <p className="text-muted text-xs mb-5 min-h-[1rem]">{active.note ?? ""}</p>

        {/* Progress reflects the calibrated stage timeline; holds near the end. */}
        <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden mb-5">
          <div
            className="h-full bg-accent transition-all duration-700 ease-out"
            style={{ width: `${Math.max(6, pct)}%` }}
          />
        </div>

        {/* Stage checklist — the real pipeline phases, in order. */}
        <ol className="space-y-2.5">
          {checklist.map((s) => {
            const fullIdx = stages.indexOf(s);
            const done = idx > fullIdx;
            const on = idx === fullIdx;
            return (
              <li key={s.label} className="flex items-center gap-3 text-[13px]">
                <span
                  className={`grid h-5 w-5 place-items-center rounded-full text-[10px] transition ${
                    done ? "bg-good text-accent-fg" : on ? "bg-accent text-accent-fg" : "bg-surface-2 text-muted"
                  }`}
                >
                  {done ? "✓" : on ? <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" /> : ""}
                </span>
                <span className={done || on ? "text-fg" : "text-muted"}>{s.label}</span>
              </li>
            );
          })}
        </ol>

        <p className="text-muted text-xs mt-5">
          Keep this tab open — your report opens automatically when it&apos;s done.
        </p>

        {/* While-you-wait: technique guides (open in a new tab so analysis keeps running). */}
        <div className="mt-6 border-t border-border pt-6">
          <h2 className="text-sm font-medium">
            While you wait — brush up on your form
          </h2>
          <p className="text-muted text-xs mt-1">
            Premium technique guides, opened in a new tab so your analysis keeps running.
          </p>
          <div className="mt-3 grid gap-2">
            {suggested.map((g) => (
              <a
                key={g.slug}
                href={`/guides/${g.slug}`}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-center gap-3 rounded-xl border border-border p-3 transition hover:border-accent hover:bg-surface-2/50"
              >
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent/10 text-accent text-[13px]">
                  {g.exerciseKey === exerciseKey ? "★" : "›"}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{g.name}</span>
                  <span className="block truncate text-[11px] text-muted">{g.category}</span>
                </span>
                <span className="text-faint transition group-hover:text-accent">↗</span>
              </a>
            ))}
          </div>
          <a href="/guides" target="_blank" rel="noopener noreferrer" className="mt-3 inline-block text-xs text-accent hover:underline">
            Browse all exercise guides →
          </a>
        </div>
      </div>
    </div>
  );
}
