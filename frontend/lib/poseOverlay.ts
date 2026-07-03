import type { Ghost, Landmarks, Rep, RepFault } from "./types";

const VIS_THRESHOLD = 0.4;

export function frameForTime(time: number, fps: number, total: number): number {
  return Math.max(0, Math.min(total - 1, Math.round(time * fps)));
}

interface Rect {
  ox: number;
  oy: number;
  rw: number;
  rh: number;
}

/** The video's displayed content rect inside the canvas under object-contain. */
function containRect(canvasW: number, canvasH: number, srcW: number, srcH: number): Rect {
  if (!srcW || !srcH) return { ox: 0, oy: 0, rw: canvasW, rh: canvasH };
  const srcAR = srcW / srcH;
  const dstAR = canvasW / canvasH;
  let rw: number;
  let rh: number;
  if (srcAR > dstAR) {
    rw = canvasW;
    rh = canvasW / srcAR;
  } else {
    rh = canvasH;
    rw = canvasH * srcAR;
  }
  return { ox: (canvasW - rw) / 2, oy: (canvasH - rh) / 2, rw, rh };
}

function drawSkeleton(
  ctx: CanvasRenderingContext2D,
  rect: Rect,
  landmarks: number[][],
  edges: number[][],
  color: string,
  alpha: number,
  jointRadius = 4,
) {
  const X = (p: number[]) => rect.ox + p[0] * rect.rw;
  const Y = (p: number[]) => rect.oy + p[1] * rect.rh;

  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 3;

  for (const [a, b] of edges) {
    const pa = landmarks[a];
    const pb = landmarks[b];
    if (!pa || !pb || pa[2] < VIS_THRESHOLD || pb[2] < VIS_THRESHOLD) continue;
    ctx.beginPath();
    ctx.moveTo(X(pa), Y(pa));
    ctx.lineTo(X(pb), Y(pb));
    ctx.stroke();
  }
  for (const p of landmarks) {
    if (!p || p[2] < VIS_THRESHOLD) continue;
    ctx.beginPath();
    ctx.arc(X(p), Y(p), jointRadius, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

/** Find the rep window containing a frame (for ghost phase alignment). */
export function repAtFrame(reps: Rep[], frame: number): Rep | null {
  for (const r of reps) {
    if (frame >= r.start_frame && frame <= r.end_frame) return r;
  }
  return null;
}

/** Landmark indices to flag red at this frame (union over active faults). */
export function highlightedJoints(faults: RepFault[], frame: number): Set<number> {
  const set = new Set<number>();
  for (const f of faults) {
    if (frame >= f.start_frame && frame <= f.end_frame) {
      for (const j of f.joints) set.add(j);
    }
  }
  return set;
}

function drawHighlight(
  ctx: CanvasRenderingContext2D,
  rect: Rect,
  landmarks: number[][],
  indices: Set<number>,
) {
  ctx.save();
  ctx.globalAlpha = 0.95;
  ctx.fillStyle = "#f43f5e";
  ctx.strokeStyle = "#f43f5e";
  ctx.lineWidth = 3;
  for (const idx of indices) {
    const p = landmarks[idx];
    if (!p || p[2] < VIS_THRESHOLD) continue;
    const x = rect.ox + p[0] * rect.rw;
    const y = rect.oy + p[1] * rect.rh;
    ctx.beginPath();
    ctx.arc(x, y, 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(x, y, 12, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();
}

export function renderOverlay(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  landmarks: Landmarks,
  frame: number,
  ghost: Ghost | null,
  reps: Rep[],
  showGhost: boolean,
  faults: RepFault[] = [],
) {
  ctx.clearRect(0, 0, w, h);
  const rect = containRect(w, h, landmarks.width, landmarks.height);

  // Ghost first (behind), phase-aligned to the current rep.
  if (showGhost && ghost?.available && ghost.frames.length > 0) {
    const rep = repAtFrame(reps, frame);
    if (rep && rep.end_frame > rep.start_frame) {
      const phase = (frame - rep.start_frame) / (rep.end_frame - rep.start_frame);
      const gi = Math.max(0, Math.min(ghost.frames.length - 1, Math.round(phase * (ghost.frames.length - 1))));
      drawSkeleton(ctx, rect, ghost.frames[gi], ghost.edges, "#a78bfa", 0.45, 5);
    }
  }

  // Live skeleton, then red-flag the joints affected by any fault active now.
  const lm = landmarks.frames[frame];
  if (lm) {
    drawSkeleton(ctx, rect, lm, landmarks.edges, "#22d3ee", 0.95, 4);
    const flagged = highlightedJoints(faults, frame);
    if (flagged.size) drawHighlight(ctx, rect, lm, flagged);
  }
}

/**
 * Draw a single live pose frame (Live Camera Mode). `landmarks` is one frame of
 * `[x, y, visibility]` (or `[x, y, z, visibility]`) triplets in normalized
 * coords; `srcW/srcH` are the camera frame dimensions for letterboxing.
 * `mirror` flips horizontally to match a selfie-view video.
 */
export function renderLiveFrame(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  srcW: number,
  srcH: number,
  landmarks: number[][],
  edges: number[][],
  mirror = false,
) {
  ctx.clearRect(0, 0, w, h);
  const rect = containRect(w, h, srcW, srcH);
  // A landmark's visibility is the last element ([x,y,vis] or [x,y,z,vis]).
  const vis = (p: number[]) => p[p.length - 1];
  const frame = landmarks.map((p) => [mirror ? 1 - p[0] : p[0], p[1], vis(p)]);
  drawSkeleton(ctx, rect, frame, edges, "#22d3ee", 0.95, 4);
}

export function scoreColor(score: number): string {
  if (score >= 85) return "#34d399";
  if (score >= 65) return "#fbbf24";
  return "#f87171";
}
