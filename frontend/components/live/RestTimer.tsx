"use client";

import { useEffect, useRef, useState } from "react";

const PRESETS = [30, 60, 90, 120];

/**
 * Between-set rest countdown. Customisable duration + skip; calls `onDone` when
 * the timer elapses or the athlete taps "Start next set".
 */
export default function RestTimer({
  defaultSeconds = 60,
  onDone,
}: {
  defaultSeconds?: number;
  onDone: () => void;
}) {
  const [duration, setDuration] = useState(defaultSeconds);
  const [remaining, setRemaining] = useState(defaultSeconds);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    const id = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) {
          clearInterval(id);
          onDoneRef.current();
          return 0;
        }
        return r - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [duration]);

  function setPreset(s: number) {
    setDuration(s);
    setRemaining(s);
  }

  const mm = Math.floor(remaining / 60);
  const ss = String(remaining % 60).padStart(2, "0");

  return (
    <div className="absolute inset-0 z-10 grid place-items-center bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="card p-6 w-[min(90vw,380px)] text-center space-y-5">
        <div className="eyebrow">Rest</div>
        <div className="font-mono text-6xl font-semibold tabular-nums text-fg">
          {mm}:{ss}
        </div>
        <div className="flex justify-center gap-2">
          {PRESETS.map((s) => (
            <button
              key={s}
              onClick={() => setPreset(s)}
              className={`px-2.5 h-8 rounded-[7px] border text-[13px] font-mono transition ${
                duration === s
                  ? "border-accent bg-accent/10 text-fg"
                  : "border-border text-muted hover:text-fg hover:bg-surface-2"
              }`}
            >
              {s}s
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost flex-1" onClick={() => setRemaining((r) => r + 15)}>
            +15s
          </button>
          <button className="btn-primary flex-1" onClick={onDone}>
            Start next set
          </button>
        </div>
      </div>
    </div>
  );
}
