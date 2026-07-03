import Link from "next/link";
import type { SessionSummary } from "@/lib/types";

const STATUS_COLOR: Record<string, string> = {
  complete: "text-good",
  processing: "text-warn",
  uploaded: "text-muted",
  failed: "text-bad",
};

export default function SessionCard({ s }: { s: SessionSummary }) {
  const href = s.status === "complete" ? `/sessions/${s.id}` : `/sessions/${s.id}/processing`;
  return (
    <Link href={href} className="card p-4 hover:border-accent transition block">
      <div className="flex items-center justify-between">
        <span className="font-medium capitalize">{s.exercise_key.replace("_", " ")}</span>
        <span className={`text-xs ${STATUS_COLOR[s.status] ?? "text-muted"}`}>{s.status}</span>
      </div>
      <div className="label mt-2">
        #{s.id} · {new Date(s.created_at).toLocaleString()}
      </div>
    </Link>
  );
}
