# MITS - Статус проекта

> Последнее обновление: Февраль 2026

## О проекте

**MITS** (Math Intelligent Tutoring System) — интеллектуальная система обучения STEM-дисциплинам с использованием сократического метода. Репетитор направляет ученика через вопросы, не давая прямых ответов.

### Целевые дисциплины
- Математика (алгебра, анализ, геометрия, статистика)
- Программирование (Python, алгоритмы, структуры данных)
- Физика (кинематика, динамика, электричество, оптика)
- Химия (строение атома, реакции, органика, растворы)
- Биология (клетка, генетика, экология, эволюция)

### Целевое оборудование
- **Inference:** CPU (Ryzen 5 9500f), 16GB RAM, Windows — Ollama + Q8_0 (~4GB)
- **Training:** Google Colab A100 40GB / 80GB

---

## Архитектура системы

```
┌─────────────────────────────────────────────────────────────────┐
│                    Next.js 14 + TypeScript                       │
│           Tailwind CSS, shadcn/ui, Zustand, WebSocket            │
└──────────────────────────────┬──────────────────────────────────┘
                               │ REST + WebSocket
┌──────────────────────────────▼──────────────────────────────────┐
│                      FastAPI Backend                              │
│   JWT Auth │ Sessions (SQLite) │ Analytics │ Export (PDF)         │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ Profiler │→│ Planner  │→│  Tutor   │→│ Verifier │         │
│  │Диагностика│ │Стратегия │ │Генерация │ │Проверка  │         │
│  │ошибок    │  │обучения  │  │ответа   │  │качества  │         │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘         │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │   RAG    │  │Knowledge │  │ Emotion  │  │   OCR    │         │
│  │ChromaDB  │  │ Tracing  │  │ Detector │  │Qwen2.5-VL│         │
│  │          │  │ BKT+DKT  │  │ RuBERT   │  │          │         │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘         │
│                                                                   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│      Ollama + Qwen3-4B-Instruct-2507 (fine-tuned, Q8_0)          │
│            CPU inference, streaming token-by-token                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Прогресс реализации

### Фаза 1: Инфраструктура ✅ ЗАВЕРШЕНА

| Компонент | Статус | Файл |
|-----------|--------|------|
| Генератор диалогов Cerebras | ✅ | `training/scripts/cerebras_dialog_generator.py` |
| База знаний RAG (hints) | ✅ | `data/knowledge/hints/*.jsonl` |
| База знаний RAG (ошибки) | ✅ | `data/knowledge/misconceptions/*.jsonl` |
| Граф навыков | ✅ | `data/knowledge/skill_graph.json` |
| Менеджер моделей | ✅ | `src/inference/model_manager.py` |
| Слой кэширования | ✅ | `src/inference/cache.py` |
| RAG Retriever | ✅ | `src/knowledge/rag_retriever.py` |

### Фаза 2: Многоагентная система ✅ ЗАВЕРШЕНА

| Компонент | Статус | Файл |
|-----------|--------|------|
| Агент Профайлер | ✅ | `src/agents/profiler.py` |
| Агент Планировщик | ✅ | `src/agents/planner.py` |
| Агент Верификатор | ✅ | `src/agents/verifier.py` |
| Оркестратор | ✅ | `src/agents/orchestrator.py` |
| Интеграция с TutorAgent | ✅ | `src/agents/tutor_agent.py` |

### Фаза 3: Оценка качества ✅ ЗАВЕРШЕНА

| Компонент | Статус | Файл |
|-----------|--------|------|
| Метрики качества | ✅ | `evaluation/metrics.py` |
| CLI оценки | ✅ | `evaluation/evaluate_model.py` |
| RAG в оркестраторе | ✅ | `src/agents/orchestrator.py` |
| Документация моделей | ✅ | `docs/MODEL_SELECTION.md` |

### Фаза 4: Генерация данных ✅ ЗАВЕРШЕНА

| Задача | Статус | Описание |
|--------|--------|----------|
| STEM генератор диалогов | ✅ | 5 дисциплин × 10 тем |
| Cerebras API интеграция | ✅ | 10 ключей, round-robin |
| Гибридный RL-датасет | ✅ | 14,203 задачи из 5 источников |
| Curriculum-классификация | ✅ | easy 39.9%, medium 34.8%, hard 25.2% |

### Фаза 5: Next.js + FastAPI миграция ✅ ЗАВЕРШЕНА

| Задача | Статус | Описание |
|--------|--------|----------|
| FastAPI backend | ✅ | REST + WebSocket + JWT auth |
| Next.js 14 frontend | ✅ | Tailwind + shadcn/ui + Zustand |
| Три режима чата | ✅ | Chat, Guided Learning, Task Generator |
| WebSocket streaming | ✅ | Sync-to-async через ThreadPoolExecutor |
| Session persistence | ✅ | SQLite + SQLAlchemy |

### Фаза 6: Comprehensive Improvements ✅ ЗАВЕРШЕНА

| Задача | Статус | Описание |
|--------|--------|----------|
| DKT Knowledge Tracing | ✅ | Pre-trained на ASSISTments |
| RuBERT эмоциональный детектор | ✅ | 5-class affective states |
| OCR рукописных решений | ✅ | Qwen2.5-VL |
| Analytics dashboard | ✅ | Recharts |
| A/B experiment framework | ✅ | Server-side experiments |
| PDF экспорт прогресса | ✅ | WeasyPrint |
| Docker Compose deployment | ✅ | Full stack |

### Фаза 7: Advanced Training Pipeline 🔄 В ПРОЦЕССЕ

> **Ветка**: `014-advanced-training-pipeline`
> **Модель**: Qwen3-4B-Instruct-2507 → GSPO → RAFT++ → AdaSTaR → DPO
> **Оборудование**: Google Colab A100 40GB / 80GB
> **Спецификация**: `specs/014-advanced-training-pipeline/`

**Обоснование удаления SFT:**
Стадия SFT была удалена из пайплайна. Qwen3-4B-Instruct уже обладает abilities
для инструкций и диалога (обучена с RLHF), поэтому дополнительный SFT на 38K примерах
переобучал модель на узкое распределение и снижал exploration diversity для GSPO.

**4-стадийный пайплайн обучения:**

| Стадия | Метод | Цель | Ноутбук | Статус |
|--------|-------|------|---------|--------|
| 1. GSPO | Group Sequence Policy Optimization | STEM reasoning через verifiable rewards + curriculum | `grpo_qwen3_4b.ipynb` | 🔄 |
| 2. RAFT++ | Rejection Sampling + GVM allocation | Self-distillation на верных решениях | `raft_plus_qwen3_4b.ipynb` | 📋 |
| 3. AdaSTaR | Adaptive Self-Taught Reasoner | Итеративная генерация с приоритизацией | `star_loop.ipynb` | 📋 |
| 4. DPO | Direct Preference Optimization | Полировка формата + reuse RAFT++ негативов | `dpo_polish_qwen3_4b.ipynb` | 📋 |

**Ключевые алгоритмические оптимизации (GSPO):**

| Техника | Статья | Эффект |
|---------|--------|--------|
| GSPO sequence-level IS | arXiv 2507.18071 | Importance sampling уровня Qwen3 |
| Dr. GRPO | arXiv 2503.20783 | Constant length normalization (без length bias) |
| ReDit дизеринг | arXiv 2506.18631 | Гауссовский шум на наградах → 10x сходимость |
| GDPO декаплинг | arXiv 2601.05242 | Независимая нормализация correctness и format |
| GRPO-LEAD | arXiv 2504.09696 | Difficulty-aware curriculum (hard=2×, easy=0.5×) |
| Zero-variance маскинг | arXiv 2505.22257 | Фильтрация групп с нулевой дисперсией |
| Clip-Higher | arXiv 2504.05118 | Асимметричный клиппинг ε=3e-4 / ε_high=4e-4 |

**Ключевые техники (RAFT++, AdaSTaR, DPO):**

| Техника | Стадия | Статья | Эффект |
|---------|--------|--------|--------|
| GVM-RAFT dynamic allocation | RAFT++ | arXiv 2504.11343 | 2-4x ускорение, адаптивный бюджет |
| Negative saving | RAFT++ | arXiv 2505.24850 | Сохранение неверных для DPO |
| Adaptive problem selection | AdaSTaR | STaR variant | Staleness + difficulty priority |
| RAFT++ negative reuse | DPO | arXiv 2505.24850 | Без повторной генерации |

### Evaluation Infrastructure ✅ ЗАВЕРШЕНА

| Компонент | Статус | Описание |
|-----------|--------|----------|
| Evaluation benchmark | ✅ | 3678 задач (MGSM + ruMMLU + custom) |
| Per-stage evaluation | ✅ | `evaluate_with_model()` + JSON reports |
| CSV summary for graphs | ✅ | `summary.csv` с per-stage метриками |
| Base model evaluation | ✅ | `evaluate_stage.py --stage base` |
| Inline notebook eval cells | ✅ | Компактные ячейки во всех ноутбуках |

**Benchmark composition:**

| Источник | Количество | Домены |
|----------|-----------|--------|
| Custom LLM-generated | 218 | Все 5 |
| MGSM Russian | 250 | Математика |
| ruMMLU STEM (20 предметов) | 3,210 | Физика, химия, биология, CS |
| **Итого** | **3,678** | **5 доменов** |

**Baseline результаты (Qwen3-4B-Instruct, без дообучения, 218 задач):**

| Домен | Accuracy |
|-------|----------|
| Математика | 79.1% |
| Физика | 74.4% |
| Информатика | 46.5% |
| Химия | 46.7% |
| Биология | 28.6% |
| **Overall** | **55.1%** |

---

## Следующие шаги

1. **Завершить GSPO тренировку** на Colab A100 (Stage 1: 200 steps + Stage 2: 400 steps)
2. **RAFT++** с GVM-динамическим аллоцированием
3. **AdaSTaR** итеративная генерация rationales
4. **DPO** полировка формата
5. **Полная оценка** на 3678-benchmark после каждой стадии
6. **Экспорт в GGUF** (Q4_K_M + Q8_0) для inference через Ollama на CPU (16GB RAM)

---

## Ссылки

- [Qwen3-4B-Instruct](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
- [Ollama](https://ollama.ai/)
- [Unsloth](https://github.com/unslothai/unsloth)
- [TRL](https://github.com/huggingface/trl)
- [GSPO paper](https://arxiv.org/abs/2507.18071)
- [Cerebras API](https://inference-docs.cerebras.ai/)
