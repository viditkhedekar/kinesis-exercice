"use client";

import { useEffect, useState } from "react";

// The onboarding guide (upload pointers + report call-outs) shows only while the
// athlete is going through their first couple of uploads, then gets out of the
// way. We track that count in localStorage so it survives reloads.
const KEY = "kinesis_upload_guide_count";
const GUIDE_UPLOADS = 2;

function readCount(): number {
  if (typeof window === "undefined") return 0;
  const n = Number(window.localStorage.getItem(KEY) ?? "0");
  return Number.isFinite(n) ? n : 0;
}

/** Record that an upload completed (call once per successful analysis). */
export function markUploadDone(): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, String(readCount() + 1));
}

/**
 * Whether the first-runs guide should be shown. Reads localStorage on mount
 * (returns false during SSR / first paint to avoid a hydration mismatch).
 */
export function useUploadGuide(): { active: boolean } {
  const [active, setActive] = useState(false);
  useEffect(() => {
    setActive(readCount() < GUIDE_UPLOADS);
  }, []);
  return { active };
}
