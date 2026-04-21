"use client";

import { useRef, useState } from "react";
import { AppShell } from "@/components/cyber/AppShell";
import { Glitch } from "@/components/cyber/Glitch";
import { useI18n } from "@/lib/i18n";
import { DOMAIN_COLOR } from "@/lib/domains";
import { createSession } from "@/lib/api";
import { useChatStore } from "@/store/chatStore";
import { useRouter } from "next/navigation";
import type { Session } from "@/types/api";

interface Node {
  id: string;
  x: number;
  y: number;
  r: number;
  label: string;
  domain: string;
  mastery: number;
  attempts: number;
  active?: boolean;
  highlight?: boolean;
}

const GRAPH_NODES: Node[] = [
  { id: "arith", x: 200, y: 260, r: 24, label: "Arithmetic", domain: "math", mastery: 0.94, attempts: 142 },
  { id: "alg", x: 320, y: 200, r: 26, label: "Algebra", domain: "math", mastery: 0.82, attempts: 118 },
  { id: "linalg", x: 440, y: 160, r: 22, label: "Linear Alg", domain: "math", mastery: 0.64, attempts: 63 },
  { id: "calc", x: 460, y: 280, r: 28, label: "Calculus", domain: "math", mastery: 0.71, attempts: 97, active: true },
  { id: "int", x: 560, y: 340, r: 24, label: "Integrals", domain: "math", mastery: 0.58, attempts: 41, highlight: true },
  { id: "diff", x: 560, y: 230, r: 22, label: "Derivatives", domain: "math", mastery: 0.78, attempts: 72 },
  { id: "geom", x: 340, y: 340, r: 22, label: "Geometry", domain: "math", mastery: 0.69, attempts: 58 },
  { id: "prob", x: 260, y: 420, r: 22, label: "Probability", domain: "math", mastery: 0.44, attempts: 29 },
  { id: "mech", x: 720, y: 180, r: 24, label: "Mechanics", domain: "phys", mastery: 0.67, attempts: 51 },
  { id: "therm", x: 820, y: 260, r: 22, label: "Thermo", domain: "phys", mastery: 0.38, attempts: 17 },
  { id: "em", x: 780, y: 380, r: 22, label: "EM Fields", domain: "phys", mastery: 0.22, attempts: 9 },
  { id: "chem", x: 660, y: 460, r: 22, label: "Chemistry", domain: "chem", mastery: 0.51, attempts: 32 },
  { id: "org", x: 760, y: 510, r: 20, label: "Organic", domain: "chem", mastery: 0.33, attempts: 12 },
  { id: "cs", x: 140, y: 380, r: 22, label: "CS Basics", domain: "cs", mastery: 0.88, attempts: 104 },
  { id: "ds", x: 100, y: 480, r: 22, label: "DS & Algo", domain: "cs", mastery: 0.72, attempts: 61 },
  { id: "dp", x: 200, y: 540, r: 20, label: "DP", domain: "cs", mastery: 0.48, attempts: 24 },
  { id: "bio", x: 900, y: 440, r: 20, label: "Biology", domain: "bio", mastery: 0.41, attempts: 18 },
  { id: "gen", x: 960, y: 530, r: 18, label: "Genetics", domain: "bio", mastery: 0.19, attempts: 6 },
];

const GRAPH_EDGES: [string, string][] = [
  ["arith", "alg"], ["alg", "linalg"], ["alg", "calc"], ["calc", "diff"], ["calc", "int"],
  ["diff", "int"], ["alg", "geom"], ["alg", "prob"], ["calc", "mech"], ["mech", "therm"],
  ["mech", "em"], ["chem", "org"], ["cs", "ds"], ["ds", "dp"], ["alg", "cs"], ["bio", "gen"],
  ["chem", "bio"], ["linalg", "mech"], ["prob", "bio"], ["int", "mech"], ["diff", "mech"],
];

