export interface Exercise {
  key: string;
  name: string;
}

export interface UserPrefs {
  onboarded?: boolean;
  goals?: string[];
  exercises?: string[];
}

export interface User {
  id: number;
  email: string;
  name: string;
  prefs: UserPrefs | null;
}

export interface StatRecent {
  session_id: number;
  exercise_key: string;
  exercise_name: string;
  overall_score: number;
  grade: string;
  status: string;
  created_at: string;
}

export interface Stats {
  total_sessions: number;
  completed: number;
  avg_score: number;
  week_sessions: number;
  week_avg: number;
  recent: StatRecent[];
  trend: { created_at: string; score: number }[];
  exercise_breakdown: Record<string, number>;
  common_faults: { type: string; count: number }[];
  personal_bests: { exercise_key: string; exercise_name: string; best_score: number }[];
}

export interface SessionSummary {
  id: number;
  exercise_key: string;
  status: "uploaded" | "processing" | "complete" | "failed";
  created_at: string;
  mode?: "upload" | "live";
}

export interface JobStatus {
  stage: string;
  progress: number;
  error: string | null;
}

export interface Fault {
  type: string;
  severity: "minor" | "moderate" | "severe";
  message: string;
  tip: string;
  start_frame: number;
  end_frame: number;
  value: number | null;
  unit: string;
  confidence: number; // 0..1
  joints: number[]; // affected MediaPipe landmark indices
}

// A fault flattened with its originating rep index, for the report fault list.
export interface RepFault extends Fault {
  rep_index: number;
}

export interface Rep {
  index: number;
  start_frame: number;
  bottom_frame: number;
  end_frame: number;
  score: number;
  rom: number | null;
  faults: Fault[];
}

export interface VideoMeta {
  filename: string;
  fps: number | null;
  duration: number | null;
  width: number | null;
  height: number | null;
}

export interface GroupedFault {
  type: string;
  message: string;
  tip: string;
  severity: "minor" | "moderate" | "severe";
  unit: string;
  count: number;
  affected_reps: number[];
  avg_value: number | null;
  worst_value: number | null;
  worst_rep: number | null;
  confidence: number;
  side: "left" | "right" | null;
  start_frame: number;
}

export interface KeyMetrics {
  rom: number;
  rom_unit: string;
  symmetry: number | null;
  symmetry_unit: string;
  symmetry_label: string;
  tempo: number;
  tempo_unit: string;
  consistency: number;
  consistency_unit: string;
  consistency_label: string;
  view: string;
  rep_count: number;
}

export interface SetSummary {
  set_index: number;
  rep_count: number;
  avg_score: number;
  duration_s: number;
}

export interface Report {
  session: SessionSummary;
  video: VideoMeta | null;
  reps: Rep[];
  overall_score: number;
  grade: string;
  key_metrics: KeyMetrics | null;
  strengths: string[];
  priorities: GroupedFault[];
  fault_groups: GroupedFault[];
  coaching: string | null;
  coaching_provider: string | null;
  // Live Camera Mode extras (empty/null for uploaded sessions).
  sets: SetSummary[];
  time_under_tension: number | null;
  duration_s: number | null;
}

// --- Live Camera Mode ---

export interface LiveCue {
  type: string;
  message: string;
  tip: string;
  severity: "minor" | "moderate" | "severe";
}

export interface LiveScoreResult {
  reps: Rep[];
  rep_count: number;
  running_score: number;
  latest_cue: LiveCue | null;
}

export interface LiveFinishResult {
  session_id: number;
}

// A captured frame: [x, y, z, visibility] per landmark, plus a capture time (s).
export type PoseFrame = number[][];

export interface Landmarks {
  fps: number;
  width: number;
  height: number;
  edges: number[][];
  frames: number[][][]; // [frame][landmark][x,y,vis]
}

export interface MetricSeries {
  key: string;
  label: string;
  unit: string;
  values: (number | null)[];
}

export interface AnalysisMetrics {
  fps: number;
  frames: number;
  stride: number;
  rep_bounds: { index: number; start: number; bottom: number; end: number }[];
  series: MetricSeries[];
}

export interface Ghost {
  available: boolean;
  source_session_id: number | null;
  source_score: number | null;
  edges: number[][];
  frames: number[][][]; // phase-normalized [phase][landmark][x,y,vis]
}

export interface ProgressPoint {
  session_id: number;
  created_at: string;
  avg_score: number;
  best_score: number;
  rep_count: number;
}

export interface CompareSide {
  session_id: number;
  exercise_key: string;
  avg_score: number;
  rep_count: number;
  fault_summary: Record<string, number>;
}

export interface CompareResult {
  a: CompareSide;
  b: CompareSide;
}
