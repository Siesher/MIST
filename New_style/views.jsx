// ==============================================================
// Profile + Sources + Tasks views + Auth screen
// ==============================================================

function ProfileView({ t, lang }) {
  const stats = [
    ['sessions', 147],
    ['problems', 892],
    ['streak', '14 days'],
    ['mastery avg', '62%'],
  ];
  const recent = lang === 'ru' ? [
    { t: '14:32', dom: 'math', ev: 'Решил интеграл ∫x·sin(x)dx с 2 подсказками' },
    { t: '13:18', dom: 'cs',   ev: 'DP задача: longest palindromic subseq · O(n²)' },
    { t: '11:05', dom: 'phys', ev: 'Маятник: период, малые колебания' },
    { t: '09:41', dom: 'chem', ev: 'pKa аминокислоты — гидролиз' },
  ] : [
    { t: '14:32', dom: 'math', ev: 'Solved ∫x·sin(x)dx with 2 hints' },
    { t: '13:18', dom: 'cs',   ev: 'DP problem: longest palindromic subseq · O(n²)' },
    { t: '11:05', dom: 'phys', ev: 'Pendulum: period under small oscillations' },
    { t: '09:41', dom: 'chem', ev: 'pKa of amino acid — hydrolysis' },
  ];
  return (
    <div className="flex-1" style={{ overflowY: 'auto', padding: 24 }}>
      <div className="row gap-4" style={{ marginBottom: 28 }}>
        <div style={{
          width: 96, height: 96, flex: '0 0 96px',
          border: '1px solid var(--violet)',
          background: 'linear-gradient(135deg, rgba(176,38,255,0.2), rgba(245,230,10,0.1))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--font-display)', fontSize: 40, fontWeight: 700,
          color: 'var(--yellow)',
          boxShadow: 'var(--glow-violet)',
          position: 'relative',
        }} className="cornered">
          <span className="tl" /><span className="br" />
          МС
        </div>
        <div className="col flex-1">
          <Glitch className="display" as="div">
            <span style={{ fontSize: 26, fontWeight: 600, color: 'var(--text)' }}>Максим Сухацкий</span>
          </Glitch>
          <div className="ghost" style={{ fontSize: 11, letterSpacing: '0.14em', marginTop: 4 }}>
            // siesher · МГТУ им. Баумана · apprentice → journeyman
          </div>
          <div className="row gap-2" style={{ marginTop: 10 }}>
            <span className="chip on">◆ GUIDED MODE</span>
            <span className="chip v">STREAK · 14</span>
            <span className="chip">{lang === 'ru' ? 'РУССКИЙ · EN' : 'RUSSIAN · EN'}</span>
          </div>
        </div>
        <button className="btn">⚙ EDIT</button>
      </div>

      {/* Stats */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 1, background: 'var(--line-hi)',
        border: '1px solid var(--line-hi)', marginBottom: 28,
      }}>
        {stats.map(([k, v]) => (
          <div key={k} style={{ background: 'var(--surface)', padding: 18 }}>
            <div className="ghost uppercase" style={{ fontSize: 10, letterSpacing: '0.18em' }}>{k}</div>
            <div className="display" style={{ fontSize: 26, color: 'var(--text)', marginTop: 4, fontWeight: 600 }}>{v}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 24 }}>
        {/* Timeline */}
        <div>
          <div className="uppercase ghost" style={{ fontSize: 10, letterSpacing: '0.22em', marginBottom: 12 }}>
            › {lang === 'ru' ? 'ПОСЛЕДНЯЯ АКТИВНОСТЬ' : 'RECENT ACTIVITY'}
          </div>
          <div className="col" style={{ position: 'relative', paddingLeft: 16 }}>
            <div style={{
              position: 'absolute', top: 6, bottom: 6, left: 4,
              width: 1, background: 'var(--line-hi)',
            }} />
            {recent.map((r, i) => (
              <div key={i} className="row gap-3" style={{ padding: '10px 0 10px 16px', position: 'relative' }}>
                <div style={{
                  position: 'absolute', left: -1, top: 16,
                  width: 9, height: 9,
                  background: DOMAIN_COLOR[r.dom] || 'var(--violet)',
                  boxShadow: `0 0 6px ${DOMAIN_COLOR[r.dom] || '#b026ff'}`,
                }} />
                <span className="mono y" style={{ fontSize: 10, letterSpacing: '0.1em', width: 40 }}>{r.t}</span>
                <span className="chip" style={{ fontSize: 9 }}>{r.dom.toUpperCase()}</span>
                <span style={{ fontSize: 12, color: 'var(--text)' }}>{r.ev}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Side — emotion + focus */}
        <div className="col gap-4">
          <div className="panel" style={{ padding: 14 }}>
            <div className="uppercase ghost" style={{ fontSize: 10, letterSpacing: '0.2em', marginBottom: 10 }}>
              › {t('emotion')}
            </div>
            <div className="row gap-2" style={{ marginBottom: 10 }}>
              <span className="neon-y" style={{ fontSize: 22 }}>● focused</span>
            </div>
            <div className="ghost" style={{ fontSize: 10 }}>
              RuBERT detector · conf 0.84
            </div>
          </div>

          <div className="panel" style={{ padding: 14 }}>
            <div className="uppercase ghost" style={{ fontSize: 10, letterSpacing: '0.2em', marginBottom: 10 }}>
              › {t('focus')} · week
            </div>
            <svg width="100%" height="80" viewBox="0 0 220 80">
              {[32, 58, 45, 72, 68, 88, 62].map((v, i) => (
                <rect key={i} x={i * 30 + 4} y={80 - v} width="22" height={v}
                  fill={i === 5 ? 'var(--yellow)' : 'var(--violet)'}
                  opacity={i === 5 ? 1 : 0.7}
                  style={{ filter: 'drop-shadow(0 0 4px currentColor)' }}
                />
              ))}
            </svg>
            <div className="row" style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.1em' }}>
              {['M','T','W','T','F','S','S'].map((d, i) => <span key={i} style={{ flex: 1, textAlign: 'center' }}>{d}</span>)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const SOURCES = [
  { name: 'Demidovich — Calculus Problems', kind: 'textbook', chunks: 12483, status: 'indexed', updated: '2d', bar: 1.0 },
  { name: 'Irodov — Physics Problems',       kind: 'textbook', chunks: 8976,  status: 'indexed', updated: '5d', bar: 1.0 },
  { name: 'CLRS — Intro to Algorithms',      kind: 'textbook', chunks: 14220, status: 'indexed', updated: '1w', bar: 1.0 },
  { name: 'Course notes · MSU Linear Algebra', kind: 'notes', chunks: 2140,  status: 'indexed', updated: '12h', bar: 1.0 },
  { name: 'MGSM-Russian benchmark',           kind: 'bench',  chunks: 3678,  status: 'active',  updated: 'live', bar: 0.9 },
  { name: 'arXiv · KTO / DPO papers (27)',    kind: 'papers', chunks: 412,   status: 'indexed', updated: '3w', bar: 1.0 },
  { name: 'Custom — user uploads',            kind: 'upload', chunks: 118,   status: 'syncing', updated: 'now', bar: 0.42 },
  { name: 'SymPy documentation',              kind: 'tool',   chunks: 1892,  status: 'indexed', updated: '2w', bar: 1.0 },
];

function SourcesView({ t, lang }) {
  return (
    <div className="flex-1" style={{ overflowY: 'auto', padding: 24 }}>
      <div className="row" style={{ marginBottom: 20 }}>
        <div>
          <Glitch className="display" as="div">
            <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: '0.06em' }}>{t('sources_title')}</span>
          </Glitch>
          <div className="ghost" style={{ fontSize: 11, letterSpacing: '0.14em', marginTop: 4 }}>
            // ChromaDB · sentence-transformers · 43,919 chunks indexed
          </div>
        </div>
        <div className="flex-1" />
        <button className="btn btn-primary">＋ {lang === 'ru' ? 'ДОБАВИТЬ' : 'ADD SOURCE'}</button>
      </div>

      {/* Tool chain */}
      <div className="panel cornered" style={{ padding: 14, marginBottom: 22 }}>
        <span className="tl" /><span className="br" />
        <div className="uppercase ghost" style={{ fontSize: 9, letterSpacing: '0.22em', marginBottom: 10 }}>
          › RETRIEVAL PIPELINE
        </div>
        <div className="row gap-2" style={{ flexWrap: 'wrap' }}>
          {['query', 'embed', 'search · top-12', 'rerank · bge', 'compress', 'context · ≤8k', 'tutor agent'].map((s, i) => (
            <React.Fragment key={s}>
              <div style={{
                padding: '6px 12px',
                border: '1px solid var(--line-hi)',
                background: i === 2 ? 'rgba(245,230,10,0.08)' : 'rgba(176,38,255,0.06)',
                fontSize: 11,
                color: i === 2 ? 'var(--yellow)' : 'var(--text)',
                letterSpacing: '0.08em',
              }}>
                <span className="ghost mono" style={{ marginRight: 6 }}>{String(i).padStart(2, '0')}</span>
                {s}
              </div>
              {i < 6 && <span className="v">→</span>}
            </React.Fragment>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
        {SOURCES.map(s => (
          <div key={s.name} className="panel cornered" style={{ padding: 14, position: 'relative' }}>
            <span className="tl" /><span className="br" />
            <div className="row gap-2" style={{ marginBottom: 6 }}>
              <span className="chip v">{s.kind.toUpperCase()}</span>
              <div className="flex-1" />
              <span className={"chip " + (s.status === 'indexed' ? 'on' : s.status === 'syncing' ? 'v' : '')}>
                {s.status === 'syncing' && <span className="dot v" />}
                {s.status === 'indexed' && '✓ '}
                {s.status.toUpperCase()}
              </span>
            </div>
            <div className="display" style={{ fontSize: 14, color: 'var(--text)', marginBottom: 8 }}>
              {s.name}
            </div>
            <div className="row gap-4" style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10 }}>
              <span><span className="ghost">chunks</span> <span className="y">{s.chunks.toLocaleString()}</span></span>
              <span><span className="ghost">updated</span> {s.updated}</span>
            </div>
            <div style={{ height: 4, background: 'rgba(176,38,255,0.12)', position: 'relative' }}>
              <div style={{
                position: 'absolute', top: 0, left: 0, bottom: 0,
                width: `${s.bar * 100}%`,
                background: s.status === 'syncing' ? 'var(--yellow)' : 'var(--violet)',
                boxShadow: s.status === 'syncing' ? '0 0 6px var(--yellow)' : '0 0 6px var(--violet)',
                animation: s.status === 'syncing' ? 'pulse-v 1.2s infinite' : 'none',
              }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TasksView({ t, lang }) {
  const tasks = lang === 'ru' ? [
    { d: 'math', diff: 'lvl 2', t: 'Интеграл по частям: ∫x·eˣ dx', tags: ['integration', 'IBP'], rate: 0.58 },
    { d: 'cs',   diff: 'lvl 3', t: 'Количество способов разменять сумму N монетами', tags: ['DP', 'coin-change'], rate: 0.44 },
    { d: 'phys', diff: 'lvl 2', t: 'Брусок на наклонной с трением — найти ускорение', tags: ['mechanics'], rate: 0.67 },
    { d: 'chem', diff: 'lvl 1', t: 'pH раствора слабой кислоты HA, Ka = 1.8·10⁻⁵', tags: ['equilibrium'], rate: 0.52 },
    { d: 'math', diff: 'lvl 3', t: 'Собственные значения матрицы 3×3', tags: ['linalg'], rate: 0.36 },
    { d: 'bio',  diff: 'lvl 2', t: 'Расчёт частот аллелей по Харди–Вайнбергу', tags: ['genetics'], rate: 0.41 },
  ] : [
    { d: 'math', diff: 'lvl 2', t: 'Integration by parts: ∫x·eˣ dx', tags: ['integration', 'IBP'], rate: 0.58 },
    { d: 'cs',   diff: 'lvl 3', t: 'Number of ways to make change of N', tags: ['DP', 'coin-change'], rate: 0.44 },
    { d: 'phys', diff: 'lvl 2', t: 'Block on incline with friction — find acceleration', tags: ['mechanics'], rate: 0.67 },
    { d: 'chem', diff: 'lvl 1', t: 'pH of weak acid HA, Ka = 1.8·10⁻⁵', tags: ['equilibrium'], rate: 0.52 },
    { d: 'math', diff: 'lvl 3', t: 'Eigenvalues of a 3×3 matrix', tags: ['linalg'], rate: 0.36 },
    { d: 'bio',  diff: 'lvl 2', t: 'Allele frequencies via Hardy–Weinberg', tags: ['genetics'], rate: 0.41 },
  ];
  return (
    <div className="flex-1" style={{ overflowY: 'auto', padding: 24 }}>
      <div className="row" style={{ marginBottom: 20 }}>
        <div>
          <Glitch className="display" as="div">
            <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: '0.06em' }}>
              {lang === 'ru' ? 'ЗАДАЧНИК' : 'TASK BANK'}
            </span>
          </Glitch>
          <div className="ghost" style={{ fontSize: 11, marginTop: 4 }}>
            // 3 678 curated · 40+ skills · adaptive difficulty
          </div>
        </div>
        <div className="flex-1" />
        <button className="btn btn-primary">⬢ {lang === 'ru' ? 'СГЕНЕРИРОВАТЬ' : 'GENERATE'}</button>
      </div>
      <div className="col gap-2">
        {tasks.map((tk, i) => (
          <div key={i} className="row gap-3 panel" style={{
            padding: 14, alignItems: 'center', cursor: 'pointer',
          }}
            onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--violet)'}
            onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--line)'}
          >
            <span style={{
              width: 30, height: 30, background: DOMAIN_COLOR[tk.d],
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#05050a', fontSize: 11, fontWeight: 700,
            }}>{tk.d.toUpperCase().slice(0, 2)}</span>
            <span className="chip">{tk.diff.toUpperCase()}</span>
            <span style={{ flex: 1, color: 'var(--text)', fontSize: 13 }}>{tk.t}</span>
            <div className="row gap-1">
              {tk.tags.map(g => <span key={g} className="chip v">{g}</span>)}
            </div>
            <span className="mono y" style={{ fontSize: 11 }}>★ {Math.round(tk.rate * 100)}%</span>
            <span className="v">›</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Auth screen — login / register
function AuthScreen({ t, lang, setLang, onLogin }) {
  const [mode, setMode] = React.useState('login'); // login | register
  return (
    <div style={{
      position: 'fixed', inset: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 10,
    }}>
      <div className="scene" />
      <Particles enabled={true} />

      <div style={{
        width: 900, maxWidth: '92%',
        display: 'grid', gridTemplateColumns: '1.1fr 1fr',
        position: 'relative', zIndex: 3,
        background: 'var(--surface)',
        border: '1px solid var(--violet)',
        boxShadow: '0 0 40px rgba(176,38,255,0.4)',
      }}
        className="cornered">
        <span className="tl" /><span className="br" />

        {/* Left — hero */}
        <div style={{
          padding: '40px 36px',
          borderRight: '1px solid var(--line-hi)',
          background: 'radial-gradient(ellipse at top left, rgba(176,38,255,0.14), transparent 60%)',
          position: 'relative',
          overflow: 'hidden',
        }}>
          <div className="row gap-2" style={{ marginBottom: 32 }}>
            <MitsMark size={40} />
            <div className="col">
              <span className="display" style={{ fontSize: 22, fontWeight: 600, letterSpacing: '0.02em' }}>MITS</span>
              <span className="ghost" style={{ fontSize: 9, letterSpacing: '0.22em' }}>math · intelligent · tutoring · system</span>
            </div>
          </div>

          <Glitch as="div" className="display">
            <span style={{ fontSize: 32, fontWeight: 700, letterSpacing: '0.02em', color: 'var(--text)', lineHeight: 1.1 }}>
              {t('auth_welcome_line1')}
            </span>
          </Glitch>
          <div style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 10, letterSpacing: '0.08em' }}>
            // {t('auth_welcome_line2')}
          </div>

          {/* Typed terminal */}
          <div style={{
            marginTop: 28,
            padding: 14,
            background: 'rgba(0,0,0,0.5)',
            border: '1px solid var(--line)',
            fontSize: 11,
            color: 'var(--text-dim)',
            fontFamily: 'var(--font-mono)',
            minHeight: 140,
          }}>
            <div><span className="y">❯</span> booting orchestrator...</div>
            <div>[<span className="y">OK</span>] profiler · planner · tutor · verifier</div>
            <div>[<span className="y">OK</span>] ollama · qwen3.5-9b · loaded in 2.4s</div>
            <div>[<span className="y">OK</span>] chromadb · 43,919 chunks</div>
            <div>[<span className="y">OK</span>] sympy · chempy bridges</div>
            <div>[<span className="y">OK</span>] bkt + dkt tracers · 40 skills</div>
            <div><Typed text="awaiting handshake..." speed={40} /></div>
          </div>

          <div style={{
            position: 'absolute', bottom: 20, left: 36, right: 36,
            fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.14em',
            borderTop: '1px dashed var(--line)', paddingTop: 10,
          }}>
            {lang === 'ru'
              ? 'МГТУ им. Баумана · дипломная работа · 2024–2026'
              : 'Bauman MSTU · thesis project · 2024–2026'}
          </div>
        </div>

        {/* Right — form */}
        <div style={{ padding: '40px 36px', position: 'relative' }}>
          <div className="row" style={{ marginBottom: 28 }}>
            <button
              onClick={() => setMode('login')}
              className="mono"
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                color: mode === 'login' ? 'var(--text)' : 'var(--text-muted)',
                fontSize: 12, letterSpacing: '0.2em', textTransform: 'uppercase',
                paddingBottom: 6, borderBottom: mode === 'login' ? '1px solid var(--yellow)' : '1px solid transparent',
                marginRight: 16,
              }}>
              ❯ {t('auth_login')}
            </button>
            <button
              onClick={() => setMode('register')}
              className="mono"
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                color: mode === 'register' ? 'var(--text)' : 'var(--text-muted)',
                fontSize: 12, letterSpacing: '0.2em', textTransform: 'uppercase',
                paddingBottom: 6, borderBottom: mode === 'register' ? '1px solid var(--yellow)' : '1px solid transparent',
              }}>
              ❯ {t('auth_register')}
            </button>
            <div className="flex-1" />
            <button onClick={() => setLang(lang === 'ru' ? 'en' : 'ru')}
              className="btn-ghost btn" style={{ fontSize: 10 }}>
              {lang === 'ru' ? 'RU' : 'EN'} ⇄
            </button>
          </div>

          <form className="col gap-3" onSubmit={e => { e.preventDefault(); onLogin(); }}>
            {mode === 'register' && (
              <label className="col gap-1">
                <span className="uppercase ghost" style={{ fontSize: 9, letterSpacing: '0.2em' }}>❯ {t('auth_name')}</span>
                <input className="input" placeholder={lang === 'ru' ? 'Максим' : 'Maxim'} />
              </label>
            )}
            <label className="col gap-1">
              <span className="uppercase ghost" style={{ fontSize: 9, letterSpacing: '0.2em' }}>❯ {t('auth_email')}</span>
              <input className="input" type="email" placeholder="siesher@mits.sys" defaultValue="siesher@mits.sys" />
            </label>
            <label className="col gap-1">
              <span className="uppercase ghost" style={{ fontSize: 9, letterSpacing: '0.2em' }}>❯ {t('auth_pass')}</span>
              <input className="input" type="password" placeholder="••••••••••••" defaultValue="demo-access-key" />
            </label>

            {mode === 'register' && (
              <div className="row gap-2" style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                <span className="y">◆</span>
                <span>{lang === 'ru'
                  ? 'Argon2 + JWT · пароль хэшируется локально'
                  : 'Argon2 + JWT · password hashed client-side'}</span>
              </div>
            )}

            <button type="submit" className="btn btn-primary" style={{
              marginTop: 12, padding: '12px 16px', justifyContent: 'center',
              fontSize: 12, letterSpacing: '0.2em',
            }}>
              ⟦ {mode === 'login' ? t('auth_login') : t('auth_register')} ⟧ →
            </button>
          </form>

          <div className="row" style={{ marginTop: 18, fontSize: 10, color: 'var(--text-muted)' }}>
            {mode === 'login' ? (
              <>
                <button className="btn-ghost btn" style={{ padding: 0, fontSize: 10 }}>{t('auth_forgot')}</button>
                <div className="flex-1" />
                <button onClick={() => setMode('register')} className="btn-ghost btn" style={{ padding: 0, fontSize: 10 }}>
                  {t('auth_to_register')} ›
                </button>
              </>
            ) : (
              <>
                <div className="flex-1" />
                <button onClick={() => setMode('login')} className="btn-ghost btn" style={{ padding: 0, fontSize: 10 }}>
                  {t('auth_to_login')} ›
                </button>
              </>
            )}
          </div>

          <div style={{
            position: 'absolute', bottom: 20, left: 36, right: 36,
            fontSize: 9, color: 'var(--text-ghost)',
            borderTop: '1px dashed var(--line)', paddingTop: 10,
            letterSpacing: '0.18em', textTransform: 'uppercase',
          }}>
            session · anonymous · no tracking
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ProfileView, SourcesView, TasksView, AuthScreen });
