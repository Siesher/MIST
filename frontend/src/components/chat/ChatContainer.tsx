"use client";

import { useEffect, useRef } from "react";
import { Message, TypingIndicator } from "./Message";
import { ChatInput } from "./ChatInput";
import { useChatStore } from "@/store/chatStore";
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
  const messages = useChatStore((s) => s.messages[sessionId] ?? EMPTY_MESSAGES);
  const streamingMessage = useChatStore((s) => s.streamingMessage);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const isLoading = useChatStore((s) => s.isLoading);
  const currentMode = useChatStore((s) => s.sessionModes[sessionId] ?? "guided_learning");
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingMessage]);

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto">
          {messages.length === 0 && !isLoading && (
            <div className="flex items-center justify-center h-64 text-muted-foreground">
              <div className="text-center space-y-2">
                <div className="text-4xl">&#x1f4d0;</div>
                <p className="text-lg font-medium">MITS</p>
                <p className="text-sm">
                  {currentMode === "chat" && "Свободный чат — спрашивай о чём угодно"}
                  {currentMode === "guided_learning" && "Математический репетитор — начните новую сессию"}
                  {currentMode === "task_generator" && "Генератор задач — укажи тему и сложность"}
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

          {/* Streaming message with thinking */}
          {isStreaming && streamingMessage && (
            <>
              {/* Thinking section - collapsible */}
              {streamingMessage.thinkingContent && (
                <div className="px-4 md:px-8 py-2">
                  <details className="group" open={streamingMessage.isThinking}>
                    <summary className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer select-none hover:text-foreground transition-colors">
                      <svg
                        className="w-3 h-3 transition-transform group-open:rotate-90"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                      <span className="flex items-center gap-1.5">
                        {streamingMessage.isThinking && (
                          <span className="inline-block w-1.5 h-1.5 bg-amber-500 rounded-full animate-pulse" />
                        )}
                        {streamingMessage.isThinking ? "Размышления модели..." : "Размышления модели"}
                      </span>
                    </summary>
                    <div className="mt-2 pl-5 text-xs text-muted-foreground/80 font-mono whitespace-pre-wrap border-l-2 border-amber-500/30 max-h-64 overflow-y-auto">
                      {streamingMessage.thinkingContent}
                    </div>
                  </details>
                </div>
              )}
              {/* Response content */}
              {!streamingMessage.isThinking && streamingMessage.content && (
                <Message
                  role="tutor"
                  content={streamingMessage.content}
                  isStreaming={true}
                />
              )}
            </>
          )}

          {/* Typing indicator */}
          {isLoading && !isStreaming && <TypingIndicator />}

          {/* Scroll anchor */}
          <div ref={bottomRef} className="h-4" />
        </div>
      </div>

      {/* Input */}
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
