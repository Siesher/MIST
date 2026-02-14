# Tasks: Advanced STEM Training Pipeline

**Input**: Design documents from `/specs/014-advanced-training-pipeline/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Not explicitly requested. Test tasks omitted. Verification is via per-domain evaluation metrics output by each notebook.

**Organization**: Tasks are grouped by user story. Note: this pipeline has sequential checkpoint dependencies (each stage loads the previous stage's adapter), but each story is independently testable by running its notebook and checking output metrics.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Notebooks**: `notebooks/` at repository root
- **Training scripts**: `training/scripts/` at repository root
- **Specs**: `specs/014-advanced-training-pipeline/`

---

## Phase 1: Setup

**Purpose**: Verify existing infrastructure and prepare environment

- [X] T001 Verify sort_curriculum.py classify_difficulty function works with HuggingFace GSPO dataset format in training/scripts/sort_curriculum.py
- [X] T002 Verify verify_answers.py verify_answer function works with all 5 STEM domains in training/scripts/verify_answers.py
- [X] T003 Read current stem_rewards.py to understand existing reward function signatures in training/scripts/stem_rewards.py

---

## Phase 2: Foundational — Reward Infrastructure (US5, Priority: P1)

**Purpose**: Update stem_rewards.py with GDPO-compatible reward functions. This is a blocking prerequisite for US1 (GSPO Curriculum).

**Goal**: Provide two separate reward functions (correctness + format) that TRL normalizes independently, preventing reward hacking.

**Independent Test**: Import stem_rewards.py, call make_gdpo_reward_fns(), verify correctness returns 1.0/0.0 and format returns [0,1].

- [X] T004 [US5] Remove -0.5 wrong answer penalty from compute_reward() — change all `w["wrong"]` defaults from -0.5 to 0.0 in training/scripts/stem_rewards.py
- [X] T005 [US5] Add make_gdpo_correctness_fn(problems, tokenizer) that returns a callable matching TRL signature: (completions, prompts=None, **kwargs) -> list[float], using verify_answers.py internally, in training/scripts/stem_rewards.py
- [X] T006 [US5] Add make_gdpo_format_fn() that returns a callable scoring \\boxed{} presence + step-by-step markers + length, returning [0,1], in training/scripts/stem_rewards.py
- [X] T007 [US5] Add make_gdpo_reward_fns(problems, tokenizer) convenience function that returns [correctness_fn, format_fn] list for GRPOTrainer, in training/scripts/stem_rewards.py
- [X] T008 [US5] Keep backward-compatible make_reward_fn() untouched for other notebooks, just update its default wrong penalty to 0.0 in training/scripts/stem_rewards.py

**Checkpoint**: stem_rewards.py provides GDPO-compatible functions. US1 can now begin.

---

## Phase 3: User Story 1 — GSPO Curriculum Training (Priority: P1) 🎯 MVP

**Goal**: Add difficulty-aware staged training and zero-variance masking to the existing GSPO notebook.

**Independent Test**: Run grpo_qwen3_4b.ipynb on Colab A100. Training logs show difficulty classification, staged training (easy+medium then all), and zero-variance groups masked. Per-domain accuracy improves >=3% over non-curriculum baseline.

### Implementation for User Story 1

- [X] T009 [US1] Add curriculum classification cell: import classify_difficulty from training.scripts.sort_curriculum, classify each verifiable_problem, print distribution stats in notebooks/grpo_qwen3_4b.ipynb
- [X] T010 [US1] Add difficulty-aware dataset splitting: create easy_medium_ds and full_ds datasets sorted by difficulty tier in notebooks/grpo_qwen3_4b.ipynb
- [X] T011 [US1] Add CURRICULUM_CONFIG with stage step allocations {stage1_steps: 200, stage2_steps: 400} and difficulty weights {easy: 0.5, medium: 1.0, hard: 2.0} in notebooks/grpo_qwen3_4b.ipynb
- [X] T012 [US1] Implement difficulty-aware reward wrapper that multiplies correctness reward by difficulty weight before returning, used as the correctness_fn in GDPO reward_funcs list in notebooks/grpo_qwen3_4b.ipynb
- [X] T013 [US1] Implement zero-variance masking wrapper: after computing rewards for a group of G completions, detect if std==0 and return sentinel values that TRL masks out in notebooks/grpo_qwen3_4b.ipynb
- [X] T014 [US1] Rewrite training cell to two-stage curriculum: Stage 1 trains on easy+medium problems for stage1_steps, Stage 2 trains on all problems (with difficulty reweighting) for stage2_steps in notebooks/grpo_qwen3_4b.ipynb
- [X] T015 [US1] Replace inline fallback reward functions with import from make_gdpo_reward_fns in training.scripts.stem_rewards, keeping fallback only if import fails in notebooks/grpo_qwen3_4b.ipynb
- [X] T016 [US1] Update evaluation cell to report per-difficulty-tier accuracy alongside per-domain accuracy in notebooks/grpo_qwen3_4b.ipynb
- [X] T017 [US1] Update saved training_config.json to include curriculum_config, difficulty_distribution, and stage metrics in notebooks/grpo_qwen3_4b.ipynb

**Checkpoint**: GSPO with curriculum runs end-to-end on A100. Saves checkpoint for RAFT++.

---

## Phase 4: User Story 2 — RAFT++ Rejection Sampling (Priority: P1)

**Goal**: Create new notebook that generates completions, filters correct ones, and SFTs on them for 1-2 rounds.

**Independent Test**: Run raft_plus_qwen3_4b.ipynb on Colab A100 after GSPO. Per-domain accuracy improves >=1% over GSPO checkpoint.

### Implementation for User Story 2

- [X] T018 [US2] Create notebook with markdown header describing RAFT++ approach, pipeline position (Stage 3 of 5), references (arXiv 2504.11343) in notebooks/raft_plus_qwen3_4b.ipynb
- [X] T019 [US2] Add configuration cell: A100_VRAM_GB toggle, GSPO checkpoint paths (Drive + HF fallback), N_COMPLETIONS (16/32), MAX_ROUNDS=2, EARLY_STOP_THRESHOLD=0.01, domain list in notebooks/raft_plus_qwen3_4b.ipynb
- [X] T020 [US2] Add Drive mount + checkpoint resolution cell (reuse pattern from grpo notebook) in notebooks/raft_plus_qwen3_4b.ipynb
- [X] T021 [US2] Add data loading cell: load problems from HuggingFace, filter verifiable only in notebooks/raft_plus_qwen3_4b.ipynb
- [X] T022 [US2] Add model loading cell: load base model + GSPO adapter via PeftModel, apply fresh LoRA (r=16, alpha=32, dropout=0.0) for RAFT++ SFT in notebooks/raft_plus_qwen3_4b.ipynb
- [X] T023 [US2] Implement generate_and_filter() function: generate N completions per problem, verify each with verify_answer(), return list of correct (prompt, completion) pairs in notebooks/raft_plus_qwen3_4b.ipynb
- [X] T024 [US2] Implement domain_balance() function: oversample minority domains to match majority domain count, shuffle in notebooks/raft_plus_qwen3_4b.ipynb
- [X] T025 [US2] Implement RAFT++ round loop: for each round, call generate_and_filter, domain_balance, SFT for 1 epoch via SFTTrainer, evaluate accuracy, check early-stop in notebooks/raft_plus_qwen3_4b.ipynb
- [X] T026 [US2] Add per-domain evaluation cell (reuse pattern from grpo notebook) in notebooks/raft_plus_qwen3_4b.ipynb
- [X] T027 [US2] Add save cell: final adapter + raft_eval_metrics.json + training_config.json in notebooks/raft_plus_qwen3_4b.ipynb

**Checkpoint**: RAFT++ notebook runs end-to-end. Saves checkpoint for AdaSTaR.

---

## Phase 5: User Story 3 — AdaSTaR Self-Improvement (Priority: P1)

**Goal**: Upgrade existing star_loop.ipynb from vanilla STaR to AdaSTaR with adaptive problem selection.

**Independent Test**: Run star_loop.ipynb on Colab A100 after RAFT++. Verify MinHeap selects stale/hard problems, curriculum weight shifts over iterations, fewer total completions generated vs vanilla STaR.

### Implementation for User Story 3

- [X] T028 [US3] Update markdown header: change pipeline reference to "SFT -> GSPO -> RAFT++ -> AdaSTaR", add AdaSTaR references in notebooks/star_loop.ipynb
- [X] T029 [US3] Add A100_VRAM_GB toggle and update COMPLETIONS_PER_PROBLEM (16/32), SFT batch sizes accordingly in notebooks/star_loop.ipynb
- [X] T030 [US3] Update checkpoint path to load RAFT++ checkpoint instead of GSPO, with Drive + HF fallback in notebooks/star_loop.ipynb
- [X] T031 [US3] Fix lora_dropout from 0.05 to 0.0 for RL consistency in notebooks/star_loop.ipynb
- [X] T032 [US3] Add difficulty classification: import classify_difficulty from sort_curriculum.py, classify each problem, store difficulty in problem dict in notebooks/star_loop.ipynb
- [X] T033 [US3] Implement StalenessTracker class: init with problems, track last_correct_iteration per problem_id, compute priority_score = staleness_weight * (current_iter - last_correct) + difficulty_weight * difficulty_score in notebooks/star_loop.ipynb
- [X] T034 [US3] Implement adaptive_select_problems() using heapq: push all problems with negative priority (for max-heap behavior), pop top K problems for each iteration in notebooks/star_loop.ipynb
- [X] T035 [US3] Implement curriculum_weight() function: as overall accuracy increases, hard_weight grows via formula hard_weight = base * (1 + boost_factor * accuracy), easy_weight shrinks inversely in notebooks/star_loop.ipynb
- [X] T036 [US3] Modify star_iteration() to use adaptive_select_problems() instead of using all problems, and update StalenessTracker after each iteration in notebooks/star_loop.ipynb
- [X] T037 [US3] Update main loop to pass StalenessTracker between iterations, log staleness stats per iteration in notebooks/star_loop.ipynb
- [X] T038 [US3] Update saved metrics to include staleness_distribution, problems_selected_per_tier, total_completions_generated for efficiency tracking in notebooks/star_loop.ipynb

**Checkpoint**: AdaSTaR runs end-to-end with adaptive selection. Saves checkpoint for DPO.

---

## Phase 6: User Story 4 — Iterative DPO Polish (Priority: P2)

**Goal**: Create new notebook that generates preference pairs and runs DPO to polish reasoning quality.

**Independent Test**: Run dpo_polish_qwen3_4b.ipynb on Colab A100 after AdaSTaR. Correctness stays within 1% of AdaSTaR; format reward score improves >=10%.

### Implementation for User Story 4

- [X] T039 [US4] Create notebook with markdown header describing iterative DPO approach, pipeline position (Stage 5 of 5), references (arXiv 2503.12854) in notebooks/dpo_polish_qwen3_4b.ipynb
- [X] T040 [US4] Add configuration cell: A100_VRAM_GB toggle, AdaSTaR checkpoint paths, DPO_BETA=0.1, DPO_LR=5e-7, DPO_STEPS=200, PAIRS_PER_PROBLEM=8, MIN_PAIRS=50 in notebooks/dpo_polish_qwen3_4b.ipynb
- [X] T041 [US4] Add Drive mount + checkpoint resolution + data loading cells (reuse patterns) in notebooks/dpo_polish_qwen3_4b.ipynb
- [X] T042 [US4] Add model loading cell: load base + AdaSTaR adapter, apply fresh LoRA for DPO in notebooks/dpo_polish_qwen3_4b.ipynb
- [X] T043 [US4] Implement generate_preference_pairs(): for each problem, generate K completions, verify correctness, score format quality, select chosen (correct + highest format) and rejected (incorrect or lowest format), skip if no valid pair in notebooks/dpo_polish_qwen3_4b.ipynb
- [X] T044 [US4] Implement format preference pairs as HuggingFace Dataset with columns: prompt, chosen, rejected (matching TRL DPOTrainer expected format) in notebooks/dpo_polish_qwen3_4b.ipynb
- [X] T045 [US4] Add DPO training cell: DPOConfig + DPOTrainer with beta, lr, steps, bf16, save settings in notebooks/dpo_polish_qwen3_4b.ipynb
- [X] T046 [US4] Add guard: if total preference pairs < MIN_PAIRS, skip DPO and log warning, keep AdaSTaR checkpoint as final in notebooks/dpo_polish_qwen3_4b.ipynb
- [X] T047 [US4] Add dual evaluation cell: measure both correctness accuracy (must stay within 1%) AND format reward score (must improve 10%+) in notebooks/dpo_polish_qwen3_4b.ipynb
- [X] T048 [US4] Add save cell: final adapter + dpo_eval_metrics.json + training_config.json with full pipeline provenance in notebooks/dpo_polish_qwen3_4b.ipynb

**Checkpoint**: DPO notebook runs end-to-end. Final model ready for GGUF export.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Ensure consistency across all notebooks and final pipeline integrity.

- [X] T049 Verify all 4 notebooks (GSPO, RAFT++, AdaSTaR, DPO) have consistent A100_VRAM_GB toggle behavior in notebooks/
- [X] T050 Verify all 4 notebooks use consistent checkpoint loading pattern (Drive first, HF fallback) in notebooks/
- [X] T051 Verify all 4 notebooks save metrics JSON with consistent schema (domain_results, training_log, config) in notebooks/
- [X] T052 Update notebook headers to reflect final pipeline: SFT -> GSPO (curriculum) -> RAFT++ -> AdaSTaR -> DPO across all notebooks
- [X] T053 Run quickstart.md validation: verify documented execution order, configuration toggles, and metric file names match actual implementation in specs/014-advanced-training-pipeline/quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately
- **Phase 2 (Reward Infrastructure / US5)**: Depends on Phase 1 (reading existing code)
- **Phase 3 (GSPO Curriculum / US1)**: Depends on Phase 2 (uses make_gdpo_reward_fns)
- **Phase 4 (RAFT++ / US2)**: Depends on Phase 3 (loads GSPO checkpoint)
- **Phase 5 (AdaSTaR / US3)**: Depends on Phase 4 (loads RAFT++ checkpoint)
- **Phase 6 (DPO / US4)**: Depends on Phase 5 (loads AdaSTaR checkpoint)
- **Phase 7 (Polish)**: Depends on Phases 3-6

### User Story Dependencies

- **US5 (Reward Infrastructure)**: Foundation — no story dependencies. BLOCKS US1.
- **US1 (GSPO Curriculum)**: Depends on US5. Produces checkpoint for US2.
- **US2 (RAFT++)**: Depends on US1 checkpoint. Produces checkpoint for US3.
- **US3 (AdaSTaR)**: Depends on US2 checkpoint. Produces checkpoint for US4.
- **US4 (DPO)**: Depends on US3 checkpoint. Final stage.

Note: While the pipeline is sequential (each stage needs the previous checkpoint), each notebook is **independently testable** — you can run any notebook with a suitable input checkpoint and verify its metrics.

### Within Each User Story

- Configuration cells first
- Data loading before model loading
- Model loading before training logic
- Training before evaluation
- Evaluation before save

### Parallel Opportunities

- **Within Phase 2**: T004-T008 all modify stem_rewards.py sequentially (same file, no parallelism)
- **Within Phase 3**: T009-T011 (config/data cells) can be done in parallel with T012-T013 (reward wrappers)
- **Within Phase 4**: T018-T021 (setup cells) can be done in parallel as they're independent notebook cells
- **Within Phase 5**: T028-T032 (config updates) can be done before T033-T035 (new AdaSTaR logic)
- **Within Phase 6**: T039-T042 (setup cells) can be done in parallel
- **Cross-phase**: Phases are sequential due to checkpoint dependencies

---

## Parallel Example: User Story 2 (RAFT++)

```bash
# These setup cells can be created in parallel (independent notebook cells):
Task: "T018 Create notebook header in notebooks/raft_plus_qwen3_4b.ipynb"
Task: "T019 Add configuration cell in notebooks/raft_plus_qwen3_4b.ipynb"
Task: "T020 Add Drive mount cell in notebooks/raft_plus_qwen3_4b.ipynb"
Task: "T021 Add data loading cell in notebooks/raft_plus_qwen3_4b.ipynb"

