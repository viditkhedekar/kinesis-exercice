"use client";

import { useState } from "react";

export default function Dropzone({
  onFile,
  compact,
}: {
  onFile: (file: File) => void;
  compact?: boolean;
}) {
  const [over, setOver] = useState(false);

  function handleFiles(files: FileList | null) {
    const f = files?.[0];
    if (f && f.type.startsWith("video/")) onFile(f);
  }

  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        handleFiles(e.dataTransfer.files);
      }}
      className={`flex flex-col items-center justify-center rounded-xl border border-dashed cursor-pointer transition ${
        over ? "border-accent bg-accent/5" : "border-border hover:border-accent/60 hover:bg-surface-2"
      } ${compact ? "p-6" : "p-10"}`}
    >
      <input type="file" accept="video/*" className="hidden" onChange={(e) => handleFiles(e.target.files)} />
      <div className="grid h-10 w-10 place-items-center rounded-lg bg-accent/10 text-accent mb-2">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 12V3M5.5 6.5 9 3l3.5 3.5M3 12v2.5A1.5 1.5 0 0 0 4.5 16h9a1.5 1.5 0 0 0 1.5-1.5V12" />
        </svg>
      </div>
      <div className="text-sm font-medium">Drag &amp; drop a video, or click to browse</div>
      <div className="label mt-1">mp4 / mov · single athlete in frame</div>
    </label>
  );
}
