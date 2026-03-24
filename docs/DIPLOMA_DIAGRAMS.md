# MITS: Блок-схемы системы

Все диаграммы в формате Mermaid. Для рендеринга: VS Code (Mermaid Preview), GitHub, или [mermaid.live](https://mermaid.live).

---

## 1. Общая архитектура системы

```mermaid
graph TB
    subgraph USER["Пользователь (Браузер)"]
        Browser["Next.js 14 SPA"]
    end

    subgraph FRONTEND["Frontend — Next.js 14 + TypeScript"]
        Pages["Страницы<br/>Auth | Chat | Dashboard | Profile"]
        Hooks["Хуки<br/>useChat | useWebSocket"]
        Store["Zustand Store<br/>chatStore.ts"]
        API_Client["REST/WS клиент<br/>api.ts"]
    end

    subgraph BACKEND["Backend — FastAPI + Python 3.11"]
        Router["API Router v1"]
        Auth["Аутентификация<br/>JWT + Argon2"]
        WS["WebSocket<br/>Streaming"]
        REST["REST API<br/>25+ эндпоинтов"]
        OrcService["Orchestrator Service<br/>Мост async↔sync"]
        Analytics["Analytics Service"]
        DB["SQLite<br/>Users | Sessions | Messages"]
    end

    subgraph AGENTS["Мультиагентное ядро — Python"]
        Orchestrator["Оркестратор<br/>orchestrator.py"]
        Profiler["Профилировщик<br/>Диагностика ученика"]
        Planner["Планировщик<br/>Выбор стратегии"]
        Tutor["Тьютор<br/>Сократический диалог"]
        Verifier["Верификатор<br/>Контроль качества"]
        Affective["Аффективный агент<br/>Детекция эмоций"]
        TaskGen["Генератор задач"]
    end

    subgraph KNOWLEDGE["Система знаний"]
        KT["Knowledge Tracing<br/>BKT + DKT"]
        RAG["RAG<br/>ChromaDB + Embeddings"]
        SkillGraph["Граф навыков<br/>skill_graph.json"]
        FewShot["Few-Shot банк<br/>Примеры решений"]
        Misconceptions["База заблуждений"]
    end

    subgraph LLM["LLM Inference"]
        Ollama["Ollama Server<br/>localhost:11434"]
        Model["Qwen3.5-9B<br/>Fine-tuned (GGUF Q4_K_M)"]
        Cache["Кеш ответов"]
    end

    subgraph TRAINING["ML Pipeline — Google Colab A100"]
        GSPO["Stage 1: GSPO"]
        RAFT["Stage 2: RAFT++"]
        DPO["Stage 3: DPO"]
        Eval["Evaluation<br/>3678 задач"]
        HF["HuggingFace Hub<br/>Адаптеры + Датасеты"]
    end

    Browser <-->|HTTP/WS| FRONTEND
    Pages --> Hooks
    Hooks --> Store
    Hooks --> API_Client

    API_Client <-->|REST + WebSocket| Router
    Router --> Auth
    Router --> WS
    Router --> REST
    WS --> OrcService
    REST --> OrcService
    REST --> Analytics
    OrcService --> DB
    Analytics --> DB

    OrcService -->|process_turn| Orchestrator
    Orchestrator --> Profiler
    Orchestrator --> Planner
    Orchestrator --> Tutor
    Orchestrator --> Verifier
    Orchestrator --> Affective
    Orchestrator --> TaskGen

    Profiler --> KT
    Tutor --> RAG
    Planner --> SkillGraph
    Tutor --> FewShot
    Profiler --> Misconceptions

    Tutor -->|generate_stream| Ollama
    Ollama --> Model
    Tutor --> Cache

    GSPO --> RAFT --> DPO
    DPO -->|export GGUF| Model
    Eval --> HF
    GSPO --> HF
    RAFT --> HF

    style USER fill:#e1f5fe
    style FRONTEND fill:#e8f5e9
    style BACKEND fill:#fff3e0
    style AGENTS fill:#fce4ec
    style KNOWLEDGE fill:#f3e5f5
    style LLM fill:#e0f2f1
    style TRAINING fill:#fff9c4
```

---

## 2. Мультиагентный конвейер (детально)

```mermaid
flowchart TD
    Input["Ввод ученика<br/>(текст, формула, изображение)"]

    subgraph PROFILER["1. Профилировщик"]
        P1["Анализ ответа"]
        P2["Классификация ошибки<br/>conceptual | procedural |<br/>careless | notation | misconception"]
        P3["Оценка уверенности<br/>low | medium | high | confused"]
        P4["Когнитивная нагрузка<br/>CLT: low | optimal | high | overload"]
        P5["Knowledge Tracing<br/>BKT (P(L)) + DKT (LSTM)"]
        P1 --> P2 --> P3 --> P4 --> P5
    end

    subgraph PLANNER["2. Планировщик"]
        PL1{"Стратегия?"}
        PL2["GUIDED_DISCOVERY<br/>Наводящие вопросы"]
        PL3["SCAFFOLDED<br/>Декомпозиция задачи"]
        PL4["ERROR_CORRECTION<br/>Исправление ошибок"]
        PL5["CONCEPTUAL_REPAIR<br/>Устранение заблуждения"]
        PL6["ENCOURAGEMENT<br/>Мотивация"]
        PL7["COGNITIVE_OFFLOAD<br/>Упрощение"]
        PL8["DIRECT_INSTRUCTION<br/>Прямое объяснение"]
        PL1 -->|"понимание > 0.7"| PL2
        PL1 -->|"процедурная ошибка"| PL3
        PL1 -->|"ошибки > 2"| PL4
        PL1 -->|"заблуждение"| PL5
        PL1 -->|"уверенность low"| PL6
        PL1 -->|"нагрузка high"| PL7
        PL1 -->|"подсказок >= 3"| PL8
    end

    subgraph TUTOR["3. Тьютор"]
        T1["Сборка промпта<br/>system + plan + history + RAG"]
        T2["LLM генерация<br/>Qwen3.5-9B (thinking mode)"]
        T3["Парсинг ответа<br/>&lt;think&gt;...&lt;/think&gt; + content"]
        T4["Форматирование<br/>LaTeX, структура, move_type"]
        T1 --> T2 --> T3 --> T4
    end

    subgraph VERIFIER["4. Верификатор"]
        V1["Утечка ответа?"]
        V2["Сократический метод?"]
        V3["LaTeX корректен?"]
        V4["Русский язык?"]
        V5["Длина адекватна?"]
        V6{"Качество ≥ 0.7?"}
        V7["Пропустить"]
        V8["Запросить<br/>переформулировку"]
        V1 --> V2 --> V3 --> V4 --> V5 --> V6
        V6 -->|Да| V7
        V6 -->|Нет| V8
    end

    Input --> PROFILER
    PROFILER -->|StudentProfile| PLANNER
    PLANNER -->|TeachingPlan| TUTOR
    TUTOR -->|TutorResponse| VERIFIER
    VERIFIER --> Output["Ответ ученику<br/>(streaming)"]
    V8 -.->|retry| TUTOR

    style PROFILER fill:#e3f2fd
    style PLANNER fill:#e8f5e9
    style TUTOR fill:#fff3e0
    style VERIFIER fill:#fce4ec
```

---

## 3. Пайплайн обучения (3-Stage RL)

```mermaid
flowchart LR
    Base["Qwen3.5-9B<br/>Baseline"]

    subgraph S1["Stage 1: GSPO"]
        G1["Группы по 16 completions"]
        G2["7 оптимизаций:<br/>Dr.GRPO, ReDit, GDPO,<br/>LEAD, Clip-Higher,<br/>Zero-Var Mask, Seq-IS"]
        G3["Curriculum:<br/>easy → medium → hard"]
        G1 --> G2 --> G3
    end

    subgraph S2["Stage 2: RAFT++"]
        R1["GVM-RAFT<br/>Динамическая аллокация"]
        R2["800 задач/раунд<br/>Стратифицированная выборка"]
        R3["SFT на верных<br/>решениях"]
        R4["Сохранение негативов<br/>→ DPO"]
        R1 --> R2 --> R3
        R2 --> R4
    end

    subgraph S3["Stage 3: DPO"]
        D1["Пары (chosen, rejected)<br/>из RAFT++ негативов"]
        D2["Полировка формата<br/>и стиля"]
        D3["β=0.1,<br/>SimPO loss"]
        D1 --> D2 --> D3
    end

    subgraph EVAL["Evaluation"]
        E1["3678 задач<br/>MGSM + ruMMLU + custom"]
        E2["5 доменов:<br/>math | physics | chemistry<br/>biology | cs"]
        E3["SymPy + ChemPy<br/>верификация"]
    end

    subgraph DEPLOY["Деплой"]
        DEP1["Merge LoRA"]
        DEP2["Export GGUF<br/>Q4_K_M"]
        DEP3["Ollama<br/>serve"]
    end

    Base --> S1
    S1 --> S2
    S2 --> S3
    S3 --> EVAL
    S3 --> DEPLOY
    DEP1 --> DEP2 --> DEP3

    S1 -.->|checkpoint| HF1["HF: mits-qwen3-9b-gspo"]
    S2 -.->|checkpoint| HF2["HF: mits-qwen3-9b-raft"]
    S3 -.->|checkpoint| HF3["HF: mits-qwen3-9b-final"]
    EVAL -.->|reports| Reports["evaluation/reports/*.json"]

    style S1 fill:#e3f2fd
    style S2 fill:#e8f5e9
    style S3 fill:#fce4ec
    style EVAL fill:#f3e5f5
    style DEPLOY fill:#e0f2f1
```

---

## 4. Поток данных (Data Flow)

```mermaid
flowchart TB
    subgraph SOURCES["Источники данных"]
        MGSM["MGSM Russian<br/>250 задач"]
        ruMMLU["ruMMLU STEM<br/>3210 задач"]
        Custom["Custom STEM<br/>218 задач"]
        RLData["rl_combined.jsonl<br/>14,203 задачи"]
    end

    subgraph PREP["Подготовка"]
        BuildBench["build_eval_benchmark.py"]
        GenData["generate_stem_data.ipynb"]
        SortCurr["sort_curriculum.py"]
    end

    subgraph DATASETS["Датасеты"]
        EvalDS["eval_dataset.jsonl<br/>3678 задач (бенчмарк)"]
        TrainDS["training_dataset.jsonl<br/>RL обучение"]
        NegDS["raft_negatives.jsonl<br/>Негативы для DPO"]
    end

    subgraph TRAINING_FLOW["Обучение (Colab A100)"]
        Stage1["GSPO<br/>grpo_qwen3.5_9b.ipynb"]
        Stage2["RAFT++<br/>raft_plus_qwen3.5_9b.ipynb"]
        Stage3["DPO<br/>dpo_polish_qwen3.5_9b.ipynb"]
    end

    subgraph ARTIFACTS["Артефакты"]
        Adapters["LoRA адаптеры<br/>HuggingFace Hub"]
        GGUF["GGUF модель<br/>Q4_K_M квантизация"]
        Reports["Отчеты оценки<br/>evaluation/reports/"]
        Negatives["Негативные пары<br/>RAFT++ → DPO"]
    end

    subgraph INFERENCE["Инференс (локально)"]
        OllamaServ["Ollama Server"]
        Agents["Мультиагентная<br/>система"]
        UserApp["Веб-приложение<br/>MITS"]
    end

    MGSM --> BuildBench
    ruMMLU --> BuildBench
    Custom --> BuildBench
    BuildBench --> EvalDS

    RLData --> SortCurr
    SortCurr --> TrainDS

    Custom --> GenData
    GenData --> TrainDS

    TrainDS --> Stage1
    Stage1 --> Stage2
    Stage2 --> Stage3
    Stage2 -->|negatives| NegDS
    NegDS --> Stage3

    Stage1 --> Adapters
    Stage2 --> Adapters
    Stage3 --> Adapters
    Stage3 --> GGUF

    EvalDS --> Reports

    GGUF --> OllamaServ
    OllamaServ --> Agents
    Agents --> UserApp

    style SOURCES fill:#e1f5fe
    style PREP fill:#e8f5e9
    style DATASETS fill:#fff3e0
    style TRAINING_FLOW fill:#fce4ec
    style ARTIFACTS fill:#f3e5f5
    style INFERENCE fill:#e0f2f1
```

---

## 5. Архитектура Knowledge Tracing

```mermaid
flowchart TD
    Input["Ответ ученика<br/>(skill, correct, timestamp)"]

    subgraph BKT["Bayesian Knowledge Tracing"]
        B1["P(L₀) = prior"]
        B2["P(L_t+1) = P(L_t) + (1-P(L_t))×p_t"]
        B3["p_t = P(correct | learned)"]
        B4["slip = P(incorrect | learned)"]
        B1 --> B2
        B3 --> B2
        B4 --> B2
    end

    subgraph DKT["Deep Knowledge Tracing"]
        D1["Embedding<br/>skill_id → vector"]
        D2["LSTM cell<br/>hidden_state_t"]
        D3["Linear → σ<br/>P(mastery)"]
        D1 --> D2 --> D3
    end

    subgraph COMBINE["Комбинирование"]
        C1["mastery = 0.4×BKT + 0.5×DKT + 0.1×recency"]
        C2{"mastery ≥ 0.7?"}
        C3["Навык освоен ✓"]
        C4["Продолжить<br/>обучение"]
        C1 --> C2
        C2 -->|Да| C3
        C2 -->|Нет| C4
    end

    Input --> BKT
    Input --> DKT
    BKT -->|"P(L)"| COMBINE
    DKT -->|"P(mastery)"| COMBINE
    COMBINE --> Planner["→ Планировщик<br/>(выбор стратегии)"]

    style BKT fill:#e3f2fd
    style DKT fill:#e8f5e9
    style COMBINE fill:#fff3e0
```

---

## 6. Стек технологий

```mermaid
mindmap
  root((MITS))
    Frontend
      Next.js 14
      TypeScript 5
      Tailwind CSS
      shadcn/ui
      Zustand
      WebSocket
      KaTeX
    Backend
      FastAPI
      SQLAlchemy
      SQLite
      JWT PyJWT
      Argon2
      Uvicorn
    Core
      Python 3.11
      Ollama API
      ChromaDB
      sentence-transformers
      SymPy
      ChemPy
      structlog
    Training
      Unsloth
      TRL
        GRPOTrainer
        DPOTrainer
        SFTTrainer
      PEFT QLoRA
      bitsandbytes
      Google Colab A100
      HuggingFace Hub
    Evaluation
      3678 benchmark
      SymPy verify
      ChemPy verify
      Per-domain metrics
```

---

## 7. Схема WebSocket-стриминга

```mermaid
sequenceDiagram
    participant U as Пользователь
    participant F as Frontend (Next.js)
    participant W as WebSocket Handler
    participant O as Orchestrator Service
    participant A as Агенты (4 шт.)
    participant L as LLM (Ollama)

    U->>F: Ввод сообщения
    F->>F: addMessage (Zustand)
    F->>W: WS: {"type":"message","content":"..."}
    W->>O: process_message_stream()
    O->>O: Загрузка сессии из DB
    O->>A: process_turn(context, input)

    Note over A: Profiler → Planner → Tutor

    A->>L: generate_stream(prompt)

    loop Токены (streaming)
        L-->>A: token
        A-->>O: yield token
        O-->>W: AsyncGenerator
        W-->>F: WS: {"type":"token","content":"...","is_thinking":bool}
        F-->>F: appendStreamingContent()
        F-->>U: Отображение в реальном времени
    end

    A->>A: Verifier.verify()
    A-->>O: TurnResult
    O->>O: Сохранение в DB
    O-->>W: response_complete
    W-->>F: WS: {"type":"response_complete","response":{...}}
    F-->>F: addMessage (final)
    F-->>U: Полный ответ
```
