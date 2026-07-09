# Feature Specification: Advanced STEM Training Pipeline with Hybrid RL Dataset + SAPO/ReDit Optimizations

**Feature Branch**: `014-advanced-training-pipeline`
**Created**: 2026-02-12
**Updated**: 2026-02-13
**Status**: Draft
**Input**: Comprehensive training pipeline for Qwen3-4B-Instruct-2507 STEM tutoring model. Hybrid RL dataset (~15K verifiable problems from 5 sources), SAPO loss, reward dithering, Dr. GRPO bias correction, GVM-RAFT dynamic allocation, curriculum learning, and 5-stage pipeline optimized per 2025-2026 RL research.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Hybrid RL Dataset Preparation (Priority: P1)

A researcher runs the data preparation script to create a combined RL training dataset from 5 sources: GSM8K (~7,400 math), MATH Hendrycks (~5,000 competition math), OlympiadBench physics (~236), ruMMLU STEM (~1,500 Russian MC), and filtered current MITS data (~800). The script normalizes all problems to a unified schema, classifies difficulty, balances sources, deduplicates, and outputs a single JSONL file ready for all pipeline stages.

**Why this priority**: Without high-quality, diverse RL data, no training algorithm can produce good results. The current SFT-derived dataset has ~99% "easy" problems and zero reward variance — fixing data is the highest-leverage improvement.

**Independent Test**: Run `python -m training.scripts.prepare_rl_dataset --output training/data/rl_combined.jsonl` locally. Verify output has ~15K problems, math ~83%, correct difficulty distribution (~30/40/30%), zero empty answers.

**Acceptance Scenarios**:

1. **Given** access to HuggingFace datasets, **When** the script runs, **Then** it downloads GSM8K, MATH, OlympiadBench, ruMMLU, and current MITS data, normalizing each to `{prompt, answer, domain, difficulty, source, answer_type}` schema.
2. **Given** combined raw data from all sources, **When** balancing is applied, **Then** each source is capped at its target count with stratified difficulty sampling preserving easy/medium/hard ratios.
3. **Given** the complete balanced dataset, **When** `--stats-only` is passed, **Then** the script prints domain/difficulty/source/answer_type statistics without saving files.
4. **Given** ruMMLU MC problems, **When** formatting prompts, **Then** answer choices are shuffled with per-problem deterministic seed to prevent positional bias.

---

### User Story 2 - GSPO Training with SAPO + Curriculum (Priority: P1)

A researcher runs the GSPO notebook on Colab A100 with Qwen3-4B-Instruct-2507 base model. Training uses SAPO loss (smooth adaptive clipping developed by Qwen team), reward dithering (Gaussian noise on binary rewards for better gradient flow), Dr. GRPO bias correction (constant length normalization), and two-stage curriculum learning with difficulty-aware advantage reweighting.

**Why this priority**: GSPO is the core RL stage where reasoning quality is trained. SAPO, ReDit, and Dr. GRPO are the three highest-impact algorithmic improvements identified by research (arXiv:2511.20347, arXiv:2506.18631, arXiv:2503.20783).

**Independent Test**: Run grpo_qwen3_4b.ipynb on Colab A100. Verify SAPO loss is active, reward dithering produces non-binary reward values, difficulty reweighting is applied, zero-variance masking works, and reward variance > 0 after 50 steps.

**Acceptance Scenarios**:

1. **Given** the hybrid RL dataset loaded from Drive JSONL, **When** GSPO training starts, **Then** it uses `loss_type="sapo"` with temperature parameters for smooth clipping.
2. **Given** binary correctness rewards (0.0 or 1.0), **When** reward dithering is active, **Then** small Gaussian noise (sigma=0.05) is added, producing continuous rewards in ~[-0.15, 1.15] range centered on true values.
3. **Given** a problem with answer_type="mc_letter", **When** formatting the prompt, **Then** the system uses the MC-specific system prompt ("Проанализируй задачу...") instead of the calc system prompt.
4. **Given** GSPO with Dr. GRPO correction active, **When** computing advantages, **Then** per-response length normalization uses a constant (max_completion_length) instead of actual response length, preventing length exploitation.

