// ==============================================================
// Chat view — streaming messages, formulas, agent thinking
// ==============================================================

const SAMPLE_SUGGESTED = {
  ru: [
    "Объясни сократически, почему ∫sin(x)dx = -cos(x)+C",
    "У меня застрял на pKa уксусной кислоты — как подойти?",
    "Дай задачу по ДП на подпоследовательности",
    "Проверь моё решение системы линейных уравнений (загрузка ниже)",
  ],
  en: [
    "Walk me socratically through ∫sin(x)dx = -cos(x)+C",
    "I'm stuck on pKa of acetic acid — how to start?",
    "Give me a DP problem on subsequences",
    "Verify my solution to this linear system (upload below)",
  ],
};

// Convert $$...$$ and $...$ using KaTeX
function renderMath(str) {
  if (!window.katex) return [{ type: 'text', content: str }];
  const parts = [];
  const regex = /(\$\$[^$]+\$\$|\$[^$\n]+\$)/g;
  let last = 0, m;
  while ((m = regex.exec(str)) !== null) {
    if (m.index > last) parts.push({ type: 'text', content: str.slice(last, m.index) });
    const block = m[0].startsWith('$$');
    const content = m[0].replace(/^\$+|\$+$/g, '');
    try {
      const html = katex.renderToString(content, { displayMode: block, throwOnError: false });
      parts.push({ type: 'math', html, block });
    } catch {
      parts.push({ type: 'text', content: m[0] });
    }
    last = m.index + m[0].length;
  }
  if (last < str.length) parts.push({ type: 'text', content: str.slice(last) });
  return parts;
}

function Markdown({ text }) {
  const parts = renderMath(text);
  return (
    <>
      {parts.map((p, i) => {
        if (p.type === 'math') {
          if (p.block) {
            return <div key={i} className="formula-block" dangerouslySetInnerHTML={{ __html: p.html }} />;
          }
          return <span key={i} dangerouslySetInnerHTML={{ __html: p.html }} />;
        }
        // simple italic / bold / code inline
        const lines = p.content.split('\n');
        return (
          <span key={i}>
            {lines.map((ln, j) => {
              const pieces = ln.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
              return (
                <React.Fragment key={j}>
                  {pieces.map((pc, k) => {
                    if (pc.startsWith('`')) return <code key={k} style={{
                      background: 'rgba(176,38,255,0.12)', padding: '1px 5px',
                      border: '1px solid var(--line)', color: 'var(--yellow)', fontSize: '0.92em',
                    }}>{pc.slice(1, -1)}</code>;
                    if (pc.startsWith('**')) return <strong key={k} style={{ color: 'var(--text)' }}>{pc.slice(2, -2)}</strong>;
                    return <React.Fragment key={k}>{pc}</React.Fragment>;
                  })}
                  {j < lines.length - 1 && <br />}
                </React.Fragment>
              );
            })}
          </span>
        );
      })}
    </>
  );
}

function AgentStep({ icon, label, detail, status, color = 'violet' }) {
  const colorMap = {
    violet: 'var(--violet)',
    yellow: 'var(--yellow)',
    cyan: 'var(--cyan)',
  };
  return (
    <div className="row gap-3" style={{
      padding: '6px 10px',
      borderLeft: '1px solid ' + colorMap[color],
      background: 'rgba(176,38,255,0.04)',
      fontSize: 11,
    }}>
      <span style={{ color: colorMap[color] }}>{icon}</span>
      <span className="uppercase" style={{ letterSpacing: '0.14em', color: 'var(--text-dim)' }}>{label}</span>
      <span className="flex-1" style={{ color: 'var(--text)' }}>{detail}</span>
      {status === 'done' && <span style={{ color: 'var(--success)' }}>✓</span>}
      {status === 'active' && <span className="dot v pulse-v" />}
    </div>
  );
}

function ThinkingPanel({ t, steps }) {
  return (
    <div style={{
      background: 'rgba(0,0,0,0.4)',
      border: '1px dashed var(--line-hi)',
      padding: 10,
      marginBottom: 10,
    }}>
      <div className="row gap-2 uppercase" style={{ fontSize: 9, letterSpacing: '0.2em', marginBottom: 8 }}>
        <span className="neon-v">⟨⟩</span>
        <span className="v">{t('thinking')}</span>
        <span className="ghost">·</span>
        <span className="dim">agent chain</span>
        <div className="flex-1" />
        <span className="chip v">STREAM</span>
      </div>
      <div className="col gap-1">
        {steps.map((s, i) => <AgentStep key={i} {...s} />)}
      </div>
    </div>
  );
}

