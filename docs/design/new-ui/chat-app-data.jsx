// MITS — Sample data & i18n strings

const I18N = {
  ru: {
    appName: "MITS",
    appSub: "Math · Intelligent Tutoring",
    newChat: "Новый чат",
    sessionsToday: "Сегодня",
    sessionsYesterday: "Вчера",
    sessionsWeek: "Эта неделя",
    placeholder: "Опишите ваш ход решения или задайте вопрос…",
    composerHint: "Enter — отправить · Shift+Enter — новая строка · ⌘K — команды",
    hintBtn: "Подсказка",
    hintsLeft: (n) => `${n} осталось`,
    modeChat: "Свободный чат",
    modeGuided: "Сократический тьютор",
    modeTask: "Генератор задач",
    modeChatDesc: "Свободное общение на любые темы",
    modeGuidedDesc: "Никогда не даёт готовый ответ — ведёт вопросами",
    modeTaskDesc: "Генерация задач по теме и сложности",
    agentLabel: "Агенты",
    agProfiler: "Profiler",
    agPlanner: "Planner",
    agTutor: "Tutor",
    agVerifier: "Verifier",
    moveScaffolding: "Разбор по шагам",
    moveHint: "Подсказка",
    moveEncourage: "Поощрение",
    moveProblematize: "Вопрос",
    moveRectify: "Исправление",
    taskLabel: "Производные · medium",
    taskTitle: "Найти производную сложной функции",
    taskDifficulty: "Сложность",
    taskHints: "Подсказок",
    taskSkill: "Навык",
    skillChain: "Цепное правило",
    sessionDeriv: "Производная sin(x²)",
    sessionIntegrate: "Интеграл по частям",
    sessionLimit: "Предел при x→0",
    sessionPhys: "Закон Ньютона II",
    sessionChem: "Гидролиз солей",
    sessionEq: "Квадратное уравнение",
    railSkills: "Освоение навыков",
    railSkillsTag: "DKT",
    railSession: "Текущая сессия",
    railArch: "Активные агенты",
    statTime: "минут",
    statMessages: "сообщений",
    statHints: "подсказок",
    statSolved: "решено",
    showThinking: "Размышления модели",
    hideThinking: "Свернуть размышления",
    thinkingTokens: (n) => `${n} токенов · 4.2с`,
    profile: "Профиль",
    settings: "Настройки",
    docs: "Документация",
    userYou: "Студент",
    userTutor: "Тьютор",
    socraticWelcome: "Сократический метод",
    thinking: "Думает…",
  },
  en: {
    appName: "MITS",
    appSub: "Math · Intelligent Tutoring",
    newChat: "New chat",
    sessionsToday: "Today",
    sessionsYesterday: "Yesterday",
    sessionsWeek: "This week",
    placeholder: "Walk through your reasoning or ask a question…",
    composerHint: "Enter to send · Shift+Enter for newline · ⌘K commands",
    hintBtn: "Hint",
    hintsLeft: (n) => `${n} left`,
    modeChat: "Open chat",
    modeGuided: "Socratic tutor",
    modeTask: "Task generator",
    modeChatDesc: "Free-form conversation on any topic",
    modeGuidedDesc: "Never gives the answer — leads with questions",
    modeTaskDesc: "Generate problems by topic and difficulty",
    agentLabel: "Agents",
    agProfiler: "Profiler",
    agPlanner: "Planner",
    agTutor: "Tutor",
    agVerifier: "Verifier",
    moveScaffolding: "Scaffolding",
    moveHint: "Hint",
    moveEncourage: "Encourage",
    moveProblematize: "Probe",
    moveRectify: "Rectify",
    taskLabel: "Derivatives · medium",
    taskTitle: "Differentiate a composed function",
    taskDifficulty: "Difficulty",
    taskHints: "Hints",
    taskSkill: "Skill",
    skillChain: "Chain rule",
    sessionDeriv: "Derivative of sin(x²)",
    sessionIntegrate: "Integration by parts",
    sessionLimit: "Limit as x→0",
    sessionPhys: "Newton's 2nd law",
    sessionChem: "Salt hydrolysis",
    sessionEq: "Quadratic equation",
    railSkills: "Skill mastery",
    railSkillsTag: "DKT",
    railSession: "Current session",
    railArch: "Live agents",
    statTime: "minutes",
    statMessages: "messages",
    statHints: "hints used",
    statSolved: "solved",
    showThinking: "Model reasoning",
    hideThinking: "Hide reasoning",
    thinkingTokens: (n) => `${n} tokens · 4.2s`,
    profile: "Profile",
    settings: "Settings",
    docs: "Docs",
    userYou: "You",
    userTutor: "Tutor",
    socraticWelcome: "Socratic method",
    thinking: "Thinking…",
  },
};

