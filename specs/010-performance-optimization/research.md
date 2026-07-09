# Research: Performance Optimization

**Feature**: 010-performance-optimization
**Date**: 2026-02-03
**Status**: Complete

## 1. Semantic Caching Strategy

### Decision: Extend existing ResponseCache with context-aware keys

### Rationale:
- Существующий `src/inference/cache.py` уже реализует LRU + semantic similarity (cosine, threshold 0.85)
- Используется sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2) - оптимален для русского языка
- Нужно добавить: учёт контекста сессии (topic, student proficiency level) в ключ кэша

### Alternatives Considered:
1. **Redis с vector similarity** - отклонено: добавляет внешнюю зависимость, усложняет офлайн работу
2. **Полное переписывание кэша** - отклонено: существующая реализация качественная, нужны минимальные расширения
3. **Prompt caching на уровне Ollama** - частично принято: Ollama не поддерживает нативный prompt caching, но можно кэшировать system prompts отдельно

### Implementation Notes:
- Добавить `context_hash` в CacheEntry (hash от topic + difficulty + student_level)
- Увеличить порог схожести до 0.90 для более точного matching
- Добавить метрику cache_hit_rate в InferenceMetrics

---

## 2. Hint Prefetch Strategy

### Decision: Predictive prefetch based on current task and common error patterns

### Rationale:
- Существующий `src/inference/hint_prefetcher.py` уже реализует базовый prefetch
- Можно предсказать вероятные следующие hints по skill graph dependencies
- Prefetch во время ожидания ввода пользователя (idle time utilization)

### Alternatives Considered:
1. **Prefetch всех hints темы** - отклонено: слишком много данных, засоряет кэш
2. **ML-based prediction** - отклонено: overcomplicated, недостаточно данных для обучения
3. **Rule-based на основе skill_graph.json** - принято: простое и эффективное решение

### Implementation Notes:
- При загрузке задачи prefetch hints для текущего skill + immediate prerequisites
- При ошибке prefetch hints для common misconceptions этого типа
- Async prefetch чтобы не блокировать основной поток

---

## 3. Few-Shot Prompting for Math

### Decision: Topic-specific few-shot examples stored in JSON bank

### Rationale:
- Few-shot значительно улучшает качество математических рассуждений (исследования показывают +15-30% accuracy)
- Примеры должны демонстрировать Socratic стиль (вопросы, не ответы)
- Динамический выбор примеров по similarity к текущей задаче

### Alternatives Considered:
1. **Hardcoded примеры в prompts** - отклонено: негибко, сложно поддерживать
2. **RAG для примеров** - частично принято: используем ChromaDB для semantic retrieval примеров
3. **Fine-tuning модели** - отклонено: требует значительных ресурсов, не соответствует hardware constraints

### Implementation Notes:
- Создать `data/few_shot/` с JSON файлами по темам
- Формат: `{problem, student_answer, tutor_response, teaching_strategy}`
- 3-5 примеров на тему, выбирать 2 наиболее релевантных
- Интегрировать в TutoringRAG.retrieve_context()

---

## 4. Chain-of-Thought для математики

### Decision: Structured CoT prompts с explicit reasoning steps

### Rationale:
- CoT критичен для математических задач (исследования показывают +20-40% на reasoning tasks)
- GLM-4 хорошо поддерживает structured reasoning
- Нужен русскоязычный CoT template

### Alternatives Considered:
1. **Zero-shot CoT ("Давай подумаем шаг за шагом")** - частично принято: как fallback
2. **Self-consistency (multiple paths)** - отклонено: увеличивает latency в 3-5x
3. **Program-of-Thought (code generation)** - отклонено: не соответствует Socratic pedagogy

### Implementation Notes:
- CoT template: "Проанализируй задачу → Определи тип → Вспомни метод → Задай наводящий вопрос"
- Добавить в system prompt секцию reasoning structure
- Использовать для сложных задач (difficulty >= medium)

---

## 5. A/B Testing Framework

### Decision: Session-level randomization with SQLite tracking

### Rationale:
- Нужно сравнивать разные стратегии промптинга
- Session-level (не request-level) для consistency
- SQLite уже используется для метрик

### Alternatives Considered:
1. **Feature flags service** - отклонено: внешняя зависимость
2. **User-level assignment** - отклонено: мало пользователей для статистической значимости
3. **Manual A/B switching** - отклонено: bias, не автоматизировано

### Implementation Notes:
- Новая таблица `ab_experiments` в metrics.db
- Поля: experiment_id, variant, session_id, metrics_json, created_at
- Хелпер для assignment: `get_variant(experiment_id, session_id)`
- Визуализация результатов в dashboard

---

## 6. Context Compression

