"use client";

// MITS new_design — application shell (theme "midnight").
// Reproduces new_design's `.app.theme-midnight` CSS grid:
//   [NavRail 56px] [Sidebar 244px] [main 1fr] [ProjectRail 296px]
// REUSES the existing data layer (chatStore + api.listSessions/createSession).

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Icon } from "./icons";
import { useTheme, applyThemeToBody } from "./useTheme";
import { useChatStore } from "@/store/chatStore";
import { listSessions, createSession } from "@/lib/api";
import type { ChatMode, Session } from "@/types/api";

// ---------- Nav rail (leftmost) ----------
interface NavItem {
  href: string;
  icon: keyof typeof Icon;
  label: string;
  // match: prefix routes that should mark this item active
  match?: (path: string) => boolean;
}

const NAV_TOP: NavItem[] = [
  { href: "/", icon: "chat", label: "Чат", match: (p) => p === "/" || p.startsWith("/chat") },
  { href: "/tasks", icon: "list", label: "Задачи" },
  { href: "/graph", icon: "graph", label: "Граф знаний" },
  { href: "/dashboard", icon: "chart", label: "Аналитика" },
  { href: "/sources", icon: "database", label: "Источники" },
];

const NAV_BOTTOM: NavItem[] = [
  { href: "/profile", icon: "user", label: "Профиль" },
  { href: "/settings", icon: "settings", label: "Настройки" },
  { href: "/auth/login", icon: "signin", label: "Войти", match: (p) => p.startsWith("/auth") },
];

function NavRail() {
  const pathname = usePathname() || "/";
  const isActive = (it: NavItem) => (it.match ? it.match(pathname) : pathname.startsWith(it.href));

  const renderBtn = (it: NavItem) => (
    <Link key={it.href} href={it.href} className={"nav-btn " + (isActive(it) ? "active" : "")}>
      {Icon[it.icon]}
      <span className="nav-label">{it.label}</span>
    </Link>
  );

  return (
    <div className="nav-rail">
      {NAV_TOP.map(renderBtn)}
      <div className="nav-spacer" />
      {NAV_BOTTOM.map(renderBtn)}
    </div>
  );
}

// ---------- Session helpers ----------
function dotForMode(m: ChatMode | string): string {
  if (m === "guided_learning") return "#22A05A";
  if (m === "chat") return "#3B7DFF";
  if (m === "task_generator") return "#6800FF";
  return "#888";
}

function sessionTitle(s: Session): string {
  if (s.topic && s.topic.trim()) return s.topic;
  if (s.difficulty) return `Задача · ${s.difficulty}`;
  return "Новая сессия";
}

function timeLabel(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    if (sameDay) {
      return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
    }
    const diffDays = Math.round((now.getTime() - d.getTime()) / 86_400_000);
    if (diffDays === 1) return "Вчера";
    return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
  } catch {
    return "";
  }
}

// ---------- Sidebar (brand + new session + sessions list) ----------
function Sidebar() {
  const router = useRouter();
  const pathname = usePathname() || "/";
  const sessions = useChatStore((s) => s.sessions);
  const setSessions = useChatStore((s) => s.setSessions);
  const addSession = useChatStore((s) => s.addSession);
  const setActiveSession = useChatStore((s) => s.setActiveSession);
  const [creating, setCreating] = useState(false);

  // Active session id derived from the URL (/chat/<id>)
  const activeId = useMemo(() => {
    const m = pathname.match(/^\/chat\/([^/]+)/);
    return m ? m[1] : null;
  }, [pathname]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await listSessions();
        if (!cancelled) setSessions(result.sessions);
      } catch {
        /* backend may be offline — graceful fallback below */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setSessions]);

  const handleNewChat = async () => {
    if (creating) return;
    setCreating(true);
    try {
      const preferredMode =
        (typeof window !== "undefined"
          ? (localStorage.getItem("mits-preferred-mode") as ChatMode | null)
          : null) ?? "guided_learning";
      const session = await createSession({ mode: preferredMode });
      addSession({
        id: session.id,
        created_at: session.created_at,
        updated_at: session.updated_at,
        topic: session.topic,
        difficulty: session.difficulty,
        status: session.status,
        mode: session.mode ?? preferredMode,
        message_count: session.message_count,
        is_solved: session.is_solved,
        hints_used: session.hints_used,
      });
      setActiveSession(session.id);
      router.push(`/chat/${session.id}`);
    } catch (e) {
      console.error("Failed to create session:", e);
    } finally {
      setCreating(false);
    }
  };

  return (
    <aside className="sidebar">
      <Link href="/" className="brand" style={{ textDecoration: "none" }}>
        <div className="brand-mark">
          M
          <svg style={{ position: "absolute", inset: 0, opacity: 0.3 }} viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="0.5">
            <circle cx="16" cy="16" r="12" />
            <circle cx="16" cy="16" r="8" />
          </svg>
        </div>
        <div>
          <div className="brand-name">MITS</div>
          <div className="brand-tag">Math · Intelligent Tutoring</div>
        </div>
      </Link>

      <button className="new-chat magnetic" onClick={handleNewChat} disabled={creating}>
        {Icon.plus}
        <span>Новая сессия</span>
        <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono), monospace", fontSize: 10, opacity: 0.7 }}>⌘N</span>
      </button>

      <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
        <div className="section-label">Сессии</div>
        <div className="session-list">
          {sessions.length === 0 && (
            <div style={{ padding: "8px 10px", fontSize: 12, color: "var(--ink-mute)", lineHeight: 1.5 }}>
              Нет сессий. Нажмите «Новая сессия», чтобы начать.
            </div>
          )}
          {sessions.map((s) => (
            <Link
              key={s.id}
              href={`/chat/${s.id}`}
              onClick={() => setActiveSession(s.id)}
              className={"session " + (s.id === activeId ? "active" : "")}
              style={{ textDecoration: "none" }}
            >
              <span className="session-dot" style={{ background: dotForMode(s.mode) }} />
              <span className="session-title">{sessionTitle(s)}</span>
              <span className="session-meta">{timeLabel(s.updated_at || s.created_at)}</span>
            </Link>
          ))}
        </div>
      </div>

      <div className="sidebar-footer">
        <a
          className="foot-item"
          href="https://github.com/Siesher/MITS"
          target="_blank"
          rel="noopener noreferrer"
        >
          {Icon.bookOpen}
          <span>Документация</span>
        </a>
        <a className="gh-card" href="https://github.com/Siesher/MITS" target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none" }}>
          <span className="gh-avatar">SH</span>
          <div className="gh-info">
            <div className="gh-handle">{Icon.github} Siesher/MITS</div>
            <div className="gh-stars">★ 247 · main</div>
          </div>
        </a>
      </div>
    </aside>
  );
}

