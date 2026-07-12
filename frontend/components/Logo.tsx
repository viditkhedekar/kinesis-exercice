// The physIQal mark — a pose "node figure" (head, hub, hands, hips, feet) drawn
// inline as SVG so it's crisp at any size and needs no asset. Always presented on
// its dark tile with a hairline ring, so the white figure reads on any theme.
export default function LogoMark({
  size = 28,
  className = "",
}: {
  size?: number;
  className?: string;
}) {
  return (
    <span
      className={`inline-grid shrink-0 place-items-center overflow-hidden rounded-[7px] bg-black ring-1 ring-white/10 ${className}`}
      style={{ width: size, height: size }}
      aria-label="physIQal"
      role="img"
    >
      <svg viewBox="0 0 100 100" width={size} height={size} className="h-full w-full">
        <g stroke="#fff" strokeWidth="2.6" strokeLinecap="round" fill="none" opacity="0.85">
          <line x1="50" y1="44" x2="50" y2="24" />
          <line x1="50" y1="44" x2="26" y2="40" />
          <line x1="50" y1="44" x2="74" y2="40" />
          <line x1="50" y1="44" x2="47" y2="64" />
          <line x1="47" y1="64" x2="33" y2="83" />
          <line x1="47" y1="64" x2="61" y2="83" />
        </g>
        <g fill="#fff">
          <circle cx="50" cy="24" r="5" />
          <circle cx="50" cy="44" r="5.6" />
          <circle cx="26" cy="40" r="4.6" />
          <circle cx="74" cy="40" r="4.6" />
          <circle cx="47" cy="64" r="4.8" />
          <circle cx="33" cy="83" r="4.6" />
          <circle cx="61" cy="83" r="4.6" />
        </g>
      </svg>
    </span>
  );
}

// The word lockup: PHYS·IQ·AL with the "IQ" set apart, matching the master logo.
export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-semibold uppercase tracking-[0.12em] ${className}`}>
      PHYS<span className="text-muted">IQ</span>AL
    </span>
  );
}

// Mark + wordmark + tagline, centered — for the landing "brand moment".
export function LogoFull({ className = "" }: { className?: string }) {
  return (
    <div className={`flex flex-col items-center gap-6 text-center ${className}`}>
      <LogoMark size={116} />
      <div>
        <Wordmark className="text-[34px] leading-none" />
        <div className="text-faint text-[12px] tracking-[0.12em] mt-3">
          Intelligence behind every movement.
        </div>
      </div>
    </div>
  );
}
