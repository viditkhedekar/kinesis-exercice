"use client";

import { useEffect, useRef } from "react";

interface Props {
  frames: number[][][];
  edges: number[][];
  fps?: number;
  aspect?: number; // width / height of the source clip, for letterboxing
  scanning?: boolean; // show an analysis scan-line sweep
  highlight?: number[]; // landmark indices to flag red
}

// The pose overlay: blue nodes + edges on pure black. No video, no person —
// only the estimated landmarks, exactly as the engine sees them.
const EDGE = "rgb(59, 130, 246)";   // blue-500
const NODE = "rgb(96, 165, 250)";   // blue-400
const NODE_BAD = "rgb(248, 113, 113)"; // red-400

export default function DemoSkeleton({
  frames,
  edges,
  fps = 15,
  aspect = 0.5625,
  scanning,
  highlight = [],
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!frames.length) return;
    let raf = 0;
    const start = performance.now();
    const hl = new Set(highlight);

    const draw = () => {
      const canvas = canvasRef.current;
      const wrap = wrapRef.current;
      if (canvas && wrap) {
        const W = (canvas.width = wrap.clientWidth);
        const H = (canvas.height = wrap.clientHeight);
        const ctx = canvas.getContext("2d")!;
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, W, H);

        // Letterbox: fit a box of the clip's aspect inside the canvas, centered.
        let dw = W;
        let dh = W / aspect;
        if (dh > H) {
          dh = H;
          dw = H * aspect;
        }
        const ox = (W - dw) / 2;
        const oy = (H - dh) / 2;

        // subtle dot grid inside the frame
        ctx.fillStyle = "rgba(96,165,250,0.10)";
        for (let x = ox; x < ox + dw; x += 26)
          for (let y = oy; y < oy + dh; y += 26) ctx.fillRect(x, y, 1, 1);

        const t = (performance.now() - start) / 1000;
        const idx = Math.floor((t * fps) % frames.length);
        const lm = frames[idx];

        const X = (p: number[]) => ox + p[0] * dw;
        const Y = (p: number[]) => oy + p[1] * dh;

        ctx.strokeStyle = EDGE;
        ctx.lineWidth = 2.5;
        ctx.lineCap = "round";
        for (const [a, b] of edges) {
          if (lm[a][2] < 0.4 || lm[b][2] < 0.4) continue;
          ctx.beginPath();
          ctx.moveTo(X(lm[a]), Y(lm[a]));
          ctx.lineTo(X(lm[b]), Y(lm[b]));
          ctx.stroke();
        }
        for (let i = 0; i < lm.length; i++) {
          if (lm[i][2] < 0.4) continue;
          const bad = hl.has(i);
          ctx.beginPath();
          ctx.fillStyle = bad ? NODE_BAD : NODE;
          ctx.arc(X(lm[i]), Y(lm[i]), bad ? 5 : 3.2, 0, Math.PI * 2);
          ctx.fill();
        }

        if (scanning) {
          const sy = oy + (Math.sin(t * 2) * 0.5 + 0.5) * dh;
          const grad = ctx.createLinearGradient(0, sy - 28, 0, sy + 28);
          grad.addColorStop(0, "rgba(59,130,246,0)");
          grad.addColorStop(0.5, "rgba(59,130,246,0.55)");
          grad.addColorStop(1, "rgba(59,130,246,0)");
          ctx.fillStyle = grad;
          ctx.fillRect(ox, sy - 28, dw, 56);
        }
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [frames, edges, fps, aspect, scanning, highlight]);

  return (
    <div ref={wrapRef} className="relative w-full aspect-square rounded-xl border border-border bg-black overflow-hidden">
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />
    </div>
  );
}
