"use client";

import { useMemo } from "react";
import { MathRenderer } from "./MathRenderer";
import { MermaidBlock } from "./MermaidBlock";
import { PlotlyBlock } from "./PlotlyBlock";

interface Props {
  content: string;
}

type Segment =
  | { kind: "text"; content: string }
  | { kind: "mermaid"; content: string }
  | { kind: "plotly"; content: string }
  | { kind: "code"; content: string; lang: string };

const FENCE = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;

function splitSegments(text: string): Segment[] {
  const segments: Segment[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  FENCE.lastIndex = 0;
  while ((m = FENCE.exec(text)) !== null) {
    if (m.index > last) {
      segments.push({ kind: "text", content: text.slice(last, m.index) });
    }
    const lang = (m[1] || "").toLowerCase();
    const body = m[2];
    if (lang === "mermaid") {
      segments.push({ kind: "mermaid", content: body });
    } else if (lang === "plotly" || lang === "plot") {
      segments.push({ kind: "plotly", content: body });
    } else {
      segments.push({ kind: "code", content: body, lang });
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    segments.push({ kind: "text", content: text.slice(last) });
  }
  return segments;
}

export function SmartContent({ content }: Props) {
  const segments = useMemo(() => splitSegments(content), [content]);

  return (
    <>
      {segments.map((seg, i) => {
        if (seg.kind === "mermaid") {
          return <MermaidBlock key={i} code={seg.content} />;
        }
        if (seg.kind === "plotly") {
          return <PlotlyBlock key={i} code={seg.content} />;
        }
        if (seg.kind === "code") {
          return (
            <pre
              key={i}
              className="my-2 p-3 overflow-x-auto font-mono text-[12px]"
              style={{
                background: "rgba(0,0,0,0.4)",
                border: "1px solid var(--line)",
                borderRadius: 3,
                color: "var(--text)",
              }}
            >
              {seg.lang && (
                <div className="up ghost text-[9px] mb-1 tracking-[0.2em]">
                  {seg.lang}
                </div>
              )}
              <code>{seg.content}</code>
            </pre>
          );
        }
        return <MathRenderer key={i} content={seg.content} />;
      })}
    </>
  );
}
