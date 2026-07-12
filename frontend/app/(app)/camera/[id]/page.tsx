"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import LiveCamera, { type LiveCameraHandle } from "@/components/live/LiveCamera";
import LiveHUD, { type LiveStats } from "@/components/live/LiveHUD";
import RestTimer from "@/components/live/RestTimer";
import { useToast } from "@/components/Toaster";
import { api, ApiError } from "@/lib/api";
import { evaluateLiveCues } from "@/lib/live/liveCoach";
import type { RepMetrics } from "@/lib/live/repMetrics";
import type { LiveCue } from "@/lib/types";

type Phase = "loading" | "active" | "resting" | "finishing";

const SEV_RANK: Record<LiveCue["severity"], number> = { minor: 0, moderate: 1, severe: 2 };
const CUE_DWELL_MS = 2500; // hold a cue at least this long before a same/lower one replaces it
const CUE_CLEAR_MS = 5000; // auto-dismiss a cue after this if nothing new arrives

export default function LiveSessionPage() {
  const params = useParams();
  const search = useSearchParams();
  const router = useRouter();
  const { toast } = useToast();
  const sessionId = Number(params.id);

  // Exercise key from the picker (?ex=); fall back to the report endpoint.
  const exFromUrl = search.get("ex") ?? "";
  const { data: fallbackReport } = useQuery({
    queryKey: ["live-ex", sessionId],
    queryFn: () => api.report(sessionId),
    enabled: !exFromUrl && Number.isFinite(sessionId),
  });
  const exerciseKey = exFromUrl || fallbackReport?.session.exercise_key || "";

  const cameraRef = useRef<LiveCameraHandle>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [paused, setPaused] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cue, setCue] = useState<LiveCue | null>(null);
  const [progress, setProgress] = useState(0);
  const [tracking, setTracking] = useState(true);
  const [nowTick, setNowTick] = useState(0);

  // Rep counting is fully client-side (instant); the authoritative scored review
  // is produced server-side at /live/finish.
  const [repsTotal, setRepsTotal] = useState(0);
  const [repsThisSet, setRepsThisSet] = useState(0);
  const [setsCompleted, setSetsCompleted] = useState(0);
  const sessionStartRef = useRef(0);
  const setStartRef = useRef(0);

  // Coaching-cue dwell so cues don't flicker frame-to-frame.
  const cueMeta = useRef({ at: 0, sev: -1 });
  const clearTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const capturing = phase === "active" && !paused;

  // 2 Hz clock for the elapsed/set-time tiles.
  useEffect(() => {
    const id = setInterval(() => setNowTick(performance.now()), 500);
    return () => clearInterval(id);
  }, []);

  useEffect(() => () => {
    if (clearTimer.current) clearTimeout(clearTimer.current);
  }, []);

  const showCue = useCallback((c: LiveCue) => {
    const now = performance.now();
    const sev = SEV_RANK[c.severity] ?? 0;
    // Keep the current cue for a minimum dwell unless a more severe one arrives.
    if (now - cueMeta.current.at < CUE_DWELL_MS && sev <= cueMeta.current.sev) return;
    cueMeta.current = { at: now, sev };
    setCue(c);
    if (clearTimer.current) clearTimeout(clearTimer.current);
    clearTimer.current = setTimeout(() => {
      setCue(null);
      cueMeta.current = { at: 0, sev: -1 };
    }, CUE_CLEAR_MS);
  }, []);

  const clearCue = useCallback(() => {
    if (clearTimer.current) clearTimeout(clearTimer.current);
    cueMeta.current = { at: 0, sev: -1 };
    setCue(null);
  }, []);

  // Fires once per completed rep, from the camera's hot loop.
  const handleRepComplete = useCallback(
    (metrics: RepMetrics) => {
      setRepsTotal((n) => n + 1);
      setRepsThisSet((n) => n + 1);
      const c = evaluateLiveCues(exerciseKey, metrics);
      if (c) showCue(c);
    },
    [exerciseKey, showCue],
  );

  const handleReady = useCallback(() => {
    sessionStartRef.current = performance.now();
    setStartRef.current = performance.now();
    cameraRef.current?.beginSet();
    setPhase("active");
  }, []);

  function pauseToggle() {
    setPaused((p) => !p);
  }

  function startRest() {
    cameraRef.current?.endSet();
    setSetsCompleted((n) => n + 1);
    setRepsThisSet(0);
    clearCue();
    setPaused(false);
    setPhase("resting");
  }

  function resumeFromRest() {
    setStartRef.current = performance.now();
    setRepsThisSet(0);
    cameraRef.current?.beginSet();
    setPhase("active");
  }

  async function endWorkout() {
    if (phase === "active") cameraRef.current?.endSet();
    setPhase("finishing");
    try {
      const payload = cameraRef.current!.getFinishPayload();
      if (payload.frames.length < 3) {
        toast("Not enough movement captured to analyze.", "error");
        setPhase("active");
        return;
      }
      await api.liveFinish(
        sessionId, payload.frames, payload.timestamps, payload.sets, payload.width, payload.height,
      );
      router.push(`/camera/${sessionId}/review`);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Couldn't finish the session", "error");
      setPhase("active");
    }
  }

  // Derived stats for the HUD.
  const elapsed = sessionStartRef.current ? (nowTick - sessionStartRef.current) / 1000 : 0;
  const setElapsed = phase === "active" && setStartRef.current ? (nowTick - setStartRef.current) / 1000 : 0;

  const stats: LiveStats = {
    reps: repsTotal,
    repsThisSet,
    sets: setsCompleted + (phase === "active" ? 1 : 0),
    elapsed: Math.max(0, elapsed),
    setElapsed: Math.max(0, setElapsed),
    progress,
    tracking,
  };

  if (!exerciseKey) {
    return <div className="text-muted text-sm">Loading session…</div>;
  }

  return (
    <div className="-mx-4 sm:-mx-6 -my-6 sm:-my-8">
      <div className="relative h-[calc(100vh-3.5rem)] lg:h-[calc(100vh-0px)] min-h-[520px] bg-black">
        <LiveCamera
          ref={cameraRef}
          exerciseKey={exerciseKey}
          capturing={capturing}
          onReady={handleReady}
          onError={(m) => setError(m)}
          onTick={(p, t) => {
            setProgress(p);
            setTracking(t);
          }}
          onRepComplete={handleRepComplete}
        />

        {phase === "loading" && !error && (
          <div className="absolute inset-0 grid place-items-center text-center">
            <div className="space-y-2">
              <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-border border-t-accent" />
              <p className="text-sm text-muted">Starting camera & pose engine…</p>
            </div>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 grid place-items-center p-6 text-center">
            <div className="card p-6 max-w-sm space-y-3">
              <p className="text-sm text-bad">{error}</p>
              <button className="btn-ghost w-full" onClick={() => location.reload()}>
                Retry
              </button>
              <button className="btn-subtle w-full" onClick={() => router.push("/camera")}>
                Back
              </button>
            </div>
          </div>
        )}

        {phase !== "loading" && !error && (
          <LiveHUD
            stats={stats}
            cue={cue}
            paused={paused}
            onPauseToggle={pauseToggle}
            onRest={startRest}
            onEnd={endWorkout}
            finishing={phase === "finishing"}
          />
        )}

        {phase === "resting" && (
          <RestTimer defaultSeconds={60} onDone={resumeFromRest} />
        )}
      </div>
    </div>
  );
}
