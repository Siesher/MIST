# MITS — Статус проекта

> Обновлено: 2026-06-10

## О проекте

**MITS** (Math Intelligent Tutoring System) — интеллектуальная система обучения STEM-дисциплинам с использованием сократического метода. Репетитор направляет ученика через вопросы, не давая прямых ответов.

### Целевые дисциплины
- Математика (алгебра, анализ, геометрия, статистика)
- Физика (кинематика, динамика, электричество, оптика)
- Химия (строение атома, реакции, органика, растворы)
- Биология (клетка, генетика, экология, эволюция)
- Информатика (Python, алгоритмы, структуры данных)

### Оборудование
- **Inference:** CPU (Ryzen 5 9500f), 16GB RAM, Windows — llama-swap + GGUF Q4_K_M (:8090)
- **Training:** RTX PRO 6000 Blackwell 96GB (bf16, без QLoRA)

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
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ Profiler │→│ Planner  │→│  Tutor   │→│ Verifier │         │
│  │Диагностика│ │Стратегия │ │Генерация │ │Проверка  │         │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │   RAG    │  │Knowledge │  │ Emotion  │  │   OCR    │         │
│  │ChromaDB  │  │ Tracing  │  │ Detector │  │Qwen3.5   │         │
│  │          │  │ BKT+DKT  │  │ rules*   │  │ vision   │         │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘         │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│   llama-swap + Qwen3.5-9B (fine-tuned, GGUF Q4_K_M, :8090)      │
│   OpenAICompatLLMClient — streaming token-by-token               │
└─────────────────────────────────────────────────────────────────┘
* Emotion: rule-based детектор по умолчанию; fine-tuned RuBERT (macro-F1 0.97) доступен через AFFECT_DETECTOR_TYPE=ml
```

---

## Прогресс реализации

### Фаза 1–6: Инфраструктура + Агенты + UI ✅ ЗАВЕРШЕНА

| Компонент | Статус |
|-----------|--------|
| Многоагентная система (Profiler, Planner, Tutor, Verifier) | ✅ |
| RAG + ChromaDB (hints + misconceptions) | ✅ |
| Knowledge Tracing (BKT + DKT на ASSISTments) | ✅ |
| Эмоциональный детектор (rule-based, default; RuBERT macro-F1 0.97, opt-in) | ✅ |
| OCR рукописных решений (Qwen3.5 native vision via llama-swap model "mits-vision") | ✅ |
| FastAPI backend (REST + WebSocket + JWT) | ✅ |
| Next.js 14 frontend (shadcn/ui + Zustand) | ✅ |
| 3 режима чата (Chat, Guided Learning, Task Generator) | ✅ |
| Analytics dashboard + PDF экспорт | ✅ |
| Docker Compose deployment | ⚠️ экспериментально, не тестировалось |

---

### Фаза 7: Training Pipeline 🔄 В ПРОЦЕССЕ

**Модель:** Qwen3.5-9B-Instruct (выпуск: 2 марта 2026)
**Оборудование:** RTX PRO 6000 Blackwell 96GB, bf16, без QLoRA
**Ветка:** `019-ns-vstar-dpo`

#### 3-стадийный RL пайплайн

```
Qwen3.5-9B-Instruct → GSPO → KTO → DPO
(SFT убран: Instruct-модель уже имеет диалоговые способности)
```

| Стадия | Метод | Цель | Ноутбук | HF Repo | Статус |
|--------|-------|------|---------|---------|--------|
| 1. GSPO | Group Sequence Policy Optimization | STEM reasoning + формат + Сократ | `grpo_qwen3.5_9b.ipynb` | `Siesher/mits-qwen3-9b-gspo` | ✅ |
| 2. KTO | Kahneman-Tversky Optimization | Сократическое выравнивание | `kto_qwen3.5_9b.ipynb` | `Siesher/mits-qwen3-9b-kto` | ✅ |
| 3. DPO | Direct Preference Optimization | Финальная полировка | `dpo_polish_qwen3.5_9b.ipynb` | `Siesher/mits-qwen3-9b-final` | 📋 |

#### Ключевые техники GSPO (тройная награда)

| Техника | Статья | Вес / Эффект |
|---------|--------|-------------|
| GDPO correctness reward | arXiv 2601.05242 | 0.40 — SymPy/точность |
| GDPO format reward | arXiv 2601.05242 | 0.15 — `\boxed{}` + шаги |
| Socratic reward | MITS custom | 0.45 — no_leak + guide |
| Dr. GRPO length norm | arXiv 2503.20783 | Без length bias |
| Clip-Higher | arXiv 2504.05118 | ε=3e-4, ε_high=4e-4 |
| Zero-variance masking | arXiv 2505.22257 | Фильтрация пустых групп |

#### KTO (arXiv 2402.01306)

Kahneman-Tversky Optimization — выравнивание на непарных предпочтениях.
Обучается на `dialogs.jsonl` (3875 диалогов) + `preference_pairs.jsonl` (12597 пар).

---

### Фаза 8: Evaluation Infrastructure ✅ ЗАВЕРШЕНА

| Компонент | Статус | Описание |
|-----------|--------|----------|
| Benchmark (3678 задач) | ✅ | MGSM + ruMMLU + custom |
| `evaluate_stage.py` | ✅ | Per-stage eval через llama-server stack |
| Гибридная верификация | ✅ | SymPy → Cerebras LLM fallback |
| Combined judge | ✅ | Accuracy + Socratic за 1 Cerebras вызов |
| `--full-judge` режим | ✅ | Все ответы → Cerebras judge |
| `--eval-150` пресет | ✅ | 10 задач × 5 доменов × 3 сложности |
| `compare-live` | ✅ | Side-by-side сравнение 2 моделей |
| Checkpoint/resume | ✅ | `--resume` продолжает с места остановки |
| WandB интеграция | ✅ | `--wandb` логирует метрики |
| CSV summary | ✅ | `evaluation/summary.csv` для графиков |

#### Benchmark состав

| Источник | Количество | Домены |
|----------|-----------|--------|
| Custom LLM-generated | 218 | Все 5 |
| MGSM Russian | 250 | Математика |
| ruMMLU STEM (20 предметов) | 3,210 | Физика, химия, биология, CS |
| **Итого** | **3,678** | **5 доменов** |

#### Baseline результаты (Qwen3.5-9B-Instruct, без дообучения)

> Phase 0a честная оценка (n=209, llama-server stack, 2026-05-18). Подробнее: `docs/diploma/phase0a_results.md`.

| Стадия | Overall Accuracy |
|--------|-----------------|
| Base (Qwen3.5-9B-Instruct) | 69.4% |
| GSPO | 70.3% |
| KTO | 69.9% |

---

## Текущие модели (llama-swap, :8090)

| Модель | Формат | Описание | Стадия |
|--------|--------|----------|--------|
| `qwen3.5:9b` (base) | GGUF Q4_K_M | Базовая Qwen3.5-9B-Instruct | base |
| `mits-tutor-9b-think` | GGUF Q4_K_M | GSPO fine-tuned | gspo |
| `mits-vision` | GGUF Q4_K_M + mmproj | Qwen3.5 native vision для OCR | vision |

---

## Следующие шаги

1. **DPO полировка** — активная стадия (spec 019-ns-vstar-dpo), вход = KTO чекпоинт
2. **Финальная оценка** — сравнение всех 4 стадий (base 69.4% / gspo 70.3% / kto 69.9% / dpo TBD)
3. **Интеграция** финальной модели как GGUF Q4_K_M в llama-swap

---

## Структура проекта

```
frontend/          # Next.js 14 UI
backend/           # FastAPI backend
src/               # Core Python agents + models
training/
  scripts/         # ML pipeline (generate_*, filter_*, export_*, evaluate_stage.py, ...)
  data/            # Training data (~1.1GB JSONL)
  Modelfile*       # Ollama model configs
notebooks/         # Colab training notebooks (GSPO, KTO, DPO)
  archive/         # Legacy notebooks (GLM, Qwen3-4B, RAFT++)
evaluation/        # Evaluation framework + reports + benchmarks
  checkpoints/     # Per-problem evaluation checkpoints (JSONL)
  completions/     # Model completion logs
  reports/         # Aggregated evaluation reports (JSON)
data/              # Knowledge bases (RAG, skill graph, tasks)
docs/              # Documentation + research articles
research/          # Research findings (findings_*.md + knowledge.md)
scripts/           # Utility scripts (DB init, Ollama, PDF ingestion)
specs/             # Feature specifications (001–019)
figures/           # Training visualizations (PDF + PNG + TeX)
tests/             # Unit & integration tests
```
