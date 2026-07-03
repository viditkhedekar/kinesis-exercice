"use client";

import { useEffect, useRef, useState } from "react";
import { videoUrl } from "@/lib/api";
import { frameForTime, renderOverlay } from "@/lib/poseOverlay";
import type { Ghost, Landmarks, Rep, RepFault } from "@/lib/types";

interface Props {
  sessionId: number;
  landmarks: Landmarks;
  reps: Rep[];
  faults: RepFault[];
  ghost: Ghost | null;
  showGhost: boolean;
  videoRef: React.RefObject<HTMLVideoElement>;
  onFrame?: (frame: number) => void;
}

export default function PlayerOverlay({
  sessionId,
  landmarks,
  reps,
  faults,
  ghost,
  showGhost,
  videoRef,
  onFrame,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const lastFrameRef = useRef(-1);
  const [dims, setDims] = useState({ w: 640, h: 360 });

  // Keep the canvas pixel size matched to the rendered video box.
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const ro = new ResizeObserver(() => {
      setDims({ w: wrap.clientWidth, h: wrap.clientHeight });
    });
    ro.observe(wrap);
    return () => ro.disconnect();
  }, []);

  // Draw loop synced to the video clock.
  useEffect(() => {
    let raf = 0;
    const draw = () => {
      const canvas = canvasRef.current;
      const video = videoRef.current;
      if (canvas && video) {
        const ctx = canvas.getContext("2d");
        if (ctx) {
          const frame = frameForTime(video.currentTime, landmarks.fps, landmarks.frames.length);
          renderOverlay(ctx, canvas.width, canvas.height, landmarks, frame, ghost, reps, showGhost, faults);
          if (frame !== lastFrameRef.current) {
            lastFrameRef.current = frame;
            onFrame?.(frame);
          }
        }
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [landmarks, ghost, reps, faults, showGhost, videoRef, onFrame]);

  return (
    <div ref={wrapRef} className="relative w-full aspect-video bg-black rounded-lg overflow-hidden">
      <video
        ref={videoRef}
        src={videoUrl(sessionId)}
        controls
        playsInline
        className="absolute inset-0 w-full h-full object-contain"
      />
      <canvas
        ref={canvasRef}
        width={dims.w}
        height={dims.h}
        className="absolute inset-0 w-full h-full pointer-events-none"
      />
    </div>
  );
}