const DIALOG = {
  ru: [
    {
      role: "user",
      time: "14:32",
      body: "<p>Думаю, тут нужно правило произведения. Получается:</p><span class='formula'>f'(x) = cos(x²) · 2x</span>",
    },
    {
      role: "tutor",
      time: "14:32",
      move: "encourage",
      body: "<p>Отличная интуиция — ты увидел, что под синусом стоит <span class='inline-math'>x²</span>, а не просто <span class='inline-math'>x</span>. Это ключевой момент. И финальный ответ верный!</p>",
    },
    {
      role: "user",
      time: "14:34",
      body: "<p>А можно теперь то же самое, но с <span class='inline-math'>cos(3x⁴ - 1)</span>?</p>",
    },
    {
      role: "tutor",
      time: "14:34",
      move: "scaffolding",
      body: "<p>Давай не я решу, а ты — но я помогу разложить мышление. Сначала вопрос:</p><p><strong>Какая функция здесь «внешняя», а какая «внутренняя»?</strong></p><p>Внешняя — это та, в которой сидит другая. Назови их по порядку, и идём дальше.</p>",
      thinking: "Студент успешно применил цепное правило на простом случае (sin(x²)). Уровень оценен как L2 — понимает структуру, но может путаться в порядке операций для более сложной композиции.\n\nПрименяю <em>scaffolding</em> вместо прямого ответа: не давать формулу, а попросить идентифицировать внешнюю/внутреннюю функции. Это активирует metacognitive recall + закрепляет паттерн.\n\nЕсли студент ответит правильно — переходим к производной внутренней. Если запутается — даю <em>hint</em> с примером на простой функции.",
      tokens: 327,
      streaming: false,
    },
    {
      role: "user",
      time: "14:36",
      body: "<p>Внешняя — это косинус, а внутренняя <span class='inline-math'>3x⁴ - 1</span>. Так?</p>",
    },
    {
      role: "tutor",
      time: "14:36",
      move: "hint",
      streaming: true,
      body: "<p>Именно. Теперь — производная цепи: сначала производная <strong>внешней</strong> по своему аргументу, потом умножаем на производную <strong>внутренней</strong>. То есть схема такая:</p><span class='formula'>f'(x) = [внешняя']ᵥ · [внутренняя']ₓ</span><p>Попробуй применить эту схему сам. Что получится для <span class='inline-math'>cos(3x⁴ - 1)</span>?</p>",
    },
  ],
  en: [
    {
      role: "user",
      time: "14:32",
      body: "<p>I think product rule applies — so:</p><span class='formula'>f'(x) = cos(x²) · 2x</span>",
    },
    {
      role: "tutor",
      time: "14:32",
      move: "encourage",
      body: "<p>Strong intuition — you spotted that the argument inside sine is <span class='inline-math'>x²</span>, not just <span class='inline-math'>x</span>. That's the key insight. And the final answer is correct!</p>",
    },
    {
      role: "user",
      time: "14:34",
      body: "<p>Can we try the same idea on <span class='inline-math'>cos(3x⁴ - 1)</span> now?</p>",
    },
    {
      role: "tutor",
      time: "14:34",
      move: "scaffolding",
      body: "<p>I'd rather scaffold your thinking than solve it for you. So first question:</p><p><strong>Which function is the «outer» one here, and which is «inner»?</strong></p><p>The outer one wraps around the other. Name them in order and we'll keep going.</p>",
      thinking: "Student successfully applied the chain rule on the simpler sin(x²). Estimated level L2 — understands structure but may stumble on operation order for more nested compositions.\n\nApplying <em>scaffolding</em> rather than a direct answer: don't give the formula — ask them to identify inner/outer first. This activates metacognitive recall and reinforces the pattern.\n\nIf they answer correctly — move on to differentiating the inner. If confused — drop a <em>hint</em> with a simpler example.",
      tokens: 312,
      streaming: false,
    },
    {
      role: "user",
      time: "14:36",
      body: "<p>The outer is cosine and the inner is <span class='inline-math'>3x⁴ - 1</span>. Right?</p>",
    },
    {
      role: "tutor",
      time: "14:36",
      move: "hint",
      streaming: true,
      body: "<p>Exactly. Now the chain rule: derivative of the <strong>outer</strong> with respect to its argument, then multiplied by the derivative of the <strong>inner</strong>. The pattern is:</p><span class='formula'>f'(x) = [outer']ᵤ · [inner']ₓ</span><p>Try to apply this pattern yourself. What do you get for <span class='inline-math'>cos(3x⁴ - 1)</span>?</p>",
    },
  ],
};

