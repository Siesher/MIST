"use client";

interface Recommendation {
  topic: string;
  priority: "high" | "medium" | "low";
  reason: string;
  solve_rate: number;
  sessions: number;
}

interface RecommendationsProps {
  data: Recommendation[];
}

const PRIORITY_STYLES = {
  high: "border-l-amber-500 bg-amber-500/5",
  medium: "border-l-blue-500 bg-blue-500/5",
  low: "border-l-green-500 bg-green-500/5",
};

const PRIORITY_LABELS = {
  high: "Рекомендовано",
  medium: "По возможности",
  low: "Повторение",
};

export function Recommendations({ data }: RecommendationsProps) {
  if (!data.length) {
    return (
      <div className="rounded-lg border border-border p-6 text-center text-muted-foreground">
        Нет рекомендаций
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border p-4">
      <h3 className="text-sm font-medium mb-4">Рекомендации</h3>
      <div className="space-y-2">
        {data.map((rec) => (
          <div
            key={rec.topic}
            className={`border-l-4 rounded-r-lg p-3 ${PRIORITY_STYLES[rec.priority]}`}
          >
            <div className="flex justify-between items-start">
              <div>
                <p className="text-sm font-medium">{rec.topic}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {rec.reason}
                </p>
              </div>
              <span className="text-xs px-2 py-0.5 rounded-full bg-background border border-border">
                {PRIORITY_LABELS[rec.priority]}
              </span>
            </div>
            <div className="flex gap-3 mt-2 text-xs text-muted-foreground">
              <span>Решено: {(rec.solve_rate * 100).toFixed(0)}%</span>
              <span>Сессий: {rec.sessions}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
