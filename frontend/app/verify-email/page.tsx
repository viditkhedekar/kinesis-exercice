"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import AuthCard from "@/components/AuthCard";
import ResendVerification from "@/components/ResendVerification";

function CheckInbox() {
  const email = useSearchParams().get("email") ?? "";
  return (
    <AuthCard
      title="Check your inbox"
      subtitle={email ? `We've sent a verification link to ${email}.` : "We've sent you a verification link."}
      footer={
        <>
          Already verified?{" "}
          <Link href="/login" className="text-accent hover:underline">
            Log in
          </Link>
        </>
      }
    >
      <div className="space-y-4">
        <div className="flex items-start gap-3 rounded-lg border border-border bg-surface-2/40 p-3.5">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-accent/10 text-accent">✉</span>
          <p className="text-sm text-muted leading-relaxed">
            Click the link in the email to activate your account. The link expires in 24 hours.
          </p>
        </div>
        <p className="text-sm text-muted">
          Didn&apos;t get it? Check your spam folder, or request a new link below.
        </p>
        <ResendVerification initialEmail={email} initialCooldown={60} />
      </div>
    </AuthCard>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<AuthCard title="Check your inbox" subtitle="Loading…"><span /></AuthCard>}>
      <CheckInbox />
    </Suspense>
  );
}
