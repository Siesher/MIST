# Tasks: NS-V-STaR-DPO (lean-demo scope)

**Feature**: 019-ns-vstar-dpo | **Generated from**: spec.md, plan.md, research.md
**Scope**: Lean demonstrator (~140 vu из 600), proof-of-concept без full-scale claim. Резерв 460 vu для retries / debug.

Phase-ordered task list. Tasks marked `[P]` могут выполняться параллельно с предыдущими (нет shared state). Compute estimates в vu (RTX 6000 Pro 96GB @ 8.71/h).

---

## Phase 0: Honest Re-eval *(P1, blocks all subsequent phases)*

- [x] **T001** Создан `notebooks/honest_eval_full_precision.ipynb` (Colab edition: A100/L4 проверка, Drive .env, repo clone, BASE_MODEL_ID, DECODING_CONFIG, eval_stage, save report). *Done в предыдущей сессии*.
- [ ] **T002** Запустить notebook на Colab A100, получить `evaluation/reports/honest_full_precision_YYYYMMDD.json` для base/GSPO/KTO **на full 218 problems** (не только calc subset). *(SC-001, ~32 vu)*
- [ ] **T003** Зафиксировать seed_choice (best of three в bf16) в `specs/019-ns-vstar-dpo/seed_choice.md` с обоснованием composite metric. *(блокирует Phase 1)*

## Phase 1: V-STaR Generation (lean-demo)

- [ ] **T004** [P] Создать `training/scripts/vstar_generate.py` — batched generation N=4 per task от seed checkpoint, output `data/vstar/completions.jsonl`. Поддержка `--subset-manifest` и `--N` CLI args.
- [ ] **T005** [P] Создать `training/scripts/build_subset.py` — stratified-by-(domain, difficulty) sampling из `dialogs.jsonl`, target 1000, output `data/vstar/subset_manifest.json` с task_ids + proportions + `random_state=42`.
- [ ] **T006** Запустить vstar_generate.py на RTX 6000 Pro 96GB, batch_size=16, ~2-3h, upload manifest+completions на HF dataset `Siesher/mits-vstar-completions-N4-1k`. *(~22 vu)*

## Phase 2: PRM Scoring (Skywork-o1-1.5B, co-located)

- [ ] **T007** Создать `src/scoring/prm_scorer.py` — wrapper вокруг **Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B** (`load_model`, `score_steps`, `aggregate_mean`). Unit-tests на 5 known-good и 5 known-bad reasoning chains.
- [ ] **T008** Создать `training/scripts/score_completions.py --component=prm` — читает completions.jsonl, бьёт по batches=16, пишет `data/cache/prm_scores.json` keyed by sha256(model_id + prompt + completion).
- [ ] **T009** Запустить PRM scoring на ~4000 completions (**co-located** в одной сессии с Phase 1 на 96GB; 1.5B PRM = 3GB, 9B tutor = 22GB, KV cache batch=16 ~30GB → 55GB total ≪ 96GB). *(~5 vu, overlap with T006)*

## Phase 3: Pedagogy Scoring (Cerebras)

- [ ] **T010** [P] Создать `src/scoring/pedagogy_scorer.py` — extract `evaluate_combined_quality` логики из `evaluate_stage.py` в reusable wrapper, добавить cache support и rotating key pool.
- [ ] **T011** Запустить `score_completions.py --component=pedagogy` на ~4000 completions (1.5-2.5h, rate-limited Cerebras 10 keys). *(API only, ~0 vu)*

## Phase 4: Composite + DPO Pairs (no sweep)

- [ ] **T012** Создать `src/scoring/composite.py` — `composite_score(corr, prm, ped, weights) -> float` с **зафиксированными `weights = (0.5, 0.25, 0.25)`** (D-002). Unit-tests на edge cases (NaN, all-zero, all-one, bounds).
- [ ] **T013** Создать `src/data/vstar_pair_builder.py` — within-task top-vs-bottom selection с τ=0.15 threshold (D-008), output `data/vstar/dpo_pairs.jsonl`. Reject tied scores.
- [ ] **T014** Создать `training/scripts/build_dpo_dataset.py` — orchestrator: composite_scores → pair_builder → dpo_pairs.jsonl. Поддержка `--weights` CLI для ablation `-PRM`.
- [ ] ~~**T015** Sensitivity sweep~~ **REMOVED — lean-demo, weights locked at D-002**.

## Phase 5: NS-V-STaR-DPO Training

- [ ] **T016** Создать `notebooks/ns_vstar_dpo.ipynb` (Lightning AI RTX 6000 Pro 96GB) — load seed checkpoint, load dpo_pairs (~1000), TRL DPOTrainer, β=0.1, **1 epoch**, push to HF `Siesher/mits-qwen3-9b-nsvstar-dpo`. Eval каждые 100 steps с early-stop.
- [ ] **T017** Запустить training (~2-3h на 96GB, batch_size=8 с gradient_accumulation), сохранить training logs в `evaluation/training_logs/ns_vstar_dpo_YYYYMMDD.json`. *(~22 vu)*