---

### User Story 3 - RAFT++ with GVM Dynamic Allocation (Priority: P1)

A researcher runs the RAFT++ notebook after GSPO. Instead of generating a fixed number of completions per problem, the notebook first runs a pilot round (4 completions) to estimate per-problem difficulty, then dynamically allocates the remaining completion budget — harder problems get more attempts. Incorrect completions are saved for DPO reuse.

**Why this priority**: GVM-RAFT achieves 2-4x speedup over fixed-allocation RAFT++ (arXiv:2504.11343). Saving negatives for DPO eliminates redundant generation in the final pipeline stage.

**Independent Test**: Run raft_plus_qwen3_4b.ipynb on Colab A100. Verify that completion counts vary per problem based on pilot results, that correct completions are used for SFT, and that incorrect completions are saved to a separate file for DPO.

**Acceptance Scenarios**:

1. **Given** a set of verifiable problems and a total completion budget, **When** the pilot round estimates per-problem pass rates, **Then** problems with lower pass rates receive proportionally more completions from the remaining budget.
2. **Given** verified-correct completions from generation, **When** SFT training runs, **Then** the model is fine-tuned only on correct completions with domain balancing.
3. **Given** incorrect completions generated during RAFT++, **When** the round completes, **Then** incorrect completions are saved to a JSONL file alongside their prompts and ground-truth answers for DPO reuse.

---

### User Story 4 - AdaSTaR Adaptive Self-Improvement (Priority: P2)

A researcher runs the AdaSTaR notebook which uses priority-based problem selection (staleness + difficulty), adaptive curriculum weighting, and domain-balanced SFT across 3 iterations with early stopping.

**Why this priority**: AdaSTaR addresses vanilla STaR stalling on hard problems and reduces FLOPs by ~58%.

**Independent Test**: Run star_loop.ipynb on Colab A100 after RAFT++. Verify MinHeap prioritization selects stale/hard problems first, curriculum weighting shifts toward harder problems over iterations, and early stopping works.

**Acceptance Scenarios**:

1. **Given** problems with tracked staleness scores, **When** selecting for the next iteration, **Then** problems with higher staleness and higher difficulty are selected with higher probability.
2. **Given** accuracy improvement below threshold between consecutive iterations, **When** the iteration completes, **Then** training stops early and saves the final checkpoint.

---

### User Story 5 - DPO Polish with RAFT++ Negatives (Priority: P2)

A researcher runs the DPO notebook after AdaSTaR. The notebook loads pre-generated incorrect completions from RAFT++ as "rejected" samples (instead of regenerating them), pairs them with correct completions as "chosen", and runs DPO to polish reasoning quality.

**Why this priority**: Reusing RAFT++ negatives (arXiv:2505.24850) eliminates redundant generation and provides diverse rejected samples.

**Independent Test**: Run dpo_polish_qwen3_4b.ipynb on Colab A100. Verify that RAFT++ negatives are loaded and used as rejected samples, DPO training converges, and format quality improves while accuracy stays within 1%.

**Acceptance Scenarios**:

1. **Given** saved incorrect completions from RAFT++ and correct completions generated fresh, **When** building preference pairs, **Then** the DPO dataset pairs correct+well-structured (chosen) vs incorrect (rejected) for the same prompts.
2. **Given** DPO training completes, **Then** format reward score improves by at least 10% while correctness accuracy degrades by no more than 1%.
3. **Given** fewer than 50 valid preference pairs, **When** the guard check runs, **Then** DPO is skipped with a warning and the AdaSTaR checkpoint is used as final.

---

### User Story 6 - Updated Reward Infrastructure (Priority: P1)

The stem_rewards.py module provides GDPO-compatible reward functions with answer-type-aware scoring (calc, MC, physics-with-units), reward dithering support, and the verify_answers.py module supports GSM8K `####` answer format extraction.

**Why this priority**: Reward infrastructure is a foundation dependency. Incorrect reward signals propagate errors through the entire pipeline.

