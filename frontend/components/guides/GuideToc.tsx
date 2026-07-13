"use client";

import { useEffect, useState } from "react";

export interface TocItem {
  id: string;
  label: string;
}

// Sticky table of contents (desktop) with scroll-spy: highlights the section
// currently in view and smooth-scrolls on click.
export default function GuideToc({ items }: { items: TocItem[] }) {
  const [active, setActive] = useState(items[0]?.id ?? "");

  useEffect(() => {
    const sections = items
      .map((i) => document.getElementById(i.id))
      .filter((el): el is HTMLElement => Boolean(el));
    if (!sections.length) return;

    const io = new IntersectionObserver(
      (entries) => {
        // Pick the entry nearest the top that's intersecting.
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-20% 0px -70% 0px", threshold: [0, 1] },
    );
    sections.forEach((s) => io.observe(s));
    return () => io.disconnect();
  }, [items]);

  const go = (id: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      history.replaceState(null, "", `#${id}`);
    }
  };

  return (
    <nav aria-label="On this page" className="text-[13px]">
      <div className="label mb-3">On this page</div>
      <ul className="space-y-0.5 border-l border-border">
        {items.map((i) => {
          const on = active === i.id;
          return (
            <li key={i.id}>
              <a
                href={`#${i.id}`}
                onClick={go(i.id)}
                className={`-ml-px block border-l-2 py-1.5 pl-3 transition ${
                  on
                    ? "border-accent text-fg font-medium"
                    : "border-transparent text-muted hover:text-fg hover:border-border-strong"
                }`}
              >
                {i.label}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
