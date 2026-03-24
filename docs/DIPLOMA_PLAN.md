# План дипломной работы (ВКР)

**Тема:** Разработка интеллектуальной системы обучения STEM-дисциплинам на основе мультиагентной архитектуры и дообученной языковой модели

**Объем:** ~80-100 страниц (без приложений)

---

## Структура

### ВВЕДЕНИЕ (~3-4 стр.)

- **Актуальность темы**
  - Рост спроса на STEM-образование; нехватка репетиторов
  - Развитие LLM (GPT-4, Qwen, DeepSeek) открывает возможности для персонализированного обучения
  - Существующие ITS (Khan Academy, Duolingo) не используют сократический метод с LLM
  - Необходимость адаптации к русскоязычным ученикам

- **Цель работы**
  - Разработать интеллектуальную систему обучения (ITS), реализующую сократический диалог по 5 STEM-дисциплинам с использованием мультиагентной архитектуры и дообученной LLM

- **Задачи**
  1. Провести анализ существующих ITS и методов обучения с подкреплением для LLM
  2. Спроектировать мультиагентную архитектуру тьюторской системы
  3. Реализовать полный стек (фронтенд, бэкенд, агенты, inference)
  4. Разработать и провести 3-стадийный пайплайн дообучения Qwen3.5-9B
  5. Создать бенчмарк (3678 задач) и провести экспериментальную оценку
  6. Внедрить систему отслеживания знаний (BKT + DKT)

- **Объект исследования** — процесс автоматизированного обучения STEM-дисциплинам
- **Предмет исследования** — мультиагентная архитектура ITS с дообученной LLM
- **Методы исследования** — машинное обучение (RL, DPO, SFT), байесовские модели, архитектурное проектирование
- **Научная новизна** — комбинация мультиагентного сократического тьютора с 3-стадийным RL-дообучением модели + dual Knowledge Tracing (BKT+DKT)
- **Практическая значимость** — готовая к использованию система для русскоязычных учеников 7-11 классов

---

### ГЛАВА 1. АНАЛИТИЧЕСКИЙ ОБЗОР (~15-18 стр.)

#### 1.1. Интеллектуальные обучающие системы (ITS) (~4 стр.)
- Определение ITS, история развития (от PLATO до LLM-based)
- Архитектуры ITS: модель ученика, модель предмета, педагогическая модель, интерфейс
- Обзор существующих систем: Carnegie Learning, ALEKS, Khan Academy, Khanmigo
- Таблица сравнения (функциональность, методы, языки, open-source)

#### 1.2. Педагогические теории в контексте ITS (~3 стр.)
- Сократический метод: принципы, типы вопросов, применимость в ИИ
- Теория когнитивной нагрузки (CLT, Sweller 1988) — управление сложностью
- Зона ближайшего развития (ZPD, Vygotsky) — адаптивная сложность
- Scaffolding — постепенное снятие поддержки
- Таксономия Блума — уровни понимания

#### 1.3. Большие языковые модели для образования (~4 стр.)
- Обзор архитектур: GPT-4, Qwen3, DeepSeek, Llama
- Thinking mode (Chain-of-Thought): Qwen3 `<think>`, DeepSeek-R1
- Проблемы: галлюцинации, утечка ответов, несогласованность
- Мультиагентные системы на LLM: GenMentor (WWW 2025), AutoGen, CrewAI
- Обоснование выбора Qwen3.5-9B (open-source, thinking mode, русский язык, 4B = локальный деплой)

#### 1.4. Обучение с подкреплением для LLM (~4 стр.)
- RLHF → GRPO → GSPO (Qwen3 paper, arXiv:2507.18071)
- Rejection Sampling: ReST, STaR, RAFT
- DPO (Direct Preference Optimization) vs PPO
- Curriculum learning для RL (easy → hard)
- Обзор техник: Dr.GRPO, ReDit, GDPO, Clip-Higher

#### 1.5. Отслеживание знаний (Knowledge Tracing) (~3 стр.)
- Bayesian Knowledge Tracing (BKT, Corbett & Anderson 1994)
- Deep Knowledge Tracing (DKT, Piech et al. 2015)
- Гибридные подходы (BKT + DKT)
- Применение в адаптивном обучении

