"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { ChatContainer } from "@/components/chat/ChatContainer";
import { useChat } from "@/hooks/useChat";
import { useChatStore } from "@/store/chatStore";
import { getSession, listSessions } from "@/lib/api";
import type { Message } from "@/types/api";

export default function ChatPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;

  const setActiveSession = useChatStore((s) => s.setActiveSession);
  const setMessages = useChatStore((s) => s.setMessages);
  const setSessions = useChatStore((s) => s.setSessions);
  const toggleSidebar = useChatStore((s) => s.toggleSidebar);
  const sessionState = useChatStore((s) => s.sessionStates[sessionId]);

  const setSessionMode = useChatStore((s) => s.setSessionMode);

  const { sendMessage, requestHint, changeMode } = useChat({
    sessionId,
    useStreaming: true,
  });

  // Load session data
  useEffect(() => {
    setActiveSession(sessionId);

    async function loadSession() {
      try {
        const detail = await getSession(sessionId);
        const msgs: Message[] = detail.messages.map((m) => ({
          id: m.id,
          session_id: m.session_id,
          role: m.role,
          content: m.content,
          timestamp: m.timestamp,
          move_type: m.move_type,
          is_correct: m.is_correct,
        }));
        setMessages(sessionId, msgs);
        if (detail.mode) {
          setSessionMode(sessionId, detail.mode);
        }
      } catch {
        // Session might not exist
      }
    }

    async function loadSessions() {
      try {
        const result = await listSessions();
        setSessions(result.sessions);
      } catch {
        // Backend might not be running
      }
    }

    loadSession();
    loadSessions();
  }, [sessionId, setActiveSession, setMessages, setSessions, setSessionMode]);

  // Apply theme from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("mits-theme") as "dark" | "light" | null;
    if (saved) {
      useChatStore.getState().setTheme(saved);
    } else {
      document.documentElement.classList.add("dark");
    }
  }, []);

  const hintsRemaining = sessionState
    ? Math.max(0, 3 - sessionState.hints_used)
    : 3;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0">
        {/* Top bar (mobile) */}
        <header className="flex items-center gap-2 px-4 py-2 border-b border-border md:hidden">
          <button
            onClick={toggleSidebar}
            className="p-1.5 rounded-md hover:bg-accent"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-5 h-5"
            >
              <path
                fillRule="evenodd"
                d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z"
                clipRule="evenodd"
              />
            </svg>
          </button>
          <span className="text-sm font-medium">MITS</span>
        </header>

        <ChatContainer
          sessionId={sessionId}
          onSendMessage={sendMessage}
          onHintRequest={requestHint}
          onModeChange={changeMode}
          hasTask={true}
          hintsRemaining={hintsRemaining}
        />
      </main>
    </div>
  );
}
