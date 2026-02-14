"use client";

interface ErrorType {
  type: string;
  count: number;
  percentage: number;
}

interface ErrorDistributionProps {
  data: ErrorType[];
}

const LABELS: Record<string, string> = {
  scaffolding: "Направление",
  hint: "Подсказки",
  encourage: "Поощрение",
  rectify: "Исправление",
  tell: "Прямой ответ",
};

const COLORS: Record<string, string> = {
  scaffolding: "#3b82f6",
  hint: "#f59e0b",
  encourage: "#10b981",
  rectify: "#ef4444",
  tell: "#6b7280",
};

export function ErrorDistribution({ data }: ErrorDistributionProps) {
  if (!data.length) {
    return (
      <div className="rounded-lg border border-border p-6 text-center text-muted-foreground">
        Нет данных об ошибках
      </div>
    );
  }

  const total = data.reduce((s, d) => s + d.count, 0);

  return (
    <div className="rounded-lg border border-border p-4">
      <h3 className="text-sm font-medium mb-4">Типы взаимодействий</h3>
      <div className="space-y-2">
        {data.map((item) => (
          <div key={item.type}>
            <div className="flex justify-between text-xs mb-1">
              <span>{LABELS[item.type] || item.type}</span>
              <span className="text-muted-foreground">
                {item.count} ({(item.percentage * 100).toFixed(0)}%)
              </span>
            </div>
            <div className="h-2 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(item.count / total) * 100}%`,
                  backgroundColor: COLORS[item.type] || "#6b7280",
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