## Phase 6: Single Ablation (`-PRM`)

- [ ] **T018** Ablation `-PRM`: повторить Phase 4 с `--weights 0.5,0.0,0.5`, тренировать `Siesher/mits-qwen3-9b-ablation-noprm`. Manifest `data/vstar/ablations/noprm_manifest.json`. *(~22 vu)*
- [ ] ~~**T019** Ablation -NoSpoiler~~ **REMOVED — lean-demo, FW completion**.

## Phase 7: External & Internal Eval

- [ ] **T020** Создать `notebooks/mathtutorbench_eval.ipynb` — load benchmark **100-task spot check (random_state=42)**, run на 3 моделях (seed_baseline, ns-vstar-dpo, ablation-noprm), output `evaluation/reports/mathtutorbench_YYYYMMDD.json`. *(~12 vu)*
- [ ] **T021** Re-run honest_eval_full_precision на 2 новых адаптерах (ns-vstar-dpo + ablation-noprm) → 5 моделей (3 baseline + 2 new) в едином отчёте `evaluation/reports/final_comparison_YYYYMMDD.json`. *(~20 vu)*

## Phase 8: Pareto + Writeup

- [ ] **T022** Создать `docs/NS_VSTAR_DPO.md` — method explanation, equations, results table, Pareto chart (matplotlib): `accuracy vs pedagogy_score` для 5 моделей.
- [ ] **T023** Создать `docs/diploma/chapter_nsvstar.docx` (новая глава) — методология (3-4 page), эксперименты на lean-demo scope (2-3 page), single-ablation analysis (1-2 page), **explicit "Limitations" section** (1 page) обсуждающий: PRM distribution mismatch, lean subset, single ablation. **"Future Work" section** (1 page): full-scale replication, second ablation `-NoSpoiler`, Rubric Reward swap, sensitivity sweep, multi-seed V-STaR.
- [ ] **T024** Update `README.md` + `CLAUDE.md` + `MEMORY.md` — указание на новый stage в pipeline (`Qwen3.5-9B → GSPO → KTO → NS-V-STaR-DPO`), пометка "lean-demo proof of concept".
- [ ] **T025** Final commit `feat(019): NS-V-STaR-DPO — composite reward DPO with V-STaR + No-Spoiler + PRM (lean-demo)`. PR на main, model cards на HF.

---

## Compute Budget Tracking (lean-demo target ~140 vu)

| Phase | Estimated vu | Actual (filled after run) | Notes |
|---|---|---|---|
| 0 | ~32 | _ | T002 |
| 1 | ~22 | _ | T006 (1000-subset, batch=16 на 96GB) |
| 2 | ~5 | _ | T009 (Skywork 1.5B co-located) |
| 3 | ~0 (API) | _ | T011 |
| 4 | ~0 | _ | No sweep, weights locked |
| 5 | ~22 | _ | T017 (1 epoch, ~1000 pairs) |
| 6 | ~22 | _ | T018 (single -PRM ablation) |
| 7 | ~32 | _ | T020 + T021 |
| **Total target** | **~135 vu** | **out of 600** | **Reserve ~465 vu** |

## Dependency Graph (lean-demo)

```text
T001 (done) → T002 → T003
                       │
                       ├─→ T004 [P] ─┐
                       └─→ T005 [P] ─┴─→ T006 ⇿ T009 (co-located)
                                          │
                                          ├─→ T007 → T008 ──┐
                                          └─→ T010 [P] → T011
                                                            │
                              T012 ──── T013 ──── T014 ─────┤
                                                            │
                                                            T016 → T017
                                                                    │
                                                                    T018 (single -PRM)
                                                                    │
                                                                    T020 ── T021
                                                                    │
                                                                    T022 → T023 → T024 → T025
```

## Future Work (отслеживаются за пределами 019 spec)

- **FW-1**: Full-scale 3875-task replication (extend Phase 1-2 на full dataset, +~70 vu).
- **FW-2**: Second ablation `-NoSpoiler` (+22 vu) — completeness.
- **FW-3**: Joint ablation `-PRM-NoSpoiler` (correctness-only baseline) (+22 vu).
- **FW-4**: Sensitivity sweep по reward weights (3 configs × 200-task mini × short DPO, +17 vu).
- **FW-5**: Rubric Reward (arXiv:2510.07774) swap для PRM-component — фундаментально решает distribution mismatch.
- **FW-6**: Multi-seed V-STaR (generate from 2-3 best seeds, compare donor effects, +88 vu).
- **FW-7**: Production q4 quantization для Ollama deploy.

Сумма Future Work: ~240 vu — comfortably fits в оставшийся резерв 460 vu, можно делать инкрементально после защиты диплома.
