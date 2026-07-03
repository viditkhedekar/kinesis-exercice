import Link from "next/link";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

export function CardSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="card p-5 space-y-3">
      <Skeleton className="h-4 w-1/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className="h-3 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: { label: string; href: string };
}) {
  return (
    <div className="card p-10 text-center">
      <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-xl border border-border text-muted">
        ✦
      </div>
      <h3 className="font-semibold">{title}</h3>
      <p className="text-muted text-sm mt-1 max-w-sm mx-auto">{description}</p>
      {action && (
        <Link href={action.href} className="btn-primary mt-4 inline-flex">
          {action.label}
        </Link>
      )}
    </div>
  );
}

export function Stat({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: string;
}) {
  return (
    <div className="card p-4">
      <div className="label">{label}</div>
      <div className="text-2xl font-semibold mt-1 font-mono" style={accent ? { color: accent } : undefined}>
        {value}
      </div>
      {hint && <div className="text-xs text-muted mt-1">{hint}</div>}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-end justify-between gap-4 flex-wrap mb-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="text-muted text-sm mt-1">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}
