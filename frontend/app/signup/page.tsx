"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import AuthCard from "@/components/AuthCard";
import { useAuth } from "@/components/AuthProvider";
import { ApiError } from "@/lib/api";
import { isValidEmail } from "@/lib/validation";

export default function SignupPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!isValidEmail(email)) {
      setError("Please enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      await register(email, name, password);
      // Account created but unverified — send them to confirm their inbox.
      router.replace(`/verify-email?email=${encodeURIComponent(email.trim())}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign up failed");
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Create your account"
      subtitle="Start analyzing your technique in minutes."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="text-accent hover:underline">
            Log in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label className="label">Name</label>
          <input className="input mt-1" value={name} onChange={(e) => setName(e.target.value)} placeholder="Alex Coach" autoFocus />
        </div>
        <div>
          <label className="label">Email</label>
          <input className="input mt-1" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div>
          <label className="label">Password</label>
          <input className="input mt-1" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required placeholder="At least 8 characters" />
        </div>
        {error && <p className="text-bad text-sm">{error}</p>}
        <button className="btn-primary w-full" disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>
    </AuthCard>
  );
}
