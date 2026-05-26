// MITS — Page components for Tasks / Graph / Dashboard / Profile / Sources / Settings

const { useState: usePg, useMemo: useMemoPg } = React;
const { DOMAIN_COLOR: DC, TASKS_DATA, GRAPH_NODES, GRAPH_EDGES, RECENT, SOURCES_LIST, PIPELINE_STEPS } = window.MITS_DATA;

// Get domain color appropriate for current theme
function getDomColor(d, theme) {
  if (!DC[d]) return "var(--accent)";
  return theme === "midnight" ? DC[d].dark : DC[d].light;
}

// Localized graph node label
function nodeLabel(n, lang) {
  if (lang === "en") return n.lab;
  const ru = {
    "Arithmetic": "Арифметика", "Algebra": "Алгебра", "Linear Alg": "Линал",
    "Calculus": "Анализ", "Integrals": "Интегралы", "Derivatives": "Производные",
    "Geometry": "Геометрия", "Probability": "Теорвер",
    "Mechanics": "Механика", "Thermo": "Термо", "EM Fields": "ЭМ поля",
    "Chemistry": "Химия", "Organic": "Органика",
    "CS Basics": "CS основы", "DS & Algo": "DS & Algo", "DP": "DP",
    "Biology": "Биология", "Genetics": "Генетика",
  };
  return ru[n.lab] || n.lab;
}