**Independent Test**: Import stem_rewards functions and test: correct calc answers get ~1.0 (with dithering noise), wrong get ~0.0, MC answers are verified by letter, format scoring routes by answer_type.

**Acceptance Scenarios**:

1. **Given** a problem with answer_type="mc_letter", **When** the correctness function evaluates a completion, **Then** it routes through verify_mc() for letter comparison.
2. **Given** binary correctness reward with dithering enabled, **When** rewards are computed, **Then** Gaussian noise (mean=0, sigma configurable) is added to provide smooth gradient landscape.
3. **Given** a completion in GSM8K format with "#### 42", **When** extract_answer() processes it, **Then** it correctly extracts "42" as the answer.

---

### Edge Cases

- What happens when a HuggingFace dataset is unavailable during preparation? The loader logs a warning and continues with remaining sources — partial datasets are supported.
- What happens when all G completions for a prompt get identical reward? Zero-variance masking returns NaN, and TRL's masked loss skips the group.
- What happens when GVM pilot round returns 0% pass rate for a problem? The problem receives maximum completion allocation (hardest = most attempts).
- What happens when RAFT++ negatives file doesn't exist for DPO? DPO falls back to generating its own completions for rejected samples.
- What happens when the user selects A100 80GB but actual GPU is 40GB? The notebook detects actual VRAM and falls back to the lower preset with a warning.
- What happens when ruMMLU answer index is out of range? The problem is skipped with a log message during dataset preparation.

## Requirements *(mandatory)*

### Functional Requirements

#### Data Preparation
- **FR-001**: System MUST download and normalize problems from GSM8K (openai/gsm8k), extracting answers after `####` and classifying difficulty by solution step count (1-3=easy, 4-6=medium, 7+=hard).
- **FR-002**: System MUST download and normalize problems from MATH (hendrycks/competition_math), extracting `\boxed{}` answers and mapping Level 1-5 to easy/medium/hard.
- **FR-003**: System MUST download and normalize OlympiadBench physics open-ended problems, all classified as "hard" with answer_type="numeric_with_unit".
- **FR-004**: System MUST download and normalize ruMMLU STEM subjects (17 subjects across math/physics/chemistry/biology/cs), formatting as MC with deterministic-seed shuffled choices.
- **FR-005**: System MUST filter current MITS dataset to keep only verifiable problems with numeric/boxed answers, excluding conceptual prompts ("explain", "prove", "derive").
- **FR-006**: System MUST balance the combined dataset by source with stratified difficulty sampling, using configurable target counts per source.
- **FR-007**: System MUST deduplicate problems by prompt text before saving.
- **FR-008**: System MUST output unified JSONL with schema: `{prompt, answer, domain, difficulty, source, answer_type}` where answer_type is one of: numeric, latex_boxed, mc_letter, numeric_with_unit.

#### GSPO Training
- **FR-009**: GSPO notebook MUST use SAPO loss type (`loss_type="sapo"`) for smooth adaptive clipping.
- **FR-010**: GSPO notebook MUST apply reward dithering (Gaussian noise, configurable sigma) to binary correctness rewards before advantage computation.
- **FR-011**: GSPO notebook MUST use Qwen3-4B-Instruct-2507 as base model across all pipeline stages.
- **FR-012**: GSPO notebook MUST implement Dr. GRPO bias correction using constant length normalization (max_completion_length) instead of per-response length.
- **FR-013**: GSPO notebook MUST implement two-stage curriculum: Stage 1 (easy+medium) and Stage 2 (all with difficulty reweighting).
- **FR-014**: GSPO notebook MUST mask zero-variance sample groups where all G completions received identical reward.
- **FR-015**: GSPO notebook MUST route MC problems to MC-specific system prompt and calc problems to calc-specific system prompt.
- **FR-016**: GSPO notebook MUST require TRL >= 0.27.0 for SAPO support.

