# Конспект: RL для языковых моделей — GSPO, KTO, DPO и архитектура Qwen3.5

---

## Слайд 1: Титульный

- Презентация покрывает теоретические основы RL для LLM и архитектуру Qwen3.5
- Практическое применение: проект MITS (3-стадийный пайплайн GSPO → KTO → DPO)
- Все методы реально использованы в дипломной работе, не обзор литературы

---

## Слайд 2: Эволюция RL для LLM

**2020 — RLHF (InstructGPT, ChatGPT):**
- Архитектура: 4 модели одновременно в VRAM:
  1. Policy model π_θ (обучаемая)
  2. Reference model π_ref (замороженная копия, для KL-штрафа)
  3. Reward model r_φ (обучена на парных предпочтениях людей)
  4. Value model V_ψ (critic, оценивает ожидаемую награду)
- PPO loss: L = -E[min(ρÂ, clip(ρ, 1-ε, 1+ε)Â)] + c₁·L_VF + c₂·S[π_θ]
  - ρ = π_θ(a|s) / π_old(a|s) — importance sampling ratio
  - Â — advantage (из GAE: обобщённая оценка преимущества)
  - L_VF — loss value function, S — entropy bonus
- Проблема: VRAM × 4 модели, нестабильность PPO, reward hacking
- VRAM на Llama-7B: ~28 GB × 4 ≈ 112 GB (4× A100 или 8× A6000)

**2023 — DPO (NeurIPS 2023):**
- Прорыв: доказали, что optimal policy имеет closed-form solution
  - π*(y|x) = π_ref(y|x) · exp(r(x,y)/β) / Z(x)
  - Следствие: r(x,y) = β · log(π*/π_ref) + β·log Z — reward можно извлечь из policy
- Убрали: Reward Model + Value Model → осталось 2 модели (policy + reference)
- VRAM: ~56 GB для 7B (2× модели) — вдвое дешевле RLHF
- Ограничение: нужны ПАРНЫЕ предпочтения (chosen, rejected) для одного промпта

**2024 — KTO (arXiv:2402.01306):**
- Ключевое: убрали требование ПАРНЫХ данных
- Каждый пример размечен просто как "хорошо" (desirable) или "плохо" (undesirable)
- Это проще собрать: thumbs up/down вместо "что лучше A или B?"
- Теоретическая база: prospect theory (Kahneman & Tversky, 1979)
- Модели: по-прежнему 2 (policy + reference)

**2025 — GRPO (DeepSeek-R1, arXiv:2402.03300):**
- Ключевое: убрали Value Model из PPO → 1 модель + reference
- Вместо V(s) для baseline используется среднее награды по группе G completions
- Нет Reward Model: используются verifiable rewards (SymPy, exact match)
- Итого: нужна только 1 обучаемая модель + 1 замороженная reference
- Идеально для задач с проверяемыми ответами (математика, код, STEM)

**2026 — GSPO (arXiv:2507.18071, команда Qwen):**
- Модификация GRPO: importance sampling на уровне ПОСЛЕДОВАТЕЛЬНОСТИ, а не токена
- Почему это важно: см. слайд 4

**Тренд: 4 модели → 2 → 2 → 1+ref → 1+ref (но с верифицируемыми наградами)**

---

## Слайд 3: GRPO — Group Relative Policy Optimization

**Алгоритм пошагово:**

```
Input: промпт x, policy π_θ, reward function r()
1. Сгенерировать G completions: {y₁, y₂, ..., y_G} ~ π_θ(·|x)
2. Оценить каждый: rᵢ = r(x, yᵢ)  # верифицируемая награда
3. Вычислить group-relative advantage:
   Âᵢ = (rᵢ - mean(r₁..r_G)) / std(r₁..r_G)
4. Обновить policy:
   L = -1/G Σᵢ Σₜ min(ρₜÂᵢ, clip(ρₜ, 1-ε, 1+ε)Âᵢ)
   где ρₜ = π_θ(yᵢₜ|x, yᵢ<ₜ) / π_old(yᵢₜ|x, yᵢ<ₜ)
5. KL-штраф (опционально):
   L_KL = β · D_KL(π_θ || π_ref)
```

