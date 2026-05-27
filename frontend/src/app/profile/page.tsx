"use client";

// Profile screen — ported from new_design (midnight) ProfilePage (pages (1).jsx ≈ 578–692).
// Renders inside NewAppShell (theme-midnight) and reuses the new_design CSS classes
// (.page / .profile-hero / .stat-cards / .timeline / .dom-pill / .gs-bar / .dash-card /
// .skill-tag …) defined in newdesign.css / newdesign-enh.css.
//
// Data (all three student endpoints):
//   GET /api/v1/students/me/profile    → identity, sessions, streak, mastery, strong/weak
//   GET /api/v1/students/me/analytics  → tasks attempted/solved, focus-week bars
//   GET /api/v1/students/me/knowledge  → mastery_by_skill (fills topic bars if profile empty)
// On backend error or empty payloads we FALL BACK to representative static data so the
// screen always looks complete (mirrors sources/page.tsx).

import { useEffect, useMemo, useState } from "react";
import { NewAppShell } from "@/components/newdesign/AppShell";
import { getProfile } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import type { StudentProfile } from "@/types/api";

// ---- Local fetch helpers for the analytics + knowledge endpoints ----------------
// (getProfile() already lives in @/lib/api; these two are profile-screen-local so we
// don't touch the shared client. Same request/auth shape as @/lib/api's request().)

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_V1 = `${API_BASE}/api/v1`;

interface ProgressByDay {
  date: string;
  sessions: number;
  solved: number;
}

interface Analytics {
  period_start: string;
  period_end: string;
  sessions_count: number;
  tasks_attempted: number;
  tasks_solved: number;
  avg_session_minutes: number;
  avg_hints_per_task: number;
  progress_by_day: ProgressByDay[];
}

interface KnowledgeState {
  mastery_by_skill: Record<string, number>;
  skill_dependencies: Record<string, string[]>;
  recommended_next: string[];
}