function UserMessage({ content }) {
  return (
    <div className="row" style={{ gap: 14, alignItems: 'flex-start', padding: '12px 0' }}>
      <div style={{
        width: 28, height: 28, flex: '0 0 28px',
        border: '1px solid var(--line-hi)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--yellow)', fontSize: 12,
      }}>&gt;_</div>
      <div className="flex-1">
        <div className="uppercase ghost" style={{ fontSize: 9, letterSpacing: '0.22em', marginBottom: 4 }}>
          USER · you
        </div>
        <div style={{ color: 'var(--text)', fontSize: 13.5, lineHeight: 1.6 }}>
          <Markdown text={content} />
        </div>
      </div>
    </div>
  );
}

function TutorMessage({ content, streaming, steps, verified, t }) {
  return (
    <div className="row" style={{ gap: 14, alignItems: 'flex-start', padding: '12px 0' }}>
      <div style={{
        width: 28, height: 28, flex: '0 0 28px',
        border: '1px solid var(--line-hi)',
        background: 'rgba(181, 138, 255, 0.06)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <MitsMark size={18} animated={false} />
      </div>
      <div className="flex-1" style={{ minWidth: 0 }}>
        <div className="row gap-2" style={{ marginBottom: 6 }}>
          <span className="uppercase neon-v" style={{ fontSize: 9, letterSpacing: '0.22em' }}>
            MITS · tutor
          </span>
          {streaming && <span className="chip v"><span className="dot v" /> {t('streaming')}</span>}
          {verified && <span className="chip on">✓ {t('verified')}</span>}
        </div>
        {steps && <ThinkingPanel t={t} steps={steps} />}
        <div style={{ color: 'var(--text)', fontSize: 13.5, lineHeight: 1.7 }}>
          <Markdown text={content} />
          {streaming && <span className="caret" />}
        </div>
      </div>
    </div>
  );
}

function ChatInput({ t, onSend, disabled }) {
  const [text, setText] = React.useState('');
  const ref = React.useRef(null);
  const submit = () => {
    if (!text.trim() || disabled) return;
    onSend(text.trim());
    setText('');
  };
  return (
    <div style={{
      borderTop: '1px solid var(--line-hi)',
      background: 'rgba(0,0,0,0.5)',
      padding: 14,
      position: 'relative',
    }}>
      <div className="scan-bar" style={{ top: 0, height: 2, background: 'var(--violet)', animation: 'none', opacity: 0.35 }} />
      <div className="row gap-2" style={{ alignItems: 'flex-start' }}>
        <span style={{ color: 'var(--yellow)', fontSize: 14, paddingTop: 8 }}>❯</span>
        <textarea
          ref={ref}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
          }}
          placeholder={t('input_placeholder')}
          rows={2}
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: 'var(--text)',
            fontFamily: 'var(--font-mono)',
            fontSize: 13.5,
            resize: 'none',
          }}
        />
        <button className="btn btn-primary" onClick={submit} disabled={disabled || !text.trim()}
          style={{ opacity: (disabled || !text.trim()) ? 0.5 : 1 }}>
          SEND ↵
        </button>
      </div>
      <div className="row gap-4" style={{ marginTop: 10, fontSize: 10, color: 'var(--text-muted)' }}>
        <span><kbd>↵</kbd> {t('input_hint_enter')}</span>
        <span><kbd>⇧↵</kbd> {t('input_hint_shift')}</span>
        <span><kbd>/</kbd> {t('input_hint_slash')}</span>
        <div className="flex-1" />
        <span className="ghost">📎 attach</span>
        <span className="ghost">🖊 OCR</span>
        <span className="ghost">λ SymPy</span>
      </div>
    </div>
  );
}