**Почему group normalization работает:**
- Если G=32: даже при 90% accuracy ~3 completion'а будут неверными
- Верные получают positive advantage, неверные — negative
- Нет нужды в отдельной baseline network (Value Model)

**Гиперпараметры в MITS:**
- G = 32 completions per prompt (Unsloth: batch_size = num_generations)
- ε = 0.2 (стандартный PPO clip для token-level)
- β = 0.0 (без KL-регуляризации — стандарт для GSPO/DAPO)
- max_completion = 1024 tokens

**Ограничение GRPO:**
- Если все G completions верные ИЛИ все неверные → std(r) ≈ 0 → деление на 0
- Решение 1: zero-variance masking (пропускаем группу)
- Решение 2: ReDit dithering (добавляем шум к наградам)

---

## Слайд 4: GSPO + 7 оптимизаций

**GSPO vs GRPO — ключевое отличие:**

GRPO (token-level IS):
```
ρₜ = π_θ(yₜ|x, y<ₜ) / π_old(yₜ|x, y<ₜ)  # для каждого токена
```
- Проблема: при длинных sequence (500+ токенов) ρₜ может сильно отклоняться
- ε_token = 0.2 (стандартный clip)

GSPO (sequence-level IS):
```
ρ_seq = π_θ(y|x) / π_old(y|x) = Πₜ ρₜ  # произведение по всем токенам
```
- На уровне последовательности вариация МЕНЬШЕ (central limit theorem эффект)
- ε_seq = 3e-4 (на 2-3 порядка меньше token-level!)
- Результат: policy обновляется мягче → меньше катастрофических шагов

**ВАЖНО:** ε для GSPO (3e-4) и GRPO (0.2) — РАЗНЫЕ масштабы. Ошибка с ε — одна из главных причин нестабильности тренировки (мы на этом обжигались).

**7 оптимизаций подробно:**

**1. Dr. GRPO (arXiv:2503.20783) — Constant Length Normalization:**
- Стандартный GRPO: loss делится на длину конкретного completion
- Проблема: короткие ответы получают больший loss per token → bias к краткости
- Dr. GRPO: делим на max_completion_length (константа) для всех
- Формула: L = Σₜ loss_t / max_len (вместо / actual_len)

**2. ReDit (arXiv:2506.18631) — Reward Dithering:**
- Проблема: бинарные rewards {0, 1} → часто все G ответов одинаковы
- Решение: r_new = r + N(0, σ²), σ = 0.05
- Эффект: даже "все верные" группы дают gradient signal
- Ускорение: до 10× по effective training steps
- Почему σ=0.05: достаточно для создания variance, но не меняет ранжирование

**3. GDPO (arXiv:2601.05242) — Decoupled Normalization:**
- Проблема: correctness ∈ {0,1}, format ∈ [0,1] — разные масштабы
- Если нормализовать вместе: format с бо́льшим variance доминирует
- GDPO: Â_correct = norm(r_correct), Â_format = norm(r_format), отдельно
- Advantage = 0.7·Â_correct + 0.15·Â_format + 0.15·Â_socratic

**4. GRPO-LEAD (arXiv:2504.09696) — Curriculum Learning:**
- Веса по сложности: hard=2.0, medium=1.0, easy=0.5
- Stage 1 (200 шагов): only easy + medium → стабильный старт
- Stage 2 (400+ шагов): все сложности → полное обучение
- Зачем: без curriculum модель может "застрять" на hard задачах

**5. Zero-variance masking (arXiv:2505.22257):**
- Если std(rewards) < 1e-6 в группе → advantage = NaN → TRL пропускает
- Экономит compute: ~15-20% групп могут быть "бесполезными"

