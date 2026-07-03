import type { Config } from "tailwindcss";

// All colors are CSS-variable-backed (RGB channel triplets) so the same
// utilities theme automatically between dark (default) and light.
const c = (v: string) => `rgb(var(${v}) / <alpha-value>)`;

const config: Config = {
  darkMode: ["class", ".light"], // see globals.css; default (no class) = dark
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: c("--bg"),
        surface: c("--surface"),
        "surface-2": c("--surface-2"),
        border: c("--border"),
        "border-strong": c("--border-strong"),
        fg: c("--fg"),
        muted: c("--muted"),
        faint: c("--faint"),
        accent: c("--accent"),
        "accent-fg": c("--accent-fg"),
        good: c("--good"),
        warn: c("--warn"),
        bad: c("--bad"),
        // Legacy aliases so existing components theme automatically.
        ink: c("--bg"),
        panel: c("--surface"),
        edge: c("--border"),
        "accent-2": c("--accent"),
        accent2: c("--accent"),
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        DEFAULT: "6px",
        md: "8px",
        lg: "10px",
        xl: "12px",
      },
      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
        "fade-in": { from: { opacity: "0", transform: "translateY(4px)" }, to: { opacity: "1", transform: "translateY(0)" } },
      },
      animation: {
        "fade-in": "fade-in 200ms ease-out",
      },
      transitionDuration: { DEFAULT: "180ms" },
    },
  },
  plugins: [],
};

export default config;