// ---------- Right rail (project / model info) ----------
const PIPELINE = [
  { stage: "GSPO", model: "mits-qwen3-9b-gspo", score: 60.2 },
  { stage: "KTO", model: "mits-qwen3-9b-kto", score: 64.1 },
  { stage: "DPO", model: "mits-qwen3-9b-final", score: 66.5 },
];

export function ProjectRail() {
  const modelName = useChatStore((s) => s.modelName);
  return (
    <aside className="rail">
      <div className="rail-card">
        <div className="rail-card-title">
          <span>Активная модель</span>
          <span className="pill">final</span>
        </div>
        <div style={{ fontFamily: "var(--font-mono), monospace", fontSize: 13, color: "var(--ink)" }}>
          {modelName || "mits-qwen3-9b-final"}
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-mute)", marginTop: 6 }}>GSPO → KTO → DPO · 9B · bf16</div>
        <div style={{ display: "flex", gap: 6, marginTop: 14, flexWrap: "wrap" }}>
          <span className="tag-chip">66.5% MGSM</span>
          <span className="tag-chip">+11.4 base</span>
        </div>
      </div>

      <div className="rail-card">
        <div className="rail-card-title">
          <span>Пайплайн обучения</span>
        </div>
        {PIPELINE.map((s) => (
          <div key={s.stage} style={{ display: "flex", alignItems: "center", gap: 12, padding: "7px 0", fontSize: 12.5 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent)" }} />
            <div style={{ flex: 1 }}>
              <div style={{ color: "var(--ink)" }}>{s.stage}</div>
              <div style={{ fontSize: 11, color: "var(--ink-mute)", fontFamily: "var(--font-mono), monospace", marginTop: 1 }}>{s.model}</div>
            </div>
            <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 12, color: "var(--ink-soft)" }}>{s.score}%</span>
          </div>
        ))}
      </div>

      <div className="rail-card">
        <div className="rail-card-title">
          <span>GitHub</span>
        </div>
        <a
          className="gh-card"
          href="https://github.com/Siesher/MITS"
          target="_blank"
          rel="noopener noreferrer"
          style={{ margin: 0, border: "none", padding: 0, background: "transparent", textDecoration: "none" }}
        >
          <span className="gh-avatar">SH</span>
          <div className="gh-info">
            <div className="gh-handle">Siesher/MITS</div>
            <div className="gh-stars">★ 247 · main</div>
          </div>
        </a>
      </div>
    </aside>
  );
}

// ---------- Midnight background decoration (drifting stars) ----------
function MidnightDecor() {
  // Deterministic positions to avoid SSR/CSR hydration mismatch.
  const stars = useMemo(() => {
    const out: { left: string; top: string; delay: string; dur: string }[] = [];
    let seed = 1337;
    const rand = () => {
      // simple LCG for stable pseudo-random values
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      return seed / 0x7fffffff;
    };
    for (let i = 0; i < 40; i++) {
      out.push({
        left: (rand() * 100).toFixed(3) + "%",
        top: (rand() * 100).toFixed(3) + "%",
        delay: (rand() * 8).toFixed(2) + "s",
        dur: (6 + rand() * 6).toFixed(2) + "s",
      });
    }
    return out;
  }, []);

  return (
    <div className="app-bg">
      <div className="particles">
        {stars.map((s, i) => (
          <span key={i} style={{ left: s.left, top: s.top, animationDelay: s.delay, animationDuration: s.dur }} />
        ))}
      </div>
    </div>
  );
}

// ---------- App shell ----------
interface AppShellProps {
  children: React.ReactNode;
  /** Right rail content; defaults to the project/model rail. */
  rail?: React.ReactNode;
}

export function NewAppShell({ children, rail }: AppShellProps) {
  const [theme] = useTheme();
  useEffect(() => {
    applyThemeToBody(theme);
  }, [theme]);
  return (
    <div className={`app theme-${theme}`}>
      <MidnightDecor />
      <NavRail />
      <Sidebar />
      {children}
      {rail ?? <ProjectRail />}
    </div>
  );
}
