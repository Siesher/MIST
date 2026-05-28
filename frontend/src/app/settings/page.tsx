"use client";

// Settings screen — ported from new_design (midnight) SettingsPage.
// Renders inside NewAppShell (theme-midnight) and reuses the new_design CSS
// classes (.page / .set-section / .set-row / .set-toggle / .set-slider /
// .theme-card / .theme-swatch / .about-text / .lang-toggle …) from newdesign.css.
//
// Mostly client-side. Persisted to localStorage:
//   • mits-lang            — UI language (via useI18n, shared with the rest of the app)
//   • mits-preferred-mode  — default chat mode for new sessions (read by AppShell / page.tsx)
//   • mits-thinking        — thinking-mode preference (on/off)
// Account section reads the current user from useAuth() (AuthProvider →
// GET /api/v1/auth/me under the hood); shows a graceful placeholder + login
// link when signed out. Theme selector renders all three new_design themes but
// stays locked to "midnight" (the shell hard-codes that look).

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { NewAppShell } from "@/components/newdesign/AppShell";
import { useAuth } from "@/components/auth/AuthProvider";
import { useI18n, type Lang } from "@/lib/i18n";
import { useTheme, setTheme, type ThemeName } from "@/components/newdesign/useTheme";
import type { ChatMode } from "@/types/api";

const PREFERRED_MODE_KEY = "mits-preferred-mode";
const THINKING_KEY = "mits-thinking";

// Theme cards — two palettes, both switchable. Wired to the shared useTheme
// store (mits-theme localStorage), same source as the chat TopBar toggle.
const THEMES: {
  id: ThemeName;
  name_ru: string;
  name_en: string;
  desc_ru: string;
  desc_en: string;
  swatch: string[];
}[] = [
  {
    id: "midnight",
    name_ru: "Тёмная",
    name_en: "Dark",
    desc_ru: "Тёмный фон, фиолетовое свечение",
    desc_en: "Dark background, purple glow",
    swatch: ["#0A0518", "#8B3CFF", "#B47BFF"],
  },
  {
    id: "daylight",
    name_ru: "Светлая",
    name_en: "Light",
    desc_ru: "Светлый фон, мягкие тени",
    desc_en: "Light background, soft shadows",
    swatch: ["#FAFAF9", "#6800FF", "#1A1330"],
  },
];

// Chat-mode options offered as the user's default for new sessions. Values match
// ChatMode and the dot colours used by the AppShell session list.
const MODES: { value: ChatMode; label_ru: string; label_en: string; dot: string }[] = [
  { value: "chat", label_ru: "Свободный чат", label_en: "Free chat", dot: "#3B7DFF" },
  { value: "guided_learning", label_ru: "Сопровождение", label_en: "Guided", dot: "#22A05A" },
  { value: "task_generator", label_ru: "Генератор задач", label_en: "Task generator", dot: "#6800FF" },
];

function isChatMode(v: string | null): v is ChatMode {
  return v === "chat" || v === "guided_learning" || v === "task_generator";
}