function ModeTabs({ t, mode, setMode }) {
  const modes = [
    { id: 'chat',   icon: '◇', label: t('mode_chat') },
    { id: 'guided', icon: '◆', label: t('mode_guided') },
    { id: 'task',   icon: '⬢', label: t('mode_task') },
  ];
  return (
    <div className="row gap-2" style={{ padding: '10px 16px', borderBottom: '1px solid var(--line)' }}>
      {modes.map(m => {
        const on = mode === m.id;
        return (
          <button key={m.id}
            onClick={() => setMode(m.id)}
            className="mono"
            style={{
              padding: '6px 12px',
              background: on ? 'rgba(181,138,255,0.08)' : 'transparent',
              border: '1px solid ' + (on ? 'var(--line-hi)' : 'var(--line)'),
              color: on ? 'var(--text)' : 'var(--text-dim)',
              fontSize: 10,
              letterSpacing: '0.16em',
              textTransform: 'uppercase',
              cursor: 'pointer',
              transition: 'all 120ms',
            }}>
            <span style={{ color: on ? 'var(--yellow)' : 'var(--violet)', marginRight: 6 }}>{m.icon}</span>
            {m.label}
          </button>
        );
      })}
      <div className="flex-1" />
      <span className="chip v">DIFFICULTY: ADAPTIVE</span>
      <span className="chip">DOMAIN: MATH</span>
    </div>
  );
}

