"use client";

import { useCallback, useEffect, useState } from "react";

export type Lang = "ru" | "en";

export const STRINGS = {
  ru: {
    brand: "MITS",
    brand_full: "Math Intelligent Tutoring System",
    tagline: "Наставник, собравший тысячи заклинаний",
    nav_chat: "Диалог",
    nav_graph: "Карта знаний",
    nav_sources: "Источники",
    nav_profile: "Профиль",
    nav_tasks: "Задачник",
    nav_logout: "Выйти",
    nav_dashboard: "Обзор",
    mode_chat: "Свободный чат",
    mode_guided: "Сопровождение",
    mode_task: "Генератор задач",
    input_placeholder: "Задай вопрос, набросай решение или попроси задачу…",
    input_hint_enter: "отправить",
    input_hint_shift: "новая строка",
    input_hint_slash: "команды",
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
    online: "В СЕТИ",
    model: "qwen3.5-9b (fine-tuned)",
    graph_title: "KNOWLEDGE TRACING",
    graph_sub: "40+ навыков · BKT + DKT",
    sources_title: "ПОДКЛЮЧЁННЫЕ ИСТОЧНИКИ",
    profile_title: "ПРОФИЛЬ",
    tasks_title: "ЗАДАЧНИК",
    thinking: "рассуждаю",
    streaming: "поток",
    verified: "проверено",
    think_profiler: "Profiler: оценка уровня",
    think_planner: "Planner: построение траектории",
    think_tutor: "Tutor: формулирование вопроса",
    think_verifier: "Verifier: SymPy-проверка",
    new_session: "Новая сессия",
    sessions: "Сессии",
    suggested: "Попробуй спросить",
    skill_mastery: "владение",
    skill_attempts: "попыток",
    learning_trace: "Траектория сегодня",
    emotion: "Настроение",
    focus: "Фокус",
  },
  en: {
    brand: "MITS",
    brand_full: "Math Intelligent Tutoring System",
    tagline: "A mentor who gathered a thousand spells",
    nav_chat: "Dialogue",
    nav_graph: "Knowledge Map",
    nav_sources: "Sources",
    nav_profile: "Profile",
    nav_tasks: "Task Bank",
    nav_logout: "Log out",
    nav_dashboard: "Overview",
    mode_chat: "Free chat",
    mode_guided: "Guided",
    mode_task: "Task generator",
    input_placeholder: "Ask, sketch a solution, or request a problem…",
    input_hint_enter: "send",
    input_hint_shift: "new line",
    input_hint_slash: "commands",
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
    thinking: "reasoning",
    streaming: "streaming",
    verified: "verified",
    think_profiler: "Profiler: estimating level",
    think_planner: "Planner: drafting path",
    think_tutor: "Tutor: forming a question",
    think_verifier: "Verifier: symbolic check",
    new_session: "New session",
    sessions: "Sessions",
    suggested: "Try asking",
    skill_mastery: "mastery",
    skill_attempts: "attempts",
    learning_trace: "Today's trace",
    emotion: "Mood",
    focus: "Focus",
  },
} as const;

export type StringKey = keyof (typeof STRINGS)["ru"];

export function useI18n() {
  const [lang, setLangState] = useState<Lang>("ru");

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

  const t = useCallback(
    (k: StringKey) => STRINGS[lang][k] ?? k,
    [lang],
  );

  return { lang, setLang, t };
}
