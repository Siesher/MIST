"use client";

import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useChatStore } from "@/store/chatStore";

export default function SettingsPage() {
  const router = useRouter();
  const theme = useChatStore((s) => s.theme);
  const toggleTheme = useChatStore((s) => s.toggleTheme);

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-xl mx-auto space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="sm" onClick={() => router.push("/")}>
            &larr; Назад
          </Button>
          <h1 className="text-2xl font-bold">Настройки</h1>
        </div>

        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Оформление</h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Тема</p>
              <p className="text-xs text-muted-foreground">
                {theme === "dark" ? "Тёмная тема" : "Светлая тема"}
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={toggleTheme}>
              {theme === "dark" ? "Светлая" : "Тёмная"}
            </Button>
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">О системе</h2>
          <div className="space-y-2 text-sm text-muted-foreground">
            <p>MITS v1.0 — Mathematics Intelligent Tutoring System</p>
            <p>Сократический метод обучения математике с ИИ</p>
          </div>
        </Card>
      </div>
    </div>
  );
}
