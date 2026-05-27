"use client";

// Shared theme switcher for the new_design UI. The 4 theme palettes
// (.theme-midnight/daylight/aurora/grimoire) live in newdesign.css — this just
// toggles which class is active on the shell + <body>, persisted to localStorage.
import { useSyncExternalStore } from "react";

export type ThemeName = "midnight" | "daylight" | "aurora" | "grimoire";
export const THEMES: ThemeName[] = ["midnight", "daylight", "aurora", "grimoire"];
export const THEME_LABELS: Record<ThemeName, string> = {
  midnight: "Midnight",
  daylight: "Daylight",
  aurora: "Aurora",
  grimoire: "Grimoire",
};

const KEY = "mits-theme";
const DEFAULT: ThemeName = "midnight";
const listeners = new Set<() => void>();
let current: ThemeName | null = null;

function read(): ThemeName {
  if (current) return current;
  if (typeof window === "undefined") return DEFAULT;
  const saved = window.localStorage.getItem(KEY) as ThemeName | null;
  current = saved && THEMES.includes(saved) ? saved : DEFAULT;
  return current;
}

export function applyThemeToBody(t: ThemeName): void {
  if (typeof document === "undefined") return;
  for (const x of THEMES) document.body.classList.remove("theme-" + x);
  document.body.classList.add("theme-" + t);
}

export function setTheme(t: ThemeName): void {
  current = t;
  if (typeof window !== "undefined") window.localStorage.setItem(KEY, t);
  applyThemeToBody(t);
  listeners.forEach((l) => l());
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

export function useTheme(): [ThemeName, (t: ThemeName) => void] {
  const theme = useSyncExternalStore(subscribe, read, () => DEFAULT);
  return [theme, setTheme];
}
