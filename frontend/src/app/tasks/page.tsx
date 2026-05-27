"use client";

// MITS new_design (midnight) — Tasks screen.
// Faithful port of new_design `pages (1).jsx` → TasksPage:
//   .page > .page-head (title + controls + filter + generate)
//         > .page-body (.insight-banner + .tasks-list of .task-row + skeletons)
// Mock data (TASKS_DATA) is REPLACED with live backend data, falling back to the
// ported static rows so the screen always renders complete for a demo.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { NewAppShell } from "@/components/newdesign/AppShell";
import { Icon } from "@/components/newdesign/icons";
import {
  createSession,
  generateTask,
  getRecommendedTasks,
  listTopics,
} from "@/lib/api";
import { useChatStore } from "@/store/chatStore";
import type { Difficulty, Session, TopicInfo } from "@/types/api";
import {
  DIFFICULTIES,
  FALLBACK_TASKS,
  T,
  domColor,
  humanizeTopic,
  pseudoRate,
  topicToDomain,
  type Lang,
  type StringKey,
  type TaskRow,
} from "./_data";

export default function TasksPage() {
  const router = useRouter();
  const addSession = useChatStore((s) => s.addSession);
  const setActiveSession = useChatStore((s) => s.setActiveSession);

  // --- language (synced with the rest of the app via localStorage) ---
  const [lang, setLangState] = useState<Lang>("ru");
  // theme toggle is cosmetic only — the shell is fixed to .theme-midnight,
  // so this just flips the sun/moon glyph to match the design header.
  const [mode, setMode] = useState<"light" | "dark">("dark");

  useEffect(() => {
    const saved = (typeof window !== "undefined"
      ? (localStorage.getItem("mits-lang") as Lang | null)
      : null);
    if (saved === "ru" || saved === "en") setLangState(saved);
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    if (typeof window !== "undefined") localStorage.setItem("mits-lang", l);
  }, []);

  const t = useCallback((k: StringKey) => T[lang][k], [lang]);

  // --- data ---
  const [rows, setRows] = useState<TaskRow[] | null>(null); // null = loading
  const [topics, setTopics] = useState<TopicInfo[]>([]);
  const [reasoning, setReasoning] = useState<string | null>(null);
  const [solvedCount] = useState(3); // progress hint in the insight banner (3 / 8)

  // --- generate / practice state ---
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selTopic, setSelTopic] = useState<string>("integrals");
  const [selDifficulty, setSelDifficulty] = useState<Difficulty>("medium");

  const fallbackRows = useMemo(() => FALLBACK_TASKS[lang], [lang]);

  // Fetch recommended tasks (rows) + topics (for the generate dialog).
  // On any error / empty payload we fall back to the ported static data.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      // topics — non-fatal; used only by the dialog select
      try {
        const { topics: tp } = await listTopics();
        if (!cancelled && tp.length) {
          setTopics(tp);
          setSelTopic((cur) => (tp.some((x) => x.id === cur) ? cur : tp[0].id));
        }
      } catch {
        /* dialog falls back to topics derived from rows */
      }

      // recommended tasks — the main list
      try {
        const rec = await getRecommendedTasks(8);
        if (cancelled) return;
        if (rec.tasks && rec.tasks.length > 0) {
          setRows(
            rec.tasks.map((task) => ({
              d: topicToDomain(task.topic),
              diff: task.difficulty,
              t: task.problem,
              tags: task.skills?.length ? task.skills.slice(0, 3) : [humanizeTopic(task.topic)],
              rate: pseudoRate(task.id || task.problem),
              topic: task.topic,
            })),
          );
          if (rec.reasoning) setReasoning(rec.reasoning);
        } else {
          setRows(fallbackRows);
        }
      } catch {
        if (!cancelled) setRows(fallbackRows);
      }
    })();

    return () => {
      cancelled = true;
    };
    // fallbackRows changes only with lang; we intentionally re-fetch on lang change
  }, [fallbackRows]);

  // Topic options for the dialog: backend topics if available, else derived from rows.
  const topicOptions = useMemo(() => {
    if (topics.length) {
      return topics.map((tp) => ({
        id: tp.id,
        label: lang === "ru" ? tp.name_ru || tp.name : tp.name,
      }));
    }
    const seen = new Set<string>();
    const opts: { id: string; label: string }[] = [];
    for (const r of rows ?? fallbackRows) {
      if (!seen.has(r.topic)) {
        seen.add(r.topic);
        opts.push({ id: r.topic, label: humanizeTopic(r.topic) });
      }
    }
    return opts;
  }, [topics, rows, fallbackRows, lang]);

  // Generate a task for {topic, difficulty}, create a guided session, open the chat.
  const startPractice = useCallback(
    async (topic: string, difficulty: Difficulty) => {
      if (busy) return;
      setBusy(true);
      setError(null);
      try {
        const task = await generateTask({ topic, difficulty, avoid_recent: true });
        const session = await createSession({
          topic,
          difficulty,
          mode: "guided_learning",
          custom_problem: task.problem,
        });
        const sessionData: Session = {
          id: session.id,
          created_at: session.created_at,
          updated_at: session.updated_at,
          topic: session.topic,
          difficulty: session.difficulty,
          status: session.status,
          mode: session.mode ?? "guided_learning",
          message_count: session.message_count,
          is_solved: session.is_solved,
          hints_used: session.hints_used,
        };
        addSession(sessionData);
        setActiveSession(session.id);
        router.push(`/chat/${session.id}`);
      } catch (e) {
        setError(
          e instanceof Error
            ? e.message
            : lang === "ru"
              ? "Не удалось сгенерировать задачу"
              : "Failed to generate task",
        );
        setBusy(false);
      }
    },
    [busy, addSession, setActiveSession, router, lang],
  );

  const confirmGenerate = async () => {
    setDialogOpen(false);
    await startPractice(selTopic, selDifficulty);
  };

  const list = rows ?? [];
  const loading = rows === null;

  return (
    <NewAppShell>
      <main className="main">
        <div className="page">
          <div className="page-head">
            <div className="page-head-info">
              <h1>{t("tasksTitle")}</h1>
              <div className="page-sub">{t("tasksSub")}</div>
            </div>

            {/* lang + theme toggles (PageControls) */}
            <div className="lang-toggle">
              <button className={lang === "ru" ? "active" : ""} onClick={() => setLang("ru")}>
                RU
              </button>
              <button className={lang === "en" ? "active" : ""} onClick={() => setLang("en")}>
                EN
              </button>
            </div>
            <button
              className="theme-toggle"
              onClick={() => setMode(mode === "light" ? "dark" : "light")}
              title="Toggle theme"
            >
              {mode === "light" ? Icon.moon : Icon.sun}
            </button>

            <button className="btn-secondary" onClick={() => setDialogOpen(true)}>
              ⌘F · {t("filter")}
            </button>
            <button className="btn-primary" onClick={() => setDialogOpen(true)} disabled={busy}>
              <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <path d="M8 1v6m-3-3 3-3 3 3M2 14h12" />
              </svg>
              {busy ? t("generating") : t("tasksGenerate")}
            </button>
          </div>

          <div className="page-body">
            <div className="insight-banner">
              <span className="ib-mark">▷</span>
              <span className="ib-text">{reasoning || t("insight")}</span>
              <span className="ib-meta">{solvedCount} / {Math.max(list.length, 8)}</span>
            </div>

            {error && (
              <div
                className="insight-banner"
                style={{
                  background: "rgba(255, 107, 107, 0.08)",
                  borderColor: "rgba(255, 107, 107, 0.3)",
                }}
              >
                <span className="ib-text" style={{ color: "#ff9c9c" }}>⚠ {error}</span>
              </div>
            )}

            <div className="tasks-list">
              {list.map((tk, i) => (
                <div
                  key={`${tk.topic}-${i}`}
                  className="task-row"
                  style={
                    {
                      "--dom": domColor(tk.d),
                      "--dom-tint": domColor(tk.d) + "10",
                      opacity: busy ? 0.5 : 1,
                    } as React.CSSProperties
                  }
                  onClick={() => !busy && startPractice(tk.topic, tk.diff)}
                >
                  <span className="dom-pill">{tk.d}</span>
                  <span className={"diff-chip " + tk.diff}>{t(("difficulty_" + tk.diff) as StringKey)}</span>
                  <span className="task-text">{tk.t}</span>
                  <div style={{ display: "flex", gap: 4 }}>
                    {tk.tags.map((tag) => (
                      <span key={tag} className="tag-chip">{tag}</span>
                    ))}
                  </div>
                  <span className="task-rate">
                    <svg viewBox="0 0 12 12" width="11" height="11" fill="currentColor" style={{ color: "#FFB85C" }}>
                      <path d="m6 .5 1.6 3.4 3.7.4-2.8 2.6.8 3.7L6 8.8l-3.3 1.8.8-3.7L.7 4.3l3.7-.4L6 .5z" />
                    </svg>
                    {Math.round(tk.rate * 100)}%
                  </span>
                  <span className="task-arrow">›</span>
                </div>
              ))}

              {/* Skeleton rows — shown while loading, else as a subtle "load more" hint. */}
              {(loading ? [0, 1, 2] : [0, 1]).map((i) => (
                <div key={"sk-" + i} className="task-row task-row-skeleton">
                  <span className="skeleton" style={{ width: 50, height: 18, borderRadius: 999 }} />
                  <span className="skeleton" style={{ width: 70, height: 18, borderRadius: 999 }} />
                  <span className="skeleton" style={{ flex: 1, height: 16, borderRadius: 4 }} />
                  <span className="skeleton" style={{ width: 60, height: 16, borderRadius: 999 }} />
                  <span className="skeleton" style={{ width: 38, height: 14, borderRadius: 4 }} />
                </div>
              ))}
            </div>
          </div>
        </div>

        {dialogOpen && (
          <GenerateDialog
            t={t}
            topics={topicOptions}
            selTopic={selTopic}
            setSelTopic={setSelTopic}
            selDifficulty={selDifficulty}
            setSelDifficulty={setSelDifficulty}
            busy={busy}
            onCancel={() => setDialogOpen(false)}
            onConfirm={confirmGenerate}
          />
        )}
      </main>
    </NewAppShell>
  );
}

