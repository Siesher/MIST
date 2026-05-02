# Implementation Plan: NS-V-STaR-DPO

**Branch**: `019-ns-vstar-dpo` | **Date**: 2026-05-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/019-ns-vstar-dpo/spec.md`

## Summary

Завершение MITS-пайплайна научно-новым этапом: после `GSPO + KTO` применить **NS-V-STaR-DPO** — single-method композицию V-STaR self-improvement, No-Spoiler pedagogy reward и PRM step-level scoring в один DPO-loss с within-task pairing. Перед этим — обязательный honest bf16 re-eval всех чекпоинтов для устранения inference artifact. Бюджет 600 vu / 8.71 ≈ 68.9 GPU-hours на Google Colab Pro+ (A100 80GB) с резервом на Lightning AI (RTX 6000) для long jobs.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**:
- `transformers==4.46.0`, `peft==0.13.0`, `trl` (DPOTrainer), `accelerate==1.1.0`, `bitsandbytes==0.44.0`
- `torch>=2.4` bf16, `datasets`, `huggingface_hub`
- `openai>=1.50` (Cerebras Combined Judge через OpenAI-compatible endpoint)
- Existing: `training/scripts/evaluate_stage.py::evaluate_combined_quality`, `training/cerebras_client.py`
- New external model: `Qwen/Qwen2.5-Math-PRM-7B` (~14GB bf16)

**Storage**:
- HF Hub — adapters, datasets, model cards
- Google Drive (`MyDrive/MITS_secrets/`) — `.env`, eval reports backup
- Local JSON cache — `data/cache/{prm,pedagogy}_scores_*.json` (idempotent re-runs)

**Testing**:
- Unit: composite scorer math, pair-formation logic, NaN/edge handling
- Integration: mini-pipeline на 200-task subset E2E
- Eval: honest benchmark (218 task) + MathTutorBench

**Target Platform**: Google Colab Pro+ (A100 80GB) primary, Lightning AI (RTX 6000 / A100 80GB) для long jobs (DPO training, ablations)

**Project Type**: Final stage of training pipeline (replaces "DPO polish" из original `Qwen3.5-9B → GSPO → KTO → DPO` плана)

**Performance Goals**: Pareto improvement (см. SC-002, SC-003, SC-004 в spec.md)

**Constraints**:
- ≤ 600 vu compute budget (RTX 6000 @ 8.71/h)
- bf16-only inference (no q4 quantization в eval/training — production q4 deploy после успеха в отдельной фазе)
- All judge / PRM calls cached → одна и та же оценка для одного и того же completion
- Cerebras key rotation (10 keys) для rate limits

**Scale/Scope**:
- 3875 socratic dialog tasks (`data/training/dialogs.jsonl`) — V-STaR generation source
- 218 calc-subset (143 numeric/latex_boxed) — honest eval benchmark
- N=4 completions per task → 15,500 generations
- Up to 3,875 DPO pairs (within-task top-vs-bottom, 1 pair per task)

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

## Phase Plan

| Phase | Описание | Compute | Длительность | vu (≈) |
|---|---|---|---|---|
| 0 | Honest bf16 re-eval (notebook готов) | A100 / RTX 6000 | 3.6–4.5 h | ~32 |
| 1 | V-STaR generation (N=4 × 3875 = 15,500 completions) | A100 80GB | 8–10 h | ~88 |
| 2 | PRM scoring (15,500 completions × Qwen2.5-Math-PRM-7B) | A100 40GB+ | 4–5 h | ~40 |
| 3 | Pedagogy scoring (Cerebras judge, async, cached) | API only | 6–8 h (rate-limited) | ~0 |
| 4 | Composite scoring + DPO pair build + sensitivity sweep | CPU + 1 short DPO run | 1–2 h + sweep | ~17 |
| 5 | NS-V-STaR-DPO training (1–2 epochs DPO) | A100 80GB | 8–12 h | ~88 |
| 6 | Ablations (−PRM, −NoSpoiler, 2 runs) | A100 80GB | 16–24 h | ~175 |
| 7 | Eval on honest + MathTutorBench (всего 6 моделей) | A100 / RTX 6000 | 6–8 h | ~70 |
| 8 | Pareto + diploma writeup | CPU | manual | ~0 |
| **Total** | | | **~52–72 GPU-h** | **~510 vu** |

Бюджет 600 vu укладывается с резервом ~90 vu на retries и неожиданные расходы.

## Complexity Tracking

| Risk | Likelihood | Mitigation |
|---|---|---|
| GSPO/KTO worse than base после honest re-eval | medium | Pivot V-STaR seed to whichever is best (base/GSPO/KTO); spec уже допускает в edge cases. `seed_choice.md` фиксирует решение детерминистично. |
| PRM 7B + tutor 9B OOM на одной GPU | high | Score completions offline в отдельной Colab-сессии, persist scores в JSON, training session не нуждается в PRM. |
| Cerebras rate limits | high | Rotating pool 10 keys, exponential backoff, async scoring with cache. Уже реализовано в `training/cerebras_client.py`. |
| Within-task pairing → too few pairs (<60% tasks с valid pair) | medium | Threshold τ adaptive: если 60% задач не дают valid pair при τ=0.15, снижаем до 0.10 или увеличиваем N с 4 до 8 (+15-20% compute). |
| MathTutorBench Russian-coverage limited | high | Использовать English subset для external validity; custom benchmark — для in-language claims. Документировать в `research.md`. |
| DPO training divergence (NaN, loss explosion) | low | β=0.1 default conservative; `bf16` forward, fp32 master weights; gradient clipping 1.0; eval каждые 200 steps с early stop. |
| Compute overrun >600 vu | medium | Fallback: сократить N с 4 до 2 (потеряем некоторые pairs); в худшем — только −PRM ablation. |

**No constitution violations.**

## Decision Hooks

Following decisions are deferred to runtime, recorded in `research.md` или `seed_choice.md`:

1. **Seed checkpoint** (D-001): best of base/GSPO/KTO в bf16 — определяется по Phase 0 results.
2. **Composite weights** (D-002): default `(0.5, 0.25, 0.25)`, validated через sweep в Phase 4.
3. **PRM aggregation** (D-005): default mean; sensitivity check на geometric mean при подозрении на длинно-зависимые artifacts.
4. **τ threshold** (D-008): default 0.15, adaptive если valid pair coverage < 60%.

## Cross-references

- Spec: [spec.md](spec.md)
- Research log: [research.md](research.md)
- Tasks: [tasks.md](tasks.md)
- Reproduction: [quickstart.md](quickstart.md)