const SESSIONS = [
  { id: 1, key: "sessionDeriv", mode: "guided", active: true, time: "14:30" },
  { id: 2, key: "sessionIntegrate", mode: "guided", time: "12:14" },
  { id: 3, key: "sessionLimit", mode: "chat", time: "11:02" },
  { id: 4, key: "sessionPhys", mode: "guided", time: "Yest." },
  { id: 5, key: "sessionChem", mode: "task", time: "Yest." },
  { id: 6, key: "sessionEq", mode: "guided", time: "Mon" },
];

const SKILLS = {
  ru: [
    { name: "Производные · базовые", val: 0.91 },
    { name: "Цепное правило", val: 0.74 },
    { name: "Произведение и частное", val: 0.62 },
    { name: "Неявная дифференциация", val: 0.38 },
    { name: "Интегралы · по частям", val: 0.55 },
  ],
  en: [
    { name: "Derivatives · basic", val: 0.91 },
    { name: "Chain rule", val: 0.74 },
    { name: "Product & quotient", val: 0.62 },
    { name: "Implicit differentiation", val: 0.38 },
    { name: "Integration by parts", val: 0.55 },
  ],
};

const TECH_TAGS = [
  "Qwen3.5-9B", "GSPO", "KTO", "DPO", "BKT", "DKT", "SymPy",
  "ChromaDB", "FastAPI", "Next.js 14", "Ollama", "WebSocket",
  "Unsloth", "TRL", "PEFT", "Qwen2.5-VL", "Argon2",
];

// ===== Nav (sidebar pages) =====
const NAV_KEYS = ["chat", "tasks", "graph", "dashboard", "sources", "profile", "settings"];

// ===== Domain colors (light + dark variants) =====
// Tuned for perceptual balance (OKLCH-equalised lightness/chroma) — keeps
// the math purple as brand anchor; tames phys orange + cs magenta a touch.
const DOMAIN_COLOR = {
  math:  { light: "#6800FF", dark: "#B47BFF" },
  phys:  { light: "#B85A1F", dark: "#F0BB7E" },
  chem:  { light: "#0E8B95", dark: "#8DD4DC" },
  cs:    { light: "#A8326A", dark: "#ED9CBF" },
  bio:   { light: "#1E7A4A", dark: "#6FE0A6" },
};

