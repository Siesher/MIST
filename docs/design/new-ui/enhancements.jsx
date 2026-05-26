// MITS — Command palette (⌘K) + contextual Shortcut bar
// Both components are surfaced on `window` so chat-app.jsx can mount them.

const { useState: useEX, useEffect: useEffectEX, useMemo: useMemoEX, useRef: useRefEX } = React;

// Localized graph-node labels (mirrors helper in pages.jsx)
function nodeLabelEX(n, lang) {
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

// ===== Command Palette =====
function CommandPalette({ open, setOpen, lang, setView, setCurrentTheme, currentTheme, onSelectNode }) {
  const [q, setQ] = useEX("");
  const [active, setActive] = useEX(0);
  const inputRef = useRefEX(null);
  const { GRAPH_NODES, SESSIONS, I18N } = window.MITS_DATA || {};
  const t = I18N && I18N[lang];

  useEffectEX(() => {
    if (open) {
      setQ("");
      setActive(0);
      setTimeout(() => inputRef.current && inputRef.current.focus(), 40);
    }
  }, [open]);

  const pages = [
    { id: "chat",      icon: "▰",  label: lang === "ru" ? "Чат" : "Chat",                    shortcut: "G C" },
    { id: "tasks",     icon: "▦",  label: lang === "ru" ? "Каталог задач" : "Tasks",         shortcut: "G T" },
    { id: "graph",     icon: "◌",  label: lang === "ru" ? "Граф знаний" : "Knowledge graph", shortcut: "G G" },
    { id: "dashboard", icon: "▣",  label: lang === "ru" ? "Аналитика" : "Dashboard",         shortcut: "G D" },
    { id: "sources",   icon: "≣",  label: lang === "ru" ? "Источники" : "Sources",           shortcut: "G S" },
    { id: "profile",   icon: "◉",  label: lang === "ru" ? "Профиль" : "Profile",             shortcut: "G P" },
  ];
  const themes = [
    { id: "aurora",   label: "Aurora",   desc: lang === "ru" ? "Чистая, минимальная" : "Clean minimal" },
    { id: "grimoire", label: "Grimoire", desc: lang === "ru" ? "Editorial, тёплая" : "Editorial, warm" },
    { id: "midnight", label: "Midnight", desc: lang === "ru" ? "Тёмная, светящаяся" : "Dark, glowing" },
  ];

  const items = useMemoEX(() => {
    const ql = q.trim().toLowerCase();
    const m = (s) => !ql || (s || "").toLowerCase().includes(ql);
    const out = [];

    pages.forEach(p => {
      if (m(p.label) || m(p.id)) out.push({
        id: "pg-" + p.id, icon: p.icon, label: p.label,
        kind: lang === "ru" ? "Страница" : "Page",
        shortcut: p.shortcut, action: () => setView(p.id),
      });
    });

    (GRAPH_NODES || []).forEach(n => {
      const lbl = nodeLabelEX(n, lang);
      if (m(lbl) || m(n.id) || m(n.d)) out.push({
        id: "nd-" + n.id, icon: "◯", label: lbl,
        meta: `${n.d} · ${Math.round(n.m * 100)}%`,
        kind: lang === "ru" ? "Тема графа" : "Topic",
        action: () => { setView("graph"); onSelectNode && onSelectNode(n.id); },
      });
    });

    (SESSIONS || []).slice(0, 5).forEach(s => {
      const title = (t && t[s.key]) || s.key;
      if (m(title)) out.push({
        id: "se-" + s.id, icon: "↺", label: title,
        meta: s.time, kind: lang === "ru" ? "Недавняя сессия" : "Recent session",
        action: () => setView("chat"),
      });
    });

    themes.forEach(th => {
      if (m(th.label) || m(th.id) || m(lang === "ru" ? "тема" : "theme")) out.push({
        id: "th-" + th.id, icon: "◐",
        label: (lang === "ru" ? "Тема — " : "Theme — ") + th.label,
        meta: th.desc,
        kind: lang === "ru" ? "Внешний вид" : "Appearance",
        action: () => setCurrentTheme && setCurrentTheme(th.id),
        selected: currentTheme === th.id,
      });
    });

    // Verbs / actions
    if (m("new") || m("новый") || m("чат") || m("chat")) out.push({
      id: "ac-new", icon: "＋",
      label: lang === "ru" ? "Новый чат" : "New chat",
      kind: lang === "ru" ? "Действие" : "Action",
      shortcut: "⌘ N", action: () => setView("chat"),
    });
    if (m("settings") || m("настройки")) out.push({
      id: "ac-set", icon: "⚙",
      label: lang === "ru" ? "Открыть настройки" : "Open settings",
      kind: lang === "ru" ? "Действие" : "Action",
      action: () => setView("settings"),
    });

    return out.slice(0, 14);
  }, [q, lang, currentTheme]);

  useEffectEX(() => { setActive(0); }, [q]);

  const run = (it) => { if (it) { it.action(); setOpen(false); } };
  const onKeyDown = (e) => {
    if (e.key === "Escape") { e.preventDefault(); setOpen(false); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setActive(a => Math.min(items.length - 1, a + 1)); }
    else if (e.key === "ArrowUp")   { e.preventDefault(); setActive(a => Math.max(0, a - 1)); }
    else if (e.key === "Enter")     { e.preventDefault(); run(items[active]); }
  };

  if (!open) return null;

  // Group items by kind for visual section breaks
  let lastKind = null;
  return (
    <div className="palette-scrim" onClick={() => setOpen(false)}>
      <div className="palette" onClick={e => e.stopPropagation()} onKeyDown={onKeyDown}>
        <div className="palette-input">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <circle cx="7" cy="7" r="4.5"/><path d="m11 11 3 3"/>
          </svg>
          <input
            ref={inputRef}
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder={lang === "ru" ? "Перейти к странице, теме или сессии…" : "Jump to a page, topic, or session…"}
          />
          <kbd className="palette-esc">esc</kbd>
        </div>
        <div className="palette-list" role="listbox">
          {items.length === 0 && (
            <div className="palette-empty">
              <div className="palette-empty-mark">◌</div>
              <div>
                <div>{lang === "ru" ? "Ничего не нашлось." : "Nothing matched."}</div>
                <div className="palette-empty-hint">
                  {lang === "ru" ? "Попробуйте «граф», «производные» или «midnight»." : "Try \"graph\", \"derivatives\", or \"midnight\"."}
                </div>
              </div>
            </div>
          )}
          {items.map((it, i) => {
            const sep = it.kind !== lastKind;
            lastKind = it.kind;
            return (
              <React.Fragment key={it.id}>
                {sep && <div className="palette-section">{it.kind}</div>}
                <div
                  className={"palette-row " + (i === active ? "active " : "") + (it.selected ? "selected" : "")}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => run(it)}>
                  <span className="palette-icon">{it.icon}</span>
                  <span className="palette-label">
                    {it.label}
                    {it.meta && <span className="palette-meta"> · {it.meta}</span>}
                  </span>
                  {it.selected && <span className="palette-check">✓</span>}
                  {it.shortcut && <kbd className="palette-shortcut">{it.shortcut}</kbd>}
                  <span className="palette-arrow">↵</span>
                </div>
              </React.Fragment>
            );
          })}
        </div>
        <div className="palette-foot">
          <span><kbd>↑</kbd><kbd>↓</kbd> {lang === "ru" ? "переход" : "navigate"}</span>
          <span><kbd>↵</kbd> {lang === "ru" ? "выбрать" : "open"}</span>
          <span><kbd>esc</kbd> {lang === "ru" ? "закрыть" : "close"}</span>
          <span className="palette-foot-brand">MITS · ⌘K</span>
        </div>
      </div>
    </div>
  );
}

