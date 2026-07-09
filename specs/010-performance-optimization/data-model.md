# Data Model: Performance Optimization

**Feature**: 010-performance-optimization
**Date**: 2026-02-03

## Entity Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   CacheEntry    │     │  SessionMetrics  │     │  ABExperiment   │
│   (Extended)    │     │    (Extended)    │     │     (New)       │
└────────┬────────┘     └────────┬─────────┘     └────────┬────────┘
         │                       │                        │
         │                       │                        │
         ▼                       ▼                        ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  ResponseCache  │     │  MetricsReport   │     │   ABVariant     │
│   (Extended)    │     │     (New)        │     │     (New)       │
└─────────────────┘     └──────────────────┘     └─────────────────┘

┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│CompressedContext│     │   FewShotExample │     │ ResourceSample  │
│     (New)       │     │      (New)       │     │     (New)       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Entities

### 1. CacheEntry (Extended)

**Purpose**: Кэшированный ответ с контекстно-зависимым ключом

**Existing Fields** (src/inference/cache.py):
- `query: str` - Исходный запрос
- `response: str` - Кэшированный ответ
- `embedding: List[float]` - Вектор для semantic search
- `created_at: datetime` - Время создания
- `access_count: int` - Счётчик использования
- `topic: Optional[str]` - Тема задачи

**New Fields**:
- `context_hash: str` - Hash(topic + difficulty + student_level) для контекстного matching
- `teaching_strategy: str` - Использованная стратегия (для A/B анализа)
- `response_time_ms: int` - Время генерации оригинального ответа
- `variant_id: Optional[str]` - ID A/B варианта если применимо

**Validation Rules**:
- context_hash: 32-char MD5 hash
- response_time_ms: > 0
- embedding: 384 dimensions (MiniLM output)

---

### 2. SessionMetrics (Extended)

**Purpose**: Метрики отдельной сессии для анализа

**Existing Fields** (src/logging/session_logger.py):
- `session_id: str`
- `student_id: str`
- `task_id: str`
- `topic: str`
- `difficulty: str`
- `outcome: str` (solved/told_answer/abandoned)
- `hints_used: int`
- `attempts: int`
- `duration_seconds: int`

**New Fields**:
- `avg_response_time_ms: float` - Среднее время ответа в сессии
- `cache_hit_count: int` - Количество cache hits
- `cache_miss_count: int` - Количество cache misses
- `total_tokens_in: int` - Входные токены за сессию
- `total_tokens_out: int` - Выходные токены за сессию
- `peak_vram_mb: int` - Пиковое использование VRAM
- `context_compressions: int` - Количество сжатий контекста
- `ab_variant: Optional[str]` - Присвоенный A/B вариант
- `few_shot_used: bool` - Использовались ли few-shot примеры
- `cot_used: bool` - Использовался ли Chain-of-Thought

**Validation Rules**:
- avg_response_time_ms: >= 0
- cache_hit_count + cache_miss_count > 0 (хотя бы один запрос)
- peak_vram_mb: 0-16000 (reasonable GPU range)

---

### 3. ABExperiment (New)

**Purpose**: Конфигурация A/B эксперимента

**Fields**:
- `experiment_id: str` - Уникальный идентификатор (e.g., "cot_vs_standard_2026_02")
- `name: str` - Человекочитаемое название
- `description: str` - Описание гипотезы
- `variants: List[ABVariant]` - Варианты эксперимента
- `allocation_weights: List[float]` - Веса распределения (сумма = 1.0)
- `target_metric: str` - Основная метрика (e.g., "success_rate", "response_time")
- `status: str` - draft/active/paused/completed
- `created_at: datetime`
- `started_at: Optional[datetime]`
- `ended_at: Optional[datetime]`
- `min_sessions: int` - Минимум сессий для статистической значимости

**Validation Rules**:
- len(variants) >= 2
- sum(allocation_weights) == 1.0
- status in ["draft", "active", "paused", "completed"]
- min_sessions > 0

---

### 4. ABVariant (New)

**Purpose**: Отдельный вариант в A/B эксперименте

