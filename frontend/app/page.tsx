"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useTheme } from "@/components/ThemeProvider";
import LogoMark from "@/components/Logo";
import InteractiveDemo from "@/components/demo/InteractiveDemo";

const EXERCISES = [
  "Squat", "Deadlift", "Chest Press", "Shoulder Press", "Cable Row",
  "Lat Pulldown", "Bicep Curl", "Tricep Pushdown", "Lateral Raise", "Push-Up",
];

const HOW = [
  ["Upload", "Record a set using your phone and upload the video."],
  ["Analyse", "Kinesis detects body landmarks, identifies repetitions and measures key movement metrics."],
  ["Review", "Explore an interactive report with video playback, technique scores, joint data and coaching recommendations."],
];

const TRACK = [
  "Technique Score", "Range of Motion", "Movement Symmetry",
  "Rep Consistency", "Tempo", "Common Faults",
];

const FAQ = [
  ["Do I need special equipment?", "No. A standard phone recording is sufficient."],
  ["Is my data stored securely?", "Yes. Uploaded videos and analysis results are associated with your account and can be managed or deleted at any time."],
  ["Can I compare multiple sessions?", "Yes. Track progress across sessions and compare technique over time."],
];

const PRICING = [
  { name: "Free", price: "$0", unit: "forever", features: ["5 analyses / month", "All 10 exercises", "Full report & timeline", "Progress tracking"], cta: "Get started" },
  { name: "Pro", price: "$12", unit: "/ month", features: ["Unlimited analyses", "Ghost Replay", "Compare sessions", "Priority processing"], cta: "Start Pro", featured: true },
  { name: "Team", price: "Custom", unit: "for coaches", features: ["Multiple athletes", "Shared library", "Coach dashboard", "Export & API"], cta: "Contact us" },
];

type DemoPhase = "idle" | "report";

