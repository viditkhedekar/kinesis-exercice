"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import Dropzone from "@/components/Dropzone";
import { useToast } from "@/components/Toaster";
import { PageHeader } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { takePendingFile } from "@/lib/pendingUpload";

export default function UploadPage() {
  const router = useRouter();
  const { user } = useAuth();
  const { toast } = useToast();
  const { data: exercises } = useQuery({ queryKey: ["exercises"], queryFn: api.exercises });

  const [exerciseKey, setExerciseKey] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  // Default exercise = first of the user's preferred, else first available.
  const preferred = user?.prefs?.exercises ?? [];
  const selected = exerciseKey || preferred[0] || exercises?.[0]?.key || "";
  const selectedName = exercises?.find((e) => e.key === selected)?.name ?? "exercise";

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
      router.replace(`/sessions/${session.id}`);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Analysis failed", "error");
      setBusy(false);
    }
  }

  // While the analysis request is in flight, show a waiting screen with an
  // estimate instead of a queued-job poller.
  if (busy) return <Analyzing exerciseName={selectedName} />;

  return (
    <div className="max-w-2xl">
      <PageHeader title="New analysis" subtitle="Upload a clip and Kinesis scores every rep against biomechanics rules." />

      <div className="card p-5 sm:p-6 space-y-6">
        <div>
          <div className="label mb-2">Exercise</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {exercises?.map((e) => (
              <button
                key={e.key}
                onClick={() => setExerciseKey(e.key)}
                className={`px-3 py-2 rounded-lg border text-sm text-left transition ${
                  selected === e.key ? "border-accent bg-accent/10 text-fg" : "border-border text-muted hover:text-fg hover:bg-surface-2"
                }`}
              >
                {e.name}
              </button>
            ))}
          </div>
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
    </div>
  );
}

// Shown while the synchronous analysis request is in flight. There's no queue to
// poll — we just wait for the response, so this gives the user a time estimate
// and something to look forward to.
function Analyzing({ exerciseName }: { exerciseName: string }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="max-w-lg mx-auto">
      <div className="card p-8">
        <div className="flex items-center gap-3 mb-6">
          <span className="relative grid h-9 w-9 place-items-center">
            <span className="absolute inset-0 rounded-full border-2 border-border" />
            <span className="absolute inset-0 rounded-full border-2 border-transparent border-t-accent animate-spin" />
          </span>
          <div className="min-w-0">
            <div className="text-sm font-medium truncate">Analyzing your {exerciseName}…</div>
            <div className="label mt-0.5">
              Estimated time ~20–40s · {elapsed}s elapsed
            </div>
          </div>
        </div>

        {/* Indeterminate progress — the request completes when the report is ready. */}
        <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden mb-2">
          <div className="h-full w-1/3 bg-accent/60 skeleton" />
        </div>
        <p className="text-muted text-xs">
          Keep this tab open — your report opens automatically when it&apos;s done.
        </p>

        {/* While-you-wait guides prompt. Intentionally blank for now. */}
        <div className="mt-6 border-t border-border pt-6">
          <h2 className="text-sm font-medium">
            While you wait — want to see some guides about exercise form and videos?
          </h2>
          <div className="mt-3 grid h-40 place-items-center rounded-xl border border-dashed border-border">
            <span className="text-xs text-muted">Guides coming soon</span>
          </div>
        </div>
      </div>
    </div>
  );
}
