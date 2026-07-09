# Training Pipeline: Дообучение Qwen3.5-9B для STEM-репетитора

> Методология 3-стадийного RL-пайплайна для дипломной работы

## 1. Обзор

Цель дообучения — превратить базовую модель Qwen3.5-9B в специализированного
STEM-репетитора, который:
1. Решает задачи пошагово на русском языке
2. Объясняет каждый шаг рассуждения
3. Оформляет финальный ответ в формате `\boxed{}`
4. Работает по 5 доменам: математика, физика, химия, биология, информатика

### Пайплайн

```
Qwen3.5-9B (базовая модель)
        │
        ├── Evaluation: baseline accuracy
        │
        ▼
┌───────────────────────────────────────┐
│  Stage 1: GSPO                        │
│  Group Sequence Policy Optimization   │
│  + Curriculum Learning                │
│  + 7 алгоритмических оптимизаций      │
└───────────────┬───────────────────────┘
                ▼
┌───────────────────────────────────────┐
│  Stage 2: KTO                         │
│  Kahneman-Tversky Optimization        │
│  + Сократическое выравнивание         │
│  + Непарные предпочтения              │
└───────────────┬───────────────────────┘
                ▼
┌───────────────────────────────────────┐
│  Stage 3: DPO                         │
│  Direct Preference Optimization       │
│  + KTO checkpoint → DPO input         │
│  + Format Polishing                   │
└───────────────┬───────────────────────┘
                ▼
        Fine-tuned STEM Tutor
        │
        └── Evaluation: post-training accuracy
```

### Обоснование удаления SFT

Начальная версия пайплайна включала стадию SFT (Supervised Fine-Tuning) перед GSPO.
Она была удалена: Instruct-модель уже обучена для диалога, дополнительный SFT
приводил к переобучению и снижению exploration diversity.

### Обоснование удаления AdaSTaR

Стадия AdaSTaR (Adaptive Self-Taught Reasoner) была удалена при переходе на Qwen3.5-9B:
9B-модель имеет значительно более сильный baseline, и marginal gain от AdaSTaR
(~1.5% на 4B) не оправдывает дополнительную стадию. 3-стадийный пайплайн проще
и быстрее.

---

## 2. Базовая модель

**Qwen3.5-9B** (Alibaba/Qwen Team, released March 2, 2026)

| Параметр | Значение |
|----------|---------|
| Параметры | ~9B |
| Архитектура | Dense Transformer, Gated DeltaNet |
| Скрытый размер | 4096 |
| Слои | 32 |
| Контекст | 128K tokens |
| Precision | bf16 (full precision, no quantization during training) |
| VRAM | ~18 GB (inference), ~45-50 GB (training bf16 LoRA) |
| GPU | RTX PRO 6000 Blackwell 96GB |
| Thinking mode | `enable_thinking=True/False` в `chat_template_kwargs` |

**Адаптация (LoRA):**
Все стадии используют Low-Rank Adaptation с параметрами:
- `r=16`, `alpha=32`, `dropout=0.0`
- Target modules: `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`
- bf16 full precision (no QLoRA 4-bit — RTX PRO 6000 Blackwell 96GB has sufficient VRAM)

---

## 3. Stage 1: GSPO (Group Sequence Policy Optimization)

**Цель:** Обучить модель генерировать пошаговые решения STEM-задач с верифицируемыми
ответами. Используется curriculum learning для постепенного усложнения.

**Ноутбук:** `notebooks/grpo_qwen3.5_9b.ipynb`

### 3.1 Метод

GSPO [arXiv:2507.18071] — метод обучения с подкреплением для LLM, разработанный
командой Qwen. Отличается от GRPO [arXiv:2402.03300] sequence-level importance
sampling ratios, что обеспечивает более стабильную тренировку.

Алгоритм:
1. Для каждого промпта генерируется G completions
2. Каждый completion оценивается reward-функциями (correctness + format + Socratic)
3. Advantage нормализуется внутри группы (group-relative)
4. Policy обновляется через clipped surrogate loss с importance sampling

