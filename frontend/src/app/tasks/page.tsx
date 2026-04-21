"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/cyber/AppShell";
import { Glitch } from "@/components/cyber/Glitch";
import { useI18n } from "@/lib/i18n";
import { DOMAIN_COLOR } from "@/lib/domains";
import { createSession, generateTask } from "@/lib/api";
import { useChatStore } from "@/store/chatStore";
import type { Difficulty, Session } from "@/types/api";

const TASKS_RU = [
  { d: "math", diff: "lvl 2", t: "Интеграл по частям: ∫x·eˣ dx", tags: ["integration", "IBP"], rate: 0.58, topic: "integrals", difficulty: "medium" as Difficulty },
  { d: "cs", diff: "lvl 3", t: "Количество способов разменять сумму N монетами", tags: ["DP", "coin-change"], rate: 0.44, topic: "dp", difficulty: "hard" as Difficulty },
  { d: "phys", diff: "lvl 2", t: "Брусок на наклонной с трением — найти ускорение", tags: ["mechanics"], rate: 0.67, topic: "mechanics", difficulty: "medium" as Difficulty },
  { d: "chem", diff: "lvl 1", t: "pH раствора слабой кислоты HA, Ka = 1.8·10⁻⁵", tags: ["equilibrium"], rate: 0.52, topic: "equilibrium", difficulty: "easy" as Difficulty },
  { d: "math", diff: "lvl 3", t: "Собственные значения матрицы 3×3", tags: ["linalg"], rate: 0.36, topic: "linear_algebra", difficulty: "hard" as Difficulty },
  { d: "bio", diff: "lvl 2", t: "Расчёт частот аллелей по Харди–Вайнбергу", tags: ["genetics"], rate: 0.41, topic: "genetics", difficulty: "medium" as Difficulty },
];

const TASKS_EN = [
  { d: "math", diff: "lvl 2", t: "Integration by parts: ∫x·eˣ dx", tags: ["integration", "IBP"], rate: 0.58, topic: "integrals", difficulty: "medium" as Difficulty },
  { d: "cs", diff: "lvl 3", t: "Number of ways to make change of N", tags: ["DP", "coin-change"], rate: 0.44, topic: "dp", difficulty: "hard" as Difficulty },
  { d: "phys", diff: "lvl 2", t: "Block on incline with friction — find acceleration", tags: ["mechanics"], rate: 0.67, topic: "mechanics", difficulty: "medium" as Difficulty },
  { d: "chem", diff: "lvl 1", t: "pH of weak acid HA, Ka = 1.8·10⁻⁵", tags: ["equilibrium"], rate: 0.52, topic: "equilibrium", difficulty: "easy" as Difficulty },
  { d: "math", diff: "lvl 3", t: "Eigenvalues of a 3×3 matrix", tags: ["linalg"], rate: 0.36, topic: "linear_algebra", difficulty: "hard" as Difficulty },
  { d: "bio", diff: "lvl 2", t: "Allele frequencies via Hardy–Weinberg", tags: ["genetics"], rate: 0.41, topic: "genetics", difficulty: "medium" as Difficulty },
];

const DIFFICULTIES: Difficulty[] = ["easy", "medium", "hard", "olympiad"];

