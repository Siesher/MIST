"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/cyber/AppShell";
import { Glitch } from "@/components/cyber/Glitch";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "@/components/auth/AuthProvider";
import { getProfile } from "@/lib/api";
import { DOMAIN_COLOR } from "@/lib/domains";
import type { StudentProfile } from "@/types/api";

const RECENT_RU = [
  { t: "14:32", dom: "math", ev: "Решил интеграл ∫x·sin(x)dx с 2 подсказками" },
  { t: "13:18", dom: "cs", ev: "DP задача: longest palindromic subseq · O(n²)" },
  { t: "11:05", dom: "phys", ev: "Маятник: период, малые колебания" },
  { t: "09:41", dom: "chem", ev: "pKa аминокислоты — гидролиз" },
];

const RECENT_EN = [
  { t: "14:32", dom: "math", ev: "Solved ∫x·sin(x)dx with 2 hints" },
  { t: "13:18", dom: "cs", ev: "DP problem: longest palindromic subseq · O(n²)" },
  { t: "11:05", dom: "phys", ev: "Pendulum: period under small oscillations" },
  { t: "09:41", dom: "chem", ev: "pKa of amino acid — hydrolysis" },
];

export default function ProfilePage() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const [profile, setProfile] = useState<StudentProfile | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setProfile(await getProfile());
      } catch {
        /* backend offline */
      }
    }
    load();
  }, []);

  const recent = lang === "ru" ? RECENT_RU : RECENT_EN;
  const displayName = user?.display_name || "Максим Сухацкий";
  const initials = displayName
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const stats: [string, string | number][] = [
    ["sessions", profile?.total_sessions ?? 147],
    ["problems", 892],
    ["streak", `${profile?.streak_days ?? 14} days`],
    [
      "mastery avg",
      `${Math.round((profile?.success_rate ?? 0.62) * 100)}%`,
    ],
  ];

  const focusWeek = [32, 58, 45, 72, 68, 88, 62];

  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto p-6">
        {/* Hero */}
        <div className="flex items-center gap-4 mb-7">
          <div
            className="cornered flex items-center justify-center font-display relative"
            style={{
              width: 96,
              height: 96,
              flex: "0 0 96px",
              border: "1px solid var(--violet)",
              background: "linear-gradient(135deg, rgba(165,131,255,0.2), rgba(232,198,104,0.1))",
              fontSize: 40,
              fontWeight: 700,
              color: "var(--yellow)",
              boxShadow: "var(--glow-violet)",
            }}
          >
            <span className="corner-tl" />
            <span className="corner-br" />
            {initials}
          </div>
          <div className="flex flex-col flex-1">
            <Glitch className="font-display" text={displayName}>
              <span style={{ fontSize: 26, fontWeight: 600, color: "var(--text)" }}>
                {displayName}
              </span>
            </Glitch>
            <div className="ghost mt-1" style={{ fontSize: 11, letterSpacing: "0.14em" }}>
              {"// "}{user?.email ?? "siesher@mits.sys"} · МГТУ им. Баумана · apprentice → journeyman
            </div>
            <div className="flex items-center gap-2 mt-2.5">
              <span className="chip on">◆ GUIDED MODE</span>
              <span className="chip v">STREAK · {profile?.streak_days ?? 14}</span>
              <span className="chip">{lang === "ru" ? "РУССКИЙ · EN" : "RUSSIAN · EN"}</span>
            </div>
          </div>
          <button className="cbtn">⚙ EDIT</button>
        </div>

        {/* Stats */}
        <div
          className="grid grid-cols-4 mb-7"
          style={{ gap: 1, background: "var(--line-hi)", border: "1px solid var(--line-hi)" }}
        >
          {stats.map(([k, v]) => (
            <div key={k} style={{ background: "var(--surface)", padding: 18 }}>
              <div className="ghost up" style={{ fontSize: 10, letterSpacing: "0.18em" }}>
                {k}
              </div>
              <div
                className="font-display mt-1"
                style={{ fontSize: 26, color: "var(--text)", fontWeight: 600 }}
              >
                {v}
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-[2fr_1fr] gap-6">
          {/* Timeline */}
          <div>
            <div className="up ghost text-[10px] tracking-[0.22em] mb-3">
              › {lang === "ru" ? "ПОСЛЕДНЯЯ АКТИВНОСТЬ" : "RECENT ACTIVITY"}
            </div>
            <div className="flex flex-col relative pl-4">
              <div
                style={{
                  position: "absolute",
                  top: 6,
                  bottom: 6,
                  left: 4,
                  width: 1,
                  background: "var(--line-hi)",
                }}
              />
              {recent.map((r, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 relative"
                  style={{ padding: "10px 0 10px 16px" }}
                >
                  <div
                    style={{
                      position: "absolute",
                      left: -1,
                      top: 16,
                      width: 9,
                      height: 9,
                      background: DOMAIN_COLOR[r.dom] || "var(--violet)",
                      boxShadow: `0 0 6px ${DOMAIN_COLOR[r.dom] || "var(--violet)"}`,
                    }}
                  />
                  <span
                    className="font-mono y"
                    style={{ fontSize: 10, letterSpacing: "0.1em", width: 40 }}
                  >
                    {r.t}
                  </span>
                  <span className="chip" style={{ fontSize: 9 }}>
                    {r.dom.toUpperCase()}
                  </span>
                  <span style={{ fontSize: 12, color: "var(--text)" }}>{r.ev}</span>
                </div>
              ))}
            </div>

            {/* Mastery by topic (real data) */}
            {profile && Object.keys(profile.mastery_by_topic).length > 0 && (
              <div className="mt-6">
                <div className="up ghost text-[10px] tracking-[0.22em] mb-3">
                  › {lang === "ru" ? "ОСВОЕНИЕ ТЕМ" : "MASTERY BY TOPIC"}
                </div>
                <div className="flex flex-col gap-2.5">
                  {Object.entries(profile.mastery_by_topic).map(([topic, m]) => (
                    <div key={topic}>
                      <div className="flex items-center justify-between text-[11px] mb-1">
                        <span className="capitalize">{topic}</span>
                        <span className="y">{Math.round(m * 100)}%</span>
                      </div>
                      <div style={{ height: 4, background: "rgba(165,131,255,0.12)", position: "relative" }}>
                        <div
                          style={{
                            position: "absolute",
                            inset: 0,
                            right: "auto",
                            width: `${m * 100}%`,
                            background: "linear-gradient(to right, var(--violet), var(--yellow))",
                            boxShadow: "0 0 6px var(--violet)",
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Side */}
          <div className="flex flex-col gap-4">
            <div className="panel" style={{ padding: 14 }}>
              <div className="up ghost text-[10px] tracking-[0.2em] mb-2.5">› {t("emotion")}</div>
              <div className="flex items-center gap-2 mb-2.5">
                <span className="neon-y" style={{ fontSize: 22 }}>
                  ● focused
                </span>
              </div>
              <div className="ghost" style={{ fontSize: 10 }}>
                RuBERT detector · conf 0.84
              </div>
            </div>

            <div className="panel" style={{ padding: 14 }}>
              <div className="up ghost text-[10px] tracking-[0.2em] mb-2.5">
                › {t("focus")} · week
              </div>
              <svg width="100%" height="80" viewBox="0 0 220 80">
                {focusWeek.map((v, i) => (
                  <rect
                    key={i}
                    x={i * 30 + 4}
                    y={80 - v}
                    width="22"
                    height={v}
                    fill={i === 5 ? "var(--yellow)" : "var(--violet)"}
                    opacity={i === 5 ? 1 : 0.7}
                    style={{ filter: "drop-shadow(0 0 4px currentColor)" }}
                  />
                ))}
              </svg>
              <div className="flex items-center" style={{ fontSize: 9, color: "var(--text-muted)" }}>
                {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
                  <span key={i} style={{ flex: 1, textAlign: "center" }}>
                    {d}
                  </span>
                ))}
              </div>
            </div>

            {profile && profile.strong_skills.length > 0 && (
              <div className="panel" style={{ padding: 14 }}>
                <div className="up ghost text-[10px] tracking-[0.2em] mb-2">
                  › {lang === "ru" ? "СИЛЬНЫЕ" : "STRONG"}
                </div>
                <div className="flex flex-wrap gap-1">
                  {profile.strong_skills.map((s) => (
                    <span key={s} className="chip on">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {profile && profile.weak_skills.length > 0 && (
              <div className="panel" style={{ padding: 14 }}>
                <div className="up ghost text-[10px] tracking-[0.2em] mb-2">
                  › {lang === "ru" ? "НА ДОРАБОТКЕ" : "TO PRACTICE"}
                </div>
                <div className="flex flex-wrap gap-1">
                  {profile.weak_skills.map((s) => (
                    <span
                      key={s}
                      className="chip"
                      style={{
                        color: "var(--error)",
                        borderColor: "rgba(232,112,147,0.4)",
                      }}
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