### 3.2 Ключевые оптимизации

| # | Техника | Источник | Описание |
|---|---------|----------|----------|
| 1 | **GSPO sequence-level IS** | arXiv:2507.18071 | Importance sampling на уровне всей последовательности, а не токенов. Требует ε на 2-3 порядка меньше (3e-4 vs 0.2). |
| 2 | **Dr. GRPO** | arXiv:2503.20783 | Constant length normalization: делим loss на `max_completion` вместо длины конкретного completion. Устраняет bias к коротким ответам. |
| 3 | **ReDit dithering** | arXiv:2506.18631 | Гауссовский шум (σ=0.05) на бинарных наградах (0/1). Создаёт градиент информации даже когда все completions правильные или неправильные. Ускоряет сходимость до 10×. |
| 4 | **GDPO decoupled normalization** | arXiv:2601.05242 | Correctness, format и Socratic rewards нормализуются независимо, затем комбинируются с весами [0.4, 0.15, 0.45]. Предотвращает reward hacking. |
| 5 | **GRPO-LEAD curriculum** | arXiv:2504.09696 | Difficulty-aware веса: hard=2×, medium=1×, easy=0.5×. Stage 1 (200 steps) — only easy+medium; Stage 2 (400 steps) — all difficulties. |
| 6 | **Zero-variance masking** | arXiv:2505.22257 | Если все G completions получили одинаковую награду (std < 1e-6), группа маскируется NaN → TRL пропускает. Экономит вычисления. |
| 7 | **Clip-Higher** | arXiv:2504.05118 | Асимметричный клиппинг: ε=3e-4 (снизу), ε_high=4e-4 (сверху). Позволяет повышать вероятность хороших ответов чуть сильнее, чем снижать плохих. |

### 3.3 Гиперпараметры

| Параметр | Значение | Обоснование |
|----------|---------|-------------|
| `loss_type` | `dr_grpo` | Constant length norm (SAPO не поддерживается Unsloth) |
| `importance_sampling_level` | `sequence` | GSPO specification |
| `epsilon` | 3e-4 | GSPO paper §5.1 (sequence-level scale) |
| `epsilon_high` | 4e-4 | GSPO paper §5.1 |
| `beta` | 0.0 | Без KL-регуляризации (GSPO/DAPO стандарт) |
| `G` | 32 | Completions per prompt (96GB) |
| `max_completion` | 1024 | Tokens per completion (Qwen3.5 thinking longer) |
| `learning_rate` | 5e-7 | Lower for 9B model |
| `grad_accum` | 4 | Effective batch = 128 |
| `steps_per_generation` | 8 | 4 optimizer updates per rollout |
| `total_steps` | 600 | Stage 1: 200 + Stage 2: 400 |
| `dithering_sigma` | 0.05 | ReDit noise scale |
| `reward_weights` | [0.4, 0.15, 0.45] | Correctness : Format : Socratic |

### 3.4 Reward Functions

**Correctness reward** (вес 0.4):
- Для расчётных задач: извлечение `\boxed{}` → SymPy symbolic comparison
- Для MC-задач: извлечение буквы ответа (A/B/C/D) → exact match
- Доменные верификаторы: ChemPy (химия), физические единицы (физика)
- Correct = 1.0, Wrong = 0.0 (без отрицательных штрафов, DRPO)

**Format reward** (вес 0.15):
- Наличие `\boxed{}` для расчётных / правильный формат для MC (+0.5)
- Step markers (шаг, следовательно, потому что) (+0.3)
- Длина 50-800 слов (+0.2)

**Socratic reward** (вес 0.45):
- Проверяет, что ответ не содержит прямого решения (no_leak)
- Оценивает наличие направляющего вопроса к ученику (guide)
- Реализован как MITS custom reward function

---

## 4. Stage 2: KTO (Kahneman-Tversky Optimization)

**Цель:** Сократическое выравнивание — модель обучается предпочитать стиль Сократа
(вопросы, направление, без прямых ответов) над прямым объяснением.

**Ноутбук:** `notebooks/kto_qwen3.5_9b.ipynb`