// ===== Contextual Shortcut Bar =====
function ShortcutBar({ lang, view, setView, openPalette }) {
  // Hide on the chat view — the composer already has its own hint strip.
  if (view === "chat" || view === "auth") return null;
  const items = [
    { keys: ["⌘", "K"], label: lang === "ru" ? "Команды" : "Commands", onClick: openPalette, primary: true },
    { keys: ["G"], label: lang === "ru" ? "Граф" : "Graph",             onClick: () => setView("graph") },
    { keys: ["T"], label: lang === "ru" ? "Задачи" : "Tasks",           onClick: () => setView("tasks") },
    { keys: ["D"], label: lang === "ru" ? "Аналитика" : "Dashboard",    onClick: () => setView("dashboard") },
    { keys: ["S"], label: lang === "ru" ? "Источники" : "Sources",      onClick: () => setView("sources") },
    { keys: ["C"], label: lang === "ru" ? "Чат" : "Chat",               onClick: () => setView("chat") },
  ];
  return (
    <div className="shortcut-bar">
      {items.map((it, i) => (
        <button key={i} className={"sc-chip " + (it.primary ? "primary" : "")} onClick={it.onClick}>
          <span className="sc-keys">{it.keys.map((k, j) => <kbd key={j}>{k}</kbd>)}</span>
          <span className="sc-label">{it.label}</span>
        </button>
      ))}
    </div>
  );
}

Object.assign(window, { CommandPalette, ShortcutBar });
