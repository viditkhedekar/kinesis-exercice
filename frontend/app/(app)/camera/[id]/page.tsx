"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import LiveCamera, { type LiveCameraHandle } from "@/components/live/LiveCamera";
import LiveHUD, { type LiveStats } from "@/components/live/LiveHUD";
import RestTimer from "@/components/live/RestTimer";
import { useToast } from "@/components/Toaster";
import { api, ApiError } from "@/lib/api";
import type { LiveCue, Rep } from "@/lib/types";

type Phase = "loading" | "active" | "resting" | "finishing";

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

  // Session-wide rep aggregation. Current set is live; ended sets are folded in.
  const [currentSetReps, setCurrentSetReps] = useState<Rep[]>([]);
  const completed = useRef({ reps: 0, scoreSum: 0, scoreCount: 0, sets: 0 });
  const sessionStartRef = useRef(0);
  const setStartRef = useRef(0);

  // Scoring request de-duplication.
  const inFlight = useRef(false);
  const pending = useRef(false);

  const capturing = phase === "active" && !paused;

  // 1 Hz clock for the elapsed/set-time tiles.
  useEffect(() => {
    const id = setInterval(() => setNowTick(performance.now()), 500);
    return () => clearInterval(id);
  }, []);

  const scoreCurrentSet = useCallback(async () => {
    if (inFlight.current) {
      pending.current = true;
      return;
    }
    inFlight.current = true;
    try {
      const { frames, fps } = cameraRef.current!.getCurrentSetFrames();
      if (frames.length < 3) return;
      const res = await api.liveScore(sessionId, fps, frames);
      setCurrentSetReps(res.reps);
      if (res.latest_cue) setCue(res.latest_cue);
    } catch {
      /* transient scoring failure — keep going, next rep retries */
    } finally {
      inFlight.current = false;
      if (pending.current) {
        pending.current = false;
        scoreCurrentSet();
      }
    }
  }, [sessionId]);

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
    // Fold the current set's scored reps into the completed totals.
    const c = completed.current;
    c.reps += currentSetReps.length;
    c.scoreSum += currentSetReps.reduce((s, r) => s + r.score, 0);
    c.scoreCount += currentSetReps.length;
    c.sets += 1;
    setCurrentSetReps([]);
    setCue(null);
    setPaused(false);
    setPhase("resting");
  }

  function resumeFromRest() {
    setStartRef.current = performance.now();
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
  const c = completed.current;
  const scoredNow = currentSetReps.reduce((s, r) => s + r.score, 0);
  const totalScoreCount = c.scoreCount + currentSetReps.length;
  const avgScore =
    totalScoreCount > 0 ? (c.scoreSum + scoredNow) / totalScoreCount : null;
  const elapsed = sessionStartRef.current ? (nowTick - sessionStartRef.current) / 1000 : 0;
  const setElapsed = phase === "active" && setStartRef.current ? (nowTick - setStartRef.current) / 1000 : 0;

  const stats: LiveStats = {
    reps: c.reps + currentSetReps.length,
    sets: c.sets + (phase === "active" ? 1 : 0),
    elapsed: Math.max(0, elapsed),
    setElapsed: Math.max(0, setElapsed),
    avgScore,
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
          onRepComplete={scoreCurrentSet}
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
