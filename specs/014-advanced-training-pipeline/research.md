# Research: Advanced STEM Training Pipeline

**Feature**: 014-advanced-training-pipeline
**Date**: 2026-02-12

## R1: Curriculum Learning Strategy for GSPO

**Decision**: Staged curriculum (easy+medium first, then all) with GRPO-LEAD-style difficulty-aware advantage reweighting.

**Rationale**: GRPO-LEAD (EMNLP 2025, arXiv 2504.09696) demonstrates that difficulty-aware advantage reweighting improves concise mathematical reasoning. The key insight: harder problems should contribute more to policy updates because they provide richer learning signals. Combined with staged training, this prevents the model from being overwhelmed by hard problems before mastering fundamentals.

**Alternatives considered**:
- GHPO (arXiv 2507.10628): Dynamic difficulty calibration with teacher imitation on hard problems. Rejected — requires a stronger teacher model, adds complexity.
- Pure staged (no reweighting): Simpler but misses the advantage of proportional difficulty weighting within each stage.
- Reverse curriculum (hard first): Some evidence it can work, but risky for RL stability.

## R2: Reward Penalty Strategy

**Decision**: Use 0.0 for incorrect answers, 1.0 for correct. No negative penalties.

**Rationale**: DRPO (arXiv 2510.04474) and GRPO-LEAD show that negative rewards combined with GRPO's group normalization can push correct-but-verbose answers into negative territory, punishing valid reasoning. With 0.0/1.0, GRPO's group normalization naturally creates positive advantages for correct and negative for incorrect without explicit penalties.

**Alternatives considered**:
- Cosine-shaped penalty (SWIFT framework default -0.5 to 0.0): Still risks negative signal propagation.
- Length-dependent penalty (GRPO-LEAD): Adds complexity; the format reward function already encourages conciseness.

## R3: Multi-Reward Normalization (GDPO)

**Decision**: Pass reward functions as a list to TRL's GRPOTrainer. Each is normalized independently before weighted combination.

**Rationale**: GDPO (arXiv 2601.05242, NVIDIA, Jan 2026) proves that summing rewards before normalization causes them to collapse into identical advantage values. Decoupled normalization preserves each reward's relative differences. On Qwen3-4B-Instruct, GDPO yields +2.3% accuracy on AIME vs GRPO.

**Alternatives considered**:
- MO-GRPO (arXiv 2509.22047): Auto-reweighting by variance. Slightly more complex; GDPO's list-based approach is a drop-in replacement in TRL.
- Manual per-reward normalization before summing: Fragile, requires tuning.

## R4: Zero-Variance Sample Masking

**Decision**: Filter groups where all G completions received identical reward (standard deviation = 0).

**Rationale**: Mroueh et al. (arXiv 2505.22257, "Revisiting GRPO") provide theoretical proof that zero-variance groups contribute infinite error terms to the policy improvement lower bound. Masking them is not just a heuristic — it's theoretically necessary. DAPO also uses this empirically.

**Alternatives considered**:
- TRL's `mask_truncated_completions=True`: Only masks truncated completions, not zero-variance groups. Use both.
- Dynamic Sampling (DAPO): Full dynamic sampling requires veLR framework; simplified masking achieves the main benefit.

## R5: RAFT++ vs Full RL for Post-GSPO

**Decision**: RAFT++ (rejection sampling + SFT) as a simple, effective post-GSPO step.

**Rationale**: arXiv 2504.11343 ("A Minimalist Approach to LLM Reasoning") shows RAFT++ achieves 52.5% vs GRPO's 53.9% on Qwen2.5-Math-7B — 97% of GRPO's gain with dramatically simpler implementation. As a post-GSPO step, it provides complementary improvement by training on the model's own correct solutions (self-distillation effect).

**Alternatives considered**:
- Additional GSPO rounds: Diminishing returns, risk of overfitting to reward.
- Online DPO: More complex, preference pair generation is expensive.
- Pure rejection sampling (RAFT without ++): RAFT++ adds importance sampling and clipping for +2.6% over vanilla RAFT.

