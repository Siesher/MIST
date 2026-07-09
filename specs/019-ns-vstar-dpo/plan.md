# Implementation Plan: NS-V-STaR-DPO

**Branch**: `019-ns-vstar-dpo` | **Date**: 2026-05-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/019-ns-vstar-dpo/spec.md`

## Summary

Завершение MITS-пайплайна научно-новым этапом (lean-demo scope): после `GSPO + KTO` применить **NS-V-STaR-DPO** — single-method композицию V-STaR self-improvement, No-Spoiler pedagogy reward и PRM step-level scoring в один DPO-loss с within-task pairing. Перед этим — обязательный honest bf16 re-eval всех чекпоинтов для устранения inference artifact. **Lean-demo target**: ~140 vu / ~16 GPU-hours на RTX 6000 Pro 96GB (Lightning AI) — proof-of-concept demonstration с резервом 460 vu для retries и debugging. Полномасштабная репликация — fixed как Future Work в diploma.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**:
- `transformers==4.46.0`, `peft==0.13.0`, `trl` (DPOTrainer), `accelerate==1.1.0`, `bitsandbytes==0.44.0`
- `torch>=2.4` bf16, `datasets`, `huggingface_hub`
- `openai>=1.50` (Cerebras Combined Judge через OpenAI-compatible endpoint)
- Existing: `training/scripts/evaluate_stage.py::evaluate_combined_quality`, `training/cerebras_client.py`
- New external model: `Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B` (~3GB bf16) — tuned для o1-style thinking traces, lean-demo выбор

**Storage**:
- HF Hub — adapters, datasets, model cards
- Google Drive (`MyDrive/MITS_secrets/`) — `.env`, eval reports backup
- Local JSON cache — `data/cache/{prm,pedagogy}_scores_*.json` (idempotent re-runs)

**Testing**:
- Unit: composite scorer math, pair-formation logic, NaN/edge handling
- Integration: mini-pipeline на 200-task subset E2E
- Eval: honest benchmark (218 task) + MathTutorBench

**Target Platform**: Lightning AI RTX 6000 Pro 96GB primary (long jobs + co-located PRM+tutor); Google Colab Pro+ (A100 80GB) для Phase 0 honest eval

**Project Type**: Final stage of training pipeline (replaces "DPO polish" из original `Qwen3.5-9B → GSPO → KTO → DPO` плана), lean-demo scope

**Performance Goals**: Direction-of-effect demonstration (см. SC-002, SC-003 — lean-demo targets, не SOTA)

**Constraints**:
- ≤ 200 vu compute target (lean scope), ≤ 600 vu hard cap (full budget с резервом на retries)
- bf16-only inference (no q4 quantization в eval/training — production q4 deploy после успеха в отдельной фазе)
- All judge / PRM calls cached → одна и та же оценка для одного и того же completion
- Cerebras key rotation (10 keys) для rate limits
- 96GB enables co-located inference: Skywork-PRM-1.5B + Qwen3.5-9B + KV cache в одной сессии

**Scale/Scope (lean-demo)**:
- **1000 stratified-by-(domain, difficulty) subset** из 3875 socratic dialog tasks
- 218 calc-subset (143 numeric/latex_boxed) — honest eval benchmark (полный, не cut)
- N=4 completions per task → ~4000 generations
- Up to 1000 DPO pairs (within-task top-vs-bottom, 1 pair per task)
- 100-task MathTutorBench spot check для external validity sanity

## Constitution Check

*GATE: Must pass before Phase 0 execution. Re-check after Phase 1 completion.*

| Principle | Status | Notes |
|---|---|---|
| I. Socratic Pedagogy | PASS | Метод сохраняет/усиливает Socratic поведение через явный pedagogy reward (No-Spoiler) — не подавляет в угоду accuracy. Ablation −NoSpoiler специально измеряет цену исключения этого компонента. |
| II. Multi-Agent Architecture | PASS | Final adapter подгружается в существующий orchestrator без изменения agent топологии — только weight delta для tutor agent. |
| III. Knowledge-Grounded Responses | PASS | Generation на in-distribution `dialogs.jsonl` (Knowledge Forge concepts), correctness-component grounded в `ground_truth`. |
| IV. Hardware Constraint Compliance | PASS | bf16 9B = ~22GB VRAM, PRM 7B запускается отдельной сессией. Production q4 conversion после успеха для on-prem deploy. |
| V. Metrics-Driven Quality | PASS | 8 SCs с числами, ablations изолируют вклады, MathTutorBench даёт external validity. |
| VI. STEM Domain Coverage | PASS | Полное покрытие math/physics/chem/bio/cs — domain распределение `dialogs.jsonl` = train; 218-task eval тоже многодоменный. |

**Result**: 6/6 PASS. No complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/019-ns-vstar-dpo/
├── plan.md              # This file
├── spec.md              # User stories, FRs, SCs
├── research.md          # Decisions + citations (V-STaR, No-Spoiler, PRM, MathTutorBench)
├── data-model.md        # Composite Scorer, DPO Pair, Honest Eval Report schemas
├── tasks.md             # Phase-ordered T001..T0NN
├── quickstart.md        # Reproduction steps
└── seed_choice.md       # GENERATED после Phase 0 — фиксирует best-of-three для V-STaR seed
```

### Source Code

