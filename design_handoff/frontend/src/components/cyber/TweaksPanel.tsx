"use client";

import { useState } from "react";
import { useCyberTheme, type CyberTheme } from "./ThemeProvider";

const THEMES: { id: CyberTheme; label: string }[] = [
  { id: "grimoire", label: "Grimoire" },
  { id: "minimal", label: "Minimal" },
  { id: "neo", label: "Mono" },
  { id: "acid", label: "Acid" },
];

export function TweaksPanel() {
  const [open, setOpen] = useState(false);
  const { theme, glow, scanlines, glitch, particles, setTheme, setGlow, setScanlines, setGlitch, setParticles } =
    useCyberTheme();

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="cbtn fixed bottom-4 right-4 z-[9998] text-[10px]"
        style={{ background: "var(--surface-hi)" }}
        aria-label="Open theme tweaks"
      >
        ⚙ THEME
      </button>
    );
  }

  return (
    <div
      className="cornered panel fixed bottom-4 right-4 z-[9999]"
      style={{
        width: 300,
        padding: 14,
        background: "var(--surface-hi)",
        border: "1px solid var(--violet)",
        boxShadow: "0 0 24px rgba(165,131,255,0.4)",
      }}
    >
      <span className="corner-tl" />
      <span className="corner-br" />
      <div className="flex items-center mb-3">
        <span className="neon-v up text-[11px]">⚙ Tweaks</span>
        <div className="flex-1" />
        <button onClick={() => setOpen(false)} className="cbtn cbtn-ghost !px-1.5 !py-0.5 text-[11px]">
          ✕
        </button>
      </div>

      <div className="flex flex-col gap-3 text-[11px]">
        <div>
          <div className="up ghost text-[9px] mb-1.5">Theme variant</div>
          <div className="flex flex-wrap gap-1">
            {THEMES.map((v) => (
              <button
                key={v.id}
                onClick={() => setTheme(v.id)}
                className="font-mono cursor-pointer"
                style={{
                  flex: "1 1 44%",
                  padding: "6px 4px",
                  border: "1px solid " + (theme === v.id ? "var(--yellow)" : "var(--line)"),
                  background: theme === v.id ? "rgba(232,198,104,0.1)" : "transparent",
                  color: theme === v.id ? "var(--yellow)" : "var(--text-dim)",
                  fontSize: 10,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  borderRadius: 3,
                }}
              >
                {v.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="flex items-center mb-1">
            <span className="up ghost text-[9px]">Neon glow</span>
            <div className="flex-1" />
            <span className="y text-[10px]">{glow}px</span>
          </div>
          <input
            type="range"
            min={0}
            max={40}
            step={2}
            value={glow}
            onChange={(e) => setGlow(+e.target.value)}
            style={{ width: "100%", accentColor: "var(--violet)" }}
          />
        </div>

        <div>
          <div className="flex items-center mb-1">
            <span className="up ghost text-[9px]">Scanlines</span>
            <div className="flex-1" />
            <span className="y text-[10px]">{Math.round(scanlines * 100)}%</span>
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={scanlines}
            onChange={(e) => setScanlines(+e.target.value)}
            style={{ width: "100%", accentColor: "var(--violet)" }}
          />
        </div>

        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={glitch} onChange={(e) => setGlitch(e.target.checked)} />
          <span className="up text-[10px] tracking-[0.14em]">Glitch on titles</span>
        </label>

        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={particles} onChange={(e) => setParticles(e.target.checked)} />
          <span className="up text-[10px] tracking-[0.14em]">Particles background</span>
        </label>
      </div>
    </div>
  );
}
