"use client";

import { formatMeasured, SEVERITY_STYLE } from "@/lib/landmarks";
import type { GroupedFault } from "@/lib/types";

interface Props {
  title: string;
  faults: GroupedFault[];
  fps: number;
  onSeek: (timeSeconds: number) => void;
  compact?: boolean;
  emptyText?: string;
}

export default function GroupedFaultList({
  title,
  faults,
  fps,
  onSeek,
  compact,
  emptyText,
}: Props) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">{title}</h3>
        {faults.length > 0 && <span className="label">{faults.length} issues</span>}
      </div>
      {faults.length === 0 ? (
        <p className="text-good text-sm">{emptyText ?? "None detected."}</p>
      ) : (
        <ul className="space-y-3">
          {faults.map((f) => (
            <li key={f.type}>
              <button
                onClick={() => onSeek(f.start_frame / fps)}
                className="w-full text-left rounded-lg border border-edge hover:border-accent/50 hover:bg-edge transition p-3"
              >
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded border ${
                      SEVERITY_STYLE[f.severity]?.cls ?? SEVERITY_STYLE.minor.cls
                    }`}
                  >
                    {SEVERITY_STYLE[f.severity]?.label ?? "Minor"}
                  </span>
                  {f.side && (
                    <span className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded border border-edge text-muted">
                      {f.side}
                    </span>
                  )}
                  <span className="font-medium">{f.message}</span>
                </div>

                {!compact && <p className="text-sm text-fg mt-2">{f.tip}</p>}

                <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs">
                  <span className="text-muted">
                    Detected in reps{" "}
                    <span className="text-fg font-mono">{f.affected_reps.join(", ")}</span>
                  </span>
                  {f.avg_value !== null && (
                    <span className="text-muted">
                      Avg <span className="text-fg font-mono">{formatMeasured(f.avg_value, f.unit)}</span>
                    </span>
                  )}
                  {f.worst_value !== null && (
                    <span className="text-muted">
                      Worst{" "}
                      <span className="text-fg font-mono">
                        rep {f.worst_rep} ({formatMeasured(f.worst_value, f.unit)})
                      </span>
                    </span>
                  )}
                  <span className="text-muted">
                    Confidence{" "}
                    <span className="text-fg font-mono">{Math.round(f.confidence * 100)}%</span>
                  </span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
