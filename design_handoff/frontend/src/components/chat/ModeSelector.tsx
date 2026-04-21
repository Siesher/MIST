"use client";

import type { ChatMode } from "@/types/api";
import { CHAT_MODES } from "@/types/api";

interface ModeSelectorProps {
  value: ChatMode;
  onChange: (mode: ChatMode) => void;
  disabled?: boolean;
}

const MODE_ICON: Record<ChatMode, string> = {
  chat: "◇",
  guided_learning: "◆",
  task_generator: "⬢",
};

const MODE_LABEL: Record<ChatMode, string> = {
  chat: "Свободный",
  guided_learning: "Сопровождение",
  task_generator: "Генератор",
};

export function ModeSelector({ value, onChange, disabled = false }: ModeSelectorProps) {
  return (
    <div className="flex items-center gap-2">
      {CHAT_MODES.map((mode) => {
        const on = value === mode.value;
        return (
          <button
            key={mode.value}
            type="button"
            onClick={() => !disabled && onChange(mode.value)}
            disabled={disabled}
            className="font-mono up cursor-pointer transition-all"
            style={{
              padding: "6px 12px",
              background: on ? "rgba(181,138,255,0.08)" : "transparent",
              border: "1px solid " + (on ? "var(--line-hi)" : "var(--line)"),
              color: on ? "var(--text)" : "var(--text-dim)",
              fontSize: 10,
              letterSpacing: "0.16em",
              opacity: disabled ? 0.5 : 1,
              borderRadius: 3,
            }}
          >
            <span style={{ color: on ? "var(--yellow)" : "var(--violet)", marginRight: 6 }}>
              {MODE_ICON[mode.value]}
            </span>
            {MODE_LABEL[mode.value]}
          </button>
        );
      })}
    </div>
  );
}