**6. Clip-Higher (arXiv:2504.05118):**
- Стандартный clip: clip(ρ, 1-ε, 1+ε) — симметричный
- Clip-Higher: clip(ρ, 1-ε_low, 1+ε_high), где ε_high > ε_low
- В MITS: ε_low = 3e-4, ε_high = 4e-4
- Смысл: чуть легче ПОВЫШАТЬ вероятность хороших ответов, чем ПОНИЖАТЬ плохих
- Это мягкая форма optimism bias

**7. ThinkingBudgetProcessor (наша разработка):**
```python
class ThinkingBudgetProcessor(LogitsProcessor):
    def __call__(self, input_ids, scores):
        thinking_tokens = count_tokens_after_think_tag(input_ids)
        if thinking_tokens > self.budget:  # budget = 2048
            scores[self.think_end_id] += self.boost  # усиливаем </think>
        return scores
```
- Проблема: Qwen3.5 в thinking-режиме может генерировать 10K+ токенов мыслей
- Hard cutoff: обрезаем → поломанный JSON, неоконченные мысли
- Мягкое завершение: boost увеличивает ВЕРОЯТНОСТЬ </think>, но не форсирует
- Модель может завершить текущую мысль и корректно выйти из thinking

---

## Слайд 5: Triple GDPO Reward

**Три reward-функции:**

**1. Correctness Reward (w=0.70):**
```python
def correctness_reward(completion, ground_truth):
    extracted = extract_boxed_answer(completion)  # парсим \boxed{}
    if is_mc_question:
        return 1.0 if extracted_letter == truth_letter else 0.0
    elif is_numeric:
        return 1.0 if sympy.simplify(extracted - truth) == 0 else 0.0
    elif is_chemistry:
        return 1.0 if chempy_verify(extracted, truth) else 0.0
```
- Бинарная: correct=1.0, wrong=0.0 (без частичных баллов)
- Без отрицательных штрафов: wrong=0, не -1 (DRPO стиль)

**2. Format Reward (w=0.15):**
```python
def format_reward(completion):
    score = 0.0
    if has_boxed(completion): score += 0.5
    if has_step_markers(completion): score += 0.3  # "шаг", "следовательно"
    if 50 <= word_count(completion) <= 800: score += 0.2
    return score  # ∈ [0, 1]
```

**3. Socratic Reward (w=0.15):**
- LLM-судья через Cerebras API (llama-4-scout-17b)
- Промпт-рубрика: guides_student (0-2), no_answer_leak (0-2), scaffolding (0-2), engagement (0-1)
- socratic_score = (guides + no_leak + scaffold + engage) / 7
- Уникально для нашей работы: в литературе reward обычно только correctness/format

**GDPO Decoupled Normalization:**
```python
# Внутри группы из G completions:
A_correct = (r_correct - mean(r_correct)) / (std(r_correct) + eps)
A_format  = (r_format - mean(r_format)) / (std(r_format) + eps)
A_socratic = (r_socratic - mean(r_socratic)) / (std(r_socratic) + eps)

# Комбинированный advantage:
A_total = 0.70 * A_correct + 0.15 * A_format + 0.15 * A_socratic
```
- Каждый тип rewards живёт в своём "пространстве" → нет доминирования

---

## Слайд 6: KTO — Kahneman-Tversky Optimization

**Теория перспектив (1979, Нобелевская премия 2002):**
- Люди оценивают изменения ОТНОСИТЕЛЬНО reference point, а не абсолютные значения
- Функция ценности v(x):
  - Gains (x ≥ 0): v(x) = x^α, α ≈ 0.88 — concave (убывающая предельная полезность)
  - Losses (x < 0): v(x) = -λ(-x)^β, β ≈ 0.88, λ ≈ 2.25
  - λ > 1 → loss aversion: потеря 100₽ "болезненнее" чем выигрыш 100₽
- S-образная кривая: крутая для losses, пологая для gains

