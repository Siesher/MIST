// MITS — Chat App component
// Renders the full Claude-Desktop-style chat interface for one theme variation.

const { useState, useEffect, useRef, useMemo } = React;
const { I18N, DIALOG, SESSIONS, SKILLS, TECH_TAGS } = window.MITS_DATA;

// ---------- Icons (inline SVG) ----------
const Icon = {
  chat: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M2 4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H7l-3.5 2.5V12H4a2 2 0 0 1-2-2V4z"/></svg>,
  list: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M5 3.5h9M5 8h9M5 12.5h9M2 3.5h1M2 8h1M2 12.5h1"/></svg>,
  graph: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="4" cy="4" r="2"/><circle cx="12" cy="4" r="2"/><circle cx="8" cy="12" r="2"/><path d="M5.5 5.5 7 10.5M10.5 5.5 9 10.5M6 4h4"/></svg>,
  chart: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M2 13V3M2 13h12"/><rect x="4" y="8" width="2.5" height="5"/><rect x="7.5" y="5" width="2.5" height="8"/><rect x="11" y="10" width="2.5" height="3"/></svg>,
  database: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><ellipse cx="8" cy="3.5" rx="5" ry="1.8"/><path d="M3 3.5v9c0 1 2.2 1.8 5 1.8s5-.8 5-1.8v-9M3 8c0 1 2.2 1.8 5 1.8s5-.8 5-1.8"/></svg>,
  user: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="5.5" r="2.5"/><path d="M3 14a5 5 0 0 1 10 0" strokeLinecap="round"/></svg>,
  signin: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M9.5 2H12a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9.5"/><path d="M3 8h7m-3-3 3 3-3 3"/></svg>,
  plus: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M8 3v10M3 8h10"/></svg>,
  send: <svg viewBox="0 0 16 16" fill="currentColor"><path d="M2.3 1.6 14 7.5a.5.5 0 0 1 0 .9L2.3 14.3a.5.5 0 0 1-.7-.6l1.6-4.7a.5.5 0 0 1 .4-.3L9 8 3.7 6.3a.5.5 0 0 1-.4-.3L1.7 2.2a.5.5 0 0 1 .6-.6Z"/></svg>,
  paperclip: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="m10.5 5-4.7 4.7a2 2 0 0 0 2.8 2.8L13 7.2a3.5 3.5 0 0 0-4.9-5L3.2 7.2a5 5 0 0 0 7 7L14 10.5"/></svg>,
  mic: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><rect x="6" y="2" width="4" height="8" rx="2"/><path d="M3.5 7.5a4.5 4.5 0 0 0 9 0M8 12v2"/></svg>,
  image: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><rect x="2" y="2.5" width="12" height="11" rx="2"/><circle cx="6" cy="6.5" r="1.3"/><path d="m2.5 11.5 3.5-3 3 2.5 2-1.5 2.5 2"/></svg>,
  github: <svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 0a8 8 0 0 0-2.5 15.6c.4.1.5-.2.5-.4v-1.5c-2 .4-2.5-.5-2.7-1 0-.1-.5-.9-.8-1.1-.3-.2-.7-.6 0-.6.6 0 1 .6 1.2.8.7 1.2 1.9 1 2.4.8 0-.5.3-1 .5-1.1-1.8-.2-3.6-.9-3.6-3.9 0-.9.3-1.6.8-2.2 0-.2-.4-1 .1-2.2 0 0 .7-.2 2.3.8a8 8 0 0 1 4 0c1.6-1 2.3-.8 2.3-.8.5 1.2.2 2 .1 2.2.5.6.8 1.3.8 2.2 0 3-1.9 3.7-3.6 3.9.3.2.5.7.5 1.4v2.1c0 .2.1.5.5.4A8 8 0 0 0 8 0Z"/></svg>,
  sparkle: <svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 0 9.5 6.5 16 8 9.5 9.5 8 16 6.5 9.5 0 8 6.5 6.5z"/></svg>,
  bookOpen: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M2 3v10l4-1 2 .5 2-.5 4 1V3l-4 1-2-.5L6 4 2 3Z"/><path d="M8 4v9"/></svg>,
  hash: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M3 6h10M3 10h10M6 2v12M10 2v12"/></svg>,
  flask: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M6 2v4.5L2.5 12a1.5 1.5 0 0 0 1.3 2.3h8.4A1.5 1.5 0 0 0 13.5 12L10 6.5V2M5 2h6"/></svg>,
  sun: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="8" r="3"/><path strokeLinecap="round" d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.5 1.5M11.5 11.5 13 13M3 13l1.5-1.5M11.5 4.5 13 3"/></svg>,
  moon: <svg viewBox="0 0 16 16" fill="currentColor"><path d="M6.5 1a7 7 0 1 0 8.5 8.5A6 6 0 0 1 6.5 1Z"/></svg>,
  settings: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="8" r="2"/><path strokeLinecap="round" d="m13.5 9.5-.7-.5a5 5 0 0 0 0-2l.7-.5a1 1 0 0 0 .2-1.3l-1-1.6a1 1 0 0 0-1.2-.4l-.8.3a5 5 0 0 0-1.7-1l-.1-.9a1 1 0 0 0-1-.8H7a1 1 0 0 0-1 .8L5.9 3a5 5 0 0 0-1.7 1L3.5 4a1 1 0 0 0-1.2.3l-1 1.6a1 1 0 0 0 .2 1.3l.8.6a5 5 0 0 0 0 2l-.8.6a1 1 0 0 0-.2 1.3l1 1.6a1 1 0 0 0 1.2.4l.8-.3a5 5 0 0 0 1.7 1l.1.9a1 1 0 0 0 1 .8h2a1 1 0 0 0 1-.8l.1-.9a5 5 0 0 0 1.7-1l.8.3a1 1 0 0 0 1.2-.4l1-1.6a1 1 0 0 0-.2-1.3Z"/></svg>,
  globe: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4"><circle cx="8" cy="8" r="6.5"/><path d="M1.5 8h13M8 1.5c2 2 2 11 0 13M8 1.5c-2 2-2 11 0 13"/></svg>,
};

