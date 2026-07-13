import Link from "next/link";
import type { GuideData } from "@/lib/guides/types";
import DemoPlaceholder from "./DemoPlaceholder";
import GuideToc, { type TocItem } from "./GuideToc";
import Reveal from "./Reveal";
import ScrollProgress from "./ScrollProgress";

const TOC: TocItem[] = [
  { id: "overview", label: "Overview" },
  { id: "walkthrough", label: "Walkthrough" },
  { id: "biomechanics", label: "Biomechanics" },
  { id: "mistakes", label: "Common mistakes" },
  { id: "analysis", label: "AI analysis" },
  { id: "coaching", label: "Coaching tips" },
  { id: "safety", label: "Safety" },
  { id: "faqs", label: "FAQs" },
  { id: "related", label: "Related guides" },
];

const DIFFICULTY_DOT: Record<string, string> = {
  Beginner: "bg-good",
  Intermediate: "bg-warn",
  Advanced: "bg-bad",
};

export default function GuideArticle({
  guide,
  related,
}: {
  guide: GuideData;
  related: GuideData[];
}) {
  return (
    <article className="mx-auto max-w-5xl px-5 sm:px-8 py-10 sm:py-14">
      <ScrollProgress />

      {/* Hero */}
      <header id="overview" className="scroll-mt-24">
        <Link href="/guides" className="text-[13px] text-muted hover:text-fg transition">
          ← Exercise Guides
        </Link>
        <div className="mt-4 flex flex-wrap items-center gap-2 text-[12px]">
          <span className="eyebrow">{guide.category}</span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-2 py-0.5 text-muted">
            <span className={`h-1.5 w-1.5 rounded-full ${DIFFICULTY_DOT[guide.difficulty] ?? "bg-muted"}`} />
            {guide.difficulty}
          </span>
        </div>
        <h1 className="t-display mt-3">{guide.name}</h1>
        <p className="text-muted mt-4 max-w-2xl text-[16px] leading-relaxed">{guide.intro}</p>

        <dl className="mt-7 grid gap-x-8 gap-y-5 sm:grid-cols-3">
          <MetaBlock label="Primary muscles" items={guide.primaryMuscles} />
          <MetaBlock label="Also works" items={guide.secondaryMuscles} muted />
          <MetaBlock label="Equipment" items={guide.equipment} muted />
        </dl>

        {guide.exerciseKey && (
          <div className="mt-7">
            <Link href={`/upload?exercise=${guide.exerciseKey}`} className="btn-primary">
              Analyse your {guide.name.toLowerCase()}
            </Link>
          </div>
        )}
      </header>

      {/* Demonstration */}
      <Reveal className="mt-10">
        <DemoPlaceholder caption={guide.demoCaption} />
      </Reveal>

      {/* Body: sticky ToC + content */}
      <div className="mt-14 grid gap-10 lg:grid-cols-[minmax(0,1fr)_190px]">
        <div className="min-w-0 space-y-16">
          <Walkthrough guide={guide} />
          <Biomechanics guide={guide} />
          <Mistakes guide={guide} />
          <AiFocus guide={guide} />
          <Coaching guide={guide} />
          <Safety guide={guide} />
          <Faqs guide={guide} />
          <Related related={related} />
        </div>

        <aside className="order-first hidden lg:order-last lg:block">
          <div className="sticky top-10">
            <GuideToc items={TOC} />
          </div>
        </aside>
      </div>
    </article>
  );
}

/* --------------------------------- pieces --------------------------------- */

function MetaBlock({ label, items, muted = false }: { label: string; items: string[]; muted?: boolean }) {
  return (
    <div>
      <dt className="label mb-1.5">{label}</dt>
      <dd className="flex flex-wrap gap-1.5">
        {items.map((m) => (
          <span
            key={m}
            className={`rounded-md border px-2 py-0.5 text-[12px] ${
              muted ? "border-border text-muted" : "border-border bg-surface-2 text-fg"
            }`}
          >
            {m}
          </span>
        ))}
      </dd>
    </div>
  );
}

