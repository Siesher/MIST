"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AppShell } from "@/components/cyber/AppShell";
import { MitsMark } from "@/components/cyber/MitsMark";
import { Glitch } from "@/components/cyber/Glitch";
import { Typed } from "@/components/cyber/Typed";
import { useChatStore } from "@/store/chatStore";
import { listSessions } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const QUICK_TOPICS = [
  { id: "derivatives", label: "Производные", domain: "math" },
  { id: "integrals", label: "Интегралы", domain: "math" },
  { id: "limits", label: "Пределы", domain: "math" },
  { id: "linear_algebra", label: "Линейная алгебра", domain: "math" },
  { id: "mechanics", label: "Механика", domain: "phys" },
  { id: "dp", label: "DP / Алгоритмы", domain: "cs" },
];

const DOMAIN_COLOR: Record<string, string> = {
  math: "var(--violet)",
  phys: "var(--yellow)",
  chem: "var(--cyan)",
  cs: "var(--magenta)",
};

export default function HomePage() {
  const { lang, t } = useI18n();
  const setSessions = useChatStore((s) => s.setSessions);

  useEffect(() => {
    async function load() {
      try {
        const result = await listSessions();
        setSessions(result.sessions);
      } catch {
        /* backend may be offline */
      }
    }
    load();
  }, [setSessions]);

  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto p-10">
        <div className="max-w-4xl mx-auto">
          {/* Hero */}
          <div className="flex items-center gap-5 mb-8">
            <MitsMark size={64} />
            <div>
              <Glitch className="font-display" text="MITS">
                <span
                  style={{
                    fontSize: 42,
                    fontWeight: 700,
                    letterSpacing: "0.02em",
                    color: "var(--text)",
                    lineHeight: 1.1,
                  }}
                >
                  MITS
                </span>
              </Glitch>
              <div className="ghost mt-1" style={{ fontSize: 11, letterSpacing: "0.22em" }}>
                {"// math · intelligent · tutoring · system"}
              </div>
            </div>
          </div>

          {/* Tagline + terminal */}
          <div
            className="panel cornered mb-10"
            style={{ padding: 24, position: "relative" }}
          >
            <span className="corner-tl" />
            <span className="corner-br" />
            <div
              className="font-display neon-v"
              style={{
                fontSize: 26,
                fontWeight: 600,
                marginBottom: 14,
                letterSpacing: "0.02em",
              }}
            >
              {lang === "ru"
                ? "Сократический репетитор, обученный по 3-ступенчатому RL-протоколу"
                : "Socratic tutor, trained via 3-stage RL protocol"}
            </div>
            <div
              style={{
                fontSize: 12,
                color: "var(--text-dim)",
                letterSpacing: "0.08em",
                marginBottom: 18,
              }}
            >
              {lang === "ru"
                ? "// GSPO (triple reward) → KTO (Socratic alignment) → DPO (polish). Base 55.1% → 66.5% на STEM benchmark."
                : "// GSPO (triple reward) → KTO (Socratic alignment) → DPO (polish). Base 55.1% → 66.5% on STEM benchmark."}
            </div>

            <div
              style={{
                padding: 14,
                background: "rgba(0,0,0,0.5)",
                border: "1px solid var(--line)",
                fontSize: 11,
                color: "var(--text-dim)",
                fontFamily: "var(--font-mono)",
                borderRadius: 3,
              }}
            >
              <div>
                <span className="y">❯</span> booting orchestrator...
              </div>
              <div>
                [<span className="y">OK</span>] profiler · planner · tutor · verifier
              </div>
              <div>
                [<span className="y">OK</span>] ollama · qwen3.5-9b · loaded in 2.4s
              </div>
              <div>
                [<span className="y">OK</span>] chromadb · 43,919 chunks
              </div>
              <div>
                [<span className="y">OK</span>] sympy · chempy bridges
              </div>
              <div>
                [<span className="y">OK</span>] bkt + dkt tracers · 40 skills
              </div>
              <div>
                <Typed text="awaiting handshake..." speed={40} />
              </div>
            </div>
          </div>

          {/* Quick topics */}
          <div className="mb-6">
            <div className="up ghost text-[10px] tracking-[0.22em] mb-3">
              › {t("suggested")}
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              {QUICK_TOPICS.map((topic) => (
                <Link
                  key={topic.id}
                  href="/chat"
                  className="font-mono panel flex items-center gap-3 cursor-pointer transition-all hover:shadow-glow-v"
                  style={{
                    padding: "14px 16px",
                    fontSize: 13,
                    color: "var(--text)",
                    textDecoration: "none",
                  }}
                >
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      background: DOMAIN_COLOR[topic.domain],
                      boxShadow: `0 0 6px ${DOMAIN_COLOR[topic.domain]}`,
                    }}
                  />
                  <span className="flex-1">{topic.label}</span>
                  <span className="v">›</span>
                </Link>
              ))}
            </div>
          </div>

          {/* Stats */}
          <div
            className="grid grid-cols-4"
            style={{
              gap: 1,
              background: "var(--line-hi)",
              border: "1px solid var(--line-hi)",
            }}
          >
            {[
              ["accuracy", "66.5%"],
              ["stages", "GSPO · KTO · DPO"],
              ["skills", "40+"],
              ["benchmark", "3 678"],
            ].map(([k, v]) => (
              <div key={k} style={{ background: "var(--surface)", padding: 18 }}>
                <div className="ghost up text-[10px] tracking-[0.18em]">{k}</div>
                <div
                  className="font-display mt-1"
                  style={{ fontSize: 20, color: "var(--text)", fontWeight: 600 }}
                >
                  {v}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