**KTO Loss (формально):**

Для хороших примеров (y_w — desirable):
```
L_w = -σ(β · (r_θ(x, y_w) - z_ref))
где r_θ(x, y) = β · log(π_θ(y|x) / π_ref(y|x))  # implicit reward
    z_ref = E_{y'~D}[β · D_KL(π_θ(y'|x) || π_ref(y'|x))]  # KL baseline
```

Для плохих примеров (y_l — undesirable):
```
L_l = -σ(β · (z_ref - r_θ(x, y_l)))  # ОБРАТНЫЙ знак!
```

Итоговая:
```
L_KTO = w_d/(w_d·n_d + w_u·n_u) · Σ L_w + w_u/(w_d·n_d + w_u·n_u) · Σ L_l
```

**Балансировка весов (критически важно!):**
- Если desirable примеров больше (наш случай: 3875 good, 12597 bad на уровне сэмплов):
  - Считаем ratio: good_count / bad_count
  - undesirable_weight = min(ratio, 2.14)  # TRL upper bound
  - desirable_weight = 1.0
- В MITS: undesirable_weight = 2.13
- Без балансировки: модель игнорирует minority class

**Отличие от DPO:**
- DPO: L = -log σ(β · (r_θ(y_w) - r_θ(y_l))) — нужна ПАРА (y_w, y_l) для одного промпта
- KTO: каждый пример сам по себе, reference point через z_ref (средний KL)
- KTO проще собирать данные: "этот диалог хороший" / "этот плохой"

**Данные MITS для KTO:**
- dialogs.jsonl: 3875 Сократических диалогов → desirable (multi-turn)
- preference_pairs.jsonl: 12597 пар → rejected половина → undesirable
- Effective batch: 6 × 5 = 30 (batch_size × grad_accum)
- Total steps: 2582 (2 эпохи), warmup: 258 steps (10%)
- lr = 5e-7, β_KTO = 0.1

---

## Слайд 7: DPO — Direct Preference Optimization

**Математический вывод (ключевой):**

Задача RLHF: max_π E[r(x,y)] - β·D_KL(π || π_ref)

Решение (Lagrangian → closed form):
```
π*(y|x) = π_ref(y|x) · exp(r(x,y)/β) / Z(x)
```
где Z(x) = Σ_y π_ref(y|x) · exp(r(x,y)/β) — partition function

Из этого извлекаем reward:
```
r(x,y) = β · log(π*(y|x) / π_ref(y|x)) + β · log Z(x)
```

Подставляем в Bradley-Terry модель предпочтений:
```
P(y_w > y_l | x) = σ(r(x, y_w) - r(x, y_l))
```

Z(x) сокращается! Получаем DPO loss:
```
L_DPO = -E[log σ(β · (log π_θ(y_w|x)/π_ref(y_w|x) - log π_θ(y_l|x)/π_ref(y_l|x)))]
```

**Интуиция:**
- Увеличиваем log-probability chosen (y_w) относительно reference
- Уменьшаем log-probability rejected (y_l) относительно reference
- β контролирует "жёсткость": малый β → сильнее отклоняемся от reference

**DPO в MITS (Stage 3):**
- Входной чекпоинт: после KTO (не после GSPO напрямую)
- β = 0.1 — мягкое ограничение (не хотим сильно менять KTO-модель)
- lr = 5e-7 (очень малый — polishing, не learning)
- max_steps = 200 (короткая стадия)
- chosen: правильное решение с лучшим format score из группы
- rejected: из RAFT++ negative saving (неправильные решения, сохранённые ранее)

**Guard механизм:**
- Если < 50 пар → DPO пропускается (мало данных)
- Если accuracy падает > 1% → early stop (safety)
- Если format score не улучшился на 10% → early stop (нет прогресса)

---

## Слайд 8: Qwen3.5-9B — архитектура

