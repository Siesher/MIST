# MITS Optimization Plan

План оптимизации системы для запуска на слабом железе без значительных потерь качества.

## Текущая конфигурация

- **Модель**: Nemotron-3-Nano-30B-A3B
- **Качество**: MATH 82.9%, AIME 89.1%
- **Требования**: ~18GB RAM/VRAM (Q4)

## Целевые конфигурации

| Уровень | GPU | RAM | Целевая скорость |
|---------|-----|-----|------------------|
| **High** | RTX 3090/4090 (24GB) | 32GB | 30+ tok/s |
| **Medium** | RTX 2080/3080 (8-10GB) | 32GB | 10-20 tok/s |
| **Low** | GTX 1660/CPU only | 16GB | 5-10 tok/s |
| **Minimal** | Integrated/Mobile | 8GB | 2-5 tok/s |

---

## Стратегия 1: Агрессивная квантизация

### Варианты квантизации Nemotron

| Квантизация | Размер | VRAM | Потеря качества |
|-------------|--------|------|-----------------|
| BF16 | ~60GB | 64GB | 0% |
| Q8_0 | ~34GB | 36GB | ~1% |
| Q5_K_M | ~26GB | 28GB | ~2% |
| **Q4_K_M** | ~18GB | 20GB | **~3%** |
| Q4_0 | ~16GB | 18GB | ~5% |
| Q3_K_M | ~14GB | 16GB | ~8% |
| **Q2_K** | ~10GB | 12GB | **~15%** |
| IQ2_XS | ~8GB | 10GB | ~20% |

### Рекомендации по железу

```
RTX 4090 (24GB): Q4_K_M — полностью в VRAM
RTX 3080 (10GB): Q4_K_M + partial offload
RTX 2080 (8GB):  Q4_0 + heavy offload или Q3_K_M
GTX 1660 (6GB):  Q2_K + CPU offload
CPU only:        Q4_K_M в RAM (медленно, но работает)
```

### Ollama команды

```bash
# Скачать нужную квантизацию
ollama pull nemotron-3-nano:30b-q4_K_M
ollama pull nemotron-3-nano:30b-q3_K_M
ollama pull nemotron-3-nano:30b-q2_K

# Настройка GPU layers для partial offload
# В ~/.ollama/config (или через API)
OLLAMA_NUM_GPU=20  # Количество слоёв на GPU
```

---

## Стратегия 2: Дистилляция в меньшую модель

### Идея

```
Nemotron-30B-A3B (Teacher) → Qwen2.5-Math-7B (Student)
         ↓ знания
    Fine-tuned 7B модель
    для математического тьюторинга
```

### Преимущества дистилляции

| Аспект | Nemotron-30B | Distilled 7B |
|--------|--------------|--------------|
| VRAM | 18GB (Q4) | **4GB (Q4)** |
| Скорость | 10-20 tok/s | **50+ tok/s** |
| Качество (MATH) | 82.9% | ~75-80%* |

*После качественной дистилляции

### План дистилляции

#### Этап 1: Генерация датасета (Teacher → Data)

```python
# training/dataset/dialog_generator.py
# Nemotron генерирует 3000+ сократических диалогов
# Покрытие: все TutorMoves, все уровни сложности
```

**Структура диалога:**
```json
{
  "task": {
    "problem": "Найдите производную f(x) = x³",
    "solution": "f'(x) = 3x²",
    "hints": ["Правило степени", "d/dx(xⁿ) = nxⁿ⁻¹"]
  },
  "dialog": [
    {"role": "student", "content": "Не знаю с чего начать"},
    {"role": "tutor", "move": "scaffolding", "content": "Какое правило применяется к степеням?"}
  ]
}
```

#### Этап 2: QLoRA Fine-tuning (Data → Student)