async function fetchJson<T>(path: string): Promise<T> {
  const token = getAccessToken();
  const res = await fetch(`${API_V1}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

const getAnalytics = (period = "week") =>
  fetchJson<Analytics>(`/students/me/analytics?period=${period}`);
const getKnowledgeState = () => fetchJson<KnowledgeState>("/students/me/knowledge");

// ---- Midnight-theme domain colours — mirrors getDomColor(d,"midnight") in new_design.
const DOM_COLOR: Record<string, string> = {
  math: "#B47BFF",
  physics: "#F0BB7E",
  phys: "#F0BB7E",
  chemistry: "#8DD4DC",
  chem: "#8DD4DC",
  biology: "#6FE0A6",
  bio: "#6FE0A6",
  cs: "#ED9CBF",
  other: "#B47BFF",
};

function getDomColor(domain: string): string {
  return DOM_COLOR[domain] ?? "var(--accent)";
}

// ---- Representative fallback data (RECENT[ru] + profile mocks from new_design) -----
interface RecentItem {
  t: string;
  d: string;
  e: string;
}

const FALLBACK_RECENT: RecentItem[] = [
  { t: "14:32", d: "math", e: "Решил ∫x·sin(x)dx с 2 подсказками" },
  { t: "13:18", d: "cs", e: "DP: longest palindromic subseq · O(n²)" },
  { t: "11:05", d: "phys", e: "Маятник: период, малые колебания" },
  { t: "09:41", d: "chem", e: "pKa аминокислоты — гидролиз" },
  { t: "Вчера", d: "math", e: "Цепное правило: 14 задач, 11 решено" },
];

// Mastery-by-topic fallback bars (label + value), verbatim from new_design ProfilePage.
const FALLBACK_MASTERY: { lab: string; v: number }[] = [
  { lab: "Алгебра", v: 0.82 },
  { lab: "Анализ", v: 0.71 },
  { lab: "Геометрия", v: 0.69 },
  { lab: "Линал", v: 0.64 },
  { lab: "Механика", v: 0.67 },
];

const FALLBACK_STRONG = ["Базовые производные", "Цепное правило", "Алгебра"];
const FALLBACK_WEAK = ["Тепловой баланс", "Электромагнетизм", "Динамическое прог-е"];

// Focus-week heights (0–90 viewBox), Thursday/Saturday peak — from new_design.
const FALLBACK_FOCUS = [32, 58, 45, 72, 68, 88, 62];
const WEEK_DAYS = ["П", "В", "С", "Ч", "П", "С", "В"];

// Map a domain → short pill alias used by the design (math/phys/chem/cs/bio).
function pillAlias(domain: string): string {
  const m: Record<string, string> = {
    physics: "phys",
    chemistry: "chem",
    biology: "bio",
  };
  return m[domain] ?? domain;
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [knowledge, setKnowledge] = useState<KnowledgeState | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      // Each endpoint is independent — settle individually so one failure
      // doesn't blank the others. Empty/zero payloads fall back per-field below.
      const [p, a, k] = await Promise.allSettled([
        getProfile(),
        getAnalytics("week"),
        getKnowledgeState(),
      ]);
      if (cancelled) return;
      if (p.status === "fulfilled") setProfile(p.value);
      if (a.status === "fulfilled") setAnalytics(a.value);
      if (k.status === "fulfilled") setKnowledge(k.value);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  // ---- Derived values: real data where present, fallback otherwise ----------------

  const totalSessions = profile?.total_sessions || 147;
  const streak = profile?.streak_days || 14;
  const masteryAvgPct = profile
    ? Math.round((profile.success_rate || 0.62) * 100)
    : 62;
  // "problems" = tasks attempted (analytics) → fall back to design's 892.
  const problems = analytics && analytics.tasks_attempted > 0 ? analytics.tasks_attempted : 892;

  // Mastery-by-topic bars: prefer profile.mastery_by_topic, then knowledge.mastery_by_skill,
  // else the representative fallback set.
  const masteryBars = useMemo<{ lab: string; v: number }[]>(() => {
    if (profile && Object.keys(profile.mastery_by_topic).length > 0) {
      return Object.entries(profile.mastery_by_topic).map(([lab, v]) => ({ lab, v }));
    }
    if (knowledge && Object.keys(knowledge.mastery_by_skill).length > 0) {
      return Object.entries(knowledge.mastery_by_skill).map(([lab, v]) => ({ lab, v }));
    }
    return FALLBACK_MASTERY;
  }, [profile, knowledge]);

  const strongSkills =
    profile && profile.strong_skills.length > 0 ? profile.strong_skills : FALLBACK_STRONG;
  const weakSkills =
    profile && profile.weak_skills.length > 0 ? profile.weak_skills : FALLBACK_WEAK;

  // Recent timeline: derive nothing real from the backend (no event feed endpoint),
  // so always render the representative recent-activity list.
  const recent = FALLBACK_RECENT;

  // Focus-week bars: scale analytics.progress_by_day (last 7) into the 0–90 viewBox,
  // else the representative shape. Keep exactly 7 bars.
  const focus = useMemo<number[]>(() => {
    const days = analytics?.progress_by_day ?? [];
    if (days.length === 0) return FALLBACK_FOCUS;
    const last7 = days.slice(-7);
    const max = Math.max(...last7.map((d) => d.sessions), 1);
    const scaled = last7.map((d) => Math.max(8, Math.round((d.sessions / max) * 88)));
    // Pad to 7 bars if the backend returned fewer.
    while (scaled.length < 7) scaled.unshift(8);
    return scaled.slice(-7);
  }, [analytics]);

  const peakIdx = useMemo(() => focus.indexOf(Math.max(...focus)), [focus]);

  return (
    <NewAppShell>
      <main className="main">
        <div className="page">
          <div className="page-head">
            <div className="page-head-info">
              <h1>Профиль</h1>
              <div className="page-sub">
                Максим Сухацкий · МГТУ им. Баумана · apprentice → journeyman
              </div>
            </div>
            <button className="btn-secondary">Редактировать</button>
          </div>

          <div className="page-body">
            {/* Hero — avatar + identity + status chips. */}
            <div className="profile-hero">
              <div className="profile-avatar">МС</div>
              <div className="profile-info">
                <h2 className="profile-name">Максим Сухацкий</h2>
                <div className="profile-meta">siesher · когорта &apos;25 · main contributor</div>
                <div className="profile-chips">
                  <span className="profile-chip">Socratic mode</span>
                  <span className="profile-chip">streak {streak}</span>
                  <span className="profile-chip">RU / EN</span>
                  <span className="profile-chip">github · siesher</span>
                </div>
              </div>
            </div>

            {/* Headline stats. */}
            <div className="stat-cards" style={{ marginBottom: 22 }}>
              <div className="stat-card">
                <div className="stat-card-k">сессий</div>
                <div className="stat-card-v">{totalSessions}</div>
              </div>
              <div className="stat-card">
                <div className="stat-card-k">задач</div>
                <div className="stat-card-v">{problems}</div>
              </div>
              <div className="stat-card">
                <div className="stat-card-k">дней подряд</div>
                <div className="stat-card-v">{streak}</div>
              </div>
              <div className="stat-card">
                <div className="stat-card-k">среднее освоение</div>
                <div className="stat-card-v">{masteryAvgPct}%</div>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 18 }}>
              {/* Left column: recent activity + mastery-by-topic. */}
              <div className="dash-card">
                <div className="dash-card-title">
                  <span>Последняя активность</span>
                </div>
                <div className="timeline">
                  {recent.map((r, i) => (
                    <div
                      key={i}
                      className="tl-item"
                      style={{ "--dom": getDomColor(r.d) } as React.CSSProperties}
                    >
                      <span className="tl-time">{r.t}</span>
                      <span
                        className="dom-pill"
                        style={
                          {
                            "--dom": getDomColor(r.d),
                            "--dom-tint": getDomColor(r.d) + "10",
                          } as React.CSSProperties
                        }
                      >
                        {pillAlias(r.d)}
                      </span>
                      <span className="tl-body">{r.e}</span>
                    </div>
                  ))}
                </div>

                <div className="dash-card-title" style={{ marginTop: 28 }}>
                  <span>Освоение по темам</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {masteryBars.map((m, i) => (
                    <div key={i}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: 12,
                          marginBottom: 4,
                        }}
                      >
                        <span style={{ color: "var(--ink)", textTransform: "capitalize" }}>
                          {m.lab}
                        </span>
                        <span
                          style={{
                            color: "var(--accent)",
                            fontFamily: "JetBrains Mono",
                            fontWeight: 600,
                          }}
                        >
                          {Math.round(m.v * 100)}%
                        </span>
                      </div>
                      <div className="gs-bar">
                        <div className="gs-bar-fill" style={{ width: m.v * 100 + "%" }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right column: emotion · focus-week · strong · weak. */}
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div className="dash-card">
                  <div className="dash-card-title">
                    <span>Эмоциональный фон</span>
                  </div>
                  <div
                    style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}
                  >
                    <span
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: "50%",
                        background: "#FFB85C",
                        boxShadow: "0 0 8px #FFB85C",
                      }}
                    />
                    <span style={{ fontSize: 18, color: "var(--ink)", fontWeight: 600 }}>
                      focused
                    </span>
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      fontFamily: "JetBrains Mono",
                      color: "var(--ink-mute)",
                    }}
                  >
                    RuBERT детектор · уверенность 0.84
                  </div>
                </div>

                <div className="dash-card">
                  <div className="dash-card-title">
                    <span>Фокус · неделя</span>
                  </div>
                  <svg width="100%" height="80" viewBox="0 0 220 90" style={{ marginBottom: 4 }}>
                    {focus.map((v, i) => (
                      <rect
                        key={i}
                        x={i * 30 + 6}
                        y={90 - v}
                        width="22"
                        height={v}
                        fill={i === peakIdx ? "#FFB85C" : "var(--accent)"}
                        rx="2"
                        opacity={i === peakIdx ? 1 : 0.85}
                        style={{
                          filter: i === peakIdx ? "drop-shadow(0 0 6px #FFB85C)" : "none",
                        }}
                      />
                    ))}
                  </svg>
                  <div
                    style={{
                      display: "flex",
                      fontSize: 10,
                      color: "var(--ink-mute)",
                      fontFamily: "JetBrains Mono",
                    }}
                  >
                    {WEEK_DAYS.map((d, i) => (
                      <span key={i} style={{ flex: 1, textAlign: "center" }}>
                        {d}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="dash-card">
                  <div className="dash-card-title">
                    <span>Сильные стороны</span>
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {strongSkills.map((s) => (
                      <span key={s} className="skill-tag strong">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="dash-card">
                  <div className="dash-card-title">
                    <span>На доработке</span>
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {weakSkills.map((s) => (
                      <span key={s} className="skill-tag weak">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </NewAppShell>
  );
}