// ---------- Generate-task dialog ----------
function GenerateDialog({
  t,
  topics,
  selTopic,
  setSelTopic,
  selDifficulty,
  setSelDifficulty,
  busy,
  onCancel,
  onConfirm,
}: {
  t: (k: StringKey) => string;
  topics: { id: string; label: string }[];
  selTopic: string;
  setSelTopic: (v: string) => void;
  selDifficulty: Difficulty;
  setSelDifficulty: (v: Difficulty) => void;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        display: "grid",
        placeItems: "center",
        background: "rgba(5, 2, 18, 0.66)",
        backdropFilter: "blur(4px)",
        zIndex: 9000,
      }}
      onClick={onCancel}
    >
      <div
        className="reco-item"
        style={{
          width: 480,
          maxWidth: "92vw",
          padding: 24,
          background: "var(--bg-panel)",
          border: "1px solid var(--line-strong)",
          borderRadius: "var(--radius-lg, 16px)",
          boxShadow: "0 24px 80px rgba(0,0,0,0.5)",
          cursor: "default",
          display: "block",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", alignItems: "center", marginBottom: 18 }}>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: "var(--ink)" }}>
            {t("dialogTitle")}
          </h2>
          <div style={{ flex: 1 }} />
          <button
            ref={closeRef}
            className="theme-toggle"
            onClick={onCancel}
            title={t("cancel")}
            style={{ fontSize: 16 }}
          >
            ✕
          </button>
        </div>

        <label style={{ display: "block", marginBottom: 16 }}>
          <span className="section-label" style={{ display: "block", marginBottom: 6 }}>
            {t("dialogTopic")}
          </span>
          <select
            value={selTopic}
            onChange={(e) => setSelTopic(e.target.value)}
            style={{
              width: "100%",
              padding: "9px 12px",
              background: "var(--bg-soft)",
              color: "var(--ink)",
              border: "1px solid var(--line-strong)",
              borderRadius: "var(--radius, 10px)",
              fontFamily: "inherit",
              fontSize: 13,
              appearance: "none",
            }}
          >
            {topics.map((tp) => (
              <option key={tp.id} value={tp.id}>
                {tp.label}
              </option>
            ))}
          </select>
        </label>

        <div style={{ marginBottom: 20 }}>
          <span className="section-label" style={{ display: "block", marginBottom: 8 }}>
            {t("dialogDifficulty")}
          </span>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {DIFFICULTIES.map((d) => {
              const active = selDifficulty === d;
              return (
                <button
                  key={d}
                  onClick={() => setSelDifficulty(d)}
                  className={"diff-chip " + d}
                  style={{
                    cursor: "pointer",
                    fontSize: 12.5,
                    padding: "6px 12px",
                    background: active ? "var(--accent-tint)" : "transparent",
                    borderColor: active ? "var(--accent)" : undefined,
                    outline: active ? "1px solid var(--accent)" : "none",
                  }}
                >
                  {t(("difficulty_" + d) as StringKey)}
                </button>
              );
            })}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ flex: 1, fontSize: 11.5, color: "var(--ink-mute)", lineHeight: 1.4 }}>
            {t("dialogHint")}
          </span>
          <button className="btn-secondary" onClick={onCancel}>
            {t("cancel")}
          </button>
          <button className="btn-primary" onClick={onConfirm} disabled={busy}>
            {busy ? t("starting") : t("confirm")} →
          </button>
        </div>
      </div>
    </div>
  );
}
