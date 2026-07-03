"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";

/**
 * ⌘K command palette. Opened globally from the AppShell. Actions are a flat list
 * of navigation + exercise shortcuts; typing filters, ↑/↓ moves, ↵ runs.
 */

type Command = {
  id: string;
  label: string;
  hint?: string;
  group: string;
  keywords?: string;
  run: () => void;
};

export default function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Exercises power the "Analyze <exercise>" and "Compare <exercise>" actions.
  const { data: exercises } = useQuery({
    queryKey: ["exercises"],
    queryFn: api.exercises,
    staleTime: 5 * 60_000,
  });

  const commands = useMemo<Command[]>(() => {
    const nav = (id: string, label: string, href: string, hint?: string): Command => ({
      id,
      label,
      hint,
      group: "Navigate",
      run: () => {
        router.push(href);
        onClose();
      },
    });

    const base: Command[] = [
      { ...nav("upload", "Upload a set", "/upload", "N"), group: "Actions" },
      nav("dashboard", "Open dashboard", "/dashboard", "D"),
      nav("history", "Open history & progress", "/history", "H"),
      nav("compare", "Compare sessions", "/compare"),
      nav("settings", "Open settings", "/settings", "S"),
    ];

    const perExercise = (exercises ?? []).flatMap<Command>((e) => [
      {
        id: `analyze-${e.key}`,
        label: `Analyze ${e.name}`,
        group: "Exercises",
        keywords: e.key,
        run: () => {
          router.push(`/upload?exercise=${e.key}`);
          onClose();
        },
      },
      {
        id: `history-${e.key}`,
        label: `${e.name} history`,
        group: "Exercises",
        keywords: e.key,
        run: () => {
          router.push(`/history?exercise=${e.key}`);
          onClose();
        },
      },
    ]);

    return [...base, ...perExercise];
  }, [exercises, router, onClose]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) =>
      `${c.label} ${c.group} ${c.keywords ?? ""}`.toLowerCase().includes(q),
    );
  }, [commands, query]);

  // Reset transient state whenever the palette opens.
  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      // focus after paint so the modal is mounted
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => setActive(0), [query]);

  // Keep the highlighted row scrolled into view.
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-idx="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) return null;

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(results.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      results[active]?.run();
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  }

  // Group results for display while keeping a single flat index for navigation.
  let flat = -1;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[15vh]">
      <div className="absolute inset-0 bg-black/50 animate-fade-in" onClick={onClose} />
      <div
        className="relative w-full max-w-lg rounded-[12px] border border-border-strong bg-surface shadow-2xl animate-fade-in overflow-hidden"
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center gap-2 border-b border-border px-3 h-11">
          <SearchIcon />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search commands and exercises…"
            className="flex-1 bg-transparent text-sm text-fg placeholder:text-faint outline-none"
          />
          <span className="kbd">esc</span>
        </div>

        <div ref={listRef} className="max-h-[52vh] overflow-y-auto py-1.5">
          {results.length === 0 && (
            <div className="px-4 py-8 text-center text-sm text-muted">No matches</div>
          )}
          {["Actions", "Navigate", "Exercises"].map((group) => {
            const rows = results.filter((c) => c.group === group);
            if (rows.length === 0) return null;
            return (
              <div key={group} className="mb-1">
                <div className="eyebrow px-3 py-1.5">{group}</div>
                {rows.map((c) => {
                  flat += 1;
                  const idx = flat;
                  return (
                    <button
                      key={c.id}
                      data-idx={idx}
                      onMouseMove={() => setActive(idx)}
                      onClick={() => c.run()}
                      className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm transition-colors ${
                        idx === active ? "bg-surface-2 text-fg" : "text-muted"
                      }`}
                    >
                      <span className="truncate">{c.label}</span>
                      {c.hint && <span className="kbd">{c.hint}</span>}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function SearchIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" className="text-faint shrink-0">
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5L14 14" strokeLinecap="round" />
    </svg>
  );
}
