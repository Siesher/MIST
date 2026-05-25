# Design: V-STaR within-task pairing (A+B, без PRM)

**Дата:** 2026-05-25
**Автор:** Сухацкий М. О. (с Claude Code)
**Ветка:** 019-ns-vstar-dpo
**Статус:** Approved design → ready for implementation plan

---

## Контекст и проблема

V-STaR generation завершена (426/426 hard problems, N=4, 1704 траектории →
`training/data/vstar_trajectories_hard.jsonl`). Анализ yield (`research/findings_vstar_yield.md`):
распределение n_correct **bimodal** (0/4: 37%, 4/4: 48%, mixed: 15%). Нужно построить DPO
preference-датасет из траекторий.

Выбран путь **A+B (без PRM)** = 84 пары, разблокирует lean-demo DPO немедленно. Полный
composite (PRM/no-spoiler, +до 194) — отдельный последующий этап поверх.

**Существующие форматы (следуем им):**
- `training/data/preference_pairs.jsonl`: `prompt=[{role,content}]`, `chosen` str, `rejected` str
- `specs/019-ns-vstar-dpo/data-model.md`: `dpo_pairs.jsonl` = `pair_id, prompt, chosen, rejected, scores_*`

## Goals

1. `scripts/build_vstar_pairs.py` → `training/data/vstar_dpo_pairs.jsonl` (~84 пары)
2. Within-task pairing (1 пара на problem — устраняет cross-task confounder)
3. Стратегии A (correctness-mixed) + B (completeness в 4/4)
4. Формат совместим с TRL DPOTrainer + 019 data-model schema

## Non-goals (YAGNI)

- PRM / no-spoiler scoring (отдельный composite-этап поверх)
- B2 (completeness в 0/4 — все ответы неверны, низкое качество)
- >1 пары на problem (cross-task confounder)
- Балансировка по доменам (берём что есть; chemistry даст ~2)

---

## Design

**Компонент:** `scripts/build_vstar_pairs.py` — идемпотентный, читает trajectories.jsonl → пишет pairs.jsonl.

**Completion scope:** `f"<think>{thinking}</think>\n{content}"` — полный completion как генерит модель.
**Обязательно** (не content-only): иначе в B-паре rejected = пустая строка (обрезанная траектория
без content) → вырожденная DPO-пара. Бонус: целит в 47% truncation — DPO учит «завершить thinking +
выдать content» > «бесконечный rambling без ответа».

**Selection logic (1 пара на problem, within-task):**
- **A — correctness-mixed (0 < n_correct < 4), 65 problems:**
  - `chosen` = correct-траектория с непустым content (приоритет `done_reason=early_boxed`)
  - `rejected` = incorrect-траектория (приоритет с непустым content для честного контраста, иначе любая incorrect)
- **B — completeness в all-correct (n_correct==4) со смесью content/обрезка, 19 problems:**
  - `chosen` = correct + непустой content
  - `rejected` = correct, но обрезанная (`content` пустой, `done_reason=length`)

**Формат записи (по 019 data-model):**
```json
{
  "pair_id": "<subset_idx>__<chosen_sample_idx>__<rejected_sample_idx>",
  "prompt": [{"role": "user", "content": "<problem prompt>"}],
  "chosen": "<think>...</think>\n<content>",
  "rejected": "<think>...</think>\n<content или пусто>",
  "domain": "math",
  "difficulty": "hard",
  "strategy": "A",
  "scores_chosen": {"correctness": 1.0, "completeness": 1.0},
  "scores_rejected": {"correctness": 0.0, "completeness": 1.0}
}
```
`completeness` = 1.0 если content непустой, иначе 0.0. Поля `prm`/`pedagogy` добавит composite-этап позже.

**prompt:** из `row['prompt']`, обёрнут в `[{"role":"user","content": ...}]` (как preference_pairs.jsonl).

---

## Verification (структурная)

`scripts/verify_vstar_pairs.py` (или inline) — re-open `vstar_dpo_pairs.jsonl`:
- всего пар ≈ 84 (A=65, B=19)
- `chosen` нигде не пустой
- каждый `pair_id` уникален
- `chosen != rejected` в каждой паре
- strategy ∈ {A, B}, разбивка 65/19
- per-domain разбивка совпадает с findings (math доминирует, chemistry ~2)
- prompt — непустой conversational list

## Open questions / риски

- Если в A-группе нет incorrect с content (все incorrect обрезаны) — rejected будет обрезанной;
  это валидно (correct+content > incorrect+обрезка), но margin смешивает correctness и completeness.
  Приемлемо для lean-demo; composite-этап позже уточнит.
- Очень длинный `thinking` (до ~14k симв.) может раздувать DPO-примеры. На этапе A+B не режем
  (сохраняем как есть); если DPOTrainer упрётся в max_length — кап добавим при тренировке.
