# Quickstart: NS-V-STaR-DPO Pipeline (lean-demo)

**Feature**: 019-ns-vstar-dpo
**Scope**: Lean demonstrator (~140 vu) для proof-of-concept в дипломе.

Полная репродукция от honest re-eval до diploma chapter.

## Prerequisites

- Lightning AI account (RTX 6000 Pro Blackwell 96GB) для long-running phases (generation + co-located scoring + DPO + ablation)
- Google Colab Pro+ (A100 80GB) для Phase 0 honest re-eval
- Hugging Face account `Siesher` с push access (write token)
- Cerebras API key pool (10 keys в `.env`) на `MyDrive/MITS_secrets/.env`
- 600 vu compute budget (RTX 6000 Pro @ 8.71/h); реально потратим ~140 vu
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
# 1. Открыть notebook из github Siesher/MIST branch 019-ns-vstar-dpo
# 2. Установить runtime → A100
# 3. Run all cells
# 4. Результат: evaluation/reports/honest_full_precision_YYYYMMDD.json (full 218 problems)
```

После завершения T002 — выбрать seed для V-STaR (T003):

```bash
# Открыть отчёт и определить best of (base, GSPO, KTO) по composite metric:
#     composite = accuracy + 0.5 * socratic_score
# Записать выбор в specs/019-ns-vstar-dpo/seed_choice.md
```

---

## Phase 1+2: V-STaR Generation + PRM Scoring (co-located, ~2.5 h, ~27 vu)

```bash
# Lightning AI RTX 6000 Pro 96GB
# Skywork-PRM-1.5B (~3GB) + Qwen3.5-9B (22GB) + KV cache batch=16 (~30GB) = 55GB → fits

# 1. Build stratified 1000-subset
uv run python training/scripts/build_subset.py \
    --tasks data/training/dialogs.jsonl \
    --target 1000 \
    --stratify-by domain difficulty \
    --random-state 42 \
    --out data/vstar/subset_manifest.json

# 2. V-STaR generation
uv run python training/scripts/vstar_generate.py \
    --seed-model Siesher/mits-qwen3-9b-{gspo|kto|base} \
    --subset-manifest data/vstar/subset_manifest.json \
    --N 4 \
    --temperature 0.7 \
    --num-predict 4096 \
    --enable-thinking \
    --batch-size 16 \
    --out data/vstar/completions.jsonl

# 3. PRM scoring (co-located в той же сессии)
uv run python training/scripts/score_completions.py \
    --component prm \
    --prm-model Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B \
    --in data/vstar/completions.jsonl \
    --cache data/cache/prm_scores.json \
    --batch-size 16

# 4. Upload to HF
huggingface-cli upload Siesher/mits-vstar-completions-N4-1k \
    data/vstar/completions.jsonl --repo-type dataset
```

---

## Phase 3: Pedagogy Scoring *(1.5–2.5 h, API only)*

```bash
uv run python training/scripts/score_completions.py \
    --component pedagogy \
    --in data/vstar/completions.jsonl \
    --cache data/cache/pedagogy_scores.json \
    --concurrent 5
```

Использует rotating pool of 10 Cerebras keys из `.env`.

---

## Phase 4: Composite + DPO Pairs *(< 30 min CPU)*

**Без sensitivity sweep — weights locked** на `(0.5, 0.25, 0.25)` (см. research.md::D-002).

```bash
uv run python training/scripts/build_dpo_dataset.py \
    --completions data/vstar/completions.jsonl \
    --prm-scores data/cache/prm_scores.json \
    --pedagogy-scores data/cache/pedagogy_scores.json \
    --weights 0.5,0.25,0.25 \
    --tau 0.15 \
    --out data/vstar/dpo_pairs.jsonl
```

Sanity check coverage:

```bash
uv run python -c "
import json
pairs = [json.loads(l) for l in open('data/vstar/dpo_pairs.jsonl')]
manifest = json.load(open('data/vstar/subset_manifest.json'))
print(f'Tasks: {len(manifest[\"task_ids\"])}, Pairs: {len(pairs)}, Coverage: {len(pairs)/len(manifest[\"task_ids\"]):.1%}')
"
# Цель: >50% coverage. Если меньше — снижаем τ до 0.10.
```

---

## Phase 5: NS-V-STaR-DPO Training *(2–3 h, ~22 vu)*

```bash
# Lightning AI RTX 6000 Pro 96GB (long job)
# Открыть notebooks/ns_vstar_dpo.ipynb
# Параметры по умолчанию:
#   - β = 0.1
#   - learning_rate = 5e-6
#   - 1 epoch (lean-demo)
#   - bf16, gradient_checkpointing, batch_size=8 + grad_accum=2
#   - eval каждые 100 steps с early-stop
# Push to HF: Siesher/mits-qwen3-9b-nsvstar-dpo
```

---

## Phase 6: Single Ablation `-PRM` *(2–3 h, ~22 vu)*

```bash
# Build ablation pairs
uv run python training/scripts/build_dpo_dataset.py \
    --completions data/vstar/completions.jsonl \
    --prm-scores data/cache/prm_scores.json \
    --pedagogy-scores data/cache/pedagogy_scores.json \
    --weights 0.5,0.0,0.5 \
    --tau 0.15 \
    --out data/vstar/dpo_pairs_noprm.jsonl