#### RAFT++ Training
- **FR-017**: RAFT++ notebook MUST implement GVM-style dynamic completion allocation: pilot round (4 completions) estimates difficulty, remaining budget allocated proportionally.
- **FR-018**: RAFT++ notebook MUST save incorrect completions to a JSONL file for DPO stage reuse.
- **FR-019**: RAFT++ notebook MUST support multiple rounds with early stopping below accuracy improvement threshold.

#### AdaSTaR Training
- **FR-020**: STaR notebook MUST use adaptive problem selection based on staleness + difficulty scoring.
- **FR-021**: STaR notebook MUST implement curriculum weighting that increases hard problem proportion as accuracy grows.

#### DPO Training
- **FR-022**: DPO notebook MUST load RAFT++ saved negatives as "rejected" samples when available.
- **FR-023**: DPO notebook MUST skip training with a warning when fewer than 50 valid preference pairs exist.

#### Reward Infrastructure
- **FR-024**: stem_rewards.py MUST provide answer-type-aware format scoring: calc (boxed+steps), MC (letter pattern+reasoning), physics (boxed+units).
- **FR-025**: stem_rewards.py MUST support configurable reward dithering with Gaussian noise on correctness rewards.
- **FR-026**: verify_answers.py MUST extract answers in GSM8K `####` format between `\boxed{}` and "Ответ:" checks.
- **FR-027**: All notebooks MUST load data via fallback chain: Drive JSONL → HF "rl" config → HF "gspo" config.

#### Cross-Cutting
- **FR-028**: All notebooks MUST include A100_VRAM_GB toggle (40/80) adjusting batch sizes and generation counts.
- **FR-029**: All notebooks MUST support Colab disconnect recovery via checkpoint-based training resumption.
- **FR-030**: All notebooks MUST save per-domain evaluation metrics and training config as JSON alongside checkpoints.

### Key Entities

- **RL Problem**: A verifiable STEM problem with `{prompt, answer, domain, difficulty, source, answer_type}`. Sources: gsm8k, math_hendrycks, olympiad_bench, rummlu, current_filtered. Answer types: numeric, latex_boxed, mc_letter, numeric_with_unit.
- **Model Checkpoint**: A LoRA adapter with training config JSON. Pipeline flow: Light SFT → GSPO → RAFT++ → AdaSTaR → DPO. Each stage loads previous stage's checkpoint.
- **Reward Function**: Callable evaluating completion quality. GDPO-style: separate correctness (binary + dithering) and format (answer-type-aware) functions, normalized independently.
- **Preference Pair**: (chosen, rejected) completions for DPO. Chosen = correct + well-structured; rejected = incorrect (from RAFT++ negatives) or poorly-structured.
- **Staleness Score**: Per-problem metric for AdaSTaR tracking iterations since last correct generation.
- **Pilot Round Results**: Per-problem pass rate from GVM-RAFT pilot (4 completions), used to allocate remaining completion budget.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The hybrid RL dataset contains 12,000-15,000 problems with math ~83%, physics ~5%, science MC ~5%, Russian STEM ~7%, and zero empty answers.
- **SC-002**: Difficulty distribution is approximately 30% easy, 40% medium, 30% hard across the combined dataset.
- **SC-003**: The full pipeline (Light SFT → GSPO → RAFT++ → AdaSTaR → DPO) produces a model scoring at least 15% higher on STEM evaluation than the SFT-only baseline.
- **SC-004**: GSPO with SAPO loss achieves equal or better convergence compared to standard GRPO loss at the same step count.
- **SC-005**: Reward dithering produces non-zero reward variance for at least 90% of prompt groups (vs ~50% without dithering).
- **SC-006**: GVM-RAFT completes RAFT++ stage in at least 50% fewer total completions compared to fixed-allocation RAFT++.
- **SC-007**: DPO polish maintains correctness within 1% of AdaSTaR checkpoint while improving format score by at least 10%.
- **SC-008**: Each pipeline stage notebook runs end-to-end on Google Colab A100 40GB without out-of-memory errors.
- **SC-009**: Per-domain evaluation metrics are saved as JSON after each stage, enabling accuracy progression tracking across the pipeline.

