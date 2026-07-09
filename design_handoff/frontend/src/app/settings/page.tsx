"use client";

import { AppShell } from "@/components/cyber/AppShell";
import { Glitch } from "@/components/cyber/Glitch";
import { useCyberTheme, type CyberTheme } from "@/components/cyber/ThemeProvider";
import { useI18n } from "@/lib/i18n";

const THEMES: { id: CyberTheme; label: string; desc_ru: string; desc_en: string }[] = [
  {
    id: "grimoire",
    label: "Grimoire",
    desc_ru: "Фиолетово-золотой гримуар — стандартная тема",
    desc_en: "Royal violet + warm champagne — default",
  },
  {
    id: "minimal",
    label: "Minimal",
    desc_ru: "Плоский стиль без эффектов — для слабых машин",
    desc_en: "Flat, no glow/scanlines — low-end friendly",
  },
  {
    id: "neo",
    label: "Mono",
    desc_ru: "Чёрно-белый, высококонтрастный",
    desc_en: "Monochrome high-contrast",
  },
  {
    id: "acid",
    label: "Acid",
    desc_ru: "Киберпанк overdrive — максимум неона",
    desc_en: "Saturated cyber overdrive",
  },
];

export default function SettingsPage() {
  const { lang } = useI18n();
  const {
    theme, glow, scanlines, glitch, particles,
    setTheme, setGlow, setScanlines, setGlitch, setParticles,
  } = useCyberTheme();

  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto">
          <div className="mb-7">
            <Glitch className="font-display" text={lang === "ru" ? "НАСТРОЙКИ" : "SETTINGS"}>
              <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: "0.06em" }}>
                {lang === "ru" ? "НАСТРОЙКИ" : "SETTINGS"}
              </span>
            </Glitch>
            <div className="ghost mt-1" style={{ fontSize: 11, letterSpacing: "0.14em" }}>
              {"// оформление, эффекты, интерфейс"}
            </div>
          </div>

          {/* Theme variants */}
          <div className="panel cornered mb-5" style={{ padding: 20 }}>
            <span className="corner-tl" />
            <span className="corner-br" />
            <div className="up ghost text-[10px] tracking-[0.22em] mb-3">
              › {lang === "ru" ? "ТЕМА ОФОРМЛЕНИЯ" : "THEME VARIANT"}
            </div>
            <div className="grid grid-cols-2 gap-2">
              {THEMES.map((v) => {
                const on = theme === v.id;
                return (
                  <button
                    key={v.id}
                    onClick={() => setTheme(v.id)}
                    className="font-mono text-left transition-all"
                    style={{
                      padding: "14px 16px",
                      border: "1px solid " + (on ? "var(--yellow)" : "var(--line)"),
                      background: on
                        ? "linear-gradient(135deg, rgba(232,198,104,0.08), rgba(165,131,255,0.04))"
                        : "transparent",
                      color: on ? "var(--yellow)" : "var(--text-dim)",
                      borderRadius: 4,
                      cursor: "pointer",
                    }}
                  >
                    <div
                      className="up"
                      style={{
                        fontSize: 12,
                        letterSpacing: "0.14em",
                        color: on ? "var(--yellow)" : "var(--text)",
                      }}
                    >
                      {on ? "▸ " : "· "}
                      {v.label}
                    </div>
                    <div
                      className="ghost mt-1.5"
                      style={{ fontSize: 10, letterSpacing: "0.08em" }}
                    >
                      {lang === "ru" ? v.desc_ru : v.desc_en}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Effects */}
          <div className="panel cornered mb-5" style={{ padding: 20 }}>
            <span className="corner-tl" />
            <span className="corner-br" />
            <div className="up ghost text-[10px] tracking-[0.22em] mb-3">
              › {lang === "ru" ? "ЭФФЕКТЫ" : "EFFECTS"}
            </div>

            <div className="mb-5">
              <div className="flex items-center mb-2">
                <span className="up" style={{ fontSize: 11, color: "var(--text)" }}>
                  {lang === "ru" ? "Неоновое свечение" : "Neon glow"}
                </span>
                <div className="flex-1" />
                <span className="y font-mono" style={{ fontSize: 11, fontVariantNumeric: "tabular-nums" }}>
                  {glow}px
                </span>
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

            <div className="mb-5">
              <div className="flex items-center mb-2">
                <span className="up" style={{ fontSize: 11, color: "var(--text)" }}>
                  {lang === "ru" ? "Линии развёртки (CRT)" : "Scanlines (CRT)"}
                </span>
                <div className="flex-1" />
                <span className="y font-mono" style={{ fontSize: 11, fontVariantNumeric: "tabular-nums" }}>
                  {Math.round(scanlines * 100)}%
                </span>
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

            <label className="flex items-center gap-3 cursor-pointer py-2">
              <input
                type="checkbox"
                checked={glitch}
                onChange={(e) => setGlitch(e.target.checked)}
                style={{ accentColor: "var(--violet)" }}
              />
              <span className="up" style={{ fontSize: 11, color: "var(--text)" }}>
                {lang === "ru" ? "Глитч на заголовках" : "Glitch on titles"}
              </span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer py-2">
              <input
                type="checkbox"
                checked={particles}
                onChange={(e) => setParticles(e.target.checked)}
                style={{ accentColor: "var(--violet)" }}
              />
              <span className="up" style={{ fontSize: 11, color: "var(--text)" }}>
                {lang === "ru" ? "Частицы на фоне" : "Background particles"}
              </span>
            </label>
          </div>

          {/* About */}
          <div className="panel" style={{ padding: 20 }}>
            <div className="up ghost text-[10px] tracking-[0.22em] mb-3">
              › {lang === "ru" ? "О СИСТЕМЕ" : "ABOUT"}
            </div>
            <div className="font-mono text-[12px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
              <div>
                MITS v.2.6.1 — <span className="v">Math Intelligent Tutoring System</span>
              </div>
              <div className="mt-2">
                Qwen3.5-9B · GSPO → KTO → DPO · Base 55.1% → 66.5%
              </div>
              <div className="mt-2">МГТУ им. Баумана · дипломная работа · 2024–2026</div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
