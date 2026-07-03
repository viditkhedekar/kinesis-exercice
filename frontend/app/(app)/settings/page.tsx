"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useTheme } from "@/components/ThemeProvider";
import { useToast } from "@/components/Toaster";
import { PageHeader } from "@/components/ui";
import { api } from "@/lib/api";

const GOALS = ["Improve strength", "Build muscle", "Injury prevention / rehab", "Sport performance", "Refine technique", "General fitness"];

export default function SettingsPage() {
  const { user, updatePrefs } = useAuth();
  const { theme, toggle } = useTheme();
  const { toast } = useToast();
  const { data: exercises } = useQuery({ queryKey: ["exercises"], queryFn: api.exercises });

  const [name, setName] = useState(user?.name ?? "");
  const goals = user?.prefs?.goals ?? [];
  const picks = user?.prefs?.exercises ?? [];

  async function saveName() {
    if (name === user?.name) return;
    await updatePrefs({ name });
    toast("Profile updated", "success");
  }

  async function togglePref(key: "goals" | "exercises", value: string) {
    const current = (key === "goals" ? goals : picks) as string[];
    const next = current.includes(value) ? current.filter((x) => x !== value) : [...current, value];
    await updatePrefs({ prefs: { [key]: next } });
  }

  return (
    <div className="max-w-2xl">
      <PageHeader title="Settings" subtitle="Manage your profile and preferences. Changes save automatically." />

      <div className="space-y-6">
        <section className="card p-5">
          <h3 className="font-semibold mb-4">Profile</h3>
          <div className="space-y-3">
            <div>
              <label className="label">Name</label>
              <input className="input mt-1" value={name} onChange={(e) => setName(e.target.value)} onBlur={saveName} />
            </div>
            <div>
              <label className="label">Email</label>
              <input className="input mt-1 opacity-60" value={user?.email ?? ""} disabled />
            </div>
          </div>
        </section>

        <section className="card p-5">
          <h3 className="font-semibold mb-1">Appearance</h3>
          <p className="text-muted text-sm mb-4">Theme preference is saved on this device.</p>
          <button onClick={toggle} className="btn-ghost">
            {theme === "dark" ? "☾ Dark" : "☀ Light"} — switch to {theme === "dark" ? "light" : "dark"}
          </button>
        </section>

        <section className="card p-5">
          <h3 className="font-semibold mb-4">Goals</h3>
          <div className="flex flex-wrap gap-2">
            {GOALS.map((g) => (
              <button
                key={g}
                onClick={() => togglePref("goals", g)}
                className={`rounded-lg border px-3 py-1.5 text-sm transition ${
                  goals.includes(g) ? "border-accent bg-accent/10 text-fg" : "border-border text-muted hover:text-fg"
                }`}
              >
                {g}
              </button>
            ))}
          </div>
        </section>

        <section className="card p-5">
          <h3 className="font-semibold mb-4">Primary exercises</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {exercises?.map((e) => (
              <button
                key={e.key}
                onClick={() => togglePref("exercises", e.key)}
                className={`rounded-lg border px-3 py-2 text-sm text-left transition ${
                  picks.includes(e.key) ? "border-accent bg-accent/10 text-fg" : "border-border text-muted hover:text-fg"
                }`}
              >
                {e.name}
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
