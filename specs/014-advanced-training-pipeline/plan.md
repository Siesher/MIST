# Implementation Plan: Advanced STEM Training Pipeline

**Branch**: `014-advanced-training-pipeline` | **Date**: 2026-02-12 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/014-advanced-training-pipeline/spec.md`

## Summary

Upgrade the Qwen3-4B STEM training pipeline from a basic SFT->GSPO->STaR flow to a research-backed 5-stage pipeline: SFT -> GSPO (curriculum + zero-variance masking) -> RAFT++ -> AdaSTaR -> Iterative DPO. Update reward infrastructure to GDPO-compatible decoupled normalization with no negative penalties. Target: Colab A100 40/80GB.

## Technical Context

**Language/Version**: Python 3.11+ (Jupyter notebooks on Google Colab)
**Primary Dependencies**: Unsloth, TRL (GRPOTrainer, DPOTrainer, SFTTrainer), PEFT, Transformers, bitsandbytes, datasets, sympy, chempy
**Storage**: Google Drive (checkpoints), HuggingFace Hub (datasets, adapters), local filesystem
**Testing**: Manual evaluation via per-domain accuracy metrics + STEM-30/MATH-100 benchmarks
**Target Platform**: Google Colab Pro+ with NVIDIA A100 40GB or 80GB
**Project Type**: ML training pipeline (Jupyter notebooks + Python utility modules)
**Performance Goals**: +15% STEM-30 accuracy over SFT baseline; each notebook completes in <8 hours on A100
**Constraints**: A100 40GB VRAM minimum; 4-bit QLoRA; final adapter must fit RTX 2080 8GB for inference
**Scale/Scope**: ~500-2000 STEM problems, 5 domains, 5 pipeline stages

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Socratic Pedagogy | PASS | Training improves reasoning quality for Socratic tutoring. Format reward encourages step-by-step explanation style. |
| II. Multi-Agent Architecture | N/A | Training pipeline is separate from inference agent architecture. |
| III. Knowledge-Grounded Responses | PASS | Training uses curated STEM problem banks with verified answers. |
| IV. Hardware Constraint Compliance | PASS | Training on A100 (cloud); final adapter is QLoRA-compatible and deployable on RTX 2080 8GB via 4-bit quantization. |
| V. Metrics-Driven Quality | PASS | Every pipeline stage outputs per-domain evaluation metrics as JSON. STEM-30 and MATH-100 benchmarks used for final evaluation. |
| VI. STEM Domain Coverage | PASS | All 5 domains (math, physics, chemistry, biology, CS) covered in training data and evaluation. Domain-balanced sampling in RAFT++ and AdaSTaR. |

**Gate result**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/014-advanced-training-pipeline/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0: research decisions
├── data-model.md        # Phase 1: entity/data design
├── quickstart.md        # Phase 1: implementation quickstart
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
notebooks/
├── sft_qwen3_4b.ipynb           # Stage 1: SFT (existing, no changes)
├── grpo_qwen3_4b.ipynb          # Stage 2: GSPO with curriculum (MODIFY)
├── raft_plus_qwen3_4b.ipynb     # Stage 3: RAFT++ rejection sampling (NEW)
├── star_loop.ipynb              # Stage 4: AdaSTaR self-improvement (MODIFY)
└── dpo_polish_qwen3_4b.ipynb    # Stage 5: Iterative DPO polish (NEW)

training/scripts/
├── stem_rewards.py              # Reward functions (MODIFY: GDPO-compatible)
├── sort_curriculum.py           # Difficulty classifier (existing, no changes)
└── verify_answers.py            # Hybrid verifier (existing, no changes)
```

**Structure Decision**: ML training pipeline using Jupyter notebooks for interactive Colab execution, backed by shared Python utility modules in `training/scripts/`. No web/mobile structure needed.

## Implementation Phases

### Phase A: Reward Infrastructure (FR-010, FR-011) — Foundation

Update `training/scripts/stem_rewards.py`:
1. Change wrong answer penalty from -0.5 to 0.0 across all compute_reward paths
2. Add `make_gdpo_reward_fns(problems, tokenizer)` function that returns `[correctness_fn, format_fn]` — two separate callables matching TRL GRPOTrainer signature
3. Correctness function: uses existing verify_answers.py, returns 1.0 (correct) or 0.0 (wrong)
4. Format function: scores `\boxed{}` presence + step-by-step markers + reasonable length, returns [0, 1]
5. Keep backward-compatible `make_reward_fn()` for other notebooks that haven't migrated

