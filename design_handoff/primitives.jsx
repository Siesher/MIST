// ==============================================================
// Primitives — shared atomic components
// ==============================================================

// MITS logo mark — original geometric glyph (triangle prism + ring + core)
function MitsMark({ size = 28, animated = true }) {
  return (
    <span className="mits-mark" style={{ width: size, height: size }}>
      <svg viewBox="0 0 32 32" fill="none">
        <defs>
          <linearGradient id="mg1" x1="0" y1="0" x2="32" y2="32">
            <stop offset="0%" stopColor="#b026ff" />
            <stop offset="100%" stopColor="#f5e60a" />
          </linearGradient>
        </defs>
        {/* outer hex ring */}
        <polygon points="16,2 28,9 28,23 16,30 4,23 4,9"
          stroke="url(#mg1)" strokeWidth="1.3" fill="none"
          style={animated ? { animation: 'float 4s ease-in-out infinite' } : {}} />
        {/* inner triangle */}
        <polygon points="16,8 23,22 9,22"
          stroke="#b026ff" strokeWidth="1" fill="rgba(176,38,255,0.12)" />
        {/* core */}
        <circle cx="16" cy="18" r="2.2" fill="#f5e60a" style={{ filter: 'drop-shadow(0 0 3px #f5e60a)' }} />
        {/* tick marks */}
        <line x1="16" y1="2" x2="16" y2="5" stroke="#f5e60a" strokeWidth="1.2" />
        <line x1="4" y1="9" x2="7" y2="10.5" stroke="#b026ff" strokeWidth="1" />
        <line x1="28" y1="9" x2="25" y2="10.5" stroke="#b026ff" strokeWidth="1" />
      </svg>
    </span>
  );
}

// Typed text — prints a string char-by-char with blinking caret
function Typed({ text, speed = 14, className = "", onDone, caret = true }) {
  const [n, setN] = React.useState(0);
  React.useEffect(() => {
    setN(0);
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setN(i);
      if (i >= text.length) {
        clearInterval(id);
        onDone && onDone();
      }
    }, speed);
    return () => clearInterval(id);
  }, [text, speed]);
  const done = n >= text.length;
  return (
    <span className={className}>
      {text.slice(0, n)}
      {caret && !done && <span style={{ color: 'var(--yellow)', animation: 'blink 1s steps(2) infinite' }}>▊</span>}
    </span>
  );
}

// Glitch text
function Glitch({ children, as: Tag = "span", className = "" }) {
  // Only use text content as data-text (avoid wrapping divs)
  const text = typeof children === 'string' ? children :
    (children?.props?.children && typeof children.props.children === 'string' ? children.props.children : '');
  return (
    <span className={`glitch ${className}`} data-text={text}>
      {children}
    </span>
  );
}

// Status bar across the top of the app (terminal style)
function StatusBar({ t, lang, setLang, view, theme, setTheme }) {
  const [time, setTime] = React.useState(new Date());
  React.useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const hhmmss = time.toTimeString().slice(0, 8);
  return (
    <div data-status-bar className="row" style={{
      height: 32, padding: '0 18px', gap: 28,
      borderBottom: '1px solid var(--line)',
      background: 'var(--bg-0)',
      fontSize: 10, letterSpacing: '0.18em', textTransform: 'uppercase',
      color: 'var(--text-dim)',
      position: 'relative', zIndex: 10,
      whiteSpace: 'nowrap', overflow: 'hidden',
    }}>
      <div className="row gap-2">
        <span className="dot g" />
        <span className="y">{t('online')}</span>
      </div>
      <span>qwen3.5-9b</span>
      <span>lat <span className="y">64ms</span></span>
      <span>tok <span style={{ color: 'var(--text)' }}>12.8k</span></span>
      <div className="flex-1" />
      <span><span className="ghost">view ›</span> <span className="v">{view}</span></span>
      <button className="btn-ghost btn" style={{ padding: '2px 6px', fontSize: 10 }}
        onClick={() => setLang(lang === 'ru' ? 'en' : 'ru')}>
        {lang === 'ru' ? 'RU' : 'EN'} ⇄
      </button>
      <span>{hhmmss}</span>
    </div>
  );
}