**Основные характеристики:**
| Параметр | Значение |
|----------|---------|
| Параметры | ~9B |
| Архитектура | Dense Transformer + Gated DeltaNet |
| Слои | 32 |
| Hidden size | 4096 |
| Контекст | 128K токенов |
| Precision | bf16 |
| Released | 2 марта 2026, Alibaba/Qwen Team |

**Гибридная архитектура (ключевая инновация Qwen3.5):**
```
Layer  0: Gated DeltaNet (linear attention)
Layer  1: Gated DeltaNet
Layer  2: Gated DeltaNet
Layer  3: Standard Attention (softmax)    ← каждый 4-й
Layer  4: Gated DeltaNet
Layer  5: Gated DeltaNet
Layer  6: Gated DeltaNet
Layer  7: Standard Attention              ← каждый 4-й
...
Layer 28: Gated DeltaNet
Layer 29: Gated DeltaNet
Layer 30: Gated DeltaNet
Layer 31: Standard Attention
```
Паттерн: [linear, linear, linear, full_attention] × 8 = 24 DeltaNet + 8 Attention

**Зачем гибрид:**
- DeltaNet (75% слоёв): O(n) сложность по длине контекста
  - Хорош для: обработки длинных контекстов, потоковой генерации
  - Слаб в: точном retrieval из длинного контекста (needle-in-haystack)
- Softmax Attention (25% слоёв): O(n²) но точный
  - Хорош для: копирования из контекста, exact matching
  - Дорогой при длинных последовательностях
- Гибрид = лучшее из обоих: скорость DeltaNet + точность Attention

**Thinking mode (важно для RL-обучения):**
- Qwen3.5 умеет `<think>...</think>` нативно
- Включение: `enable_thinking=True` в chat_template_kwargs
- НЕ `/think` `/nothink` как у DeepSeek — другой API!
- Для Ollama: Modelfile ОБЯЗАТЕЛЬНО содержит:
  ```
  RENDERER qwen3.5
  PARSER qwen3.5
  ```
  Без этих строк thinking-теги не парсятся → модель работает, но <think> видны в output

**VRAM при обучении:**
- Inference: ~18 GB (bf16, batch=1)
- Training (LoRA r=16): ~45-50 GB (bf16, A100 80GB)
- GSPO (G=32 rollouts): ~65-70 GB (A100 80GB — впритык!)

---

## Слайд 9: Gated DeltaNet — линейное внимание

**Проблема стандартного attention:**
- Softmax attention: Attention(Q,K,V) = softmax(QK^T/√d)·V
- Сложность: O(n²·d) по длине контекста n
- 128K токенов: 128K × 128K = 16.4 млрд операций на слой → медленно

**Delta Rule (основа DeltaNet):**
- Рекуррентное состояние S ∈ R^{d_k × d_v} (матрица "памяти")
- Обновление на каждом шаге t:
```
S_t = α_t · S_{t-1} + β_t · (v_t ⊗ k_t^T)
```
- α_t (decay/alpha): скаляр на голову, экспоненциальное забывание
  - α → 1: долгая память (помним старые токены)
  - α → 0: короткая память (только свежие токены)
- β_t (write strength/beta): скаляр на голову, сила записи
  - β → 1: сильно записываем новую информацию
  - β → 0: игнорируем текущий токен

- Выход: o_t = z_t ⊙ (S_t · q_t)
  - z_t (gate): контролирует, сколько из S_t попадает на выход
  - Аналогия: z_t — "читающая головка", β_t — "записывающая головка"

**Почему O(n):**
- S_t зависит только от S_{t-1} → рекуррентное обновление
- Нет матрицы n×n (как в softmax attention)
- Каждый шаг: O(d_k · d_v) операций → линейно по n

**Causal conv1d:**
- Дополнительный компонент: короткое скользящее окно (kernel_size=4)
- Зачем: DeltaNet хорош для глобальных паттернов, но слаб для локальных
- conv1d добавляет "ближнее зрение" → лучшая локальная связность

