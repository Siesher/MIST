"use client";

// MITS new_design — CHAT screen (theme "midnight").
// Ports TopBar / AgentFlow / TaskCard / MessageList / Message / Composer from
// new_design and WIRES them to the real data layer (useChat + useChatStore).
// LaTeX is rendered via the existing SmartContent/MathRenderer (KaTeX).

import { Fragment, useEffect, useRef, useState } from "react";
import { Icon } from "./icons";
import { useTheme, THEMES, THEME_LABELS } from "./useTheme";
import { useI18n, type StringKey } from "@/lib/i18n";
import { SmartContent } from "@/components/chat/SmartContent";
import { useChatStore } from "@/store/chatStore";
import { ingestFile, runDream, type DreamReport } from "@/lib/api";
import { useIdleTimer } from "@/hooks/useIdleTimer";
import type { ChatMode, Message as MessageType, TutorMoveType } from "@/types/api";

const EMPTY_MESSAGES: MessageType[] = [];

// new_design move → CSS badge class + RU label
const MOVE_META: Record<string, { cls: string; labelKey: StringKey }> = {
  scaffolding: { cls: "scaffolding", labelKey: "move_scaffolding" },
  hint: { cls: "hint", labelKey: "move_hint" },
  encourage: { cls: "encourage", labelKey: "move_encourage" },
  problematize: { cls: "problematize", labelKey: "move_problematize" },
  rectify: { cls: "rectify", labelKey: "move_rectify" },
  clarify: { cls: "scaffolding", labelKey: "move_clarify" },
  tell: { cls: "scaffolding", labelKey: "move_tell" },
};

// UI mode (new_design) <-> backend ChatMode
const MODES: { id: ChatMode; labelKey: StringKey; descKey: StringKey; dot: string }[] = [
  { id: "chat", labelKey: "mode_chat", descKey: "mode_chat_desc", dot: "#3B7DFF" },
  { id: "guided_learning", labelKey: "mode_guided", descKey: "mode_guided_desc", dot: "#22A05A" },
  { id: "task_generator", labelKey: "mode_task", descKey: "mode_task_desc", dot: "#6800FF" },
];

function fmtTime(iso?: string): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

// ---------- Top bar ----------
function TopBar({ title, subtitle }: { title: string; subtitle?: string }) {
  const [theme, setTheme] = useTheme();
  const { lang, setLang, t } = useI18n();
  const cycleTheme = () => setTheme(THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length]);
  return (
    <div className="top-bar">
      <div className="top-title">
        <h1>{title}</h1>
        {subtitle && <span className="top-sub">{subtitle}</span>}
      </div>
      <div className="lang-toggle">
        <button className={lang === "ru" ? "active" : ""} onClick={() => setLang("ru")}>RU</button>
        <button className={lang === "en" ? "active" : ""} onClick={() => setLang("en")}>EN</button>
      </div>
      <button
        className="theme-toggle"
        title={`${t("theme_label")}: ${THEME_LABELS[theme]}`}
        onClick={cycleTheme}
      >
        {theme === "daylight" ? Icon.moon : Icon.sun}
      </button>
    </div>
  );
}

// ---------- Agent flow strip ----------
function AgentFlow({ active }: { active: boolean }) {
  const { t } = useI18n();
  const agents = [
    { key: "Profiler", state: "done" },
    { key: "Planner", state: "done" },
    { key: "Tutor", state: active ? "active" : "" },
    { key: "Verifier", state: "" },
  ];
  const modelName = useChatStore((s) => s.modelName) || "Qwen3.5-9B · final";
  return (
    <div className="agent-flow">
      <span className="agent-flow-label">{t("agents")}</span>
      {agents.map((a, i) => (
        <Fragment key={a.key}>
          <div className={"agent-pill " + a.state}>
            <span className="agent-dot" />
            <span>{a.key}</span>
          </div>
          {i < agents.length - 1 && (
            <div className="agent-arrow">
              {(agents[i].state === "done" || agents[i].state === "active") && (
                <span className="flow-dot" style={{ animationDelay: i * 0.4 + "s" }} />
              )}
            </div>
          )}
        </Fragment>
      ))}
      <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ fontSize: 11, color: "var(--ink-mute)" }}>{modelName}</span>
        <span className="agent-dot" style={{ background: "#22A05A" }} />
      </div>
    </div>
  );
}

