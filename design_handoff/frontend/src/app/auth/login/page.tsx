"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import { MitsMark } from "@/components/cyber/MitsMark";
import { Glitch } from "@/components/cyber/Glitch";
import { Typed } from "@/components/cyber/Typed";
import { useI18n } from "@/lib/i18n";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const { t, lang, setLang } = useI18n();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка входа");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 flex items-center justify-center z-10">
      <div
        className="cornered relative z-[3]"
        style={{
          width: 900,
          maxWidth: "92%",
          display: "grid",
          gridTemplateColumns: "1.1fr 1fr",
          background: "var(--surface)",
          border: "1px solid var(--violet)",
          boxShadow: "0 0 40px rgba(165,131,255,0.4)",
        }}
      >
        <span className="corner-tl" />
        <span className="corner-br" />

        {/* Left — hero */}
        <div
          style={{
            padding: "40px 36px",
            borderRight: "1px solid var(--line-hi)",
            background: "radial-gradient(ellipse at top left, rgba(165,131,255,0.14), transparent 60%)",
            position: "relative",
            overflow: "hidden",
          }}
        >
          <div className="flex items-center gap-2 mb-8">
            <MitsMark size={40} />
            <div className="flex flex-col">
              <span
                className="font-display"
                style={{ fontSize: 22, fontWeight: 600, letterSpacing: "0.02em" }}
              >
                MITS
              </span>
              <span className="ghost" style={{ fontSize: 9, letterSpacing: "0.22em" }}>
                math · intelligent · tutoring · system
              </span>
            </div>
          </div>

          <Glitch className="font-display" text={t("auth_welcome_line1")}>
            <span
              style={{
                fontSize: 32,
                fontWeight: 700,
                letterSpacing: "0.02em",
                color: "var(--text)",
                lineHeight: 1.1,
              }}
            >
              {t("auth_welcome_line1")}
            </span>
          </Glitch>
          <div
            style={{
              fontSize: 13,
              color: "var(--text-dim)",
              marginTop: 10,
              letterSpacing: "0.08em",
            }}
          >
            {"// "}{t("auth_welcome_line2")}
          </div>

          <div
            style={{
              marginTop: 28,
              padding: 14,
              background: "rgba(0,0,0,0.5)",
              border: "1px solid var(--line)",
              fontSize: 11,
              color: "var(--text-dim)",
              fontFamily: "var(--font-mono)",
              minHeight: 140,
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

          <div
            style={{
              position: "absolute",
              bottom: 20,
              left: 36,
              right: 36,
              fontSize: 10,
              color: "var(--text-muted)",
              letterSpacing: "0.14em",
              borderTop: "1px dashed var(--line)",
              paddingTop: 10,
            }}
          >
            {lang === "ru"
              ? "МГТУ им. Баумана · дипломная работа · 2024–2026"
              : "Bauman MSTU · thesis project · 2024–2026"}
          </div>
        </div>

        {/* Right — form */}
        <div style={{ padding: "40px 36px", position: "relative" }}>
          <div className="flex items-center mb-7">
            <span
              className="font-mono"
              style={{
                color: "var(--text)",
                fontSize: 12,
                letterSpacing: "0.2em",
                textTransform: "uppercase",
                paddingBottom: 6,
                borderBottom: "1px solid var(--yellow)",
                marginRight: 16,
              }}
            >
              ❯ {t("auth_login")}
            </span>
            <Link
              href="/auth/register"
              style={{
                color: "var(--text-muted)",
                fontSize: 12,
                letterSpacing: "0.2em",
                textTransform: "uppercase",
                paddingBottom: 6,
                textDecoration: "none",
              }}
            >
              ❯ {t("auth_register")}
            </Link>
            <div className="flex-1" />
            <button
              onClick={() => setLang(lang === "ru" ? "en" : "ru")}
              className="cbtn cbtn-ghost text-[10px]"
            >
              {lang === "ru" ? "RU" : "EN"} ⇄
            </button>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            {error && (
              <div
                style={{
                  background: "rgba(232, 112, 147, 0.1)",
                  color: "var(--error)",
                  fontSize: 11,
                  padding: "8px 12px",
                  border: "1px solid rgba(232, 112, 147, 0.3)",
                  borderRadius: 3,
                }}
              >
                {error}
              </div>
            )}

            <label className="flex flex-col gap-1">
              <span className="up ghost text-[9px] tracking-[0.2em]">
                ❯ {t("auth_email")}
              </span>
              <input
                className="cinput"
                type="email"
                placeholder="siesher@mits.sys"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="up ghost text-[9px] tracking-[0.2em]">
                ❯ {t("auth_pass")}
              </span>
              <input
                className="cinput"
                type="password"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </label>

            <button
              type="submit"
              className="cbtn cbtn-primary justify-center mt-3"
              style={{ padding: "12px 16px", fontSize: 12, letterSpacing: "0.2em" }}
              disabled={loading}
            >
              {loading ? "..." : `⟦ ${t("auth_login")} ⟧ →`}
            </button>
          </form>

          <div className="flex items-center mt-4 text-[10px] text-cyber-text-muted">
            <button className="cbtn cbtn-ghost !p-0 text-[10px]">{t("auth_forgot")}</button>
            <div className="flex-1" />
            <Link
              href="/auth/register"
              className="cbtn cbtn-ghost !p-0 text-[10px]"
              style={{ textDecoration: "none" }}
            >
              {t("auth_to_register")} ›
            </Link>
          </div>

          <div
            style={{
              position: "absolute",
              bottom: 20,
              left: 36,
              right: 36,
              fontSize: 9,
              color: "var(--text-ghost)",
              borderTop: "1px dashed var(--line)",
              paddingTop: 10,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
            }}
          >
            session · anonymous · no tracking
          </div>
        </div>
      </div>
    </div>
  );
}
