# Quickstart: NS-V-STaR-DPO Pipeline

**Feature**: 019-ns-vstar-dpo

Полная репродукция pipeline от honest re-eval до diploma chapter.

## Prerequisites

- Google Colab Pro+ (A100 80GB) для eval/scoring
- Lightning AI account (RTX 6000 / A100 80GB) для long-running training (DPO + ablations)
- Hugging Face account `Siesher` с push access (write token)
- Cerebras API key pool (10 keys в `.env`) на `MyDrive/MITS_secrets/.env`
- 600 vu compute budget (RTX 6000 @ 8.71/h)
- `huggingface-cli login` с write token

### .env (на Drive `MyDrive/MITS_secrets/.env`)

```bash
CEREBRAS_API_KEY_1=...
CEREBRAS_API_KEY_2=...
# ... up to _10
HF_TOKEN=hf_...
```

---

## Phase 0: Honest Re-eval *(3.6–4.5 h, ~32 vu)*

Notebook готов: [`notebooks/honest_eval_full_precision.ipynb`](../../notebooks/honest_eval_full_precision.ipynb).

```bash
# В Colab Pro+, runtime → A100 80GB
# 1. Открыть notebook из github Siesher/MITS branch 019-ns-vstar-dpo
# 2. Установить runtime → A100
# 3. Run all cells
# 4. Результат: evaluation/reports/honest_full_precision_YYYYMMDD.json
# 5. Зафиксировать seed_choice вручную:
```

После завершения T002 — выбрать seed для V-STaR (T003):

```bash
# Открыть отчёт и определить best of (base, GSPO, KTO) по composite metric:
#     composite = accuracy + 0.5 * socratic_score
# Записать выбор в specs/019-ns-vstar-dpo/seed_choice.md
```

---

## Phase 1: V-STaR Generation *(8–10 h, ~88 vu)*

```bash
# Lightning AI A100 80GB (или Colab Pro+ если уверены в session length)
uv run python training/scripts/vstar_generate.py \
    --seed-model Siesher/mits-qwen3-9b-{gspo|kto|base} \
    --tasks data/training/dialogs.jsonl \
    --N 4 \
    --temperature 0.7 \
    --num-predict 4096 \
    --enable-thinking \
    --out data/vstar/completions.jsonl

# Upload to HF dataset
huggingface-cli upload Siesher/mits-vstar-completions-N4 \
    data/vstar/completions.jsonl --repo-type dataset
```

---

## Phase 2: PRM Scoring *(4–5 h, ~40 vu)*

```bash
# Отдельная Colab/Lightning сессия (PRM 7B + tutor 9B не помещаются вместе)
uv run python training/scripts/score_completions.py \
    --component prm \
    --prm-model Qwen/Qwen2.5-Math-PRM-7B \
    --in data/vstar/completions.jsonl \
    --cache data/cache/prm_scores.json \
    --batch-size 8
```

Idempotent — пропускает already-cached entries.

---

## Phase 3: Pedagogy Scoring *(6–8 h, API only)*

```bash
uv run python training/scripts/score_completions.py \
    --component pedagogy \
    --in data/vstar/completions.jsonl \
    --cache data/cache/pedagogy_scores.json \
    --concurrent 5
```

Использует rotating pool of 10 Cerebras keys из `.env`.

---

## Phase 4: Composite + DPO Pairs *(<1 h CPU + 3 h sweep)*

### Sensitivity sweep (T015 — выбор финальных весов)

```bash
for weights in "0.5,0.25,0.25" "0.4,0.3,0.3" "0.6,0.2,0.2"; do
    uv run python training/scripts/build_dpo_dataset.py \
        --completions data/vstar/completions.jsonl \
        --prm-scores data/cache/prm_scores.json \
        --pedagogy-scores data/cache/pedagogy_scores.json \
        --weights "$weights" \
        --tau 0.15 \
        --subset-size 200 \
        --out "data/vstar/sweep/dpo_pairs_${weights}.jsonl"
done

# Запустить short DPO (200 steps) на каждом subset, выбрать best Pareto
# Update specs/019-ns-vstar-dpo/research.md::D-002 с финальным выбором
```

### Финальный pair-build

```bash
uv run python training/scripts/build_dpo_dataset.py \
    --completions data/vstar/completions.jsonl \
    --prm-scores data/cache/prm_scores.json \
    --pedagogy-scores data/cache/pedagogy_scores.json \
    --weights <FINAL_WEIGHTS> \
    --tau 0.15 \
    --out data/vstar/dpo_pairs.jsonl
```

