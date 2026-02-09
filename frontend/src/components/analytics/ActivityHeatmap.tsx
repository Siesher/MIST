"use client";

interface ActivityDay {
  date: string;
  count: number;
}

interface ActivityHeatmapProps {
  data: ActivityDay[];
}

export function ActivityHeatmap({ data }: ActivityHeatmapProps) {
  if (!data.length) {
    return (
      <div className="rounded-lg border border-border p-6 text-center text-muted-foreground">
        Нет данных об активности
      </div>
    );
  }

  const maxCount = Math.max(...data.map((d) => d.count), 1);

  const getColor = (count: number) => {
    if (count === 0) return "bg-muted";
    const intensity = count / maxCount;
    if (intensity > 0.75) return "bg-amber-500";
    if (intensity > 0.5) return "bg-amber-400";
    if (intensity > 0.25) return "bg-amber-300";
    return "bg-amber-200";
  };

  // Group by weeks
  const weeks: ActivityDay[][] = [];
  let currentWeek: ActivityDay[] = [];

  for (const day of data) {
    const date = new Date(day.date);
    if (currentWeek.length > 0 && date.getDay() === 0) {
      weeks.push(currentWeek);
      currentWeek = [];
    }
    currentWeek.push(day);
  }
  if (currentWeek.length) weeks.push(currentWeek);

  return (
    <div className="rounded-lg border border-border p-4">
      <h3 className="text-sm font-medium mb-4">Активность</h3>
      <div className="flex gap-0.5 overflow-x-auto">
        {weeks.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-0.5">
            {week.map((day) => (
              <div
                key={day.date}
                className={`w-3 h-3 rounded-sm ${getColor(day.count)}`}
                title={`${day.date}: ${day.count} сообщений`}
              />
            ))}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-1 mt-2 text-xs text-muted-foreground">
        <span>Меньше</span>
        <div className="w-3 h-3 rounded-sm bg-muted" />
        <div className="w-3 h-3 rounded-sm bg-amber-200" />
        <div className="w-3 h-3 rounded-sm bg-amber-300" />
        <div className="w-3 h-3 rounded-sm bg-amber-400" />
        <div className="w-3 h-3 rounded-sm bg-amber-500" />
        <span>Больше</span>
      </div>
    </div>
  );
}
