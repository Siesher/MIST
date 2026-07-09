"use client";

// Shared i18n for the new_design UI. Backed by a module-level store (like
// useTheme) so setLang() propagates to EVERY component using useI18n — not just
// the one that changed it. Persisted to localStorage("mits-lang").
import { useSyncExternalStore } from "react";

export type Lang = "ru" | "en";

export const STRINGS = {
  ru: {
    brand: "MITS",
    brand_full: "Math Intelligent Tutoring System",
    brand_sub: "Math · Intelligent Tutoring",
    tagline: "Наставник, собравший тысячи заклинаний",
    // nav (new_design wording)
    nav_chat: "Чат",
    nav_tasks: "Задачи",
    nav_graph: "Граф знаний",
    nav_dashboard: "Аналитика",
    nav_sources: "Источники",
    nav_profile: "Профиль",
    nav_settings: "Настройки",
    nav_signin: "Войти",
    nav_logout: "Выйти",
    // sidebar / shell
    new_session: "Новая сессия",
    sessions: "Сессии",
    no_sessions: "Нет сессий. Нажмите «Новая сессия», чтобы начать.",
    docs: "Документация",
    suggested: "Попробуй спросить",
    agents: "Агенты",
    // chat modes
    mode_chat: "Свободный чат",
    mode_chat_desc: "Свободное общение на любые темы",
    mode_guided: "Сократический тьютор",
    mode_guided_desc: "Никогда не даёт готовый ответ — ведёт вопросами",
    mode_task: "Генератор задач",
    mode_task_desc: "Генерация задач по теме и сложности",
    // composer
    hint_btn: "Подсказка",
    hints_left: "осталось",
    input_placeholder: "Опишите ваш ход решения или задайте вопрос…",
    input_placeholder_guided: "Ваш ответ или вопрос…",
    input_placeholder_task: "Какую тему и сложность задач сгенерировать?",
    ws_reconnecting: "Переподключение к серверу… ответ придёт, как только связь восстановится.",
    input_hint_enter: "отправить",
    input_hint_shift: "новая строка",
    input_hint_slash: "команды",
    // messages
    msg_student: "Студент",
    msg_tutor: "Тьютор",
    think_show: "Размышления модели",
    think_hide: "Свернуть размышления",
    citations_label: "ИСТОЧНИКИ",
    citations_open: "Открыть библиотеку источников",
    thinking: "рассуждаю",
    streaming: "поток",
    verified: "проверено",
    think_profiler: "Profiler: оценка уровня",
    think_planner: "Planner: построение траектории",
    think_tutor: "Tutor: формулирование вопроса",
    think_verifier: "Verifier: SymPy-проверка",
    // auth
    auth_login: "Войти",
    auth_register: "Регистрация",
    auth_email: "E-mail или логин",
    auth_pass: "Пароль",
    auth_name: "Имя",
    auth_welcome_line1: "ДОСТУП К ГРИМУАРУ",
    auth_welcome_line2: "система сократического обучения",
    auth_forgot: "Забыл пароль",
    auth_to_register: "Создать учётную запись",
    auth_to_login: "У меня уже есть доступ",
    // status / misc
    online: "В СЕТИ",
    model: "qwen3.5-9b (fine-tuned)",
    graph_title: "KNOWLEDGE TRACING",
    graph_sub: "40+ навыков · BKT + DKT",
    sources_title: "ПОДКЛЮЧЁННЫЕ ИСТОЧНИКИ",
    profile_title: "ПРОФИЛЬ",
    tasks_title: "ЗАДАЧНИК",
    skill_mastery: "владение",
    skill_attempts: "попыток",
    learning_trace: "Траектория сегодня",
    emotion: "Настроение",
    focus: "Фокус",
    difficulty: "Сложность",
    attach: "Прикрепить файл (PDF, DOCX, фото, текст)",
    voice: "Голос",
    send: "Отправить",
    attach_analyzing: "Читаю источник…",
    attach_attached: "Источник прикреплён",
    attach_remove: "Убрать",
    attach_error: "Не удалось прочитать файл",
    empty_title: "Сократический метод",
    empty_hint: "Опишите ваш ход решения или задайте вопрос.",
    thinking_dots: "Думает",
    rail_session: "Текущая сессия",
    stat_messages: "сообщений",
    stat_hints: "подсказок",
    stat_solved: "решено",
    stat_latency: "отклик",
    active_agents: "Активные агенты",
    move_scaffolding: "Разбор по шагам",
    move_hint: "Подсказка",
    move_encourage: "Поощрение",
    move_problematize: "Вопрос",
    move_rectify: "Исправление",
    move_clarify: "Уточнение",
    move_tell: "Ответ",
    theme_label: "Тема",
    task_default: "Задача",
    task_current: "Текущая задача",
  },
  en: {
    brand: "MITS",
    brand_full: "Math Intelligent Tutoring System",
    brand_sub: "Math · Intelligent Tutoring",
    tagline: "A mentor who gathered a thousand spells",
    nav_chat: "Chat",
    nav_tasks: "Tasks",
    nav_graph: "Knowledge Graph",
    nav_dashboard: "Analytics",
    nav_sources: "Sources",
    nav_profile: "Profile",
    nav_settings: "Settings",
    nav_signin: "Sign in",
    nav_logout: "Log out",
    new_session: "New session",
    sessions: "Sessions",
    no_sessions: "No sessions yet. Click “New session” to start.",
    docs: "Documentation",
    suggested: "Try asking",
    agents: "Agents",
    mode_chat: "Free chat",
    mode_chat_desc: "Open conversation on any topic",
    mode_guided: "Socratic tutor",
    mode_guided_desc: "Never gives the answer — guides with questions",
    mode_task: "Task generator",
    mode_task_desc: "Generate problems by topic and difficulty",
    hint_btn: "Hint",
    hints_left: "left",
    input_placeholder: "Describe your reasoning or ask a question…",
    input_placeholder_guided: "Your answer or question…",
    input_placeholder_task: "Which topic and difficulty should I generate?",
    ws_reconnecting: "Reconnecting to the server… your answer will arrive once the connection is back.",
    input_hint_enter: "send",
    input_hint_shift: "new line",
    input_hint_slash: "commands",
    msg_student: "Student",
    msg_tutor: "Tutor",
    think_show: "Model reasoning",
    think_hide: "Hide reasoning",
    citations_label: "SOURCES",
    citations_open: "Open source library",
    thinking: "reasoning",
    streaming: "streaming",
    verified: "verified",
    think_profiler: "Profiler: estimating level",
    think_planner: "Planner: drafting path",
    think_tutor: "Tutor: forming a question",
    think_verifier: "Verifier: symbolic check",
    auth_login: "Log in",
    auth_register: "Register",
    auth_email: "E-mail or handle",
    auth_pass: "Password",
    auth_name: "Name",
    auth_welcome_line1: "ACCESS THE GRIMOIRE",
    auth_welcome_line2: "a socratic STEM tutor",
    auth_forgot: "Forgot password",
    auth_to_register: "Create account",
    auth_to_login: "I already have access",
    online: "ONLINE",
    model: "qwen3.5-9b (fine-tuned)",
    graph_title: "KNOWLEDGE TRACING",
    graph_sub: "40+ skills · BKT + DKT",
    sources_title: "CONNECTED SOURCES",
    profile_title: "PROFILE",
    tasks_title: "TASK BANK",
    skill_mastery: "mastery",
    skill_attempts: "attempts",
    learning_trace: "Today's trace",
    emotion: "Mood",
    focus: "Focus",
    difficulty: "Difficulty",
    attach: "Attach file (PDF, DOCX, photo, text)",
    voice: "Voice",
    send: "Send",
    attach_analyzing: "Reading source…",
    attach_attached: "Source attached",
    attach_remove: "Remove",
    attach_error: "Couldn't read file",
    empty_title: "Socratic method",
    empty_hint: "Describe your reasoning or ask a question.",
    thinking_dots: "Thinking",
    rail_session: "Current session",
    stat_messages: "messages",
    stat_hints: "hints",
    stat_solved: "solved",
    stat_latency: "response",
    active_agents: "Active agents",
    move_scaffolding: "Step-by-step",
    move_hint: "Hint",
    move_encourage: "Encouragement",
    move_problematize: "Question",
    move_rectify: "Correction",
    move_clarify: "Clarification",
    move_tell: "Answer",
    theme_label: "Theme",
    task_default: "Task",
    task_current: "Current task",
  },
} as const;

export type StringKey = keyof (typeof STRINGS)["ru"];

const KEY = "mits-lang";
const DEFAULT: Lang = "ru";
const listeners = new Set<() => void>();
let current: Lang | null = null;

function read(): Lang {
  if (current) return current;
  if (typeof window === "undefined") return DEFAULT;
  const saved = window.localStorage.getItem(KEY) as Lang | null;
  current = saved === "en" || saved === "ru" ? saved : DEFAULT;
  return current;
}

export function setLang(l: Lang): void {
  current = l;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(KEY, l);
    document.documentElement.lang = l;
  }
  listeners.forEach((fn) => fn());
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

export function useI18n() {
  const lang = useSyncExternalStore(subscribe, read, () => DEFAULT);
  const t = (k: StringKey): string => STRINGS[lang][k] ?? k;
  return { lang, setLang, t };
}
