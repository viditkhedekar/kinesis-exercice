import Link from "next/link";
import LogoMark from "./Logo";

export default function AuthCard({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="min-h-screen grid place-items-center px-4 py-10">
      <div className="w-full max-w-sm">
        <Link href="/" className="flex flex-col items-center gap-2.5 mb-6">
          <LogoMark size={44} className="rounded-[10px]" />
          <span className="flex flex-col items-center">
            <span className="font-semibold text-lg tracking-tight">Kinesis</span>
            <span className="eyebrow mt-0.5">Move better. Be better.</span>
          </span>
        </Link>
        <div className="card p-6">
          <h1 className="text-lg font-semibold">{title}</h1>
          <p className="text-muted text-sm mt-1 mb-5">{subtitle}</p>
          {children}
        </div>
        {footer && <div className="text-center text-sm text-muted mt-4">{footer}</div>}
      </div>
    </div>
  );
}