**Fields**:
- `variant_id: str` - Уникальный ID (e.g., "control", "treatment_cot")
- `name: str` - Название варианта
- `config: Dict[str, Any]` - Конфигурация варианта
  - `use_cot: bool`
  - `use_few_shot: bool`
  - `few_shot_count: int`
  - `temperature: float`
  - `system_prompt_variant: str`
- `sessions_count: int` - Количество сессий с этим вариантом
- `metrics_summary: Dict[str, float]` - Агрегированные метрики

**Validation Rules**:
- config keys match expected experiment type
- sessions_count >= 0
- metrics_summary values are numeric

---

### 5. CompressedContext (New)

**Purpose**: Сжатая история диалога

**Fields**:
- `session_id: str` - Связь с сессией
- `original_turns: int` - Исходное количество turns
- `compressed_turns: int` - Количество после сжатия
- `original_tokens: int` - Исходное количество токенов
- `compressed_tokens: int` - Количество после сжатия
- `key_events: List[KeyEvent]` - Извлечённые ключевые события
- `recent_messages: List[ConversationTurn]` - Последние N сообщений (полные)
- `summary: Optional[str]` - LLM-generated summary если применялся
- `compression_method: str` - "sliding_window" | "llm_summary" | "hybrid"
- `created_at: datetime`

**KeyEvent Structure**:
- `turn_index: int`
- `event_type: str` - "error", "hint_given", "progress", "stuck_point"
- `content: str` - Краткое описание события
- `importance_score: float` - 0.0-1.0

**Validation Rules**:
- compressed_tokens < original_tokens
- compression_ratio = compressed_tokens / original_tokens < 0.8
- len(recent_messages) <= 10

---

### 6. FewShotExample (New)

**Purpose**: Пример для few-shot prompting

**Fields**:
- `example_id: str` - Уникальный ID
- `topic: str` - Математическая тема (derivatives, integrals, etc.)
- `subtopic: Optional[str]` - Подтема (chain_rule, integration_by_parts)
- `difficulty: str` - easy/medium/hard
- `problem: str` - Условие задачи
- `student_answer: str` - Ответ студента (правильный или с ошибкой)
- `student_error_type: Optional[str]` - Тип ошибки если есть
- `tutor_response: str` - Образцовый ответ тьютора (Socratic)
- `teaching_strategy: str` - HINT/ENCOURAGE/RECTIFY/etc.
- `embedding: List[float]` - Для semantic retrieval
- `usage_count: int` - Сколько раз использовался
- `effectiveness_score: Optional[float]` - Оценка эффективности (из A/B тестов)

**Validation Rules**:
- topic in valid_topics
- difficulty in ["easy", "medium", "hard"]
- teaching_strategy in valid_strategies
- tutor_response не содержит прямых ответов (Socratic check)

---

### 7. MetricsReport (New)

**Purpose**: Сгенерированный отчёт с метриками

**Fields**:
- `report_id: str` - Уникальный ID
- `report_type: str` - "daily", "weekly", "experiment", "custom"
- `period_start: datetime`
- `period_end: datetime`
- `generated_at: datetime`
- `metrics: Dict[str, Any]` - Агрегированные метрики
  - `total_sessions: int`
  - `avg_response_time_ms: float`
  - `cache_hit_rate: float`
  - `success_rate: float`
  - `telling_rate: float`
  - `avg_hints_per_session: float`
  - `peak_vram_mb: int`
  - `total_tokens: int`
- `charts: List[ChartData]` - Данные для графиков
- `export_paths: Dict[str, str]` - Пути к экспортированным файлам
  - `json: str`
  - `csv: str`
  - `png_charts: List[str]`

**ChartData Structure**:
- `chart_type: str` - "line", "bar", "histogram", "pie"
- `title: str`
- `x_label: str`
- `y_label: str`
- `data: List[Dict]` - Данные для графика

---

### 8. ResourceSample (New)

**Purpose**: Замер использования ресурсов