# Then sequentially:
Task: "T022 Add model loading cell"
Task: "T023-T025 Implement core RAFT++ logic"
Task: "T026-T027 Evaluation and save"
```

---

## Implementation Strategy

### MVP First (Phase 2 + Phase 3 = Reward Infra + GSPO Curriculum)

1. Complete Phase 1: Setup (verify existing code)
2. Complete Phase 2: Update stem_rewards.py (foundation)
3. Complete Phase 3: GSPO with curriculum learning
4. **STOP and VALIDATE**: Run GSPO notebook on Colab, verify curriculum stages in logs, check +3% accuracy improvement
5. This alone delivers the highest-impact improvement

### Incremental Delivery

1. Phase 2 + Phase 3 → GSPO with curriculum → validate on Colab
2. Add Phase 4 → RAFT++ → validate accuracy improvement over GSPO
3. Add Phase 5 → AdaSTaR → validate efficiency gains + accuracy
4. Add Phase 6 → DPO polish → validate format quality improvement
5. Phase 7 → Polish and consistency check
6. Each stage adds measurable value independently

### Estimated Timeline (per Colab session)

| Phase | Development | Colab Training | Total |
|-------|-------------|----------------|-------|
| Phase 2 (Rewards) | 30 min | N/A | 30 min |
| Phase 3 (GSPO) | 1 hr | 4-6 hrs | 5-7 hrs |
| Phase 4 (RAFT++) | 1 hr | 2-4 hrs | 3-5 hrs |
| Phase 5 (AdaSTaR) | 1 hr | 3-5 hrs | 4-6 hrs |
| Phase 6 (DPO) | 1 hr | 1-2 hrs | 2-3 hrs |
| Phase 7 (Polish) | 30 min | N/A | 30 min |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each notebook is independently testable with a suitable input checkpoint
- Commit after each phase completion
- Stop at any checkpoint to validate independently on Colab
- All reward values in [0, 1] — no negative penalties anywhere in the pipeline