# Re-run notebook с dpo_pairs_noprm.jsonl
# Push: Siesher/mits-qwen3-9b-ablation-noprm
```

`-NoSpoiler` ablation — Future Work (см. research.md::D-010).

---

## Phase 7: External & Internal Eval *(3–4 h, ~32 vu)*

```bash
# 1. MathTutorBench spot check (100 random tasks, random_state=42)
# Открыть notebooks/mathtutorbench_eval.ipynb
# Run на 3 моделях (seed_baseline, ns-vstar-dpo, ablation-noprm)
# → evaluation/reports/mathtutorbench_YYYYMMDD.json

# 2. Re-run honest_eval_full_precision на 2 новых адаптерах
# (ns-vstar-dpo, ablation-noprm)
# Объединить с Phase 0 result → evaluation/reports/final_comparison_YYYYMMDD.json
# Всего 5 моделей: base, gspo, kto (Phase 0), ns-vstar-dpo, ablation-noprm
```

---

## Phase 8: Pareto + Diploma Writeup

```bash
# 1. Generate Pareto chart
uv run python -c "
import json, matplotlib.pyplot as plt
with open('evaluation/reports/final_comparison_YYYYMMDD.json') as f:
    data = json.load(f)
# ... plot accuracy vs pedagogy для 5 моделей
"

# 2. Write docs/NS_VSTAR_DPO.md (method explanation)

# 3. Compile docs/diploma/chapter_nsvstar.docx (~10-12 pages)
#    Sections: Method (3-4) / Experiments lean-scope (2-3) / Single Ablation (1-2)
#    + Limitations (1) — distribution mismatch, lean subset, single ablation
#    + Future Work (1) — full-scale, -NoSpoiler, Rubric Reward, sweep

# 4. Update README.md, CLAUDE.md, MEMORY.md

# 5. Final commit + PR
git add specs/019-ns-vstar-dpo/ docs/NS_VSTAR_DPO.md docs/diploma/chapter_nsvstar.docx
git commit -m "feat(019): NS-V-STaR-DPO — lean-demo proof of concept"
git push origin 019-ns-vstar-dpo
gh pr create --title "feat(019): NS-V-STaR-DPO (lean-demo)" --body "See specs/019-ns-vstar-dpo/spec.md"
```

---

## Troubleshooting

- **Colab disconnect mid-generation**: чекпоинт каждые 100 tasks в `data/vstar/completions.jsonl` (append mode); resume автоматически.
- **PRM OOM на 96GB**: маловероятно (1.5B + 9B = 25GB модели + 30GB KV ≈ 55GB). Если случилось — уменьшить batch_size до 8.
- **Cerebras 429**: rotating pool автоматически переключается; если все 10 keys exhausted — wait 60s и retry.
- **DPO loss spike**: уменьшить `learning_rate` до 1e-6 или увеличить `β` до 0.2 (более conservative).
- **Subset coverage < 50% в Phase 4**: снизить τ до 0.10 в `build_dpo_dataset.py`.

## Validation Checklist (перед PR)

- [ ] Phase 0 report committed (full 218 problems)
- [ ] `seed_choice.md` committed с обоснованием
- [ ] `subset_manifest.json` committed (1000 task_ids + per-domain proportions)
- [ ] 2 trained adapters на HF Hub (NS-V-STaR-DPO + ablation-noprm) с model cards
- [ ] dpo_pairs.jsonl + dpo_pairs_noprm.jsonl committed (или uploaded на HF dataset)
- [ ] PRM cache + Pedagogy cache committed (для воспроизводимости)
- [ ] final_comparison_YYYYMMDD.json + Pareto chart в `docs/`
- [ ] Diploma chapter draft committed с явными Limitations + Future Work секциями
- [ ] CLAUDE.md / MEMORY.md обновлены
