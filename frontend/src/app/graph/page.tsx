"use client";

// MITS — Knowledge Graph screen (new_design "midnight" port).
//
// Faithfully reproduces new_design/pages.jsx → GraphPage (the SVG node graph):
//   HUD · edge-type legend · domain-coloured nodes with mastery rings & parallax ·
//   prerequisite-chain highlighting · mini-map · domain legend · node-inspect side panel.
//
// Data comes from the live Knowledge Forge backend (see ./graphData.ts) and falls
// back to the ported new_design sample graph so the screen always renders fully.

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { NewAppShell } from "@/components/newdesign/AppShell";
import { ThemeToggle } from "@/components/newdesign/ThemeToggle";
import { useChatStore } from "@/store/chatStore";
import { createKnowledgeNode, createSession } from "@/lib/api";
import type { Session } from "@/types/api";
import {
  DOMAIN_KEYS,
  FALLBACK_DATA,
  defaultSelected,
  fetchGraph,
  getDomColor,
  type EdgeKind,
  type GraphData,
  type GraphNode,
} from "./graphData";

// Locked to the midnight shell — colours resolve via the "dark" variant.
const THEME = "midnight";

// ── Local i18n (mirrors new_design graph strings; the app i18n lacks these keys) ──
type Lang = "ru" | "en";

const GRAPH_I18N: Record<Lang, Record<string, string>> = {
  ru: {
    graphTitle: "Граф знаний",
    graphSub: "Маппинг навыков · BKT + DKT · 5 доменов · 40+ концептов",
    graphInspect: "Узел · детали",
    graphMastery: "Освоение",
    graphAttempts: "Попыток",
    graphTrace: "След обучения",
    graphPrereq: "Предпосылки",
    graphPractice: "Практиковать",
    graphLastErr: "Посл. ошибка",
    graphBKT: "BKT p(known)",
    graphDKT: "DKT логит",
    graphNoData: "нет данных",
    graphSoon: "D2",
    graph3hAgo: "3ч назад",
    edgePrereq: "prerequisite",
    edgeRelated: "связано",
    edgeDerived: "производное",
    overview: "ОБЗОР",
    topic: "тема",
    creating: "Создание сессии…",
  },
  en: {
    graphTitle: "Knowledge graph",
    graphSub: "Skill mapping · BKT + DKT · 5 domains · 40+ concepts",
    graphInspect: "Node · inspect",
    graphMastery: "Mastery",
    graphAttempts: "Attempts",
    graphTrace: "Learning trace",
    graphPrereq: "Prerequisites",
    graphPractice: "Practice",
    graphLastErr: "Last error",
    graphBKT: "BKT p(known)",
    graphDKT: "DKT logit",
    graphNoData: "no data",
    graphSoon: "D2",
    graph3hAgo: "3h ago",
    edgePrereq: "prerequisite",
    edgeRelated: "related",
    edgeDerived: "derived",
    overview: "OVERVIEW",
    topic: "topic",
    creating: "Creating session…",
  },
};

/** Localized node label — prefer the Russian title when lang === ru. */
function nodeLabel(n: GraphNode, lang: Lang): string {
  if (lang === "ru" && n.labRu) return n.labRu;
  return n.lab;
}

// ── Shared head controls (lang toggle + theme toggle) — ported from new_design ──
function PageControls({ lang, setLang }: { lang: Lang; setLang: (l: Lang) => void }) {
  return (
    <>
      <div className="lang-toggle">
        <button className={lang === "ru" ? "active" : ""} onClick={() => setLang("ru")}>
          RU
        </button>
        <button className={lang === "en" ? "active" : ""} onClick={() => setLang("en")}>
          EN
        </button>
      </div>
      <ThemeToggle />
    </>
  );
}

// Edge-type style table — ported from new_design.
const EDGE_STYLE: Record<EdgeKind, { dash?: string; width: number; arrow: boolean; baseOpacity: number }> = {
  prereq: { dash: undefined, width: 1.4, arrow: true, baseOpacity: 0.55 },
  related: { dash: "5 4", width: 1.2, arrow: false, baseOpacity: 0.45 },
  derived: { dash: "1.5 4", width: 1.2, arrow: true, baseOpacity: 0.45 },
};

