"use client";

import { useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/store/chatStore";
import { createSession, deleteSession } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";
import { MitsMark } from "@/components/cyber/MitsMark";
import { Glitch } from "@/components/cyber/Glitch";
import { useI18n, type StringKey } from "@/lib/i18n";
import type { Session, ChatMode } from "@/types/api";

const topicLabels: Record<string, string> = {
  derivatives: "Производные",
  integrals: "Интегралы",
  limits: "Пределы",
  series: "Ряды",
  equations: "Уравнения",
  linear_algebra: "Линейная алгебра",
};

const NAV_ITEMS: { id: string; icon: string; labelKey: StringKey | null; label?: string; href: string }[] = [
  { id: "chat", icon: "◈", labelKey: "nav_chat", href: "/" },
  { id: "graph", icon: "◎", labelKey: "nav_graph", href: "/graph" },
  { id: "tasks", icon: "◇", labelKey: "nav_tasks", href: "/tasks" },
  { id: "sources", icon: "▤", labelKey: "nav_sources", href: "/sources" },
  { id: "profile", icon: "⊙", labelKey: "nav_profile", href: "/profile" },
  { id: "settings", icon: "⚙", labelKey: null, label: "Настройки", href: "/settings" },
];

export function Sidebar() {
  const router = useRouter();
  const pathname = usePathname() || "/";
  const { t } = useI18n();
  const { isAuthenticated, logout } = useAuth();
  const sessions = useChatStore((s) => s.sessions);
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const addSession = useChatStore((s) => s.addSession);
  const removeSession = useChatStore((s) => s.removeSession);
  const setActiveSession = useChatStore((s) => s.setActiveSession);

  const activeView =
    pathname.startsWith("/chat") || pathname === "/"
      ? "chat"
      : pathname.startsWith("/graph")
      ? "graph"
      : pathname.startsWith("/tasks")
      ? "tasks"
      : pathname.startsWith("/sources")
      ? "sources"
      : pathname.startsWith("/profile")
      ? "profile"
      : pathname.startsWith("/settings")
      ? "settings"
      : null;

  const handleNewChat = useCallback(async () => {
    try {
      const preferredMode =
        (typeof window !== "undefined"
          ? (localStorage.getItem("mits-preferred-mode") as ChatMode | null)
          : null) ?? "guided_learning";
      const session = await createSession({ mode: preferredMode });
      const sessionData: Session = {
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
      };
      addSession(sessionData);
      setActiveSession(session.id);
      router.push(`/chat/${session.id}`);
    } catch (e) {
      console.error("Failed to create session:", e);
    }
  }, [addSession, setActiveSession, router]);

  const handleSelectSession = useCallback(
    (sessionId: string) => {
      setActiveSession(sessionId);
      router.push(`/chat/${sessionId}`);
    },
    [setActiveSession, router],
  );

  const handleDeleteSession = useCallback(
    async (e: React.MouseEvent, sessionId: string) => {
      e.stopPropagation();
      e.preventDefault();
      try {
        await deleteSession(sessionId);
        removeSession(sessionId);
        if (activeSessionId === sessionId) {
          setActiveSession(null);
          router.push("/");
        }
      } catch (err) {
        console.error("Failed to delete session:", err);
      }
    },
    [removeSession, activeSessionId, setActiveSession, router],
  );

  return (
    <aside
      className="flex flex-col relative z-[2]"
      style={{
        width: 240,
        flex: "0 0 240px",
        borderRight: "1px solid var(--line)",
        background: "rgba(0,0,0,0.3)",
        backdropFilter: "blur(14px)",
        WebkitBackdropFilter: "blur(14px)",
        boxShadow: "inset 0 1px 0 rgba(196, 169, 255, 0.06), inset -1px 0 0 rgba(165, 131, 255, 0.06)",
      }}
    >
      {/* Brand */}
      <div style={{ padding: "18px 16px 14px", borderBottom: "1px solid var(--line)" }}>
        <div className="flex items-center gap-3">
          <MitsMark size={34} />
          <div className="flex flex-col">
            <Glitch className="font-display" text="MITS">
              <span style={{ fontSize: 18, fontWeight: 600, letterSpacing: "0.04em" }}>MITS</span>
            </Glitch>
            <span className="ghost" style={{ fontSize: 9, letterSpacing: "0.22em" }}>
              v.2.6.1
            </span>
          </div>
        </div>
      </div>

      {/* New chat button */}
      <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--line)" }}>
        <button
          onClick={handleNewChat}
          className="cbtn cbtn-primary w-full justify-center text-[13px]"
          style={{ padding: "11px 14px", letterSpacing: "0.16em" }}
        >
          ＋ {t("new_session")}
        </button>
      </div>

      {/* Nav */}
      <nav style={{ padding: 12, display: "flex", flexDirection: "column", gap: 3 }}>
        {NAV_ITEMS.map((it) => {
          const active = activeView === it.id;
          return (
            <Link
              key={it.id}
              href={it.href}
              className="font-mono flex items-center gap-3 relative transition-all"
              style={{
                textAlign: "left",
                background: active
                  ? "linear-gradient(90deg, rgba(165,131,255,0.18), rgba(165,131,255,0.04))"
                  : "transparent",
                borderLeft: "2px solid " + (active ? "var(--violet)" : "transparent"),
                color: active ? "var(--text)" : "var(--text-dim)",
                padding: "12px 14px",
                fontSize: 14,
                letterSpacing: "0.08em",
                textDecoration: "none",
              }}
            >
              <span
                style={{
                  color: active ? "var(--yellow)" : "var(--violet)",
                  fontSize: 18,
                }}
              >
                {it.icon}
              </span>
              <span style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>
                {it.labelKey ? t(it.labelKey) : it.label}
              </span>
              {active && (
                <span
                  style={{
                    position: "absolute",
                    right: 10,
                    color: "var(--yellow)",
                    fontSize: 10,
                  }}
                >
                  ›
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Session history */}
      <div
        style={{
          padding: "8px 14px",
          borderTop: "1px solid var(--line)",
          marginTop: 4,
          overflowY: "auto",
          flex: "1 1 auto",
          minHeight: 0,
        }}
      >
        <div className="up ghost text-[9px] mb-2 tracking-[0.2em]">› {t("sessions")}</div>
        <div className="flex flex-col gap-0.5 text-[11px]">
          {sessions.length === 0 && (
            <div className="ghost text-center py-4 text-[10px]">— пусто —</div>
          )}
          {sessions.slice(0, 15).map((s) => {
            const isActive = activeSessionId === s.id;
            const title = s.topic ? topicLabels[s.topic] || s.topic : "Свободная тема";
            return (
              <button
                key={s.id}
                onClick={() => handleSelectSession(s.id)}
                className={cn(
                  "group flex items-center gap-2 cursor-pointer w-full text-left",
                )}
                style={{
                  color: isActive ? "var(--text)" : "var(--text-muted)",
                  padding: "4px 8px",
                  borderLeft: "1px solid " + (isActive ? "var(--yellow)" : "transparent"),
                  transition: "all 100ms",
                }}
              >
                <span>{isActive ? "▸" : "·"}</span>
                <span className="flex-1 truncate">{title}</span>
                <span
                  role="button"
                  aria-label="delete"
                  onClick={(e) => handleDeleteSession(e, s.id)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity text-cyber-error"
                  style={{ fontSize: 10 }}
                >
                  ✕
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <div style={{ padding: 12, borderTop: "1px solid var(--line)" }}>
        {isAuthenticated ? (
          <button
            className="cbtn cbtn-ghost w-full justify-center text-[10px]"
            onClick={async () => {
              await logout();
              router.push("/");
            }}
          >
            ⏻ {t("nav_logout")}
          </button>
        ) : (
          <Link
            href="/auth/login"
            className="cbtn cbtn-ghost w-full justify-center text-[10px]"
            style={{ textDecoration: "none" }}
          >
            ◆ {t("auth_login")}
          </Link>
        )}
      </div>
    </aside>
  );
}