export default function GraphPage() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const addSession = useChatStore((s) => s.addSession);
  const setActiveSession = useChatStore((s) => s.setActiveSession);

  const svgRef = useRef<SVGSVGElement | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [selected, setSelected] = useState("int");
  const [dragging, setDragging] = useState(false);
  const [hover, setHover] = useState<string | null>(null);
  const [practicing, setPracticing] = useState(false);
  const dragStart = useRef({ x: 0, y: 0, px: 0, py: 0 });

  const startPractice = async (node: Node | undefined) => {
    if (!node || practicing) return;
    setPracticing(true);
    try {
      const topicId = node.id;
      const customProblem =
        lang === "ru"
          ? `Давай поработаем над темой «${node.label}» (${node.domain}). Покажи задачу на этот концепт.`
          : `Let's work on "${node.label}" (${node.domain}). Show me a problem on this concept.`;

      const session = await createSession({
        topic: topicId,
        difficulty: "medium",
        mode: "guided_learning",
        custom_problem: customProblem,
      });

      const sessionData: Session = {
        id: session.id,
        created_at: session.created_at,
        updated_at: session.updated_at,
        topic: session.topic,
        difficulty: session.difficulty,
        status: session.status,
        mode: session.mode ?? "guided_learning",
        message_count: session.message_count,
        is_solved: session.is_solved,
        hints_used: session.hints_used,
      };
      addSession(sessionData);
      setActiveSession(session.id);
      router.push(`/chat/${session.id}`);
    } catch (e) {
      console.error("Practice start failed:", e);
      setPracticing(false);
      alert(e instanceof Error ? e.message : "Не удалось начать практику");
    }
  };

  const onDown = (e: React.MouseEvent) => {
    setDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y };
  };
  const onMove = (e: React.MouseEvent) => {
    if (!dragging) return;
    setPan({
      x: dragStart.current.px + (e.clientX - dragStart.current.x),
      y: dragStart.current.py + (e.clientY - dragStart.current.y),
    });
  };
  const onUp = () => setDragging(false);
  const onWheel = (e: React.WheelEvent) => {
    const delta = -e.deltaY * 0.001;
    setZoom((z) => Math.min(3, Math.max(0.4, z + delta)));
  };

  const sel = GRAPH_NODES.find((n) => n.id === selected);

  return (
    <AppShell>
      <div className="flex flex-col flex-1 min-w-0">
        {/* header */}
        <div
          className="flex items-center"
          style={{
            padding: "14px 20px",
            borderBottom: "1px solid var(--line)",
            background: "rgba(0,0,0,0.3)",
          }}
        >
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <Glitch className="font-display" text={t("graph_title")}>
                <span style={{ fontSize: 18, fontWeight: 600, letterSpacing: "0.08em" }}>
                  {t("graph_title")}
                </span>
              </Glitch>
              <span className="chip v">LIVE</span>
            </div>
            <div className="ghost mt-1" style={{ fontSize: 10, letterSpacing: "0.16em" }}>
              {"// "}{t("graph_sub")}
            </div>
          </div>
          <div className="flex-1" />
          <div className="flex items-center gap-2">
            {Object.entries(DOMAIN_COLOR).map(([k, c]) => (
              <div key={k} className="flex items-center gap-1 text-[10px]">
                <span style={{ width: 8, height: 8, background: c, boxShadow: `0 0 6px ${c}` }} />
                <span className="up ghost tracking-[0.14em]">{k}</span>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-1 ml-4">
            <button className="cbtn !px-2 !py-1 text-[11px]" onClick={() => setZoom((z) => Math.min(3, z + 0.2))}>
              +
            </button>
            <button className="cbtn !px-2 !py-1 text-[11px]" onClick={() => setZoom((z) => Math.max(0.4, z - 0.2))}>
              −
            </button>
            <button
              className="cbtn !px-2 !py-1 text-[11px]"
              onClick={() => {
                setZoom(1);
                setPan({ x: 0, y: 0 });
              }}
            >
              ⌂
            </button>
          </div>
        </div>

        <div className="flex flex-1 min-h-0">
          {/* canvas */}
          <div
            className="flex-1 relative overflow-hidden"
            style={{
              cursor: dragging ? "grabbing" : "grab",
              background: "radial-gradient(ellipse at center, rgba(165,131,255,0.06), transparent 70%)",
            }}
            onMouseDown={onDown}
            onMouseMove={onMove}
            onMouseUp={onUp}
            onMouseLeave={onUp}
            onWheel={onWheel}
          >
            <div
              className="absolute top-3 left-3.5 z-[2] text-[10px]"
              style={{ color: "var(--text-muted)", letterSpacing: "0.14em" }}
            >
              <div>ZOOM · <span className="y">{zoom.toFixed(2)}x</span></div>
              <div>PAN · <span className="v">{Math.round(pan.x)}, {Math.round(pan.y)}</span></div>
              <div>NODES · <span>{GRAPH_NODES.length}</span></div>
              <div>EDGES · <span>{GRAPH_EDGES.length}</span></div>
            </div>

            <svg ref={svgRef} width="100%" height="100%" viewBox="0 0 1080 640" style={{ display: "block" }}>
              <defs>
                <filter id="glowf" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="3" result="b" />
                  <feMerge>
                    <feMergeNode in="b" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <radialGradient id="ring-active">
                  <stop offset="60%" stopColor="rgba(232,198,104,0)" />
                  <stop offset="95%" stopColor="rgba(232,198,104,0.5)" />
                  <stop offset="100%" stopColor="rgba(232,198,104,0)" />
                </radialGradient>
              </defs>

              <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                {Array.from({ length: 22 }).map((_, i) => (
                  <line
                    key={`v${i}`}
                    x1={i * 60}
                    y1="0"
                    x2={i * 60}
                    y2="640"
                    stroke="rgba(165,131,255,0.06)"
                    strokeWidth="1"
                  />
                ))}
                {Array.from({ length: 12 }).map((_, i) => (
                  <line
                    key={`h${i}`}
                    x1="0"
                    y1={i * 60}
                    x2="1320"
                    y2={i * 60}
                    stroke="rgba(165,131,255,0.06)"
                    strokeWidth="1"
                  />
                ))}

                {GRAPH_EDGES.map(([a, b], i) => {
                  const na = GRAPH_NODES.find((n) => n.id === a);
                  const nb = GRAPH_NODES.find((n) => n.id === b);
                  if (!na || !nb) return null;
                  const highlight = selected === a || selected === b;
                  return (
                    <line
                      key={i}
                      x1={na.x}
                      y1={na.y}
                      x2={nb.x}
                      y2={nb.y}
                      stroke={highlight ? "#e8c668" : "rgba(165,131,255,0.3)"}
                      strokeWidth={highlight ? 1.6 : 1}
                      style={{
                        filter: highlight ? "drop-shadow(0 0 4px #e8c668)" : "none",
                        transition: "all 200ms",
                      }}
                    />
                  );
                })}

                {GRAPH_NODES.map((n) => {
                  const color = DOMAIN_COLOR[n.domain];
                  const isSel = selected === n.id;
                  const isHover = hover === n.id;
                  return (
                    <g
                      key={n.id}
                      style={{ cursor: "pointer" }}
                      onMouseDown={(e) => e.stopPropagation()}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelected(n.id);
                      }}
                      onMouseEnter={() => setHover(n.id)}
                      onMouseLeave={() => setHover(null)}
                    >
                      {n.active && (
                        <circle cx={n.x} cy={n.y} r={n.r + 14} fill="url(#ring-active)">
                          <animate
                            attributeName="r"
                            values={`${n.r + 8};${n.r + 22};${n.r + 8}`}
                            dur="2.2s"
                            repeatCount="indefinite"
                          />
                        </circle>
                      )}
                      <circle cx={n.x} cy={n.y} r={n.r + 4} stroke="rgba(255,255,255,0.05)" strokeWidth="2" fill="none" />
                      <circle
                        cx={n.x}
                        cy={n.y}
                        r={n.r + 4}
                        stroke={color}
                        strokeWidth="2"
                        fill="none"
                        strokeDasharray={`${(n.mastery * 2 * Math.PI * (n.r + 4)).toFixed(1)} 9999`}
                        transform={`rotate(-90 ${n.x} ${n.y})`}
                        style={{ transition: "all 300ms" }}
                      />
                      <circle
                        cx={n.x}
                        cy={n.y}
                        r={n.r}
                        fill={isSel ? color : `${color}22`}
                        stroke={color}
                        strokeWidth={isSel ? 2 : 1.2}
                        filter={isSel || isHover || n.highlight ? "url(#glowf)" : undefined}
                        style={{ transition: "all 150ms" }}
                      />
                      <circle cx={n.x} cy={n.y} r={n.r * 0.35} fill={isSel ? "#05050a" : color} opacity={isSel ? 1 : 0.8} />
                      <text
                        x={n.x}
                        y={n.y + n.r + 14}
                        textAnchor="middle"
                        fill={isSel ? "#e8c668" : "rgba(228,224,255,0.85)"}
                        fontSize="10"
                        fontFamily="var(--font-mono)"
                        style={{ letterSpacing: "0.08em", textTransform: "uppercase", pointerEvents: "none" }}
                      >
                        {n.label}
                      </text>
                      <text
                        x={n.x}
                        y={n.y + 3}
                        textAnchor="middle"
                        fill={isSel ? "#0a0014" : "rgba(255,255,255,0.9)"}
                        fontSize="9"
                        fontWeight="600"
                        fontFamily="var(--font-mono)"
                        style={{ pointerEvents: "none" }}
                      >
                        {Math.round(n.mastery * 100)}
                      </text>
                    </g>
                  );
                })}
              </g>
            </svg>

            <div className="scan-bar absolute" />
          </div>

          {/* Side panel */}
          <div
            style={{
              width: 300,
              flex: "0 0 300px",
              borderLeft: "1px solid var(--line)",
              background: "rgba(0,0,0,0.35)",
              padding: 16,
              overflowY: "auto",
            }}
          >
            <div className="up ghost text-[9px] tracking-[0.22em] mb-2">› NODE INSPECT</div>
            {sel && (
              <>
                <div className="flex items-center gap-2 mb-3">
                  <span
                    style={{
                      width: 14,
                      height: 14,
                      background: DOMAIN_COLOR[sel.domain],
                      boxShadow: `0 0 8px ${DOMAIN_COLOR[sel.domain]}`,
                    }}
                  />
                  <span
                    className="font-display"
                    style={{ fontSize: 16, color: "var(--text)", letterSpacing: "0.02em" }}
                  >
                    {sel.label}
                  </span>
                </div>
                <div className="ghost mb-3.5" style={{ fontSize: 10, letterSpacing: "0.14em" }}>
                  ID · {sel.id.toUpperCase()} · DOMAIN · {sel.domain.toUpperCase()}
                </div>

                <div className="mb-3.5">
                  <div className="flex items-center text-[10px] mb-1">
                    <span className="up ghost">{t("skill_mastery")}</span>
                    <div className="flex-1" />
                    <span className="y">{Math.round(sel.mastery * 100)}%</span>
                  </div>
                  <div style={{ height: 6, background: "rgba(165,131,255,0.15)", position: "relative" }}>
                    <div
                      style={{
                        position: "absolute",
                        inset: 0,
                        right: "auto",
                        width: `${sel.mastery * 100}%`,
                        background: `linear-gradient(to right, ${DOMAIN_COLOR[sel.domain]}, var(--yellow))`,
                        boxShadow: `0 0 8px ${DOMAIN_COLOR[sel.domain]}`,
                      }}
                    />
                  </div>
                </div>

                <div
                  className="grid grid-cols-2 mb-4"
                  style={{ gap: 1, background: "var(--line-hi)", border: "1px solid var(--line-hi)" }}
                >
                  {[
                    ["BKT p(known)", (sel.mastery * 0.95).toFixed(2)],
                    ["DKT logit", ((sel.mastery - 0.5) * 4).toFixed(2)],
                    [t("skill_attempts"), sel.attempts],
                    ["last err.", lang === "ru" ? "3ч назад" : "3h ago"],
                  ].map(([k, v]) => (
                    <div key={k} style={{ background: "var(--surface-hi)", padding: "8px 10px" }}>
                      <div
                        className="ghost up"
                        style={{ fontSize: 9, letterSpacing: "0.14em" }}
                      >
                        {k}
                      </div>
                      <div style={{ fontSize: 14, color: "var(--text)", marginTop: 2 }}>{v}</div>
                    </div>
                  ))}
                </div>

                <div className="up ghost text-[9px] mb-1.5 tracking-[0.2em]">
                  › {t("learning_trace")}
                </div>
                <svg width="100%" height="60" viewBox="0 0 260 60" className="mb-3.5">
                  <polyline
                    fill="none"
                    stroke="var(--violet)"
                    strokeWidth="1.5"
                    points="0,45 22,42 44,40 66,36 88,32 110,35 132,28 154,24 176,26 198,20 220,15 242,12 260,14"
                    style={{ filter: "drop-shadow(0 0 3px var(--violet))" }}
                  />
                  <polyline
                    fill="none"
                    stroke="var(--yellow)"
                    strokeWidth="1"
                    strokeDasharray="3 3"
                    points="0,50 260,50"
                    opacity="0.4"
                  />
                </svg>

                <div className="up ghost text-[9px] mb-1.5 tracking-[0.2em]">› prerequisites</div>
                <div className="flex flex-col gap-1 mb-4">
                  {GRAPH_EDGES.filter((e) => e[1] === sel.id).map(([from], i) => {
                    const pre = GRAPH_NODES.find((n) => n.id === from);
                    if (!pre) return null;
                    return (
                      <button
                        key={i}
                        onClick={() => setSelected(pre.id)}
                        className="font-mono flex items-center gap-2 text-left"
                        style={{
                          padding: "6px 10px",
                          background: "rgba(165,131,255,0.06)",
                          border: "1px solid var(--line)",
                          color: "var(--text-dim)",
                          fontSize: 11,
                          cursor: "pointer",
                          borderRadius: 3,
                        }}
                      >
                        <span style={{ color: DOMAIN_COLOR[pre.domain] }}>↳</span>
                        <span>{pre.label}</span>
                        <div className="flex-1" />
                        <span className="y">{Math.round(pre.mastery * 100)}%</span>
                      </button>
                    );
                  })}
                </div>

                <button
                  className="cbtn cbtn-primary w-full justify-center"
                  onClick={() => startPractice(sel)}
                  disabled={practicing}
                >
                  {practicing
                    ? (lang === "ru" ? "СОЗДАНИЕ СЕССИИ…" : "CREATING SESSION…")
                    : "◆ " + (lang === "ru" ? "ПРАКТИКОВАТЬ" : "PRACTICE") + " →"}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
