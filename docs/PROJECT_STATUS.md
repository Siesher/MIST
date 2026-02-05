# MITS - Статус проекта

> Последнее обновление: Январь 2026

## О проекте

**MITS** (Math Intelligent Tutoring System) — интеллектуальная система обучения с использованием сократического метода. Репетитор направляет ученика через вопросы, не давая прямых ответов.

### Целевые дисциплины
- Математика (алгебра, анализ, геометрия, статистика)
- Программирование (Python, алгоритмы, структуры данных)
- Физика
- Химия
- Биология

### Целевое оборудование
- GPU: NVIDIA RTX 2080 (8GB VRAM)
- RAM: 32GB
- OS: Windows

---

## Архитектура системы

```
┌─────────────────────────────────────────────────────────────────┐
│                         GRADIO UI                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    АГЕНТ-ОРКЕСТРАТОР                            │
│  Координирует работу всех агентов (паттерн GenMentor)           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Profiler │→│ Planner  │→│  Tutor   │→│ Verifier │        │
│  │          │  │          │  │          │  │          │        │
│  │Диагностика│  │Стратегия │  │Генерация│  │Проверка │        │
│  │ошибок    │  │обучения  │  │ответа   │  │качества │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │   RAG    │   │  Cache   │   │   LLM    │
        │ Retriever│   │ Manager  │   │  Client  │
        └──────────┘   └──────────┘   └──────────┘
              │               │               │
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │Knowledge │   │Semantic  │   │ Ollama/  │
        │Base      │   │Cache     │   │ Cerebras │
        └──────────┘   └──────────┘   └──────────┘
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

### Фаза 3: Оценка и интеграция ✅ ЗАВЕРШЕНА

| Компонент | Статус | Файл |
|-----------|--------|------|
| Метрики качества | ✅ | `evaluation/metrics.py` |
| CLI оценки | ✅ | `evaluation/evaluate_model.py` |
| RAG в оркестраторе | ✅ | `src/agents/orchestrator.py` |
| Документация моделей | ✅ | `docs/MODEL_SELECTION.md` |

### Фаза 4: Генерация данных ✅ ГОТОВО К ЗАПУСКУ

| Задача | Статус | Описание |
|--------|--------|----------|
| Генератор STEM диалогов | ✅ | Поддержка всех 5 дисциплин |
| Темы математики | ✅ | 10 тем (линейные уравнения, производные, интегралы...) |
| Темы программирования | ✅ | 13 тем (Python: циклы, функции, ООП, алгоритмы...) |
| Темы физики | ✅ | 10 тем (кинематика, динамика, электричество...) |
| Темы химии | ✅ | 10 тем (строение атома, реакции, органика...) |
| Темы биологии | ✅ | 10 тем (клетка, генетика, экология...) |
| Настройка Cerebras API | ⏳ | Получить API ключи (.env) |
| Запуск генерации | ⏳ | ~10000+ диалогов |

**Использование генератора:**
```bash
# Все дисциплины (по 5 тем на каждую)
python training/scripts/cerebras_dialog_generator.py \
    --discipline all \
    --topics-per-discipline 5 \
    --dialogs-per-combo 2

# Конкретная дисциплина
python training/scripts/cerebras_dialog_generator.py \
    --discipline coding \
    --topics "циклы,функции,списки" \
    --dialogs-per-combo 5

# Показать доступные темы
python training/scripts/cerebras_dialog_generator.py --list-topics
```

### Фаза 5: Дообучение модели ✅ ГОТОВО К ЗАПУСКУ

| Задача | Статус | Описание |
|--------|--------|----------|
| Скрипт фильтрации диалогов | ✅ | `training/scripts/filter_dataset.py` |
| Конфигурация QLoRA | ✅ | `training/configs/qlora_rtx2080.yaml` |
| Скрипт дообучения | ✅ | `training/scripts/train_qlora.py` |
| Скачать Qwen3-8B | ⏳ | HuggingFace (автоматически при запуске) |
| Запустить тренировку | ⏳ | После генерации ~10K диалогов |

**Использование:**
```bash
# Фильтрация сгенерированных диалогов
python training/scripts/filter_dataset.py \
    --input data/training/cerebras_dialogs.jsonl \
    --output data/training/filtered_dialogs.jsonl \
    --min-quality 0.7

# Запуск дообучения
python training/scripts/train_qlora.py \
    --config training/configs/qlora_rtx2080.yaml

# Тестовый запуск (100 шагов)
python training/scripts/train_qlora.py \
    --config training/configs/qlora_rtx2080.yaml \
    --max-steps 100 \
    --output outputs/test-run