export default function TasksPage() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const addSession = useChatStore((s) => s.addSession);
  const setActiveSession = useChatStore((s) => s.setActiveSession);

  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selTopic, setSelTopic] = useState("integrals");
  const [selDifficulty, setSelDifficulty] = useState<Difficulty>("medium");

  const tasks = lang === "ru" ? TASKS_RU : TASKS_EN;

  const startPracticeForTopic = async (topic: string, difficulty: Difficulty) => {
    setGenerating(true);
    setError(null);
    try {
      // 1. Generate task via LLM
      const task = await generateTask({ topic, difficulty, avoid_recent: true });

      // 2. Create session with that task
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

      // 3. Navigate to chat
      router.push(`/chat/${session.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сгенерировать задачу");
      setGenerating(false);
    }
  };

  const handleGenerate = () => {
    setDialogOpen(true);
  };

  const confirmGenerate = async () => {
    setDialogOpen(false);
    await startPracticeForTopic(selTopic, selDifficulty);
  };

  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="flex items-center mb-5">
          <div>
            <Glitch className="font-display" text={t("tasks_title")}>
              <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: "0.06em" }}>
                {t("tasks_title")}
              </span>
            </Glitch>
            <div className="ghost mt-1" style={{ fontSize: 11 }}>
              {"// 3 678 curated · 40+ skills · adaptive difficulty"}
            </div>
          </div>
          <div className="flex-1" />
          <button
            className="cbtn cbtn-primary"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating
              ? (lang === "ru" ? "ГЕНЕРАЦИЯ…" : "GENERATING…")
              : "⬢ " + (lang === "ru" ? "СГЕНЕРИРОВАТЬ" : "GENERATE")}
          </button>
        </div>

        {error && (
          <div
            className="mb-4 p-3 font-mono text-[11px]"
            style={{
              background: "rgba(232, 112, 147, 0.08)",
              border: "1px solid rgba(232, 112, 147, 0.3)",
              color: "var(--error)",
              borderRadius: 3,
            }}
          >
            ⚠ {error}
          </div>
        )}

        <div className="flex flex-col gap-2">
          {tasks.map((tk, i) => (
            <div
              key={i}
              className="panel flex items-center gap-3 cursor-pointer transition-colors"
              style={{ padding: 14, opacity: generating ? 0.5 : 1 }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--violet)")}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--line)")}
              onClick={() => !generating && startPracticeForTopic(tk.topic, tk.difficulty)}
            >
              <span
                className="flex items-center justify-center font-bold"
                style={{
                  width: 30,
                  height: 30,
                  background: DOMAIN_COLOR[tk.d],
                  color: "#05050a",
                  fontSize: 11,
                }}
              >
                {tk.d.toUpperCase().slice(0, 2)}
              </span>
              <span className="chip">{tk.diff.toUpperCase()}</span>
              <span style={{ flex: 1, color: "var(--text)", fontSize: 13 }}>{tk.t}</span>
              <div className="flex items-center gap-1">
                {tk.tags.map((g) => (
                  <span key={g} className="chip v">
                    {g}
                  </span>
                ))}
              </div>
              <span className="font-mono y" style={{ fontSize: 11 }}>
                ★ {Math.round(tk.rate * 100)}%
              </span>
              <span className="v">›</span>
            </div>
          ))}
        </div>

        {dialogOpen && (
          <div
            className="fixed inset-0 flex items-center justify-center z-[9000]"
            style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
            onClick={() => setDialogOpen(false)}
          >
            <div
              className="panel cornered"
              style={{
                width: 480,
                maxWidth: "92%",
                padding: 24,
                border: "1px solid var(--violet)",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <span className="corner-tl" />
              <span className="corner-br" />
              <div className="flex items-center mb-4">
                <Glitch className="font-display" text={lang === "ru" ? "НОВАЯ ЗАДАЧА" : "NEW TASK"}>
                  <span style={{ fontSize: 16, fontWeight: 600 }}>
                    {lang === "ru" ? "НОВАЯ ЗАДАЧА" : "NEW TASK"}
                  </span>
                </Glitch>
                <div className="flex-1" />
                <button
                  onClick={() => setDialogOpen(false)}
                  className="cbtn cbtn-ghost !px-2 !py-0.5 text-[11px]"
                >
                  ✕
                </button>
              </div>

              <label className="flex flex-col gap-1 mb-3">
                <span className="up ghost text-[9px] tracking-[0.2em]">❯ тема</span>
                <select
                  className="cinput"
                  value={selTopic}
                  onChange={(e) => setSelTopic(e.target.value)}
                  style={{ appearance: "none" }}
                >
                  {TASKS_RU.map((t) => (
                    <option key={t.topic} value={t.topic}>
                      {t.topic}
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col gap-1 mb-4">
                <span className="up ghost text-[9px] tracking-[0.2em]">❯ сложность</span>
                <div className="flex items-center gap-2">
                  {DIFFICULTIES.map((d) => (
                    <button
                      key={d}
                      onClick={() => setSelDifficulty(d)}
                      className="font-mono up cursor-pointer"
                      style={{
                        padding: "6px 12px",
                        border:
                          "1px solid " +
                          (selDifficulty === d ? "var(--yellow)" : "var(--line)"),
                        background:
                          selDifficulty === d
                            ? "rgba(232,198,104,0.1)"
                            : "transparent",
                        color: selDifficulty === d ? "var(--yellow)" : "var(--text-dim)",
                        fontSize: 10,
                        letterSpacing: "0.14em",
                        borderRadius: 3,
                      }}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </label>

              <div className="flex items-center gap-2 mt-3">
                <div className="ghost text-[10px]">
                  {"// модель сгенерирует задачу, создаст сессию и откроет чат"}
                </div>
                <div className="flex-1" />
                <button
                  onClick={() => setDialogOpen(false)}
                  className="cbtn text-[11px]"
                >
                  Отмена
                </button>
                <button
                  onClick={confirmGenerate}
                  className="cbtn cbtn-primary text-[11px]"
                  disabled={generating}
                >
                  {generating ? "..." : "⬢ ГЕНЕРИРОВАТЬ →"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