**Выводы по главе 1:** формулировка требований к разрабатываемой системе

---

### ГЛАВА 2. ПРОЕКТИРОВАНИЕ СИСТЕМЫ (~18-22 стр.)

#### 2.1. Требования к системе (~3 стр.)
- Функциональные: сократический диалог, 5 доменов, 4 уровня сложности, 3 режима
- Нефункциональные: latency < 3с (first token), русский язык, локальный деплой
- Пользовательские сценарии (use cases)

#### 2.2. Общая архитектура (~4 стр.)
- 3-уровневая архитектура: Frontend → Backend → AI Core
- **Блок-схема** общей архитектуры (см. DIPLOMA_DIAGRAMS.md, диаграмма 1)
- Обоснование выбора технологий:
  - Frontend: Next.js 14 (SSR, App Router, React Server Components)
  - Backend: FastAPI (async, WebSocket, auto-docs)
  - DB: SQLite (portability, zero-config)
  - LLM: Ollama (локальный, GGUF, API-совместимый)

#### 2.3. Мультиагентная архитектура (~5 стр.)
- Паттерн «конвейер агентов» (GenMentor): Profiler → Planner → Tutor → Verifier
- **Блок-схема** конвейера (диаграмма 2)
- Профилировщик: классификация ошибок, модель ученика
- Планировщик: 8 стратегий обучения, дерево принятия решений
- Тьютор: промпт-инжиниринг, streaming, thinking mode
- Верификатор: 10 проверок качества, score ≥ 0.7
- Аффективный агент: детекция эмоций (RuBERT)

#### 2.4. Модель ученика и Knowledge Tracing (~3 стр.)
- Dual-model: BKT (вероятностный) + DKT (нейросетевой)
- Формула комбинирования: mastery = 0.4×BKT + 0.5×DKT + 0.1×recency
- Граф навыков: предпосылки, связи, уровни
- **Блок-схема** Knowledge Tracing (диаграмма 5)

#### 2.5. RAG-система (~2 стр.)
- Архитектура: ChromaDB + sentence-transformers embeddings
- Источники: база задач, примеры решений, база заблуждений
- Контекст для тьютора: hints, worked examples, misconception fixes

#### 2.6. Система стриминга (~3 стр.)
- WebSocket protocol: типы сообщений, формат
- Мост sync→async: ThreadPoolExecutor + asyncio.Queue
- Парсинг thinking-блоков в реальном времени
- **Sequence diagram** стриминга (диаграмма 7)

#### 2.7. Проектирование пайплайна обучения (~2 стр.)
- 3-стадийная архитектура: GSPO → RAFT++ → DPO
- Обоснование удаления SFT (Instruct-модель уже умеет диалог)
- **Блок-схема** пайплайна (диаграмма 3)
- Потоки данных (диаграмма 4)

**Выводы по главе 2:** спроектированная архитектура удовлетворяет требованиям

---

### ГЛАВА 3. РЕАЛИЗАЦИЯ (~18-22 стр.)

#### 3.1. Реализация фронтенда (~4 стр.)
- Структура приложения: App Router, 5 страниц
- Zustand store: управление состоянием чата
- useChat / useWebSocket hooks: потоковое взаимодействие
- UI: shadcn/ui компоненты, KaTeX для формул
- Скриншоты интерфейса (2-3 шт.)

#### 3.2. Реализация бэкенда (~4 стр.)
- FastAPI: 25+ эндпоинтов, API v1
- Аутентификация: JWT (access + refresh), Argon2 хеширование
- ORM: SQLAlchemy 2.0, 4 таблицы (User, Session, Message, RefreshToken)
- WebSocket handler: потоковая передача токенов
- Листинги ключевых функций

#### 3.3. Реализация мультиагентного ядра (~5 стр.)
- BaseAgent: абстрактный интерфейс (process, health_check, get_metrics)
- Orchestrator: координация 4 агентов, graceful degradation
- Профилировщик: промпт + парсинг JSON + BKT/DKT интеграция
- Планировщик: дерево решений, 8 стратегий
- Тьютор: сборка контекста (system prompt + plan + RAG + history), streaming
- Верификатор: regex проверки, score, retry logic
- Листинги ключевого кода