```

### Фаза 6: Оптимизация 📋 ЗАПЛАНИРОВАНО

| Задача | Статус | Описание |
|--------|--------|----------|
| Speculative decoding | 📋 | Qwen-0.5B draft |
| Semantic caching | 📋 | sentence-transformers |
| Обновление UI | 📋 | Gradio app |

---

## Структура проекта

```
MITS/
├── docs/                          # Документация
│   ├── MODEL_SELECTION.md         # Выбор модели
│   └── PROJECT_STATUS.md          # Этот файл
│
├── src/
│   ├── agents/                    # Агенты системы
│   │   ├── orchestrator.py        # Главный координатор
│   │   ├── profiler.py            # Диагностика ошибок
│   │   ├── planner.py             # Выбор стратегии
│   │   ├── verifier.py            # Проверка качества
│   │   └── tutor_agent.py         # Основной репетитор
│   │
│   ├── inference/                 # Инференс и оптимизация
│   │   ├── model_manager.py       # Управление моделями
│   │   └── cache.py               # Кэширование ответов
│   │
│   ├── knowledge/                 # База знаний
│   │   └── rag_retriever.py       # RAG система
│   │
│   └── models/                    # LLM клиенты
│       └── llm_client.py          # Ollama клиент
│
├── data/
│   └── knowledge/                 # База знаний RAG
│       ├── hints/                 # Подсказки по темам
│       │   ├── algebra.jsonl
│       │   ├── calculus.jsonl
│       │   └── geometry.jsonl
│       ├── misconceptions/        # Типичные ошибки
│       │   └── common_errors.jsonl
│       └── skill_graph.json       # Граф навыков
│
├── training/
│   ├── configs/
│   │   └── qlora_rtx2080.yaml            # QLoRA конфигурация
│   └── scripts/
│       ├── cerebras_dialog_generator.py  # STEM генератор диалогов
│       ├── filter_dataset.py             # Фильтрация качества
│       └── train_qlora.py                # Скрипт дообучения
│
├── evaluation/                    # Оценка качества
│   ├── __init__.py
│   ├── metrics.py                 # Метрики
│   └── evaluate_model.py          # CLI
│
└── interface/
    └── gradio_app.py              # Web UI
```

---

## Выбранные модели

### Для inference (основная работа)
**Qwen3-8B-Instruct** + QLoRA fine-tuning

- MMLU: 76.89
- GPQA: 63.3 (с RL)
- GSM8K: 89.84
- Coding: 67.65
- VRAM: ~5GB (4-bit)

### Для генерации данных
**Вариант A:** Cerebras API (Qwen-3-235B) — бесплатно, ~1000 tok/sec
**Вариант B:** Nemotron-Cascade-8B-Thinking — локально, 90.5% AIME

### Для RAG эмбеддингов
**MiniLM-L12** (paraphrase-multilingual) — 0.1GB VRAM

---

## Следующие шаги

1. **Сейчас:** Получить API ключ Cerebras (https://cloud.cerebras.ai/) и добавить в `.env`
2. **Затем:** Запустить генерацию диалогов для всех STEM дисциплин
3. **Далее:** Отфильтровать диалоги и запустить QLoRA дообучение
4. **Потом:** Оценить качество дообученной модели
5. **Финал:** Оптимизировать inference и обновить UI

---

## Команды для работы

```bash
# === ГЕНЕРАЦИЯ ДАННЫХ ===
# Все STEM дисциплины (5 тем на дисциплину)
python training/scripts/cerebras_dialog_generator.py \
    --discipline all \
    --topics-per-discipline 5 \
    --dialogs-per-combo 2

# Только математика
python training/scripts/cerebras_dialog_generator.py \
    --discipline math \
    --topics "линейные_уравнения,квадратные_уравнения"

# Показать доступные темы
python training/scripts/cerebras_dialog_generator.py --list-topics

# === ФИЛЬТРАЦИЯ ===
python training/scripts/filter_dataset.py \
    --input data/training/cerebras_dialogs.jsonl \
    --output data/training/filtered_dialogs.jsonl \
    --min-quality 0.7

# === ДООБУЧЕНИЕ ===
python training/scripts/train_qlora.py \
    --config training/configs/qlora_rtx2080.yaml

# === ОЦЕНКА ===
python evaluation/evaluate_model.py \
    --test-set data/test_dialogs.jsonl \
    --model qwen3:8b

# === ЗАПУСК ===
python interface/gradio_app.py
ollama run qwen3:8b
```

---

## Полезные ссылки

- [Qwen3 на HuggingFace](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)
- [Nemotron-Cascade](https://huggingface.co/nvidia/Nemotron-Cascade-8B-Thinking)
- [Cerebras API Docs](https://inference-docs.cerebras.ai/)
- [Ollama](https://ollama.ai/)
- [Unsloth (QLoRA)](https://github.com/unslothai/unsloth)
