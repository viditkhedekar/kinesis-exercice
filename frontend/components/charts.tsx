"use client";

import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTheme } from "./ThemeProvider";
import type { AnalysisMetrics } from "@/lib/types";

// SVG attributes don't resolve CSS var(), so read the tokens to concrete rgb().
const DARK = { accent: "rgb(235 235 235)", grid: "rgb(42 42 42)", axis: "rgb(110 110 110)", fg: "rgb(237 237 237)", surface: "rgb(22 22 22)" };
function useChartColors() {
  const { theme } = useTheme();
  const [c, setC] = useState(DARK);
  useEffect(() => {
    const s = getComputedStyle(document.documentElement);
    const v = (n: string) => `rgb(${s.getPropertyValue(n).trim() || "128 128 128"})`;
    setC({ accent: v("--accent"), grid: v("--border"), axis: v("--faint"), fg: v("--fg"), surface: v("--surface") });
  }, [theme]);
  return c;
}

function useTooltip() {
  const c = useChartColors();
  return {
    contentStyle: { background: c.surface, border: `1px solid ${c.grid}`, borderRadius: 8, fontSize: 12, padding: "6px 10px" },
    labelStyle: { color: c.axis, marginBottom: 2 },
    itemStyle: { color: c.fg },
  };
}

export function Sparkline({ data, height = 40 }: { data: number[]; height?: number }) {
  const w = 120;
  const h = height;
  if (data.length < 2) return <div style={{ height }} />;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const d = data.map((v, i) => `${i === 0 ? "M" : "L"} ${(i / (data.length - 1)) * w} ${h - ((v - min) / span) * (h - 4) - 2}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="w-full text-accent" style={{ height }}>
      <path d={`${d} L ${w} ${h} L 0 ${h} Z`} fill="currentColor" fillOpacity={0.07} />
      <path d={d} fill="none" stroke="currentColor" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function TrendArea({ data, height = 200 }: { data: { i: number; v: number }[]; height?: number }) {
  const c = useChartColors();
  const tt = useTooltip();
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ left: -22, right: 6, top: 8, bottom: 0 }}>
        <XAxis dataKey="i" hide />
        <YAxis domain={[0, 100]} stroke={c.axis} fontSize={11} tickLine={false} axisLine={false} width={30} />
        <Tooltip {...tt} labelFormatter={() => ""} />
        <Area type="monotone" dataKey="v" stroke={c.accent} strokeWidth={1.75} fill={c.accent} fillOpacity={0.06} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function AngleChart({
  metrics,
  seriesKey,
  currentFrame,
  onScrub,
  height = 180,
}: {
  metrics: AnalysisMetrics;
  seriesKey: string;
  currentFrame: number;
  onScrub?: (frame: number) => void;
  height?: number;
}) {
  const c = useChartColors();
  const tt = useTooltip();
  const s = metrics.series.find((x) => x.key === seriesKey) ?? metrics.series[0];
  if (!s) return null;
  const data = s.values.map((v, i) => ({ f: i * metrics.stride, v }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart
        data={data}
        margin={{ left: -18, right: 8, top: 8, bottom: 0 }}
        onClick={(state) => {
          const f = state?.activeLabel;
          if (onScrub && f != null) onScrub(Number(f));
        }}
      >
        <XAxis dataKey="f" stroke={c.axis} fontSize={11} tickLine={false} axisLine={{ stroke: c.grid }} />
        <YAxis stroke={c.axis} fontSize={11} tickLine={false} axisLine={false} width={34} unit="°" />
        <Tooltip {...tt} formatter={(v: number) => [`${v}°`, s.label]} labelFormatter={(f) => `frame ${f}`} />
        {metrics.rep_bounds.map((r) => (
          <ReferenceLine key={r.index} x={r.bottom} stroke={c.grid} strokeDasharray="3 3" />
        ))}
        <ReferenceLine x={currentFrame} stroke={c.accent} strokeWidth={1} />
        <Line type="monotone" dataKey="v" stroke={c.accent} strokeWidth={1.6} dot={false} isAnimationActive={false} connectNulls />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function RomBars({ data, height = 150 }: { data: { rep: string; rom: number; color: string }[]; height?: number }) {
  const c = useChartColors();
  const tt = useTooltip();
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ left: -20, right: 6, top: 8, bottom: 0 }}>
        <XAxis dataKey="rep" stroke={c.axis} fontSize={11} tickLine={false} axisLine={{ stroke: c.grid }} />
        <YAxis stroke={c.axis} fontSize={11} tickLine={false} axisLine={false} width={34} unit="°" />
        <Tooltip {...tt} formatter={(v: number) => [`${v}°`, "ROM"]} />
        <Bar dataKey="rom" radius={[3, 3, 0, 0]} maxBarSize={26} isAnimationActive={false}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.color} fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