**Fields**:
- `sample_id: str`
- `timestamp: datetime`
- `ram_used_mb: int`
- `ram_available_mb: int`
- `vram_used_mb: int`
- `vram_total_mb: int`
- `gpu_utilization_percent: float`
- `cpu_percent: float`
- `active_sessions: int`
- `alert_triggered: bool` - Превышен ли порог
- `alert_type: Optional[str]` - "vram_high", "ram_high", "gpu_overload"

**Validation Rules**:
- All memory values >= 0
- gpu_utilization_percent: 0-100
- cpu_percent: 0-100

---

## Database Schema Updates

### SQLite Tables (metrics.db)

```sql
-- Extended sessions table
ALTER TABLE sessions ADD COLUMN avg_response_time_ms REAL;
ALTER TABLE sessions ADD COLUMN cache_hit_count INTEGER DEFAULT 0;
ALTER TABLE sessions ADD COLUMN cache_miss_count INTEGER DEFAULT 0;
ALTER TABLE sessions ADD COLUMN total_tokens_in INTEGER DEFAULT 0;
ALTER TABLE sessions ADD COLUMN total_tokens_out INTEGER DEFAULT 0;
ALTER TABLE sessions ADD COLUMN peak_vram_mb INTEGER;
ALTER TABLE sessions ADD COLUMN context_compressions INTEGER DEFAULT 0;
ALTER TABLE sessions ADD COLUMN ab_variant TEXT;
ALTER TABLE sessions ADD COLUMN few_shot_used INTEGER DEFAULT 0;
ALTER TABLE sessions ADD COLUMN cot_used INTEGER DEFAULT 0;

-- New table: ab_experiments
CREATE TABLE ab_experiments (
    experiment_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    variants_json TEXT NOT NULL,
    allocation_weights_json TEXT NOT NULL,
    target_metric TEXT NOT NULL,
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    min_sessions INTEGER DEFAULT 100
);

-- New table: ab_assignments
CREATE TABLE ab_assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES ab_experiments(experiment_id)
);

-- New table: resource_samples
CREATE TABLE resource_samples (
    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ram_used_mb INTEGER,
    ram_available_mb INTEGER,
    vram_used_mb INTEGER,
    vram_total_mb INTEGER,
    gpu_utilization_percent REAL,
    cpu_percent REAL,
    active_sessions INTEGER DEFAULT 0,
    alert_triggered INTEGER DEFAULT 0,
    alert_type TEXT
);

-- New table: metrics_reports
CREATE TABLE metrics_reports (
    report_id TEXT PRIMARY KEY,
    report_type TEXT NOT NULL,
    period_start TIMESTAMP,
    period_end TIMESTAMP,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metrics_json TEXT NOT NULL,
    charts_json TEXT,
    export_paths_json TEXT
);

-- Indexes for performance
CREATE INDEX idx_ab_assignments_experiment ON ab_assignments(experiment_id);
CREATE INDEX idx_ab_assignments_session ON ab_assignments(session_id);
CREATE INDEX idx_resource_samples_timestamp ON resource_samples(timestamp);
CREATE INDEX idx_metrics_reports_type_period ON metrics_reports(report_type, period_start);
```

### JSON Files

**data/few_shot/derivatives.json**:
```json
{
  "topic": "derivatives",
  "examples": [
    {
      "example_id": "deriv_001",
      "subtopic": "product_rule",
      "difficulty": "medium",
      "problem": "Найди производную f(x) = x² · sin(x)",
      "student_answer": "2x · cos(x)",
      "student_error_type": "missing_product_rule",
      "tutor_response": "Смотри, здесь у нас произведение двух функций. Какое правило нужно применить для производной произведения?",
      "teaching_strategy": "HINT"
    }
  ]
}
```

---

## State Transitions

### ABExperiment Status

```
draft → active → paused → active → completed
                    ↓
                completed (early stop)
```

- `draft`: Эксперимент создан, не запущен
- `active`: Собираются данные
- `paused`: Временно остановлен
- `completed`: Достигнут min_sessions или ручное завершение

### Compression Trigger

```
Normal → Check tokens → Compress if > 4000 → Return to Normal
           ↓
    No compression needed
```
