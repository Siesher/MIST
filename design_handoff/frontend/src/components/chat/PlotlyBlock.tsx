"use client";

import { useMemo } from "react";
import dynamic from "next/dynamic";

// Dynamic import — Plotly is ~1MB, only load on demand
const Plot = dynamic(
  async () => {
    const [createPlotlyComponent, Plotly] = await Promise.all([
      import("react-plotly.js/factory").then((m) => m.default),
      // @ts-expect-error — plotly.js-basic-dist-min has no types
      import("plotly.js-basic-dist-min").then((m) => m.default),
    ]);
    return createPlotlyComponent(Plotly);
  },
  { ssr: false, loading: () => <div className="ghost text-[11px] p-4">loading plot…</div> },
);

interface Props {
  code: string;
}

const DARK_LAYOUT = {
  paper_bgcolor: "rgba(10, 6, 18, 0.4)",
  plot_bgcolor: "rgba(0, 0, 0, 0.3)",
  font: {
    family: "var(--font-mono), monospace",
    color: "#ece6fa",
    size: 11,
  },
  xaxis: {
    gridcolor: "rgba(165, 131, 255, 0.15)",
    zerolinecolor: "rgba(165, 131, 255, 0.4)",
    linecolor: "rgba(165, 131, 255, 0.3)",
  },
  yaxis: {
    gridcolor: "rgba(165, 131, 255, 0.15)",
    zerolinecolor: "rgba(165, 131, 255, 0.4)",
    linecolor: "rgba(165, 131, 255, 0.3)",
  },
  colorway: ["#a583ff", "#e8c668", "#8dd4dc", "#cf7fb8", "#6fe0a6"],
  margin: { t: 30, b: 40, l: 50, r: 20 },
  autosize: true,
};

export function PlotlyBlock({ code }: Props) {
  const parsed = useMemo(() => {
    try {
      const obj = JSON.parse(code.trim());
      const data = Array.isArray(obj.data) ? obj.data : [];
      const layout = { ...DARK_LAYOUT, ...(obj.layout || {}) };
      return { data, layout, error: null as string | null };
    } catch (e) {
      return { data: [], layout: DARK_LAYOUT, error: e instanceof Error ? e.message : String(e) };
    }
  }, [code]);

  if (parsed.error) {
    return (
      <div
        className="my-2 p-3 font-mono text-[11px]"
        style={{
          background: "rgba(232, 112, 147, 0.08)",
          border: "1px solid rgba(232, 112, 147, 0.3)",
          color: "var(--error)",
          borderRadius: 3,
        }}
      >
        <div className="up mb-1 text-[9px] tracking-[0.2em]">plotly · json error</div>
        <pre className="whitespace-pre-wrap">{parsed.error}</pre>
        <details className="mt-2">
          <summary className="ghost cursor-pointer">source</summary>
          <pre className="mt-1 text-[10px] ghost whitespace-pre-wrap">{code}</pre>
        </details>
      </div>
    );
  }

  return (
    <div
      className="my-3 p-3"
      style={{
        background: "rgba(10, 6, 18, 0.4)",
        border: "1px solid var(--line-hi)",
        borderRadius: 4,
      }}
    >
      <div
        className="up ghost text-[9px] mb-2 tracking-[0.22em]"
        style={{ fontFamily: "var(--font-mono)" }}
      >
        ⟨/⟩ plotly
      </div>
      <Plot
        data={parsed.data}
        layout={parsed.layout}
        useResizeHandler
        style={{ width: "100%", height: 360 }}
        config={{ displayModeBar: false, responsive: true }}
      />
    </div>
  );
}
