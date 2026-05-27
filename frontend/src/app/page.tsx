"use client";

// Home / chat landing. Resolves to the most-recent session (or creates one)
// and redirects into the real chat route, which renders the new_design chat.
import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { NewAppShell } from "@/components/newdesign/AppShell";
import { useChatStore } from "@/store/chatStore";
import { listSessions, createSession } from "@/lib/api";
import type { ChatMode } from "@/types/api";

export default function HomePage() {
  const router = useRouter();
  const setSessions = useChatStore((s) => s.setSessions);
  const addSession = useChatStore((s) => s.addSession);
  const setActiveSession = useChatStore((s) => s.setActiveSession);
  const resolving = useRef(false);

  useEffect(() => {
    if (resolving.current) return;
    resolving.current = true;

    (async () => {
      try {
        const result = await listSessions();
        setSessions(result.sessions);
        if (result.sessions.length > 0) {
          // newest first (API returns recent first); fall back to sort by updated_at
          const sorted = [...result.sessions].sort(
            (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
          );
          const target = sorted[0];
          setActiveSession(target.id);
          router.replace(`/chat/${target.id}`);
          return;
        }
        // No sessions yet — create one so the chat screen has somewhere to stream.
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
        router.replace(`/chat/${session.id}`);
      } catch (e) {
        // Backend offline: stay on the shell with a hint.
        console.error("Failed to resolve a chat session:", e);
        resolving.current = false;
      }
    })();
  }, [router, setSessions, addSession, setActiveSession]);

  return (
    <NewAppShell>
      <main className="main">
        <div
          style={{
            flex: 1,
            display: "grid",
            placeItems: "center",
            color: "var(--ink-mute)",
            fontSize: 13,
          }}
        >
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 15, color: "var(--ink-soft)", marginBottom: 8 }}>MITS</div>
            <div>Открываем сессию…</div>
          </div>
        </div>
      </main>
    </NewAppShell>
  );
}
