"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getProfile } from "@/lib/api";
import type { StudentProfile } from "@/types/api";

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<StudentProfile | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await getProfile();
        setProfile(data);
      } catch {
        // Backend might not be running
      }
    }
    load();
  }, []);

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="sm" onClick={() => router.push("/")}>
            &larr; Назад
          </Button>
          <h1 className="text-2xl font-bold">Профиль ученика</h1>
        </div>

        {!profile ? (
          <p className="text-muted-foreground">Загрузка...</p>
        ) : (
          <>
            {/* Stats cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card className="p-4 text-center">
                <p className="text-2xl font-bold">{profile.total_sessions}</p>
                <p className="text-xs text-muted-foreground">Сессий</p>
              </Card>
              <Card className="p-4 text-center">
                <p className="text-2xl font-bold">
                  {Math.round(profile.success_rate * 100)}%
                </p>
                <p className="text-xs text-muted-foreground">Успешность</p>
              </Card>
              <Card className="p-4 text-center">
                <p className="text-2xl font-bold">{profile.streak_days}</p>
                <p className="text-xs text-muted-foreground">Дней подряд</p>
              </Card>
              <Card className="p-4 text-center">
                <p className="text-2xl font-bold">{profile.total_time_minutes}</p>
                <p className="text-xs text-muted-foreground">Минут</p>
              </Card>
            </div>

            {/* Mastery by topic */}
            <Card className="p-6">
              <h2 className="text-lg font-semibold mb-4">Освоение тем</h2>
              {Object.keys(profile.mastery_by_topic).length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Пока нет данных. Решите несколько задач для отображения прогресса.
                </p>
              ) : (
                <div className="space-y-3">
                  {Object.entries(profile.mastery_by_topic).map(
                    ([topic, mastery]) => (
                      <div key={topic}>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="capitalize">{topic}</span>
                          <span>{Math.round(mastery * 100)}%</span>
                        </div>
                        <div className="h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-amber-600 rounded-full transition-all"
                            style={{ width: `${mastery * 100}%` }}
                          />
                        </div>
                      </div>
                    ),
                  )}
                </div>
              )}
            </Card>

            {/* Skills */}
            <div className="grid md:grid-cols-2 gap-4">
              <Card className="p-6">
                <h3 className="text-sm font-semibold mb-2 text-green-500">
                  Сильные навыки
                </h3>
                {profile.strong_skills.length === 0 ? (
                  <p className="text-xs text-muted-foreground">Пока нет данных</p>
                ) : (
                  <div className="flex flex-wrap gap-1">
                    {profile.strong_skills.map((skill) => (
                      <span
                        key={skill}
                        className="text-xs bg-green-500/10 text-green-500 px-2 py-1 rounded"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                )}
              </Card>
              <Card className="p-6">
                <h3 className="text-sm font-semibold mb-2 text-red-500">
                  Нужно практиковать
                </h3>
                {profile.weak_skills.length === 0 ? (
                  <p className="text-xs text-muted-foreground">Пока нет данных</p>
                ) : (
                  <div className="flex flex-wrap gap-1">
                    {profile.weak_skills.map((skill) => (
                      <span
                        key={skill}
                        className="text-xs bg-red-500/10 text-red-500 px-2 py-1 rounded"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                )}
              </Card>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
