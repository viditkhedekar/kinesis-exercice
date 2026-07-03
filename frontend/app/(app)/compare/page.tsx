"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { scoreColor } from "@/lib/poseOverlay";
import type { CompareSide } from "@/lib/types";

export default function ComparePage() {
  const { data: sessions } = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api.sessions(),
  });
  const complete = sessions?.filter((s) => s.status === "complete") ?? [];
  const [a, setA] = useState<number | "">("");
  const [b, setB] = useState<number | "">("");
  const [result, setResult] = useState<{ a: CompareSide; b: CompareSide } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (a === "" || b === "") return;
    setError(null);
    try {
      setResult(await api.compare(Number(a), Number(b)));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Compare two sessions</h1>

      <div className="card p-6 flex flex-wrap items-end gap-4">
        <Picker label="Session A" value={a} onChange={setA} options={complete} />
        <Picker label="Session B" value={b} onChange={setB} options={complete} />
        <button className="btn-primary" onClick={run} disabled={a === "" || b === ""}>
          Compare
        </button>
      </div>

      {error && <p className="text-bad text-sm">{error}</p>}

      {result && (
        <div className="grid sm:grid-cols-2 gap-4">
          <SideCard side={result.a} />
          <SideCard side={result.b} />
        </div>
      )}
    </div>
  );
}

function Picker({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: number | "";
  onChange: (v: number | "") => void;
  options: { id: number; exercise_key: string }[];
}) {
  return (
    <div>
      <div className="label mb-1">{label}</div>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : "")}
        className="bg-panel border border-edge rounded-lg px-3 py-2 text-sm min-w-[200px]"
      >
        <option value="">Select…</option>
        {options.map((s) => (
          <option key={s.id} value={s.id}>
            #{s.id} · {s.exercise_key.replace("_", " ")}
          </option>
        ))}
      </select>
    </div>
  );
}

function SideCard({ side }: { side: CompareSide }) {
  const faults = Object.entries(side.fault_summary).sort((x, y) => y[1] - x[1]);
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="label capitalize">{side.exercise_key.replace("_", " ")}</div>
          <h3 className="font-semibold">Session #{side.session_id}</h3>
        </div>
        <div className="text-right">
          <div className="label">Avg score</div>
          <div className="text-2xl font-mono" style={{ color: scoreColor(side.avg_score) }}>
            {side.avg_score.toFixed(0)}
          </div>
        </div>
      </div>
      <div className="label mt-3">{side.rep_count} reps</div>
      <div className="mt-3 space-y-1">
        {faults.length === 0 ? (
          <p className="text-good text-sm">No faults detected</p>
        ) : (
          faults.map(([type, count]) => (
            <div key={type} className="flex justify-between text-sm">
              <span className="text-fg capitalize">{type.replace(/_/g, " ")}</span>
              <span className="text-muted font-mono">{count}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