// Sidebar nav
function Sidebar({ t, view, setView, onLogout }) {
  const [pinned, setPinned] = React.useState(() => localStorage.getItem('mits_sidebar_pinned') === '1');
  const [hovered, setHovered] = React.useState(false);
  const open = pinned || hovered;

  React.useEffect(() => {
    localStorage.setItem('mits_sidebar_pinned', pinned ? '1' : '0');
  }, [pinned]);

  const items = [
    { id: 'chat',    icon: '◈', label: t('nav_chat') },
    { id: 'graph',   icon: '◎', label: t('nav_graph') },
    { id: 'tasks',   icon: '◇', label: t('nav_tasks') },
    { id: 'sources', icon: '▤', label: t('nav_sources') },
    { id: 'profile', icon: '⊙', label: t('nav_profile') },
  ];
  return (
    <>
      {/* Hover-trigger strip on left edge */}
      <div
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          position: 'fixed', left: 0, top: 32, bottom: 0, width: 12,
          zIndex: 9,
        }}
      />
      {/* Thin rail indicator when closed */}
      {!open && (
        <div style={{
          position: 'fixed', left: 0, top: '50%', transform: 'translateY(-50%)',
          width: 3, height: 42, borderRadius: '0 3px 3px 0',
          background: 'var(--violet)', opacity: 0.25,
          pointerEvents: 'none', zIndex: 8,
        }} />
      )}

    <aside
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
      width: open ? 240 : 0, flex: open && pinned ? '0 0 240px' : '0 0 0px',
      position: pinned ? 'relative' : 'fixed',
      left: 0, top: pinned ? 'auto' : 32, bottom: pinned ? 'auto' : 0,
      height: pinned ? 'auto' : 'calc(100vh - 32px)',
      transform: open ? 'translateX(0)' : 'translateX(-100%)',
      transition: 'transform 220ms cubic-bezier(0.22, 1, 0.36, 1), width 220ms cubic-bezier(0.22, 1, 0.36, 1)',
      borderRight: '1px solid var(--line)',
      background: pinned ? 'rgba(18, 10, 31, 0.6)' : 'rgba(14, 8, 24, 0.92)',
      backdropFilter: 'blur(20px) saturate(1.2)',
      WebkitBackdropFilter: 'blur(20px) saturate(1.2)',
      display: 'flex', flexDirection: 'column',
      zIndex: 10,
      boxShadow: pinned ? 'none' : '4px 0 32px rgba(0,0,0,0.5)',
      overflow: 'hidden',
    }}>
      <div style={{ padding: '18px 16px 14px', borderBottom: '1px solid var(--line)' }}>
        <div className="row gap-3">
          <MitsMark size={34} />
          <div className="col">
            <Glitch className="display" as="div" >
              <span style={{ fontSize: 18, fontWeight: 600, letterSpacing: '0.04em' }}>{t('brand')}</span>
            </Glitch>
            <span className="ghost" style={{ fontSize: 9, letterSpacing: '0.22em' }}>v.2.6.1</span>
          </div>
        </div>
      </div>

      <nav style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {items.map(it => {
          const active = view === it.id;
          return (
            <button key={it.id}
              onClick={() => setView(it.id)}
              style={{
                textAlign: 'left',
                background: active ? 'rgba(176,38,255,0.12)' : 'transparent',
                border: '1px solid ' + (active ? 'var(--line-hi)' : 'transparent'),
                color: active ? 'var(--text)' : 'var(--text-dim)',
                padding: '9px 12px',
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                letterSpacing: '0.08em',
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 10,
                position: 'relative',
                transition: 'all 100ms',
              }}
              onMouseEnter={e => { if (!active) e.currentTarget.style.color = 'var(--violet)'; }}
              onMouseLeave={e => { if (!active) e.currentTarget.style.color = 'var(--text-dim)'; }}
            >
              <span style={{ color: active ? 'var(--yellow)' : 'var(--violet)', fontSize: 14 }}>{it.icon}</span>
              <span style={{ textTransform: 'uppercase', letterSpacing: '0.12em' }}>{it.label}</span>
              {active && <span style={{
                position: 'absolute', right: 10, color: 'var(--yellow)', fontSize: 10
              }}>›</span>}
            </button>
          );
        })}
      </nav>

      {/* Session history — flavor */}
      <div style={{ padding: '8px 14px', borderTop: '1px solid var(--line)', marginTop: 4 }}>
        <div className="uppercase ghost" style={{ fontSize: 9, marginBottom: 8, letterSpacing: '0.2em' }}>
          › {t('sessions')}
        </div>
        <div className="col gap-1" style={{ fontSize: 11 }}>
          {['Интегралы по частям','Маятник Фуко','pKa фенола','Мемы о BKT'].map((s, i) => (
            <div key={i} style={{
              color: i === 0 ? 'var(--text)' : 'var(--text-muted)',
              padding: '4px 8px',
              borderLeft: '1px solid ' + (i === 0 ? 'var(--yellow)' : 'transparent'),
              cursor: 'pointer',
            }}>
              {i === 0 ? '▸' : '·'} {s}
            </div>
          ))}
        </div>
      </div>

      <div className="flex-1" />

      <div style={{ padding: 12, borderTop: '1px solid var(--line)', display: 'flex', gap: 6 }}>
        <button className="btn-ghost btn" style={{ flex: 1, justifyContent: 'center', fontSize: 10 }}
          onClick={onLogout}>
          ⏻ {t('nav_logout')}
        </button>
        <button className="btn-ghost btn" title={pinned ? 'Unpin sidebar' : 'Pin sidebar'}
          style={{ padding: '6px 10px', fontSize: 11 }}
          onClick={() => setPinned(p => !p)}>
          {pinned ? '⇤' : '⇥'}
        </button>
      </div>
    </aside>
    </>
  );
}