// ---------- Task card (shown when the session has a task) ----------
function TaskCard({ topic, difficulty, problem }: { topic?: string; difficulty?: string | null; problem?: string }) {
  const { t } = useI18n();
  return (
    <div className="task-card">
      <div className="task-icon">{Icon.sparkle}</div>
      <div className="task-body">
        <div className="task-label">
          {topic || t("task_default")}
          {difficulty ? ` · ${difficulty}` : ""}
        </div>
        <h3 className="task-title">{topic || t("task_current")}</h3>
        {problem && (
          <div className="task-formula">
            <SmartContent content={problem} />
          </div>
        )}
        <div className="task-meta">
          <span>
            {t("difficulty")}: <b>{difficulty || "—"}</b>
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------- Single message ----------
function Message({ m }: { m: MessageType }) {
  const isUser = m.role === "user";
  const move = m.move_type ? MOVE_META[m.move_type as TutorMoveType] : undefined;
  const [thinkOpen, setThinkOpen] = useState(false);
  const { t } = useI18n();
  return (
    <div className={"msg " + (isUser ? "user" : "tutor")}>
      <div className="msg-avatar">{isUser ? "S" : "T"}</div>
      <div className="msg-content">
        <div className="msg-header">
          <span className="msg-name">{isUser ? t("msg_student") : t("msg_tutor")}</span>
          {move && <span className={"move-badge " + move.cls}>{t(move.labelKey)}</span>}
          <span className="msg-time">{fmtTime(m.timestamp)}</span>
        </div>
        {m.thinking && (
          <div className="thinking">
            <button className="thinking-toggle" onClick={() => setThinkOpen((o) => !o)}>
              <span className="dot" />
              <span>{thinkOpen ? t("think_hide") : t("think_show")}</span>
            </button>
            {thinkOpen && (
              <div className="thinking-body" style={{ whiteSpace: "pre-wrap" }}>{m.thinking}</div>
            )}
          </div>
        )}
        <div className="msg-body">
          <SmartContent content={m.content} />
        </div>
        {m.citations && m.citations.length > 0 && (
          <div
            className="msg-citations"
            style={{
              marginTop: 8,
              paddingTop: 6,
              borderTop: "1px solid var(--line, rgba(255,255,255,0.08))",
            }}
          >
            <div style={{ fontSize: 10, letterSpacing: "0.15em", opacity: 0.6, marginBottom: 4 }}>
              {t("citations_label")}
            </div>
            {m.citations.map((c, i) => (
              <a
                key={c.source_id + i}
                href="/sources"
                title={t("citations_open")}
                style={{ display: "block", fontSize: 11.5, textDecoration: "none", marginBottom: 3 }}
              >
                <span style={{ color: "var(--violet, #b58aff)" }}>📄 {c.title}</span>
                {c.excerpt && (
                  <span style={{ color: "var(--text-dim, #9aa)", opacity: 0.8 }}>
                    {" — «"}
                    {c.excerpt.slice(0, 140)}
                    {c.excerpt.length > 140 ? "…" : ""}
                    {"»"}
                  </span>
                )}
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Live streaming message (thinking + answer + cursor) ----------
function StreamingMessage() {
  const sm = useChatStore((s) => s.streamingMessage);
  // Collapsed by default: a long reasoning trace must not push the actual
  // answer off-screen while tokens stream (matches the persisted-message variant).
  const [thinkOpen, setThinkOpen] = useState(false);
  const { t } = useI18n();
  if (!sm) return null;
  const hasThinking = !!sm.thinkingContent;
  const hasBody = !!sm.content;
  if (!hasThinking && !hasBody) return null;

  return (
    <div className="msg tutor">
      <div className="msg-avatar">T</div>
      <div className="msg-content">
        <div className="msg-header">
          <span className="msg-name">Тьютор</span>
          <span className="msg-time">сейчас</span>
        </div>

        {hasThinking && (
          <div className="thinking">
            <button className="thinking-toggle" onClick={() => setThinkOpen((o) => !o)}>
              <span className="dot" />
              <span>{thinkOpen ? t("think_hide") : t("think_show")}</span>
            </button>
            {thinkOpen && <div className="thinking-body" style={{ whiteSpace: "pre-wrap" }}>{sm.thinkingContent}</div>}
          </div>
        )}

        <div className="msg-body">
          <SmartContent content={sm.content} />
          {(sm.isThinking || hasBody) && <span className="cursor" />}
        </div>
      </div>
    </div>
  );
}

// ---------- Messages list ----------
function MessageList({
  sessionId,
  task,
}: {
  sessionId: string;
  task?: { topic?: string; difficulty?: string | null; problem?: string };
}) {
  const { t } = useI18n();
  const messages = useChatStore((s) => s.messages[sessionId] ?? EMPTY_MESSAGES);
  const streamingMessage = useChatStore((s) => s.streamingMessage);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const isLoading = useChatStore((s) => s.isLoading);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, streamingMessage, isLoading]);

  const showTask = !!task && (task.problem || task.topic);

  return (
    <div className="messages" ref={scrollRef}>
      <div className="msg-wrap">
        {showTask && <TaskCard topic={task!.topic} difficulty={task!.difficulty} problem={task!.problem} />}

        {messages.length === 0 && !isLoading && !showTask && (
          <div style={{ textAlign: "center", padding: "48px 0", color: "var(--ink-mute)" }}>
            <div style={{ fontSize: 15, color: "var(--ink-soft)", marginBottom: 6 }}>{t("empty_title")}</div>
            <div style={{ fontSize: 13 }}>{t("empty_hint")}</div>
          </div>
        )}

        {messages.map((m) => (
          <Message key={m.id} m={m} />
        ))}

        {isStreaming && <StreamingMessage />}

        {isLoading && !isStreaming && (
          <div className="msg tutor">
            <div className="msg-avatar">T</div>
            <div className="msg-content">
              <div className="msg-header">
                <span className="msg-name">{t("msg_tutor")}</span>
              </div>
              <div className="msg-body" style={{ color: "var(--ink-mute)" }}>
                {t("thinking_dots")}<span className="cursor" />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Composer (mode selector + textarea + send) ----------
function Composer({
  mode,
  onSend,
  onHint,
  onModeChange,
  disabled,
  hintsRemaining,
}: {
  mode: ChatMode;
  onSend: (text: string) => void;
  onHint: () => void;
  onModeChange: (m: ChatMode) => void;
  disabled: boolean;
  hintsRemaining: number;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [val, setVal] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [attached, setAttached] = useState<{ name: string; text: string } | null>(null);
  const [ingesting, setIngesting] = useState(false);
  const [attachError, setAttachError] = useState(false);

  const current = MODES.find((m) => m.id === mode) ?? MODES[1];

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (e.target) e.target.value = ""; // позволяем повторно выбрать тот же файл
    if (!file) return;
    setAttachError(false);
    setIngesting(true);
    try {
      const resp = await ingestFile(file);
      setAttached({ name: resp.filename || file.name, text: resp.text || "" });
    } catch {
      setAttachError(true);
      setAttached(null);
    } finally {
      setIngesting(false);
    }
  };

  const autoSize = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  };

  const submit = () => {
    const text = val.trim();
    if ((!text && !attached) || disabled) return;
    let payload = text;
    if (attached && attached.text) {
      // Подмешиваем извлечённый источник перед вопросом — тьютор его анализирует.
      payload =
        `Материал из источника «${attached.name}»:\n"""\n${attached.text}\n"""\n\n` +
        (text || "Проанализируй этот источник и помоги мне разобраться.");
    }
    onSend(payload);
    setVal("");
    setAttached(null);
    requestAnimationFrame(autoSize);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="composer">
      <div className="composer-wrap">
        <div className="composer-row1">
          <div style={{ position: "relative" }}>
            <button className="mode-chip active" onClick={() => setOpen((o) => !o)}>
              <span className="mode-dot" style={{ background: current.dot }} />
              <span>{t(current.labelKey)}</span>
              <svg viewBox="0 0 12 12" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ transform: open ? "rotate(180deg)" : "", transition: "transform .15s" }}>
                <path d="m3 4.5 3 3 3-3" strokeLinecap="round" />
              </svg>
            </button>
            {open && (
              <div className="mode-pop">
                {MODES.map((m) => (
                  <div
                    key={m.id}
                    className="mode-pop-item"
                    onClick={() => {
                      onModeChange(m.id);
                      setOpen(false);
                    }}
                  >
                    <span className="mode-dot" style={{ background: m.dot, marginTop: 4, width: 8, height: 8, borderRadius: "50%" }} />
                    <div>
                      <div className="mode-pop-title">{t(m.labelKey)}</div>
                      <div className="mode-pop-desc">{t(m.descKey)}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          {current.id === "guided_learning" && (
            <button className="hint-btn" onClick={onHint} disabled={hintsRemaining <= 0}>
              <svg viewBox="0 0 12 12" width="11" height="11" fill="currentColor">
                <circle cx="6" cy="6" r="5" opacity="0.2" />
                <circle cx="6" cy="6" r="2" />
              </svg>
              <span>{t("hint_btn")}</span>
              <span style={{ opacity: 0.7 }}>· {hintsRemaining} {t("hints_left")}</span>
            </button>
          )}
        </div>
        {(ingesting || attached || attachError) && (
          <div
            className="attach-chip"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 12,
              padding: "4px 2px 6px",
              color: "var(--ink-soft)",
            }}
          >
            {ingesting && (
              <>
                <span className="dot" style={{ animation: "pulse 1s infinite" }} />
                {t("attach_analyzing")}
              </>
            )}
            {!ingesting && attached && (
              <>
                <span style={{ color: "var(--accent)" }}>
                  📎 {t("attach_attached")}: {attached.name}
                </span>
                <button
                  type="button"
                  onClick={() => setAttached(null)}
                  style={{
                    marginLeft: "auto",
                    background: "none",
                    border: "none",
                    color: "var(--ink-mute)",
                    cursor: "pointer",
                  }}
                >
                  {t("attach_remove")}
                </button>
              </>
            )}
            {!ingesting && attachError && (
              <span style={{ color: "var(--error, #e87093)" }}>{t("attach_error")}</span>
            )}
          </div>
        )}
        <div className="composer-input">
          <textarea
            ref={textareaRef}
            value={val}
            onChange={(e) => {
              setVal(e.target.value);
              autoSize();
            }}
            onKeyDown={onKeyDown}
            placeholder={t(
              current.id === "task_generator"
                ? "input_placeholder_task"
                : current.id === "guided_learning"
                  ? "input_placeholder_guided"
                  : "input_placeholder",
            )}
            rows={1}
          />
          <div className="composer-tools">
            <button
              className="tool-btn"
              title={t("attach")}
              type="button"
              onClick={() => fileInputRef.current?.click()}
            >
              {Icon.image}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt,.md,.markdown,.py,.ts,.tsx,.js,.json,image/*"
              style={{ display: "none" }}
              onChange={handleFile}
            />
            <button
              className="send-btn magnetic"
              onClick={submit}
              disabled={disabled || (!val.trim() && !attached)}
              type="button"
              aria-label={t("send")}
            >
              {Icon.send}
            </button>
          </div>
        </div>
        <div className="composer-hint">
          <kbd>Enter</kbd> {t("input_hint_enter")}
          <span style={{ opacity: 0.4 }}>•</span>
          <kbd>Shift</kbd>
          <kbd>Enter</kbd> {t("input_hint_shift")}
        </div>
      </div>
    </div>
  );
}

// ---------- Chat-specific right rail (session stats) ----------
function ChatRail({ sessionId }: { sessionId: string }) {
  const { t } = useI18n();
  const messages = useChatStore((s) => s.messages[sessionId] ?? EMPTY_MESSAGES);
  const state = useChatStore((s) => s.sessionStates[sessionId]);
  const metrics = useChatStore((s) => s.sessionMetrics[sessionId]);

  const hintsUsed = state?.hints_used ?? 0;
  const solved = state?.is_solved ? "1/1" : "0/1";
  const latencyS = metrics?.lastLatency ? (metrics.lastLatency / 1000).toFixed(1) + "с" : "—";

  return (
    <aside className="rail">
      <div className="rail-card">
        <div className="rail-card-title">
          <span>{t("rail_session")}</span>
        </div>
        <div className="stat-grid">
          <div className="stat">
            <div className="stat-val">{messages.length}</div>
            <div className="stat-lbl">{t("stat_messages")}</div>
          </div>
          <div className="stat">
            <div className="stat-val">{hintsUsed}/3</div>
            <div className="stat-lbl">{t("stat_hints")}</div>
          </div>
          <div className="stat">
            <div className="stat-val">{solved}</div>
            <div className="stat-lbl">{t("stat_solved")}</div>
          </div>
          <div className="stat">
            <div className="stat-val">{latencyS}</div>
            <div className="stat-lbl">{t("stat_latency")}</div>
          </div>
        </div>
      </div>

      <div className="rail-card">
        <div className="rail-card-title">
          <span>{t("active_agents")}</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {["Profiler", "Planner", "Tutor", "Verifier"].map((a) => (
            <div key={a} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12.5, color: "var(--ink-soft)" }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent)" }} />
              {a}
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}

// ---------- Rest / "dreaming" prompt (cognitive break + reflection) ----------
function RestCard({ onClose }: { onClose: () => void }) {
  const [dreaming, setDreaming] = useState(false);
  const [dreamReport, setDreamReport] = useState<DreamReport | null>(null);
  const [dreamErr, setDreamErr] = useState(false);

  const sleep = async () => {
    setDreaming(true);
    setDreamErr(false);
    try {
      const r = await runDream();
      setDreamReport(r);
    } catch {
      setDreamErr(true);
    } finally {
      setDreaming(false);
    }
  };

  if (dreamReport) {
    return (
      <div className="rest-card">
        <span>Я осмыслил {dreamReport.sessions_count} сессий 💤 — заметки в разделе «Сны».</span>
        <button className="btn-secondary" onClick={onClose}>Закрыть</button>
      </div>
    );
  }

  return (
    <div className="rest-card">
      <span>
        {dreamErr
          ? "Не удалось осмыслить сейчас — проверьте сервер и попробуйте ещё раз."
          : "Хочешь передохнуть? Я пока обдумаю твои сессии 💤"}
      </span>
      <button className="btn-primary" disabled={dreaming} onClick={sleep}>
        {dreaming ? "Сплю…" : "Отдохнуть и осмыслить"}
      </button>
      <button className="btn-secondary" onClick={onClose}>Позже</button>
    </div>
  );
}

// ---------- Public: chat main column + rail ----------
interface ChatScreenProps {
  sessionId: string;
  onSendMessage: (text: string) => void;
  onHintRequest: () => void;
  onModeChange: (m: ChatMode) => void;
  task?: { topic?: string; difficulty?: string | null; problem?: string };
  connectionLost?: boolean;
}

export function ChatMain({ sessionId, onSendMessage, onHintRequest, onModeChange, task, connectionLost }: ChatScreenProps) {
  const { t } = useI18n();
  const mode = useChatStore((s) => s.sessionModes[sessionId] ?? "guided_learning");
  const isStreaming = useChatStore((s) => s.isStreaming);
  const isLoading = useChatStore((s) => s.isLoading);
  const state = useChatStore((s) => s.sessionStates[sessionId]);
  const hintsRemaining = state ? Math.max(0, 3 - state.hints_used) : 3;

  // One reconciled rest-card state: opens on a backend `suggest_rest` (cognitive
  // overload) OR on prolonged idle. Local `restOpen` drives the card; the store
  // flag is the cross-component bridge from the WS handler.
  const restSuggested = useChatStore((s) => s.restSuggested);
  const setRestSuggested = useChatStore((s) => s.setRestSuggested);
  const [restOpen, setRestOpen] = useState(false);
  useEffect(() => {
    if (restSuggested) setRestOpen(true);
  }, [restSuggested]);
  useIdleTimer(() => setRestOpen(true));
  const closeRest = () => {
    setRestOpen(false);
    setRestSuggested(false);
  };

  const title = task?.topic || "Сократическая сессия";
  const subtitle = task?.difficulty ? `${task.topic ? "Задача" : ""} · ${task.difficulty}` : undefined;

  return (
    <main className="main">
      <TopBar title={title} subtitle={subtitle} />
      {connectionLost && (
        <div
          role="status"
          style={{
            margin: "0 24px 6px",
            padding: "8px 14px",
            borderRadius: 8,
            fontSize: 13,
            display: "flex",
            alignItems: "center",
            gap: 9,
            color: "var(--ink)",
            background: "color-mix(in oklab, var(--warning, #f5a623) 13%, var(--bg))",
            border: "1px solid color-mix(in oklab, var(--warning, #f5a623) 38%, var(--line))",
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--warning, #f5a623)",
              animation: "pulse 1.2s infinite",
              flex: "0 0 auto",
            }}
          />
          {t("ws_reconnecting")}
        </div>
      )}
      <AgentFlow active={isStreaming || isLoading} />
      <MessageList sessionId={sessionId} task={task} />
      {restOpen && <RestCard onClose={closeRest} />}
      <Composer
        mode={mode}
        onSend={onSendMessage}
        onHint={onHintRequest}
        onModeChange={onModeChange}
        disabled={isStreaming || isLoading}
        hintsRemaining={hintsRemaining}
      />
    </main>
  );
}

export { ChatRail };
