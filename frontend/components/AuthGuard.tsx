"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "./AuthProvider";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      const next = encodeURIComponent(pathname);
      router.replace(`/login?next=${next}`);
    } else if (!user.prefs?.onboarded) {
      router.replace("/onboarding");
    }
  }, [user, loading, router, pathname]);

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center">
        <div className="flex items-center gap-3 text-muted">
          <span className="h-4 w-4 rounded-full border-2 border-border border-t-accent animate-spin" />
          Loading…
        </div>
      </div>
    );
  }
  if (!user || !user.prefs?.onboarded) return null; // redirecting

  return <>{children}</>;
}
