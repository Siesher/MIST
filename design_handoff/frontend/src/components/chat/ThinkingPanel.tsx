"use client";

import { useEffect, useState } from "react";
import { useChatStore } from "@/store/chatStore";

interface Props {
  content: string;
  isActive: boolean;  // true while tokens arrive for thinking phase
  isLive: boolean;    // true during entire streaming (live timer enabled)
}

function useTick(intervalMs: number, enabled: boolean) {
  const [, setN] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => setN((n) => n + 1), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs, enabled]);
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${Math.round(s - m * 60)}s`;
}

export function ThinkingPanel({ content, isActive, isLive }: Props) {
  const metrics = useChatStore((s) => s.streamMetrics);
  const [expanded, setExpanded] = useState(true);

  // Tick every 100ms during live thinking to refresh timer display
  useTick(100, isLive && isActive);

  // Collapse automatically once thinking finishes
  useEffect(() => {
    if (!isActive && isLive) {
      // Keep expanded briefly after finish, then collapse
      const id = setTimeout(() => setExpanded(false), 1500);
      return () => clearTimeout(id);
    }
  }, [isActive, isLive]);

  const duration =
    metrics.thinkingStartedAt !== null
      ? (metrics.thinkingEndedAt ?? performance.now()) - metrics.thinkingStartedAt
      : 0;
  const tokens = metrics.thinkingTokens;
  const tps = duration > 100 ? (tokens / (duration / 1000)).toFixed(1) : "—";

  return (
    <div
      className="mb-2"
      style={{
        background: "rgba(0,0,0,0.35)",
        border: "1px solid var(--line-hi)",
        borderRadius: 4,
        overflow: "hidden",
      }}
    >
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-2.5 cursor-pointer font-mono text-left"
        style={{
          padding: "8px 12px",
          background: "transparent",
          border: "none",
          color: "var(--text-dim)",
          fontSize: 11,
        }}
      >
        <span
          style={{
            transform: expanded ? "rotate(90deg)" : "none",
            transition: "transform 120ms",
            color: "var(--violet)",
          }}
        >
          ›
        </span>

        {isActive ? (
          <span className="dot v" style={{ animation: "pulseV 1.2s infinite" }} />
        ) : (
          <span style={{ color: "var(--success)", fontSize: 11 }}>✓</span>
        )}

        <span className="up" style={{ letterSpacing: "0.2em", color: "var(--violet)" }}>
          {isActive ? "размышляю" : "рассуждение"}
        </span>

        <span className="ghost">·</span>
        <span className="y" style={{ fontVariantNumeric: "tabular-nums" }}>
          {formatMs(duration)}
        </span>
        <span className="ghost">·</span>
        <span style={{ color: "var(--text)", fontVariantNumeric: "tabular-nums" }}>
          {tokens} tok
        </span>
        {tps !== "—" && (
          <>
            <span className="ghost">·</span>
            <span className="ghost" style={{ fontVariantNumeric: "tabular-nums" }}>
              {tps} tok/s
            </span>
          </>
        )}
        <div className="flex-1" />
        {!expanded && content && (
          <span className="ghost" style={{ fontSize: 10 }}>
            {expanded ? "свернуть" : "раскрыть"}
          </span>
        )}
      </button>

      {expanded && (
        <div
          style={{
            padding: "10px 14px",
            borderTop: "1px dashed var(--line)",
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--text-dim)",
            whiteSpace: "pre-wrap",
            maxHeight: 320,
            overflowY: "auto",
            lineHeight: 1.55,
          }}
        >
          {content || <span className="ghost">{"// ожидание токенов…"}</span>}
          {isActive && <span className="caret" />}
        </div>
      )}
    </div>
  );
}