export default function Landing() {
  const { user } = useAuth();
  const { theme, toggle } = useTheme();
  const demoRef = useRef<HTMLDivElement>(null);
  const [demoPhase, setDemoPhase] = useState<DemoPhase>("idle");
  const [demoKey, setDemoKey] = useState(0);

  function showDemo(phase: DemoPhase) {
    setDemoPhase(phase);
    setDemoKey((k) => k + 1);
    setTimeout(() => demoRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 20);
  }

  return (
    <div className="min-h-screen">
      {/* Nav */}
      <header className="sticky top-0 z-30 border-b border-border bg-bg/85 backdrop-blur">
        <div className="mx-auto max-w-6xl px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link href="/" className="flex items-center gap-2">
              <LogoMark size={26} />
              <span className="font-semibold tracking-tight text-[15px]">Kinesis</span>
            </Link>
            <nav className="hidden md:flex items-center gap-6 text-[13px] text-muted">
              <a href="#features" className="hover:text-fg transition">Features</a>
              <a href="#demo" className="hover:text-fg transition">Demo</a>
              <a href="#exercises" className="hover:text-fg transition">Supported Exercises</a>
              <a href="#pricing" className="hover:text-fg transition">Pricing</a>
            </nav>
          </div>
          <div className="flex items-center gap-1.5">
            <button onClick={toggle} className="btn-subtle px-2" aria-label="Toggle theme">{theme === "dark" ? "☾" : "☀"}</button>
            {user ? (
              <Link href="/dashboard" className="btn-primary">Dashboard</Link>
            ) : (
              <>
                <Link href="/login" className="btn-subtle">Sign In</Link>
                <Link href="/signup" className="btn-primary">Sign up</Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-6xl px-6 pt-16 pb-16 sm:pt-20">
        <div className="grid lg:grid-cols-[1.1fr_1fr] gap-10 lg:gap-12 items-center">
          <div>
            <h1 className="t-display">Improve your lifting technique with objective movement analysis.</h1>
            <p className="text-muted mt-4 text-[16px] leading-relaxed max-w-xl">
              Upload a training video and receive frame-by-frame biomechanical feedback based on pose
              estimation and movement analysis. No wearables. No subjective coaching.
            </p>
            <div className="flex items-center gap-2.5 mt-6">
              <button onClick={() => showDemo("idle")} className="btn-primary btn-lg">Try Interactive Demo</button>
              <button onClick={() => showDemo("report")} className="btn-ghost btn-lg">View sample analysis</button>
            </div>
            <p className="t-caption mt-5 max-w-xl leading-relaxed">
              Supports Squat, Deadlift, Bench Press, Shoulder Press, Rows, Bicep Curls, Tricep Pushdowns,
              Lateral Raises, Lat Pulldowns and Push-Ups.
            </p>
          </div>

          {/* Brand moment — the full logo, framed so it reads on any theme */}
          <div className="relative mx-auto w-full max-w-md">
            <div className="pointer-events-none absolute -inset-6 opacity-70 [background:radial-gradient(60%_50%_at_50%_35%,rgb(var(--fg)/0.08),transparent_70%)]" />
            <div className="relative aspect-square overflow-hidden rounded-2xl border border-border bg-black ring-1 ring-white/5">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/kinesis-logo.png"
                alt="Kinesis — Move better. Be better."
                width={720}
                height={720}
                className="h-full w-full object-contain"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Trusted analysis */}
      <section className="mx-auto max-w-6xl px-6 py-12 border-t border-border">
        <div className="eyebrow mb-2">Trusted analysis</div>
        <h2 className="t-h2 max-w-2xl">Designed for athletes, coaches and anyone looking for objective feedback on movement quality.</h2>
        <p className="text-muted text-[15px] leading-relaxed max-w-2xl mt-4">
          Kinesis analyses joint positions throughout each repetition to measure range of motion,
          symmetry, tempo and exercise-specific technique. Every recommendation is linked back to
          measurable data, so you can see exactly why feedback was generated.
        </p>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-6xl px-6 py-12">
        <div className="eyebrow mb-1">How it works</div>
        <h2 className="t-h2 mb-8">Three steps from clip to coaching</h2>
        <ol className="grid sm:grid-cols-3 gap-px bg-border rounded-lg border border-border overflow-hidden">
          {HOW.map(([t, d], i) => (
            <li key={t} className="bg-surface p-5">
              <div className="text-[12px] font-mono text-faint">0{i + 1}</div>
              <div className="font-medium mt-2 text-[15px]">{t}</div>
              <div className="text-muted text-[13px] mt-1.5 leading-relaxed">{d}</div>
            </li>
          ))}
        </ol>
      </section>

      {/* Interactive demo */}
      <section id="demo" ref={demoRef} className="mx-auto max-w-6xl px-6 py-16 scroll-mt-16">
        <div className="eyebrow mb-1">Interactive demo</div>
        <h2 className="t-h2 mb-3">Try a complete analysis using one of our sample videos.</h2>
        <p className="text-muted text-[15px] leading-relaxed max-w-2xl mb-6">
          Explore the timeline, inspect each repetition and see how technique changes throughout the set.
        </p>
        <div className="rounded-xl border border-border bg-surface overflow-hidden">
          <div className="flex items-center gap-2 px-3 h-9 border-b border-border">
            <span className="flex gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-border-strong" />
              <span className="h-2.5 w-2.5 rounded-full bg-border-strong" />
              <span className="h-2.5 w-2.5 rounded-full bg-border-strong" />
            </span>
            <div className="mx-auto flex items-center gap-1.5 rounded-[6px] bg-surface-2 px-3 h-6 text-[12px] text-faint font-mono">
              app.kinesis.io / analysis / squat
            </div>
          </div>
          <div className="p-4 sm:p-5">
            <InteractiveDemo key={demoKey} initialPhase={demoPhase} />
          </div>
        </div>
        <div className="mt-4">
          <button onClick={() => showDemo("idle")} className="btn-primary">Launch Demo</button>
        </div>
      </section>

      {/* Built for real training */}
      <section id="features" className="mx-auto max-w-6xl px-6 py-12 scroll-mt-16">
        <div className="eyebrow mb-2">Built for real training</div>
        <h2 className="t-h2 max-w-2xl">
          Rather than assigning a single score, Kinesis evaluates each repetition individually and
          highlights where technique changes during a set.
        </h2>
        <div className="mt-8">
          <div className="label mb-3">Track</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-px bg-border rounded-lg border border-border overflow-hidden">
            {TRACK.map((t) => (
              <div key={t} className="bg-surface px-4 py-3 text-[14px] font-medium">{t}</div>
            ))}
          </div>
        </div>
      </section>

      {/* Supported exercises */}
      <section id="exercises" className="mx-auto max-w-6xl px-6 py-16 scroll-mt-16">
        <div className="eyebrow mb-1">Supported exercises</div>
        <h2 className="t-h2 mb-6">Current support includes</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-px bg-border rounded-lg border border-border overflow-hidden">
          {EXERCISES.map((e) => (
            <div key={e} className="bg-surface px-4 py-3 text-[14px]">{e}</div>
          ))}
        </div>
        <p className="text-muted text-[13px] mt-4">More exercises can be added as the movement engine expands.</p>
      </section>

      {/* Why Kinesis */}
      <section className="mx-auto max-w-3xl px-6 py-16">
        <div className="eyebrow mb-2">Why Kinesis?</div>
        <h2 className="t-h2">Traditional video review is slow and subjective.</h2>
        <p className="text-muted text-[15px] leading-relaxed mt-4">
          Kinesis provides consistent analysis that can be reviewed immediately after a training
          session. Every recommendation is linked to measurable movement rather than generic advice,
          making it easier to identify recurring issues and monitor improvement over time.
        </p>
      </section>

      {/* Pricing */}
      <section id="pricing" className="mx-auto max-w-6xl px-6 py-16 scroll-mt-16">
        <div className="eyebrow mb-1">Pricing</div>
        <h2 className="t-h2 mb-8">Simple, honest pricing</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {PRICING.map((p) => (
            <div key={p.name} className={`card p-5 flex flex-col ${p.featured ? "border-accent/50" : ""}`}>
              <div className="flex items-center justify-between">
                <span className="font-medium">{p.name}</span>
                {p.featured && <span className="badge border-accent/40 text-accent">Popular</span>}
              </div>
              <div className="mt-3 flex items-baseline gap-1.5">
                <span className="text-[28px] font-semibold tracking-tight">{p.price}</span>
                <span className="t-caption">{p.unit}</span>
              </div>
              <ul className="mt-4 space-y-2 text-[13px] text-muted flex-1">
                {p.features.map((f) => <li key={f} className="flex items-center gap-2"><span className="text-faint">–</span>{f}</li>)}
              </ul>
              <Link href="/signup" className={`mt-5 ${p.featured ? "btn-primary" : "btn-ghost"} w-full`}>{p.cta}</Link>
            </div>
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="mx-auto max-w-3xl px-6 py-16">
        <div className="eyebrow mb-1">FAQ</div>
        <h2 className="t-h2 mb-6">Frequently asked questions</h2>
        <div className="divide-y divide-border border-y border-border">
          {FAQ.map(([q, a]) => (
            <details key={q} className="group py-4">
              <summary className="font-medium cursor-pointer list-none flex items-center justify-between gap-4 text-[14px]">
                {q}
                <span className="text-faint text-lg leading-none group-open:rotate-45 transition shrink-0">+</span>
              </summary>
              <p className="text-muted text-[13px] mt-2.5 leading-relaxed">{a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* Final CTA */}
      <section className="mx-auto max-w-6xl px-6 pb-16">
        <div className="card p-8 sm:p-10 text-center">
          <h2 className="t-h2">Ready to analyse your next session?</h2>
          <p className="text-muted mt-3 max-w-xl mx-auto text-[15px] leading-relaxed">
            Upload your first video in minutes and start building a history of your movement quality.
          </p>
          <div className="flex items-center justify-center gap-2.5 mt-6">
            <Link href={user ? "/dashboard" : "/signup"} className="btn-primary btn-lg">Create Account</Link>
            <button onClick={() => showDemo("idle")} className="btn-ghost btn-lg">Try Demo</button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border">
        <div className="mx-auto max-w-6xl px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-3 text-[13px] text-muted">
          <div className="flex items-center gap-2">
            <LogoMark size={20} />
            Kinesis — movement intelligence
          </div>
          <div className="flex items-center gap-6">
            <a href="#features" className="hover:text-fg transition">Features</a>
            <a href="#exercises" className="hover:text-fg transition">Supported Exercises</a>
            <a href="#pricing" className="hover:text-fg transition">Pricing</a>
            <Link href="/login" className="hover:text-fg transition">Sign In</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
