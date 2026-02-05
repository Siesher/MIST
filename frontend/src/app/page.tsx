"use client";

import { useEffect } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { useChatStore } from "@/store/chatStore";
import { listSessions } from "@/lib/api";

export default function HomePage() {
  const setSessions = useChatStore((s) => s.setSessions);

  // Load sessions on mount
  useEffect(() => {
    async function load() {
      try {
        const result = await listSessions();
        setSessions(result.sessions);
      } catch {
        // Backend might not be running
      }
    }
    load();
  }, [setSessions]);

  // Apply theme from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("mits-theme") as "dark" | "light" | null;
    if (saved) {
      useChatStore.getState().setTheme(saved);
    } else {
      document.documentElement.classList.add("dark");
    }
  }, []);

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 flex items-center justify-center">
        <div className="text-center space-y-6 max-w-md px-4">
          <div className="text-6xl">&#x1f4d0;</div>
          <h1 className="text-3xl font-bold text-foreground">
            MITS
          </h1>
          <p className="text-lg text-muted-foreground">
            Математический Интеллектуальный Репетитор
          </p>
          <p className="text-sm text-muted-foreground">
            Нажмите &laquo;Новый чат&raquo; в боковой панели, чтобы начать обучение
          </p>
          <div className="flex flex-wrap justify-center gap-2 pt-4">
            {["Производные", "Интегралы", "Пределы", "Уравнения"].map((topic) => (
              <span
                key={topic}
                className="text-xs bg-muted text-muted-foreground px-3 py-1.5 rounded-full"
              >
                {topic}
              </span>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
