"use client";

import type { ReactNode } from "react";

/**
 * A floating onboarding pop-up, fixed to the bottom-centre of the viewport so it's
 * clearly visible the moment you enter a page. Used during the first couple of
 * uploads to point out what to do. Dismissible; auto-updates as the user progresses.
 */
export default function GuidePopup({
  step,
  total,
  title,
  children,
  onDismiss,
  cta = "Got it",
}: {
  step: number;
  total?: number;
  title: string;
  children?: ReactNode;
  onDismiss: () => void;
  cta?: string;
}) {
  return (
    <div className="fixed inset-x-0 bottom-6 z-[60] flex justify-center px-4 pointer-events-none">
      <div className="guide-pop pointer-events-auto" role="dialog" aria-label={title}>
        <div className="flex items-start gap-3">
          <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-accent text-accent-fg text-[12px] font-semibold">
            {step}
          </span>
          <div className="min-w-0 flex-1">
            <div className="font-semibold">{title}</div>
            {children && <div className="text-sm text-muted mt-0.5">{children}</div>}
            <div className="mt-3 flex items-center gap-3">
              <button className="btn-primary h-8" onClick={onDismiss}>{cta}</button>
              {total && <span className="text-xs text-faint">Tip {step} of {total}</span>}
            </div>
          </div>
          <button
            aria-label="Dismiss guide"
            onClick={onDismiss}
            className="btn-subtle h-7 w-7 -mt-1 -mr-1 grid place-items-center shrink-0"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  );
}
