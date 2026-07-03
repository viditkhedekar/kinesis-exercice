"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AuthCard from "@/components/AuthCard";
import { useAuth } from "@/components/AuthProvider";
import { api, ApiError } from "@/lib/api";

export default function ResetPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("token") ?? "";
    setToken(t);
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.reset(token, password);
      await refresh();
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Reset failed");
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Choose a new password"
      subtitle="Enter a new password for your account."
      footer={
        <Link href="/login" className="text-accent hover:underline">
          Back to log in
        </Link>
      }
    >
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label className="label">New password</label>
          <input className="input mt-1" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoFocus placeholder="At least 8 characters" />
        </div>
        {!token && <p className="text-warn text-sm">Missing or invalid reset link.</p>}
        {error && <p className="text-bad text-sm">{error}</p>}
        <button className="btn-primary w-full" disabled={busy || !token}>
          {busy ? "Updating…" : "Update password"}
        </button>
      </form>
    </AuthCard>
  );
}