**Конфигурация:**
```yaml
model: Qwen/Qwen2.5-Math-7B-Instruct
quantization: 4bit (NF4)
lora:
  r: 64
  alpha: 128
  target_modules: [q_proj, k_proj, v_proj, o_proj]
training:
  epochs: 3
  batch_size: 4
  learning_rate: 2e-4
  gradient_accumulation: 4
```

**Требования для обучения:**
- Google Colab A100 (40GB) — рекомендуется
- RTX 4090 (24GB) — возможно с gradient checkpointing
- Время: ~4-8 часов на 3000 диалогов

#### Этап 3: Оценка и итерация

```python
# evaluation/metrics.py
- json_validity_rate > 95%
- move_accuracy > 80%
- latex_usage_rate > 90%
- no_answer_leak_rate > 98%
- socratic_score (questions vs statements) > 70%
```

### Выбор Student модели

| Модель | Размер | MATH | Русский | Рекомендация |
|--------|--------|------|---------|--------------|
| **Qwen2.5-Math-7B** | 7B | 85% | ⚠️ | Лучшая математика |
| **Qwen2.5-7B** | 7B | 75% | ✅ | Лучший русский |
| Qwen2.5-3B | 3B | 65% | ✅ | Минимальный размер |
| Phi-3-mini | 3.8B | 70% | ❌ | Только английский |

**Рекомендация:** `Qwen2.5-7B-Instruct` как баланс качества и русского языка.

---

## Стратегия 3: Оптимизация промптов

### Сокращение системного промпта

**Было (~2000 токенов):**
```
Ты — сократический репетитор по математике...
[длинные инструкции]
[примеры для каждого move]
[подробные правила]
```

**Стало (~500 токенов):**
```
Репетитор математики. Принципы:
1. Не давай ответ — задавай вопросы
2. Один вопрос за раз
3. $LaTeX$ для формул
4. JSON: {"move": "...", "message": "...", "reasoning": "..."}
```

### Экономия контекста

| Оптимизация | Экономия токенов |
|-------------|------------------|
| Короткий system prompt | -1500 |
| Сжатие истории диалога | -500 |
| Убрать примеры | -800 |
| **Итого** | **~2800 токенов** |

**Влияние на VRAM:**
- Меньше контекста = меньше KV-cache
- ~500MB экономии на 4K контексте

---

## Стратегия 4: Кэширование и оптимизация инференса

### 4.1 Prompt Caching

```python
# src/utils/prompt_cache.py
class PromptCache:
    """Кэширование частых промптов и ответов."""

    def __init__(self, max_size=1000):
        self.cache = LRUCache(max_size)

    def get_or_generate(self, prompt_hash, generate_fn):
        if prompt_hash in self.cache:
            return self.cache[prompt_hash]
        result = generate_fn()
        self.cache[prompt_hash] = result
        return result
```

### 4.2 Speculative Decoding

Использование маленькой draft модели для ускорения:

```
Draft model (Qwen-0.5B) → предсказывает N токенов
Target model (Nemotron-30B) → проверяет за 1 проход
Ускорение: 2-3x
```

**Поддержка в llama.cpp:**
```bash
./main -m nemotron-30b.gguf \
       --draft-model qwen-0.5b.gguf \
       --draft-n 8
```

### 4.3 Continuous Batching

Для multi-user сценариев:

```python
# Использовать vLLM или TGI вместо Ollama
# vLLM: до 10x throughput increase
pip install vllm
vllm serve nvidia/Nemotron-3-Nano-30B-A3B --quantization awq
```

---

## Стратегия 5: Гибридная архитектура

### Идея: Router + Специализированные модели

```
                    ┌─────────────────────┐
                    │   Router (0.5B)     │
                    │ Классификация задач │
                    └──────────┬──────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ Simple Math   │    │ Complex Math  │    │ Explanation   │
│ Qwen-0.5B     │    │ Nemotron-30B  │    │ Qwen-3B       │
│ ~1GB VRAM     │    │ Full power    │    │ ~2GB VRAM     │
└───────────────┘    └───────────────┘    └───────────────┘
```

### Когда какую модель использовать

