"use client";

import { cn } from "@/lib/utils";
import { MathRenderer } from "./MathRenderer";
import type { MessageRole, TutorMoveType } from "@/types/api";

interface MessageProps {
  role: MessageRole;
  content: string;
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
  moveType,
  isStreaming,
}: MessageProps) {
  const isTutor = role === "tutor" || role === "system";

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
