import Link from "next/link";
import { scoreColor } from "@/lib/poseOverlay";
import type { SessionSummary } from "@/lib/types";

const STATUS_COLOR: Record<string, string> = {
  complete: "text-good",
  processing: "text-warn",
  uploaded: "text-muted",
  failed: "text-bad",
};

export default function SessionCard({
  s,
  onDeleteVideo,
  onDeleteSession,
  busy = false,
}: {
  s: SessionSummary;
  onDeleteVideo?: (s: SessionSummary) => void;
  onDeleteSession?: (s: SessionSummary) => void;
  busy?: boolean;
}) {
  const href = s.status === "complete" ? `/sessions/${s.id}` : `/sessions/${s.id}/processing`;
  const complete = s.status === "complete";
  const score = s.overall_score;
  const analysisOnly = s.has_analysis === true && s.has_video === false;
  const showActions = !!(onDeleteVideo || onDeleteSession);

  // Buttons live inside the card <Link>, so stop them from navigating.
  const guard = (fn?: (s: SessionSummary) => void) => (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    fn?.(s);
  };

  return (
    <Link href={href} className="card p-4 hover:border-accent transition block">
      <div className="flex items-start justify-between gap-3">
        <span className="font-medium capitalize">{s.exercise_key.replace("_", " ")}</span>
        {complete ? (
          <span
            className="font-mono tabular-nums text-lg leading-none"
            style={{ color: score != null ? scoreColor(score) : undefined }}
            title={score != null ? "Technique score" : "No trustworthy score for this clip"}
          >
            {score != null ? score.toFixed(0) : "--"}
          </span>
        ) : (
          <span className={`text-xs ${STATUS_COLOR[s.status] ?? "text-muted"}`}>{s.status}</span>
        )}
      </div>

      <div className="label mt-2 flex items-center gap-2 flex-wrap">
        <span>#{s.id} · {new Date(s.created_at).toLocaleDateString()}</span>
        {analysisOnly && (
          <span className="badge border-border text-muted normal-case tracking-normal" title="Video removed to free space — analysis and Ghost Replay kept">
            Analysis only · ¼ slot
          </span>
        )}
      </div>

      {showActions && (
        <div className="mt-3 pt-3 border-t border-border flex items-center gap-2">
          {onDeleteVideo && s.has_video === true && (
            <button className="btn-subtle h-7 px-2 text-[12px]" disabled={busy} onClick={guard(onDeleteVideo)}>
              Delete video · keep analysis
            </button>
          )}
          {onDeleteSession && (
            <button className="btn-subtle h-7 px-2 text-[12px] text-bad hover:text-bad" disabled={busy} onClick={guard(onDeleteSession)}>
              Delete
            </button>
          )}
        </div>
      )}
    </Link>
  );
}