function SectionHead({ eyebrow, title, blurb }: { eyebrow: string; title: string; blurb?: string }) {
  return (
    <div className="mb-6 max-w-2xl">
      <div className="eyebrow mb-1.5">{eyebrow}</div>
      <h2 className="t-h2">{title}</h2>
      {blurb && <p className="text-muted mt-2 text-[15px] leading-relaxed">{blurb}</p>}
    </div>
  );
}

function Walkthrough({ guide }: { guide: GuideData }) {
  return (
    <section id="walkthrough" aria-labelledby="walkthrough-h" className="scroll-mt-24">
      <SectionHead eyebrow="Technique" title="Step-by-step walkthrough" blurb="The full movement, phase by phase." />
      <span id="walkthrough-h" className="sr-only">
        Step-by-step walkthrough
      </span>
      <ol className="space-y-3">
        {guide.steps.map((s, i) => (
          <li key={s.phase}>
            <Reveal delay={i * 40} className="card block p-5 sm:p-6">
              <div className="flex items-baseline gap-3">
                <span className="font-mono text-[12px] text-faint tabular-nums">{String(i + 1).padStart(2, "0")}</span>
                <h3 className="text-[15px] font-semibold">{s.phase}</h3>
              </div>
              <p className="text-muted mt-2 text-[14px] leading-relaxed">{s.body}</p>
              {s.cues && s.cues.length > 0 && (
                <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
                  {s.cues.map((c) => (
                    <li key={c} className="flex items-center gap-1.5 text-[13px] text-fg/90">
                      <span className="text-accent">›</span>
                      {c}
                    </li>
                  ))}
                </ul>
              )}
            </Reveal>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Biomechanics({ guide }: { guide: GuideData }) {
  return (
    <section id="biomechanics" aria-labelledby="biomechanics-h" className="scroll-mt-24">
      <SectionHead eyebrow="The science, simply" title="Key biomechanics" />
      <span id="biomechanics-h" className="sr-only">
        Key biomechanics
      </span>
      <div className="grid gap-3 sm:grid-cols-2">
        {guide.biomechanics.map((b, i) => (
          <Reveal key={b.title} delay={i * 40}>
            <div className="card h-full p-5">
              <h3 className="text-[14px] font-semibold">{b.title}</h3>
              <p className="text-muted mt-1.5 text-[13px] leading-relaxed">{b.body}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

function Mistakes({ guide }: { guide: GuideData }) {
  return (
    <section id="mistakes" aria-labelledby="mistakes-h" className="scroll-mt-24">
      <SectionHead eyebrow="Fix these first" title="Common mistakes" blurb="Why each happens, what it costs you, and exactly how to fix it." />
      <span id="mistakes-h" className="sr-only">
        Common mistakes
      </span>
      <div className="divide-y divide-border overflow-hidden rounded-xl border border-border">
        {guide.mistakes.map((m, i) => (
          <details key={m.title} className="group" open={i === 0}>
            <summary className="flex cursor-pointer list-none items-center gap-3 p-4 sm:p-5 hover:bg-surface-2/50 transition">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-bad/12 text-bad text-[12px] font-semibold">
                {i + 1}
              </span>
              <span className="flex-1 text-[14px] font-medium">{m.title}</span>
              <span className="text-faint text-lg leading-none transition group-open:rotate-45">+</span>
            </summary>
            <div className="grid gap-3 px-4 pb-5 pt-0 sm:grid-cols-3 sm:px-5 sm:pl-14">
              <Detail label="Why it happens" body={m.why} />
              <Detail label="Why it matters" body={m.impact} tone="bad" />
              <Detail label="How to fix it" body={m.fix} tone="good" />
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}

function Detail({ label, body, tone }: { label: string; body: string; tone?: "good" | "bad" }) {
  const color = tone === "good" ? "text-good" : tone === "bad" ? "text-bad" : "text-faint";
  return (
    <div>
      <div className={`label mb-1 ${color}`}>{label}</div>
      <p className="text-muted text-[13px] leading-relaxed">{body}</p>
    </div>
  );
}

function AiFocus({ guide }: { guide: GuideData }) {
  return (
    <section id="analysis" aria-labelledby="analysis-h" className="scroll-mt-24">
      <SectionHead
        eyebrow="Physiqal AI"
        title="What our analysis looks for"
        blurb="When you upload a clip of this lift, the Physiqal engine measures these signals frame by frame."
      />
      <span id="analysis-h" className="sr-only">
        What the Physiqal AI looks for
      </span>
      <div className="grid gap-3 sm:grid-cols-2">
        {guide.aiFocus.map((a, i) => (
          <Reveal key={a.label} delay={i * 30}>
            <div className="flex gap-3 rounded-xl border border-border bg-surface p-4">
              <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-accent/10 text-accent text-[13px]">
                ◈
              </span>
              <div>
                <div className="text-[14px] font-medium">{a.label}</div>
                <p className="text-muted mt-1 text-[13px] leading-relaxed">{a.detail}</p>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

function Coaching({ guide }: { guide: GuideData }) {
  return (
    <section id="coaching" aria-labelledby="coaching-h" className="scroll-mt-24">
      <SectionHead eyebrow="Progression" title="Coaching tips" blurb="How to get more from the lift as you advance." />
      <span id="coaching-h" className="sr-only">
        Coaching tips
      </span>
      <div className="grid gap-3 sm:grid-cols-3">
        {guide.coaching.map((tier, i) => (
          <Reveal key={tier.level} delay={i * 50}>
            <div className="card h-full p-5">
              <div className="text-[13px] font-semibold">{tier.level}</div>
              <ul className="mt-3 space-y-2">
                {tier.tips.map((t) => (
                  <li key={t} className="flex gap-2 text-[13px] text-muted leading-relaxed">
                    <span className="mt-0.5 text-accent">›</span>
                    <span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

function Safety({ guide }: { guide: GuideData }) {
  return (
    <section id="safety" aria-labelledby="safety-h" className="scroll-mt-24">
      <SectionHead eyebrow="Train hard, stay healthy" title="Safety considerations" />
      <span id="safety-h" className="sr-only">
        Safety considerations
      </span>
      <ul className="grid gap-2.5 sm:grid-cols-2">
        {guide.safety.map((s) => (
          <li key={s} className="flex gap-2.5 rounded-lg border border-border bg-surface p-3.5 text-[13px] text-muted leading-relaxed">
            <span className="mt-0.5 text-warn">▲</span>
            <span>{s}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Faqs({ guide }: { guide: GuideData }) {
  return (
    <section id="faqs" aria-labelledby="faqs-h" className="scroll-mt-24">
      <SectionHead eyebrow="Answers" title="Frequently asked questions" />
      <span id="faqs-h" className="sr-only">
        Frequently asked questions
      </span>
      <div className="divide-y divide-border border-y border-border">
        {guide.faqs.map((f) => (
          <details key={f.q} className="group py-4">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[14px] font-medium">
              {f.q}
              <span className="text-faint text-lg leading-none transition group-open:rotate-45 shrink-0">+</span>
            </summary>
            <p className="text-muted mt-2.5 text-[13px] leading-relaxed">{f.a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

function Related({ related }: { related: GuideData[] }) {
  if (!related.length) return null;
  return (
    <section id="related" aria-labelledby="related-h" className="scroll-mt-24">
      <SectionHead eyebrow="Keep learning" title="Related guides" />
      <span id="related-h" className="sr-only">
        Related guides
      </span>
      <div className="grid gap-3 sm:grid-cols-2">
        {related.map((g) => (
          <Link key={g.slug} href={`/guides/${g.slug}`} className="card p-5 transition hover:border-accent">
            <div className="eyebrow">{g.category}</div>
            <div className="mt-1 text-[15px] font-semibold">{g.name}</div>
            <p className="text-muted mt-1.5 text-[13px] leading-relaxed">{g.summary}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