export default function GraphPage() {
  const router = useRouter();
  const addSession = useChatStore((s) => s.addSession);
  const setActiveSession = useChatStore((s) => s.setActiveSession);

  const [lang, setLang] = useState<Lang>("ru");
  const [data, setData] = useState<GraphData>(FALLBACK_DATA);
  const [selected, setSelected] = useState<string>("int");
  const [hover, setHover] = useState<string | null>(null);
  const [mouse, setMouse] = useState({ x: 0, y: 0 });
  const [practicing, setPracticing] = useState(false);
  // Which metric the node badges show — cycled by the top-bar button.
  const [metric, setMetric] = useState<"mastery" | "bkt" | "dkt">("mastery");
  // «+ тема»: add a node to the Knowledge Forge graph.
  const [addOpen, setAddOpen] = useState(false);
  const [addTitle, setAddTitle] = useState("");
  const [addDomain, setAddDomain] = useState("math");
  const [addType, setAddType] = useState("concept");
  const [addBusy, setAddBusy] = useState(false);

  const fieldStyle = {
    flex: 1,
    padding: "8px 10px",
    borderRadius: 8,
    background: "var(--bg)",
    border: "1px solid var(--line)",
    color: "var(--ink)",
    fontSize: 13,
  };

  const handleAddTopic = async () => {
    const title = addTitle.trim();
    if (!title || addBusy) return;
    setAddBusy(true);
    try {
      await createKnowledgeNode({ title, domain: addDomain, node_type: addType });
      setData(await fetchGraph());
      setAddTitle("");
      setAddOpen(false);
    } catch (e) {
      console.error("Failed to add topic:", e);
    } finally {
      setAddBusy(false);
    }
  };
  const svgRef = useRef<SVGSVGElement | null>(null);

  const tt = (k: string) => GRAPH_I18N[lang][k] ?? k;

  // Persisted language (matches the rest of the app).
  useEffect(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem("mits-lang") : null;
    if (saved === "ru" || saved === "en") setLang(saved);
  }, []);
  const changeLang = (l: Lang) => {
    setLang(l);
    if (typeof window !== "undefined") localStorage.setItem("mits-lang", l);
  };

  // Load the live graph; fall back to the static sample on any error/empty.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const g = await fetchGraph();
        if (!cancelled) {
          setData(g);
          setSelected(defaultSelected(g));
        }
      } catch {
        if (!cancelled) {
          setData(FALLBACK_DATA);
          setSelected(defaultSelected(FALLBACK_DATA));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const { nodes, edges, domains } = data;

  const sel = useMemo(() => nodes.find((n) => n.id === selected), [nodes, selected]);

  // Full prerequisite chain (BFS upstream) for path-highlighting.
  const chainSet = useMemo(() => {
    const set = new Set<string>([selected]);
    const queue = [selected];
    while (queue.length) {
      const cur = queue.shift()!;
      for (const e of edges) {
        if (e[1] === cur && !set.has(e[0])) {
          set.add(e[0]);
          queue.push(e[0]);
        }
      }
    }
    return set;
  }, [selected, edges]);

  const prereqs = useMemo(
    () =>
      edges
        .filter((e) => e[1] === selected)
        .map(([from]) => nodes.find((n) => n.id === from))
        .filter((n): n is GraphNode => Boolean(n)),
    [selected, edges, nodes],
  );

  // Mouse-parallax — weaker mastery drifts more (feels "further away").
  const handleMove = (e: React.MouseEvent) => {
    const r = e.currentTarget.getBoundingClientRect();
    setMouse({
      x: ((e.clientX - r.left) / r.width - 0.5) * 2,
      y: ((e.clientY - r.top) / r.height - 0.5) * 2,
    });
  };
  const handleLeave = () => setMouse({ x: 0, y: 0 });
  const parallaxFor = (n: GraphNode) => {
    const factor = (1 - n.m) * 6 + 1.5; // 1.5..7.5 px
    return { dx: mouse.x * factor, dy: mouse.y * factor };
  };

  // Start a guided-learning session on the selected concept.
  const startPractice = async (node: GraphNode | undefined) => {
    if (!node || practicing) return;
    setPracticing(true);
    try {
      const label = nodeLabel(node, lang);
      const customProblem =
        lang === "ru"
          ? `Давай поработаем над темой «${label}» (${node.d}). Покажи задачу на этот концепт.`
          : `Let's work on "${label}" (${node.d}). Show me a problem on this concept.`;
      const session = await createSession({
        topic: node.id,
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

  return (
    <NewAppShell>
      <main className="main">
        <div className="page">
          <div className="page-head">
            <div className="page-head-info">
              <h1>{tt("graphTitle")}</h1>
              <div className="page-sub">{tt("graphSub")}</div>
            </div>
            <PageControls lang={lang} setLang={changeLang} />
            <button
              className="btn-secondary"
              title="Переключить метрику узлов"
              onClick={() =>
                setMetric((m) => (m === "mastery" ? "bkt" : m === "bkt" ? "dkt" : "mastery"))
              }
            >
              {metric === "bkt"
                ? tt("graphBKT")
                : metric === "dkt"
                  ? tt("graphDKT")
                  : `${tt("graphMastery")} %`}
            </button>
            <button className="btn-primary" onClick={() => setAddOpen(true)}>
              + {tt("topic")}
            </button>
          </div>

          {addOpen && (
            <div
              onClick={() => !addBusy && setAddOpen(false)}
              style={{
                position: "fixed",
                inset: 0,
                zIndex: 50,
                background: "rgba(0,0,0,0.55)",
                display: "grid",
                placeItems: "center",
              }}
            >
              <div
                onClick={(e) => e.stopPropagation()}
                style={{
                  width: 380,
                  maxWidth: "92vw",
                  padding: 20,
                  borderRadius: 14,
                  background: "var(--bg-elev)",
                  border: "1px solid var(--line)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                  color: "var(--ink)",
                }}
              >
                <div style={{ fontSize: 15, fontWeight: 600 }}>
                  {lang === "ru" ? "Новая тема в граф" : "New graph topic"}
                </div>
                <input
                  autoFocus
                  value={addTitle}
                  onChange={(e) => setAddTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void handleAddTopic();
                  }}
                  placeholder={lang === "ru" ? "Название темы" : "Topic name"}
                  style={fieldStyle}
                />
                <div style={{ display: "flex", gap: 10 }}>
                  <select value={addDomain} onChange={(e) => setAddDomain(e.target.value)} style={fieldStyle}>
                    <option value="math">math</option>
                    <option value="physics">physics</option>
                    <option value="chemistry">chemistry</option>
                    <option value="biology">biology</option>
                    <option value="cs">cs</option>
                  </select>
                  <select value={addType} onChange={(e) => setAddType(e.target.value)} style={fieldStyle}>
                    <option value="concept">concept</option>
                    <option value="formula">formula</option>
                    <option value="theorem">theorem</option>
                    <option value="method">method</option>
                    <option value="example">example</option>
                    <option value="misconception">misconception</option>
                  </select>
                </div>
                <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 4 }}>
                  <button className="btn-secondary" onClick={() => setAddOpen(false)} disabled={addBusy}>
                    {lang === "ru" ? "Отмена" : "Cancel"}
                  </button>
                  <button
                    className="btn-primary"
                    onClick={() => void handleAddTopic()}
                    disabled={addBusy || !addTitle.trim()}
                  >
                    {addBusy ? "…" : lang === "ru" ? "Добавить" : "Add"}
                  </button>
                </div>
              </div>
            </div>
          )}

          <div className="page-body" style={{ padding: 0, overflow: "hidden" }}>
            <div className="graph-wrap">
              <div className="graph-canvas" onMouseMove={handleMove} onMouseLeave={handleLeave}>
                <div className="graph-hud">
                  <div>
                    NODES · <span>{nodes.length}</span>
                  </div>
                  <div>
                    EDGES · <span>{edges.length}</span>
                  </div>
                  <div>
                    DOMAINS · <span>{domains.length}</span>
                  </div>
                </div>

                {/* Edge type legend */}
                <div className="graph-edge-legend">
                  <span className="el-item">
                    <svg width="22" height="6">
                      <line x1="1" y1="3" x2="21" y2="3" stroke="currentColor" strokeWidth="1.4" />
                      <path d="M16,1 L21,3 L16,5 z" fill="currentColor" />
                    </svg>{" "}
                    {tt("edgePrereq")}
                  </span>
                  <span className="el-item">
                    <svg width="22" height="6">
                      <line x1="1" y1="3" x2="21" y2="3" stroke="currentColor" strokeWidth="1.2" strokeDasharray="5 4" />
                    </svg>{" "}
                    {tt("edgeRelated")}
                  </span>
                  <span className="el-item">
                    <svg width="22" height="6">
                      <line x1="1" y1="3" x2="17" y2="3" stroke="currentColor" strokeWidth="1.2" strokeDasharray="1.5 4" />
                      <path d="M14,1 L19,3 L14,5 z" fill="currentColor" />
                    </svg>{" "}
                    {tt("edgeDerived")}
                  </span>
                </div>

                <svg ref={svgRef} width="100%" height="100%" viewBox="0 0 1080 640" style={{ display: "block" }}>
                  <defs>
                    <filter id="gf" x="-50%" y="-50%" width="200%" height="200%">
                      <feGaussianBlur stdDeviation="3" result="b" />
                      <feMerge>
                        <feMergeNode in="b" />
                        <feMergeNode in="SourceGraphic" />
                      </feMerge>
                    </filter>
                    <filter id="ge" x="-50%" y="-50%" width="200%" height="200%">
                      <feGaussianBlur stdDeviation="1.4" result="b" />
                      <feMerge>
                        <feMergeNode in="b" />
                        <feMergeNode in="SourceGraphic" />
                      </feMerge>
                    </filter>
                    {DOMAIN_KEYS.map((d) => {
                      const c = getDomColor(d, THEME);
                      return (
                        <marker
                          key={d}
                          id={`arr-${d}`}
                          viewBox="0 0 10 10"
                          refX="9"
                          refY="5"
                          markerWidth="5"
                          markerHeight="5"
                          orient="auto-start-reverse"
                        >
                          <path d="M0,0 L10,5 L0,10 z" fill={c} />
                        </marker>
                      );
                    })}
                    <marker
                      id="arr-accent"
                      viewBox="0 0 10 10"
                      refX="9"
                      refY="5"
                      markerWidth="5.5"
                      markerHeight="5.5"
                      orient="auto-start-reverse"
                    >
                      <path d="M0,0 L10,5 L0,10 z" fill="var(--accent)" />
                    </marker>
                  </defs>

                  {/* Edges */}
                  {edges.map((e, i) => {
                    const [a, b] = e;
                    const type = (e[2] || "prereq") as EdgeKind;
                    const st = EDGE_STYLE[type];
                    const na = nodes.find((n) => n.id === a);
                    const nb = nodes.find((n) => n.id === b);
                    if (!na || !nb) return null;
                    const inChain = chainSet.has(a) && chainSet.has(b);
                    const adj = selected === a || selected === b;
                    const dim = !inChain && !adj;
                    const hi = inChain || adj;
                    const pa = parallaxFor(na);
                    const pb = parallaxFor(nb);

                    // Shorten line so the arrow doesn't sit on top of the node.
                    const dx = nb.x + pb.dx - (na.x + pa.dx);
                    const dy = nb.y + pb.dy - (na.y + pa.dy);
                    const len = Math.hypot(dx, dy) || 1;
                    const ux = dx / len;
                    const uy = dy / len;
                    const x1 = na.x + pa.dx + ux * (na.r + 4);
                    const y1 = na.y + pa.dy + uy * (na.r + 4);
                    const x2 = nb.x + pb.dx - ux * (nb.r + 6);
                    const y2 = nb.y + pb.dy - uy * (nb.r + 6);

                    const edgeColor = hi ? "var(--accent)" : getDomColor(na.d, THEME);

                    return (
                      <g key={i} style={{ transition: "opacity .25s var(--ease-spring, ease-out)" }} opacity={dim ? 0.15 : 1}>
                        {/* halo */}
                        <line
                          x1={x1}
                          y1={y1}
                          x2={x2}
                          y2={y2}
                          stroke={edgeColor}
                          strokeWidth={hi ? 6 : 3.5}
                          strokeLinecap="round"
                          opacity={hi ? 0.45 : 0.18}
                          filter="url(#ge)"
                          strokeDasharray={st.dash}
                          style={{ transition: "all .25s var(--ease-spring, ease-out)" }}
                        />
                        {/* core */}
                        <line
                          x1={x1}
                          y1={y1}
                          x2={x2}
                          y2={y2}
                          stroke={edgeColor}
                          strokeWidth={hi ? 1.9 : st.width}
                          strokeLinecap="round"
                          strokeDasharray={st.dash}
                          opacity={hi ? 1 : st.baseOpacity + 0.25}
                          markerEnd={st.arrow ? (hi ? "url(#arr-accent)" : `url(#arr-${na.d})`) : undefined}
                          style={{ transition: "all .25s var(--ease-spring, ease-out)" }}
                        />
                      </g>
                    );
                  })}

                  {/* Nodes */}
                  {nodes.map((n) => {
                    const c = getDomColor(n.d, THEME);
                    const isSel = selected === n.id;
                    const isHv = hover === n.id;
                    const inChain = chainSet.has(n.id);
                    const dim = !inChain;
                    const p = parallaxFor(n);
                    const cx = n.x + p.dx;
                    const cy = n.y + p.dy;
                    return (
                      <g
                        key={n.id}
                        style={{ cursor: "pointer", transition: "opacity .25s var(--ease-spring, ease-out)" }}
                        opacity={dim ? 0.32 : 1}
                        onClick={() => setSelected(n.id)}
                        onMouseEnter={() => setHover(n.id)}
                        onMouseLeave={() => setHover(null)}
                      >
                        {n.active && (
                          <circle cx={cx} cy={cy} r={n.r + 14} fill="none" stroke={c} strokeWidth="1" opacity="0.4">
                            <animate attributeName="r" values={`${n.r + 8};${n.r + 22};${n.r + 8}`} dur="2.4s" repeatCount="indefinite" />
                            <animate attributeName="opacity" values="0.4;0;0.4" dur="2.4s" repeatCount="indefinite" />
                          </circle>
                        )}
                        {/* Mastery ring */}
                        <circle
                          cx={cx}
                          cy={cy}
                          r={n.r + 4}
                          stroke={c}
                          strokeWidth="2"
                          fill="none"
                          strokeDasharray={`${(n.hasMastery === false ? 0 : n.m * 2 * Math.PI * (n.r + 4)).toFixed(1)} 9999`}
                          transform={`rotate(-90 ${cx} ${cy})`}
                          opacity={isSel ? 1 : 0.85}
                        />
                        <circle cx={cx} cy={cy} r={n.r + 4} stroke={c} strokeWidth="2" fill="none" opacity="0.1" />
                        {/* Node body */}
                        <circle
                          cx={cx}
                          cy={cy}
                          r={n.r}
                          fill={isSel ? c : THEME === "midnight" ? c + "44" : c + "1A"}
                          stroke={c}
                          strokeWidth={isSel ? 0 : 1.2}
                          filter={isSel || isHv || n.highlight ? "url(#gf)" : undefined}
                          style={{ transition: "all .25s var(--ease-spring, ease-out)" }}
                        />
                        <text
                          x={cx}
                          y={cy + 3}
                          textAnchor="middle"
                          fontFamily="JetBrains Mono"
                          fontSize="11"
                          fontWeight="600"
                          fill={isSel ? (THEME === "midnight" ? "#0a0518" : "#fff") : c}
                          style={{ pointerEvents: "none" }}
                        >
                          {n.hasMastery === false
                            ? "—"
                            : metric === "bkt"
                              ? n.m.toFixed(2)
                              : metric === "dkt"
                                ? tt("graphSoon")
                                : Math.round(n.m * 100)}
                        </text>
                        {(() => {
                          const focused = isSel || isHv || n.highlight || n.active;
                          return (
                            <text
                              x={cx}
                              y={cy + n.r + 13}
                              textAnchor="middle"
                              fontFamily="JetBrains Mono"
                              fontSize={focused ? 10.5 : 9.5}
                              fill={isSel ? c : "currentColor"}
                              opacity={focused ? 1 : 0.82}
                              style={{
                                letterSpacing: "0.01em",
                                pointerEvents: "none",
                                color: focused ? "var(--ink)" : "var(--ink-soft)",
                                fontWeight: focused ? 700 : 500,
                                paintOrder: "stroke",
                                stroke: "var(--bg)",
                                strokeWidth: focused ? 3 : 2.5,
                              }}
                            >
                              {nodeLabel(n, lang)}
                            </text>
                          );
                        })()}
                      </g>
                    );
                  })}
                </svg>

                {/* Mini-map (overview navigator) */}
                <div className="graph-minimap">
                  <div className="mm-label">{tt("overview")}</div>
                  <svg viewBox="0 0 1080 640" preserveAspectRatio="xMidYMid meet" width="100%" height="76">
                    {edges.map((e, i) => {
                      const na = nodes.find((n) => n.id === e[0]);
                      const nb = nodes.find((n) => n.id === e[1]);
                      if (!na || !nb) return null;
                      const onChain = chainSet.has(na.id) && chainSet.has(nb.id);
                      return (
                        <line
                          key={i}
                          x1={na.x}
                          y1={na.y}
                          x2={nb.x}
                          y2={nb.y}
                          stroke={onChain ? "var(--accent)" : "currentColor"}
                          strokeWidth={onChain ? "4" : "2.5"}
                          opacity={onChain ? 0.9 : 0.18}
                        />
                      );
                    })}
                    {nodes.map((n) => (
                      <circle
                        key={n.id}
                        cx={n.x}
                        cy={n.y}
                        r={selected === n.id ? 18 : chainSet.has(n.id) ? 13 : 9}
                        fill={getDomColor(n.d, THEME)}
                        opacity={chainSet.has(n.id) ? 1 : 0.45}
                        style={{ cursor: "pointer" }}
                        onClick={() => setSelected(n.id)}
                      />
                    ))}
                  </svg>
                </div>

                <div className="graph-legend">
                  {DOMAIN_KEYS.map((d) => (
                    <div className="lg-item" key={d}>
                      <span className="lg-dot" style={{ background: getDomColor(d, THEME), color: getDomColor(d, THEME) }} />
                      {d}
                    </div>
                  ))}
                </div>
              </div>

              <div className="graph-side">
                <div className="gs-head">{tt("graphInspect")}</div>
                {sel && (
                  <>
                    <h2 className="gs-title" style={{ color: getDomColor(sel.d, THEME) }}>
                      <span className="dot" style={{ background: getDomColor(sel.d, THEME), color: getDomColor(sel.d, THEME) }} />
                      {nodeLabel(sel, lang)}
                    </h2>
                    <div className="gs-id">
                      {sel.id} · {sel.d}
                    </div>

                    <div className="gs-mastery-row">
                      <span style={{ color: "var(--ink-mute)" }}>{tt("graphMastery")}</span>
                      <span style={{ color: "var(--ink)", fontWeight: 500, fontVariantNumeric: "tabular-nums" }}>
                        {Math.round((sel.hasMastery === false ? 0 : sel.m) * 100)}%
                      </span>
                    </div>
                    <div className="gs-bar">
                      <div className="gs-bar-fill" style={{ width: (sel.hasMastery === false ? 0 : sel.m) * 100 + "%" }} />
                    </div>

                    <div className="gs-mini-stats">
                      <div className="gs-mini">
                        <div className="k">{tt("graphBKT")}</div>
                        <div className="v">{sel.hasMastery === false ? tt("graphNoData") : sel.m.toFixed(2)}</div>
                      </div>
                      <div className="gs-mini">
                        <div className="k">{tt("graphDKT")}</div>
                        <div className="v">{tt("graphSoon")}</div>
                      </div>
                      <div className="gs-mini">
                        <div className="k">{tt("graphAttempts")}</div>
                        <div className="v">{sel.att}</div>
                      </div>
                      <div className="gs-mini">
                        <div className="k">{tt("graphLastErr")}</div>
                        <div className="v">{tt("graph3hAgo")}</div>
                      </div>
                    </div>

                    <div className="gs-head" style={{ marginTop: 4, marginBottom: 10 }}>
                      {tt("graphTrace")}
                    </div>
                    <svg width="100%" height="60" viewBox="0 0 260 60" style={{ marginBottom: 14 }}>
                      <polyline
                        fill="none"
                        stroke="var(--accent)"
                        strokeWidth="1.5"
                        points="0,45 22,42 44,40 66,36 88,32 110,35 132,28 154,24 176,26 198,20 220,15 242,12 260,14"
                        style={{ filter: "drop-shadow(0 0 4px var(--accent))" }}
                      />
                      <polyline
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1"
                        strokeDasharray="3 3"
                        points="0,50 260,50"
                        opacity="0.3"
                        style={{ color: "var(--ink-mute)" }}
                      />
                    </svg>

                    <div className="gs-head" style={{ marginTop: 4, marginBottom: 10 }}>
                      {tt("graphPrereq")}
                    </div>
                    <div style={{ marginBottom: 14 }}>
                      {prereqs.map((p, i) => (
                        <div
                          key={i}
                          className="gs-prereq"
                          onClick={() => setSelected(p.id)}
                          style={{ ["--dom" as string]: getDomColor(p.d, THEME) }}
                        >
                          <span className="arrow" style={{ color: getDomColor(p.d, THEME) }}>
                            ↳
                          </span>
                          <span style={{ flex: 1, color: "var(--ink)" }}>{nodeLabel(p, lang)}</span>
                          <span style={{ color: "var(--accent)" }}>{Math.round(p.m * 100)}%</span>
                        </div>
                      ))}
                    </div>

                    <button
                      className="btn-primary"
                      style={{ width: "100%", justifyContent: "center" }}
                      onClick={() => startPractice(sel)}
                      disabled={practicing}
                    >
                      {practicing ? tt("creating") : `${tt("graphPractice")} →`}
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </NewAppShell>
  );
}
