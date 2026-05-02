# Tasks: NS-V-STaR-DPO

**Feature**: 019-ns-vstar-dpo | **Generated from**: spec.md, plan.md, research.md

Phase-ordered task list. Tasks marked `[P]` могут выполняться параллельно с предыдущими (нет shared state). Compute estimates в vu (RTX 6000 @ 8.71/h).

---

## Phase 0: Honest Re-eval *(P1, blocks all subsequent phases)*

- [x] **T001** Создан `notebooks/honest_eval_full_precision.ipynb` (Colab edition: A100/L4 проверка, Drive .env, repo clone, BASE_MODEL_ID, DECODING_CONFIG, eval_stage, save report). *Done в предыдущей сессии*.
- [ ] **T002** Запустить notebook на Colab A100, получить `evaluation/reports/honest_full_precision_YYYYMMDD.json` для base/GSPO/KTO. *(SC-001, ~32 vu)*
- [ ] **T003** Зафиксировать seed_choice (best of three в bf16) в `specs/019-ns-vstar-dpo/seed_choice.md` с обоснованием выбранного composite metric. *(блокирует Phase 1)*

## Phase 1: V-STaR Generation

- [ ] **T004** [P] Создать `training/scripts/vstar_generate.py` — batched generation N=4 per task от seed checkpoint, output `data/vstar/completions.jsonl` со схемой из data-model.md.
- [ ] **T005** [P] Создать `data/vstar/manifest.json` — список task_id из `data/training/dialogs.jsonl`, контрольные хэши, dataset card.
- [ ] **T006** Запустить vstar_generate.py на A100 80GB (8-10h), upload результат на HF dataset `Siesher/mits-vstar-completions-N4`. *(~88 vu)*

## Phase 2: PRM Scoring

- [ ] **T007** Создать `src/scoring/prm_scorer.py` — wrapper вокруг Qwen2.5-Math-PRM-7B (`load_model`, `score_steps`, `aggregate_mean`). Unit-tests на 5 known-good и 5 known-bad reasoning chains (golden/regression suite).
- [ ] **T008** Создать `training/scripts/score_completions.py --component=prm` — читает completions.jsonl, бьёт по batches, пишет `data/cache/prm_scores.json` с cache keyed by sha256 (D-006).
- [ ] **T009** Запустить PRM scoring на 15,500 completions (4-5h, A100 40GB+). *(~40 vu)*

## Phase 3: Pedagogy Scoring (Cerebras)

- [ ] **T010** [P] Создать `src/scoring/pedagogy_scorer.py` — extract `evaluate_combined_quality` логики из `evaluate_stage.py` в reusable wrapper, добавить cache support и rotating key pool.
- [ ] **T011** Запустить `score_completions.py --component=pedagogy` на 15,500 completions (6-8h, rate-limited Cerebras). *(API only, ~0 vu)*

## Phase 4: Composite + DPO Pairs

- [ ] **T012** Создать `src/scoring/composite.py` — `composite_score(corr, prm, ped, weights) -> float`. Unit-tests на edge cases (NaN handling, all-zero, all-one, bounds).
- [ ] **T013** Создать `src/data/vstar_pair_builder.py` — within-task top-vs-bottom selection с τ threshold (D-008), output `data/vstar/dpo_pairs.jsonl`. Reject tied scores (no random tie-breaking).
- [ ] **T014** Создать `training/scripts/build_dpo_dataset.py` — orchestrator: composite_scores → pair_builder → dpo_pairs.jsonl. Поддержка `--weights` CLI-параметра для ablations.
- [ ] **T015** Sensitivity sweep: 3 weight configs (D-002) × 200-task mini-subset → выбор финальных весов. Update `research.md::D-002` с recorded result. *(~17 vu, ~3h на A100)*

## Phase 5: NS-V-STaR-DPO Training

