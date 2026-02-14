"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { MathRenderer } from "./MathRenderer";
import type { MessageRole, TutorMoveType } from "@/types/api";

interface MessageProps {
  role: MessageRole;
  content: string;
  thinking?: string | null;
  moveType?: TutorMoveType;
  isCorrect?: boolean;
  isStreaming?: boolean;
  timestamp?: string;
}

const moveTypeLabels: Record<TutorMoveType, string> = {
  scaffolding: "Разбираем по шагам",
  problematize: "Вопрос для размышления",
  rectify: "Исправление",
  encourage: "Отлично!",
  hint: "Подсказка",
  tell: "Объяснение",
  clarify: "Уточнение",
  system: "Система",
};

export function Message({
  role,
  content,
  thinking,
  moveType,
  isStreaming,
}: MessageProps) {
  const isTutor = role === "tutor" || role === "system";
  const [thinkingExpanded, setThinkingExpanded] = useState(false);

  // Count thinking tokens for display
  const thinkingTokens = thinking ? thinking.split(/\s+/).length : 0;

  return (
    <div
      className={cn(
        "flex w-full gap-3 py-4 px-4 md:px-8",
        isTutor ? "bg-muted/30" : "",
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-medium",
          isTutor
            ? "bg-amber-600 text-white"
            : "bg-blue-600 text-white",
        )}
      >
        {isTutor ? "T" : "S"}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">
            {isTutor ? "Репетитор" : "Вы"}
          </span>
          {moveType && isTutor && (
            <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
              {moveTypeLabels[moveType] || moveType}
            </span>
          )}
        </div>

        {/* Thinking block (collapsible) */}
        {thinking && isTutor && (
          <div className="mb-2">
            <button
              onClick={() => setThinkingExpanded(!thinkingExpanded)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <svg
                className={cn(
                  "w-3 h-3 transition-transform",
                  thinkingExpanded ? "rotate-90" : ""
                )}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              <span>
                {thinkingExpanded ? "Скрыть размышления" : "Показать размышления"}
              </span>
              <span className="text-muted-foreground/60">
                ({thinkingTokens} токенов)
              </span>
            </button>
            {thinkingExpanded && (
              <div className="mt-1.5 pl-4 border-l-2 border-amber-500/30 text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap">
                {thinking}
              </div>
            )}
          </div>
        )}

        <div className="text-sm leading-relaxed text-foreground/90 prose prose-sm dark:prose-invert max-w-none">
          <MathRenderer content={content} />
          {isStreaming && (
            <span className="inline-block w-2 h-4 ml-0.5 bg-amber-500 animate-pulse" />
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Typing indicator shown while tutor is generating.
 */
export function TypingIndicator() {
  return (
    <div className="flex w-full gap-3 py-4 px-4 md:px-8 bg-muted/30">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-600 text-white text-sm font-medium">
        T
      </div>
      <div className="flex items-center gap-1 pt-2">
        <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce [animation-delay:0ms]" />
        <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce [animation-delay:150ms]" />
        <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce [animation-delay:300ms]" />
      </div>
    </div>
  );
}