// Tweaks panel
function TweaksPanel({ tweaks, setTweaks, visible, onClose }) {
  if (!visible) return null;
  const updateVar = (k, v) => {
    setTweaks(prev => ({ ...prev, [k]: v }));
    if (k === 'glow') document.documentElement.style.setProperty('--glow-size', v + 'px');
    if (k === 'scanlines') document.documentElement.style.setProperty('--scanline-opacity', v);
    window.parent.postMessage({ type: '__edit_mode_set_keys', edits: { [k]: v } }, '*');
  };
  return (
    <div style={{
      position: 'fixed', bottom: 16, right: 16,
      width: 300,
      background: 'var(--surface-hi)',
      border: '1px solid var(--violet)',
      boxShadow: '0 0 24px rgba(176,38,255,0.4)',
      padding: 14, zIndex: 9999,
      fontSize: 11,
    }} className="cornered">
      <span className="tl" /><span className="br" />
      <div className="row" style={{ marginBottom: 10 }}>
        <span className="neon-v uppercase" style={{ letterSpacing: '0.2em', fontSize: 11 }}>⚙ Tweaks</span>
        <div className="flex-1" />
        <button onClick={onClose} className="btn-ghost btn" style={{ padding: '2px 6px' }}>✕</button>
      </div>

      <div className="col gap-3">
        <div>
          <div className="uppercase ghost" style={{ fontSize: 9, marginBottom: 6 }}>Theme variant</div>
          <div className="row gap-1" style={{ flexWrap: 'wrap' }}>
            {[
              { id: 'terminal', label: 'Terminal' },
              { id: 'minimal',  label: 'Minimal' },
              { id: 'grimoire', label: 'Grimoire' },
              { id: 'neo',      label: 'Mono' },
              { id: 'acid',     label: 'Acid' },
            ].map(v => (
              <button key={v.id}
                onClick={() => updateVar('theme', v.id)}
                style={{
                  flex: '1 1 44%',
                  padding: '6px 4px',
                  border: '1px solid ' + (tweaks.theme === v.id ? 'var(--yellow)' : 'var(--line)'),
                  background: tweaks.theme === v.id ? 'rgba(240,217,74,0.1)' : 'transparent',
                  color: tweaks.theme === v.id ? 'var(--yellow)' : 'var(--text-dim)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  cursor: 'pointer',
                }}>
                {v.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="row" style={{ marginBottom: 4 }}>
            <span className="uppercase ghost" style={{ fontSize: 9 }}>Neon glow</span>
            <div className="flex-1" />
            <span className="y" style={{ fontSize: 10 }}>{tweaks.glow}px</span>
          </div>
          <input type="range" min="0" max="40" step="2" value={tweaks.glow}
            onChange={e => updateVar('glow', +e.target.value)}
            style={{ width: '100%', accentColor: 'var(--violet)' }} />
        </div>

        <div>
          <div className="row" style={{ marginBottom: 4 }}>
            <span className="uppercase ghost" style={{ fontSize: 9 }}>Scanlines</span>
            <div className="flex-1" />
            <span className="y" style={{ fontSize: 10 }}>{Math.round(tweaks.scanlines * 100)}%</span>
          </div>
          <input type="range" min="0" max="1" step="0.05" value={tweaks.scanlines}
            onChange={e => updateVar('scanlines', +e.target.value)}
            style={{ width: '100%', accentColor: 'var(--violet)' }} />
        </div>

        <div>
          <label className="row gap-2" style={{ cursor: 'pointer' }}>
            <input type="checkbox" checked={tweaks.glitch}
              onChange={e => updateVar('glitch', e.target.checked)} />
            <span className="uppercase" style={{ fontSize: 10, letterSpacing: '0.14em' }}>
              Glitch on titles
            </span>
          </label>
        </div>
        <div>
          <label className="row gap-2" style={{ cursor: 'pointer' }}>
            <input type="checkbox" checked={tweaks.particles}
              onChange={e => updateVar('particles', e.target.checked)} />
            <span className="uppercase" style={{ fontSize: 10, letterSpacing: '0.14em' }}>
              Particles background
            </span>
          </label>
        </div>
      </div>
    </div>
  );
}

// Particle field — small violet/yellow dots drifting upward
function Particles({ enabled }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (!enabled) return;
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let running = true;
    const resize = () => {
      canvas.width = canvas.offsetWidth * devicePixelRatio;
      canvas.height = canvas.offsetHeight * devicePixelRatio;
    };
    resize();
    window.addEventListener('resize', resize);
    const particles = Array.from({ length: 60 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vy: -0.2 - Math.random() * 0.4,
      vx: (Math.random() - 0.5) * 0.1,
      r: 0.5 + Math.random() * 1.2,
      c: Math.random() > 0.8 ? '#f5e60a' : '#b026ff',
      a: 0.2 + Math.random() * 0.5,
    }));
    const loop = () => {
      if (!running) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        if (p.y < 0) { p.y = canvas.height; p.x = Math.random() * canvas.width; }
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * devicePixelRatio, 0, Math.PI * 2);
        ctx.fillStyle = p.c;
        ctx.globalAlpha = p.a;
        ctx.shadowColor = p.c;
        ctx.shadowBlur = 8;
        ctx.fill();
      });
      requestAnimationFrame(loop);
    };
    loop();
    return () => { running = false; window.removeEventListener('resize', resize); };
  }, [enabled]);
  if (!enabled) return null;
  return <canvas ref={ref} style={{
    position: 'fixed', inset: 0, width: '100%', height: '100%',
    pointerEvents: 'none', zIndex: 1, opacity: 0.6,
  }} />;
}

Object.assign(window, { MitsMark, Typed, Glitch, StatusBar, Sidebar, TweaksPanel, Particles });
