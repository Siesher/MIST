# Implementation Plan: Performance Optimization

**Branch**: `010-performance-optimization` | **Date**: 2026-02-03 | **Spec**: [spec.md](./spec.md)
**Input**: Комплексная оптимизация MITS для максимальной эффективности

## Summary

Комплексная оптимизация системы MITS для достижения времени ответа <2 секунд, снижения использования VRAM до <7GB, и сбора метрик для дипломной защиты. Включает семантическое кэширование ответов, prefetch подсказок, few-shot prompting, Chain-of-Thought для математики, A/B тестирование, сжатие контекста и batch processing embeddings.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Ollama, Gradio 4.x, ChromaDB, sentence-transformers, pydantic, structlog, SQLite
**Storage**: SQLite (metrics, sessions), ChromaDB (vectors), JSON (configs, knowledge base)
**Testing**: pytest
**Target Platform**: Windows/Linux с GPU (RTX 2080 8GB VRAM минимум)
**Project Type**: Single project (src/ + interface/ + tests/)
**Performance Goals**: Время ответа <2 сек (новые), <0.5 сек (кэш), cache hit rate >20%
**Constraints**: VRAM <7GB, RAM <16GB, полностью офлайн
**Scale/Scope**: Одиночный пользователь, сессии до 2+ часов, сбор данных для диплома

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Socratic Pedagogy | PASS | Оптимизации не влияют на педагогический подход, кэширование сохраняет Socratic responses |
| II. Multi-Agent Architecture | PASS | Оптимизации интегрируются через существующий Orchestrator, не обходят агентов |
| III. Knowledge-Grounded Responses | PASS | RAG расширяется, не заменяется; few-shot примеры добавляются в knowledge base |
| IV. Hardware Constraint Compliance | PASS | Цель: VRAM <7GB (соответствует требованию <6GB + overhead) |
| V. Metrics-Driven Quality | PASS | A/B тестирование и метрики напрямую поддерживают этот принцип |
| VI. STEM Domain Coverage | PASS | Оптимизации применяются ко всем дисциплинам равномерно |

**Gate Status**: PASSED - все принципы соблюдены

## Project Structure

### Documentation (this feature)

```text
specs/010-performance-optimization/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/
├── agents/
│   └── tutor_agent.py       # Интеграция CoT, few-shot
├── inference/
│   ├── cache.py             # СУЩЕСТВУЕТ: семантический кэш (расширить)
│   ├── metrics.py           # СУЩЕСТВУЕТ: inference метрики (расширить)
│   ├── hint_prefetcher.py   # СУЩЕСТВУЕТ: prefetch (оптимизировать)
│   ├── batch_processor.py   # СУЩЕСТВУЕТ: batch embeddings (оптимизировать)
│   ├── context_compressor.py # НОВЫЙ: сжатие контекста диалога
│   └── ab_testing.py        # НОВЫЙ: A/B тестирование
├── logging/
│   ├── session_logger.py    # СУЩЕСТВУЕТ: логирование (расширить)
│   └── report_generator.py  # НОВЫЙ: автоматические отчёты
├── knowledge/
│   ├── rag_retriever.py     # СУЩЕСТВУЕТ: RAG (расширить few-shot)
│   └── few_shot_bank.py     # НОВЫЙ: банк few-shot примеров
├── models/
│   └── llm_client.py        # СУЩЕСТВУЕТ: добавить prompt caching
└── data/
    └── schemas.py           # Расширить схемы для метрик

interface/
└── unified_app.py           # Добавить dashboard метрик

tests/
├── unit/
│   ├── test_cache.py
│   ├── test_context_compressor.py
│   └── test_ab_testing.py
└── integration/
    └── test_performance.py

data/
├── metrics.db               # СУЩЕСТВУЕТ: SQLite метрики
├── few_shot/                # НОВЫЙ: few-shot примеры по темам
│   ├── derivatives.json
│   ├── integrals.json
│   └── limits.json
└── reports/                 # НОВЫЙ: сгенерированные отчёты
```

**Structure Decision**: Используется существующая структура single project. Новые модули добавляются в соответствующие директории (inference/, logging/, knowledge/). Тесты следуют существующей структуре tests/.

## Complexity Tracking

> No violations identified - all changes align with constitution principles.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |

---

## Phase Completion Status

### Phase 0: Research - COMPLETE

**Output**: [research.md](./research.md)

Researched and documented decisions for:
- Semantic caching strategy (extend existing ResponseCache)
- Hint prefetch strategy (rule-based on skill graph)
- Few-shot prompting (topic-specific JSON bank)
- Chain-of-Thought for math (structured reasoning templates)
- A/B testing framework (session-level SQLite)
- Context compression (sliding window + key events)
- Batch embedding processing (time-windowed queue)
- Metrics collection (automated report generation)
- Ollama optimization settings
- Resource monitoring (psutil + pynvml)

### Phase 1: Design & Contracts - COMPLETE

**Outputs**:
- [data-model.md](./data-model.md) - 8 entities defined with SQLite schema
- [contracts/cache_api.py](./contracts/cache_api.py) - Caching API contract
- [contracts/metrics_api.py](./contracts/metrics_api.py) - Metrics & A/B testing API contract
- [contracts/optimization_api.py](./contracts/optimization_api.py) - Compression, few-shot, prefetch API contract
- [quickstart.md](./quickstart.md) - Developer quickstart guide
- CLAUDE.md updated with feature technologies

### Constitution Re-Check (Post Phase 1)

| Principle | Status | Design Impact |
|-----------|--------|---------------|
| I. Socratic Pedagogy | PASS | Few-shot examples validated for Socratic content; CoT templates guide questions not answers |
| II. Multi-Agent Architecture | PASS | All optimizations work through existing agents; no bypass paths |
| III. Knowledge-Grounded Responses | PASS | Few-shot bank extends knowledge base; RAG integration preserved |
| IV. Hardware Constraint Compliance | PASS | ResourceMonitor enforces VRAM <7GB with alerts |
| V. Metrics-Driven Quality | PASS | A/B testing + report generator directly implement this principle |
| VI. STEM Domain Coverage | PASS | Few-shot examples cover all math topics equally |

**Post-Design Gate Status**: PASSED

---

## Next Step

Run `/speckit.tasks` to generate implementation tasks from this plan.
