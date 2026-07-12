"use client";

import type { ComponentType, SVGProps } from "react";
import type { Insight } from "@/lib/types";
import { Icon } from "./icons";

type IconC = ComponentType<SVGProps<SVGSVGElement>>;

// Icon per insight kind; falls back to a lightbulb for anything new.
const KIND_ICON: Record<string, IconC> = {
  timing: Icon.Gauge,
  progress: Icon.Trending,
  prevalence: Icon.Target,
  clean: Icon.Check,
  symmetry: Icon.Scale,
  consistency: Icon.Activity,
};

// Tone -> tailwind classes (accent bar, icon/emphasis color, emphasis chip bg).
const TONE: Record<Insight["tone"], { text: string; bar: string; chip: string }> = {
  positive: { text: "text-good", bar: "bg-good", chip: "bg-good/12" },
  attention: { text: "text-warn", bar: "bg-warn", chip: "bg-warn/12" },
  neutral: { text: "text-accent", bar: "bg-accent", chip: "bg-accent/12" },
};

/**
 * Insight cards — one or two concise, data-grounded observations surfaced right
 * after a session (e.g. a cross-session improvement or a per-rep timing lag).
 */
export default function InsightCards({ insights }: { insights: Insight[] }) {
  if (!insights || insights.length === 0) return null;

  return (
    <section aria-label="Session insights">
      <div className="eyebrow mb-2 flex items-center gap-1.5">
        <Icon.Bulb width={13} height={13} />
        Insights
      </div>
      <div className={`grid gap-3 ${insights.length > 1 ? "sm:grid-cols-2" : ""}`}>
        {insights.map((ins, i) => {
          const IconC = KIND_ICON[ins.kind] ?? Icon.Bulb;
          const tone = TONE[ins.tone] ?? TONE.neutral;
          return (
            <div key={i} className="card relative overflow-hidden p-4 pl-5">
              <span className={`absolute left-0 top-0 bottom-0 w-1 ${tone.bar}`} aria-hidden />
              <div className="flex items-center gap-2 mb-1.5">
                <IconC width={16} height={16} className={tone.text} aria-hidden />
                {ins.emphasis && (
                  <span className={`ml-auto rounded-[6px] px-2 py-0.5 font-mono text-[13px] font-semibold tabular-nums ${tone.chip} ${tone.text}`}>
                    {ins.emphasis}
                  </span>
                )}
              </div>
              <p className="text-sm text-fg leading-snug">{ins.text}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