| Задача | Модель | Причина |
|--------|--------|---------|
| Простая арифметика | Qwen-0.5B | Быстро, дёшево |
| Сложные уравнения | Nemotron-30B | Нужна мощь |
| Объяснения | Qwen-3B | Баланс |
| Верификация ответа | SymPy | Точно, бесплатно |

### Реализация

```python
# src/agents/router_agent.py
class TaskRouter:
    """Роутер задач к оптимальной модели."""

    COMPLEXITY_THRESHOLDS = {
        "simple": 0.3,    # → small model
        "medium": 0.7,    # → medium model
        "complex": 1.0    # → full model
    }

    def route(self, task: Task) -> str:
        complexity = self._estimate_complexity(task)
        if complexity < 0.3:
            return "qwen:0.5b"
        elif complexity < 0.7:
            return "qwen:3b"
        else:
            return "nemotron-3-nano:30b"
```

---

## Стратегия 6: Progressive Loading

### Идея: Загружать модель по частям

```python
# Для очень ограниченной памяти
# Загружаем только нужные эксперты MoE

class ProgressiveLoader:
    """Динамическая загрузка экспертов."""

    def __init__(self, model_path, max_experts_in_memory=16):
        self.expert_cache = LRUCache(max_experts_in_memory)

    def load_expert(self, expert_id):
        if expert_id not in self.expert_cache:
            # Выгружаем старый, загружаем новый
            self.expert_cache.put(expert_id, self._load_from_disk(expert_id))
        return self.expert_cache[expert_id]
```

**Примечание:** Это экспериментальная техника, требует модификации inference engine.

---

## Рекомендованный план действий

### Фаза 1: Немедленные оптимизации (1-2 дня)

1. ✅ Переключиться на Nemotron-3-Nano
2. [ ] Оптимизировать системные промпты
3. [ ] Настроить оптимальную квантизацию для железа
4. [ ] Добавить prompt caching

### Фаза 2: Дистилляция (1-2 недели)

5. [ ] Создать пайплайн генерации датасета
6. [ ] Сгенерировать 3000+ диалогов
7. [ ] Fine-tune Qwen2.5-7B на Colab
8. [ ] Оценить качество

### Фаза 3: Продвинутые оптимизации (опционально)

9. [ ] Реализовать гибридную архитектуру с роутером
10. [ ] Добавить speculative decoding
11. [ ] Интегрировать vLLM для production

---

## Ожидаемые результаты

| Конфигурация | До оптимизации | После |
|--------------|----------------|-------|
| RTX 2080 (8GB) | 5-10 tok/s | **15-25 tok/s** |
| GTX 1660 (6GB) | 2-5 tok/s | **8-15 tok/s** |
| CPU only (16GB) | 1-2 tok/s | **3-5 tok/s** |

| Метрика | Nemotron-30B | Distilled-7B |
|---------|--------------|--------------|
| MATH accuracy | 82.9% | **~78%** |
| Response time | 3-5s | **0.5-1s** |
| VRAM | 18GB | **4GB** |

---

## Файлы для реализации

```
training/
├── configs/
│   ├── qlora_config.yaml          # QLoRA конфиг
│   └── quantization_config.yaml   # Настройки квантизации
├── dataset/
│   ├── dialog_generator.py        # Генератор диалогов
│   ├── dataset_builder.py         # Сборщик датасета
│   └── quality_filter.py          # Фильтр качества
├── scripts/
│   ├── generate_dataset.py        # Скрипт генерации
│   ├── train_sft.py               # SFT обучение
│   └── optimize_prompts.py        # Оптимизация промптов
└── utils/
    ├── prompt_cache.py            # Кэширование
    └── model_router.py            # Роутер моделей

src/models/
├── hf_client.py                   # HuggingFace клиент
└── optimized_client.py            # Оптимизированный клиент

evaluation/
├── metrics.py                     # Метрики качества
└── benchmark.py                   # Бенчмарки
```
