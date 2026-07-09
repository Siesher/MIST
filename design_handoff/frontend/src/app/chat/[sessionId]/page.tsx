"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/cyber/AppShell";
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
  const sessionState = useChatStore((s) => s.sessionStates[sessionId]);
  const setSessionMode = useChatStore((s) => s.setSessionMode);

  const { sendMessage, requestHint, changeMode } = useChat({
    sessionId,
    useStreaming: true,
  });

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
        if (detail.mode) setSessionMode(sessionId, detail.mode);
      } catch {
        /* session may not exist */
      }
    }

    async function loadSessions() {
      try {
        const result = await listSessions();
        setSessions(result.sessions);
      } catch {
        /* backend offline */
      }
    }

    loadSession();
    loadSessions();
  }, [sessionId, setActiveSession, setMessages, setSessions, setSessionMode]);

  const hintsRemaining = sessionState ? Math.max(0, 3 - sessionState.hints_used) : 3;

  return (
    <AppShell>
      <ChatContainer
        sessionId={sessionId}
        onSendMessage={sendMessage}
        onHintRequest={requestHint}
        onModeChange={changeMode}
        hasTask={true}
        hintsRemaining={hintsRemaining}
      />
    </AppShell>
  );
}