function ChatView({ t, lang }) {
  const [mode, setMode] = React.useState('guided');
  const [messages, setMessages] = React.useState(() => initialConversation(lang));
  const [streaming, setStreaming] = React.useState(false);
  const scrollRef = React.useRef(null);

  React.useEffect(() => {
    setMessages(initialConversation(lang));
  }, [lang]);

  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  const send = (text) => {
    const userMsg = { role: 'user', content: text, id: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setStreaming(true);
    // Fake streaming reply
    const reply = lang === 'ru'
      ? `Хороший ход. Давай зафиксируем постановку.\n\nМы ищем $f(x)$ такую, что $f'(x) = \\sin(x)$. Какое элементарное преобразование тебе подсказывает интуиция — что даёт $-\\cos(x)$ при дифференцировании?\n\n$$\\frac{d}{dx}\\bigl(-\\cos x\\bigr) = \\sin x$$\n\nПроверь знак и константу. Не забывай про $+C$ — почему именно константа, а не, скажем, функция?`
      : `Good start. Let's pin the setup.\n\nWe want $f(x)$ such that $f'(x) = \\sin(x)$. What elementary transform does your intuition suggest — what gives $-\\cos(x)$ when differentiated?\n\n$$\\frac{d}{dx}\\bigl(-\\cos x\\bigr) = \\sin x$$\n\nCheck sign and constant. Why \\textit{a constant} and not a function?`;
    const steps = [
      { icon: '◉', label: t('think_profiler'), detail: lang === 'ru' ? 'уровень: intermediate · скилл: integration_basics' : 'level: intermediate · skill: integration_basics', status: 'done' },
      { icon: '◈', label: t('think_planner'),  detail: lang === 'ru' ? 'стратегия: обратное дифференцирование → подсказка' : 'strategy: reverse-diff → targeted hint', status: 'done' },
      { icon: '◆', label: t('think_tutor'),    detail: lang === 'ru' ? 'сократический вопрос; не раскрывать ответ' : 'socratic prompt; do not reveal', status: 'active', color: 'yellow' },
      { icon: '⬢', label: t('think_verifier'), detail: 'SymPy: diff(-cos(x)) ≡ sin(x) ✓', status: 'done' },
    ];
    const tutorId = Date.now() + 1;
    setMessages(prev => [...prev, { role: 'tutor', content: '', id: tutorId, streaming: true, steps, verified: false }]);

    // chunked streaming
    let i = 0;
    const chunkSize = 2;
    const id = setInterval(() => {
      i += chunkSize;
      setMessages(prev => prev.map(m => m.id === tutorId ? { ...m, content: reply.slice(0, i) } : m));
      if (i >= reply.length) {
        clearInterval(id);
        setMessages(prev => prev.map(m => m.id === tutorId ? { ...m, streaming: false, verified: true } : m));
        setStreaming(false);
      }
    }, 24);
  };

  return (
    <div className="col flex-1" style={{ minWidth: 0 }}>
      <ModeTabs t={t} mode={mode} setMode={setMode} />

      <div ref={scrollRef} className="flex-1" style={{
        overflowY: 'auto',
        padding: '14px 28px',
        position: 'relative',
      }}>
        {/* Greeter */}
        <div style={{ padding: '18px 0', borderBottom: '1px solid var(--line)', marginBottom: 10 }}>
          <div className="row gap-3">
            <MitsMark size={40} />
            <div>
              <Glitch className="display" as="div">
                <span style={{ fontSize: 22, fontWeight: 600, color: 'var(--text)' }}>
                  {lang === 'ru' ? 'Гримуар открыт.' : 'Grimoire open.'}
                </span>
              </Glitch>
              <div className="ghost" style={{ fontSize: 11, letterSpacing: '0.12em', marginTop: 2 }}>
                {lang === 'ru'
                  ? '// сократический режим · агенты готовы · SymPy на связи'
                  : '// socratic mode · agents ready · sympy online'}
              </div>
            </div>
          </div>
        </div>

        {messages.map(m => m.role === 'user'
          ? <UserMessage key={m.id} content={m.content} />
          : <TutorMessage key={m.id} t={t} {...m} />
        )}

        {messages.length <= 2 && (
          <div style={{ marginTop: 24, borderTop: '1px dashed var(--line)', paddingTop: 16 }}>
            <div className="uppercase ghost" style={{ fontSize: 10, letterSpacing: '0.22em', marginBottom: 10 }}>
              › {t('suggested')}
            </div>
            <div className="col gap-2">
              {SAMPLE_SUGGESTED[lang].map((s, i) => (
                <button key={i}
                  onClick={() => send(s)}
                  className="mono"
                  style={{
                    textAlign: 'left',
                    padding: '10px 14px',
                    background: 'rgba(176,38,255,0.04)',
                    border: '1px solid var(--line)',
                    color: 'var(--text-dim)',
                    fontSize: 12,
                    cursor: 'pointer',
                    transition: 'all 120ms',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.color = 'var(--text)';
                    e.currentTarget.style.borderColor = 'var(--violet)';
                    e.currentTarget.style.boxShadow = '0 0 12px rgba(176,38,255,0.2)';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.color = 'var(--text-dim)';
                    e.currentTarget.style.borderColor = 'var(--line)';
                    e.currentTarget.style.boxShadow = 'none';
                  }}
                >
                  <span className="v" style={{ marginRight: 8 }}>▸</span>{s}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <ChatInput t={t} onSend={send} disabled={streaming} />
    </div>
  );
}

function initialConversation(lang) {
  if (lang === 'ru') {
    return [
      { id: 1, role: 'user', content: "Покажи интеграл ∫sin(x)dx и объясни шаги" },
      { id: 2, role: 'tutor',
        content: "Давай не торопиться с ответом. Что такое интегрирование — с точки зрения операций? Если я попрошу тебя найти функцию, производная которой даёт $\\sin(x)$ — какая функция приходит в голову первой?\n\nПодсказка: подумай о производных тригонометрических функций. Посмотри:\n\n$$\\frac{d}{dx}[\\cos(x)] = -\\sin(x)$$\n\nЧто отсюда следует для первообразной $\\sin(x)$?",
        steps: [
          { icon: '◉', label: 'Profiler', detail: 'novice · integration_basics=0.22', status: 'done' },
          { icon: '◈', label: 'Planner',  detail: 'стратегия: from derivative memory → reverse', status: 'done' },
          { icon: '◆', label: 'Tutor',    detail: 'socratic · не раскрывать ответ', status: 'done' },
        ],
        verified: true,
      },
    ];
  }
  return [
    { id: 1, role: 'user', content: "Show me the integral ∫sin(x)dx and explain the steps" },
    { id: 2, role: 'tutor',
      content: "Let's not rush to the answer. What *is* integration, operationally? If I ask for a function whose derivative is $\\sin(x)$ — what's the first candidate that comes to mind?\n\nHint: recall the derivatives of trig functions. Observe:\n\n$$\\frac{d}{dx}[\\cos(x)] = -\\sin(x)$$\n\nWhat does this imply for the antiderivative of $\\sin(x)$?",
      steps: [
        { icon: '◉', label: 'Profiler', detail: 'novice · integration_basics=0.22', status: 'done' },
        { icon: '◈', label: 'Planner',  detail: 'strategy: derivative-memory → reverse', status: 'done' },
        { icon: '◆', label: 'Tutor',    detail: 'socratic · do not reveal', status: 'done' },
      ],
      verified: true,
    },
  ];
}

Object.assign(window, { ChatView });
