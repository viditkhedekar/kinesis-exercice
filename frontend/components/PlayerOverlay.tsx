"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { videoUrl } from "@/lib/api";
import { frameForTime, renderOverlay } from "@/lib/poseOverlay";
import type { Ghost, Landmarks, Rep, RepFault } from "@/lib/types";

export interface PlayerHandle {
  seek: (timeSeconds: number) => void;
}

interface Props {
  sessionId: number;
  /** When false, the raw clip was deleted — play the skeleton overlay on its own clock. */
  hasVideo: boolean;
  landmarks: Landmarks;
  reps: Rep[];
  faults: RepFault[];
  ghost: Ghost | null;
  showGhost: boolean;
  onFrame?: (frame: number) => void;
}

const PlayerOverlay = forwardRef<PlayerHandle, Props>(function PlayerOverlay(
  { sessionId, hasVideo, landmarks, reps, faults, ghost, showGhost, onFrame },
  ref,
) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const lastFrameRef = useRef(-1);
  const [dims, setDims] = useState({ w: 640, h: 360 });

  // Skeleton-mode playback clock (used only when there's no video).
  const frameRef = useRef(0);
  const [playing, setPlaying] = useState(false);
  const totalFrames = landmarks.frames.length;

  useImperativeHandle(
    ref,
    () => ({
      seek: (t: number) => {
        if (hasVideo && videoRef.current) {
          videoRef.current.currentTime = t;
          videoRef.current.pause();
        } else {
          frameRef.current = Math.max(0, Math.min(totalFrames - 1, Math.round(t * landmarks.fps)));
          setPlaying(false);
        }
      },
    }),
    [hasVideo, landmarks.fps, totalFrames],
  );

  // Keep the canvas pixel size matched to the rendered box.
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const ro = new ResizeObserver(() => setDims({ w: wrap.clientWidth, h: wrap.clientHeight }));
    ro.observe(wrap);
    return () => ro.disconnect();
  }, []);

  // Draw loop — synced to the video clock when there's a video, else our own clock.
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    const draw = (now: number) => {
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      if (canvas && ctx) {
        let frame: number;
        if (hasVideo) {
          const video = videoRef.current;
          frame = video ? frameForTime(video.currentTime, landmarks.fps, totalFrames) : 0;
        } else {
          if (playing && totalFrames > 0) {
            frameRef.current += ((now - last) / 1000) * landmarks.fps;
            if (frameRef.current >= totalFrames) frameRef.current = 0; // loop
          }
          frame = Math.max(0, Math.min(totalFrames - 1, Math.floor(frameRef.current)));
        }
        renderOverlay(ctx, canvas.width, canvas.height, landmarks, frame, ghost, reps, showGhost, faults);
        if (frame !== lastFrameRef.current) {
          lastFrameRef.current = frame;
          onFrame?.(frame);
        }
      }
      last = now;
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [hasVideo, landmarks, ghost, reps, faults, showGhost, playing, totalFrames, onFrame]);

  return (
    <div ref={wrapRef} className="relative w-full aspect-video bg-black rounded-lg overflow-hidden">
      {hasVideo ? (
        <video
          ref={videoRef}
          src={videoUrl(sessionId)}
          controls
          playsInline
          className="absolute inset-0 w-full h-full object-contain"
        />
      ) : (
        <button
          type="button"
          onClick={() => setPlaying((p) => !p)}
          aria-label={playing ? "Pause" : "Play"}
          className="absolute inset-0 z-10 grid place-items-center group"
        >
          {!playing && (
            <span className="grid h-14 w-14 place-items-center rounded-full bg-black/50 text-white text-xl transition group-hover:bg-black/70">
              ▶
            </span>
          )}
        </button>
      )}
      <canvas
        ref={canvasRef}
        width={dims.w}
        height={dims.h}
        className="absolute inset-0 w-full h-full pointer-events-none"
      />
      {!hasVideo && (
        <span className="absolute top-2 left-2 z-10 badge border-transparent bg-black/55 text-white/90">
          Analysis only · video removed
        </span>
      )}
    </div>
  );
});

export default PlayerOverlay;