---

## Phase 5: NS-V-STaR-DPO Training *(8–12 h, ~88 vu)*

```bash
# Lightning AI A100 80GB (long job, надёжнее Colab)
# Открыть notebooks/ns_vstar_dpo.ipynb
# Параметры по умолчанию:
#   - β = 0.1
#   - learning_rate = 5e-6
#   - 1-2 epochs
#   - bf16, gradient_checkpointing
#   - eval каждые 200 steps
# Push to HF: Siesher/mits-qwen3-9b-nsvstar-dpo
```

---

## Phase 6: Ablations *(16–24 h, ~175 vu)*

### Ablation −PRM

```bash
uv run python training/scripts/build_dpo_dataset.py \
    --completions data/vstar/completions.jsonl \
    --prm-scores data/cache/prm_scores.json \
    --pedagogy-scores data/cache/pedagogy_scores.json \
    --weights "0.5,0.0,0.5" \
    --tau 0.15 \
    --out data/vstar/dpo_pairs_noprm.jsonl

# Re-run notebook с dpo_pairs_noprm.jsonl
# Push: Siesher/mits-qwen3-9b-ablation-noprm
```

### Ablation −NoSpoiler

```bash
uv run python training/scripts/build_dpo_dataset.py \
    --weights "0.5,0.5,0.0" \
    --out data/vstar/dpo_pairs_nospoiler.jsonl
# ...
# Push: Siesher/mits-qwen3-9b-ablation-nospoiler
```

---

## Phase 7: External & Internal Eval *(6–8 h, ~70 vu)*

```bash
# 1. MathTutorBench eval
# Открыть notebooks/mathtutorbench_eval.ipynb
# Run на 6 моделях → evaluation/reports/mathtutorbench_YYYYMMDD.json

# 2. Re-run honest_eval_full_precision на 3 новых адаптерах
# (ns-vstar-dpo, ablation-noprm, ablation-nospoiler)
# Объединить с Phase 0 result → evaluation/reports/final_comparison_YYYYMMDD.json
```

---

## Phase 8: Pareto + Diploma Writeup

```bash
# 1. Generate Pareto chart
uv run python -c "
import json, matplotlib.pyplot as plt
with open('evaluation/reports/final_comparison_YYYYMMDD.json') as f:
    data = json.load(f)
# ... plot accuracy vs pedagogy для 6 моделей
"

# 2. Write docs/NS_VSTAR_DPO.md (method explanation)

# 3. Compile docs/diploma/chapter_nsvstar.docx (~10-12 pages)
#    Sections: Method (3-4) / Experiments (3) / Ablations (2) / Discussion (1-2)

# 4. Update README.md, CLAUDE.md, MEMORY.md

# 5. Final commit + PR
git add specs/019-ns-vstar-dpo/ docs/NS_VSTAR_DPO.md docs/diploma/chapter_nsvstar.docx
git commit -m "feat(019): NS-V-STaR-DPO — composite reward DPO with V-STaR + No-Spoiler + PRM"
git push -u origin 019-ns-vstar-dpo
gh pr create --title "feat(019): NS-V-STaR-DPO" --body "See specs/019-ns-vstar-dpo/spec.md"
```

---

## Troubleshooting

- **Colab disconnect mid-generation**: чекпоинт каждые 100 tasks в `data/vstar/completions.jsonl` (append mode); resume автоматически.
- **PRM OOM**: уменьшить `batch_size` до 4 или 2; PRM 7B bf16 = ~14GB, требует ≥24GB GPU.
- **Cerebras 429**: rotating pool автоматически переключается; если все 10 keys exhausted — wait 60s и retry.
- **DPO loss spike**: уменьшить `learning_rate` до 1e-6 или увеличить `β` до 0.2 (более conservative).
- **Compute budget overrun**: см. fallback в plan.md (Complexity Tracking).

## Validation Checklist (перед PR)

- [ ] Phase 0 report committed
- [ ] seed_choice.md committed с обоснованием
- [ ] Все 3 trained adapters на HF Hub с model cards
- [ ] dpo_pairs.jsonl + 2 ablation variants committed (или uploaded на HF dataset)
- [ ] PRM cache + Pedagogy cache committed (для воспроизводимости)
- [ ] final_comparison_YYYYMMDD.json + Pareto chart в `docs/`
- [ ] Diploma chapter draft committed
- [ ] CLAUDE.md / MEMORY.md обновлены