```text
notebooks/
├── honest_eval_full_precision.ipynb    # READY — Phase 0 (bf16 re-eval всех 3-х чекпоинтов)
├── ns_vstar_dpo.ipynb                   # NEW — Phase 5 main training
└── mathtutorbench_eval.ipynb            # NEW — Phase 7 external eval

src/scoring/
├── __init__.py                          # NEW
├── prm_scorer.py                        # NEW — Qwen2.5-Math-PRM-7B wrapper
├── pedagogy_scorer.py                   # NEW — Cerebras Combined Judge wrapper (extracts existing logic)
└── composite.py                         # NEW — w1·corr + w2·prm + w3·ped с config

src/data/
└── vstar_pair_builder.py                # NEW — within-task DPO pair formation

training/scripts/
├── vstar_generate.py                    # NEW — N=4 completions per task batch
├── score_completions.py                 # NEW — orchestrates 3-component scoring
└── build_dpo_dataset.py                 # NEW — emits dpo_pairs.jsonl

evaluation/
├── reports/
│   └── honest_full_precision_*.json     # Phase 0 outputs
└── benchmarks/
    └── mathtutorbench/                  # downloaded subset

docs/
├── NS_VSTAR_DPO.md                      # NEW — method explanation для diploma reference
└── diploma/
    └── chapter_nsvstar.docx             # NEW — main deliverable
```

**Structure Decision**: Изолируем новые модули в `src/scoring/` (3 scorer файла, чистые функциональные обёртки) и `src/data/`. Тренировочные скрипты — в `training/scripts/` для совместимости с существующим pipeline. Notebooks для интерактивных stages (Colab-friendly), `.py`-скрипты для batch-операций. Никаких изменений в `backend/`/`frontend/` — это чисто training feature.

## Phase Plan (lean-demo)

| Phase | Описание | Compute | Длительность | vu (≈) |
|---|---|---|---|---|
| 0 | Honest bf16 re-eval (notebook готов, full 218 problems) | A100 / RTX 6000 Pro | 3.6–4.5 h | ~32 |
| 1 | V-STaR generation (N=4 × **1000-task subset** = ~4000 completions) | RTX 6000 Pro 96GB | 2–3 h | ~22 |
| 2 | PRM scoring (Skywork-1.5B, **co-located** с Phase 1) | RTX 6000 Pro 96GB | overlap with Phase 1 | ~5 |
| 3 | Pedagogy scoring (Cerebras judge, async, cached) | API only | 1.5–2.5 h (rate-limited) | ~0 |
| 4 | Composite scoring + DPO pair build (no sweep, fixed weights) | CPU | <30 min | ~0 |
| 5 | NS-V-STaR-DPO training (1 epoch on ~1000 pairs) | RTX 6000 Pro 96GB | 2–3 h | ~22 |
| 6 | **Single ablation `-PRM`** (one run) | RTX 6000 Pro 96GB | 2–3 h | ~22 |
| 7 | Eval honest 218 ×3 + MathTutorBench-100 ×3 | A100 / RTX 6000 Pro | 3–4 h | ~32 |
| 8 | Pareto + diploma writeup | CPU | manual | ~0 |
| **Total** | | | **~16 GPU-h** | **~135 vu** |

**Резерв ~465 vu** для retries, debug, scale-up if нужно (например, добавить второй ablation или расширить subset).

Бюджет 200 vu комфортно укладывается; 600 vu hard cap не достигается.

## Complexity Tracking

| Risk | Likelihood | Mitigation |
|---|---|---|
| GSPO/KTO worse than base после honest re-eval | medium | Pivot V-STaR seed to whichever is best (base/GSPO/KTO); spec уже допускает в edge cases. `seed_choice.md` фиксирует решение детерминистично. |
| PRM 1.5B distribution mismatch с Qwen3.5 | medium | Skywork-o1 tuned для o1-style thinking traces (≈ Qwen3.5 thinking mode). Limitation документируется в diploma "Limitations". В worst case — null result в `-PRM` ablation, репортуется честно. |
| Cerebras rate limits | high | Rotating pool 10 keys, exponential backoff, async scoring with cache. Уже реализовано в `training/cerebras_client.py`. |
| Within-task pairing → too few pairs (<50% tasks с valid pair на 1000-subset) | medium | Threshold τ adaptive: если <50% задач дают valid pair при τ=0.15, снижаем до 0.10. Запас compute (резерв 460 vu) позволяет повторить с N=6 если нужно. |
| MathTutorBench coverage limited | low | 100-task spot check — sanity, не peer claim. Документируется в `research.md` как scope decision. |
| DPO training divergence (NaN, loss explosion) | low | β=0.1 default conservative; `bf16` forward, fp32 master weights; gradient clipping 1.0; eval каждые 200 steps с early stop. |
| Single ablation null result | medium | Acceptable как honest negative finding для proof-of-concept diploma. Discussion section обсуждает possible causes (PRM noise, distribution mismatch). |
| Compute overrun >200 vu (lean target) | low | Резерв 400+ vu делает overrun практически невозможным; в крайнем случае cut subset 1000 → 500. |

**No constitution violations.**

## Decision Hooks

Following decisions are deferred to runtime, recorded в `research.md` или `seed_choice.md`:

1. **Seed checkpoint** (D-001): best of base/GSPO/KTO в bf16 — определяется по Phase 0 results.
2. **Composite weights** (D-002): **зафиксированы** на `(0.5, 0.25, 0.25)` (no sweep в lean scope).
3. **PRM aggregation** (D-005): default mean; sensitivity check вынесен в Future Work.
4. **τ threshold** (D-008): default 0.15, adaptive если valid pair coverage < 50%.
5. **PRM model** (D-005-bis): `Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B` — lean-demo выбор (3GB, fast, o1-tuned).
6. **Subset sampling** (D-009): stratified by `(domain, difficulty)`, target 1000 tasks, fallback all-available если domain имеет <100 примеров.

## Cross-references

- Spec: [spec.md](spec.md)
- Research log: [research.md](research.md)
- Tasks: [tasks.md](tasks.md)
- Reproduction: [quickstart.md](quickstart.md)
