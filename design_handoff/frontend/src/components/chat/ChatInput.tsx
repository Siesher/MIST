"use client";

import { useState, useRef, useCallback } from "react";
import { ModeSelector } from "./ModeSelector";
import { AttachmentButton } from "./AttachmentButton";
import { useI18n } from "@/lib/i18n";
import type { IngestResponse } from "@/lib/api";
import type { ChatMode } from "@/types/api";
import { CHAT_MODES } from "@/types/api";

interface ChatInputProps {
  onSend: (content: string) => void;
  onHintRequest?: () => void;
  onModeChange?: (mode: ChatMode) => void;
  onImageUpload?: (file: File) => void;
  disabled?: boolean;
  hasTask?: boolean;
  hintsRemaining?: number;
  currentMode?: ChatMode;
}

interface Attachment {
  id: string;
  kind: string;
  filename: string;
  text: string;
  preview: string;
  pages: number | null;
  truncated: boolean;
}

const ICONS: Record<string, string> = {
  pdf: "📄",
  docx: "📝",
  image: "🖼",
  text: "📃",
};

export function ChatInput({
  onSend,
  onHintRequest,
  onModeChange,
  disabled = false,
  hasTask = false,
  hintsRemaining = 0,
  currentMode = "guided_learning",
}: ChatInputProps) {
  const { t } = useI18n();
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const placeholder =
    CHAT_MODES.find((m) => m.value === currentMode)?.placeholder ?? t("input_placeholder");

  const handleAttach = useCallback((res: IngestResponse) => {
    setAttachments((prev) => [
      ...prev,
      {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        kind: res.kind,
        filename: res.filename,
        text: res.text,
        preview: res.preview,
        pages: res.pages,
        truncated: res.truncated,
      },
    ]);
  }, []);

  const removeAttachment = useCallback((id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if ((!trimmed && attachments.length === 0) || disabled) return;

    // Build payload: prepend attachment context blocks, then user question
    let payload = "";
    if (attachments.length > 0) {
      const blocks = attachments.map((a) => {
        const header = `[${ICONS[a.kind] || "📎"} Приложен файл "${a.filename}"`
          + (a.pages ? `, ${a.pages} стр.` : "")
          + (a.truncated ? ", обрезано" : "")
          + "]";
        return `${header}\n${a.text}`;
      });
      payload = blocks.join("\n\n---\n\n") + "\n\n";
    }
    payload += trimmed || "Проанализируй приложенные материалы.";

    onSend(payload);
    setInput("");
    setAttachments([]);
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }, [input, attachments, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleInput = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, []);

  return (
    <div
      style={{
        borderTop: "1px solid var(--line-hi)",
        background: "rgba(0,0,0,0.5)",
        padding: 14,
        position: "relative",
      }}
    >
      <div
        className="scan-bar"
        style={{
          top: 0,
          height: 2,
          background: "var(--violet)",
          animation: "none",
          opacity: 0.35,
        }}
      />

      {/* Mode selector + hint button row */}
      <div className="flex items-center gap-2 mb-2 max-w-3xl mx-auto">
        <ModeSelector
          value={currentMode}
          onChange={(mode) => onModeChange?.(mode)}
          disabled={disabled}
        />
        {hasTask && hintsRemaining > 0 && currentMode === "guided_learning" && (
          <button
            className="cbtn text-[10px]"
            onClick={onHintRequest}
            disabled={disabled}
          >
            ◆ подсказка ({hintsRemaining})
          </button>
        )}
      </div>

      {/* Attachment chips */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2 max-w-3xl mx-auto">
          {attachments.map((a) => (
            <div
              key={a.id}
              className="flex items-center gap-2 px-2 py-1"
              style={{
                background: "rgba(165,131,255,0.08)",
                border: "1px solid rgba(165,131,255,0.3)",
                borderRadius: 3,
                fontSize: 11,
                fontFamily: "var(--font-mono)",
                maxWidth: 340,
              }}
            >
              <span style={{ fontSize: 14 }}>{ICONS[a.kind] || "📎"}</span>
              <span
                style={{
                  color: "var(--text)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  flex: 1,
                }}
                title={`${a.filename}${a.pages ? ` · ${a.pages} стр.` : ""}\n\n${a.preview}`}
              >
                {a.filename}
              </span>
              <span className="ghost" style={{ fontSize: 9 }}>
                {(a.text.length / 1000).toFixed(1)}k
                {a.truncated ? "*" : ""}
              </span>
              <button
                onClick={() => removeAttachment(a.id)}
                className="cbtn cbtn-ghost !px-1 !py-0 text-[10px]"
                title="remove"
                style={{ border: "none" }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input area */}
      <div className="flex items-start gap-3 max-w-3xl mx-auto">
        <span
          style={{ color: "var(--yellow)", fontSize: 20, paddingTop: 6 }}
          aria-hidden
        >
          ❯
        </span>
        <AttachmentButton onIngested={handleAttach} disabled={disabled} />
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={2}
          style={{
            flex: 1,
            background: "transparent",
            border: "none",
            outline: "none",
            color: "var(--text)",
            fontFamily: "var(--font-mono)",
            fontSize: 14.5,
            resize: "none",
            maxHeight: 200,
            padding: "6px 0",
          }}
        />
        <button
          className="cbtn cbtn-primary"
          onClick={handleSend}
          disabled={disabled || (!input.trim() && attachments.length === 0)}
          style={{
            opacity:
              disabled || (!input.trim() && attachments.length === 0) ? 0.5 : 1,
            fontSize: 13,
            padding: "11px 18px",
            letterSpacing: "0.18em",
          }}
        >
          SEND ↵
        </button>
      </div>
      <div
        className="flex items-center gap-5 mt-3 max-w-3xl mx-auto"
        style={{ fontSize: 12, color: "var(--text-muted)" }}
      >
        <span>
          <kbd
            style={{
              fontSize: 11,
              padding: "2px 8px",
              color: "var(--text)",
            }}
          >
            ↵
          </kbd>{" "}
          {t("input_hint_enter")}
        </span>
        <span>
          <kbd
            style={{
              fontSize: 11,
              padding: "2px 8px",
              color: "var(--text)",
            }}
          >
            ⇧↵
          </kbd>{" "}
          {t("input_hint_shift")}
        </span>
        <span>
          <kbd
            style={{
              fontSize: 11,
              padding: "2px 8px",
              color: "var(--text)",
            }}
          >
            /
          </kbd>{" "}
          {t("input_hint_slash")}
        </span>
        <div className="flex-1" />
        <span
          className="ghost"
          style={{ fontSize: 12, color: "var(--text-dim)" }}
          title="Поддерживаемые форматы: PDF · Word · PNG/JPG/WEBP · TXT/MD"
        >
          📎 PDF · DOCX · IMG · MD
        </span>
        <span
          className="ghost"
          style={{
            fontSize: 12,
            color: "var(--success)",
            textShadow: "0 0 8px rgba(111, 224, 166, 0.4)",
          }}
          title="SymPy verifier активен (symbolic math checking)"
        >
          ● λ SymPy
        </span>
      </div>
    </div>
  );
}