### Phase B: GSPO Curriculum (FR-001 to FR-004) — Existing Notebook Enhancement

Modify `notebooks/grpo_qwen3_4b.ipynb`:
1. Add curriculum classification cell: import `classify_difficulty` from `sort_curriculum.py`, classify each problem as easy/medium/hard
2. Implement staged training: Stage 1 (200 steps) on easy+medium; Stage 2 (400 steps) on all tiers
3. Add difficulty-aware advantage reweighting: weight multipliers `{easy: 0.5, medium: 1.0, hard: 2.0}` applied to advantages before policy update. Implemented via custom reward wrapper that embeds difficulty weight.
4. Add zero-variance masking: wrap reward functions to detect groups where all G completions got identical reward; return NaN or sentinel value that TRL's masking handles. Alternatively, use TRL's `mask_truncated_completions` + custom filtering.
5. Import `make_gdpo_reward_fns` from updated `stem_rewards.py` instead of inline fallback

### Phase C: RAFT++ Notebook (FR-005, FR-006) — New

Create `notebooks/raft_plus_qwen3_4b.ipynb`:
1. Config cell: A100_VRAM_GB toggle, GSPO checkpoint path, N completions per problem (default 16 for 40GB, 32 for 80GB), rounds (default 2), early-stop threshold
2. Load GSPO checkpoint + problems from HuggingFace
3. For each round:
   a. Generate N completions per problem (batched inference)
   b. Verify each completion using hybrid verifier (verify_answers.py)
   c. Keep only correct completions
   d. Domain-balance the filtered set
   e. SFT for 1 epoch on filtered data using SFTTrainer
   f. Evaluate per-domain accuracy on held-out set
   g. If improvement < threshold, stop early
4. Save final adapter + metrics JSON

### Phase D: AdaSTaR Upgrade (FR-007, FR-008) — Existing Notebook Modification

Modify `notebooks/star_loop.ipynb`:
1. Add staleness tracking: dict mapping problem_id -> (last_correct_iteration, difficulty)
2. Replace uniform random selection with priority scoring: `priority = staleness_weight * staleness + difficulty_weight * difficulty_score`
3. Implement MinHeap-based selection: use `heapq` with negative priority for highest-first selection
4. Add curriculum weighting: as overall accuracy increases, shift sampling probability toward harder problems. Formula: `hard_weight = base_hard_weight * (1 + accuracy_boost_factor * current_accuracy)`
5. Update pipeline reference from "SimPO -> GSPO -> STaR" to "GSPO -> RAFT++ -> AdaSTaR"
6. Add A100_VRAM_GB toggle
7. Fix: use `lora_dropout=0.0` for RL consistency

### Phase E: Iterative DPO Notebook (FR-009) — New

Create `notebooks/dpo_polish_qwen3_4b.ipynb`:
1. Config cell: A100_VRAM_GB toggle, AdaSTaR checkpoint path, DPO hyperparameters (beta=0.1, lr=5e-7)
2. Load AdaSTaR checkpoint + problems
3. Preference pair generation:
   a. Generate 8 completions per problem
   b. Verify correctness + score format quality
   c. Chosen = correct completion with highest format score
   d. Rejected = incorrect completion (or correct but lowest format score)
   e. Minimum: need at least 1 correct + 1 incorrect/poor per problem
   f. Skip problems without valid pairs
4. DPO training using TRL DPOTrainer for 200 steps
5. Evaluate: accuracy must stay within 1% of AdaSTaR; format score should improve 10%+
6. Save final adapter + metrics JSON

### Phase F: Cross-Notebook Integration (FR-012 to FR-014)

1. Add A100_VRAM_GB toggle to all new/modified notebooks (already in GSPO)
2. Standardize checkpoint loading: try Drive path first, fall back to HF repo
3. Standardize metrics saving: JSON with domain_results, training_log, config sections
4. Update pipeline stage references in all notebook headers
5. Verify verify_answers.py integration works in all notebooks

## Complexity Tracking

No constitution violations to justify.