**Проекции DeltaNet vs Standard Attention:**

| Standard Attention | DeltaNet | Описание |
|-------------------|----------|----------|
| q_proj | in_proj_qkv | Q,K,V (fused в DeltaNet!) |
| k_proj | (в in_proj_qkv) | — |
| v_proj | (в in_proj_qkv) | — |
| — | in_proj_z | Gate (нет аналога в attention) |
| — | in_proj_b | Beta/write strength (нет аналога) |
| — | in_proj_a | Alpha/decay (нет аналога) |
| o_proj | out_proj | Output |

**Критично для LoRA fine-tuning:**
```python
TARGET_MODULES = [
    # Standard Attention (8 слоёв)
    "q_proj", "k_proj", "v_proj", "o_proj",
    # DeltaNet (24 слоя) — ОБЯЗАТЕЛЬНО!
    "in_proj_qkv", "in_proj_z", "in_proj_b", "in_proj_a", "out_proj",
    # MLP (все 32 слоя)
    "gate_proj", "up_proj", "down_proj",
]
```
- Если указать только q/k/v/o_proj → LoRA затронет ТОЛЬКО 8 из 32 слоёв (25%)!
- 75% token-mixing слоёв (DeltaNet) будут пропущены → модель почти не обучится
- В Unsloth: можно использовать `"all-linear"` как shortcut

**Отличие Qwen3.5 от Qwen3Next:**
- Qwen3.5: split projections — in_proj_qkv, in_proj_z, in_proj_b, in_proj_a
- Qwen3Next: fused projections — in_proj_qkvz (Q+K+V+gate слиты), in_proj_ba
- Нельзя путать! Разные имена параметров → LoRA конфиг несовместим

---

## Слайд 10: Сравнение методов и пайплайн

**Сводная таблица:**

| | RLHF (PPO) | DPO | KTO | GRPO/GSPO |
|-|-----------|-----|-----|-----------|
| **Модели в VRAM** | 4 (π, π_ref, r, V) | 2 (π, π_ref) | 2 (π, π_ref) | 2 (π, π_ref) |
| **Reward Model** | Да (обучаемая) | Нет (implicit) | Нет (implicit) | Нет (verifiable) |
| **Данные** | Парные предпочтения | Парные | Непарные | Промпты + verifier |
| **Exploration** | Да (sampling) | Нет (offline) | Нет (offline) | Да (G rollouts) |
| **Стабильность** | Низкая (PPO) | Высокая | Высокая | Средняя |
| **VRAM (7B)** | ~112 GB | ~56 GB | ~56 GB | ~56 GB + rollouts |
| **Лучше для** | Общий alignment | Polish/format | Dialogue style | Math/code/STEM |

**Почему 3 стадии, а не одна:**

1. **GSPO (Stage 1)** — "научить решать":
   - Exploration: модель генерирует 32 варианта, учится на лучших
   - Verifiable rewards: SymPy проверяет ответы автоматически
   - Нельзя заменить DPO/KTO: они offline (нет exploration)

2. **KTO (Stage 2)** — "научить вести диалог":
   - Непарные данные из реальных Сократических диалогов
   - Prospect theory: модель сильнее штрафуется за плохие диалоги
   - Нельзя заменить GSPO: нет verifiable reward для "качества диалога"

3. **DPO (Stage 3)** — "отполировать":
   - Парные данные: лучший vs худший формат ответа
   - Минимальные изменения (β=0.1, 200 шагов)
   - Нельзя использовать первым: нет данных для пар без GSPO

**Qwen3.5-9B — почему именно эта модель:**
- 128K контекст → длинные диалоги с учеником
- Thinking mode → модель "думает" перед ответом (Chain-of-Thought)
- DeltaNet → быстрый inference на длинных последовательностях
- 9B параметров → влезает на A100 80GB для training
- Instruct → не нужен SFT, можно сразу RL
- bf16 → нет потери качества от квантизации при обучении
