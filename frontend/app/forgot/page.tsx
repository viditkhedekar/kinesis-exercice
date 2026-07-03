"use client";

import Link from "next/link";
import { useState } from "react";
import AuthCard from "@/components/AuthCard";
import { api } from "@/lib/api";

export default function ForgotPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await api.forgot(email);
      setToken(res.token);
      setDone(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Reset your password"
      subtitle="Enter your email and we'll start the reset."
      footer={
        <Link href="/login" className="text-accent hover:underline">
          Back to log in
        </Link>
      }
    >
      {done ? (
        <div className="space-y-3 text-sm">
          <p className="text-fg">If an account exists for {email}, a reset link has been issued.</p>
          {/* No email service in this build — surface the reset link directly. */}
          {token && (
            <Link href={`/reset?token=${encodeURIComponent(token)}`} className="btn-primary w-full">
              Continue to reset password
            </Link>
          )}
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="label">Email</label>
            <input className="input mt-1" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
          </div>
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Sending…" : "Send reset link"}
          </button>
        </form>
      )}
    </AuthCard>
  );
}