// ===== Tasks (mock data) =====
const TASKS_DATA = {
  ru: [
    { d: "math",  diff: "medium",   t: "Интеграл по частям: ∫x·eˣ dx",        tags: ["integration", "IBP"],   rate: 0.58 },
    { d: "cs",    diff: "hard",     t: "Кол-во способов разменять сумму N",   tags: ["DP", "coin-change"],    rate: 0.44 },
    { d: "phys",  diff: "medium",   t: "Брусок на наклонной с трением",       tags: ["mechanics"],            rate: 0.67 },
    { d: "chem",  diff: "easy",     t: "pH слабой кислоты HA, Ka = 1.8·10⁻⁵", tags: ["equilibrium"],          rate: 0.52 },
    { d: "math",  diff: "hard",     t: "Собственные значения матрицы 3×3",    tags: ["linalg"],               rate: 0.36 },
    { d: "bio",   diff: "medium",   t: "Частоты аллелей по Харди–Вайнбергу",  tags: ["genetics"],             rate: 0.41 },
    { d: "math",  diff: "olympiad", t: "Неравенство Иенсена для log-сумм",    tags: ["inequalities"],         rate: 0.18 },
    { d: "cs",    diff: "medium",   t: "Длина наибольшей возрастающей подп.", tags: ["DP", "LIS"],            rate: 0.62 },
  ],
  en: [
    { d: "math",  diff: "medium",   t: "Integration by parts: ∫x·eˣ dx",       tags: ["integration", "IBP"],   rate: 0.58 },
    { d: "cs",    diff: "hard",     t: "Ways to make change for amount N",     tags: ["DP", "coin-change"],    rate: 0.44 },
    { d: "phys",  diff: "medium",   t: "Block on incline with friction",       tags: ["mechanics"],            rate: 0.67 },
    { d: "chem",  diff: "easy",     t: "pH of weak acid HA, Ka = 1.8·10⁻⁵",    tags: ["equilibrium"],          rate: 0.52 },
    { d: "math",  diff: "hard",     t: "Eigenvalues of a 3×3 matrix",          tags: ["linalg"],               rate: 0.36 },
    { d: "bio",   diff: "medium",   t: "Allele frequencies via Hardy–Weinberg",tags: ["genetics"],             rate: 0.41 },
    { d: "math",  diff: "olympiad", t: "Jensen's inequality for log-sums",     tags: ["inequalities"],         rate: 0.18 },
    { d: "cs",    diff: "medium",   t: "Longest increasing subsequence",       tags: ["DP", "LIS"],            rate: 0.62 },
  ],
};

// ===== Graph nodes (knowledge map) =====
const GRAPH_NODES = [
  { id: "arith",  x: 200, y: 260, r: 24, lab: "Arithmetic",      d: "math",  m: 0.94, att: 142 },
  { id: "alg",    x: 320, y: 200, r: 26, lab: "Algebra",         d: "math",  m: 0.82, att: 118 },
  { id: "linalg", x: 440, y: 160, r: 22, lab: "Linear Alg",      d: "math",  m: 0.64, att:  63 },
  { id: "calc",   x: 460, y: 290, r: 28, lab: "Calculus",        d: "math",  m: 0.71, att:  97, active: true },
  { id: "int",    x: 570, y: 360, r: 24, lab: "Integrals",       d: "math",  m: 0.58, att:  41, highlight: true },
  { id: "diff",   x: 570, y: 240, r: 22, lab: "Derivatives",     d: "math",  m: 0.78, att:  72 },
  { id: "geom",   x: 350, y: 340, r: 22, lab: "Geometry",        d: "math",  m: 0.69, att:  58 },
  { id: "prob",   x: 270, y: 420, r: 22, lab: "Probability",     d: "math",  m: 0.44, att:  29 },
  { id: "mech",   x: 720, y: 200, r: 24, lab: "Mechanics",       d: "phys",  m: 0.67, att:  51 },
  { id: "therm",  x: 820, y: 280, r: 22, lab: "Thermo",          d: "phys",  m: 0.38, att:  17 },
  { id: "em",     x: 780, y: 380, r: 22, lab: "EM Fields",       d: "phys",  m: 0.22, att:   9 },
  { id: "chem",   x: 670, y: 470, r: 22, lab: "Chemistry",       d: "chem",  m: 0.51, att:  32 },
  { id: "org",    x: 770, y: 510, r: 20, lab: "Organic",         d: "chem",  m: 0.33, att:  12 },
  { id: "cs",     x: 150, y: 380, r: 22, lab: "CS Basics",       d: "cs",    m: 0.88, att: 104 },
  { id: "ds",     x: 110, y: 480, r: 22, lab: "DS & Algo",       d: "cs",    m: 0.72, att:  61 },
  { id: "dp",     x: 210, y: 540, r: 20, lab: "DP",              d: "cs",    m: 0.48, att:  24 },
  { id: "bio",    x: 880, y: 440, r: 20, lab: "Biology",         d: "bio",   m: 0.41, att:  18 },
  { id: "gen",    x: 940, y: 530, r: 18, lab: "Genetics",        d: "bio",   m: 0.19, att:   6 },
];
// Third element = edge semantics:
//   "prereq"  — hard prerequisite (solid line + arrow)
//   "related" — cross-domain relationship (dashed)
//   "derived" — derived/dual concept (dotted + arrow)
const GRAPH_EDGES = [
  ["arith","alg","prereq"],["alg","linalg","prereq"],["alg","calc","prereq"],
  ["calc","diff","prereq"],["calc","int","prereq"],["diff","int","derived"],
  ["alg","geom","prereq"],["alg","prob","prereq"],["calc","mech","prereq"],
  ["mech","therm","prereq"],["mech","em","prereq"],["chem","org","prereq"],
  ["cs","ds","prereq"],["ds","dp","prereq"],["alg","cs","prereq"],
  ["bio","gen","prereq"],["chem","bio","related"],["linalg","mech","prereq"],
  ["prob","bio","related"],["int","mech","prereq"],["diff","mech","prereq"],
];

