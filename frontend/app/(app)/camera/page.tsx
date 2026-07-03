"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toaster";
import { PageHeader } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { signalFor } from "@/lib/live/exerciseSignals";

export default function CameraPickerPage() {
  const router = useRouter();
  const { user } = useAuth();
  const { toast } = useToast();
  const { data: exercises } = useQuery({ queryKey: ["exercises"], queryFn: api.exercises });

  const [exerciseKey, setExerciseKey] = useState("");
  const [busy, setBusy] = useState(false);

  const preferred = user?.prefs?.exercises ?? [];
  const selected = exerciseKey || preferred[0] || exercises?.[0]?.key || "";

  async function start() {
    if (!selected) return;
    setBusy(true);
    try {
      const session = await api.liveCreate(selected);
      router.push(`/camera/${session.id}?ex=${selected}`);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Couldn't start live session", "error");
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Live camera"
        subtitle="Pick an exercise, then get real-time rep counting, technique scoring and coaching cues from your camera."
      />

      <div className="card p-5 sm:p-6 space-y-6">
        <div>
          <div className="label mb-2">Exercise</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {exercises?.map((e) => {
              const supported = !!signalFor(e.key);
              return (
                <button
                  key={e.key}
                  onClick={() => setExerciseKey(e.key)}
                  disabled={!supported}
                  className={`px-3 py-2 rounded-lg border text-sm text-left transition ${
                    selected === e.key
                      ? "border-accent bg-accent/10 text-fg"
                      : "border-border text-muted hover:text-fg hover:bg-surface-2"
                  } ${supported ? "" : "opacity-40 cursor-not-allowed"}`}
                >
                  {e.name}
                </button>
              );
            })}
          </div>
        </div>

        <button className="btn-primary btn-lg w-full" disabled={!selected || busy} onClick={start}>
          {busy ? "Starting…" : "Start live session"}
        </button>
        <p className="text-xs text-muted text-center">
          Prop your phone or webcam so your whole body is in frame. Film side-on for
          squats, deadlifts and push-ups; front-on for curls, presses and raises.
        </p>
      </div>
    </div>
  );
}