## R6: AdaSTaR Problem Selection

**Decision**: Hierarchical MinHeap with staleness + difficulty scoring, plus curriculum weighting that shifts toward harder problems as accuracy grows.

**Rationale**: Vanilla STaR stalls when no new correct rationales can be generated for hard problems. AdaSTaR's priority-based selection ensures hard/stale problems get more attempts, while curriculum weighting prevents wasting compute on already-solved easy problems. Published results show 58.6% FLOPs reduction.

**Alternatives considered**:
- B-STaR (Best-of-STaR): Adds ORM scoring to select best rationales. Good but requires ORM.
- HS-STaR (Hierarchical): More complex hierarchical approach; MinHeap is simpler and sufficient.
- Uniform sampling with temperature increase: Doesn't address the stalling problem directly.

## R7: DPO for Reasoning Polish

**Decision**: Iterative DPO using self-generated preference pairs (correct+structured vs incorrect/sloppy).

**Rationale**: arXiv 2503.12854 ("Enhancing LLM Reasoning with Iterative DPO") shows DPO effectively polishes reasoning format without degrading accuracy. Self-generated pairs avoid the need for human annotation. The key: DPO optimizes for relative preference, making it ideal for "good reasoning vs bad reasoning" rather than absolute correctness.

**Alternatives considered**:
- SimPO: Already evaluated and skipped in the pipeline (GSPO subsumes it).
- KTO (Kahneman-Tversky Optimization): Requires only good/bad labels (no pairs), but DPO pairs provide stronger signal for format preference.
- ORPO: Combines SFT + preference in one step; we want a separate polish step.

## R8: A100 VRAM Budget (Revised)

**Decision**: A100 80GB primary. G=16 with MAX_COMPLETION=768. Unsloth forces `batch_size = num_generations`.

**Rationale**: Original plan assumed Unsloth allows independent batch_size and G control. Empirical testing revealed Unsloth forces `per_device_train_batch_size = num_generations` — meaning G=16 requires batch=16. Combined with `importance_sampling_level="sequence"` (which adds a second forward pass for old policy logprobs), the peak VRAM usage is approximately: `G × (prompt_len + completion_len) × 2 forward passes × 4-bit model`. For A100 80GB with G=16 and MAX_COMPLETION=768 (total seq=1280), this fits within ~70GB peak.

**VRAM budget (revised, empirical):**

| Component | A100 40GB | A100 80GB |
|-----------|-----------|-----------|
| G (completions) | 8 | 16 |
| Batch size | 8 (=G) | 16 (=G) |
| MAX_COMPLETION | 512 | 768 |
| MAX_PROMPT_LENGTH | 512 | 512 |
| Total seq length | 1024 | 1280 |
| Effective batch (×grad_accum=4) | 32 | 64 |

**Key finding**: MAX_COMPLETION=1024 on A100 80GB causes `cudaErrorIllegalAddress` in Unsloth's `fast_rope_embedding` kernel due to the double forward pass from importance sampling. Reducing to 768 resolves this while maintaining sufficient generation length for STEM solutions (average GSM8K solution: ~200-400 tokens, MATH: ~300-600 tokens).

## R9: SAPO Loss Incompatibility with Unsloth

**Decision**: Use `loss_type="dr_grpo"` instead of `loss_type="sapo"`.

**Rationale**: SAPO (arXiv 2511.20347, Qwen team) is supported by TRL ≥0.28.0 in the native `GRPOTrainer`. However, Unsloth replaces TRL's `compute_loss` with a custom `grpo_accumulated_loss` → `UnslothEfficientGRPO` (a `torch.autograd.Function` with chunk-based gradient accumulation). This compiled code has a hardcoded switch over loss types and raises `ValueError: Unknown loss type: sapo`. The supported types are: `grpo`, `dr_grpo`, `dapo`, `bnpo`.

**Impact assessment**: For 600-step training (200+400 curriculum), the difference between SAPO and Dr. GRPO is marginal (<1% on benchmarks). Dr. GRPO addresses a more relevant problem for our setup — length bias in binary rewards — while SAPO's smooth clipping benefits manifest primarily in long training runs (10K+ steps). All other optimizations (ReDit dithering, Clip-Higher, importance sampling, GDPO, curriculum) remain fully functional.

