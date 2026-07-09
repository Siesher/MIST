# Детальное описание технологий GSPO-пайплайна

> Технический справочник для дипломной работы: математические формулировки,
> мотивация выбора, взаимодействия между техниками и детали реализации.

**Стадия:** 1 из 4 (GSPO → RAFT++ → AdaSTaR → DPO)
**Ноутбук:** `notebooks/grpo_qwen3_4b.ipynb`
**Аппаратура:** Google Colab A100 80GB

---

## Содержание

1. [Общая архитектура GSPO-стадии](#1-общая-архитектура-gspo-стадии)
2. [GSPO: Sequence-level Importance Sampling](#2-gspo-sequence-level-importance-sampling)
3. [Dr. GRPO: Constant Length Normalization](#3-dr-grpo-constant-length-normalization)
4. [ReDit: Reward Dithering](#4-redit-reward-dithering)
5. [GDPO: Decoupled Reward Normalization](#5-gdpo-decoupled-reward-normalization)
6. [GRPO-LEAD: Curriculum Learning с Difficulty Reweighting](#6-grpo-lead-curriculum-learning)
7. [Zero-variance Masking](#7-zero-variance-masking)
8. [Clip-Higher: Asymmetric Clipping](#8-clip-higher-asymmetric-clipping)
9. [DRPO: No Negative Reward Penalties](#9-drpo-no-negative-reward-penalties)
10. [Lion Optimizer](#10-lion-optimizer)
11. [Verifiable Rewards: Система верификации ответов](#11-verifiable-rewards)
12. [Взаимодействия между техниками](#12-взаимодействия-между-техниками)
13. [Двухстадийное обучение (Curriculum)](#13-двухстадийное-обучение)
14. [Инфраструктура: Unsloth-патчи и Colab Recovery](#14-инфраструктура)
15. [Сводная таблица гиперпараметров](#15-сводная-таблица-гиперпараметров)
16. [Ссылки](#16-ссылки)

---

## 1. Общая архитектура GSPO-стадии

### 1.1 Цикл обучения

На каждом шаге GSPO-тренировки выполняется следующий цикл:

```
Для каждого промпта x из датасета:
  1. Модель πθ генерирует G = 16 completions {y₁, ..., y₁₆}
  2. Каждый completion оценивается двумя reward-функциями:
     - Correctness reward r_c(x, yᵢ) ∈ {0, 1} → + ReDit dithering
     - Format reward r_f(x, yᵢ) ∈ [0, 1]
  3. GDPO: rewards нормализуются независимо, затем агрегируются с весами [0.8, 0.2]
  4. GRPO-LEAD: advantage умножается на difficulty weight (easy=0.5, medium=1.0, hard=2.0)
  5. Zero-variance masking: если все 16 completions получили одинаковый reward → пропуск
  6. Policy update через clipped surrogate loss с sequence-level IS (GSPO)
     и Dr. GRPO length normalization
```

### 1.2 Почему не нужна Reward Model

В отличие от классического RLHF (PPO + neural reward model), данный подход
использует **верифицируемые награды** (verifiable rewards):

- **RLHF:** Требует обученную reward model `r_φ(x, y)` — нейросеть, аппроксимирующую
  человеческие предпочтения. Дорого, нестабильно, подвержена reward hacking.
- **Наш подход:** Бинарная верификация: `r(x, y) = 1` если ответ правильный, `0` иначе.
  Верификация через SymPy (символьное сравнение), exact match (MC-задачи), ChemPy (химия).

Это возможно потому, что STEM-задачи имеют **объективно проверяемые ответы** —
числовое значение, формула или буква варианта. Для open-ended задач (эссе, диалог)
верифицируемые награды не применимы, и необходима neural RM.

### 1.3 Базовая модель и LoRA

| Параметр | Значение | Обоснование |
|----------|---------|-------------|
| Базовая модель | Qwen3-4B-Instruct-2507 | Instruct-версия уже имеет dialogue abilities; SFT-стадия удалена |
| Квантизация | 4-bit QLoRA (bitsandbytes NF4) | Помещается в A100 с G=16 completions + IS double-pass |
| LoRA rank | r=16, α=32 | Баланс ёмкости и стабильности; rank ratio α/r = 2 |
| Target modules | q,k,v,o,gate,up,down_proj | Все attention + MLP проекции (7 модулей) |
| Trainable params | 33M / 4.06B (0.81%) | Достаточно для domain adaptation |
| max_seq_length | 2048 | Потолок RoPE; headroom 768 над prompt+completion (1280) |

---

## 2. GSPO: Sequence-level Importance Sampling

**Источник:** [arXiv:2507.18071](https://arxiv.org/abs/2507.18071) (Qwen Team)

### 2.1 Проблема token-level IS

В стандартном GRPO [arXiv:2402.03300] importance sampling ratio вычисляется
на уровне отдельных токенов:

```
ρₜ = πθ(yₜ | x, y<ₜ) / πθ_old(yₜ | x, y<ₜ)
```

Лосс-функция:

```
L_GRPO = -1/|y| Σₜ min(ρₜ · Âᵢ, clip(ρₜ, 1-ε, 1+ε) · Âᵢ)
```

**Проблема:** Произведение token-level ratios по длине последовательности имеет
экспоненциально растущую дисперсию. Для длинных completions (500+ токенов)
дисперсия настолько велика, что обучение становится нестабильным.

### 2.2 Решение GSPO

GSPO вычисляет importance ratio на уровне всей последовательности, нормализованный
по длине:

```
sᵢ(θ) = exp(1/|yᵢ| · Σₜ log(πθ(yᵢ,ₜ | x, yᵢ,<ₜ) / πθ_old(yᵢ,ₜ | x, yᵢ,<ₜ)))
```

Это среднее геометрическое token-level ratios. Нормализация по длине `1/|yᵢ|`
приводит ratio к единой числовой шкале независимо от длины completion.

Лосс-функция GSPO:

```
L_GSPO = -1/G · Σᵢ min(sᵢ(θ) · Âᵢ, clip(sᵢ(θ), 1-ε, 1+ε) · Âᵢ)
```

### 2.3 Критический момент: масштаб ε

Sequence-level ratio `sᵢ(θ)` имеет значительно меньшую дисперсию, чем token-level.
Поэтому **ε должен быть на 2-3 порядка меньше**:

| Уровень IS | ε (типичное) | ε_high | Масштаб |
|-----------|-------------|--------|---------|
| Token-level (GRPO/DAPO) | 0.2 | 0.28 | 10⁻¹ |
| Sequence-level (GSPO) | **3×10⁻⁴** | **4×10⁻⁴** | 10⁻⁴ |

При ε = 3×10⁻⁴ ratio клэмпится в диапазон [0.9997, 1.0004] — это означает,
что policy update крайне консервативный на каждом шаге. Это фундаментальное
свойство GSPO: много мелких, но стабильных шагов вместо редких крупных.

### 2.4 Реализация

```python
# GRPOConfig
importance_sampling_level = "sequence"  # GSPO
epsilon = 3e-4                          # GSPO paper §5.1
epsilon_high = 4e-4                     # Clip-Higher (asymmetric)
```

**Технический нюанс:** TRL issue #3823 выявил broadcasting bug при
`importance_sampling_level="sequence"`: тензор `per_token_loss` имеет shape (B,1),
а `completion_mask` — shape (B,T). При broadcasting (B,1)×(B,T) = (B,T), но
это создаёт непреднамеренное скалирование. В текущей версии TRL/Unsloth баг
исправлен через `loss_type="dr_grpo"`.

---

## 3. Dr. GRPO: Constant Length Normalization

**Источник:** [arXiv:2503.20783](https://arxiv.org/abs/2503.20783)

### 3.1 Проблема length bias

Стандартный GRPO нормализует лосс на длину конкретного completion:

```
L_standard = 1/|yᵢ| · Σₜ log πθ(yₜ | x, y<ₜ) · Âᵢ
```

Это создаёт bias: модель предпочитает короткие ответы, потому что их потери
per-token выше. Длинный правильный ответ с детальными объяснениями получает
**меньший градиент** чем короткий правильный ответ.

### 3.2 Решение

Dr. GRPO заменяет `1/|yᵢ|` на константу `1/C`, где `C = max_completion_length`:

```
L_Dr.GRPO = 1/C · Σₜ log πθ(yₜ | x, y<ₜ) · Âᵢ
```

Теперь **все completions нормализованы одинаково** независимо от длины.
Длинные пошаговые решения получают справедливый градиент.

### 3.3 Значение для STEM-репетитора

Это критически важно для нашей задачи:
- STEM-решения требуют пошаговых объяснений (200-500 токенов)
- Без Dr. GRPO модель склоняется к коротким ответам "42" без объяснений
- С Dr. GRPO длинное `"Шаг 1: ... Шаг 2: ... \boxed{42}"` и короткое `"\boxed{42}"`
  получают сопоставимые градиенты

### 3.4 Реализация

```python
loss_type = "dr_grpo"  # Unsloth compiled loss
```

`loss_type="dr_grpo"` в Unsloth/TRL активирует constant length normalization.
Альтернатива `loss_type="sapo"` (SAPO, Qwen-native) заблокирована в Unsloth's
compiled kernels и вызывает runtime error.

---

## 4. ReDit: Reward Dithering

**Источник:** [arXiv:2506.18631](https://arxiv.org/abs/2506.18631)

### 4.1 Проблема бинарных наград

При верифицируемых rewards награда бинарная: `r ∈ {0, 1}`. Для группы G completions
это создаёт три сценария:

| Сценарий | Rewards | Advantage | Проблема |
|----------|---------|-----------|----------|
| Все правильные | [1,1,...,1] | [0,0,...,0] | Zero gradient |
| Все неправильные | [0,0,...,0] | [0,0,...,0] | Zero gradient |
| Смешанные | [1,0,1,0,...] | [-1,+1,...] | Нормальный gradient |

В сценариях 1 и 2 все completions получают одинаковую награду → advantage = 0 →
нет обучающего сигнала. Это **gradient anomaly** — потеря информации о качестве
отдельных completions внутри группы.

### 4.2 Решение: Gaussian Dithering

ReDit добавляет гауссовский шум к каждой награде:

```
r̃ᵢ = rᵢ + εᵢ,   εᵢ ~ N(0, σ²)
```

Теперь даже для группы "все правильные" [1,1,...,1]:
```
r̃ = [1.03, 0.97, 1.05, 0.98, ...]
```

Advantage ≠ 0, создаётся **исследовательский градиент** (exploratory gradient):
модель слегка усиливает completions с r̃ > mean и ослабляет с r̃ < mean.

### 4.3 Математическое обоснование

Ожидание дитеринг-наград совпадает с оригинальными:
```
E[r̃ᵢ] = E[rᵢ + εᵢ] = rᵢ + E[εᵢ] = rᵢ + 0 = rᵢ
```

Дисперсия увеличивается, но контролируемо:
```
Var(r̃ᵢ) = Var(rᵢ) + σ²
```

Это эквивалентно стохастической регуляризации — модель обучается на слегка
зашумлённом, но несмещённом сигнале.

### 4.4 Выбор σ

Paper ReDit рекомендует: для uniform dithering с амплитудой `a`, оптимум `a = 0.05`,
что соответствует `σ = a/√3 ≈ 0.029` для Gaussian.

В нашей реализации используется `σ = 0.05` (чуть выше оптимума, но в пределах
стабильной области). Авторы показывают, что ReDit ускоряет сходимость в **10×**
(1000 шагов vs 9000 для vanilla GRPO).

### 4.5 Реализация

```python
DITHERING_SIGMA = 0.05

def correctness_reward(completions, prompts):
    rewards = [verify(c, p) for c, p in zip(completions, prompts)]  # {0, 1}
    noise = np.random.normal(0.0, DITHERING_SIGMA, size=len(rewards))
    return [r + n for r, n in zip(rewards, noise)]
```

---

## 5. GDPO: Decoupled Reward Normalization

**Источник:** [arXiv:2601.05242](https://arxiv.org/abs/2601.05242) (NVIDIA)

### 5.1 Проблема совместной нормализации

При нескольких reward-функциях (correctness + format) стандартный GRPO
нормализует **сумму** наград:

```
R_total = w₁·r_correctness + w₂·r_format
Â = (R_total - mean(R_total)) / std(R_total)
```

**Проблема:** Разные комбинации (correctness=1, format=0) и (correctness=0, format=1)
могут дать одинаковый R_total, но имеют принципиально разную семантику.
После нормализации различие теряется.

### 5.2 Трёхшаговый алгоритм GDPO

**Шаг 1: Независимая нормализация каждой reward-функции внутри группы**
```
Â_correctness,ᵢ = (r_c,ᵢ - mean_group(r_c)) / std_group(r_c)
Â_format,ᵢ = (r_f,ᵢ - mean_group(r_f)) / std_group(r_f)
```

**Шаг 2: Взвешенная агрегация**
```
Â_multi,ᵢ = w₁ · Â_correctness,ᵢ + w₂ · Â_format,ᵢ
```

**Шаг 3: Batch-wise нормализация (опциональная)**
```
Â_final,ᵢ = (Â_multi,ᵢ - mean_batch(Â_multi)) / std_batch(Â_multi)
```

### 5.3 Зачем независимая нормализация

Рассмотрим группу из 4 completions:

| Completion | Correctness | Format | Стандартная Â | GDPO Â |
|-----------|-------------|--------|--------------|--------|
| A | 1 | 0.3 | +0.5 | +0.6 |
| B | 1 | 0.9 | +0.8 | +1.2 |
| C | 0 | 0.9 | -0.1 | -0.4 |
| D | 0 | 0.3 | -1.2 | -1.4 |

GDPO корректно ранжирует: B > A > C > D. Стандартный подход может спутать
C (неправильный, но красиво оформлен) с A (правильный, но плохой формат).

### 5.4 Реализация

```python
reward_weights = [0.8, 0.2]  # correctness : format

# TRL GRPOTrainer принимает список reward-функций
reward_funcs = [correctness_fn, format_fn]
```

TRL/Unsloth реализует GDPO через параметр `reward_weights` в GRPOConfig.
Каждая reward-функция нормализуется независимо внутри группы, затем комбинируется
с указанными весами.

---

## 6. GRPO-LEAD: Curriculum Learning

**Источник:** [arXiv:2504.09696](https://arxiv.org/abs/2504.09696)

### 6.1 Мотивация

Равномерная выборка задач неэффективна:
- **Лёгкие задачи:** Модель быстро достигает 90%+ → advantage ≈ 0, нет обучения
- **Сложные задачи:** Модель на 5% → все completions неправильные → advantage ≈ 0
- **Средние задачи:** Максимальная дисперсия, максимальный обучающий сигнал

### 6.2 Difficulty-aware Advantage Reweighting

GRPO-LEAD присваивает вес каждой задаче на основе её сложности:

```
Â_weighted,ᵢ = w(difficulty) · Âᵢ
```

Оригинальная формулировка GRPO-LEAD использует непрерывную логистическую функцию:
```
w(ρ) = A + B / (1 + exp(k · (ρ - ρ₀)))
```
где ρ — эмпирический pass rate.

Наша реализация упрощает до дискретных весов (определяются при подготовке данных):

| Сложность | Вес | Обоснование |
|-----------|-----|-------------|
| Easy (pass rate > 80%) | 0.5 | Мало нового, снижаем влияние |
| Medium (20-80%) | 1.0 | Максимальный обучающий сигнал |
| Hard (< 20%) | 2.0 | Ценные, но редкие правильные решения усилены |

### 6.3 Двухстадийный curriculum

| Стадия | Шаги | Задачи | Оптимизатор | Rationale |
|--------|------|--------|-------------|-----------|
| Stage 1 | 200 | Easy + Medium (10619) | AdamW | Стабилизация policy на решаемых задачах |
| Stage 2 | 400 | All (14203) | Lion | Расширение на hard с усиленным весом |

Stage 1 не включает hard-задачи, потому что на ранних шагах модель не может
решить их → все 16 completions неправильные → нулевой advantage → wasted compute.
После 200 шагов на easy+medium модель достаточно сильна, чтобы решать ~20% hard-задач,
что даёт ненулевой градиент.

### 6.4 Реализация

```python
CURRICULUM_CONFIG = {
    "stage1_steps": 200,   # easy + medium only
    "stage2_steps": 400,   # all difficulties
    "difficulty_weights": {"easy": 0.5, "medium": 1.0, "hard": 2.0},
}

def difficulty_weighted_correctness(completions, prompts):
    rewards = base_correctness(completions, prompts)
    for i, prompt in enumerate(prompts):
        problem = lookup(prompt)
        weight = DIFFICULTY_WEIGHTS[problem.difficulty]
        rewards[i] *= weight
    return rewards
```

---

## 7. Zero-variance Masking

**Источник:** [arXiv:2505.22257](https://arxiv.org/abs/2505.22257)

### 7.1 Концепция

Если все G completions для промпта получили одинаковую награду:
```
std({r₁, r₂, ..., r_G}) = 0
```

то advantage для каждого completion = 0, и group не несёт обучающего сигнала.
Вычисление forward + backward pass для такой группы — потеря ~6% compute.

Zero-variance masking детектирует такие группы и возвращает NaN, что заставляет
TRL пропустить их в loss computation.

### 7.2 Взаимодействие с ReDit

**Важный нюанс:** ReDit dithering добавляет шум σ=0.05 к каждой награде.
Это делает **точный** zero-variance невозможным — даже для группы [1,1,...,1]
после дитеринга будет [1.03, 0.97, ...] со std ≈ 0.05.

Решение: пороговое значение вместо exact zero:
```python
if std(group_rewards) < 1e-6:  # порог, а не == 0
    mask_group_as_nan()
```

**Практический результат:** При обучении Stage 1 (200 шагов) было замаскировано
**0 из 152 групп** — ReDit дитеринг эффективно предотвращает zero-variance.
Маскирование остаётся как safety net для edge cases (например, если все completions
обрезаны по max_length → `mask_truncated_completions=True` уже удалил их).

### 7.3 Реализация

```python
def zero_variance_masked_correctness(completions, prompts):
    rewards = difficulty_weighted_correctness(completions, prompts)
    for group in group_by_prompt(rewards):
        if np.std(group.rewards) < 1e-6:
            group.rewards = [float('nan')] * len(group)
    return rewards
```

---

## 8. Clip-Higher: Asymmetric Clipping

**Источник:** DAPO [arXiv:2503.14476](https://arxiv.org/abs/2503.14476),
VAPO [arXiv:2504.05118](https://arxiv.org/abs/2504.05118)

### 8.1 Проблема симметричного клиппинга

Стандартный PPO/GRPO использует симметричный клип:
```
clip(ρ, 1-ε, 1+ε)  →  clip(ρ, 0.8, 1.2) при ε=0.2
```

Для **хороших** completions (Â > 0) мы хотим увеличить их вероятность.
Для **плохих** completions (Â < 0) — уменьшить.

Но симметричный клип одинаково ограничивает оба направления.
Для низковероятных "exploration tokens" это создаёт **entropy collapse**:
модель не может достаточно усилить редкие, но правильные стратегии решения.

### 8.2 Решение: Clip-Higher

Асимметричные границы:
```
clip(ρ, 1-ε_low, 1+ε_high)

где ε_low = 3×10⁻⁴,  ε_high = 4×10⁻⁴  (для sequence-level IS)
```

ε_high > ε_low означает: **усиление хороших completions** допускается чуть сильнее,
чем **подавление плохих**. Это поддерживает exploration diversity.

### 8.3 Масштабирование под GSPO

Оригинальные значения DAPO/VAPO (ε_low=0.2, ε_high=0.28) предназначены для
token-level IS. При sequence-level IS (GSPO) они масштабируются пропорционально:

```
Token-level:    ε = 0.2,   ε_high = 0.28   (ratio: 1.4)
Sequence-level: ε = 3e-4,  ε_high = 4e-4   (ratio: 1.33)
```

Ratio сохраняется ~1.3-1.4×, обеспечивая аналогичный exploration bias.

### 8.4 Реализация

```python
epsilon = 3e-4        # GRPOConfig.epsilon
epsilon_high = 4e-4   # GRPOConfig.epsilon_high
```

---

## 9. DRPO: No Negative Reward Penalties

**Источник:** [arXiv:2510.04474](https://arxiv.org/abs/2510.04474)

### 9.1 Проблема отрицательных наград

Некоторые reward-схемы используют отрицательные награды за неправильные ответы:
```
r(y) = +1 если правильно, -1 если неправильно
```

Это создаёт нежелательный эффект: при нормализации advantage в группе,
неправильные ответы с r=-1 сильно "тянут" среднее вниз, что может дать
**положительный** advantage для ответа, который правильный, но слишком длинный.

### 9.2 Решение: только неотрицательные награды

```
r_correctness(y) = 1.0 если правильно
                   0.0 если неправильно
```

Преимущества:
- Advantage для неправильных completions всегда ≤ 0 (подавляются)
- Нет путаницы между "плохой формат" и "неправильный ответ"
- Совместимо с ReDit dithering (шум не уводит reward в сильно отрицательную область)

### 9.3 Реализация

```python
def verify_answer(completion, ground_truth, domain):
    # Бинарная верификация: {0.0, 1.0}
    if is_correct(completion, ground_truth, domain):
        return 1.0
    return 0.0  # НЕ -1.0!
```

---

## 10. Lion Optimizer

**Источник:** [arXiv:2302.06675](https://arxiv.org/abs/2302.06675) (Google Brain)

### 10.1 Мотивация

AdamW хранит два состояния: первый момент (m) и второй момент (v),
что требует 2× память параметров для состояния оптимизатора.

Lion (EvoLved Sign Momentum) найден через программный поиск оптимизаторов
и использует **только один момент** + операцию **sign()**.

### 10.2 Алгоритм

```
Вход: параметры θ, градиент g, momentum m, learning rate γ, weight decay λ

1. u = β₁ · m + (1 - β₁) · g       # Комбинация momentum + gradient (для update)
2. θ = θ - γ · (sign(u) + λ · θ)    # Update: sign() + decoupled weight decay
3. m = β₂ · m + (1 - β₂) · g       # Обновление momentum (для следующего шага)
```

Где:
- `β₁ = 0.9` (update momentum — короткая память)
- `β₂ = 0.99` (tracking momentum — длинная память)
- `sign(u)` — поэлементный знак (∈ {-1, 0, +1})

### 10.3 Ключевые свойства

1. **Единообразная магнитуда update:** `sign()` даёт ±1 для каждого параметра →
   все параметры обновляются на одинаковую величину `γ`. Нет проблемы
   "малые градиенты → малые обновления" как в AdamW.

2. **33% меньше памяти:** Один момент вместо двух. Для 4B модели с LoRA (33M params):
   - AdamW: 33M × 2 × 4 bytes = 264 MB состояния
   - Lion: 33M × 1 × 4 bytes = 132 MB состояния

3. **Robustifier для heavy-tailed градиентов:** RL-обучение создаёт выбросы в
   градиентах (reward spikes, long sequences). `sign()` ограничивает влияние выбросов
   до ±1, что является естественной формой gradient clipping.

4. **Неявная регуляризация:** Uniform-magnitude updates создают эффект, аналогичный
   SignSGD — модель исследует пространство параметров более равномерно.

### 10.4 Отличия от AdamW: требуемые изменения гиперпараметров

| Параметр | AdamW (Stage 1) | Lion (Stage 2) | Ratio | Обоснование |
|----------|----------------|----------------|-------|-------------|
| Learning rate | 1×10⁻⁶ | 3×10⁻⁷ | 0.3× | sign() даёт бо́льшую эффективную update norm |
| Weight decay | 0.1 | 0.3 | 3× | Компенсирует меньший LR; Lion paper рекомендует 3-10× |
| adam_beta2 | 0.99 | — (нет) | — | Lion не использует второй момент |

**Почему LR меньше:** В AdamW update ∝ m/√v, что может быть << 1. В Lion update = sign(u) = ±1.
При одинаковом LR, Lion делает значительно бо́льшие шаги → нужен меньший LR.

### 10.5 Реализация

```python
STAGE2_OPTIMIZER = "lion_8bit"       # bitsandbytes 8-bit Lion
STAGE2_LEARNING_RATE = 3e-7          # 3× smaller than AdamW
STAGE2_WEIGHT_DECAY = 0.3            # 3× larger than AdamW
```

Допустимые имена в Transformers: `lion_8bit`, `lion_32bit`, `paged_lion_8bit`,
`paged_lion_32bit`. Имя `lion_bnb_8bit` (как в bitsandbytes docs) **не** является
валидным OptimizerNames enum.

---

## 11. Verifiable Rewards: Система верификации ответов

### 11.1 Архитектура reward pipeline

```
Completion text
    │
    ├── Extract answer:
    │     ├── \boxed{...} → SymPy parse
    │     ├── MC letter (A/B/C/D) → regex match
    │     └── Numeric → float parse
    │
    ├── Verify:
    │     ├── Math: SymPy simplify(pred - gold) == 0
    │     ├── Physics: |pred - gold| / |gold| < 0.05 (5% tolerance)
    │     ├── Chemistry: ChemPy validation
    │     ├── MC: exact match (case-insensitive)
    │     └── Numeric: exact or float comparison
    │
    ├── Correctness reward: 1.0 (correct) / 0.0 (incorrect)
    │
    ├── ReDit dithering: + N(0, 0.05²)
    │
    ├── Difficulty weighting: × {0.5, 1.0, 2.0}
    │
    └── Zero-variance masking: NaN if all-same

Format reward (independent):
    ├── \boxed{} present: +0.5 (calc) / answer format: +0.5 (MC)
    ├── Step markers: +0.3
    └── Length 50-800 words: +0.2
```

### 11.2 Доменные верификаторы

| Домен | Метод верификации | Tolerance | Пример |
|-------|-------------------|-----------|--------|
| Математика | SymPy symbolic equality | Exact | `simplify(x² + 2x + 1 - (x+1)²) == 0` |
| Физика | Numeric relative error | 5% | `|9.78 - 9.81| / 9.81 = 0.3%` ✓ |
| Химия | ChemPy formula validation | Exact | `H₂O == H₂O` ✓ |
| Биология | String match (MC) | Exact | `B == B` ✓ |
| Информатика | String match (MC) | Exact | `C == C` ✓ |

### 11.3 Датасет

| Источник | Количество | Тип | Домен |
|----------|-----------|-----|-------|
| GSM8K | 7,400 | numeric | math |
| MATH (Hendrycks) | 4,985 | latex_boxed | math |
| ruMMLU STEM | 1,495 | mc_letter | bio, chem, cs, phys |
| OlympiadBench | 232 | numeric_with_unit | physics |
| Custom (LLM-generated) | 91 | numeric | all |
| **Total** | **14,203** | | |

Разбиение: 90% train (12,783), 10% eval (1,420) — стратифицированно по домену.

---

## 12. Взаимодействия между техниками

### 12.1 Синергии

| Техника A | Техника B | Взаимодействие |
|-----------|-----------|---------------|
| GSPO (seq-level IS) | Dr. GRPO (constant norm) | Оба уменьшают length bias — взаимно усиливают |
| ReDit (dithering) | GDPO (decoupled norm) | Dithering создаёт дисперсию → GDPO нормализация работает лучше |
| GRPO-LEAD (curriculum) | Zero-var masking | На Stage 1 easy-задачи часто "все правильно" → masking экономит compute |
| Clip-Higher | GSPO | Асимметрия сохраняет exploration при крайне малых ε |
| DRPO (no neg) | ReDit | Шум не уводит reward в сильно отрицательную зону |

### 12.2 Конфликты

| Техника A | Техника B | Конфликт | Решение |
|-----------|-----------|----------|---------|
| ReDit (σ=0.05) | Zero-var masking | Шум делает exact zero std невозможным | Порог 1e-6 вместо == 0 |
| GSPO (ε=3e-4) | Clip-Higher (ε_high=4e-4) | Очень узкий clip → почти нет разницы | Принято как design choice |

### 12.3 Порядок применения reward transformations

```
1. Base correctness: verify(completion, answer) → {0, 1}
2. ReDit dithering: + N(0, σ²) → ℝ
3. Difficulty weighting: × {0.5, 1.0, 2.0} → ℝ
4. Zero-variance masking: → ℝ or NaN
5. GDPO group normalization → advantage Â
6. Reward weights aggregation: 0.8·Â_correctness + 0.2·Â_format
7. GSPO clipped surrogate loss с sequence-level IS
8. Dr. GRPO constant length normalization
```

---

## 13. Двухстадийное обучение

### 13.1 Stage 1: Warm-up (AdamW)

| Параметр | Значение |
|----------|---------|
| Шаги | 200 |
| Задачи | Easy + Medium (10,619) |
| Оптимизатор | adamw_torch_fused |
| LR | 1×10⁻⁶ |
| Weight decay | 0.1 |
| adam_beta2 | 0.99 |
| Warmup | 10% (20 шагов) |

**Наблюдения из Stage 1:**
- Correctness reward: 0.58 → 0.86 (пик step 180)
- Format reward: стабильно 0.88-0.99
- Один loss spike на step 145 (905K) — вызван длинной последовательностью,
  не повторился после увеличения `max_seq_length` с 1280 до 2048

### 13.2 Stage 2: Full curriculum (Lion)

| Параметр | Значение |
|----------|---------|
| Шаги | 400 |
| Задачи | All (12,785 — easy+medium+hard) |
| Оптимизатор | lion_8bit |
| LR | 3×10⁻⁷ |
| Weight decay | 0.3 |
| Warmup | 8% (32 шага) |

**Наблюдения из Stage 2 (в процессе):**
- Correctness reward: осциллирует 0.3-1.0 (нормально для mixed difficulty)
- Пики > 1.0 (step 30: 1.067, step 95: 1.058) — hard-задачи с весом 2×
- Clipped ratio: 0-50%, выше при hard-батчах
- Стабильная тренировка, без spikes

### 13.3 Post-audit гиперпараметры

По результатам аудита статей (DeepSeek-Math, VAPO, GSPO docs) были внесены
три исправления:

| Параметр | Было | Стало | Источник |
|----------|------|-------|----------|
| max_grad_norm | 1.0 | **0.1** | Unsloth GSPO docs |
| weight_decay | 0 (default) | **0.1** | DeepSeek-Math, VAPO |
| adam_beta2 | 0.999 (default) | **0.99** | Быстрая адаптация второго момента |

---

## 14. Инфраструктура

### 14.1 Unsloth compatibility patches

Unsloth оптимизирует TRL's GRPOTrainer через torch.compile, что создаёт
несовместимости с Qwen3 tokenizer. Применены 4 идемпотентных патча:

| # | Патч | Проблема | Решение |
|---|------|----------|---------|
| 1 | `has_images` | Unsloth ожидает глобальную переменную | Inject `has_images=False` |
| 2 | `batch_decode` | Token IDs > vocab_size после генерации | Clamp к [0, 151936) |
| 3 | `embed_tokens` | OOV tokens → IndexError в embedding | Clamp input tensor |
| 4 | `gen_score` | Невалидные IDs в completion tensors | Replace с pad_token_id |

### 14.2 Max sequence length fix

**Проблема:** `max_seq_length = MAX_PROMPT_LENGTH + MAX_COMPLETION = 512 + 768 = 1280`.
Некоторые промпты после chat template tokenization > 512 токенов. TRL truncation
применяется **после** tokenization, но Unsloth's compiled loss использует
`max_seq_length` для внутренних буферов. При input_ids=1857 > 1280, `torch.gather`
получает shape mismatch → crash.

**Решение:** Разделить `max_seq_length` (модельный потолок) от
`max_prompt_length + max_completion` (TRL generation control):

```python
MAX_SEQ_LENGTH = 2048       # Model ceiling (RoPE, attention buffers)
MAX_PROMPT_LENGTH = 512     # TRL truncation control
MAX_COMPLETION = 768        # Generation limit
# Headroom: 2048 - 512 - 768 = 768 tokens safety margin
```

С flash attention реальная VRAM зависит от фактических длин, а не от потолка.

### 14.3 Colab disconnect recovery

```python
def find_latest_checkpoint(output_dir):
    """Находит последний checkpoint с совместимым LoRA rank."""
    checkpoints = sorted(glob("checkpoint-*"), key=step_number, reverse=True)
    for ckpt in checkpoints:
        if ckpt.adapter_config.r == current_LORA_R:
            return ckpt  # Совместимый — resume
        else:
            skip  # Несовместимый LoRA rank — пропустить
    return None

trainer.train(resume_from_checkpoint=find_latest_checkpoint(stage_dir))
```

---

## 15. Сводная таблица гиперпараметров

| Группа | Параметр | Значение | Источник |
|--------|----------|---------|----------|
| **GSPO** | importance_sampling_level | sequence | arXiv:2507.18071 |
| | epsilon | 3×10⁻⁴ | arXiv:2507.18071 §5.1 |
| | epsilon_high | 4×10⁻⁴ | DAPO/VAPO scaled |
| | beta | 0.0 | GSPO/DAPO standard |
| **Dr. GRPO** | loss_type | dr_grpo | arXiv:2503.20783 |
| **ReDit** | dithering_sigma | 0.05 | arXiv:2506.18631 |
| **GDPO** | reward_weights | [0.8, 0.2] | arXiv:2601.05242 |
| **GRPO-LEAD** | difficulty_weights | {e:0.5, m:1.0, h:2.0} | arXiv:2504.09696 |
| **Training** | G (completions) | 16 | GSPO paper |
| | max_completion | 768 | A100 VRAM constraint |
| | max_prompt_length | 512 | TRL truncation |
| | max_seq_length | 2048 | Model ceiling (headroom fix) |
| | grad_accum | 2 | Effective batch = 32 |
| | steps_per_generation | 8 | 4 optimizer updates/rollout |
| | save_steps | 25 | ~25 min recovery points |
| **Stage 1** | optimizer | adamw_torch_fused | Standard |
| | learning_rate | 1×10⁻⁶ | DeepSeek-Math consensus |
| | weight_decay | 0.1 | Post-audit fix |
| | adam_beta2 | 0.99 | Post-audit fix |
| | max_grad_norm | 0.1 | Unsloth GSPO docs |
| | warmup_ratio | 0.10 | |
| | steps | 200 | Easy+medium warm-up |
| **Stage 2** | optimizer | lion_8bit | arXiv:2302.06675 |
| | learning_rate | 3×10⁻⁷ | Lion: 3× smaller |
| | weight_decay | 0.3 | Lion: 3× larger |
| | max_grad_norm | 0.1 | Same |
| | warmup_ratio | 0.08 | Longer for hard problems |
| | steps | 400 | Full curriculum |
| **LoRA** | r | 16 | |
| | alpha | 32 | Rank ratio = 2 |
| | dropout | 0.0 | Standard for RL |
| | targets | q,k,v,o,gate,up,down | All attention + MLP |

---

## 16. Ссылки

### Основные алгоритмы

| # | Метод | Ссылка | Применение |
|---|-------|--------|-----------|
| 1 | GSPO | [arXiv:2507.18071](https://arxiv.org/abs/2507.18071) | Sequence-level IS |
| 2 | GRPO | [arXiv:2402.03300](https://arxiv.org/abs/2402.03300) | Group-relative advantages |
| 3 | Dr. GRPO | [arXiv:2503.20783](https://arxiv.org/abs/2503.20783) | Length normalization |
| 4 | DAPO | [arXiv:2503.14476](https://arxiv.org/abs/2503.14476) | Clip-Higher |
| 5 | VAPO | [arXiv:2504.05118](https://arxiv.org/abs/2504.05118) | Epsilon bounds |
| 6 | ReDit | [arXiv:2506.18631](https://arxiv.org/abs/2506.18631) | Reward dithering |
| 7 | GDPO | [arXiv:2601.05242](https://arxiv.org/abs/2601.05242) | Decoupled rewards |
| 8 | GRPO-LEAD | [arXiv:2504.09696](https://arxiv.org/abs/2504.09696) | Curriculum RL |
| 9 | Revisiting GRPO | [arXiv:2505.22257](https://arxiv.org/abs/2505.22257) | Zero-variance masking |
| 10 | DRPO | [arXiv:2510.04474](https://arxiv.org/abs/2510.04474) | No negative penalties |
| 11 | Lion | [arXiv:2302.06675](https://arxiv.org/abs/2302.06675) | Sign-based optimizer |

### Базовая модель

| Ресурс | Ссылка |
|--------|--------|
| Qwen3 Technical Report | [arXiv:2505.09388](https://arxiv.org/abs/2505.09388) |
| Qwen3 GSPO Blog | [qwenlm.github.io/blog/gspo](https://qwenlm.github.io/blog/gspo/) |
| SAPO (Qwen loss) | [arXiv:2511.20347](https://arxiv.org/abs/2511.20347) |
| DeepSeek-Math | [arXiv:2402.03300](https://arxiv.org/abs/2402.03300) |

### Инструменты

| Инструмент | Ссылка |
|-----------|--------|
| Unsloth | [github.com/unslothai/unsloth](https://github.com/unslothai/unsloth) |
| TRL | [github.com/huggingface/trl](https://github.com/huggingface/trl) |
| PEFT | [github.com/huggingface/peft](https://github.com/huggingface/peft) |
| bitsandbytes | [github.com/bitsandbytes-foundation/bitsandbytes](https://github.com/bitsandbytes-foundation/bitsandbytes) |
| SymPy | [sympy.org](https://www.sympy.org/) |
| ChemPy | [github.com/bjodah/chempy](https://github.com/bjodah/chempy) |
