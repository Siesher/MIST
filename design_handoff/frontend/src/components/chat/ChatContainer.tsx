"use client";

import { useEffect, useRef } from "react";
import { Message, TypingIndicator } from "./Message";
import { ChatInput } from "./ChatInput";
import { ThinkingPanel } from "./ThinkingPanel";
import { MitsMark } from "@/components/cyber/MitsMark";
import { Glitch } from "@/components/cyber/Glitch";
import { useChatStore } from "@/store/chatStore";
import { useI18n } from "@/lib/i18n";
import type { Message as MessageType, TutorMoveType, ChatMode } from "@/types/api";

const EMPTY_MESSAGES: MessageType[] = [];

interface ChatContainerProps {
  sessionId: string;
  onSendMessage: (content: string) => void;
  onHintRequest?: () => void;
  onModeChange?: (mode: ChatMode) => void;
  hasTask?: boolean;
  hintsRemaining?: number;
}

export function ChatContainer({
  sessionId,
  onSendMessage,
  onHintRequest,
  onModeChange,
  hasTask = false,
  hintsRemaining = 0,
}: ChatContainerProps) {
  const { t, lang } = useI18n();
  const messages = useChatStore((s) => s.messages[sessionId] ?? EMPTY_MESSAGES);
  const streamingMessage = useChatStore((s) => s.streamingMessage);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const isLoading = useChatStore((s) => s.isLoading);
  const currentMode = useChatStore((s) => s.sessionModes[sessionId] ?? "guided_learning");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingMessage]);

  const emptyMessage =
    currentMode === "chat"
      ? lang === "ru"
        ? "Свободный чат — спрашивай о чём угодно"
        : "Free chat — ask anything"
      : currentMode === "guided_learning"
      ? lang === "ru"
        ? "Сократический режим · начни диалог"
        : "Socratic mode · start a dialogue"
      : lang === "ru"
      ? "Генератор задач — укажи тему и сложность"
      : "Task generator — specify topic & difficulty";

  return (
    <div className="flex flex-col h-full">
      {/* Greeter */}
      <div
        style={{
          padding: "16px 28px",
          borderBottom: "1px solid var(--line)",
          background: "rgba(0,0,0,0.3)",
        }}
      >
        <div className="flex items-center gap-3">
          <MitsMark size={34} />
          <div>
            <Glitch className="font-display" text={lang === "ru" ? "Гримуар открыт" : "Grimoire open"}>
              <span style={{ fontSize: 18, fontWeight: 600, color: "var(--text)" }}>
                {lang === "ru" ? "Гримуар открыт" : "Grimoire open"}
              </span>
            </Glitch>
            <div className="ghost" style={{ fontSize: 10, letterSpacing: "0.12em", marginTop: 2 }}>
              {"// "}{t("model")} · agents ready · SymPy online
            </div>
          </div>
          <div className="flex-1" />
          <span className="chip v">DIFFICULTY: ADAPTIVE</span>
          <span className="chip">DOMAIN: MATH</span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto" style={{ padding: "14px 28px" }}>
        <div className="max-w-3xl mx-auto">
          {messages.length === 0 && !isLoading && (
            <div className="flex items-center justify-center h-64">
              <div className="text-center">
                <MitsMark size={48} />
                <p
                  className="font-display mt-3"
                  style={{ fontSize: 18, color: "var(--text)", letterSpacing: "0.04em" }}
                >
                  MITS
                </p>
                <p className="ghost mt-2" style={{ fontSize: 12, letterSpacing: "0.1em" }}>
                  {emptyMessage}
                </p>
              </div>
            </div>
          )}

          {messages.map((msg: MessageType) => (
            <Message
              key={msg.id}
              role={msg.role}
              content={msg.content}
              moveType={msg.move_type as TutorMoveType | undefined}
              isCorrect={msg.is_correct}
              timestamp={msg.timestamp}
            />
          ))}

          {isStreaming && streamingMessage && (
            <div className="py-2">
              {streamingMessage.thinkingContent && (
                <ThinkingPanel
                  content={streamingMessage.thinkingContent}
                  isActive={streamingMessage.isThinking}
                  isLive={true}
                />
              )}
              {!streamingMessage.isThinking && streamingMessage.content && (
                <Message role="tutor" content={streamingMessage.content} isStreaming={true} />
              )}
            </div>
          )}

          {isLoading && !isStreaming && <TypingIndicator />}

          <div ref={bottomRef} className="h-4" />
        </div>
      </div>

      <ChatInput
        onSend={onSendMessage}
        onHintRequest={onHintRequest}
        onModeChange={onModeChange}
        disabled={isLoading || isStreaming}
        hasTask={hasTask}
        hintsRemaining={hintsRemaining}
        currentMode={currentMode}
      />
    </div>
  );
}
