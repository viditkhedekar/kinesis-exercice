"use client";

import { useTheme } from "./ThemeProvider";

export default function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      onClick={toggle}
      className="btn-subtle w-full justify-start"
      aria-label="Toggle theme"
      title="Toggle theme"
    >
      <span className="w-4 text-center">{theme === "dark" ? "☾" : "☀"}</span>
      <span>{theme === "dark" ? "Dark" : "Light"} mode</span>
    </button>
  );
}
