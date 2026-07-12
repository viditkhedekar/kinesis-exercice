import type {
  AnalysisMetrics,
  CompareResult,
  Exercise,
  Ghost,
  JobStatus,
  Landmarks,
  LiveFinishResult,
  LiveScoreResult,
  PoseFrame,
  ProgressPoint,
  Quota,
  Report,
  SessionSummary,
  Stats,
  User,
  UserPrefs,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store",
    credentials: "include", // send the session cookie
    headers: { ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers },
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : "Request failed");
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function videoUrl(sessionId: number): string {
  return `${API_BASE}/sessions/${sessionId}/video`;
}

export const api = {
  // --- auth ---
  me: () => req<User>("/auth/me"),
  register: (email: string, name: string, password: string) =>
    req<User>("/auth/register", { method: "POST", body: JSON.stringify({ email, name, password }) }),
  login: (email: string, password: string, remember: boolean) =>
    req<User>("/auth/login", { method: "POST", body: JSON.stringify({ email, password, remember }) }),
  logout: () => req<void>("/auth/logout", { method: "POST" }),
  updateMe: (patch: { name?: string; prefs?: UserPrefs }) =>
    req<User>("/auth/me", { method: "PATCH", body: JSON.stringify(patch) }),
  forgot: (email: string) =>
    req<{ sent: boolean; token: string | null }>("/auth/forgot", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  reset: (token: string, password: string) =>
    req<User>("/auth/reset", { method: "POST", body: JSON.stringify({ token, password }) }),

  // --- data ---
  exercises: () => req<Exercise[]>("/exercises"),
  stats: () => req<Stats>("/stats"),
  sessions: (exercise?: string) =>
    req<SessionSummary[]>(`/sessions${exercise ? `?exercise=${exercise}` : ""}`),
  quota: () => req<Quota>("/sessions/quota"),
  deleteVideo: (id: number) => req<SessionSummary>(`/sessions/${id}/video`, { method: "DELETE" }),
  deleteSession: (id: number) => req<void>(`/sessions/${id}`, { method: "DELETE" }),
  status: (id: number) => req<JobStatus>(`/sessions/${id}/status`),
  report: (id: number) => req<Report>(`/sessions/${id}/report`),
  landmarks: (id: number) => req<Landmarks>(`/sessions/${id}/landmarks`),
  metrics: (id: number) => req<AnalysisMetrics>(`/sessions/${id}/metrics`),
  ghost: (id: number) => req<Ghost>(`/sessions/${id}/ghost`),
  progress: (exercise?: string) =>
    req<ProgressPoint[]>(`/progress${exercise ? `?exercise=${exercise}` : ""}`),

  async upload(exerciseKey: string, file: File): Promise<SessionSummary> {
    const form = new FormData();
    form.append("exercise_key", exerciseKey);
    form.append("file", file);
    const res = await fetch(`${API_BASE}/sessions`, {
      method: "POST",
      body: form,
      credentials: "include",
    });
    if (!res.ok) {
      // Surface the server's detail (e.g. the history-quota message) when present.
      let detail = `Upload failed (${res.status})`;
      try {
        const body = await res.json();
        if (typeof body.detail === "string") detail = body.detail;
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, detail);
    }
    return res.json();
  },

  compare: (a: number, b: number) =>
    req<CompareResult>("/compare", { method: "POST", body: JSON.stringify({ session_a: a, session_b: b }) }),

  // --- live camera mode ---
  liveCreate: (exerciseKey: string) =>
    req<SessionSummary>("/sessions/live", {
      method: "POST",
      body: JSON.stringify({ exercise_key: exerciseKey }),
    }),
  liveScore: (id: number, fps: number, frames: PoseFrame[]) =>
    req<LiveScoreResult>(`/sessions/live/${id}/score`, {
      method: "POST",
      body: JSON.stringify({ fps, frames }),
    }),
  liveFinish: (
    id: number,
    frames: PoseFrame[],
    timestamps: number[],
    sets: { start: number; end: number }[],
    width: number,
    height: number,
  ) =>
    req<LiveFinishResult>(`/sessions/live/${id}/finish`, {
      method: "POST",
      body: JSON.stringify({ frames, timestamps, sets, width, height }),
    }),
};