### Decision: Extractive summarization with key points preservation

### Rationale:
- Длинные диалоги (>20 turns) замедляют inference
- Нужно сохранить: текущую задачу, ошибки студента, использованные hints
- GLM-4 context window 128K, но >8K tokens замедляет

### Alternatives Considered:
1. **Truncation (отбросить старые сообщения)** - отклонено: теряется важный контекст
2. **Summarization через LLM** - частично принято: для очень длинных диалогов
3. **Sliding window + key events** - принято: баланс скорости и качества

### Implementation Notes:
- Sliding window: последние 10 сообщений полностью
- Для старых: извлечь key events (errors, hints, progress markers)
- Threshold: compress когда context > 4000 tokens
- Сохранять compression ratio в метриках

---

## 7. Batch Embedding Processing

### Decision: Queue-based batching with configurable batch size

### Rationale:
- Существующий `src/inference/batch_processor.py` нуждается в оптимизации
- sentence-transformers эффективнее с батчами (GPU utilization)
- RAG queries часто приходят группами

### Alternatives Considered:
1. **Eager embedding (при загрузке)** - отклонено: высокий initial latency
2. **Lazy single-item** - текущее состояние, неэффективно
3. **Time-windowed batching** - принято: собирать запросы за 50ms окно

### Implementation Notes:
- Batch size: 8-16 items (оптимум для MiniLM на GPU)
- Timeout window: 50ms
- Async queue с consumer thread
- Fallback на single-item при таймауте

---

## 8. Metrics Collection for Diploma

### Decision: Comprehensive logging with automated report generation

### Rationale:
- Нужны данные для графиков и таблиц в дипломе
- Существующий SessionLogger хороший, но нужны агрегации
- Формат: JSON для analysis + PNG графики

### Alternatives Considered:
1. **Manual export** - отклонено: трудоёмко, error-prone
2. **Real-time dashboard only** - отклонено: нужны exportable артефакты
3. **Jupyter notebooks** - частично принято: для глубокого анализа

### Implementation Notes:
- Метрики: response_time_ms, cache_hit, tokens_in/out, VRAM_mb, strategy_used
- Агрегации: daily, weekly, per-topic, per-difficulty
- Report generator: matplotlib/seaborn графики
- Export formats: JSON, CSV, PNG

---

## 9. Ollama Optimization Settings

### Decision: Optimized inference parameters for GLM-4.7-Flash

### Rationale:
- GLM-4.7-Flash (23B MoE, 3B active) оптимизирован для speed
- Текущие настройки в config.py уже хорошие
- Можно добавить: num_ctx tuning, num_batch optimization

### Alternatives Considered:
1. **Speculative decoding** - отклонено: требует draft model, усложняет setup
2. **Model quantization (Q4)** - уже используется через GGUF
3. **Flash Attention** - принято: Ollama автоматически использует если доступен

### Implementation Notes:
- Проверить `OLLAMA_FLASH_ATTENTION=1` в environment
- num_ctx: 4096 (достаточно для большинства диалогов)
- num_batch: 512 (баланс latency/throughput)
- Мониторить VRAM через nvidia-smi

---

## 10. RAM/VRAM Monitoring

### Decision: Periodic sampling with alerts

### Rationale:
- Нужно доказать stability в дипломе (2+ часа без утечек)
- Детектировать проблемы до OOM
- Данные для таблицы "Использование ресурсов"

### Alternatives Considered:
1. **External monitoring (Prometheus)** - отклонено: overcomplicated
2. **Manual checks** - отклонено: не systematic
3. **psutil + pynvml** - принято: lightweight, no dependencies

### Implementation Notes:
- Sampling interval: 30 seconds
- Metrics: RAM_used, RAM_available, VRAM_used, VRAM_total, GPU_utilization
- Alert threshold: VRAM > 7GB, RAM > 14GB
- Store in metrics.db для trending

---

## Summary of Decisions

| Area | Decision | Key Benefit |
|------|----------|-------------|
| Caching | Extend ResponseCache with context keys | <0.5s cached responses |
| Prefetch | Rule-based on skill graph | Reduced perceived latency |
| Few-shot | JSON bank + semantic retrieval | +15-30% response quality |
| CoT | Structured reasoning template | Better math explanations |
| A/B Testing | Session-level SQLite tracking | Data-driven optimization |
| Compression | Sliding window + key events | Stable performance on long sessions |
| Batch Embeddings | Time-windowed queue | 30%+ embedding speedup |
| Metrics | Automated report generator | Ready diploma artifacts |
| Ollama | Optimized num_ctx/num_batch | Consistent <2s responses |
| Monitoring | psutil + pynvml sampling | Proven stability |
