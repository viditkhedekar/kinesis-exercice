"use client";

import { useCallback, useEffect, useState } from "react";
import { formatMeasured, SEVERITY_STYLE } from "@/lib/landmarks";
import type { GroupedFault } from "@/lib/types";
import { Icon } from "./icons";

/**
 * The headline of the report, shown big and directly above the video: the top
 * things to fix, flicked through one at a time (arrows / dots / ←→ keys) like the
 * detected-issues deck. The card carries a live red glow so it can't be missed;
 * each fix sits in a bright-green glowing panel you can expand for more detail.
 */
export default function PrioritiesSpotlight({
  priorities,
  fps,
  onSeek,
}: {
  priorities: GroupedFault[];
  fps: number;
  onSeek?: (timeSeconds: number) => void;
}) {
  const [index, setIndex] = useState(0);
  const [showInfo, setShowInfo] = useState(false);
  const total = priorities.length;

  // Keep the index in range and collapse the detail when the card changes.
  useEffect(() => {
    setIndex((i) => (total === 0 ? 0 : Math.min(i, total - 1)));
  }, [total]);
  useEffect(() => {
    setShowInfo(false);
  }, [index]);

  const go = useCallback(
    (next: number) => {
      if (total === 0) return;
      const wrapped = (next + total) % total;
      setIndex(wrapped);
      const f = priorities[wrapped];
      if (f && onSeek) onSeek(f.start_frame / fps);
    },
    [total, priorities, onSeek, fps],
  );

  if (total === 0) {
    return (
      <div className="card glow-green p-6">
        <div className="flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-good/15 text-good">✓</span>
          <div>
            <h2 className="font-semibold">No priority issues</h2>
            <p className="text-muted text-sm">Clean, consistent reps — nothing urgent to fix. Nice work.</p>
          </div>
        </div>
      </div>
    );
  }

  const f = priorities[index];
  const sev = SEVERITY_STYLE[f.severity] ?? SEVERITY_STYLE.minor;

  return (
    <div className="card glow-red p-5 sm:p-6">
      <div className="flex items-center gap-2.5 mb-4">
        <span className="grid h-8 w-8 place-items-center rounded-full bg-bad/15 text-bad">
          <Icon.Target width={16} height={16} />
        </span>
        <div className="min-w-0">
          <h2 className="font-semibold text-[17px]">Top priorities to fix</h2>
          <p className="text-muted text-[13px]">
            The {total} thing{total > 1 ? "s" : ""} that will most improve your next set.
          </p>
        </div>
        <span className="ml-auto text-[11px] text-faint tabular-nums">{index + 1} / {total}</span>
      </div>

      <div
        tabIndex={0}
        role="group"
        aria-roledescription="carousel"
        aria-label="Top priorities"
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") { e.preventDefault(); go(index + 1); }
          else if (e.key === "ArrowLeft") { e.preventDefault(); go(index - 1); }
        }}
        className="outline-none focus-visible:ring-2 focus-visible:ring-accent/40 rounded-xl"
      >
        {/* Current priority */}
        <div key={index} className="rounded-xl border border-bad/25 bg-bad/[0.04] p-4 animate-fade-in">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="grid h-6 w-6 place-items-center rounded-full bg-bad text-[12px] font-bold text-white">
              {index + 1}
            </span>
            <span className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded border ${sev.cls}`}>
              {sev.label}
            </span>
            {f.side && (
              <span className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded border border-edge text-muted">
                {f.side}
              </span>
            )}
            <span className="ml-auto text-[11px] text-faint">
              {Math.round((f.confidence ?? 0) * 100)}% confidence
            </span>
          </div>

          <p className="font-medium text-[15px] mt-2.5">{f.message}</p>

          {/* Fix — bright green, click to expand more detail. */}
          {f.tip && (
            <div className="glow-green rounded-lg border bg-good/[0.06] mt-3 overflow-hidden">
              <button
                onClick={() => setShowInfo((s) => !s)}
                aria-expanded={showInfo}
                className="w-full text-left p-3 flex items-start gap-2"
              >
                <span className="text-good font-semibold text-[13px] shrink-0">Fix →</span>
                <p className="text-[14px] text-fg flex-1">{f.tip}</p>
                <span className="text-good shrink-0 inline-flex items-center gap-1 text-[12px]">
                  {showInfo ? "Less" : "More info"}
                  <Icon.Arrow width={13} height={13} className={`transition-transform ${showInfo ? "-rotate-90" : "rotate-90"}`} />
                </span>
              </button>
              {showInfo && (
                <div className="px-3 pb-3 pt-0 animate-fade-in">
                  <div className="border-t border-good/20 pt-3 grid gap-x-5 gap-y-1.5 text-xs sm:grid-cols-2">
                    <Evidence label="Affected reps" value={f.affected_reps.join(", ") || "—"} />
                    <Evidence label="Times detected" value={`${f.count}`} />
                    {f.avg_value != null && <Evidence label="Average" value={formatMeasured(f.avg_value, f.unit)} />}
                    {f.worst_value != null && (
                      <Evidence label="Worst rep" value={`rep ${f.worst_rep} (${formatMeasured(f.worst_value, f.unit)})`} />
                    )}
                  </div>
                  {onSeek && (
                    <button
                      onClick={() => onSeek(f.start_frame / fps)}
                      className="mt-3 btn-ghost h-8 inline-flex items-center gap-1.5 text-[13px]"
                    >
                      <Icon.Play width={13} height={13} />
                      Jump to this in the video
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Flick-through controls */}
        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={() => go(index - 1)}
            aria-label="Previous priority"
            className="btn-subtle h-8 w-8 grid place-items-center"
            disabled={total < 2}
          >
            <Icon.Arrow width={16} height={16} className="rotate-180" />
          </button>

          <div className="flex-1 flex items-center justify-center gap-1.5 flex-wrap">
            {priorities.map((item, i) => (
              <button
                key={item.type}
                onClick={() => go(i)}
                aria-label={`Priority ${i + 1}: ${item.message}`}
                aria-current={i === index}
                title={item.message}
                className={`h-2 rounded-full transition-all ${i === index ? "" : "bg-border-strong opacity-50 hover:opacity-80"}`}
                style={
                  i === index
                    ? { width: 18, background: SEVERITY_STYLE[item.severity]?.dot ?? SEVERITY_STYLE.minor.dot }
                    : { width: 8 }
                }
              />
            ))}
          </div>

          <button
            onClick={() => go(index + 1)}
            aria-label="Next priority"
            className="btn-subtle h-8 w-8 grid place-items-center"
            disabled={total < 2}
          >
            <Icon.Arrow width={16} height={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

function Evidence({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted">{label}</span>
      <span className="text-fg font-mono">{value}</span>
    </div>
  );
}
