import type { Report } from "@/lib/types";

export default function CoachPanel({ report }: { report: Report }) {
  if (!report.coaching) return null;
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">AI Coach</h3>
        <span className="label">
          {report.coaching_provider === "claude" ? "Claude" : "rule-based"} · explains the analysis
        </span>
      </div>
      <div className="space-y-3 text-sm leading-relaxed text-fg whitespace-pre-line">
        {report.coaching}
      </div>
    </div>
  );
}
