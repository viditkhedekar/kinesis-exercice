"use client";

import { createContext, useCallback, useContext, useState } from "react";

type Toast = { id: number; message: string; kind: "info" | "error" | "success" };
const ToastCtx = createContext<{ toast: (m: string, k?: Toast["kind"]) => void }>({
  toast: () => {},
});

export function Toaster({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((message: string, kind: Toast["kind"] = "info") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, message, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);

  return (
    <ToastCtx.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-[320px] max-w-[90vw]">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`card px-4 py-3 text-sm shadow-lg animate-fade-in flex items-start gap-2 ${
              t.kind === "error"
                ? "border-bad/50"
                : t.kind === "success"
                  ? "border-good/50"
                  : "border-border"
            }`}
          >
            <span
              className={
                t.kind === "error" ? "text-bad" : t.kind === "success" ? "text-good" : "text-accent"
              }
            >
              {t.kind === "error" ? "✕" : t.kind === "success" ? "✓" : "•"}
            </span>
            <span className="text-fg">{t.message}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);