#### 3.4. Реализация LLM inference (~3 стр.)
- LLMClient: generate(), generate_stream(), fallback models
- Ollama integration: API, model management
- Кеширование: TTL-based, prompt hash
- Batch processing и оптимизации

#### 3.5. Реализация пайплайна обучения (~4 стр.)
- Stage 1 — GSPO: 7 оптимизаций (Dr.GRPO, ReDit, GDPO, LEAD, Clip-Higher, Zero-Var, Seq-IS)
- Stage 2 — RAFT++: GVM динамическая аллокация, negative saving, `native_matmul()` оптимизация
- Stage 3 — DPO: preference pairs из RAFT++ негативов
- Таблица гиперпараметров для каждой стадии
- Инфраструктура: Google Colab A100, HuggingFace Hub, checkpoint recovery

#### 3.6. Бенчмарк и инструменты оценки (~2 стр.)
- build_eval_benchmark.py: сборка из MGSM + ruMMLU + custom (3678 задач)
- evaluate_stage.py: inference + verify (SymPy, ChemPy) + report
- Структура отчетов: per-domain accuracy, answer extraction rate

**Выводы по главе 3:** система полностью реализована и готова к экспериментальной оценке

---

### ГЛАВА 4. ЭКСПЕРИМЕНТАЛЬНОЕ ИССЛЕДОВАНИЕ (~15-18 стр.)

#### 4.1. Методология эксперимента (~3 стр.)
- Бенчмарк: 3678 задач, 5 доменов, 3 уровня сложности
- Источники: MGSM Russian (250), ruMMLU STEM (3210), Custom (218)
- Метрики: accuracy (per-domain + overall), answer extraction rate
- Верификация: SymPy (math), ChemPy (chemistry), regex + tolerance (physics), exact match (CS, bio)
- Условия: Ollama local (GGUF Q4_K_M), temperature=0.3

#### 4.2. Результаты базовой модели (~2 стр.)
- Qwen3.5-9B baseline: 55.1% overall
- Разбивка по доменам: math 79.1%, physics 74.4%, cs 46.5%, chemistry 46.7%, bio 28.6%
- Анализ: сильные/слабые стороны, типичные ошибки

#### 4.3. Результаты по стадиям обучения (~5 стр.)
- **Таблица:** Accuracy per stage per domain (Base → GSPO → RAFT++ → DPO)
- **Графики:** Кривые обучения, convergence plots
- Stage 1 (GSPO): RL with verifiable rewards + curriculum
- Stage 2 (RAFT++): rejection sampling + quality filtering
- Stage 3 (DPO): preference learning + format polishing

#### 4.4. Ablation study (~3 стр.)
- Вклад каждой из 7 оптимизаций GSPO
- Эффект curriculum learning (easy→hard vs random)
- Эффект GVM dynamic allocation vs flat generation
- Эффект negative saving для DPO

#### 4.5. Качественный анализ (~3 стр.)
- Примеры сократических диалогов (2-3 примера: math, physics, chemistry)
- Сравнение: базовая модель vs дообученная (стиль, точность, метод)
- Анализ move types: scaffolding, problematize, rectify, encourage
- Качество thinking-рассуждений

#### 4.6. Анализ Knowledge Tracing (~2 стр.)
- Точность предсказания BKT vs DKT vs combined
- Корреляция mastery score и реальной успеваемости
- Adaptive difficulty: работает ли подстройка сложности

**Выводы по главе 4:** подтверждение эффективности пайплайна дообучения (+11.4%) и мультиагентной архитектуры

---

### ЗАКЛЮЧЕНИЕ (~2-3 стр.)

- Краткое изложение полученных результатов (по каждой задаче)
- Достигнутые показатели: +11.4% accuracy, 5 доменов, 25+ API endpoints, 3-стадийный пайплайн
- Практическая применимость: готовая система для русскоязычных учеников
- Ограничения работы:
  - Модель 9B — ограниченные возможности для олимпиадных задач
  - SQLite — не масштабируется на 1M+ пользователей
  - Evaluation только автоматическое (нет user study)
- Направления дальнейшего развития:
  - Модель побольше (Qwen3.5-35B-A3B при развитии hardware)
  - User study с реальными учениками
  - Gamification и мотивационная система
  - Мультимодальность (распознавание рукописных формул)
  - PostgreSQL + горизонтальное масштабирование