### 4.1 Метод [arXiv:2402.01306]

KTO — метод выравнивания предпочтений, основанный на теории перспектив Канемана-Тверски.
В отличие от DPO и RLHF, KTO не требует парных примеров (chosen/rejected на один и тот же промпт):
обучается на непарных предпочтениях — отдельных примерах с меткой "good" или "bad".

Функция потерь:
- **Desirable (good):** максимизировать log p(y|x) − KL(π || π_ref)
- **Undesirable (bad):** минимизировать log p(y|x) − KL(π || π_ref)
- Асимметрия (λ_D vs λ_U) отражает психологическую нелинейность: потери ощущаются сильнее, чем приобретения

### 4.2 Данные

| Источник | Количество | Описание |
|----------|-----------|----------|
| `data/training/dialogs.jsonl` | 3 875 | Сократические диалоги (good examples) |
| `training/data/preference_pairs.jsonl` | 12 597 | Пары предпочтений (desirable + undesirable) |

### 4.3 Параметры

| Параметр | Значение |
|----------|---------|
| KTO beta | 0.1 |
| λ_D (desirable weight) | 1.0 |
| λ_U (undesirable weight) | 1.0 |
| Learning rate | 5e-7 |
| Max steps | 600 |
| Batch size | 4 (96GB) |
| Gradient accumulation | 4 |
| Random seed | 42 |

---

## 5. Stage 3: DPO (Direct Preference Optimization)

**Цель:** Полировка формата рассуждений через preference learning.
Не должна ухудшать accuracy — только улучшить читаемость и структуру.
DPO загружает KTO чекпоинт напрямую.

**Ноутбук:** `notebooks/dpo_polish_qwen3.5_9b.ipynb`

### 5.1 Метод

DPO [arXiv:2305.18290] обучает модель на парах (chosen, rejected) без
необходимости явной reward model:

- **Chosen:** правильное решение с лучшим format score (из KTO данных)
- **Rejected:** примеры с низким format score из preference_pairs.jsonl

### 5.2 Guard механизм

DPO пропускается если:
1. Сгенерировано < MIN_PAIRS preference pairs (модель уже сильная)
2. Accuracy падает более чем на 1% (safety check)
3. Format score не улучшается на 10%+

### 5.3 Параметры

| Параметр | Значение |
|----------|---------|
| DPO beta | 0.1 |
| Learning rate | 5e-7 |
| Max steps | 200 |
| Batch size | 2 (96GB) |
| Gradient accumulation | 8 |
| Min pairs | 50 |
| Pairs per problem | 8 |
| Input checkpoint | KTO output |

---

## 6. Evaluation Methodology

### 6.1 Benchmark

Составной benchmark из 3 источников, 3678 задач:

| Источник | Количество | Тип ответа | Описание |
|----------|-----------|-----------|----------|
| Custom LLM-generated | 218 | numeric, latex | 5 доменов, 3 сложности |
| MGSM Russian | 250 | numeric | GSM8K переведённый на русский |
| ruMMLU STEM | 3,210 | mc_letter | 20 предметов → 5 доменов MITS |

**Распределение по доменам:**

| Домен | Количество |
|-------|-----------|
| Математика | 1,141 |
| Биология | 904 |
| Физика | 829 |
| Информатика | 455 |
| Химия | 349 |

### 6.2 Verification Pipeline

```
Model output → extract_answer() → verify()
                    │                    │
                    ├── \boxed{} → SymPy simplify → symbolic eq
                    ├── MC letter → exact match (A/B/C/D)
                    ├── numeric → tolerance 5% (physics) or exact
                    └── chemistry → ChemPy validation
```

### 6.3 Метрики

Для каждой стадии сохраняются:
- **Overall accuracy** (все задачи)
- **Per-domain accuracy** (math, physics, chemistry, biology, cs)
- **Per-difficulty accuracy** (easy, medium, hard)
- **Время inference** (seconds per problem)

Формат: JSON report + строка в `summary.csv` для графиков.

### 6.4 Скрипты

