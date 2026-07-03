import { scoreColor } from "@/lib/poseOverlay";
import type { KeyMetrics } from "@/lib/types";

const LABEL_COLOR: Record<string, string> = {
  good: "text-good",
  fair: "text-warn",
  poor: "text-bad",
  "n/a": "text-muted",
};

// A dense metric line — label left, value right — hairline-separated.
// No boxed "gauge" cards; reads like a terminal, not a dashboard widget.
function Row({
  label,
  value,
  sub,
  subClass,
}: {
  label: string;
  value: string;
  sub?: string;
  subClass?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2 border-b border-border/70 last:border-b-0">
      <span className="text-[13px] text-muted">{label}</span>
      <span className="flex items-baseline gap-2">
        {sub && <span className={`text-[11px] ${subClass ?? "text-faint"}`}>{sub}</span>}
        <span className="font-mono text-[15px] text-fg tabular-nums">{value}</span>
      </span>
    </div>
  );
}

export default function ScoreHero({
  score,
  grade,
  metrics,
}: {
  score: number;
  grade: string;
  metrics: KeyMetrics | null;
}) {
  const color = scoreColor(score);
  const pct = Math.max(0, Math.min(100, score));

  return (
    <section className="panel">
      <div className="grid lg:grid-cols-[minmax(0,1fr)_1.4fr]">
        {/* Score — a number, not a dial */}
        <div className="p-5 lg:border-r border-border flex flex-col justify-between gap-4">
          <div className="flex items-end justify-between">
            <div>
              <div className="eyebrow">Overall technique</div>
              <div className="mt-1 flex items-baseline gap-1.5">
                <span className="font-mono text-[44px] leading-none font-semibold tabular-nums" style={{ color }}>
                  {score.toFixed(0)}
                </span>
                <span className="text-faint text-sm font-mono">/100</span>
              </div>
            </div>
            <div className="text-right">
              <div className="text-lg font-semibold" style={{ color }}>{grade}</div>
              {metrics && (
                <div className="text-[11px] text-faint mt-0.5">
                  {metrics.rep_count} reps · {metrics.view} view
                </div>
              )}
            </div>
          </div>
          {/* Thin score bar — the only "chart", flat and honest */}
          <div className="h-1 rounded-full bg-surface-2 overflow-hidden">
            <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${pct}%`, background: color }} />
          </div>
        </div>

        {/* Metrics — dense rows */}
        {metrics && (
          <div className="p-5 pt-3 grid sm:grid-cols-2 sm:gap-x-8">
            <Row label="Range of motion" value={`${metrics.rom.toFixed(0)}°`} sub="avg/rep" />
            <Row
              label="Symmetry"
              value={metrics.symmetry === null ? "—" : `${metrics.symmetry.toFixed(1)}°`}
              sub={metrics.symmetry_label}
              subClass={LABEL_COLOR[metrics.symmetry_label]}
            />
            <Row label="Tempo" value={`${metrics.tempo.toFixed(1)}s`} sub="per rep" />
            <Row
              label="Consistency"
              value={metrics.consistency ? `${metrics.consistency.toFixed(0)}%` : "—"}
              sub={metrics.consistency_label}
              subClass={LABEL_COLOR[metrics.consistency_label]}
            />
          </div>
        )}
      </div>
    </section>
  );
}
