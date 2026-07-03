// Thin, consistent line icons (1.5px stroke, currentColor) — Lucide-style.
import type { SVGProps } from "react";

const base: SVGProps<SVGSVGElement> = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

type P = SVGProps<SVGSVGElement>;

export const Icon = {
  Activity: (p: P) => (
    <svg {...base} {...p}><path d="M3 12h4l2 6 4-14 2 8h6" /></svg>
  ),
  Target: (p: P) => (
    <svg {...base} {...p}><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="4" /><circle cx="12" cy="12" r="0.8" fill="currentColor" /></svg>
  ),
  Layers: (p: P) => (
    <svg {...base} {...p}><path d="M12 3 3 8l9 5 9-5-9-5Z" /><path d="M3 13l9 5 9-5" /></svg>
  ),
  Ghost: (p: P) => (
    <svg {...base} {...p}><path d="M5 21V9a7 7 0 0 1 14 0v12l-2.5-2-2.5 2-2-2-2 2-2.5-2L5 21Z" /><circle cx="9.5" cy="10" r="0.8" fill="currentColor" /><circle cx="14.5" cy="10" r="0.8" fill="currentColor" /></svg>
  ),
  Gauge: (p: P) => (
    <svg {...base} {...p}><path d="M4 18a8 8 0 1 1 16 0" /><path d="M12 18l4-5" /></svg>
  ),
  Trending: (p: P) => (
    <svg {...base} {...p}><path d="M3 17l6-6 4 4 8-8" /><path d="M21 7v5h-5" /></svg>
  ),
  Play: (p: P) => (
    <svg {...base} {...p}><path d="M7 5l11 7-11 7V5Z" /></svg>
  ),
  Arrow: (p: P) => (
    <svg {...base} {...p}><path d="M5 12h14M13 6l6 6-6 6" /></svg>
  ),
};
