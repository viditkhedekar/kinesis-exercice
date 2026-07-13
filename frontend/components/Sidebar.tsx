"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";
import LogoMark, { Wordmark } from "./Logo";
import ThemeToggle from "./ThemeToggle";

type NavItem = { href: string; label: string; icon: React.ComponentType; badge?: string };

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: GridIcon },
  { href: "/camera", label: "Live Camera", icon: CameraIcon, badge: "Refining" },
  { href: "/guides", label: "Exercise Guides", icon: BookIcon },
  { href: "/history", label: "History & Progress", icon: ChartIcon },
  { href: "/settings", label: "Settings", icon: GearIcon },
];

export default function Sidebar({
  onNavigate,
  onOpenPalette,
}: {
  onNavigate?: () => void;
  onOpenPalette?: () => void;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <div className="flex h-full flex-col gap-1 p-3">
      <Link href="/dashboard" onClick={onNavigate} className="flex items-center gap-2 px-2 py-3">
        <LogoMark size={28} />
        <Wordmark className="text-[15px]" />
      </Link>

      <button
        onClick={onOpenPalette}
        className="flex items-center gap-2 rounded-[8px] border border-border bg-surface-2/60 px-2.5 h-8 text-[13px] text-faint hover:text-muted hover:border-border-strong transition mb-1"
      >
        <SearchIcon />
        <span>Search…</span>
        <span className="ml-auto flex items-center gap-0.5">
          <span className="kbd">⌘</span>
          <span className="kbd">K</span>
        </span>
      </button>

      <Link
        href="/upload"
        onClick={onNavigate}
        className="btn-primary w-full mt-1 mb-2"
        title="New analysis (n)"
      >
        <PlusIcon />
        New analysis
      </Link>

      <nav className="flex flex-col gap-0.5">
        {NAV.map(({ href, label, icon: Icon, badge }) => (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
              isActive(href)
                ? "bg-surface-2 text-fg font-medium"
                : "text-muted hover:text-fg hover:bg-surface-2"
            }`}
          >
            <Icon />
            {label}
            {badge && (
              <span className="ml-auto self-end rounded-[5px] border border-orange-500/40 bg-orange-500/15 px-1.5 py-px text-[10px] font-medium leading-none text-orange-500">
                {badge}
              </span>
            )}
          </Link>
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-2 pt-3">
        <ThemeToggle />
        <div className="rounded-lg border border-border p-3">
          <div className="text-sm font-medium truncate">{user?.name || "Athlete"}</div>
          <div className="text-xs text-muted truncate">{user?.email}</div>
          <button
            onClick={async () => {
              await logout();
              router.push("/login");
            }}
            className="btn-subtle mt-2 w-full justify-start text-xs"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}

/* — minimal inline icons (stroke = currentColor) — */
function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M8 3v10M3 8h10" />
    </svg>
  );
}
function SearchIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" className="shrink-0">
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5L14 14" strokeLinecap="round" />
    </svg>
  );
}
function CameraIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="1.5" y="4" width="13" height="9" rx="1.5" />
      <path d="M5 4l1-1.5h4L11 4" />
      <circle cx="8" cy="8.5" r="2.3" />
    </svg>
  );
}
function BookIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 3.5C6.8 2.6 5.3 2.3 3 2.5v9c2.3-.2 3.8.1 5 1 1.2-.9 2.7-1.2 5-1v-9c-2.3-.2-3.8.1-5 1Z" />
      <path d="M8 3.5v9" />
    </svg>
  );
}
function GridIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6">
      <rect x="2" y="2" width="5" height="5" rx="1" /><rect x="9" y="2" width="5" height="5" rx="1" />
      <rect x="2" y="9" width="5" height="5" rx="1" /><rect x="9" y="9" width="5" height="5" rx="1" />
    </svg>
  );
}
function ChartIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 13h12M4 11V7M8 11V4M12 11V9" />
    </svg>
  );
}
function GearIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <circle cx="8" cy="8" r="2.2" />
      <path d="M8 1.5v1.7M8 12.8v1.7M1.5 8h1.7M12.8 8h1.7M3.4 3.4l1.2 1.2M11.4 11.4l1.2 1.2M12.6 3.4l-1.2 1.2M4.6 11.4l-1.2 1.2" />
    </svg>
  );
}
