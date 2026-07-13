// Animated-demonstration placeholder. A framed 16:9 panel with the brand pose
// "node figure" and a soft breathing glow — a tasteful stand-in for the video /
// interactive illustration that will slot in here later.
export default function DemoPlaceholder({ caption }: { caption?: string }) {
  return (
    <figure className="relative aspect-video w-full overflow-hidden rounded-2xl border border-border bg-black ring-1 ring-white/5">
      {/* soft radial vignette */}
      <div className="pointer-events-none absolute inset-0 [background:radial-gradient(60%_60%_at_50%_45%,rgb(255_255_255/0.06),transparent_70%)]" />
      {/* breathing glow behind the figure */}
      <div className="pointer-events-none absolute left-1/2 top-1/2 h-40 w-40 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/10 blur-3xl animate-pulse" />

      <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full border border-white/10 bg-black/50 px-2.5 py-1 backdrop-blur">
        <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
        <span className="text-[11px] font-medium tracking-wide text-white/80">Demonstration</span>
      </div>

      <div className="absolute inset-0 grid place-items-center">
        <svg viewBox="0 0 100 100" className="h-1/2 w-1/2 opacity-90" aria-hidden>
          <g stroke="#fff" strokeWidth="2.4" strokeLinecap="round" fill="none" opacity="0.85">
            <line x1="50" y1="44" x2="50" y2="24" />
            <line x1="50" y1="44" x2="26" y2="40" />
            <line x1="50" y1="44" x2="74" y2="40" />
            <line x1="50" y1="44" x2="47" y2="64" />
            <line x1="47" y1="64" x2="33" y2="83" />
            <line x1="47" y1="64" x2="61" y2="83" />
          </g>
          <g fill="#fff">
            <circle cx="50" cy="24" r="4.6" />
            <circle cx="50" cy="44" r="5.2" />
            <circle cx="26" cy="40" r="4.2" />
            <circle cx="74" cy="40" r="4.2" />
            <circle cx="47" cy="64" r="4.4" />
            <circle cx="33" cy="83" r="4.2" />
            <circle cx="61" cy="83" r="4.2" />
          </g>
        </svg>
      </div>

      {caption && (
        <figcaption className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-3 text-[12px] text-white/70">
          {caption}
        </figcaption>
      )}
    </figure>
  );
}
