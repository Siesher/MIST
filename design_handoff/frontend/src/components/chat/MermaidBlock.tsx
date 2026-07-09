"use client";

import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

let initialized = false;

function initMermaid() {
  if (initialized) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    securityLevel: "loose",
    fontFamily: "var(--font-mono), monospace",
    themeVariables: {
      background: "transparent",
      primaryColor: "#1a1029",
      primaryTextColor: "#ece6fa",
      primaryBorderColor: "#a583ff",
      lineColor: "#a583ff",
      secondaryColor: "#6b4fb8",
      tertiaryColor: "#120a1f",
      mainBkg: "#1a1029",
      nodeBorder: "#a583ff",
      clusterBkg: "rgba(165,131,255,0.08)",
      edgeLabelBackground: "#0a0612",
    },
  });
  initialized = true;
}

interface Props {
  code: string;
}

export function MermaidBlock({ code }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    initMermaid();
    const id = `mermaid-${Math.random().toString(36).slice(2, 10)}`;
    (async () => {
      try {
        setError(null);
        const { svg } = await mermaid.render(id, code.trim());
        if (ref.current) ref.current.innerHTML = svg;
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
      }
    })();
  }, [code]);

  if (error) {
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
        <div className="up mb-1 text-[9px] tracking-[0.2em]">mermaid · error</div>
        <pre className="whitespace-pre-wrap">{error}</pre>
        <details className="mt-2">
          <summary className="ghost cursor-pointer">source</summary>
          <pre className="mt-1 text-[10px] ghost whitespace-pre-wrap">{code}</pre>
        </details>
      </div>
    );
  }

  return (
    <div
      className="my-3 p-4"
      style={{
        background: "rgba(10, 6, 18, 0.4)",
        border: "1px solid var(--line-hi)",
        borderRadius: 4,
        overflowX: "auto",
      }}
    >
      <div
        className="up ghost text-[9px] mb-2 tracking-[0.22em]"
        style={{ fontFamily: "var(--font-mono)" }}
      >
        ⬡ mermaid
      </div>
      <div ref={ref} className="mermaid-container" style={{ minHeight: 20 }} />
    </div>
  );
}