## Assumptions

- Qwen3-4B-Instruct-2507 is available on HuggingFace and compatible with Unsloth's FastLanguageModel.
- TRL >= 0.27.0 supports `loss_type="sapo"` and `sapo_temperature_neg`/`sapo_temperature_pos` parameters.
- HuggingFace datasets (GSM8K, MATH, OlympiadBench, ruMMLU) are publicly accessible.
- Google Colab Pro+ provides A100 40/80GB GPU instances with 4-8 hours runtime per stage.
- Pipeline stages are run sequentially by the researcher (not automated end-to-end).
- The existing SFT checkpoint may need retraining on the Instruct base (separate task from this spec).

## Scope Boundaries

### In Scope
- Hybrid RL dataset preparation script with 5 HuggingFace sources
- SAPO loss integration in GSPO notebook
- Reward dithering (ReDit) in stem_rewards.py
- Dr. GRPO bias correction in GSPO notebook
- GVM-RAFT dynamic allocation in RAFT++ notebook
- RAFT++ negative saving for DPO reuse
- Base model switch to Qwen3-4B-Instruct-2507 across all notebooks
- TRL >= 0.27.0 pinning across all notebooks
- Answer-type-aware reward scoring (calc, MC, physics-with-units)
- GSM8K `####` answer extraction in verify_answers.py
- Drive JSONL → HF "rl" → HF "gspo" data loading fallback chain
- Light SFT stage (brief adaptation of Instruct model to Russian STEM tutoring)

### Out of Scope
- Process Reward Model (PRM) training or inference-time PRM-guided selection
- TEMPO prefix tree credit assignment (Tier 3 — future improvement)
- BRIDGE cooperative SFT+RL (requires custom TRL integration)
- Automated end-to-end pipeline orchestration
- Model export to GGUF/Ollama deployment format
- Multi-GPU or distributed training support
- CISPO loss (alternative to SAPO — can be tested separately)

## References

- [SAPO: Soft Adaptive Policy Optimization (arXiv:2511.20347)](https://arxiv.org/abs/2511.20347) — Qwen team, smooth clipping
- [ReDit: Reward Dithering (arXiv:2506.18631)](https://arxiv.org/abs/2506.18631) — 4% accuracy, 10x convergence speed
- [Dr. GRPO (arXiv:2503.20783)](https://arxiv.org/abs/2503.20783) — Token aggregation bias correction
- [GVM-RAFT / Minimalist Approach (arXiv:2504.11343)](https://arxiv.org/abs/2504.11343) — 2-4x RAFT speedup
- [Harnessing Negative Signals (arXiv:2505.24850)](https://arxiv.org/abs/2505.24850) — Reusing incorrect completions
- [GSPO (arXiv:2507.18071)](https://arxiv.org/abs/2507.18071) — Group Sequence Policy Optimization
- [DAPO (arXiv:2503.14476)](https://arxiv.org/abs/2503.14476) — Clip-Higher, Dynamic Sampling
- [VAPO (arXiv:2504.05118)](https://arxiv.org/abs/2504.05118) — Epsilon bounds
- [GDPO (arXiv:2601.05242)](https://arxiv.org/abs/2601.05242) — Decoupled multi-reward normalization
- [GRPO-LEAD (arXiv:2504.09696)](https://arxiv.org/abs/2504.09696) — Difficulty-aware curriculum RL
- [Revisiting GRPO (arXiv:2505.22257)](https://arxiv.org/abs/2505.22257) — Zero-variance masking
- [GFPO (arXiv:2508.09726)](https://arxiv.org/abs/2508.09726) — Group Filtered Policy Optimization
- [Qwen3 Technical Report (arXiv:2505.09388)](https://arxiv.org/abs/2505.09388)
- [RLVR Sampling Efficiency (arXiv:2504.13837)](https://arxiv.org/abs/2504.13837) — NeurIPS 2025
- [Light-R1 (arXiv:2503.10460)](https://arxiv.org/abs/2503.10460) — ACL Industry 2025
