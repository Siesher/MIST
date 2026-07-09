"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { useChatStore } from "@/store/chatStore";

interface Props {
  view?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function formatLatency(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function formatTokens(n: number): string {
  if (n < 1000) return String(n);
  if (n < 10000) return `${(n / 1000).toFixed(1)}k`;
  return `${Math.round(n / 1000)}k`;
}

export function StatusBar({ view = "home" }: Props) {
  const { t, lang, setLang } = useI18n();
  const [time, setTime] = useState<string>("");
  const [backendUp, setBackendUp] = useState<boolean | null>(null);

  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const modelName = useChatStore((s) => s.modelName);
  const setModelName = useChatStore((s) => s.setModelName);
  const backendKind = useChatStore((s) => s.backendKind);
  const turboQuant = useChatStore((s) => s.turboQuant);
  const contextLength = useChatStore((s) => s.contextLength);
  const setBackendInfo = useChatStore((s) => s.setBackendInfo);

  const [cacheHitRate, setCacheHitRate] = useState<number | null>(null);
  const [cacheTotal, setCacheTotal] = useState<number>(0);
  const sessionMetrics = useChatStore((s) =>
    activeSessionId ? s.sessionMetrics[activeSessionId] : undefined,
  );
  const streamMetrics = useChatStore((s) => s.streamMetrics);
  const isStreaming = useChatStore((s) => s.isStreaming);

  // Live ticker while streaming — updates session totals in real time
  const [, forceTick] = useState(0);
  useEffect(() => {
    if (!isStreaming) return;
    const id = setInterval(() => forceTick((n) => n + 1), 250);
    return () => clearInterval(id);
  }, [isStreaming]);

  useEffect(() => {
    const update = () => setTime(new Date().toTimeString().slice(0, 8));
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, []);

  // Probe /health once + every 20s for model name & status
  useEffect(() => {
    let cancelled = false;
    async function probe() {
      try {
        const res = await fetch(`${API_BASE}/api/v1/health`);
        if (!res.ok) throw new Error(String(res.status));
        const data = await res.json();
        if (cancelled) return;
        setBackendUp(true);
        const llm = data?.components?.llm;
        if (typeof llm?.model === "string") setModelName(llm.model);
        setBackendInfo({
          kind: llm?.backend,
          turbo_quant: !!llm?.turbo_quant,
          context_length: llm?.context_length,
        });
      } catch {
        if (!cancelled) setBackendUp(false);
      }
    }
    probe();
    const id = setInterval(probe, 20000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [setModelName, setBackendInfo]);

  // Poll cache stats every 10s
  useEffect(() => {
    let cancelled = false;
    async function probeCache() {
      try {
        const res = await fetch(`${API_BASE}/api/v1/metrics/cache`);
        if (!res.ok) return;
        const s = await res.json();
        if (cancelled) return;
        setCacheHitRate(s.hit_rate);
        setCacheTotal(s.total_requests);
      } catch {
        /* ignore */
      }
    }
    probeCache();
    const id = setInterval(probeCache, 10000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  // Live totals during streaming: base + current stream
  const liveTokens = isStreaming
    ? streamMetrics.thinkingTokens + streamMetrics.responseTokens
    : 0;
  const totalTokens = (sessionMetrics?.totalTokens ?? 0) + liveTokens;

  // Average latency — over last 10
  const avgLatency = (() => {
    const lats = sessionMetrics?.latencies ?? [];
    if (lats.length === 0) return null;
    return lats.reduce((a, b) => a + b, 0) / lats.length;
  })();

  const latencyDisplay = isStreaming
    ? formatLatency(
        streamMetrics.requestSentAt !== null
          ? performance.now() - streamMetrics.requestSentAt
          : null,
      )
    : formatLatency(avgLatency);

  return (
    <div
      data-status-bar
      className="flex items-center gap-7 px-5 text-[10px] uppercase tracking-[0.18em] text-cyber-text-dim border-b whitespace-nowrap overflow-hidden relative z-10"
      style={{
        height: 32,
        borderColor: "var(--line)",
        background: "var(--bg-0)",
      }}
    >
      <div className="flex items-center gap-2">
        <span className={`dot ${backendUp === true ? "g" : backendUp === false ? "" : "v"}`}
          style={backendUp === false ? { background: "var(--error)", boxShadow: "0 0 8px var(--error)" } : undefined} />
        <span className={backendUp === true ? "y" : "ghost"}>
          {backendUp === null ? "…" : backendUp ? t("online") : lang === "ru" ? "ОФЛАЙН" : "OFFLINE"}
        </span>
      </div>

      <span title="текущая модель и backend">
        <span className="ghost">model</span>{" "}
        <span style={{ color: "var(--text)" }}>{modelName ?? "—"}</span>
        {backendKind === "huggingface" && (
          <>
            <span className="ghost mx-1">·</span>
            <span className="y" title="HuggingFace backend with TurboQuant KV compression">
              HF
            </span>
          </>
        )}
        {turboQuant && (
          <>
            <span className="ghost mx-1">·</span>
            <span className="neon-y" title="TurboQuant KV cache compression active">
              TQ
            </span>
          </>
        )}
        {contextLength && contextLength > 4096 && (
          <>
            <span className="ghost mx-1">·</span>
            <span className="v" title="context window">
              {Math.round(contextLength / 1024)}K ctx
            </span>
          </>
        )}
      </span>

      <span title={isStreaming ? "секунд с момента запроса" : "средняя задержка ответа (последние 10)"}>
        <span className="ghost">{isStreaming ? "elapsed" : "avg lat"}</span>{" "}
        <span className="y" style={{ fontVariantNumeric: "tabular-nums" }}>
          {latencyDisplay}
        </span>
      </span>

      <span title="оценка токенов в сессии (≈4 символа/токен)">
        <span className="ghost">tok</span>{" "}
        <span style={{ color: "var(--text)", fontVariantNumeric: "tabular-nums" }}>
          {formatTokens(totalTokens)}
        </span>
        {isStreaming && liveTokens > 0 && (
          <>
            <span className="ghost mx-1">+</span>
            <span className="v" style={{ fontVariantNumeric: "tabular-nums" }}>
              {liveTokens}
            </span>
          </>
        )}
      </span>

      {cacheHitRate !== null && cacheTotal > 0 && (
        <span title={`LLM response cache · ${cacheTotal} запросов`}>
          <span className="ghost">cache</span>{" "}
          <span
            className={cacheHitRate > 0.2 ? "y" : "ghost"}
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {(cacheHitRate * 100).toFixed(0)}%
          </span>
        </span>
      )}

      <div className="flex-1" />
      <span>
        <span className="ghost">view ›</span> <span className="v">{view}</span>
      </span>
      <button
        className="cbtn cbtn-ghost !py-0.5 !px-1.5 text-[10px]"
        onClick={() => setLang(lang === "ru" ? "en" : "ru")}
      >
        {lang === "ru" ? "RU" : "EN"} ⇄
      </button>
      <span style={{ fontVariantNumeric: "tabular-nums" }}>{time}</span>
    </div>
  );
}
