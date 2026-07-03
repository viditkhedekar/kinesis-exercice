"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import CommandPalette from "./CommandPalette";
import Sidebar from "./Sidebar";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const router = useRouter();

  // Global keyboard shortcuts.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // ⌘K / Ctrl-K opens the command palette from anywhere, even mid-typing.
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
        return;
      }
      const el = e.target as HTMLElement;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      // Single-key nav is ignored while typing in a field.
      if (["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName) || el.isContentEditable) return;
      const go: Record<string, string> = { n: "/upload", d: "/dashboard", h: "/history", s: "/settings" };
      if (go[e.key]) {
        e.preventDefault();
        router.push(go[e.key]);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router]);

  return (
    <div className="min-h-screen">
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />

      {/* Desktop sidebar */}
      <aside className="hidden lg:block fixed inset-y-0 left-0 w-64 border-r border-border bg-surface">
        <Sidebar onOpenPalette={() => setPaletteOpen(true)} />
      </aside>

      {/* Mobile top bar */}
      <div className="lg:hidden sticky top-0 z-30 flex items-center justify-between border-b border-border bg-surface/90 backdrop-blur px-4 h-14">
        <button onClick={() => setOpen(true)} className="btn-subtle px-2" aria-label="Open menu">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M3 6h14M3 10h14M3 14h14" />
          </svg>
        </button>
        <span className="font-semibold">Kinesis</span>
        <span className="w-8" />
      </div>

      {/* Mobile drawer */}
      {open && (
        <div className="lg:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/50 animate-fade-in" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-surface border-r border-border animate-fade-in">
            <Sidebar
              onNavigate={() => setOpen(false)}
              onOpenPalette={() => {
                setOpen(false);
                setPaletteOpen(true);
              }}
            />
          </div>
        </div>
      )}

      <main className="lg:pl-64">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 py-6 sm:py-8">{children}</div>
      </main>
    </div>
  );
}
