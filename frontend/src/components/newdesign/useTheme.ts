"use client";

// Shared theme switcher for the new_design UI. Two palettes
// (.theme-midnight = dark, .theme-daylight = light) live in newdesign.css —
// this just toggles which class is active on the shell + <body>, persisted
// to localStorage. Legacy values (aurora/grimoire) fall back to midnight.
import { useSyncExternalStore } from "react";

export type ThemeName = "midnight" | "daylight";
export const THEMES: ThemeName[] = ["midnight", "daylight"];
export const THEME_LABELS: Record<ThemeName, string> = {
  midnight: "Тёмная",
  daylight: "Светлая",
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
