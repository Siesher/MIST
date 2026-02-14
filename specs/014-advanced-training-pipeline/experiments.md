# Experiment Log: Advanced STEM Training Pipeline

**Feature**: 014-advanced-training-pipeline
**Period**: 2026-02-12 — 2026-02-13 (ongoing)
**Hardware**: Google Colab Pro+, NVIDIA A100 80GB
**Model**: Qwen3-4B-Instruct-2507 (base) + SFT adapter (Siesher/mits-qwen3-4b-sft)

## Table of Contents

1. [Dataset Preparation](#1-dataset-preparation)
2. [GSPO Training — Error Resolution](#2-gspo-training--error-resolution)
3. [Hyperparameter Selection Rationale](#3-hyperparameter-selection-rationale)
4. [Implemented Techniques Summary](#4-implemented-techniques-summary)
5. [Key Discoveries](#5-key-discoveries)

---

## 1. Dataset Preparation

### 1.1 Objective

Create a hybrid RL dataset optimized for verifiable reward signal, replacing the SFT-derived dataset that had ~99.4% "easy" problems and zero reward variance.

### 1.2 Data Sources & Fallback Strategy

| Source | HuggingFace ID | Status | Notes |
|--------|----------------|--------|-------|
| GSM8K | `openai/gsm8k` | OK | 7,400 grade-school math problems, answer after `####` |
| MATH (Hendrycks) | `hendrycks/competition_math` | **403 Forbidden** | Gated dataset. Fallback chain implemented |
| MATH fallback 1 | `lighteval/MATH` | Tested | Works but may differ in formatting |
| MATH fallback 2 | `DigitalLearningGmbH/MATH-lighteval` | **Used** | Ungated mirror, 4,985 problems |
| OlympiadBench | `Hothan/OlympiadBench` | OK | 232 physics problems (OE_TO_physics_en_COMP) |
| ruMMLU | `NLPCoreTeam/mmlu_ru` | **Deprecated** | `trust_remote_code=True` also deprecated in datasets lib |
| ruMMLU replacement | `CohereLabs/Global-MMLU` config `"ru"` | **Used** | Standard parquet format, 1,495 STEM problems |
| Current MITS | `Siesher/mits-stem-training-data` | OK | 91 problems after filtering |

### 1.3 ruMMLU Migration Details

Original `NLPCoreTeam/mmlu_ru` used a custom dataset script (`mmlu_ru.py`) that was deprecated by HuggingFace. The `trust_remote_code=True` parameter was also removed from the `datasets` library. Solution: migrate to `CohereLabs/Global-MMLU` which uses standard parquet format with `"ru"` config.

**Schema difference:**

| Field | NLPCoreTeam/mmlu_ru | CohereLabs/Global-MMLU |
|-------|---------------------|------------------------|
| Choices | `choices: list[str]` (4 items) | `option_a`, `option_b`, `option_c`, `option_d` |
| Answer | `answer: int` (0-3 index) | `answer: str` ("A"-"D" letter) |
| Config | single split | language configs (`"ru"`, `"en"`, etc.) |

### 1.4 Final Dataset Statistics

```
Total:         14,203 problems
Sources:       gsm8k=7400, math_hendrycks=4985, rummlu=1495, olympiad_bench=232, current=91
Domains:       math=12931 (91.0%), physics=545 (3.8%), biology=307 (2.2%), cs=258 (1.8%), chemistry=162 (1.1%)
Difficulty:    easy=5673 (39.9%), medium=4946 (34.8%), hard=3584 (25.2%)
Answer types:  numeric=7491, latex_boxed=4985, mc_letter=1495, numeric_with_unit=232
Empty answers: 0
```

**Output**: `training/data/rl_combined.jsonl` (unified schema)

### 1.5 Script: `training/scripts/prepare_rl_dataset.py`

Key design decisions:
- **Fallback chain** for gated datasets: try primary → secondary → tertiary source with try/except per loader
- **Per-problem seed** for MC choice shuffling (prevents positional bias, reproducible)
- **Difficulty mapping**: GSM8K by step count (1-3=easy, 4-6=medium, 7+=hard); MATH by level field (1-2=easy, 3=medium, 4-5=hard); OlympiadBench all hard; ruMMLU by subject prefix (elementary_*=easy, high_school_*=medium, college_*=hard)

---

## 2. GSPO Training — Error Resolution

### 2.1 Chronological Error Log

Training on Google Colab A100 80GB with Unsloth + TRL 0.28.0.

| # | Error | Root Cause | Fix | Status |
|---|-------|------------|-----|--------|
| 1 | `TypeError: max_prompt_length` | Unsloth wraps GRPOConfig `__init__`, blocks newer TRL params | `inspect.signature` + `setattr` post-init injection | Resolved |
| 2 | `TypeError: use_dr_grpo` | Assumed Dr. GRPO was a boolean flag | Discovered it's `loss_type="dr_grpo"` (mutually exclusive) | Resolved |
| 3 | `OutOfMemoryError` (A100 40GB) | Unsloth forces `batch_size=G`; G=16 too large for 40GB | Switched to A100 80GB; reduced MAX_COMPLETION to 768 | Resolved |
| 4 | `NameError: has_images` | Unsloth compiled cache uses `has_images` variable undefined for text-only models | Inject `has_images=False` into function `__globals__` | Resolved |
| 5 | `RecursionError` | Monkey-patch wrapping method applied twice (re-run cell) | Made patch idempotent via marker attribute check | Resolved |
| 6 | `cudaErrorIllegalAddress` in `fast_rope_embedding` | G=16 + MAX_COMPLETION=1024 + importance_sampling = double forward pass OOM | Reduced MAX_COMPLETION to 768 for A100 80GB | Resolved |
| 7 | `OverflowError` in `batch_decode` | Generated token IDs contain values > uint32 max | Patch `tokenizer.batch_decode` to clamp IDs | Resolved |
| 8 | `cudaErrorAssert` in `embed_tokens` | Same invalid token IDs in forward pass | Patch `embed_tokens.forward` to clamp input | Resolved |
| 9 | `Triton RuntimeError` in compiled loss | Same invalid token IDs in `gather` operation | Wrap `_generate_and_score_completions` output | Resolved |
| 10 | `ValueError: Unknown loss type: sapo` | Unsloth's `UnslothEfficientGRPO` doesn't support SAPO | Switch to `loss_type="dr_grpo"` | Resolved |
| 11 | Patch clamped 196K+ "bad" IDs including valid padding | Used `tokenizer.vocab_size` (151,643) instead of `num_embeddings` (151,936) | Use `model.get_input_embeddings().num_embeddings` | Resolved |

### 2.2 Unsloth Compatibility Issues (Detailed)

#### 2.2.1 GRPOConfig Parameter Blocking

Unsloth wraps TRL's `GRPOConfig.__init__` with a fixed signature from an older TRL version. Parameters added in TRL 0.27-0.28 are rejected:

**Blocked parameters** (require post-init injection):
- `max_prompt_length`
- `epsilon_high` (Clip-Higher)
- `importance_sampling_level` (GSPO)
- `mask_truncated_completions`
- `reward_weights` (GDPO)
- `sapo_temperature_pos/neg` (SAPO)

**Solution**: Split params into `init_kwargs` (accepted by Unsloth wrapper) and `post_kwargs` (injected via `setattr` after construction). TRL reads config attributes at runtime via `self.args.xxx`.

#### 2.2.2 Compiled Loss Function Limitations

Unsloth replaces TRL's `compute_loss` with `grpo_accumulated_loss` → `UnslothEfficientGRPO.apply()` — a custom `torch.autograd.Function` using `torch.func.grad_and_value` for chunk-based gradient accumulation. This compiled function has a hardcoded switch over supported loss types: `grpo`, `dr_grpo`, `dapo`, `bnpo`. SAPO is not included.

#### 2.2.3 `has_images` Bug

Unsloth's compiled `_generate_and_score_completions` references a module-level variable `has_images` that is only defined when vision models (VLMs) are loaded. For text-only models like Qwen3-4B-Instruct, this variable is undefined, causing `NameError`.

**Fix**: Inject into function's `__globals__` dict (the compiled module's global scope):
```python
GRPOTrainer._generate_and_score_completions.__globals__["has_images"] = False
```

#### 2.2.4 `vocab_size` Mismatch

Qwen3's tokenizer reports multiple vocabulary sizes:

| Property | Value | Includes |
|----------|-------|----------|
| `tokenizer.vocab_size` | 151,643 | Base tokens only |
| `len(tokenizer)` | 151,669 | + 26 special tokens (pad, eos, im_start, im_end, tools, etc.) |
| `model.config.vocab_size` | 151,936 | + alignment padding (GPU-friendly size) |
| `embed_tokens.num_embeddings` | 151,936 | Actual embedding table |

Key special tokens outside base vocab: `pad_token_id=151654`, `eos_token_id=151645`, `bos_token_id=None`.

Using `tokenizer.vocab_size` for validation/clamping incorrectly treats ALL padding and EOS tokens as invalid.

### 2.3 Final Patch Architecture

Four-layer idempotent defense against Unsloth/Qwen3 token ID issues:

```
Generation → [Patch 4: clamp ID tensors] → buffered_inputs
                                              ├→ [Patch 2: batch_decode clamp] → text decoding
                                              └→ compute_loss
                                                  ├→ [Patch 3: embed_tokens clamp] → embedding lookup
                                                  └→ Triton kernels (covered by Patch 4 clamping)
```

All patches use marker attributes (`_original_xxx_unpatched`) for idempotency — safe to re-run without restart.

---

## 3. Hyperparameter Selection Rationale

### 3.1 Final GSPO Configuration

| Parameter | Value | Source / Rationale |
|-----------|-------|--------------------|
| `loss_type` | `"dr_grpo"` | Dr. GRPO (arXiv 2503.20783). SAPO blocked by Unsloth. |
| `beta` | 0.0 | No KL regularization (GSPO/DAPO standard) |
| `epsilon` | 0.2 | PPO-style clipping lower bound (DAPO/VAPO) |
| `epsilon_high` | 0.28 | Clip-Higher asymmetric upper bound (VAPO, arXiv 2504.05118) |
| `importance_sampling_level` | `"sequence"` | GSPO sequence-level ratios (Qwen3 training, arXiv 2507.18071) |
| `num_generations` (G) | 16 | A100 80GB budget; more = better advantage estimation |
| `max_completion_length` | 768 | Reduced from 1024 due to importance_sampling double pass |
| `max_prompt_length` | 512 | Sufficient for STEM prompts + system prompt |
| `steps_per_generation` | 16 | = 4 × gradient_accumulation_steps; reuse generations |
| `gradient_accumulation_steps` | 4 | Effective batch = 16 × 4 = 64 |
| `learning_rate` | 2e-6 | Conservative for RL stability |
| `lr_scheduler` | cosine | Standard for RL fine-tuning |
| `temperature` | 0.9 | Diverse generation for advantage estimation |
| `reward_weights` | [0.8, 0.2] | GDPO: 80% correctness, 20% format |
| `dithering_sigma` | 0.05 | ReDit (arXiv 2506.18631): Gaussian noise on binary rewards |
| `mask_truncated_completions` | True | Exclude incomplete generations from loss |

### 3.2 Curriculum Configuration

| Stage | Steps | Problems | Warmup | Difficulty Weights |
|-------|-------|----------|--------|--------------------|
| 1 (warm-up) | 200 | easy + medium (10,619) | 10% | easy=0.5, medium=1.0 |
| 2 (full) | 400 | all tiers (14,203) | 3% | easy=0.5, medium=1.0, hard=2.0 |

**Total**: 600 steps, ~6-8 hours on A100 80GB

### 3.3 LoRA Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `r` | 16 | Matches SFT adapter rank |
| `alpha` | 32 | Standard 2× multiplier |
| `dropout` | 0.0 | No stochastic noise in RL advantage estimation |
| `target_modules` | q,k,v,o,gate,up,down | All attention + MLP layers |

---

## 4. Implemented Techniques Summary

### 4.1 Techniques from Literature

| Technique | Paper | arXiv | Implementation |
|-----------|-------|-------|----------------|
| GSPO (sequence importance sampling) | Qwen3 Technical Report | 2507.18071 | `importance_sampling_level="sequence"` in GRPOConfig |
| Dr. GRPO (constant length normalization) | Dr. GRPO | 2503.20783 | `loss_type="dr_grpo"` |
| Clip-Higher (asymmetric clipping) | VAPO / DAPO | 2504.05118, 2503.14476 | `epsilon=0.2`, `epsilon_high=0.28` |
| ReDit (reward dithering) | ReDit | 2506.18631 | Gaussian noise sigma=0.05 in reward functions |
| GDPO (decoupled reward normalization) | GDPO | 2601.05242 | `reward_funcs=[correctness, format]`, `reward_weights=[0.8, 0.2]` |
| GRPO-LEAD (difficulty-aware curriculum) | GRPO-LEAD | 2504.09696 | 2-stage curriculum + difficulty weight multipliers |
| Zero-variance masking | Revisiting GRPO | 2505.22257 | NaN reward for groups with std=0 |
| DRPO (no negative penalties) | DRPO | 2510.04474 | correct=1.0, wrong=0.0 (not -0.5) |

### 4.2 Techniques NOT Used (and Why)

| Technique | Paper | Reason for exclusion |
|-----------|-------|---------------------|
| SAPO (smooth adaptive clipping) | arXiv 2511.20347 | Blocked by Unsloth's compiled loss function |
| Dynamic Sampling (DAPO) | arXiv 2503.14476 | Requires veLR framework integration |
| GHPO (teacher imitation) | arXiv 2507.10628 | Requires stronger teacher model |
| MO-GRPO (auto reward weighting) | arXiv 2509.22047 | GDPO's manual weights are simpler and sufficient |

---

## 5. Key Discoveries

### 5.1 Unsloth's Hidden Constraints

1. **`batch_size = num_generations`**: Unsloth silently enforces this, meaning G directly controls VRAM usage. Cannot set small batch with large G.
2. **Compiled loss functions**: Unsloth replaces TRL's loss with custom Triton kernels. New TRL loss types are not automatically supported.
3. **`has_images` assumption**: Compiled code assumes VLM-related variables exist in module scope.
4. **GRPOConfig wrapper**: Blocks newer TRL parameters via restrictive `__init__` override.

### 5.2 HuggingFace Token Vocabulary Architecture

```
tokenizer.vocab_size (151,643) — base vocabulary
    ↓ + 26 special tokens
len(tokenizer) (151,669) — all real tokens
    ↓ + 267 alignment padding entries
model.config.vocab_size (151,936) — embedding table size
```

**Lesson**: Always use `model.get_input_embeddings().num_embeddings` for token ID validation, never `tokenizer.vocab_size`.

### 5.3 Importance Sampling Memory Model

`importance_sampling_level="sequence"` requires computing log-probabilities under BOTH current and old policies. This means:
- 2 forward passes per generation batch (current + old policy)
- Peak VRAM: ~2× the non-importance-sampling case
- On A100 80GB with G=16: MAX_COMPLETION=768 is the safe maximum (1024 OOMs)

### 5.4 Dataset Quality vs Algorithm Sophistication

The hybrid RL dataset (R12) was the single highest-leverage improvement. The original SFT-derived dataset had:
- 99.4% "easy" problems → zero curriculum signal
- Template-based generation → ~5 variants per template (low diversity)
- Conceptual problems ("explain", "prove") → reward function returns 0.0 always → zero gradient

The new dataset (14,203 problems from 5 sources) provides proper difficulty distribution, diverse problem types, and verifiable answers — enabling all downstream RL techniques to function.