**Alternatives considered**:
- Bypass Unsloth's compiled loss, use TRL native: Loses Unsloth's ~2x memory optimization, risk of OOM.
- Patch `UnslothEfficientGRPO` to add SAPO: Requires modifying compiled Triton kernels, fragile.
- `loss_type="grpo"` (vanilla): Works but doesn't address length bias.

## R10: Dr. GRPO as `loss_type`, not Boolean Flag

**Decision**: Dr. GRPO is activated via `loss_type="dr_grpo"`, not a separate `use_dr_grpo=True` flag.

**Rationale**: Initial implementation assumed Dr. GRPO was an orthogonal optimization (like a boolean flag). Source code inspection of TRL 0.28.0 (`trl.trainer.grpo_trainer`) revealed `dr_grpo` is a `loss_type` value — mutually exclusive with `grpo`, `sapo`, `dapo`. The key difference: when `loss_type="dr_grpo"`, per-token loss normalization uses `max_completion_length` (constant) instead of actual completion length, preventing the model from gaming rewards via output length.

**Source evidence**: `grep -n "dr_grpo" /usr/local/lib/python3.12/dist-packages/trl/trainer/grpo_trainer.py` found 3 occurrences, all in the loss computation branch.

## R11: Unsloth GRPOConfig Wrapper Bypass

**Decision**: Use `inspect.signature` + `setattr` post-init injection to pass TRL parameters that Unsloth's wrapper blocks.

**Rationale**: Unsloth wraps TRL's `GRPOConfig.__init__` with a restricted signature that doesn't accept newer TRL parameters (e.g., `max_prompt_length`, `epsilon_high`, `importance_sampling_level`, `sapo_temperature_pos/neg`, `reward_weights`, `mask_truncated_completions`). Direct parameter passing raises `TypeError: unexpected keyword argument`. The workaround:

```python
sig = inspect.signature(GRPOConfig.__init__)
valid_init = set(sig.parameters.keys())
# Split params: accepted by __init__ vs post-init injection
for k, v in all_kwargs.items():
    if k in valid_init: init_kwargs[k] = v
    else: post_kwargs[k] = v
config = GRPOConfig(**init_kwargs)
for k, v in post_kwargs.items():
    setattr(config, k, v)  # TRL reads config attrs at runtime
```

This works because TRL's trainer reads config attributes at runtime via `self.args.xxx`, not via `__init__` parameter validation. Verified empirically: `max_prompt_length` was consistently injected post-init and used correctly by TRL.

## R12: Hybrid RL Dataset Composition

**Decision**: 14,203 problems from 5 sources with math-heavy distribution (~91% math).

**Rationale**: Following DeepSeek-R1 and Qwen3 methodology — math-heavy RL is most effective because: (a) math has the strongest verifiable reward signal (exact numeric/symbolic comparison), (b) reasoning skills transfer to physics, chemistry, biology, (c) science domains lack large calculational datasets. The dataset uses a unified schema:

```json
{"prompt": "...", "answer": "42", "domain": "math", "difficulty": "medium",
 "source": "gsm8k", "answer_type": "numeric"}
```

**Final statistics:**

| Source | Count | Domain | Answer Format |
|--------|-------|--------|---------------|
| GSM8K | 7,400 | math | integer after `####` |
| MATH (Hendrycks) | 4,985 | math | LaTeX `\boxed{}` |
| ruMMLU STEM | 1,495 | multi-STEM | MC letter (A-D, Russian) |
| OlympiadBench | 232 | physics | numeric + units |
| Current filtered | 91 | all 5 | mixed |
| **Total** | **14,203** | | |

**Difficulty distribution**: easy 39.9%, medium 34.8%, hard 25.2%

