import type { Metadata } from "next";
import Link from "next/link";
import { allGuides } from "@/lib/guides";

export const metadata: Metadata = {
  title: "Exercise Guides",
  description:
    "Premium, biomechanics-based technique guides for the squat, deadlift, bench press, bicep curl and lateral raise — the movement library behind physIQal's AI analysis.",
  alternates: { canonical: "/guides" },
};

const DIFFICULTY_DOT: Record<string, string> = {
  Beginner: "bg-good",
  Intermediate: "bg-warn",
  Advanced: "bg-bad",
};

export default function GuidesIndex() {
  const guides = allGuides();
  return (
    <main className="mx-auto max-w-5xl px-5 py-14 sm:px-8 sm:py-20">
      <div className="max-w-2xl">
        <div className="eyebrow mb-2">Movement library</div>
        <h1 className="t-display">Exercise Guides</h1>
        <p className="text-muted mt-4 text-[16px] leading-relaxed">
          Professional, biomechanics-first breakdowns of the lifts physIQal analyses — technique,
          the science behind it, the mistakes that hold you back, and exactly what our AI measures
          in your reps.
        </p>
      </div>

      <div className="mt-12 grid gap-4 sm:grid-cols-2">
        {guides.map((g) => (
          <Link
            key={g.slug}
            href={`/guides/${g.slug}`}
            className="group card flex flex-col p-6 transition hover:border-accent"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="eyebrow">{g.category}</span>
              <span className="inline-flex items-center gap-1.5 text-[12px] text-muted">
                <span className={`h-1.5 w-1.5 rounded-full ${DIFFICULTY_DOT[g.difficulty] ?? "bg-muted"}`} />
                {g.difficulty}
              </span>
            </div>
            <h2 className="t-h3 mt-3 group-hover:text-accent transition">{g.name}</h2>
            <p className="text-muted mt-2 flex-1 text-[14px] leading-relaxed">{g.summary}</p>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {g.primaryMuscles.map((m) => (
                <span key={m} className="rounded-md border border-border bg-surface-2 px-2 py-0.5 text-[12px] text-muted">
                  {m}
                </span>
              ))}
            </div>
            <span className="mt-5 text-[13px] font-medium text-accent">Read the guide →</span>
          </Link>
        ))}
      </div>
    </main>
  );
}
