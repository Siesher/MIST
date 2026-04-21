"use client";

import { useState } from "react";
import { SmartContent } from "./SmartContent";
import { MitsMark } from "@/components/cyber/MitsMark";
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
  scaffolding: "scaffolding",
  problematize: "вопрос",
  rectify: "rectify",
  encourage: "encourage",
  hint: "подсказка",
  tell: "объяснение",
  clarify: "уточнение",
  system: "система",
};

export function Message({
  role,
  content,
  thinking,
  moveType,
  isCorrect,
  isStreaming,
}: MessageProps) {
  const isTutor = role === "tutor" || role === "system";
  const [expanded, setExpanded] = useState(false);
  const tokens = thinking ? thinking.split(/\s+/).length : 0;

  return (
    <div
      className="flex gap-3.5 items-start"
      style={{ padding: "12px 0" }}
    >
      <div
        style={{
          width: 28,
          height: 28,
          flex: "0 0 28px",
          border: "1px solid var(--line-hi)",
          background: isTutor ? "rgba(181, 138, 255, 0.06)" : "transparent",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--yellow)",
          fontSize: 12,
          borderRadius: 999,
        }}
      >
        {isTutor ? <MitsMark size={18} animated={false} /> : ">_"}
      </div>

      <div
        className={`flex-1 min-w-0 ${isTutor ? "msg-tutor" : "msg-user"}`}
      >
        <div className="flex items-center gap-2 mb-1.5">
          <span
            className="up"
            style={{
              fontSize: 9,
              letterSpacing: "0.22em",
              color: isTutor ? "var(--violet)" : "var(--text-ghost)",
              textShadow: isTutor
                ? "0 0 12px rgba(165, 131, 255, 0.5)"
                : "none",
            }}
          >
            {isTutor ? "MITS · tutor" : "USER · you"}
          </span>
          {moveType && isTutor && <span className="chip v">{moveTypeLabels[moveType] || moveType}</span>}
          {isStreaming && (
            <span className="chip v">
              <span className="dot v" /> поток
            </span>
          )}
          {isCorrect && <span className="chip on">✓ проверено</span>}
        </div>

        {thinking && isTutor && (
          <div className="mb-2">
            <button
              onClick={() => setExpanded((v) => !v)}
              className="flex items-center gap-1.5 font-mono up"
              style={{
                fontSize: 9,
                letterSpacing: "0.2em",
                color: "var(--text-muted)",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                padding: 0,
              }}
            >
              <span style={{ transform: expanded ? "rotate(90deg)" : "none", transition: "transform 120ms", color: "var(--violet)" }}>
                ›
              </span>
              <span>{expanded ? "скрыть размышления" : "показать размышления"}</span>
              <span style={{ color: "var(--text-ghost)" }}>({tokens} tok)</span>
            </button>
            {expanded && (
              <div
                style={{
                  marginTop: 6,
                  padding: "8px 12px",
                  background: "rgba(0,0,0,0.35)",
                  border: "1px dashed var(--line-hi)",
                  fontSize: 11,
                  color: "var(--text-dim)",
                  fontFamily: "var(--font-mono)",
                  whiteSpace: "pre-wrap",
                  maxHeight: 256,
                  overflowY: "auto",
                  borderRadius: 3,
                }}
              >
                {thinking}
              </div>
            )}
          </div>
        )}

        <div
          style={{
            color: "var(--text)",
            fontSize: 13.5,
            lineHeight: 1.7,
          }}
        >
          <SmartContent content={content} />
          {isStreaming && <span className="caret" />}
        </div>
      </div>
    </div>
  );
}

export function TypingIndicator() {
  return (
    <div className="flex gap-3.5 items-start" style={{ padding: "12px 0" }}>
      <div
        style={{
          width: 28,
          height: 28,
          flex: "0 0 28px",
          border: "1px solid var(--line-hi)",
          background: "rgba(181, 138, 255, 0.06)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 3,
        }}
      >
        <MitsMark size={18} animated={false} />
      </div>
      <div className="flex items-center gap-1 pt-2">
        <span className="dot v" style={{ animation: "pulseV 1.2s infinite" }} />
        <span className="dot v" style={{ animation: "pulseV 1.2s infinite 0.2s" }} />
        <span className="dot v" style={{ animation: "pulseV 1.2s infinite 0.4s" }} />
      </div>
    </div>
  );
}
