// Tasks screen — local helpers, i18n strings and static fallback data.
// Ported from new_design (`pages (1).jsx` → TasksPage, `chat-app-data (1).jsx` → TASKS_DATA / DOMAIN_COLOR).
// The live screen replaces this mock with backend data; this is the offline/demo fallback
// so the Tasks screen ALWAYS renders complete.

import type { Difficulty } from "@/types/api";

export type Lang = "ru" | "en";

// Domain palette — midnight (dark) variants from new_design DOMAIN_COLOR.dark.
// Keyed by the short domain code used on the task pill.
export const DOMAIN_DARK: Record<string, string> = {
  math: "#B47BFF",
  phys: "#F0BB7E",
  chem: "#8DD4DC",
  cs: "#ED9CBF",
  bio: "#6FE0A6",
};

export function domColor(code: string): string {
  return DOMAIN_DARK[code] ?? "var(--accent)";
}

// A task row as the screen renders it (design shape).
export interface TaskRow {
  /** short domain code: math | phys | chem | cs | bio */
  d: string;
  /** difficulty bucket → drives the .diff-chip color */
  diff: Difficulty;
  /** problem text */
  t: string;
  /** skill tags */
  tags: string[];
  /** solve rate 0..1 (shown as %) */
  rate: number;
  /** backend topic id used to start practice */
  topic: string;
}

// i18n strings used by this screen (ported from I18N in chat-app-data).
export const T = {
  ru: {
    tasksTitle: "Каталог задач",
    tasksSub: "3 678 курированных · 40+ навыков · адаптивная сложность",
    tasksGenerate: "Сгенерировать",
    filter: "Фильтр",
    insight:
      "Эти задачи подобраны под слабые места в графе. Решите 3 — обновлю траекторию обучения.",
    difficulty_easy: "easy",
    difficulty_medium: "medium",
    difficulty_hard: "hard",
    difficulty_olympiad: "olympiad",
    generating: "Генерация…",
    dialogTitle: "Новая задача",
    dialogTopic: "тема",
    dialogDifficulty: "сложность",
    dialogHint: "модель сгенерирует задачу, создаст сессию и откроет чат",
    cancel: "Отмена",
    confirm: "Сгенерировать",
    starting: "Создаём сессию…",
  },
  en: {
    tasksTitle: "Task catalog",
    tasksSub: "3,678 curated · 40+ skills · adaptive difficulty",
    tasksGenerate: "Generate",
    filter: "Filter",
    insight:
      "These tasks target your weak spots in the graph. Solve 3 — I'll re-plan the trajectory.",
    difficulty_easy: "easy",
    difficulty_medium: "medium",
    difficulty_hard: "hard",
    difficulty_olympiad: "olympiad",
    generating: "Generating…",
    dialogTitle: "New task",
    dialogTopic: "topic",
    dialogDifficulty: "difficulty",
    dialogHint: "the model generates a task, creates a session and opens the chat",
    cancel: "Cancel",
    confirm: "Generate",
    starting: "Creating session…",
  },
} as const;

export type StringKey = keyof (typeof T)["ru"];

export const DIFFICULTIES: Difficulty[] = ["easy", "medium", "hard", "olympiad"];

// Static fallback rows (ported from TASKS_DATA, with backend `topic` ids added).
export const FALLBACK_TASKS: Record<Lang, TaskRow[]> = {
  ru: [
    { d: "math", diff: "medium", t: "Интеграл по частям: ∫x·eˣ dx", tags: ["integration", "IBP"], rate: 0.58, topic: "integrals" },
    { d: "cs", diff: "hard", t: "Кол-во способов разменять сумму N", tags: ["DP", "coin-change"], rate: 0.44, topic: "dp" },
    { d: "phys", diff: "medium", t: "Брусок на наклонной с трением", tags: ["mechanics"], rate: 0.67, topic: "mechanics" },
    { d: "chem", diff: "easy", t: "pH слабой кислоты HA, Ka = 1.8·10⁻⁵", tags: ["equilibrium"], rate: 0.52, topic: "equilibrium" },
    { d: "math", diff: "hard", t: "Собственные значения матрицы 3×3", tags: ["linalg"], rate: 0.36, topic: "linear_algebra" },
    { d: "bio", diff: "medium", t: "Частоты аллелей по Харди–Вайнбергу", tags: ["genetics"], rate: 0.41, topic: "genetics" },
    { d: "math", diff: "olympiad", t: "Неравенство Йенсена для log-сумм", tags: ["inequalities"], rate: 0.18, topic: "inequalities" },
    { d: "cs", diff: "medium", t: "Длина наибольшей возрастающей подп.", tags: ["DP", "LIS"], rate: 0.62, topic: "dp" },
  ],
  en: [
    { d: "math", diff: "medium", t: "Integration by parts: ∫x·eˣ dx", tags: ["integration", "IBP"], rate: 0.58, topic: "integrals" },
    { d: "cs", diff: "hard", t: "Ways to make change for amount N", tags: ["DP", "coin-change"], rate: 0.44, topic: "dp" },
    { d: "phys", diff: "medium", t: "Block on incline with friction", tags: ["mechanics"], rate: 0.67, topic: "mechanics" },
    { d: "chem", diff: "easy", t: "pH of weak acid HA, Ka = 1.8·10⁻⁵", tags: ["equilibrium"], rate: 0.52, topic: "equilibrium" },
    { d: "math", diff: "hard", t: "Eigenvalues of a 3×3 matrix", tags: ["linalg"], rate: 0.36, topic: "linear_algebra" },
    { d: "bio", diff: "medium", t: "Allele frequencies via Hardy–Weinberg", tags: ["genetics"], rate: 0.41, topic: "genetics" },
    { d: "math", diff: "olympiad", t: "Jensen's inequality for log-sums", tags: ["inequalities"], rate: 0.18, topic: "inequalities" },
    { d: "cs", diff: "medium", t: "Longest increasing subsequence", tags: ["DP", "LIS"], rate: 0.62, topic: "dp" },
  ],
};

// Map a backend topic id (e.g. "integrals", "mechanics", "organic_chemistry")
// to the short domain code used for the colored pill.
const DOMAIN_KEYWORDS: [RegExp, string][] = [
  [/(phys|mechan|kinemat|dynam|therm|electro|magnet|optic|wave)/i, "phys"],
  [/(chem|acid|base|equilibr|organic|reaction|mole|stoich)/i, "chem"],
  [/(bio|genet|cell|evolut|ecolog|protein|dna)/i, "bio"],
  [/(cs|algo|program|data.?struct|complexity|graph.?theory|dp|recursion|sort)/i, "cs"],
  [/(math|algebra|calc|integr|deriv|geometr|linear|matrix|probab|number|inequalit|trig)/i, "math"],
];

export function topicToDomain(topic: string): string {
  for (const [re, code] of DOMAIN_KEYWORDS) {
    if (re.test(topic)) return code;
  }
  return "math";
}

// Deterministic pseudo solve-rate for backend tasks that don't carry one,
// so the row still shows the star + % exactly like the design (stable per id).
export function pseudoRate(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) & 0x7fffffff;
  // 0.18 .. 0.82 range, matching the mock distribution
  return 0.18 + (h % 65) / 100;
}

// Humanize a topic id for the Generate dialog (e.g. "linear_algebra" → "linear algebra").
export function humanizeTopic(topic: string): string {
  return topic.replace(/[_-]+/g, " ").trim();
}
