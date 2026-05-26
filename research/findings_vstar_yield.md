# V-STaR Generation Yield Analysis (Phase 1.5 hard-only)

**Дата:** 2026-05-25
**Источник:** `training/data/vstar_trajectories_hard.jsonl` (426 hard problems, N=4, 1704 траектории)
**Seed model:** mits-eval-gspo (Q4_K_M GGUF), turbo3 KV, llama-swap :8081

## n_correct distribution (bimodal)

| n_correct | problems | %      | категория        |
|-----------|----------|--------|------------------|
| 0/4       | 158      | 37.1%  | слишком сложно   |
| 1/4       | 22       | 5.2%   | usable           |
| 2/4       | 21       | 4.9%   | usable           |
| 3/4       | 22       | 5.2%   | usable           |
| 4/4       | 203      | 47.7%  | слишком легко    |

**All-or-nothing: 84.8%** (4/4 + 0/4). Within-task pairing по correctness → **usable 65/426 = 15.3%**.

## Per-domain usable (correctness-only)

| domain    | total | usable | yield |
|-----------|-------|--------|-------|
| math      | 100   | 31     | 31%   |
| cs        | 100   | 14     | 14%   |
| physics   | 100   | 11     | 11%   |
| biology   | 78    | 7      | 9%    |
| chemistry | 48    | 2      | 4%    |

## done_reason (1704 траектории)

| reason         | count | %     |
|----------------|-------|-------|
| early_boxed    | 867   | 50.9% |
| length (обрезка)| 807  | 47.4% |
| stop           | 26    | 1.5%  |
| wallclock_cap  | 4     | 0.2%  |

## Ключевые выводы

1. **15.3% — это floor (correctness-only), не потолок.** Composite scorer
   (`correctness×0.5 + PRM×0.3 + no_spoiler×0.2`) строит пары и среди 203 all-correct
   problems через вариативность PRM (reasoning quality) и no-spoiler (pedagogy).
   Composite **разблокирует** yield там, где correctness бинарна. Это аргумент за
   composite-награду в дизайне (не просто outcome DPO).

2. **Bimodal — сигнатура hard-only pivot** на фиксированном seed: модель либо умеет
   (4/4), либо нет (0/4). Ожидаемо; within-task correctness-pairing режет до ~15%.

3. **47.4% обрезок (length)** — часть 0/4 это «не закончил», не «не умеет». Поднятие
   completion budget перевело бы часть 0/4 → решённые (но уменьшило бы correctness-usable,
   т.к. стали бы 4/4). Для composite это плюс — больше валидных reasoning traces.

4. **Chemistry yield 4% (2 пары)** — слабейший домен; коррелирует с Phase 0a regression.
   Отметить в per-domain анализе диплома (Глава 4).

## Импликации для pipeline

- **Composite scorer (task #5) — критический unlock**, не повторная генерация.
- **65 correctness-пар достаточно для lean-demo** DPO (proof-of-concept).
- Для масштаба: composite-расширение 65 → ~200+ пар (4/4 кластер по PRM/pedagogy).
- Альтернативы при нехватке: ↑temperature (разнообразие) > ↑N (4/4 и 0/4 не сдвинутся).

## Trajectory structure + content availability

Каждая траектория: `thinking` (reasoning), `content` (ответ ученику), `extracted`, `tokens`,
`done_reason`, `correct`. **No-spoiler judge оценивает `content`** (что видит ученик).

- **content непустой: 56.1%** (956/1704); пустой (только thinking, обрезан): 43.9%.
- **done_reason ↔ content**: early_boxed → 100% content; length → 8%; stop → 96%; wallclock_cap → 0%.
  early_boxed = «золотые» траектории; length = rambling-обрезки без ответа.

## Pairing potential (что выжимается)

| Стратегия | Пар | PRM? |
|-----------|-----|------|
| A. correctness-mixed (1-3/4) | 65 | нет |
| B. + completeness в 4/4 (content vs обрезка) | +19 → **84** | нет |
| C. composite PRM/no-spoiler в 4/4 (≥2 content) | до +194 (верх 259) | да |

- **84 пары выжимаемо без PRM** (A+B) — достаточно для lean-demo DPO.
- **194/203 all-correct групп composite-rankable** (≥2 непустых content). Completeness-proxy (B)
  ловит лишь 19 (смесь content+обрезка); остальные 175 различимы только judge'ом (PRM качество
  reasoning + no-spoiler педагогика) — именно там PRM окупается.
- Реалистично с composite: ~130-200 пар (где judge даёт margin). B2 (40 пар из 0/4) пропускаем —
  все ответы неверны, низкое качество preference.