// ===== Recent activity (Profile) =====
const RECENT = {
  ru: [
    { t: "14:32", d: "math",  e: "Решил ∫x·sin(x)dx с 2 подсказками" },
    { t: "13:18", d: "cs",    e: "DP: longest palindromic subseq · O(n²)" },
    { t: "11:05", d: "phys",  e: "Маятник: период, малые колебания" },
    { t: "09:41", d: "chem",  e: "pKa аминокислоты — гидролиз" },
    { t: "Вчера", d: "math",  e: "Цепное правило: 14 задач, 11 решено" },
  ],
  en: [
    { t: "14:32", d: "math",  e: "Solved ∫x·sin(x)dx with 2 hints" },
    { t: "13:18", d: "cs",    e: "DP: longest palindromic subseq · O(n²)" },
    { t: "11:05", d: "phys",  e: "Pendulum: period under small oscillations" },
    { t: "09:41", d: "chem",  e: "pKa of amino acid — hydrolysis" },
    { t: "Yest.", d: "math",  e: "Chain rule: 14 problems, 11 solved" },
  ],
};

// ===== Sources =====
const SOURCES_LIST = {
  ru: [
    { kind: "TEXT", domain: "math",  status: "extracted",  title: "Демидович · гл. 3 — Интегралы",      preview: "Понятие интеграла, неопределённый и определённый интеграл, методы интегрирования…", nodes: 48, edges: 87, when: "2 ч назад" },
    { kind: "PDF",  domain: "phys",  status: "extracting", title: "Иродов · Механика, §1.4–1.7",         preview: "Уравнение движения, второй закон Ньютона, силы трения, наклонная плоскость…",      nodes: 22, edges: 31, when: "извлекается" },
    { kind: "URL",  domain: "cs",    status: "extracted",  title: "CLRS · Dynamic Programming",          preview: "Optimal substructure, overlapping subproblems, memoization vs tabulation, classic…",   nodes: 36, edges: 58, when: "вчера" },
    { kind: "TEXT", domain: "chem",  status: "pending",    title: "Глинка · Водные растворы кислот",     preview: "Электролитическая диссоциация, константа равновесия, pH, гидролиз солей…",         nodes:  0, edges:  0, when: "в очереди" },
  ],
  en: [
    { kind: "TEXT", domain: "math",  status: "extracted",  title: "Demidovich · ch. 3 — Integrals",      preview: "The concept of integral, indefinite and definite integrals, integration methods…",     nodes: 48, edges: 87, when: "2h ago" },
    { kind: "PDF",  domain: "phys",  status: "extracting", title: "Irodov · Mechanics, §1.4–1.7",         preview: "Equation of motion, Newton's 2nd law, friction forces, inclined plane…",              nodes: 22, edges: 31, when: "extracting" },
    { kind: "URL",  domain: "cs",    status: "extracted",  title: "CLRS · Dynamic Programming",          preview: "Optimal substructure, overlapping subproblems, memoization vs tabulation…",            nodes: 36, edges: 58, when: "yesterday" },
    { kind: "TEXT", domain: "chem",  status: "pending",    title: "Glinka · Aqueous solutions of acids", preview: "Electrolytic dissociation, equilibrium constant, pH, hydrolysis of salts…",            nodes:  0, edges:  0, when: "queued" },
  ],
};

