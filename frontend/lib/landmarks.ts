// MediaPipe Pose landmark index -> human-readable joint name (for fault display).
export const LANDMARK_NAME: Record<number, string> = {
  0: "nose",
  7: "left ear", 8: "right ear",
  11: "left shoulder", 12: "right shoulder",
  13: "left elbow", 14: "right elbow",
  15: "left wrist", 16: "right wrist",
  19: "left index", 20: "right index",
  21: "left thumb", 22: "right thumb",
  23: "left hip", 24: "right hip",
  25: "left knee", 26: "right knee",
  27: "left ankle", 28: "right ankle",
  29: "left heel", 30: "right heel",
  31: "left foot", 32: "right foot",
};

export function jointNames(indices: number[]): string {
  const names = indices.map((i) => LANDMARK_NAME[i]).filter(Boolean);
  return names.length ? Array.from(new Set(names)).join(", ") : "—";
}

export function formatMeasured(value: number | null, unit: string): string {
  if (value === null || Number.isNaN(value)) return "—";
  const decimals = unit === "ratio" || unit === "x" || unit === "s" ? 2 : unit === "%CV" ? 0 : 1;
  const n = value.toFixed(decimals);
  switch (unit) {
    case "deg":
      return `${n}°`;
    case "%body":
      return `${n}% body`;
    case "x":
      return `${n}×`;
    case "ratio":
      return `${n}`;
    case "%":
    case "%CV":
      return `${n}%`;
    case "":
      return n;
    default:
      return `${n} ${unit}`;
  }
}

export const SEVERITY_STYLE: Record<string, { label: string; cls: string; dot: string }> = {
  severe: { label: "Severe", cls: "bg-bad/15 text-bad border-bad/40", dot: "#f87171" },
  moderate: { label: "Moderate", cls: "bg-warn/15 text-warn border-warn/40", dot: "#fb923c" },
  minor: { label: "Minor", cls: "bg-accent/15 text-accent border-accent/30", dot: "#22d3ee" },
};