| Скрипт | Назначение |
|--------|-----------|
| `training/scripts/evaluate_stage.py` | Основной: `evaluate_with_model()`, `save_report()`, `append_summary_csv()` |
| `training/scripts/build_eval_benchmark.py` | Сборка benchmark из 3 источников |
| `training/scripts/generate_eval_dataset.py` | Генерация custom задач через LLM |

---

## 7. Оборудование и воспроизводимость

### Training

| Параметр | Значение |
|----------|---------|
| GPU | RTX PRO 6000 Blackwell 96GB |
| Framework | Unsloth + TRL + PEFT |
| Квантизация | Нет (bf16 full precision) |
| Precision | bfloat16 |
| Random seed | 42 |

### Inference (целевое)

| Параметр | Значение |
|----------|---------|
| GPU | NVIDIA RTX 2080 (8GB VRAM) |
| CPU | AMD Ryzen 9 9950X |
| RAM | 32 GB |
| Runtime | llama-server / llama-swap (GGUF Q4_K_M, порт :8090) |

### Воспроизводимость

1. Все ноутбуки содержат resume support для Colab disconnect recovery
2. Checkpoints сохраняются на Google Drive
3. Adapters загружаются на HuggingFace Hub (private repos)
4. Training configs сохраняются в JSON рядом с checkpoints
5. Evaluation reports воспроизводимы через `evaluate_stage.py`

---

## 8. Ссылки

### Основные методы

| Метод | Статья | Использование |
|-------|--------|---------------|
| GSPO | [arXiv:2507.18071](https://arxiv.org/abs/2507.18071) | Stage 1: основной алгоритм |
| GRPO | [arXiv:2402.03300](https://arxiv.org/abs/2402.03300) | Stage 1: group-relative advantages |
| Dr. GRPO | [arXiv:2503.20783](https://arxiv.org/abs/2503.20783) | Stage 1: length normalization |
| DAPO | [arXiv:2503.14476](https://arxiv.org/abs/2503.14476) | Stage 1: Clip-Higher |
| VAPO | [arXiv:2504.05118](https://arxiv.org/abs/2504.05118) | Stage 1: clipping bounds |
| ReDit | [arXiv:2506.18631](https://arxiv.org/abs/2506.18631) | Stage 1: reward dithering |
| GDPO | [arXiv:2601.05242](https://arxiv.org/abs/2601.05242) | Stage 1: decoupled rewards |
| GRPO-LEAD | [arXiv:2504.09696](https://arxiv.org/abs/2504.09696) | Stage 1: curriculum RL |
| Revisiting GRPO | [arXiv:2505.22257](https://arxiv.org/abs/2505.22257) | Stage 1: zero-variance masking |
| DRPO | [arXiv:2510.04474](https://arxiv.org/abs/2510.04474) | Stage 1: no negative penalties |
| KTO | [arXiv:2402.01306](https://arxiv.org/abs/2402.01306) | Stage 2: Kahneman-Tversky alignment |
| DPO | [arXiv:2305.18290](https://arxiv.org/abs/2305.18290) | Stage 3: preference optimization |

### Базовая модель

| Ресурс | Ссылка |
|--------|--------|
| Qwen3 Technical Report | [arXiv:2505.09388](https://arxiv.org/abs/2505.09388) |
| Qwen3 GSPO Blog | [qwenlm.github.io/blog/gspo](https://qwenlm.github.io/blog/gspo/) |
| SAPO (Qwen loss) | [arXiv:2511.20347](https://arxiv.org/abs/2511.20347) |

### Инструменты

| Инструмент | Ссылка |
|-----------|--------|
| Unsloth | [github.com/unslothai/unsloth](https://github.com/unslothai/unsloth) |
| TRL | [github.com/huggingface/trl](https://github.com/huggingface/trl) |
| PEFT | [github.com/huggingface/peft](https://github.com/huggingface/peft) |
| llama-server / llama-swap | Production inference stack (GGUF Q4_K_M, :8090) |
| Ollama | [ollama.ai](https://ollama.ai/) — legacy fallback only |
