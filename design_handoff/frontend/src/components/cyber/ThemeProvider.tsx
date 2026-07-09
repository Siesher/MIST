"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type CyberTheme = "grimoire" | "neo" | "acid" | "minimal";

interface Tweaks {
  theme: CyberTheme;
  glow: number;
  scanlines: number;
  glitch: boolean;
  particles: boolean;
}

interface Ctx extends Tweaks {
  setTheme: (t: CyberTheme) => void;
  setGlow: (n: number) => void;
  setScanlines: (n: number) => void;
  setGlitch: (b: boolean) => void;
  setParticles: (b: boolean) => void;
}

const DEFAULTS: Tweaks = {
  theme: "grimoire",
  glow: 14,
  scanlines: 0.5,
  glitch: true,
  particles: true,
};

const ThemeCtx = createContext<Ctx | null>(null);

export function useCyberTheme() {
  const ctx = useContext(ThemeCtx);
  if (!ctx) throw new Error("useCyberTheme must be inside ThemeProvider");
  return ctx;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [tweaks, setTweaks] = useState<Tweaks>(DEFAULTS);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem("mits-cyber-tweaks");
      if (raw) {
        const parsed = JSON.parse(raw);
        setTweaks({ ...DEFAULTS, ...parsed });
      }
    } catch {
      /* ignore */
    }
  }, []);

  // Apply tweaks to <html> attributes + CSS vars
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = tweaks.theme;
    root.dataset.glitch = tweaks.glitch ? "on" : "off";
    root.style.setProperty("--glow-size", `${tweaks.glow}px`);
    root.style.setProperty("--scanline-opacity", String(tweaks.scanlines));
    try {
      localStorage.setItem("mits-cyber-tweaks", JSON.stringify(tweaks));
    } catch {
      /* ignore */
    }
  }, [tweaks]);

  const ctx: Ctx = {
    ...tweaks,
    setTheme: (t) => setTweaks((p) => ({ ...p, theme: t })),
    setGlow: (n) => setTweaks((p) => ({ ...p, glow: n })),
    setScanlines: (n) => setTweaks((p) => ({ ...p, scanlines: n })),
    setGlitch: (b) => setTweaks((p) => ({ ...p, glitch: b })),
    setParticles: (b) => setTweaks((p) => ({ ...p, particles: b })),
  };

  return <ThemeCtx.Provider value={ctx}>{children}</ThemeCtx.Provider>;
}
