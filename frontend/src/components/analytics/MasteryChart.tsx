"use client";

interface TopicHistory {
  topic: string;
  history: { date: string; mastery: number }[];
}

interface MasteryChartProps {
  data: TopicHistory[];
}

const COLORS = [
  "#f59e0b", "#3b82f6", "#10b981", "#ef4444", "#8b5cf6",
  "#ec4899", "#06b6d4", "#84cc16",
];

export function MasteryChart({ data }: MasteryChartProps) {
  if (!data.length) {
    return (
      <div className="rounded-lg border border-border p-6 text-center text-muted-foreground">
        Нет данных по темам
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border p-4">
      <h3 className="text-sm font-medium mb-4">Освоение по темам</h3>
      <div className="space-y-3">
        {data.map((topic, i) => {
          const latest = topic.history[topic.history.length - 1];
          const mastery = latest?.mastery ?? 0;
          const color = COLORS[i % COLORS.length];

          return (
            <div key={topic.topic}>
              <div className="flex justify-between text-xs mb-1">
                <span>{topic.topic}</span>
                <span className="text-muted-foreground">
                  {(mastery * 100).toFixed(0)}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${mastery * 100}%`,
                    backgroundColor: color,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
