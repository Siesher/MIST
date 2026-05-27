"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { NewAppShell } from "@/components/newdesign/AppShell";
import { ChatMain, ChatRail } from "@/components/newdesign/ChatScreen";
import { useChat } from "@/hooks/useChat";
import { useChatStore } from "@/store/chatStore";
import { getSession } from "@/lib/api";
import type { Message } from "@/types/api";

interface TaskInfo {
  topic?: string;
  difficulty?: string | null;
  problem?: string;
}

export default function ChatPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;

  const setActiveSession = useChatStore((s) => s.setActiveSession);
  const setMessages = useChatStore((s) => s.setMessages);
  const setSessionMode = useChatStore((s) => s.setSessionMode);
  const [task, setTask] = useState<TaskInfo | undefined>(undefined);

  const { sendMessage, requestHint, changeMode } = useChat({
    sessionId,
    useStreaming: true,
  });

  useEffect(() => {
    setActiveSession(sessionId);

    (async () => {
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
        if (detail.task || detail.topic) {
          setTask({
            topic: detail.task?.topic ?? detail.topic,
            difficulty: detail.task?.difficulty ?? detail.difficulty ?? null,
            problem: detail.task?.problem,
          });
        }
      } catch {
        /* session may not exist yet */
      }
    })();
  }, [sessionId, setActiveSession, setMessages, setSessionMode]);

  return (
    <NewAppShell rail={<ChatRail sessionId={sessionId} />}>
      <ChatMain
        sessionId={sessionId}
        onSendMessage={sendMessage}
        onHintRequest={requestHint}
        onModeChange={changeMode}
        task={task}
      />
    </NewAppShell>
  );
}