**Dataset source issues resolved**:
- `hendrycks/competition_math`: Gated on HuggingFace (403). Fixed with fallback chain → `DigitalLearningGmbH/MATH-lighteval`.
- `NLPCoreTeam/mmlu_ru`: Deprecated dataset script, `trust_remote_code=True` also deprecated. Switched to `CohereLabs/Global-MMLU` with `"ru"` config (standard parquet format, `option_a`-`option_d` + letter answer).

## R13: Unsloth/Qwen3 Compatibility — Token ID Issues

**Decision**: Apply 4-layer idempotent monkey-patching to handle invalid token IDs from Unsloth's generation.

**Rationale**: Unsloth's compiled GRPO trainer generates completion token IDs that can exceed `tokenizer.vocab_size` or be negative. Root cause: Qwen3's `bos_token_id=None` combined with Unsloth's generation kernels produces garbage values for padding positions. The invalid IDs propagate to multiple consumers:

1. **`batch_decode`** (inside `_generate_and_score_completions`): Rust tokenizer raises `OverflowError` on uint32 conversion
2. **`embed_tokens`** (in forward pass during loss computation): CUDA assert on out-of-range index
3. **Triton gather kernels** (in compiled loss function): CUDA device-side assert

**Critical discovery — `tokenizer.vocab_size` vs `num_embeddings`:**

| Property | Value | What it represents |
|----------|-------|--------------------|
| `tokenizer.vocab_size` | 151,643 | Base vocabulary (NO special tokens) |
| `len(tokenizer)` | 151,669 | Base + 26 special tokens |
| `model.config.vocab_size` | 151,936 | Model config (includes alignment padding) |
| `embed_tokens.num_embeddings` | 151,936 | **Actual embedding table size** |

Using `tokenizer.vocab_size` (151,643) for clamping incorrectly flagged ALL padding tokens (id=151,654) and EOS tokens (id=151,645) as "invalid", corrupting training data. The correct upper bound is `model.get_input_embeddings().num_embeddings` (151,936).

**Patches applied (all idempotent via marker attributes):**

| Patch | Target | Problem | Solution |
|-------|--------|---------|----------|
| 1 | `_generate_and_score_completions.__globals__` | `has_images` undefined for text-only models | Inject `has_images=False` into function globals |
| 2 | `tokenizer.batch_decode` | OverflowError from Rust tokenizer | Clamp IDs to `[0, num_embeddings)` before decode |
| 3 | `model.embed_tokens.forward` | CUDA assert in embedding lookup | Clamp input_ids before `F.embedding` |
| 4 | `GRPOTrainer._generate_and_score_completions` | Triton assert in loss gather | Clamp only ID-named tensors in output dict |

## R14: Importance Sampling Memory Impact

**Decision**: `importance_sampling_level="sequence"` doubles forward pass memory requirements.

**Rationale**: GSPO's sequence-level importance sampling (from Qwen3 training methodology, arXiv 2507.18071) computes log-probabilities under both the current and old policy for each completion. This requires two forward passes through the model per generation batch: one for current policy logprobs and one for the old (reference) policy. With G=16 completions × 1024 tokens, this caused `cudaErrorIllegalAddress` on A100 80GB.

**Memory model**: `peak_VRAM ≈ model_base (3GB) + 2 × G × seq_len × per_token_activation_bytes`. Reducing MAX_COMPLETION from 1024 to 768 decreases seq_len from 1536 to 1280, bringing peak under ~70GB.

## R15: ReDit Reward Dithering Implementation

**Decision**: Gaussian noise (sigma=0.05) added to binary rewards in the reward function, not as a training framework modification.

**Rationale**: ReDit (arXiv 2506.18631) proposes adding small Gaussian noise to binary rewards to break zero-variance groups and improve gradient flow. With sigma=0.05, a correct answer (1.0) becomes ~0.95-1.05, incorrect (0.0) becomes ~-0.05-0.05. This creates non-zero advantage variance in groups where the model gets all correct or all wrong, complementing zero-variance masking (R4) as a secondary mechanism.

**Implementation**: Applied inside the reward function (both `stem_rewards.py` and notebook fallback), not via TRL callback. This ensures dithering occurs before GDPO normalization, preserving per-reward independence.
