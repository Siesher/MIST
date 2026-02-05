"use client";

import { useState, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { ModeSelector } from "./ModeSelector";
import type { ChatMode } from "@/types/api";
import { CHAT_MODES } from "@/types/api";

interface ChatInputProps {
  onSend: (content: string) => void;
  onHintRequest?: () => void;
  onModeChange?: (mode: ChatMode) => void;
  disabled?: boolean;
  hasTask?: boolean;
  hintsRemaining?: number;
  currentMode?: ChatMode;
}

export function ChatInput({
  onSend,
  onHintRequest,
  onModeChange,
  disabled = false,
  hasTask = false,
  hintsRemaining = 0,
  currentMode = "guided_learning",
}: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const placeholder =
    CHAT_MODES.find((m) => m.value === currentMode)?.placeholder ??
    "Напишите ваш ответ...";

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;

    onSend(trimmed);
    setInput("");

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [input, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleInput = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setInput(e.target.value);
      // Auto-resize
      const el = e.target;
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 200) + "px";
    },
    [],
  );

  return (
    <div className="border-t border-border bg-background p-4">
      <div className="max-w-3xl mx-auto">
        {/* Mode selector + hint button row */}
        <div className="flex items-center gap-2 mb-2">
          <ModeSelector
            value={currentMode}
            onChange={(mode) => onModeChange?.(mode)}
            disabled={disabled}
          />
          {hasTask && hintsRemaining > 0 && currentMode === "guided_learning" && (
            <Button
              variant="outline"
              size="sm"
              onClick={onHintRequest}
              disabled={disabled}
              className="text-xs"
            >
              Подсказка ({hintsRemaining} осталось)
            </Button>
          )}
        </div>

        {/* Input area */}
        <div className="flex items-end gap-2">
          <div className="relative flex-1">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={disabled}
              rows={1}
              className="w-full resize-none rounded-lg border border-input bg-muted/50 px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
              style={{ maxHeight: 200 }}
            />
          </div>
          <Button
            onClick={handleSend}
            disabled={disabled || !input.trim()}
            size="icon"
            className="h-[46px] w-[46px] shrink-0 rounded-lg bg-amber-600 hover:bg-amber-700"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="h-5 w-5"
            >
              <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
            </svg>
          </Button>
        </div>
        <p className="mt-1.5 text-xs text-muted-foreground text-center">
          Enter — отправить, Shift+Enter — новая строка
        </p>
      </div>
    </div>
  );
}