---

### СПИСОК ЛИТЕРАТУРЫ (~40-60 источников)

**Ключевые источники:**

1. VanLehn, K. (2011). The Relative Effectiveness of Human Tutoring, ITS, and Other Tutoring Systems. *Educational Psychologist*, 46(4).
2. Qwen Team (2025). Qwen3 Technical Report. *arXiv:2507.18071*.
3. Rafailov et al. (2023). Direct Preference Optimization. *NeurIPS*.
4. Shao et al. (2024). DeepSeekMath: GRPO. *arXiv:2402.03300*.
5. Corbett & Anderson (1994). Knowledge Tracing: Modeling the Acquisition of Procedural Knowledge. *User Modeling and User-Adapted Interaction*.
6. Piech et al. (2015). Deep Knowledge Tracing. *NeurIPS*.
7. Singh et al. (2024). Beyond Human Data: Scaling Self-Training for Problem-Solving (STaR). *arXiv*.
8. Sweller (1988). Cognitive Load During Problem Solving. *Cognitive Science*.
9. GenMentor (2025). Multi-Agent Tutoring Framework. *WWW 2025*.
10. Zelikman et al. (2022). STaR: Bootstrapping Reasoning With Reasoning. *NeurIPS*.
11. Yuan et al. (2023). RAFT: Reward rAnked FineTuning. *arXiv*.
12. GVM-RAFT (2025). Minimalist Approach to LLM Reasoning. *arXiv:2504.11343*.
13. Harnessing Negative Signals (2025). *arXiv:2505.24850*.
14. Ames et al. (2024). Clip-Higher: Asymmetric Clipping for GRPO. *arXiv*.
15. Bloom (1956). Taxonomy of Educational Objectives. *Longmans*.
16. Vygotsky (1978). Mind in Society: Development of Higher Psychological Processes. *Harvard UP*.

**Технические источники (библиотеки и фреймворки):**
- Next.js 14, FastAPI, SQLAlchemy, Ollama, Unsloth, TRL, PEFT, ChromaDB, SymPy

---

### ПРИЛОЖЕНИЯ

#### Приложение А. Скриншоты интерфейса (~5 стр.)
- Экран авторизации
- Главная страница (список сессий)
- Чат (сократический диалог, thinking mode)
- Аналитика (графики, mastery по навыкам)
- Профиль пользователя

#### Приложение Б. Листинги ключевого кода (~10-15 стр.)
- Orchestrator.process_turn() — координация агентов
- generate_and_filter() — RAFT++ генерация с GVM
- native_matmul() — оптимизация inference для Unsloth
- verify_completion() — верификация ответов (SymPy/ChemPy)
- useChat hook — фронтенд стриминг
- WebSocket handler — мост async↔sync

#### Приложение В. Таблицы результатов (~3-5 стр.)
- Полная таблица accuracy per domain per stage
- Гиперпараметры для каждой стадии обучения
- Структура бенчмарка (3678 задач по доменам/сложности/источникам)

#### Приложение Г. Примеры диалогов (~5 стр.)
- Пример 1: Алгебра (квадратные уравнения) — scaffolding
- Пример 2: Физика (кинематика) — guided discovery
- Пример 3: Химия (балансировка реакций) — error correction
- Пример 4: Информатика (алгоритмы) — problematize

#### Приложение Д. Диаграммы (~3-5 стр.)
- Все Mermaid-диаграммы из DIPLOMA_DIAGRAMS.md (отрендеренные)

---

## Примерное распределение объема

| Раздел | Страниц | % |
|--------|---------|---|
| Введение | 3-4 | 4% |
| Глава 1. Аналитический обзор | 15-18 | 18% |
| Глава 2. Проектирование | 18-22 | 22% |
| Глава 3. Реализация | 18-22 | 22% |
| Глава 4. Эксперименты | 15-18 | 18% |
| Заключение | 2-3 | 3% |
| Список литературы | 3-4 | 4% |
| **Итого основной текст** | **~80-90** | **~90%** |
| Приложения | 25-35 | — |
| **Итого с приложениями** | **~110-125** | — |