const PIPELINE_STEPS = ["query", "route", "graph query", "explore(node)", "prerequisites", "context build", "tutor agent"];

// Add new i18n keys to both languages
Object.assign(I18N.ru, {
  navChat: "Чат", navTasks: "Задачи", navGraph: "Граф знаний", navDashboard: "Аналитика", navSources: "Источники", navProfile: "Профиль", navSettings: "Настройки",
  tasksTitle: "Каталог задач", tasksSub: "3 678 курированных · 40+ навыков · адаптивная сложность",
  tasksGenerate: "Сгенерировать", tasksSolveRate: "решаемость",
  graphTitle: "Граф знаний", graphSub: "Маппинг навыков · BKT + DKT · 5 доменов · 40+ концептов",
  graphInspect: "Узел · детали", graphMastery: "Освоение", graphAttempts: "Попыток", graphTrace: "След обучения", graphPrereq: "Предпосылки", graphPractice: "Практиковать",
  graphLastErr: "Посл. ошибка", graphBKT: "BKT p(known)", graphDKT: "DKT логит", graph3hAgo: "3ч назад",
  dashTitle: "Аналитика обучения", dashSub: "Сократический прогресс · последние 30 дней",
  dashExport: "Экспорт PDF", dashSessions: "Сессий", dashSolved: "Решено", dashRate: "Решаемость", dashHints: "Подсказок",
  dashMastery: "Освоение по темам", dashActivity: "Активность · 12 недель", dashErrors: "Распределение ошибок", dashReco: "Рекомендации",
  errAlgebra: "Алгебраические", errArith: "Арифметические", errConcept: "Концептуальные", errMethod: "Метод не выбран", errSyntax: "Запись формулы",
  recoTitle: "Что прокачать дальше",
  recoItems: [
    "Цепное правило · ↑12% за 3 сессии",
    "Интегрирование по частям · переход с MEDIUM на HARD",
    "Тепловой баланс · слабая зона в физике",
  ],
  profTitle: "Профиль", profStreak: "дней подряд", profSessions: "сессий", profProblems: "задач", profMastery: "среднее освоение",
  profRecent: "Последняя активность", profMasteryByTopic: "Освоение по темам", profStrong: "Сильные стороны", profWeak: "На доработке", profFocusWeek: "Фокус · неделя", profEmotion: "Эмоциональный фон", profEmotionDesc: "RuBERT детектор · уверенность 0.84", profEdit: "Редактировать",
  srcTitle: "Источники знаний", srcSub: "Knowledge Forge · активный граф · не RAG",
  srcAdd: "Добавить источник", srcPipeline: "PIPELINE", srcStatus: "Статус",
  srcStatPending: "В очереди", srcStatExtracting: "Извлечение", srcStatExtracted: "Готово", srcStatFailed: "Ошибка",
  srcNodes: "узлов", srcEdges: "рёбер", srcAdded: "добавлен",
  setTitle: "Настройки", setSub: "Оформление · эффекты · интерфейс",
  setTheme: "Тема", setEffects: "Эффекты", setLanguage: "Язык", setAbout: "О системе",
  setMotion: "Анимации", setGlow: "Свечение акцентов", setParticles: "Частицы на фоне", setGrain: "Текстура зерна",
  setAboutText: "MITS v.2.6.1 · Math Intelligent Tutoring System · Qwen3.5-9B · GSPO → KTO → DPO · Base 55.1% → 66.5% · МГТУ им. Баумана · 2024–2026",
  strongSkills: ["Базовые производные", "Цепное правило", "Алгебра"],
  weakSkills: ["Тепловой баланс", "Электромагнетизм", "Динамическое прог-е"],
  difficulty_easy: "easy", difficulty_medium: "medium", difficulty_hard: "hard", difficulty_olympiad: "olympiad",
});
Object.assign(I18N.en, {
  navChat: "Chat", navTasks: "Tasks", navGraph: "Knowledge graph", navDashboard: "Analytics", navSources: "Sources", navProfile: "Profile", navSettings: "Settings",
  tasksTitle: "Task catalog", tasksSub: "3,678 curated · 40+ skills · adaptive difficulty",
  tasksGenerate: "Generate", tasksSolveRate: "solve rate",
  graphTitle: "Knowledge graph", graphSub: "Skill mapping · BKT + DKT · 5 domains · 40+ concepts",
  graphInspect: "Node · inspect", graphMastery: "Mastery", graphAttempts: "Attempts", graphTrace: "Learning trace", graphPrereq: "Prerequisites", graphPractice: "Practice",
  graphLastErr: "Last error", graphBKT: "BKT p(known)", graphDKT: "DKT logit", graph3hAgo: "3h ago",
  dashTitle: "Learning analytics", dashSub: "Socratic progress · last 30 days",
  dashExport: "Export PDF", dashSessions: "Sessions", dashSolved: "Solved", dashRate: "Solve rate", dashHints: "Hints used",
  dashMastery: "Mastery by topic", dashActivity: "Activity · 12 weeks", dashErrors: "Error distribution", dashReco: "Recommendations",
  errAlgebra: "Algebraic", errArith: "Arithmetic", errConcept: "Conceptual", errMethod: "Wrong method", errSyntax: "Notation",
  recoTitle: "What to practice next",
  recoItems: [
    "Chain rule · ↑12% over 3 sessions",
    "Integration by parts · move from MEDIUM to HARD",
    "Thermal balance · weak area in physics",
  ],
  profTitle: "Profile", profStreak: "day streak", profSessions: "sessions", profProblems: "problems", profMastery: "avg mastery",
  profRecent: "Recent activity", profMasteryByTopic: "Mastery by topic", profStrong: "Strengths", profWeak: "To practice", profFocusWeek: "Focus · week", profEmotion: "Emotional state", profEmotionDesc: "RuBERT detector · conf. 0.84", profEdit: "Edit",
  srcTitle: "Knowledge sources", srcSub: "Knowledge Forge · active graph · not RAG",
  srcAdd: "Add source", srcPipeline: "PIPELINE", srcStatus: "Status",
  srcStatPending: "Queued", srcStatExtracting: "Extracting", srcStatExtracted: "Extracted", srcStatFailed: "Failed",
  srcNodes: "nodes", srcEdges: "edges", srcAdded: "added",
  setTitle: "Settings", setSub: "Appearance · effects · interface",
  setTheme: "Theme", setEffects: "Effects", setLanguage: "Language", setAbout: "About",
  setMotion: "Animations", setGlow: "Accent glow", setParticles: "Background particles", setGrain: "Grain texture",
  setAboutText: "MITS v.2.6.1 · Math Intelligent Tutoring System · Qwen3.5-9B · GSPO → KTO → DPO · Base 55.1% → 66.5% · Bauman MSTU · 2024–2026",
  strongSkills: ["Basic derivatives", "Chain rule", "Algebra"],
  weakSkills: ["Thermal balance", "Electromagnetism", "Dynamic programming"],
  difficulty_easy: "easy", difficulty_medium: "medium", difficulty_hard: "hard", difficulty_olympiad: "olympiad",
});

window.MITS_DATA = { I18N, DIALOG, SESSIONS, SKILLS, TECH_TAGS, NAV_KEYS, DOMAIN_COLOR, TASKS_DATA, GRAPH_NODES, GRAPH_EDGES, RECENT, SOURCES_LIST, PIPELINE_STEPS };
