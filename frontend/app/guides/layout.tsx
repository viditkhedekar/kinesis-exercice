import type { Metadata } from "next";
import Link from "next/link";
import LogoMark, { Wordmark } from "@/components/Logo";

export const metadata: Metadata = {
  title: {
    default: "Exercise Guides — physIQal",
    template: "%s — physIQal Guides",
  },
  description:
    "A movement education library from physIQal: premium, biomechanics-based technique guides for the lifts our AI analyses.",
};

export default function GuidesLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-border bg-bg/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-5 sm:px-8">
          <Link href="/guides" className="flex items-center gap-2">
            <LogoMark size={24} />
            <Wordmark className="text-[14px]" />
            <span className="ml-1 hidden text-[13px] text-muted sm:inline">Guides</span>
          </Link>
          <nav className="flex items-center gap-1.5 text-[13px]">
            <Link href="/guides" className="btn-subtle">All guides</Link>
            <Link href="/dashboard" className="btn-primary">Open app</Link>
          </nav>
        </div>
      </header>

      {children}

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-3 px-5 py-8 text-[13px] text-muted sm:flex-row sm:px-8">
          <div className="flex items-center gap-2">
            <LogoMark size={18} />
            physIQal — intelligence behind every movement
          </div>
          <div className="flex items-center gap-5">
            <Link href="/guides" className="hover:text-fg transition">Guides</Link>
            <Link href="/login" className="hover:text-fg transition">Sign in</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
