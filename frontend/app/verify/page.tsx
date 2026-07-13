"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import AuthCard from "@/components/AuthCard";
import { useAuth } from "@/components/AuthProvider";
import ResendVerification from "@/components/ResendVerification";
import { ApiError } from "@/lib/api";

type State = "loading" | "success" | "error";

function VerifyToken() {
  const token = useSearchParams().get("token") ?? "";
  const { verifyEmail } = useAuth();
  const router = useRouter();
  const [state, setState] = useState<State>("loading");
  const [msg, setMsg] = useState("");
  const ran = useRef(false);

  useEffect(() => {
    // Verification tokens are single-use; guard against React's double-invoke so
    // we don't consume the token and then report it as "already used".
    if (ran.current) return;
    ran.current = true;
    if (!token) {
      setState("error");
      setMsg("This verification link is missing its token.");
      return;
    }
    verifyEmail(token)
      .then(() => {
        setState("success");
        setTimeout(() => router.replace("/onboarding"), 1200);
      })
      .catch((e) => {
        setState("error");
        setMsg(e instanceof ApiError ? e.message : "We couldn't verify this link.");
      });
  }, [token, verifyEmail, router]);

  if (state === "loading") {
    return (
      <AuthCard title="Verifying your email" subtitle="One moment while we confirm your link.">
        <div className="flex items-center gap-3 text-sm text-muted">
          <span className="relative grid h-6 w-6 place-items-center">
            <span className="absolute inset-0 rounded-full border-2 border-border" />
            <span className="absolute inset-0 rounded-full border-2 border-transparent border-t-accent animate-spin" />
          </span>
          Confirming…
        </div>
      </AuthCard>
    );
  }

  if (state === "success") {
    return (
      <AuthCard
        title="Email verified"
        subtitle="You're all set — taking you to your account…"
        footer={
          <Link href="/onboarding" className="text-accent hover:underline">
            Continue
          </Link>
        }
      >
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-good/15 text-good">✓</span>
          <p className="text-sm text-muted">Your email address has been confirmed.</p>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="This link didn't work"
      subtitle={msg}
      footer={
        <>
          Back to{" "}
          <Link href="/login" className="text-accent hover:underline">
            Log in
          </Link>
        </>
      }
    >
      <p className="text-sm text-muted mb-3">Request a fresh verification link:</p>
      <ResendVerification />
    </AuthCard>
  );
}

export default function VerifyPage() {
  return (
    <Suspense fallback={<AuthCard title="Verifying your email" subtitle="Loading…"><span /></AuthCard>}>
      <VerifyToken />
    </Suspense>
  );
}