// Shared controls (lang toggle + theme toggle) for non-chat page heads
function PageControls({ lang, setLang, mode, setMode }) {
  return (
    <>
      <div className="lang-toggle">
        <button className={lang === "ru" ? "active" : ""} onClick={() => setLang("ru")}>RU</button>
        <button className={lang === "en" ? "active" : ""} onClick={() => setLang("en")}>EN</button>
      </div>
      <button className="theme-toggle" onClick={() => setMode(mode === "light" ? "dark" : "light")} title="Toggle theme">
        {mode === "light"
          ? <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M6.5 1a7 7 0 1 0 8.5 8.5A6 6 0 0 1 6.5 1Z"/></svg>
          : <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="8" r="3"/><path strokeLinecap="round" d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.5 1.5M11.5 11.5 13 13M3 13l1.5-1.5M11.5 4.5 13 3"/></svg>}
      </button>
    </>
  );
}

// ---------- Tasks page ----------
function TasksPage({ t, lang, themeName, setLang, mode, setMode }) {
  const tasks = TASKS_DATA[lang];
  return (
    <div className="page">
      <div className="page-head">
        <div className="page-head-info">
          <h1>{t.tasksTitle}</h1>
          <div className="page-sub">{t.tasksSub}</div>
        </div>
        <PageControls lang={lang} setLang={setLang} mode={mode} setMode={setMode}/>
        <button className="btn-secondary">⌘F · {lang === "ru" ? "Фильтр" : "Filter"}</button>
        <button className="btn-primary">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M8 1v6m-3-3 3-3 3 3M2 14h12"/></svg>
          {t.tasksGenerate}
        </button>
      </div>
      <div className="page-body">
        <div className="insight-banner">
          <span className="ib-mark">▷</span>
          <span className="ib-text">
            {lang === "ru"
              ? "Эти задачи подобраны под слабые места в графе. Решите 3 — обновлю траекторию обучения."
              : "These tasks target your weak spots in the graph. Solve 3 — I'll re-plan the trajectory."}
          </span>
          <span className="ib-meta">3 / 8</span>
        </div>
        <div className="tasks-list">
          {tasks.map((tk, i) => (
            <div key={i} className="task-row" style={{ "--dom": getDomColor(tk.d, themeName), "--dom-tint": getDomColor(tk.d, themeName) + "10" }}>
              <span className="dom-pill">{tk.d}</span>
              <span className={"diff-chip " + tk.diff}>{t["difficulty_" + tk.diff]}</span>
              <span className="task-text">{tk.t}</span>
              <div style={{ display: "flex", gap: 4 }}>
                {tk.tags.map(tag => <span key={tag} className="tag-chip">{tag}</span>)}
              </div>
              <span className="task-rate">
                <svg viewBox="0 0 12 12" width="11" height="11" fill="currentColor" style={{ color: "#FFB85C" }}><path d="m6 .5 1.6 3.4 3.7.4-2.8 2.6.8 3.7L6 8.8l-3.3 1.8.8-3.7L.7 4.3l3.7-.4L6 .5z"/></svg>
                {Math.round(tk.rate * 100)}%
              </span>
              <span className="task-arrow">›</span>
            </div>
          ))}
          {/* Skeleton: lazy-loading more — modern shimmer */}
          {[0, 1].map(i => (
            <div key={"sk-" + i} className="task-row task-row-skeleton">
              <span className="skeleton" style={{ width: 50, height: 18, borderRadius: 999 }}/>
              <span className="skeleton" style={{ width: 70, height: 18, borderRadius: 999 }}/>
              <span className="skeleton" style={{ flex: 1, height: 16, borderRadius: 4 }}/>
              <span className="skeleton" style={{ width: 60, height: 16, borderRadius: 999 }}/>
              <span className="skeleton" style={{ width: 38, height: 14, borderRadius: 4 }}/>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------- Graph page ----------
function GraphPage({ t, lang, themeName, setLang, mode, setMode, focusNodeId }) {
  const [selected, setSelected] = usePg(focusNodeId || "int");
  const [hover, setHover] = usePg(null);
  const [mouse, setMouse] = usePg({ x: 0, y: 0 });
  const svgRef = React.useRef(null);

  // Honour external focus from the command palette
  React.useEffect(() => {
    if (focusNodeId) setSelected(focusNodeId);
  }, [focusNodeId]);

  const sel = useMemoPg(() => GRAPH_NODES.find(n => n.id === selected), [selected]);

  // Full prerequisite chain (BFS upstream) for path-highlighting on hover/select
  const chainSet = useMemoPg(() => {
    const set = new Set([selected]);
    const queue = [selected];
    while (queue.length) {
      const cur = queue.shift();
      for (const e of GRAPH_EDGES) {
        if (e[1] === cur && !set.has(e[0])) {
          set.add(e[0]); queue.push(e[0]);
        }
      }
    }
    return set;
  }, [selected]);

  const prereqs = useMemoPg(
    () => GRAPH_EDGES.filter(e => e[1] === selected).map(([from]) => GRAPH_NODES.find(n => n.id === from)).filter(Boolean),
    [selected]
  );

  // Mouse-parallax — weaker mastery moves more (feels "further away")
  const handleMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    setMouse({
      x: ((e.clientX - r.left) / r.width  - 0.5) * 2,
      y: ((e.clientY - r.top)  / r.height - 0.5) * 2,
    });
  };
  const handleLeave = () => setMouse({ x: 0, y: 0 });

  const parallaxFor = (n) => {
    const factor = (1 - n.m) * 6 + 1.5; // 1.5..7.5 px range
    return { dx: mouse.x * factor, dy: mouse.y * factor };
  };

  // Edge type styles
  const edgeStyle = {
    prereq:  { dash: undefined,    width: 1.4, arrow: true,  baseOpacity: 0.55 },
    related: { dash: "5 4",        width: 1.2, arrow: false, baseOpacity: 0.45 },
    derived: { dash: "1.5 4",      width: 1.2, arrow: true,  baseOpacity: 0.45 },
  };

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-head-info">
          <h1>{t.graphTitle}</h1>
          <div className="page-sub">{t.graphSub}</div>
        </div>
        <PageControls lang={lang} setLang={setLang} mode={mode} setMode={setMode}/>
        <button className="btn-secondary">{t.graphBKT} · {t.graphDKT}</button>
        <button className="btn-primary">+ {lang === "ru" ? "тема" : "topic"}</button>
      </div>
      <div className="page-body" style={{ padding: 0, overflow: "hidden" }}>
        <div className="graph-wrap">
          <div className="graph-canvas" onMouseMove={handleMove} onMouseLeave={handleLeave}>
            <div className="graph-hud">
              <div>NODES · <span>{GRAPH_NODES.length}</span></div>
              <div>EDGES · <span>{GRAPH_EDGES.length}</span></div>
              <div>DOMAINS · <span>5</span></div>
            </div>

            {/* Edge type legend */}
            <div className="graph-edge-legend">
              <span className="el-item"><svg width="22" height="6"><line x1="1" y1="3" x2="21" y2="3" stroke="currentColor" strokeWidth="1.4"/><path d="M16,1 L21,3 L16,5 z" fill="currentColor"/></svg> {lang === "ru" ? "prerequisite" : "prerequisite"}</span>
              <span className="el-item"><svg width="22" height="6"><line x1="1" y1="3" x2="21" y2="3" stroke="currentColor" strokeWidth="1.2" strokeDasharray="5 4"/></svg> {lang === "ru" ? "связано" : "related"}</span>
              <span className="el-item"><svg width="22" height="6"><line x1="1" y1="3" x2="17" y2="3" stroke="currentColor" strokeWidth="1.2" strokeDasharray="1.5 4"/><path d="M14,1 L19,3 L14,5 z" fill="currentColor"/></svg> {lang === "ru" ? "производное" : "derived"}</span>
            </div>

            <svg ref={svgRef} width="100%" height="100%" viewBox="0 0 1080 640" style={{ display: "block" }}>
              <defs>
                <filter id="gf" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="3" result="b"/>
                  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
                </filter>
                <filter id="ge" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="1.4" result="b"/>
                  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
                </filter>
                {Object.keys(DC).map(d => {
                  const c = getDomColor(d, themeName);
                  return (
                    <marker key={d} id={`arr-${d}`} viewBox="0 0 10 10" refX="9" refY="5"
                      markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                      <path d="M0,0 L10,5 L0,10 z" fill={c}/>
                    </marker>
                  );
                })}
                <marker id="arr-accent" viewBox="0 0 10 10" refX="9" refY="5"
                  markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse">
                  <path d="M0,0 L10,5 L0,10 z" fill="var(--accent)"/>
                </marker>
              </defs>

              {/* Edges */}
              {GRAPH_EDGES.map((e, i) => {
                const [a, b] = e;
                const type = e[2] || "prereq";
                const st = edgeStyle[type];
                const na = GRAPH_NODES.find(n => n.id === a);
                const nb = GRAPH_NODES.find(n => n.id === b);
                if (!na || !nb) return null;
                const inChain = chainSet.has(a) && chainSet.has(b);
                const adj = selected === a || selected === b;
                const dim = !inChain && !adj;
                const hi = inChain || adj;
                const pa = parallaxFor(na);
                const pb = parallaxFor(nb);

                // Shorten line so arrow doesn't sit on top of node
                const dx = (nb.x + pb.dx) - (na.x + pa.dx);
                const dy = (nb.y + pb.dy) - (na.y + pa.dy);
                const len = Math.hypot(dx, dy) || 1;
                const ux = dx / len, uy = dy / len;
                const x1 = na.x + pa.dx + ux * (na.r + 4);
                const y1 = na.y + pa.dy + uy * (na.r + 4);
                const x2 = nb.x + pb.dx - ux * (nb.r + 6);
                const y2 = nb.y + pb.dy - uy * (nb.r + 6);

                const edgeColor = hi ? "var(--accent)" : getDomColor(na.d, themeName);

                return (
                  <g key={i} style={{ transition: "opacity .25s var(--ease-spring, ease-out)" }}
                     opacity={dim ? 0.15 : 1}>
                    {/* halo */}
                    <line x1={x1} y1={y1} x2={x2} y2={y2}
                      stroke={edgeColor}
                      strokeWidth={hi ? 6 : 3.5}
                      strokeLinecap="round"
                      opacity={hi ? 0.45 : 0.18}
                      filter="url(#ge)"
                      strokeDasharray={st.dash}
                      style={{ transition: "all .25s var(--ease-spring, ease-out)" }}/>
                    {/* core */}
                    <line x1={x1} y1={y1} x2={x2} y2={y2}
                      stroke={edgeColor}
                      strokeWidth={hi ? 1.9 : st.width}
                      strokeLinecap="round"
                      strokeDasharray={st.dash}
                      opacity={hi ? 1 : st.baseOpacity + 0.25}
                      markerEnd={st.arrow ? (hi ? "url(#arr-accent)" : `url(#arr-${na.d})`) : undefined}
                      style={{ transition: "all .25s var(--ease-spring, ease-out)" }}/>
                  </g>
                );
              })}

              {/* Nodes */}
              {GRAPH_NODES.map(n => {
                const c = getDomColor(n.d, themeName);
                const isSel = selected === n.id;
                const isHv  = hover === n.id;
                const inChain = chainSet.has(n.id);
                const dim = !inChain;
                const p = parallaxFor(n);
                const cx = n.x + p.dx, cy = n.y + p.dy;
                return (
                  <g key={n.id}
                    style={{ cursor: "pointer", transition: "opacity .25s var(--ease-spring, ease-out)" }}
                    opacity={dim ? 0.32 : 1}
                    onClick={() => setSelected(n.id)}
                    onMouseEnter={() => setHover(n.id)}
                    onMouseLeave={() => setHover(null)}>
                    {n.active && (
                      <circle cx={cx} cy={cy} r={n.r + 14} fill="none" stroke={c} strokeWidth="1" opacity="0.4">
                        <animate attributeName="r" values={`${n.r + 8};${n.r + 22};${n.r + 8}`} dur="2.4s" repeatCount="indefinite"/>
                        <animate attributeName="opacity" values="0.4;0;0.4" dur="2.4s" repeatCount="indefinite"/>
                      </circle>
                    )}
                    {/* Mastery ring */}
                    <circle cx={cx} cy={cy} r={n.r + 4}
                      stroke={c} strokeWidth="2" fill="none"
                      strokeDasharray={`${(n.m * 2 * Math.PI * (n.r + 4)).toFixed(1)} 9999`}
                      transform={`rotate(-90 ${cx} ${cy})`}
                      opacity={isSel ? 1 : 0.85}/>
                    <circle cx={cx} cy={cy} r={n.r + 4}
                      stroke={c} strokeWidth="2" fill="none"
                      opacity="0.1"/>
                    {/* Node body */}
                    <circle cx={cx} cy={cy} r={n.r}
                      fill={isSel ? c : (themeName === "midnight" ? c + "44" : c + "1A")}
                      stroke={c} strokeWidth={isSel ? 0 : 1.2}
                      filter={isSel || isHv || n.highlight ? "url(#gf)" : undefined}
                      style={{ transition: "all .25s var(--ease-spring, ease-out)" }}/>
                    <text x={cx} y={cy + 3}
                      textAnchor="middle"
                      fontFamily="JetBrains Mono"
                      fontSize="11" fontWeight="600"
                      fill={isSel ? (themeName === "midnight" ? "#0a0518" : "#fff") : c}
                      style={{ pointerEvents: "none" }}>
                      {Math.round(n.m * 100)}
                    </text>
                    <text x={cx} y={cy + n.r + 14}
                      textAnchor="middle"
                      fontFamily="JetBrains Mono"
                      fontSize="10"
                      fill={isSel ? c : "currentColor"}
                      style={{
                        letterSpacing: "0.06em",
                        textTransform: "uppercase",
                        pointerEvents: "none",
                        color: "var(--ink-soft)",
                        fontWeight: isSel ? 700 : 500
                      }}>
                      {nodeLabel(n, lang)}
                    </text>
                  </g>
                );
              })}
            </svg>

            {/* Mini-map (overview navigator) */}
            <div className="graph-minimap">
              <div className="mm-label">{lang === "ru" ? "ОБЗОР" : "OVERVIEW"}</div>
              <svg viewBox="0 0 1080 640" preserveAspectRatio="xMidYMid meet" width="100%" height="76">
                {GRAPH_EDGES.map((e, i) => {
                  const na = GRAPH_NODES.find(n => n.id === e[0]);
                  const nb = GRAPH_NODES.find(n => n.id === e[1]);
                  if (!na || !nb) return null;
                  return (
                    <line key={i} x1={na.x} y1={na.y} x2={nb.x} y2={nb.y}
                      stroke={chainSet.has(na.id) && chainSet.has(nb.id) ? "var(--accent)" : "currentColor"}
                      strokeWidth={chainSet.has(na.id) && chainSet.has(nb.id) ? "4" : "2.5"}
                      opacity={chainSet.has(na.id) && chainSet.has(nb.id) ? 0.9 : 0.18}/>
                  );
                })}
                {GRAPH_NODES.map(n => (
                  <circle key={n.id} cx={n.x} cy={n.y}
                    r={selected === n.id ? 18 : (chainSet.has(n.id) ? 13 : 9)}
                    fill={getDomColor(n.d, themeName)}
                    opacity={chainSet.has(n.id) ? 1 : 0.45}
                    style={{ cursor: "pointer" }}
                    onClick={() => setSelected(n.id)}/>
                ))}
              </svg>
            </div>

            <div className="graph-legend">
              {Object.keys(DC).map(d => (
                <div className="lg-item" key={d}>
                  <span className="lg-dot" style={{ background: getDomColor(d, themeName), color: getDomColor(d, themeName) }}/>
                  {d}
                </div>
              ))}
            </div>
          </div>

          <div className="graph-side">
            <div className="gs-head">{t.graphInspect}</div>
            {sel && (
              <>
                <h2 className="gs-title" style={{ color: getDomColor(sel.d, themeName) }}>
                  <span className="dot" style={{ background: getDomColor(sel.d, themeName), color: getDomColor(sel.d, themeName) }}/>
                  {nodeLabel(sel, lang)}
                </h2>
                <div className="gs-id">{sel.id} · {sel.d}</div>

                <div className="gs-mastery-row">
                  <span style={{ color: "var(--ink-mute)" }}>{t.graphMastery}</span>
                  <span style={{ color: "var(--ink)", fontWeight: 500, fontVariantNumeric: "tabular-nums" }}>{Math.round(sel.m * 100)}%</span>
                </div>
                <div className="gs-bar"><div className="gs-bar-fill" style={{ width: (sel.m * 100) + "%" }}/></div>

                <div className="gs-mini-stats">
                  <div className="gs-mini"><div className="k">{t.graphBKT}</div><div className="v">{(sel.m * 0.95).toFixed(2)}</div></div>
                  <div className="gs-mini"><div className="k">{t.graphDKT}</div><div className="v">{((sel.m - 0.5) * 4).toFixed(2)}</div></div>
                  <div className="gs-mini"><div className="k">{t.graphAttempts}</div><div className="v">{sel.att}</div></div>
                  <div className="gs-mini"><div className="k">{t.graphLastErr}</div><div className="v">{t.graph3hAgo}</div></div>
                </div>

                <div className="gs-head" style={{ marginTop: 4, marginBottom: 10 }}>{t.graphTrace}</div>
                <svg width="100%" height="60" viewBox="0 0 260 60" style={{ marginBottom: 14 }}>
                  <polyline fill="none" stroke="var(--accent)" strokeWidth="1.5"
                    points="0,45 22,42 44,40 66,36 88,32 110,35 132,28 154,24 176,26 198,20 220,15 242,12 260,14"
                    style={{ filter: "drop-shadow(0 0 4px var(--accent))" }}/>
                  <polyline fill="none" stroke="currentColor" strokeWidth="1" strokeDasharray="3 3"
                    points="0,50 260,50" opacity="0.3" style={{ color: "var(--ink-mute)" }}/>
                </svg>

                <div className="gs-head" style={{ marginTop: 4, marginBottom: 10 }}>{t.graphPrereq}</div>
                <div style={{ marginBottom: 14 }}>
                  {prereqs.map((p, i) => (
                    <div key={i} className="gs-prereq" onClick={() => setSelected(p.id)} style={{ "--dom": getDomColor(p.d, themeName) }}>
                      <span className="arrow" style={{ color: getDomColor(p.d, themeName) }}>↳</span>
                      <span style={{ flex: 1, color: "var(--ink)" }}>{nodeLabel(p, lang)}</span>
                      <span style={{ color: "var(--accent)" }}>{Math.round(p.m * 100)}%</span>
                    </div>
                  ))}
                </div>

                <button className="btn-primary" style={{ width: "100%", justifyContent: "center" }}>
                  {t.graphPractice} →
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------- Dashboard page ----------
function DashboardPage({ t, lang, themeName, setLang, mode, setMode }) {
  const stats = [
    { k: t.dashSessions, v: "147", delta: "+18 за месяц" },
    { k: t.dashSolved, v: "92", delta: "+12 за месяц" },
    { k: t.dashRate, v: "68%", delta: "+4% за неделю" },
    { k: t.dashHints, v: "31", delta: "−7 за неделю", down: true },
  ];
  const masteryData = [
    { lab: "Алгебра", v: 0.82 }, { lab: "Анализ", v: 0.71 }, { lab: "Гео", v: 0.69 },
    { lab: "Линал", v: 0.64 }, { lab: "Мех", v: 0.67 }, { lab: "Электр", v: 0.22 }, { lab: "Тепло", v: 0.38 },
  ];
  const masteryDataEn = [
    { lab: "Algebra", v: 0.82 }, { lab: "Calculus", v: 0.71 }, { lab: "Geom", v: 0.69 },
    { lab: "LinAlg", v: 0.64 }, { lab: "Mech", v: 0.67 }, { lab: "EM", v: 0.22 }, { lab: "Therm", v: 0.38 },
  ];
  const md = lang === "ru" ? masteryData : masteryDataEn;

  // Activity heatmap — 84 cells (12 weeks x 7 days)
  const heat = [];
  for (let i = 0; i < 84; i++) {
    const v = Math.random() < 0.45 ? 0 : Math.random();
    heat.push(v);
  }

  const errKeys = ["errAlgebra", "errArith", "errConcept", "errMethod", "errSyntax"];
  const errValues = [0.34, 0.22, 0.18, 0.16, 0.10];

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-head-info">
          <h1>{t.dashTitle}</h1>
          <div className="page-sub">{t.dashSub}</div>
        </div>
        <PageControls lang={lang} setLang={setLang} mode={mode} setMode={setMode}/>
        <button className="btn-secondary">30d</button>
        <button className="btn-primary">{t.dashExport}</button>
      </div>
      <div className="page-body">
        <div className="dash-bento">
          {/* HERO — overall mastery */}
          <div className="dash-card b-hero">
            <div className="dash-card-title">
              <span>{lang === "ru" ? "Общее владение" : "Overall mastery"}</span>
              <span style={{ color: "var(--ink-mute)" }}>BKT · DKT</span>
            </div>
            <div className="hero-num">
              <span className="hero-num-v">62</span>
              <span className="hero-num-pct">%</span>
              <span className="hero-num-delta">↗ +4% / 7d</span>
            </div>
            <svg width="100%" height="64" viewBox="0 0 320 64" style={{ marginTop: 8 }}>
              <defs>
                <linearGradient id="hero-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.28"/>
                  <stop offset="100%" stopColor="var(--accent)" stopOpacity="0"/>
                </linearGradient>
              </defs>
              <path d="M0,50 L20,48 L40,46 L60,42 L80,40 L100,42 L120,36 L140,32 L160,30 L180,26 L200,22 L220,18 L240,16 L260,14 L280,12 L300,10 L320,8 L320,64 L0,64 Z"
                fill="url(#hero-grad)"/>
              <polyline fill="none" stroke="var(--accent)" strokeWidth="1.8"
                points="0,50 20,48 40,46 60,42 80,40 100,42 120,36 140,32 160,30 180,26 200,22 220,18 240,16 260,14 280,12 300,10 320,8"
                style={{ filter: "drop-shadow(0 0 6px var(--accent))" }}/>
            </svg>
            <div className="hero-segs">
              {[
                { l: lang === "ru" ? "Сильные" : "Strong",   v: 12, c: "#22A05A" },
                { l: lang === "ru" ? "Средние" : "Medium",   v: 18, c: "var(--accent)" },
                { l: lang === "ru" ? "Слабые" : "Weak",      v:  8, c: "#E07A5F" },
              ].map((s, i) => (
                <div key={i} className="hero-seg">
                  <div className="hero-seg-v" style={{ color: s.c }}>{s.v}</div>
                  <div className="hero-seg-l">{s.l}</div>
                </div>
              ))}
            </div>
          </div>

          {/* 4 small stat cards */}
          {stats.map((s, i) => (
            <div className="dash-card b-stat" key={i}>
              <div className="stat-card-k">{s.k}</div>
              <div className="stat-card-v">{s.v}</div>
              <div className={"stat-card-delta " + (s.down ? "down" : "")}>{s.delta}</div>
            </div>
          ))}

          {/* Mastery by topic — wide */}
          <div className="dash-card b-mid">
            <div className="dash-card-title"><span>{t.dashMastery}</span><span style={{ color: "var(--ink-mute)" }}>BKT</span></div>
            <div className="bar-chart">
              {md.map((b, i) => (
                <div key={i} className={"bar " + (b.v > 0.7 ? "highlight" : "")} style={{ height: (b.v * 100) + "%" }}/>
              ))}
            </div>
            <div className="bar-labels">
              {md.map((b, i) => <span key={i}>{b.lab}</span>)}
            </div>
          </div>

          {/* Activity heatmap — large */}
          <div className="dash-card b-wide">
            <div className="dash-card-title"><span>{t.dashActivity}</span><span style={{ color: "var(--ink-mute)" }}>84 дн</span></div>
            <div className="heatmap">
              {heat.map((v, i) => (
                <div key={i} className="heatmap-day" style={{
                  background: v === 0
                    ? undefined
                    : (themeName === "midnight"
                      ? `rgba(180, 123, 255, ${0.2 + v * 0.8})`
                      : `rgba(104, 0, 255, ${0.15 + v * 0.85})`)
                }}/>
              ))}
            </div>
            <div className="heat-legend">
              <span>{lang === "ru" ? "Меньше" : "Less"}</span>
              {[0.2, 0.4, 0.6, 0.8, 1].map(v => (
                <span key={v} className="heat-key" style={{ background: themeName === "midnight" ? `rgba(180,123,255,${v})` : `rgba(104,0,255,${v})` }}/>
              ))}
              <span>{lang === "ru" ? "Больше" : "More"}</span>
              <span style={{ marginLeft: "auto" }}>{lang === "ru" ? "Серия: 14 дней 🔥" : "Streak: 14d 🔥"}</span>
            </div>
          </div>

          {/* Errors — wide */}
          <div className="dash-card b-mid">
            <div className="dash-card-title"><span>{t.dashErrors}</span></div>
            {errKeys.map((k, i) => (
              <div key={k} style={{ display: "flex", alignItems: "center", gap: 10, padding: "5px 0", fontSize: 12 }}>
                <span style={{ flex: 1, color: "var(--ink)" }}>{t[k]}</span>
                <div style={{ width: 160, height: 5, background: "var(--bg-soft)", borderRadius: 999, overflow: "hidden" }}>
                  <div style={{ width: (errValues[i] / errValues[0] * 100) + "%", height: "100%", background: ["#A8326A", "#B85A1F", "#6800FF", "#0E8B95", "#1E7A4A"][i], borderRadius: "inherit" }}/>
                </div>
                <span style={{ fontFamily: "JetBrains Mono", fontSize: 11, color: "var(--ink-mute)", minWidth: 38, textAlign: "right" }}>
                  {Math.round(errValues[i] * 100)}%
                </span>
              </div>
            ))}
          </div>

          {/* Recommendations — full width */}
          <div className="dash-card b-full">
            <div className="dash-card-title"><span>{t.dashReco}</span><span style={{ color: "var(--ink-mute)" }}>{t.recoTitle}</span></div>
            <div className="reco-grid">
              {t.recoItems.map((r, i) => (
                <div className="reco-item" key={i}>
                  <span className="reco-num">{i + 1}</span>
                  <span>{r}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------- Profile page ----------
function ProfilePage({ t, lang, themeName, setLang, mode, setMode }) {
  const recent = RECENT[lang];
  const focus = [32, 58, 45, 72, 68, 88, 62];
  const days = lang === "ru" ? ["П", "В", "С", "Ч", "П", "С", "В"] : ["M", "T", "W", "T", "F", "S", "S"];
  return (
    <div className="page">
      <div className="page-head">
        <div className="page-head-info">
          <h1>{t.profTitle}</h1>
          <div className="page-sub">{lang === "ru" ? "Максим Сухацкий · МГТУ им. Баумана · apprentice → journeyman" : "Maxim Sukhatskiy · Bauman MSTU · apprentice → journeyman"}</div>
        </div>
        <PageControls lang={lang} setLang={setLang} mode={mode} setMode={setMode}/>
        <button className="btn-secondary">{t.profEdit}</button>
      </div>
      <div className="page-body">
        <div className="profile-hero">
          <div className="profile-avatar">МС</div>
          <div className="profile-info">
            <h2 className="profile-name">Максим Сухацкий</h2>
            <div className="profile-meta">{lang === "ru" ? "siesher · когорта '25 · main contributor" : "siesher · cohort '25 · main contributor"}</div>
            <div className="profile-chips">
              <span className="profile-chip">Socratic mode</span>
              <span className="profile-chip">streak 14</span>
              <span className="profile-chip">RU / EN</span>
              <span className="profile-chip">github · siesher</span>
            </div>
          </div>
        </div>

        <div className="stat-cards" style={{ marginBottom: 22 }}>
          <div className="stat-card"><div className="stat-card-k">{t.profSessions}</div><div className="stat-card-v">147</div></div>
          <div className="stat-card"><div className="stat-card-k">{t.profProblems}</div><div className="stat-card-v">892</div></div>
          <div className="stat-card"><div className="stat-card-k">{t.profStreak}</div><div className="stat-card-v">14</div></div>
          <div className="stat-card"><div className="stat-card-k">{t.profMastery}</div><div className="stat-card-v">62%</div></div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 18 }}>
          <div className="dash-card">
            <div className="dash-card-title"><span>{t.profRecent}</span></div>
            <div className="timeline">
              {recent.map((r, i) => (
                <div key={i} className="tl-item" style={{ "--dom": getDomColor(r.d, themeName) }}>
                  <span className="tl-time">{r.t}</span>
                  <span className="dom-pill" style={{ "--dom": getDomColor(r.d, themeName), "--dom-tint": getDomColor(r.d, themeName) + "10" }}>{r.d}</span>
                  <span className="tl-body">{r.e}</span>
                </div>
              ))}
            </div>

            <div className="dash-card-title" style={{ marginTop: 28 }}><span>{t.profMasteryByTopic}</span></div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {[
                { lab: lang === "ru" ? "Алгебра" : "Algebra", v: 0.82 },
                { lab: lang === "ru" ? "Анализ" : "Calculus", v: 0.71 },
                { lab: lang === "ru" ? "Геометрия" : "Geometry", v: 0.69 },
                { lab: lang === "ru" ? "Линал" : "Linear Algebra", v: 0.64 },
                { lab: lang === "ru" ? "Механика" : "Mechanics", v: 0.67 },
              ].map((m, i) => (
                <div key={i}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                    <span style={{ color: "var(--ink)" }}>{m.lab}</span>
                    <span style={{ color: "var(--accent)", fontFamily: "JetBrains Mono", fontWeight: 600 }}>{Math.round(m.v * 100)}%</span>
                  </div>
                  <div className="gs-bar"><div className="gs-bar-fill" style={{ width: (m.v * 100) + "%" }}/></div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div className="dash-card">
              <div className="dash-card-title"><span>{t.profEmotion}</span></div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#FFB85C", boxShadow: "0 0 8px #FFB85C" }}/>
                <span style={{ fontSize: 18, color: "var(--ink)", fontWeight: 600 }}>focused</span>
              </div>
              <div style={{ fontSize: 11, fontFamily: "JetBrains Mono", color: "var(--ink-mute)" }}>{t.profEmotionDesc}</div>
            </div>

            <div className="dash-card">
              <div className="dash-card-title"><span>{t.profFocusWeek}</span></div>
              <svg width="100%" height="80" viewBox="0 0 220 90" style={{ marginBottom: 4 }}>
                {focus.map((v, i) => (
                  <rect key={i} x={i * 30 + 6} y={90 - v} width="22" height={v}
                    fill={i === 5 ? "#FFB85C" : "var(--accent)"}
                    rx="2"
                    opacity={i === 5 ? 1 : 0.85}
                    style={{ filter: i === 5 ? "drop-shadow(0 0 6px #FFB85C)" : "none" }}/>
                ))}
              </svg>
              <div style={{ display: "flex", fontSize: 10, color: "var(--ink-mute)", fontFamily: "JetBrains Mono" }}>
                {days.map((d, i) => <span key={i} style={{ flex: 1, textAlign: "center" }}>{d}</span>)}
              </div>
            </div>

            <div className="dash-card">
              <div className="dash-card-title"><span>{t.profStrong}</span></div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {t.strongSkills.map(s => <span key={s} className="skill-tag strong">{s}</span>)}
              </div>
            </div>
            <div className="dash-card">
              <div className="dash-card-title"><span>{t.profWeak}</span></div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {t.weakSkills.map(s => <span key={s} className="skill-tag weak">{s}</span>)}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------- Sources page ----------
function SourcesPage({ t, lang, themeName, setLang, mode, setMode }) {
  const list = SOURCES_LIST[lang];
  return (
    <div className="page">
      <div className="page-head">
        <div className="page-head-info">
          <h1>{t.srcTitle}</h1>
          <div className="page-sub">{t.srcSub}</div>
        </div>
        <PageControls lang={lang} setLang={setLang} mode={mode} setMode={setMode}/>
        <button className="btn-primary">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M8 3v10M3 8h10"/></svg>
          {t.srcAdd}
        </button>
      </div>
      <div className="page-body">
        <div className="pipeline">
          {PIPELINE_STEPS.map((s, i) => (
            <React.Fragment key={s}>
              <div className={"pipe-step " + (i === 2 ? "current" : "")}>
                <span className="pipe-idx">{String(i).padStart(2, "0")}</span>
                <span>{s}</span>
              </div>
              {i < PIPELINE_STEPS.length - 1 && <span className="pipe-arrow">→</span>}
            </React.Fragment>
          ))}
        </div>

        <div className="stat-cards" style={{ gridTemplateColumns: "repeat(4, 1fr)", marginBottom: 18 }}>
          <div className="stat-card"><div className="stat-card-k">nodes</div><div className="stat-card-v">106</div></div>
          <div className="stat-card"><div className="stat-card-k">edges</div><div className="stat-card-v">176</div></div>
          <div className="stat-card"><div className="stat-card-k">domains</div><div className="stat-card-v">4</div></div>
          <div className="stat-card"><div className="stat-card-k">sources</div><div className="stat-card-v">{list.length}</div></div>
        </div>

        <div className="src-grid">
          {list.map((s, i) => (
            <div className="src-card" key={i}>
              <div className="src-row1">
                <span className="kind-chip">{s.kind}</span>
                <span className="dom-pill" style={{ "--dom": getDomColor(s.domain, themeName), "--dom-tint": getDomColor(s.domain, themeName) + "10" }}>{s.domain}</span>
                <span className={"status-chip " + s.status}>
                  {(s.status === "extracting" || s.status === "pending") && <span className="ld"/>}
                  {s.status === "extracted" && "✓ "}
                  {t["srcStat" + s.status.charAt(0).toUpperCase() + s.status.slice(1)]}
                </span>
              </div>
              <h3 className="src-title">{s.title}</h3>
              <div className="src-preview">{s.preview}</div>
              <div className="src-stats">
                <span><span style={{ opacity: 0.6 }}>{t.srcNodes}</span> <b>{s.nodes}</b></span>
                <span><span style={{ opacity: 0.6 }}>{t.srcEdges}</span> <b>{s.edges}</b></span>
                <span style={{ marginLeft: "auto", opacity: 0.7 }}>{s.when}</span>
              </div>
              <div className="src-progress">
                <div className={"src-progress-fill " + (s.status === "extracting" ? "extracting" : "")}
                  style={{
                    width: s.status === "extracted" ? "100%" : s.status === "extracting" ? "62%" : s.status === "pending" ? "12%" : "100%",
                    background: s.status === "extracted" ? "#22A05A" : "var(--accent)"
                  }}/>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------- Settings page ----------
function SettingsPage({ t, lang, themeName, setLang, mode, setMode, currentTheme, setCurrentTheme }) {
  const [glow, setGlow] = usePg(themeName === "midnight" ? 18 : 8);
  const [motion, setMotion] = usePg(true);
  const [particles, setParticles] = usePg(themeName !== "aurora");
  const [grain, setGrain] = usePg(themeName === "grimoire");

  const themes = [
    { id: "aurora", name: "Aurora", desc: "Clean Anthropic-style", swatch: ["#FFF9EB", "#6800FF", "#1A1330"] },
    { id: "grimoire", name: "Grimoire", desc: "Magical editorial", swatch: ["#F4ECD8", "#6800FF", "#3D2E66"] },
    { id: "midnight", name: "Midnight", desc: "Dark with purple glow", swatch: ["#0A0518", "#8B3CFF", "#B47BFF"] },
  ];

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-head-info">
          <h1>{t.setTitle}</h1>
          <div className="page-sub">{t.setSub}</div>
        </div>
        <PageControls lang={lang} setLang={setLang} mode={mode} setMode={setMode}/>
      </div>
      <div className="page-body">
        <div className="set-section">
          <div className="set-section-title">{t.setTheme}</div>
          <div className="theme-cards">
            {themes.map(th => (
              <button key={th.id} className={"theme-card " + (currentTheme === th.id ? "active" : "")} onClick={() => setCurrentTheme && setCurrentTheme(th.id)}>
                <div className="theme-swatch">{th.swatch.map((c, i) => <span key={i} style={{ background: c }}/>)}</div>
                <div className="theme-card-name">{currentTheme === th.id && "▸ "}{th.name}</div>
                <div className="theme-card-desc">{th.desc}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="set-section">
          <div className="set-section-title">{t.setEffects}</div>
          <div className="set-row">
            <span className="set-row-label">{t.setGlow}</span>
            <input className="set-slider" type="range" min="0" max="32" step="2" value={glow} onChange={e => setGlow(+e.target.value)}/>
            <span className="set-value">{glow}px</span>
          </div>
          <div className="set-row">
            <span className="set-row-label">{t.setMotion}</span>
            <button className={"set-toggle " + (motion ? "on" : "")} onClick={() => setMotion(!motion)}/>
          </div>
          <div className="set-row">
            <span className="set-row-label">{t.setParticles}</span>
            <button className={"set-toggle " + (particles ? "on" : "")} onClick={() => setParticles(!particles)}/>
          </div>
          <div className="set-row">
            <span className="set-row-label">{t.setGrain}</span>
            <button className={"set-toggle " + (grain ? "on" : "")} onClick={() => setGrain(!grain)}/>
          </div>
        </div>

        <div className="set-section">
          <div className="set-section-title">{t.setAbout}</div>
          <div className="about-text">{t.setAboutText}</div>
        </div>
      </div>
    </div>
  );
}

window.MITS_PAGES = { TasksPage, GraphPage, DashboardPage, ProfilePage, SourcesPage, SettingsPage };