- [ ] **T016** Создать `notebooks/ns_vstar_dpo.ipynb` (Lightning AI A100 80GB) — load seed checkpoint, load dpo_pairs, TRL DPOTrainer, β=0.1, 1-2 epochs, push to HF `Siesher/mits-qwen3-9b-nsvstar-dpo`. Включает eval каждые 200 steps с early-stop.
- [ ] **T017** Запустить training (8-12h на A100 80GB), сохранить training logs в `evaluation/training_logs/ns_vstar_dpo_YYYYMMDD.json`. *(~88 vu)*

## Phase 6: Ablations

- [ ] **T018** [P] Ablation −PRM: повторить Phase 4 с `--weights 0.5,0.0,0.5`, тренировать `Siesher/mits-qwen3-9b-ablation-noprm`. Manifest `data/vstar/ablations/noprm_manifest.json`. *(~88 vu)*
- [ ] **T019** [P] Ablation −NoSpoiler: повторить Phase 4 с `--weights 0.5,0.5,0.0`, тренировать `Siesher/mits-qwen3-9b-ablation-nospoiler`. Manifest `data/vstar/ablations/nospoiler_manifest.json`. *(~88 vu)*

## Phase 7: External & Internal Eval

- [ ] **T020** Создать `notebooks/mathtutorbench_eval.ipynb` — load benchmark (English subset, 500 random tasks для compute budget), run на 6 моделях (base, gspo, kto, ns-vstar-dpo, ablation-noprm, ablation-nospoiler), output `evaluation/reports/mathtutorbench_YYYYMMDD.json`. *(~35 vu)*
- [ ] **T021** Re-run honest_eval_full_precision на ns-vstar-dpo и 2 ablations → 6 моделей в едином отчёте `evaluation/reports/final_comparison_YYYYMMDD.json`. *(~35 vu)*

## Phase 8: Pareto + Writeup

- [ ] **T022** Создать `docs/NS_VSTAR_DPO.md` — method explanation, equations, results table, Pareto chart (matplotlib): `accuracy vs pedagogy_score` для всех 6 моделей.
- [ ] **T023** Создать `docs/diploma/chapter_nsvstar.docx` (новая глава для diploma) — методология (3-4 page), эксперименты (3 page), ablation analysis (2 page), discussion of limitations + future work (1-2 page).
- [ ] **T024** Update `README.md` + `CLAUDE.md` + `MEMORY.md` — указание на новый stage в pipeline (`Qwen3.5-9B → GSPO → KTO → NS-V-STaR-DPO`).
- [ ] **T025** Final commit `feat(019): NS-V-STaR-DPO — composite reward DPO with V-STaR + No-Spoiler + PRM`. PR на main, model card на HF.

---

## Compute Budget Tracking

| Phase | Estimated vu | Actual (filled after run) | Notes |
|---|---|---|---|
| 0 | ~32 | _ | T002 |
| 1 | ~88 | _ | T006 |
| 2 | ~40 | _ | T009 |
| 3 | ~0 (API) | _ | T011 |
| 4 | ~17 | _ | T015 sweep |
| 5 | ~88 | _ | T017 |
| 6 | ~175 | _ | T018 + T019 |
| 7 | ~70 | _ | T020 + T021 |
| **Total** | **~510 vu** | **out of 600** | Reserve ~90 vu |

## Dependency Graph

```text
T001 (done) → T002 → T003
                       │
                       ├─→ T004 [P] ─┐
                       └─→ T005 [P] ─┴─→ T006
                                          │
                                          ├─→ T007 → T008 → T009
                                          └─→ T010 [P] → T011
                                                          │
                              T012 ──── T013 ──── T014 ───┤
                                                          │
                                                          T015 (sweep, finalizes weights)
                                                          │
                                                          T016 → T017
                                                                  │
                                                                  ├─→ T018 [P]
                                                                  ├─→ T019 [P]
                                                                  │
                                                                  T020 ── T021
                                                                  │
                                                                  T022 → T023 → T024 → T025
```
