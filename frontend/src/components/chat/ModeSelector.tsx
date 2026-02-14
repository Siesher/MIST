"use client";

import { useState, useRef, useEffect } from "react";
import type { ChatMode } from "@/types/api";
import { CHAT_MODES } from "@/types/api";

interface ModeSelectorProps {
  value: ChatMode;
  onChange: (mode: ChatMode) => void;
  disabled?: boolean;
}

const MODE_COLORS: Record<ChatMode, string> = {
  chat: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  guided_learning: "bg-green-500/15 text-green-400 border-green-500/30",
  task_generator: "bg-purple-500/15 text-purple-400 border-purple-500/30",
};

const MODE_DOT_COLORS: Record<ChatMode, string> = {
  chat: "bg-blue-400",
  guided_learning: "bg-green-400",
  task_generator: "bg-purple-400",
};

function ModeIcon({ mode, className = "w-4 h-4" }: { mode: ChatMode; className?: string }) {
  switch (mode) {
    case "chat":
      return (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={className}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
        </svg>
      );
    case "guided_learning":
      return (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={className}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a23.838 23.838 0 0 0-1.012 5.434c3.586-1.022 7.26-1.584 11.009-1.584 3.749 0 7.423.562 11.009 1.584a23.838 23.838 0 0 0-1.012-5.434m-15.482 0A23.82 23.82 0 0 1 12 3.75a23.82 23.82 0 0 1 7.741 1.285m-15.482 5.112a76.739 76.739 0 0 1 15.482 0" />
        </svg>
      );
    case "task_generator":
      return (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={className}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
        </svg>
      );
  }
}

export function ModeSelector({ value, onChange, disabled = false }: ModeSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const currentMode = CHAT_MODES.find((m) => m.value === value) ?? CHAT_MODES[1];

  return (
    <div ref={ref} className="relative">
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => !disabled && setOpen(!open)}
        disabled={disabled}
        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors whitespace-nowrap ${MODE_COLORS[value]} ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer hover:brightness-110"}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${MODE_DOT_COLORS[value]}`} />
        <ModeIcon mode={value} className="w-3.5 h-3.5" />
        <span>{currentMode.label}</span>
        <svg className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute bottom-full left-0 mb-1 w-56 rounded-lg border border-border bg-popover shadow-lg z-50">
          {CHAT_MODES.map((mode) => (
            <button
              key={mode.value}
              type="button"
              onClick={() => {
                onChange(mode.value);
                setOpen(false);
              }}
              className={`flex items-center gap-2.5 w-full px-3 py-2.5 text-sm text-left transition-colors hover:bg-muted/50 first:rounded-t-lg last:rounded-b-lg ${value === mode.value ? "bg-muted/30" : ""}`}
            >
              <span className={`w-2 h-2 rounded-full ${MODE_DOT_COLORS[mode.value]}`} />
              <ModeIcon mode={mode.value} className="w-4 h-4 text-muted-foreground" />
              <div className="flex-1">
                <div className="font-medium">{mode.label}</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {mode.value === "chat" && "Свободное общение на любые темы"}
                  {mode.value === "guided_learning" && "Сократический метод обучения"}
                  {mode.value === "task_generator" && "Генерация задач с решениями"}
                </div>
              </div>
              {value === mode.value && (
                <svg className="w-4 h-4 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
