"use client";

import { THEME_LABELS, THEMES, useTheme } from "./useTheme";

const SUN = (
  <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="8" cy="8" r="3" />
    <path
      strokeLinecap="round"
      d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.5 1.5M11.5 11.5 13 13M3 13l1.5-1.5M11.5 4.5 13 3"
    />
  </svg>
);

const MOON = (
  <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 9.6A5.6 5.6 0 1 1 6.4 2.5 4.6 4.6 0 0 0 13.5 9.6Z" />
  </svg>
);

/**
 * Shared theme toggle wired to the global useTheme store (NOT per-page state).
 * Cycles midnight ↔ daylight and persists via useTheme; the glyph shows the
 * theme you'd switch TO. Previously each screen hand-rolled this button and
 * most were dead (local state / no handler) — see ChatScreen for the original.
 */
export function ThemeToggle({ className = "theme-toggle" }: { className?: string }) {
  const [theme, setTheme] = useTheme();
  const cycle = (): void => setTheme(THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length]);
  return (
    <button type="button" className={className} title={`Тема: ${THEME_LABELS[theme]}`} onClick={cycle}>
      {theme === "daylight" ? MOON : SUN}
    </button>
  );
}
