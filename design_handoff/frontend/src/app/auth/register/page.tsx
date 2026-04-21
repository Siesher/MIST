"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import { MitsMark } from "@/components/cyber/MitsMark";
import { Glitch } from "@/components/cyber/Glitch";
import { useI18n } from "@/lib/i18n";

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();
  const { t, lang, setLang } = useI18n();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError("Пароли не совпадают");
      return;
    }
    if (password.length < 6) {
      setError("Пароль должен быть не менее 6 символов");
      return;
    }
    setLoading(true);
    try {
      await register(email, password, displayName);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка регистрации");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 flex items-center justify-center z-10">
      <div
        className="cornered relative z-[3]"
        style={{
          width: 560,
          maxWidth: "92%",
          background: "var(--surface)",
          border: "1px solid var(--violet)",
          boxShadow: "0 0 40px rgba(165,131,255,0.4)",
          padding: "40px 36px",
        }}
      >
        <span className="corner-tl" />
        <span className="corner-br" />

        <div className="flex items-center gap-2 mb-6">
          <MitsMark size={36} />
          <div className="flex flex-col">
            <Glitch className="font-display" text="MITS">
              <span style={{ fontSize: 20, fontWeight: 600, letterSpacing: "0.02em" }}>MITS</span>
            </Glitch>
            <span className="ghost" style={{ fontSize: 9, letterSpacing: "0.22em" }}>
              math · intelligent · tutoring · system
            </span>
          </div>
          <div className="flex-1" />
          <button
            onClick={() => setLang(lang === "ru" ? "en" : "ru")}
            className="cbtn cbtn-ghost text-[10px]"
          >
            {lang === "ru" ? "RU" : "EN"} ⇄
          </button>
        </div>

        <div className="flex items-center mb-5">
          <Link
            href="/auth/login"
            style={{
              color: "var(--text-muted)",
              fontSize: 12,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              paddingBottom: 6,
              textDecoration: "none",
              marginRight: 16,
            }}
          >
            ❯ {t("auth_login")}
          </Link>
          <span
            className="font-mono"
            style={{
              color: "var(--text)",
              fontSize: 12,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              paddingBottom: 6,
              borderBottom: "1px solid var(--yellow)",
            }}
          >
            ❯ {t("auth_register")}
          </span>
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
            <span className="up ghost text-[9px] tracking-[0.2em]">❯ {t("auth_name")}</span>
            <input
              className="cinput"
              type="text"
              placeholder={lang === "ru" ? "Максим" : "Maxim"}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
              autoComplete="name"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="up ghost text-[9px] tracking-[0.2em]">❯ {t("auth_email")}</span>
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
            <span className="up ghost text-[9px] tracking-[0.2em]">❯ {t("auth_pass")}</span>
            <input
              className="cinput"
              type="password"
              placeholder="•••••• (min 6)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="up ghost text-[9px] tracking-[0.2em]">
              ❯ {lang === "ru" ? "повторите пароль" : "confirm password"}
            </span>
            <input
              className="cinput"
              type="password"
              placeholder="••••••"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              autoComplete="new-password"
            />
          </label>

          <div className="flex items-center gap-2 text-[10px] text-cyber-text-muted mt-1">
            <span className="y">◆</span>
            <span>
              {lang === "ru"
                ? "Argon2 + JWT · пароль хэшируется локально"
                : "Argon2 + JWT · password hashed client-side"}
            </span>
          </div>

          <button
            type="submit"
            className="cbtn cbtn-primary justify-center mt-3"
            style={{ padding: "12px 16px", fontSize: 12, letterSpacing: "0.2em" }}
            disabled={loading}
          >
            {loading ? "..." : `⟦ ${t("auth_register")} ⟧ →`}
          </button>
        </form>

        <div className="flex items-center mt-4 text-[10px] text-cyber-text-muted">
          <div className="flex-1" />
          <Link
            href="/auth/login"
            className="cbtn cbtn-ghost !p-0 text-[10px]"
            style={{ textDecoration: "none" }}
          >
            {t("auth_to_login")} ›
          </Link>
        </div>
      </div>
    </div>
  );
}