// ---------- Nav rail (leftmost) ----------
function NavRail({ t, view, setView }) {
  const items = [
    { id: "chat",      icon: Icon.chat,     label: t.navChat },
    { id: "tasks",     icon: Icon.list,     label: t.navTasks },
    { id: "graph",     icon: Icon.graph,    label: t.navGraph },
    { id: "dashboard", icon: Icon.chart,    label: t.navDashboard },
    { id: "sources",   icon: Icon.database, label: t.navSources },
  ];
  const signInLabel = t.appName === "MITS" && t.navProfile === "Профиль" ? "Войти" : "Sign in";
  const bottom = [
    { id: "profile",  icon: Icon.user,     label: t.navProfile },
    { id: "settings", icon: Icon.settings, label: t.navSettings },
    { id: "auth",     icon: Icon.signin,   label: signInLabel },
  ];
  return (
    <div className="nav-rail">
      {items.map(it => (
        <button key={it.id} className={"nav-btn " + (view === it.id ? "active" : "")} onClick={() => setView(it.id)}>
          {it.icon}
          <span className="nav-label">{it.label}</span>
        </button>
      ))}
      <div className="nav-spacer"/>
      {bottom.map(it => (
        <button key={it.id} className={"nav-btn " + (view === it.id ? "active" : "")} onClick={() => setView(it.id)}>
          {it.icon}
          <span className="nav-label">{it.label}</span>
        </button>
      ))}
    </div>
  );
}

