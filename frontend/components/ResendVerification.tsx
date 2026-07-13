"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { ApiError } from "@/lib/api";
import { isValidEmail } from "@/lib/validation";

// Resend a verification email, with a client-side cooldown that mirrors the
// server's rate limit so the button can't be mashed. Editable email so it works
// both on the "check your inbox" page and the invalid-link error page.
export default function ResendVerification({
  initialEmail = "",
  initialCooldown = 0,
}: {
  initialEmail?: string;
  initialCooldown?: number;
}) {
  const { resendVerification } = useAuth();
  const [email, setEmail] = useState(initialEmail);
  const [cooldown, setCooldown] = useState(initialCooldown);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setInterval(() => setCooldown((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, [cooldown]);

  async function resend() {
    setErr(null);
    setNote(null);
    if (!isValidEmail(email)) {
      setErr("Please enter a valid email address.");
      return;
    }
    if (busy || cooldown > 0) return;
    setBusy(true);
    try {
      const res = await resendVerification(email);
      setNote(res.message);
      setCooldown(res.retry_after || 60);
    } catch (e) {
      if (e instanceof ApiError && e.status === 429) {
        const m = /(\d+)\s*s/.exec(e.message);
        setCooldown(m ? Number(m[1]) : 60);
        setErr(e.message);
      } else {
        setErr(e instanceof ApiError ? e.message : "Couldn't resend right now — try again shortly.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <input
        className="input"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@example.com"
        aria-label="Email address"
      />
      <button className="btn-ghost w-full" disabled={busy || cooldown > 0} onClick={resend}>
        {busy ? "Sending…" : cooldown > 0 ? `Resend available in ${cooldown}s` : "Resend verification email"}
      </button>
      {note && <p className="text-good text-sm">{note}</p>}
      {err && <p className="text-bad text-sm">{err}</p>}
    </div>
  );
}
