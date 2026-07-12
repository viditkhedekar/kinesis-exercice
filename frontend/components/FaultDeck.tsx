"use client";

import type { ComponentType, SVGProps } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { formatMeasured, SEVERITY_STYLE } from "@/lib/landmarks";
import type { GroupedFault } from "@/lib/types";
import { Icon } from "./icons";

type IconC = ComponentType<SVGProps<SVGSVGElement>>;

export interface DeckTab {
  key: string;
  label: string;
  faults: GroupedFault[];
  emptyText?: string;
}

// Icon per known tab key; anything else falls back to the layers glyph.
const TAB_ICON: Record<string, IconC> = {
  priorities: Icon.Target,
  all: Icon.Layers,
};

interface Props {
  tabs: DeckTab[];
  fps: number;
  /** When provided, navigating seeks the player and a "Jump to video" affordance shows. */
  onSeek?: (timeSeconds: number) => void;
  title?: string;
}

/**
 * A single-card browser for detected issues: flick through a list one at a time
 * with the arrows, dots, or ←/→ keys. With two tabs (e.g. Priorities / All) a
 * toggle appears; with one tab it's just a flick-through of that list. Each step
 * seeks the player (when seekable) to where the fault first occurs.
 */
export default function FaultDeck({ tabs, fps, onSeek, title = "Detected issues" }: Props) {
  // Open on the first tab that actually has issues (else the first tab).
  const initial = tabs.find((t) => t.faults.length > 0) ?? tabs[0];
  const [activeKey, setActiveKey] = useState(initial?.key ?? "");
  const [index, setIndex] = useState(0);
  const regionRef = useRef<HTMLDivElement>(null);

  const tab = tabs.find((t) => t.key === activeKey) ?? tabs[0];
  const list = tab?.faults ?? [];
  const total = list.length;
  const showToggle = tabs.length > 1;

  // Keep the index in range if the active list changes.
  useEffect(() => {
    setIndex((i) => (total === 0 ? 0 : Math.min(i, total - 1)));
  }, [total]);

  const seekTo = useCallback(
    (f: GroupedFault | undefined) => {
      if (f && onSeek) onSeek(f.start_frame / fps);
    },
    [onSeek, fps],
  );

  const go = useCallback(
    (next: number) => {
      if (total === 0) return;
      const wrapped = (next + total) % total;
      setIndex(wrapped);
      seekTo(list[wrapped]);
    },
    [total, list, seekTo],
  );

  const selectTab = (key: string) => {
    if (key === activeKey) return;
    setActiveKey(key);
    setIndex(0);
    seekTo(tabs.find((t) => t.key === key)?.faults[0]);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight") {
      e.preventDefault();
      go(index + 1);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      go(index - 1);
    }
  };

  const f = list[index];
  const sev = f ? SEVERITY_STYLE[f.severity] ?? SEVERITY_STYLE.minor : null;

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <h3 className="font-semibold">{title}</h3>
        {showToggle && (
          <div className="inline-flex rounded-[8px] border border-border overflow-hidden text-[12px]">
            {tabs.map((t, i) => {
              const TabIcon = TAB_ICON[t.key] ?? Icon.Layers;
              const on = t.key === activeKey;
              return (
                <button
                  key={t.key}
                  onClick={() => selectTab(t.key)}
                  className={`px-3 h-7 inline-flex items-center gap-1.5 transition ${
                    i > 0 ? "border-l border-border" : ""
                  } ${on ? "bg-surface-2 text-fg" : "text-muted hover:text-fg"}`}
                >
                  <TabIcon width={13} height={13} />
                  {t.label} <span className="tabular-nums text-faint">{t.faults.length}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {total === 0 ? (
        <p className="text-good text-sm">{tab?.emptyText ?? "None detected — clean, consistent reps."}</p>
      ) : (
        <div
          ref={regionRef}
          tabIndex={0}
          onKeyDown={onKeyDown}
          role="group"
          aria-roledescription="carousel"
          aria-label={`${title}: ${tab?.label ?? ""}`}
          className="outline-none focus-visible:ring-2 focus-visible:ring-accent/40 rounded-lg"
        >
          {/* Card */}
          <div
            key={`${activeKey}-${index}`}
            className="rounded-lg border border-edge bg-edge/40 p-4 min-h-[168px] flex flex-col animate-fade-in"
          >
            <div className="flex items-center gap-2 flex-wrap">
              {sev && (
                <span className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded border ${sev.cls}`}>
                  {sev.label}
                </span>
              )}
              {f?.side && (
                <span className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded border border-edge text-muted">
                  {f.side}
                </span>
              )}
              <span className="ml-auto text-[11px] text-faint tabular-nums">
                {index + 1} / {total}
              </span>
            </div>

            <p className="font-medium mt-2.5">{f?.message}</p>
            {f?.tip && (
              <p className="text-sm text-muted mt-1.5">
                <span className="text-good">Fix · </span>
                {f.tip}
              </p>
            )}

            <div className="mt-auto pt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs">
              <span className="text-muted">
                Reps <span className="text-fg font-mono">{f?.affected_reps.join(", ") || "—"}</span>
              </span>
              {f?.avg_value != null && (
                <span className="text-muted">
                  Avg <span className="text-fg font-mono">{formatMeasured(f.avg_value, f.unit)}</span>
                </span>
              )}
              {f?.worst_value != null && (
                <span className="text-muted">
                  Worst{" "}
                  <span className="text-fg font-mono">
                    rep {f.worst_rep} ({formatMeasured(f.worst_value, f.unit)})
                  </span>
                </span>
              )}
              <span className="text-muted">
                Confidence <span className="text-fg font-mono">{Math.round((f?.confidence ?? 0) * 100)}%</span>
              </span>
            </div>
          </div>

          {/* Controls */}
          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={() => go(index - 1)}
              aria-label="Previous issue"
              className="btn-subtle h-8 w-8 grid place-items-center"
              disabled={total < 2}
            >
              <Icon.Arrow width={16} height={16} className="rotate-180" />
            </button>

            {/* Dots */}
            <div className="flex-1 flex items-center justify-center gap-1.5 flex-wrap">
              {list.map((item, i) => (
                <button
                  key={item.type}
                  onClick={() => go(i)}
                  aria-label={`Issue ${i + 1}: ${item.message}`}
                  aria-current={i === index}
                  title={item.message}
                  className={`h-2 rounded-full transition-all ${
                    i === index ? "" : "bg-border-strong opacity-50 hover:opacity-80"
                  }`}
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
              aria-label="Next issue"
              className="btn-subtle h-8 w-8 grid place-items-center"
              disabled={total < 2}
            >
              <Icon.Arrow width={16} height={16} />
            </button>
          </div>

          {onSeek && f && (
            <button
              onClick={() => seekTo(f)}
              className="mt-3 w-full btn-ghost h-8 inline-flex items-center justify-center gap-1.5 text-[13px]"
            >
              <Icon.Play width={13} height={13} />
              Jump to this in the video
            </button>
          )}
        </div>
      )}
    </div>
  );
}
