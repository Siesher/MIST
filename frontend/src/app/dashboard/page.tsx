"use client";

import { useCallback, useEffect, useState } from "react";
import { MasteryChart } from "@/components/analytics/MasteryChart";
import { ActivityHeatmap } from "@/components/analytics/ActivityHeatmap";
import { ErrorDistribution } from "@/components/analytics/ErrorDistribution";
import { Recommendations } from "@/components/analytics/Recommendations";
import { useAuth } from "@/components/auth/AuthProvider";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PerformanceData {
  total_sessions: number;
  solved_sessions: number;
  solve_rate: number;
  total_hints_used: number;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [activity, setActivity] = useState([]);
  const [mastery, setMastery] = useState([]);
  const [errors, setErrors] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [performance, setPerformance] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user?.id) {
      setLoading(false);
      return;
    }

    const fetchAll = async () => {
      const headers: Record<string, string> = {};
      const token = localStorage.getItem("mits-access-token");
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const base = `${API_BASE}/api/v1/analytics`;
      const params = `user_id=${user.id}`;

      try {
        const [actRes, mastRes, errRes, recRes, perfRes] = await Promise.all([
          fetch(`${base}/activity?${params}`, { headers }),
          fetch(`${base}/mastery?${params}`, { headers }),
          fetch(`${base}/errors?${params}`, { headers }),
          fetch(`${base}/recommendations?${params}`, { headers }),
          fetch(`${base}/performance?${params}`, { headers }),
        ]);

        if (actRes.ok) setActivity(await actRes.json());
        if (mastRes.ok) setMastery(await mastRes.json());
        if (errRes.ok) setErrors(await errRes.json());
        if (recRes.ok) setRecommendations(await recRes.json());
        if (perfRes.ok) setPerformance(await perfRes.json());
      } catch (e) {
        console.error("Failed to fetch analytics:", e);
      } finally {
        setLoading(false);
      }
    };

    fetchAll();
  }, [user]);

  const handleExport = useCallback(async () => {
    if (!user?.id) return;
    const token = localStorage.getItem("mits-access-token");
    const params = new URLSearchParams({ user_id: user.id, user_name: user.display_name || "Студент" });
    const res = await fetch(`${API_BASE}/api/v1/export/report.pdf?${params}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "mits_report.pdf";
    a.click();
    URL.revokeObjectURL(url);
  }, [user]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Загрузка аналитики...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">
          Войдите в аккаунт для просмотра аналитики
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Аналитика</h1>
        <button
          onClick={handleExport}
          className="px-4 py-2 text-sm rounded-lg border border-border hover:bg-muted transition-colors"
        >
          Экспорт PDF
        </button>
      </div>

      {/* Stats summary */}
      {performance && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Сессий" value={performance.total_sessions} />
          <StatCard label="Решено" value={performance.solved_sessions} />
          <StatCard
            label="Процент решения"
            value={`${(performance.solve_rate * 100).toFixed(0)}%`}
          />
          <StatCard label="Подсказок" value={performance.total_hints_used} />
        </div>
      )}

      {/* Charts grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <MasteryChart data={mastery} />
        <ActivityHeatmap data={activity} />
        <ErrorDistribution data={errors} />
        <Recommendations data={recommendations} />
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-border p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-2xl font-semibold mt-1">{value}</p>
    </div>
  );
}