// ---------- Sidebar (chat sessions list) ----------
function Sidebar({ t, lang }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">M
          <svg style={{position:'absolute',inset:0,opacity:0.3}} viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="0.5">
            <circle cx="16" cy="16" r="12"/><circle cx="16" cy="16" r="8"/>
          </svg>
        </div>
        <div>
          <div className="brand-name">{t.appName}</div>
          <div className="brand-tag">{t.appSub}</div>
        </div>
      </div>

      <button className="new-chat magnetic">
        {Icon.plus}
        <span>{t.newChat}</span>
        <span style={{marginLeft:"auto",fontFamily:'JetBrains Mono',fontSize:10,opacity:0.7}}>⌘N</span>
      </button>

      <div>
        <div className="section-label">{t.sessionsToday}</div>
        <div className="session-list">
          {SESSIONS.slice(0, 3).map(s => (
            <div key={s.id} className={"session " + (s.active ? "active" : "")}>
              <span className="session-dot" style={{background: dotForMode(s.mode)}}/>
              <span className="session-title">{t[s.key]}</span>
              <span className="session-meta">{s.time}</span>
            </div>
          ))}
        </div>

        <div className="section-label" style={{marginTop:8}}>{t.sessionsYesterday}</div>
        <div className="session-list">
          {SESSIONS.slice(3, 5).map(s => (
            <div key={s.id} className="session">
              <span className="session-dot" style={{background: dotForMode(s.mode)}}/>
              <span className="session-title">{t[s.key]}</span>
              <span className="session-meta">{s.time}</span>
            </div>
          ))}
        </div>

        <div className="section-label" style={{marginTop:8}}>{t.sessionsWeek}</div>
        <div className="session-list">
          {SESSIONS.slice(5).map(s => (
            <div key={s.id} className="session">
              <span className="session-dot" style={{background: dotForMode(s.mode)}}/>
              <span className="session-title">{t[s.key]}</span>
              <span className="session-meta">{s.time}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="sidebar-footer">
        <button className="foot-item">{Icon.bookOpen}<span>{t.docs}</span></button>
        <a className="gh-card" href="https://github.com/Siesher/MITS" target="_blank" rel="noopener">
          <span className="gh-avatar">SH</span>
          <div className="gh-info">
            <div className="gh-handle">{Icon.github} Siesher/MITS</div>
            <div className="gh-stars">★ 247 · main</div>
          </div>
        </a>
      </div>
    </aside>
  );
}

function dotForMode(m) {
  if (m === "guided") return "#22A05A";
  if (m === "chat") return "#3B7DFF";
  if (m === "task") return "#6800FF";
  return "#888";
}

// ---------- Top bar ----------
function TopBar({ t, lang, setLang, theme, setTheme, hideTitle }) {
  return (
    <div className="top-bar">
      <div className="top-title">
        {!hideTitle && <h1>{t.taskTitle}</h1>}
        {!hideTitle && <span className="top-sub">{t.taskLabel}</span>}
      </div>

      <div className="lang-toggle">
        <button className={lang === "ru" ? "active" : ""} onClick={() => setLang("ru")}>RU</button>
        <button className={lang === "en" ? "active" : ""} onClick={() => setLang("en")}>EN</button>
      </div>

      <button className="theme-toggle" onClick={() => setTheme(theme === "light" ? "dark" : "light")} title="Toggle theme">
        {theme === "light" ? Icon.moon : Icon.sun}
      </button>
    </div>
  );
}

// ---------- Agent flow strip ----------
function AgentFlow({ t }) {
  const agents = [
    { key: "agProfiler", state: "done" },
    { key: "agPlanner", state: "done" },
    { key: "agTutor", state: "active" },
    { key: "agVerifier", state: "" },
  ];
  return (
    <div className="agent-flow">
      <span className="agent-flow-label">{t.agentLabel}</span>
      {agents.map((a, i) => (
        <React.Fragment key={a.key}>
          <div className={"agent-pill " + a.state}>
            <span className="agent-dot"/>
            <span>{t[a.key]}</span>
          </div>
          {i < agents.length - 1 && (
            <div className="agent-arrow">
              {(agents[i].state === "done" || agents[i].state === "active") && <span className="flow-dot" style={{animationDelay: (i * 0.4) + "s"}}/>}
            </div>
          )}
        </React.Fragment>
      ))}
      <div style={{marginLeft:"auto",display:"flex",gap:8,alignItems:"center"}}>
        <span style={{fontSize:11,color:"var(--ink-mute)"}}>Qwen3.5-9B · final</span>
        <span className="agent-dot" style={{background:"#22A05A"}}/>
      </div>
    </div>
  );
}

// ---------- Task card ----------
function TaskCard({ t }) {
  return (
    <div className="task-card">
      <div className="task-icon">{Icon.sparkle}</div>
      <div className="task-body">
        <div className="task-label">{t.taskLabel}</div>
        <h3 className="task-title">{t.taskTitle}</h3>
        <div className="task-formula">f(x) = sin(x²) · cos(3x⁴ − 1)</div>
        <div className="task-meta">
          <span>{t.taskDifficulty}: <b>medium</b></span>
          <span>{t.taskHints}: <b>3/3</b></span>
          <span>{t.taskSkill}: <b>{t.skillChain}</b></span>
        </div>
      </div>
    </div>
  );
}

// ---------- Single message ----------
function Message({ m, t, lang }) {
  const [thinkOpen, setThinkOpen] = useState(true);
  const [typed, setTyped] = useState(m.streaming ? "" : m.body);

  useEffect(() => {
    if (!m.streaming) return;
    let i = 0;
    const target = m.body;
    const id = setInterval(() => {
      i = Math.min(i + 8, target.length);
      setTyped(target.slice(0, i));
      if (i >= target.length) clearInterval(id);
    }, 28);
    return () => clearInterval(id);
  }, [m.streaming, m.body, lang]);

  return (
    <div className={"msg " + m.role}>
      <div className="msg-avatar">{m.role === "user" ? "S" : "T"}</div>
      <div className="msg-content">
        <div className="msg-header">
          <span className="msg-name">{m.role === "user" ? t.userYou : t.userTutor}</span>
          {m.move && (
            <span className={"move-badge " + m.move}>{t["move" + capitalize(m.move)]}</span>
          )}
          <span className="msg-time">{m.time}</span>
        </div>
        {m.thinking && (
          <div className="thinking">
            <button className="thinking-toggle" onClick={() => setThinkOpen(!thinkOpen)}>
              <span className="dot"/>
              <span>{thinkOpen ? t.hideThinking : t.showThinking}</span>
              <span style={{color:"var(--ink-mute)",opacity:0.6}}>· {t.thinkingTokens(m.tokens)}</span>
            </button>
            {thinkOpen && (
              <div className="thinking-body" dangerouslySetInnerHTML={{__html: m.thinking}}/>
            )}
          </div>
        )}
        <div className="msg-body" dangerouslySetInnerHTML={{__html: typed}}/>
        {m.streaming && typed.length < m.body.length && <span className="cursor"/>}
      </div>
    </div>
  );
}

function capitalize(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

// ---------- Messages list ----------
function MessageList({ t, lang }) {
  const scrollRef = useRef(null);
  const dialog = DIALOG[lang];

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [lang]);

  return (
    <div className="messages" ref={scrollRef}>
      <div className="msg-wrap">
        <TaskCard t={t}/>
        {dialog.map((m, i) => <Message key={lang + "-" + i} m={m} t={t} lang={lang}/>)}
      </div>
    </div>
  );
}

// ---------- Mode selector + composer ----------
function Composer({ t, lang }) {
  const [mode, setMode] = useState("guided");
  const [open, setOpen] = useState(false);
  const [val, setVal] = useState("");

  const modes = [
    { id: "chat", label: t.modeChat, desc: t.modeChatDesc, dot: "#3B7DFF" },
    { id: "guided", label: t.modeGuided, desc: t.modeGuidedDesc, dot: "#22A05A" },
    { id: "task", label: t.modeTask, desc: t.modeTaskDesc, dot: "#6800FF" },
  ];
  const current = modes.find(m => m.id === mode);

  return (
    <div className="composer">
      <div className="composer-wrap">
        <div className="composer-row1">
          <div style={{position:"relative"}}>
            <button className="mode-chip active" onClick={() => setOpen(!open)}>
              <span className="mode-dot" style={{background:current.dot}}/>
              <span>{current.label}</span>
              <svg viewBox="0 0 12 12" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="1.5" style={{transform: open ? "rotate(180deg)" : "", transition:"transform .15s"}}><path d="m3 4.5 3 3 3-3" strokeLinecap="round"/></svg>
            </button>
            {open && (
              <div className="mode-pop">
                {modes.map(m => (
                  <div key={m.id} className="mode-pop-item" onClick={() => { setMode(m.id); setOpen(false); }}>
                    <span className="mode-dot" style={{background:m.dot,marginTop:4,width:8,height:8,borderRadius:"50%"}}/>
                    <div>
                      <div className="mode-pop-title">{m.label}</div>
                      <div className="mode-pop-desc">{m.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button className="hint-btn">
            <svg viewBox="0 0 12 12" width="11" height="11" fill="currentColor"><circle cx="6" cy="6" r="5" opacity="0.2"/><circle cx="6" cy="6" r="2"/></svg>
            <span>{t.hintBtn}</span>
            <span style={{opacity:0.7}}>· {t.hintsLeft(3)}</span>
          </button>
        </div>
        <div className="composer-input">
          <textarea
            value={val}
            onChange={(e) => setVal(e.target.value)}
            placeholder={t.placeholder}
            rows={1}
          />
          <div className="composer-tools">
            <button className="tool-btn" title="Attach image">{Icon.image}</button>
            <button className="tool-btn" title="Voice">{Icon.mic}</button>
            <button className="send-btn magnetic">{Icon.send}</button>
          </div>
        </div>
        <div className="composer-hint">
          <kbd>Enter</kbd> {t.composerHintSend || (lang === "ru" ? "отправить" : "to send")}
          <span style={{opacity:0.4}}>•</span>
          <kbd>Shift</kbd><kbd>Enter</kbd> {t.composerHintNew || (lang === "ru" ? "новая строка" : "newline")}
          <span style={{opacity:0.4}}>•</span>
          <kbd>⌘</kbd><kbd>K</kbd> {t.composerHintCmd || (lang === "ru" ? "команды" : "commands")}
        </div>
      </div>
    </div>
  );
}

// ---------- Right rail ----------
function Rail({ t, lang }) {
  const skills = SKILLS[lang];
  return (
    <aside className="rail">
      <div className="rail-card">
        <div className="rail-card-title">
          <span>{t.railSkills}</span>
          <span className="pill">{t.railSkillsTag}</span>
        </div>
        {skills.map((s, i) => (
          <div className="skill-row" key={i}>
            <span className="skill-name">{s.name}</span>
            <span className="skill-bar"><span className="skill-bar-fill" style={{width: (s.val * 100) + "%"}}/></span>
            <span className="skill-val">{Math.round(s.val * 100)}%</span>
          </div>
        ))}
      </div>

      <div className="rail-card">
        <div className="rail-card-title"><span>{t.railSession}</span></div>
        <div className="stat-grid">
          <div className="stat"><div className="stat-val">18</div><div className="stat-lbl">{t.statTime}</div></div>
          <div className="stat"><div className="stat-val">14</div><div className="stat-lbl">{t.statMessages}</div></div>
          <div className="stat"><div className="stat-val">0/3</div><div className="stat-lbl">{t.statHints}</div></div>
          <div className="stat"><div className="stat-val">1/1</div><div className="stat-lbl">{t.statSolved}</div></div>
        </div>
      </div>

      <div className="rail-card">
        <div className="rail-card-title"><span>{t.railArch}</span></div>
        <ArchDiagram/>
      </div>

      <div className="marquee">
        <div className="marquee-track">
          {[...TECH_TAGS, ...TECH_TAGS].map((tag, i) => (
            <span className="tech-tag" key={i}>{tag}</span>
          ))}
        </div>
      </div>
    </aside>
  );
}

function ArchDiagram() {
  return (
    <svg className="arch-svg" viewBox="0 0 260 170">
      {/* Nodes */}
      <rect className="arch-node" x="10" y="20" width="56" height="26" rx="5"/>
      <text className="arch-text" x="38" y="36" textAnchor="middle">PROFILER</text>

      <rect className="arch-node" x="80" y="20" width="56" height="26" rx="5"/>
      <text className="arch-text" x="108" y="36" textAnchor="middle">PLANNER</text>

      <rect className="arch-node active" x="150" y="20" width="50" height="26" rx="5"/>
      <text className="arch-text" x="175" y="36" textAnchor="middle" style={{fill:"var(--accent-text)"}}>TUTOR</text>

      <rect className="arch-node" x="214" y="20" width="36" height="26" rx="5"/>
      <text className="arch-text" x="232" y="36" textAnchor="middle">VERIFY</text>

      {/* Lower layer */}
      <rect className="arch-node" x="10" y="100" width="56" height="22" rx="4"/>
      <text className="arch-text" x="38" y="114" textAnchor="middle" style={{fontSize:8}}>RAG · CHROMA</text>

      <rect className="arch-node" x="80" y="100" width="56" height="22" rx="4"/>
      <text className="arch-text" x="108" y="114" textAnchor="middle" style={{fontSize:8}}>KNOWLEDGE · KT</text>

      <rect className="arch-node" x="150" y="100" width="100" height="22" rx="4"/>
      <text className="arch-text" x="200" y="114" textAnchor="middle" style={{fontSize:8}}>SKI · TOOLS</text>

      {/* Bottom */}
      <rect className="arch-node" x="40" y="140" width="180" height="22" rx="4"/>
      <text className="arch-text" x="130" y="154" textAnchor="middle" style={{fontSize:8}}>OLLAMA · QWEN3.5-9B · BF16</text>

      {/* Arrows */}
      <path className="arch-link" d="M66 33h14M136 33h14M200 33h14"/>
      <path className="arch-link" d="M175 46v44"/>
      <path className="arch-link" d="M38 46v44M108 46v44"/>
      <path className="arch-link" d="M130 122v18"/>

      {/* Animated data dots */}
      <circle r="2" fill="var(--accent)">
        <animateMotion dur="2.4s" repeatCount="indefinite" path="M66 33 L150 33"/>
      </circle>
      <circle r="2" fill="var(--accent)">
        <animateMotion dur="3s" repeatCount="indefinite" path="M175 46 L175 100"/>
      </circle>
      <circle r="2" fill="var(--accent)">
        <animateMotion dur="2.6s" repeatCount="indefinite" path="M108 122 L130 140"/>
      </circle>
    </svg>
  );
}

// ---------- Decorations per theme ----------
function ThemeDecor({ theme }) {
  if (theme === "grimoire") {
    return (
      <>
        <svg className="hex" style={{top: 80, left: 100, width: 120, height: 120}} viewBox="0 0 120 120" fill="none" stroke="currentColor" strokeWidth="0.6">
          <circle cx="60" cy="60" r="56"/>
          <circle cx="60" cy="60" r="42"/>
          <circle cx="60" cy="60" r="28"/>
          <polygon points="60,8 105,86 15,86"/>
          <polygon points="60,112 15,34 105,34"/>
        </svg>
        <svg className="hex" style={{bottom: 60, right: 60, width: 140, height: 140, animationDuration: "80s", animationDirection:"reverse"}} viewBox="0 0 140 140" fill="none" stroke="currentColor" strokeWidth="0.6">
          <circle cx="70" cy="70" r="66"/>
          <circle cx="70" cy="70" r="50"/>
          <polygon points="70,10 124,100 16,100"/>
          <polygon points="70,130 16,40 124,40"/>
        </svg>
        <svg className="hex" style={{top: "45%", right: 280, width: 80, height: 80, animationDuration: "100s"}} viewBox="0 0 80 80" fill="none" stroke="currentColor" strokeWidth="0.4">
          <circle cx="40" cy="40" r="38"/>
          <polygon points="40,6 70,58 10,58"/>
          <polygon points="40,74 10,22 70,22"/>
        </svg>
      </>
    );
  }
  if (theme === "midnight") {
    const stars = [];
    for (let i = 0; i < 40; i++) {
      stars.push(<span key={i} style={{
        left: Math.random() * 100 + "%",
        top: Math.random() * 100 + "%",
        animationDelay: (Math.random() * 8) + "s",
        animationDuration: (6 + Math.random() * 6) + "s",
      }}/>);
    }
    return <div className="particles">{stars}</div>;
  }
  return null;
}

// ---------- Status bar (thin top strip with live indicators) ----------
function StatusBar({ t, lang, view }) {
  const labels = {
    chat: lang === "ru" ? "Сократическая сессия" : "Socratic session",
    tasks: lang === "ru" ? "Каталог задач" : "Task catalog",
    graph: lang === "ru" ? "Граф знаний" : "Knowledge graph",
    dashboard: lang === "ru" ? "Аналитика" : "Analytics",
    profile: lang === "ru" ? "Профиль" : "Profile",
    sources: lang === "ru" ? "Источники" : "Sources",
    settings: lang === "ru" ? "Настройки" : "Settings",
  };
  return (
    <div className="status-bar">
      <span className="status-dot"/>
      <span>{lang === "ru" ? "Модель работает" : "Model online"}</span>
      <span className="sb-divider"/>
      <span>mits-qwen3-9b-final</span>
      <span className="sb-divider"/>
      <span style={{color:"var(--ink)"}}>{labels[view] || labels.chat}</span>
      <span className="sb-spacer"/>
      <a className="sb-link" href="https://github.com/Siesher/MITS" target="_blank" rel="noopener" style={{display:"inline-flex",alignItems:"center",gap:6}}>
        {Icon.github}
        Siesher/MITS
      </a>
      <span className="sb-divider"/>
      <span>★ 247</span>
      <span className="sb-divider"/>
      <span style={{display:"inline-flex",alignItems:"center",gap:5}}>
        <kbd className="sb-key">⌘</kbd>
        <kbd className="sb-key">K</kbd>
      </span>
    </div>
  );
}

// ---------- Chat view ----------
function ChatView({ t, lang, setLang, mode, setMode }) {
  return (
    <>
      <main className="main">
        <StatusBar t={t} lang={lang} view="chat"/>
        <TopBar t={t} lang={lang} setLang={setLang} theme={mode} setTheme={setMode}/>
        <AgentFlow t={t}/>
        <MessageList t={t} lang={lang}/>
        <Composer t={t} lang={lang}/>
      </main>
      <Rail t={t} lang={lang}/>
    </>
  );
}

// ---------- Project info rail (for non-chat pages) ----------
function ProjectRail({ t, lang, themeName }) {
  return (
    <aside className="rail">
      <div className="rail-card">
        <div className="rail-card-title">
          <span>{lang === "ru" ? "Активная модель" : "Active model"}</span>
          <span className="pill">final</span>
        </div>
        <div style={{fontFamily:'JetBrains Mono', fontSize:13, color:'var(--ink)'}}>mits-qwen3-9b-final</div>
        <div style={{fontSize:12, color:'var(--ink-mute)', marginTop:6}}>GSPO → KTO → DPO · 9B · bf16</div>
        <div style={{display:'flex', gap:6, marginTop:14, flexWrap:'wrap'}}>
          <span className="tag-chip">66.5% MGSM</span>
          <span className="tag-chip">+11.4 base</span>
        </div>
      </div>

      <div className="rail-card">
        <div className="rail-card-title"><span>{lang === "ru" ? "Пайплайн обучения" : "Training pipeline"}</span></div>
        {[
          { stage: "GSPO", model: "mits-qwen3-9b-gspo", score: 60.2 },
          { stage: "KTO",  model: "mits-qwen3-9b-kto",  score: 64.1 },
          { stage: "DPO",  model: "mits-qwen3-9b-final",score: 66.5 },
        ].map(s => (
          <div key={s.stage} style={{display:'flex', alignItems:'center', gap:12, padding:'7px 0', fontSize:12.5}}>
            <span style={{width:6, height:6, borderRadius:'50%', background:'var(--accent)'}}/>
            <div style={{flex:1}}>
              <div style={{color:'var(--ink)'}}>{s.stage}</div>
              <div style={{fontSize:11, color:'var(--ink-mute)', fontFamily:'JetBrains Mono', marginTop:1}}>{s.model}</div>
            </div>
            <span style={{fontVariantNumeric:'tabular-nums', fontSize:12, color:'var(--ink-soft)'}}>{s.score}%</span>
          </div>
        ))}
      </div>

      <div className="rail-card">
        <div className="rail-card-title"><span>GitHub</span></div>
        <a className="gh-card" href="https://github.com/Siesher/MITS" target="_blank" rel="noopener" style={{margin:0, border:'none', padding:0, background:'transparent'}}>
          <span className="gh-avatar">SH</span>
          <div className="gh-info">
            <div className="gh-handle">Siesher/MITS</div>
            <div className="gh-stars">★ 247 · main</div>
          </div>
        </a>
      </div>
    </aside>
  );
}

// ---------- Auth View (login / register) ----------
function AuthView({ t, lang, setLang, mode, setMode, setView }) {
  const [authMode, setAuthMode] = useState("login"); // login | register
  const [showPwd, setShowPwd] = useState(false);
  const isReg = authMode === "register";

  const L = {
    ru: {
      welcome: "Добро пожаловать",
      welcomeSub: "Сократический наставник для STEM — ведёт вопросами, а не даёт ответы",
      login: "Войти",
      register: "Создать аккаунт",
      loginTitle: "Войдите в аккаунт",
      regTitle: "Начните учиться с MITS",
      loginSub: "Введите данные, чтобы продолжить",
      regSub: "Бесплатно · без кредитной карты",
      name: "Имя",
      namePh: "Максим Сухацкий",
      email: "Почта",
      emailPh: "name@example.com",
      pwd: "Пароль",
      pwdHint: "Минимум 8 символов",
      forgot: "Забыли пароль?",
      remember: "Запомнить меня",
      submitLogin: "Войти",
      submitReg: "Продолжить",
      or: "или",
      withGoogle: "Продолжить с Google",
      withGithub: "Продолжить с GitHub",
      noAcc: "Нет аккаунта?",
      hasAcc: "Уже есть аккаунт?",
      createOne: "Создать",
      signIn: "Войти",
      terms: "Нажимая «Продолжить», вы соглашаетесь с условиями и политикой конфиденциальности",
      benefit1: "3-стадийный RL-пайплайн обучения из GSPO → KTO → DPO",
      benefit2: "Символьная верификация решений через SymPy / ChemPy",
      benefit3: "40+ навыков, BKT + DKT knowledge tracing",
      benefit4: "5 STEM-доменов · 3 678 задач в бенчмарке",
      backHome: "Назад к демо",
      quote: "«Магия — это не талант. Это терпение, практика и правильный наставник.»",
      quoteAuthor: "— README MITS",
    },
    en: {
      welcome: "Welcome",
      welcomeSub: "A Socratic tutor for STEM — leads with questions, never just answers",
      login: "Sign in",
      register: "Create account",
      loginTitle: "Sign in to your account",
      regTitle: "Start learning with MITS",
      loginSub: "Enter your credentials to continue",
      regSub: "Free · no credit card required",
      name: "Name",
      namePh: "Maxim Sukhatskiy",
      email: "Email",
      emailPh: "name@example.com",
      pwd: "Password",
      pwdHint: "At least 8 characters",
      forgot: "Forgot your password?",
      remember: "Remember me",
      submitLogin: "Sign in",
      submitReg: "Continue",
      or: "or",
      withGoogle: "Continue with Google",
      withGithub: "Continue with GitHub",
      noAcc: "Don't have an account?",
      hasAcc: "Already have an account?",
      createOne: "Create one",
      signIn: "Sign in",
      terms: "By continuing, you agree to our Terms and Privacy Policy",
      benefit1: "3-stage RL training pipeline: GSPO → KTO → DPO",
      benefit2: "Symbolic verification via SymPy / ChemPy",
      benefit3: "40+ skills with BKT + DKT knowledge tracing",
      benefit4: "5 STEM domains · 3,678 problems in benchmark",
      backHome: "Back to demo",
      quote: "“Magic isn’t talent. It’s patience, practice, and the right mentor.”",
      quoteAuthor: "— MITS README",
    }
  };
  const x = L[lang];

  return (
    <div className="auth-shell">
      {/* Top bar with controls */}
      <div className="auth-top">
        <div className="auth-brand" onClick={() => setView("chat")} style={{cursor:'pointer'}}>
          <div className="brand-mark">M
            <svg style={{position:'absolute',inset:0,opacity:0.3}} viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="0.5">
              <circle cx="16" cy="16" r="12"/><circle cx="16" cy="16" r="8"/>
            </svg>
          </div>
          <span className="brand-name">MITS</span>
        </div>
        <span className="auth-back" onClick={() => setView("chat")}>{x.backHome}</span>
        <div style={{flex:1}}/>
        <div className="lang-toggle">
          <button className={lang === "ru" ? "active" : ""} onClick={() => setLang("ru")}>RU</button>
          <button className={lang === "en" ? "active" : ""} onClick={() => setLang("en")}>EN</button>
        </div>
        <button className="theme-toggle" onClick={() => setMode(mode === "light" ? "dark" : "light")}>
          {mode === "light"
            ? <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M6.5 1a7 7 0 1 0 8.5 8.5A6 6 0 0 1 6.5 1Z"/></svg>
            : <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="8" r="3"/><path strokeLinecap="round" d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.5 1.5M11.5 11.5 13 13M3 13l1.5-1.5M11.5 4.5 13 3"/></svg>}
        </button>
      </div>

      {/* Two-column layout */}
      <div className="auth-grid">
        {/* Left: brand storytelling */}
        <div className="auth-side">
          <div className="auth-side-inner">
            <div className="auth-tagline">
              <span className="status-dot"/>
              <span>{lang === "ru" ? "Открытая бета" : "Open beta"}</span>
            </div>
            <h1 className="auth-headline">{x.welcome}</h1>
            <p className="auth-headline-sub">{x.welcomeSub}</p>

            <div className="auth-benefits">
              {[x.benefit1, x.benefit2, x.benefit3, x.benefit4].map((b, i) => (
                <div key={i} className="auth-benefit">
                  <span className="auth-benefit-num">{String(i+1).padStart(2,"0")}</span>
                  <span>{b}</span>
                </div>
              ))}
            </div>

            <blockquote className="auth-quote">
              <p>{x.quote}</p>
              <cite>{x.quoteAuthor}</cite>
            </blockquote>
          </div>
        </div>

        {/* Right: form */}
        <div className="auth-form-wrap">
          <div className="auth-form">
            <div className="auth-switch">
              <button className={!isReg ? "active" : ""} onClick={() => setAuthMode("login")}>{x.login}</button>
              <button className={isReg ? "active" : ""} onClick={() => setAuthMode("register")}>{x.register}</button>
            </div>

            <h2 className="auth-form-title" key={"title-" + authMode}>{isReg ? x.regTitle : x.loginTitle}</h2>
            <p className="auth-form-sub" key={"sub-" + authMode}>{isReg ? x.regSub : x.loginSub}</p>

            <div className="auth-social">
              <button className="auth-social-btn">
                <svg viewBox="0 0 18 18" width="16" height="16">
                  <path fill="#EA4335" d="M9 3.5c1.6 0 3 .55 4.1 1.6L16 2.2C14.2.7 11.8 0 9 0 5.5 0 2.5 2 1 4.9l3.4 2.6C5.2 5.2 6.9 3.5 9 3.5z"/>
                  <path fill="#4285F4" d="M17.6 9.2c0-.6-.06-1.1-.18-1.7H9v3.5h4.8c-.2 1.1-.8 2-1.7 2.6l2.7 2.1c1.5-1.4 2.8-3.6 2.8-6.5z"/>
                  <path fill="#FBBC05" d="M4.4 10.7C4.3 10.1 4.2 9.6 4.2 9c0-.6.1-1.1.2-1.7L1 4.9C.4 6.2 0 7.6 0 9c0 1.5.4 2.9 1 4.1l3.4-2.4z"/>
                  <path fill="#34A853" d="M9 18c2.4 0 4.5-.8 6-2.2l-2.8-2.2c-.8.5-1.8.9-3.2.9-2.4 0-4.5-1.7-5.3-3.9L1 13.1C2.5 16 5.5 18 9 18z"/>
                </svg>
                {x.withGoogle}
              </button>
              <button className="auth-social-btn">
                {Icon.github}
                {x.withGithub}
              </button>
            </div>

            <div className="auth-divider"><span>{x.or}</span></div>

            <form className="auth-fields" key={authMode} onSubmit={(e) => e.preventDefault()}>
              {isReg && (
                <label className="auth-field">
                  <span>{x.name}</span>
                  <input type="text" placeholder={x.namePh}/>
                </label>
              )}
              <label className="auth-field">
                <span>{x.email}</span>
                <input type="email" placeholder={x.emailPh}/>
              </label>
              <label className="auth-field">
                <span style={{display:'flex',alignItems:'center',gap:8}}>
                  {x.pwd}
                  {!isReg && <a href="#" className="auth-link" onClick={e=>e.preventDefault()}>{x.forgot}</a>}
                </span>
                <div className="auth-pwd">
                  <input type={showPwd ? "text" : "password"} placeholder="••••••••"/>
                  <button type="button" onClick={() => setShowPwd(!showPwd)} aria-label="toggle">
                    {showPwd
                      ? <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"><path d="M2 8s2.5-5 6-5 6 5 6 5-2.5 5-6 5-6-5-6-5z"/><circle cx="8" cy="8" r="2"/></svg>
                      : <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"><path d="M2 8s2.5-5 6-5 6 5 6 5-2.5 5-6 5-6-5-6-5zM2 2l12 12"/></svg>}
                  </button>
                </div>
                {isReg && <span className="auth-hint">{x.pwdHint}</span>}
              </label>

              {!isReg && (
                <label className="auth-checkbox">
                  <input type="checkbox"/>
                  <span>{x.remember}</span>
                </label>
              )}

              <button type="submit" className="auth-submit">
                {isReg ? x.submitReg : x.submitLogin}
                <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M3 8h10m-4-4 4 4-4 4"/></svg>
              </button>
              {isReg && <p className="auth-terms">{x.terms}</p>}
            </form>

            <div className="auth-switch-text">
              {isReg ? x.hasAcc : x.noAcc}{" "}
              <a href="#" onClick={(e) => { e.preventDefault(); setAuthMode(isReg ? "login" : "register"); }}>
                {isReg ? x.signIn : x.createOne}
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------- Main App ----------
function ChatApp({ themeName: initialTheme = "aurora", initialLang = "ru", initialView = "chat" }) {
  const [lang, setLang] = useState(initialLang);
  const [view, setView] = useState(initialView);
  const [themeName, setThemeName] = useState(initialTheme);
  const [mode, setMode] = useState(themeName === "midnight" ? "dark" : "light");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [focusedGraphNode, setFocusedGraphNode] = useState(null);
  const t = I18N[lang];
  const P = window.MITS_PAGES || {};
  const CmdPalette = window.CommandPalette;
  const ShortcutBarC = window.ShortcutBar;

  // Global ⌘K / Ctrl+K — opens command palette
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault(); setPaletteOpen(o => !o);
      } else if (e.key === "Escape" && paletteOpen) {
        setPaletteOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [paletteOpen]);

  // Theme toggle support: when on Midnight + mode "light", switch to Daylight (light Midnight palette).
  // When on Daylight + mode "dark", switch back to Midnight.
  const effectiveTheme = useMemo(() => {
    if ((themeName === "midnight" || themeName === "daylight") && mode === "light") return "daylight";
    if ((themeName === "midnight" || themeName === "daylight") && mode === "dark") return "midnight";
    return themeName;
  }, [themeName, mode]);

  const renderPage = () => {
    if (view === "auth")      return <AuthView t={t} lang={lang} setLang={setLang} mode={mode} setMode={setMode} setView={setView}/>;
    if (view === "chat")      return <ChatView t={t} lang={lang} setLang={setLang} mode={mode} setMode={setMode}/>;
    const PageBody = ({ Comp, extraProps }) => (
      <>
        <main className="main">
          <StatusBar t={t} lang={lang} view={view}/>
          <Comp
            t={t} lang={lang} themeName={effectiveTheme}
            setLang={setLang}
            mode={mode} setMode={setMode}
            currentTheme={themeName} setCurrentTheme={setThemeName}
            {...(extraProps || {})}
          />
        </main>
        <ProjectRail t={t} lang={lang} themeName={effectiveTheme}/>
      </>
    );
    if (view === "tasks"     && P.TasksPage)     return <PageBody Comp={P.TasksPage}/>;
    if (view === "graph"     && P.GraphPage)     return <PageBody Comp={P.GraphPage} extraProps={{ focusNodeId: focusedGraphNode }}/>;
    if (view === "dashboard" && P.DashboardPage) return <PageBody Comp={P.DashboardPage}/>;
    if (view === "profile"   && P.ProfilePage)   return <PageBody Comp={P.ProfilePage}/>;
    if (view === "sources"   && P.SourcesPage)   return <PageBody Comp={P.SourcesPage}/>;
    if (view === "settings"  && P.SettingsPage)  return <PageBody Comp={P.SettingsPage}/>;
    return <ChatView t={t} lang={lang} setLang={setLang} mode={mode} setMode={setMode}/>;
  };

  // Auth view occupies the full app (no nav rail / sidebar)
  if (view === "auth") {
    return (
      <div className={"app theme-" + effectiveTheme + " app-auth"}>
        <div className="app-bg"><ThemeDecor theme={effectiveTheme}/></div>
        <React.Fragment key={view}>{renderPage()}</React.Fragment>
      </div>
    );
  }

  return (
    <div className={"app theme-" + effectiveTheme}>
      <div className="app-bg"><ThemeDecor theme={effectiveTheme}/></div>
      <NavRail t={t} view={view} setView={setView}/>
      <Sidebar t={t} lang={lang}/>
      <React.Fragment key={view}>{renderPage()}</React.Fragment>
      {ShortcutBarC && <ShortcutBarC lang={lang} view={view} setView={setView} openPalette={() => setPaletteOpen(true)}/>}
      {CmdPalette && (
        <CmdPalette
          open={paletteOpen} setOpen={setPaletteOpen}
          lang={lang}
          setView={setView}
          currentTheme={themeName} setCurrentTheme={setThemeName}
          onSelectNode={(id) => { setFocusedGraphNode(id); setTimeout(() => setFocusedGraphNode(null), 100); }}
        />
      )}
    </div>
  );
}

window.ChatApp = ChatApp;
