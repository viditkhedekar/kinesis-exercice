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
      const session = await api.upload(selected, file);
      router.push(`/sessions/${session.id}/processing`);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Upload failed", "error");
      setBusy(false);
    }
  }

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
