// Static demo data for the landing-page interactive demo. This is REAL output of
// the physIQal pipeline (MediaPipe pose + biomechanics + rules) precomputed on
// four sample clips and exported to /public/demo/demos.json — only landmark
// coordinates are stored (rendered as nodes on black), never any video.
import type { GroupedFault, KeyMetrics } from "./types";

export interface DemoRep {
  index: number;
  start: number;
  bottom: number;
  end: number;
  score: number;
  rom: number;
  fault_count: number;
}

export interface DemoSeries {
  key: string;
  label: string;
  unit: string;
  values: (number | null)[];
}

export interface DemoRepBound {
  index: number;
  start: number;
  bottom: number;
  end: number;
}

export interface DemoExample {
  key: string;
  name: string;
  reps: number;
  view: string;
  fps: number;
  aspect: number; // width / height, for letterboxing the skeleton
  edges: number[][];
  frames: number[][][]; // [frame][landmark][x, y, visibility], normalized
  highlight: number[];
  score: number;
  grade: string;
  metrics: KeyMetrics;
  strengths: string[];
  priorities: GroupedFault[];
  fault_groups: GroupedFault[];
  rep_breakdown: DemoRep[];
  stride: number;
  rep_bounds: DemoRepBound[];
  series: DemoSeries[];
}

interface DemoBundle {
  generatedAt: string;
  examples: DemoExample[];
}

let cache: Promise<DemoExample[]> | null = null;

export function loadDemos(): Promise<DemoExample[]> {
  if (!cache) {
    cache = fetch("/demo/demos.json")
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load demo data (${r.status})`);
        return r.json() as Promise<DemoBundle>;
      })
      .then((b) => b.examples)
      .catch((e) => {
        cache = null; // allow retry on next mount
        throw e;
      });
  }
  return cache;
}

export const DEMO_FPS = 15;