export default function SettingsPage() {
  // Language is shared app-wide via useI18n (persists to mits-lang).
  const { lang, setLang } = useI18n();
  const [theme] = useTheme();
  const { user, isAuthenticated, isLoading } = useAuth();

  // Preferred default chat mode (persists to mits-preferred-mode; read by AppShell).
  const [mode, setModeState] = useState<ChatMode>("guided_learning");
  // Thinking mode preference (persists to mits-thinking).
  const [thinking, setThinkingState] = useState(true);

  // Visual-effect toggles — local/ephemeral. Defaults mirror new_design's
  // midnight preset; they do not mutate the locked shell.
  const [glow, setGlow] = useState(18);
  const [motion, setMotion] = useState(true);
  const [particles, setParticles] = useState(true);
  const [grain, setGrain] = useState(false);

  // Hydrate persisted preferences after mount (avoids SSR/CSR mismatch).
  useEffect(() => {
    if (typeof window === "undefined") return;
    const savedMode = localStorage.getItem(PREFERRED_MODE_KEY);
    if (isChatMode(savedMode)) setModeState(savedMode);
    const savedThinking = localStorage.getItem(THINKING_KEY);
    if (savedThinking === "0" || savedThinking === "1") {
      setThinkingState(savedThinking === "1");
    }
  }, []);

  const setMode = useCallback((m: ChatMode) => {
    setModeState(m);
    if (typeof window !== "undefined") localStorage.setItem(PREFERRED_MODE_KEY, m);
  }, []);

  const setThinking = useCallback((v: boolean) => {
    setThinkingState(v);
    if (typeof window !== "undefined") localStorage.setItem(THINKING_KEY, v ? "1" : "0");
  }, []);

  const ru = lang === "ru";

  return (
    <NewAppShell>
      <main className="main">
        <div className="page">
          <div className="page-head">
            <div className="page-head-info">
              <h1>{ru ? "Настройки" : "Settings"}</h1>
              <div className="page-sub">
                {ru ? "Предпочтения · оформление · аккаунт" : "Preferences · appearance · account"}
              </div>
            </div>
            {/* Language toggle (new_design PageControls) — persists via useI18n. */}
            <div className="lang-toggle">
              <button className={lang === "ru" ? "active" : ""} onClick={() => setLang("ru")}>
                RU
              </button>
              <button className={lang === "en" ? "active" : ""} onClick={() => setLang("en")}>
                EN
              </button>
            </div>
          </div>

          <div className="page-body">
            {/* ---------- Preferences ---------- */}
            <div className="set-section">
              <div className="set-section-title">{ru ? "Предпочтения" : "Preferences"}</div>

              <div className="set-row">
                <span className="set-row-label">{ru ? "Язык интерфейса" : "Interface language"}</span>
                <div className="lang-toggle">
                  <button
                    className={lang === "ru" ? "active" : ""}
                    onClick={() => setLang("ru" as Lang)}
                  >
                    RU
                  </button>
                  <button
                    className={lang === "en" ? "active" : ""}
                    onClick={() => setLang("en" as Lang)}
                  >
                    EN
                  </button>
                </div>
              </div>

              <div className="set-row">
                <span className="set-row-label">
                  {ru ? "Режим диалога по умолчанию" : "Default chat mode"}
                </span>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
                  {MODES.map((m) => {
                    const on = mode === m.value;
                    return (
                      <button
                        key={m.value}
                        onClick={() => setMode(m.value)}
                        className="tag-chip"
                        style={{
                          cursor: "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 7,
                          borderColor: on ? "var(--accent)" : undefined,
                          color: on ? "var(--ink)" : "var(--ink-mute)",
                          boxShadow: on ? "0 0 0 2px var(--accent-tint)" : undefined,
                        }}
                      >
                        <span
                          style={{
                            width: 7,
                            height: 7,
                            borderRadius: "50%",
                            background: m.dot,
                            display: "inline-block",
                          }}
                        />
                        {ru ? m.label_ru : m.label_en}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="set-row">
                <span className="set-row-label">
                  {ru ? "Режим рассуждений (thinking)" : "Reasoning mode (thinking)"}
                </span>
                <button
                  className={"set-toggle " + (thinking ? "on" : "")}
                  aria-pressed={thinking}
                  onClick={() => setThinking(!thinking)}
                />
              </div>
            </div>

            {/* ---------- Theme (dark / light, both switchable) ---------- */}
            <div className="set-section">
              <div className="set-section-title">{ru ? "Тема" : "Theme"}</div>
              <div className="theme-cards">
                {THEMES.map((th) => {
                  const active = th.id === theme;
                  return (
                    <button
                      key={th.id}
                      type="button"
                      className={"theme-card " + (active ? "active" : "")}
                      onClick={() => setTheme(th.id)}
                    >
                      <div className="theme-swatch">
                        {th.swatch.map((c, i) => (
                          <span key={i} style={{ background: c }} />
                        ))}
                      </div>
                      <div className="theme-card-name">
                        {active && "▸ "}
                        {ru ? th.name_ru : th.name_en}
                      </div>
                      <div className="theme-card-desc">{ru ? th.desc_ru : th.desc_en}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* ---------- Effects (visual-only, local) ---------- */}
            <div className="set-section">
              <div className="set-section-title">{ru ? "Эффекты" : "Effects"}</div>
              <div className="set-row">
                <span className="set-row-label">{ru ? "Свечение акцентов" : "Accent glow"}</span>
                <input
                  className="set-slider"
                  type="range"
                  min={0}
                  max={32}
                  step={2}
                  value={glow}
                  onChange={(e) => setGlow(+e.target.value)}
                />
                <span className="set-value">{glow}px</span>
              </div>
              <div className="set-row">
                <span className="set-row-label">{ru ? "Анимации" : "Animations"}</span>
                <button
                  className={"set-toggle " + (motion ? "on" : "")}
                  aria-pressed={motion}
                  onClick={() => setMotion(!motion)}
                />
              </div>
              <div className="set-row">
                <span className="set-row-label">{ru ? "Частицы на фоне" : "Background particles"}</span>
                <button
                  className={"set-toggle " + (particles ? "on" : "")}
                  aria-pressed={particles}
                  onClick={() => setParticles(!particles)}
                />
              </div>
              <div className="set-row">
                <span className="set-row-label">{ru ? "Текстура зерна" : "Grain texture"}</span>
                <button
                  className={"set-toggle " + (grain ? "on" : "")}
                  aria-pressed={grain}
                  onClick={() => setGrain(!grain)}
                />
              </div>
            </div>

            {/* ---------- Account ---------- */}
            <div className="set-section">
              <div className="set-section-title">{ru ? "Аккаунт" : "Account"}</div>
              <AccountBlock
                ru={ru}
                isLoading={isLoading}
                isAuthenticated={isAuthenticated}
                displayName={user?.display_name ?? null}
                email={user?.email ?? null}
                preferredMode={user?.preferred_mode ?? null}
                createdAt={user?.created_at ?? null}
              />
            </div>

            {/* ---------- About ---------- */}
            <div className="set-section">
              <div className="set-section-title">{ru ? "О системе" : "About"}</div>
              <div className="about-text">
                {ru
                  ? "MITS v.2.6.1 · Math Intelligent Tutoring System · Qwen3.5-9B · GSPO → KTO → DPO · Base 55.1% → 66.5% · МГТУ им. Баумана · 2024–2026"
                  : "MITS v.2.6.1 · Math Intelligent Tutoring System · Qwen3.5-9B · GSPO → KTO → DPO · Base 55.1% → 66.5% · Bauman MSTU · 2024–2026"}
              </div>
            </div>
          </div>
        </div>
      </main>
    </NewAppShell>
  );
}

// ---------- Account section ----------
// Renders the signed-in user (from AuthProvider / GET /api/v1/auth/me) or a
// placeholder with a login link. Avatar initials mirror the profile screen.
function AccountBlock({
  ru,
  isLoading,
  isAuthenticated,
  displayName,
  email,
  preferredMode,
  createdAt,
}: {
  ru: boolean;
  isLoading: boolean;
  isAuthenticated: boolean;
  displayName: string | null;
  email: string | null;
  preferredMode: string | null;
  createdAt: string | null;
}) {
  if (isLoading) {
    return (
      <div className="about-text" style={{ color: "var(--ink-mute)" }}>
        {ru ? "Загрузка профиля…" : "Loading profile…"}
      </div>
    );
  }

  if (!isAuthenticated || !displayName) {
    return (
      <div
        className="rail-card"
        style={{ display: "flex", alignItems: "center", gap: 14, maxWidth: 720 }}
      >
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: "50%",
            background: "rgba(0,0,0,0.35)",
            border: "1px solid var(--line)",
            display: "grid",
            placeItems: "center",
            color: "var(--ink-mute)",
            fontSize: 16,
            flex: "0 0 44px",
          }}
        >
          ?
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, color: "var(--ink)" }}>
            {ru ? "Вы не вошли в систему" : "You are not signed in"}
          </div>
          <div style={{ fontSize: 11, color: "var(--ink-mute)", marginTop: 2 }}>
            {ru
              ? "Войдите, чтобы синхронизировать прогресс и предпочтения."
              : "Sign in to sync your progress and preferences."}
          </div>
        </div>
        <Link href="/auth/login" className="btn-primary" style={{ textDecoration: "none" }}>
          {ru ? "Войти" : "Log in"}
        </Link>
      </div>
    );
  }

  const initials = displayName
    .split(/\s+/)
    .map((p) => p[0])
    .filter(Boolean)
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const joined = (() => {
    if (!createdAt) return null;
    const d = new Date(createdAt);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleDateString(ru ? "ru-RU" : "en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  })();

  const modeLabel =
    MODES.find((m) => m.value === preferredMode)?.[ru ? "label_ru" : "label_en"] ??
    preferredMode ??
    "—";

  return (
    <div
      className="rail-card"
      style={{ display: "flex", alignItems: "center", gap: 14, maxWidth: 720 }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: "50%",
          background: "linear-gradient(135deg, var(--accent), rgba(180,123,255,0.6))",
          display: "grid",
          placeItems: "center",
          color: "var(--accent-text, #fff)",
          fontSize: 15,
          fontWeight: 600,
          flex: "0 0 44px",
        }}
      >
        {initials || "?"}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, color: "var(--ink)", fontWeight: 500 }}>{displayName}</div>
        {email && (
          <div
            style={{
              fontSize: 11,
              color: "var(--ink-mute)",
              fontFamily: "var(--font-mono), monospace",
              marginTop: 2,
            }}
          >
            {email}
          </div>
        )}
        <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
          <span className="tag-chip">
            {ru ? "Режим" : "Mode"} · {modeLabel}
          </span>
          {joined && (
            <span className="tag-chip">
              {ru ? "С нами с" : "Joined"} {joined}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
