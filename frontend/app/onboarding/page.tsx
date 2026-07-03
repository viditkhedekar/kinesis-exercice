"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { api } from "@/lib/api";

const GOALS = [
  "Improve strength",
  "Build muscle",
  "Injury prevention / rehab",
  "Sport performance",
  "Refine technique",
  "General fitness",
];

export default function OnboardingPage() {
  const router = useRouter();
  const { user, loading, updatePrefs } = useAuth();
  const { data: exercises } = useQuery({ queryKey: ["exercises"], queryFn: api.exercises });

  const [step, setStep] = useState(0);
  const [goals, setGoals] = useState<string[]>([]);
  const [picks, setPicks] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else if (user.prefs?.onboarded) router.replace("/dashboard");
  }, [user, loading, router]);

  if (loading || !user || user.prefs?.onboarded) return null;

  const toggle = (arr: string[], v: string, set: (a: string[]) => void) =>
    set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  async function finish(goUpload: boolean) {
    setSaving(true);
    await updatePrefs({ prefs: { onboarded: true, goals, exercises: picks } });
    router.replace(goUpload ? "/upload" : "/dashboard");
  }

  const steps = [
    {
      title: `Welcome${user.name ? `, ${user.name.split(" ")[0]}` : ""} 👋`,
      body: (
        <div className="space-y-4">
          <p className="text-muted">
            Kinesis analyzes your lifts frame-by-frame — pose estimation, rep detection, and a
            biomechanics rule engine — then explains exactly what to fix. Let's tailor it to you. This
            takes under a minute.
          </p>
          <ul className="grid sm:grid-cols-3 gap-3 text-sm">
            {[
              ["Upload", "Drop a clip of any supported lift."],
              ["Analyze", "We score every rep against coaching rules."],
              ["Improve", "Get prioritized, plain-English coaching."],
            ].map(([t, d]) => (
              <li key={t} className="card p-4">
                <div className="font-medium">{t}</div>
                <div className="text-muted text-xs mt-1">{d}</div>
              </li>
            ))}
          </ul>
        </div>
      ),
    },
    {
      title: "What are your goals?",
      body: (
        <div className="flex flex-wrap gap-2">
          {GOALS.map((g) => (
            <button
              key={g}
              onClick={() => toggle(goals, g, setGoals)}
              className={`rounded-lg border px-3 py-2 text-sm transition ${
                goals.includes(g) ? "border-accent bg-accent/10 text-fg" : "border-border text-muted hover:text-fg"
              }`}
            >
              {g}
            </button>
          ))}
        </div>
      ),
    },
    {
      title: "Which exercises do you train most?",
      body: (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {exercises?.map((e) => (
            <button
              key={e.key}
              onClick={() => toggle(picks, e.key, setPicks)}
              className={`rounded-lg border px-3 py-2 text-sm text-left transition ${
                picks.includes(e.key) ? "border-accent bg-accent/10 text-fg" : "border-border text-muted hover:text-fg"
              }`}
            >
              {e.name}
            </button>
          ))}
        </div>
      ),
    },
    {
      title: "You're all set",
      body: (
        <div className="space-y-4">
          <p className="text-muted">
            Your workspace is ready. Upload your first clip now to see a full analysis in under two
            minutes — or head to your dashboard.
          </p>
        </div>
      ),
    },
  ];

  const last = step === steps.length - 1;

  return (
    <div className="min-h-screen grid place-items-center px-4 py-10">
      <div className="w-full max-w-xl">
        <div className="flex items-center gap-1.5 mb-6 justify-center">
          {steps.map((_, i) => (
            <span key={i} className={`h-1.5 rounded-full transition-all ${i <= step ? "w-8 bg-accent" : "w-4 bg-border"}`} />
          ))}
        </div>
        <div className="card p-6 sm:p-8 animate-fade-in">
          <h1 className="text-xl font-semibold mb-4">{steps[step].title}</h1>
          {steps[step].body}

          <div className="flex items-center justify-between mt-8">
            <button
              className="btn-subtle"
              onClick={() => (step === 0 ? finish(false) : setStep((s) => s - 1))}
            >
              {step === 0 ? "Skip" : "Back"}
            </button>
            {last ? (
              <div className="flex gap-2">
                <button className="btn-ghost" onClick={() => finish(false)} disabled={saving}>
                  Go to dashboard
                </button>
                <button className="btn-primary" onClick={() => finish(true)} disabled={saving}>
                  Upload first clip
                </button>
              </div>
            ) : (
              <button className="btn-primary" onClick={() => setStep((s) => s + 1)}>
                Continue
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
