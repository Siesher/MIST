# GRPO Best Practices Research Findings

**Topic:** GRPO/GSPO training best practices for Qwen3.5-9B STEM tutoring
**Date:** 2026-03-18
**Researcher:** ML Research Agent (Claude Sonnet 4.6)
**Scope:** 9 specific questions on GRPO training hyperparameters and techniques

---

## Executive Summary

The GRPO landscape has evolved substantially since DeepSeek-R1 with DAPO, Dr. GRPO, GSPO, and GDPO all addressing specific failure modes. The current MITS notebook configuration (`grpo_qwen3.5_9b.ipynb`) is largely aligned with 2025-2026 best practices, with two concrete improvement opportunities: (1) the high clipped_ratio problem requires an overlong reward shaping function, not just masking, and (2) LoRA rank should be reduced from 32 to 16 for optimal reasoning performance. The thinking model truncation issue is the most critical unresolved risk and requires an explicit length-penalty reward term.

---

## Q1: clipped_ratio > 95% — What to Do

### Problem Description

`completions/clipped_ratio` measures the fraction of completions truncated due to `max_completion_length`. When this exceeds 95%, the training signal degrades severely because most samples are truncated and either (a) receive biased loss if included, or (b) are all masked leaving zero gradient.

### Analysis

**Option A: `mask_truncated_completions=True` alone**

- Described as "preventing truncated completions from being incorrectly penalized" (TRL docs).
- Default is `False`. Setting `True` is recommended by DAPO paper.
- **Critical bug (Unsloth GitHub issue #3149, 2025):** When clipped_ratio is very high, masking ALL completions in a group causes `n_mask_per_reward = 0`, which makes KL divergence become NaN and crashes training.
- **Verdict: Necessary but not sufficient** for clipped_ratio > 95%.

**Option B: Increase `max_completion_length`**

- Most direct solution. For Qwen3.5-9B with `<think>` blocks, thinking traces alone can reach 2000-8000+ tokens.
- DAPO uses `L_max = 16384` with `L_cache = 4096` as the soft penalty buffer (total budget: 20480 tokens).
- On A100 80GB with bf16, Qwen3.5-9B can handle sequences up to ~16K without memory pressure assuming batch size is adjusted.
- **Verdict: Primary fix.** If clipped_ratio > 95% is caused by `<think>` traces, `max_completion_length` must be large enough to contain them.

**Option C: DAPO Overlong Reward Shaping (recommended)**

The DAPO paper (arXiv 2503.14476, ByteDance/Tsinghua) defines a soft penalty:
- Define `L_max` (max generation budget) and `L_cache` (penalty buffer, e.g., 4096).
- Completions under `L_max - L_cache` tokens: no penalty.
- Completions in `[L_max - L_cache, L_max]`: linearly increasing penalty from 0 to -1.
- Completions exceeding `L_max`: maximum penalty of -1 (acts as a strong truncation deterrent).

This is preferable to hard masking because it provides a learning signal that explicitly trains the model to be concise.

**Option D: Token-Level Policy Gradient Loss (`loss_type="dapo"` or `"dr_grpo"`)**

DAPO shows that using token-level loss (averaging over all tokens in the batch, not per-sequence) is "critical for long-CoT RL scenarios." Both `loss_type="dapo"` and `loss_type="dr_grpo"` implement this. Do NOT use `loss_type="grpo"` (has length bias).

### Recommendation

Use all three fixes together:
1. Set `mask_truncated_completions=True` (but monitor for NaN KL when clipped_ratio is very high).
2. Increase `max_completion_length` to 12288-16384 to accommodate thinking traces.
3. Add overlong reward shaping: soft penalty starting 4096 tokens before `max_completion_length`.
4. Use `loss_type="dr_grpo"` (already in MITS notebook - correct).

---

## Q2: GSPO (arXiv 2507.18071) — Hyperparameters

### Paper Summary

Group Sequence Policy Optimization (Chujie Zheng et al., Qwen team, July 2025) performs importance sampling at the sequence level instead of token level. This is the algorithm actually used to train Qwen3 models.

**Key insight:** Sequence-level importance ratio = `exp(sum of log-probs of sequence / length) / ref`. Due to length normalization, this ratio is numerically much smaller than token-level ratios.

### Recommended Hyperparameters (Paper Section 5.1)

| Parameter | Value | Note |
|-----------|-------|-------|
| `epsilon` | `3e-4` | Left clipping threshold (sequence-level) |
| `epsilon_high` | `4e-4` | Right clipping threshold (sequence-level) |
| `steps_per_generation` | `4` | Minibatch partitioning of rollout batch |
| `beta` | `0.0` | Zero KL regularization |
| `importance_sampling_level` | `"sequence"` | Must be set (not default `"token"`) |

### Critical Scaling Factor

Token-level GRPO uses `epsilon = 0.2` and `epsilon_high = 0.28`. Sequence-level GSPO uses `3e-4` and `4e-4`. This is a **~1000x difference** in magnitude. The paper explicitly states this is expected because of the distinct importance ratio definition. Setting GSPO epsilon to 0.2 would clip almost nothing, destroying the sequence-level regularization.

### TRL/Swift Configuration

In ms-swift: `--importance_sampling_level sequence --epsilon 3e-4 --epsilon_high 4e-4 --beta 0`

In TRL GRPOConfig (v0.25+): `importance_sampling_level="sequence"` is a parameter added by the GSPO integration.

**MITS notebook status: Correctly configured** with `epsilon=3e-4`, `epsilon_high=4e-4`, `importance_sampling_level="sequence"`.

---

## Q3: Dr. GRPO (arXiv 2503.20783) — loss_type and Length Normalization

### Paper Summary

"Understanding R1-Zero-Like Training: A Critical Perspective" (SAIL group, COLM 2025) identifies two biases in standard GRPO:

1. **Response-level length bias:** Dividing loss by sequence length `|o_i|` causes shorter correct answers to get larger gradient updates than longer ones. Also, long incorrect answers are penalized less than short ones.
2. **Question-level difficulty bias:** Dividing advantage by standard deviation of rewards upweights questions with low reward variance (either all-correct or all-incorrect), distorting learning signal.

### Dr. GRPO Fixes

**Fix 1 - loss_type:** Use `loss_type="dr_grpo"` in TRL GRPOConfig. This normalizes by a **global constant** (`max_completion_length`) instead of per-sample sequence length. All sequences get the same normalization weight regardless of their actual length.

**Fix 2 - std normalization:** Set `norm_adv_by_std_in_grpo=False` or the equivalent. In TRL, the GRPO default still divides advantages by group std. Dr. GRPO removes this. In veRL: `algorithm.norm_adv_by_std_in_grpo: False`.

**Important tradeoff on std removal:** Removing std normalization means questions with high reward variance get larger absolute advantages than low-variance questions. For questions where some completions are correct and some wrong (the most useful learning signal), variance is high and advantages are large - this is desirable. For all-correct or all-wrong groups, variance is low/zero - advantages become small. This is the correct behavior.

### TRL loss_type Options (as of TRL v0.27+)

| loss_type | Normalization | Notes |
|-----------|--------------|-------|
| `grpo` | Per-sequence length | Original, biased, NOT recommended |
| `dr_grpo` | Global constant (max_completion_length) | Paper recommendation |
| `dapo` | Active tokens in global accumulated batch | DAPO default, unbiased |
| `bnpo` | Active tokens in local batch | Similar to dapo, local-only |
| `cispo` | Clips IS weights separately | Different mechanism |
| `sapo` | Soft temperature-controlled gating | Qwen SAPO paper |

**Recommendation for MITS:** `loss_type="dr_grpo"` is correct. The MITS notebook already uses this.

**Note on std:** TRL's `dr_grpo` loss_type does NOT automatically disable std normalization in advantage computation. You may need to explicitly set `norm_adv_by_std_in_grpo=False` if the config supports it, or implement it in a custom trainer.

---

## Q4: ReDit Reward Dithering (arXiv 2506.18631) — Is sigma=0.05 Correct?

### Paper Summary

ReDit adds Gaussian noise `N(0, sigma^2)` to rewards before advantage computation. For binary rewards (0/1), this smooths the discrete signal and provides exploratory gradients throughout training.

### Key Findings from Ablation Study

The paper tests uniform noise with radius `a` (Gaussian `sigma = a / sqrt(3)`):

| Uniform `a` | Gaussian `sigma` | Performance |
|-------------|-----------------|-------------|
| 0.01 | ~0.0058 | Minimal improvement over baseline |
| 0.05 | ~0.0289 | **Optimal - fastest convergence + best accuracy** |
| 0.5 | ~0.289 | Degraded - over-smoothing |

The Gaussian variant `sigma = 0.05` (directly, not converted from uniform) is what the MITS notebook uses. The paper's primary result uses `a = 0.05`, which corresponds to `sigma ≈ 0.029` for Gaussian. However, the paper also validates Gaussian noise directly.

### Assessment

**sigma = 0.05 for Gaussian noise is slightly above the paper's optimal range but within the safe zone.** The paper's range for good performance is roughly `sigma in [0.01, 0.1]`. Using `sigma = 0.05` is reasonable.

**Important caveat:** The paper's experiments used simple math tasks. For STEM with weighted rewards (correctness=0.7, format=0.15, Socratic=0.15), apply dithering to each component's raw reward before weighting, not to the aggregated reward. The noise magnitude should be proportional to each reward's scale (all are 0-1 binary here, so same sigma works).

**Verdict: sigma=0.05 is correct and within the validated range.**

---

## Q5: Multi-Objective GRPO with GDPO — Independent vs. Aggregated Normalization

### The Problem

GRPO with multiple rewards `r_1, r_2, ..., r_k` naively sums them then normalizes:
```
r_sum = w_1*r_1 + w_2*r_2 + ...
A = (r_sum - mean(r_sum)) / std(r_sum)
```

When objectives have different difficulty levels (correctness is harder than format), the GRPO normalization collapses advantages: reward combinations that should be distinct end up with identical advantage values, reducing training signal resolution.

### GDPO Fix (arXiv 2601.05242, NVLabs, January 2026)

Normalize each reward **independently** before aggregation:
```python
# For each reward k:
A_k = (r_k - mean(r_k)) / std(r_k)

# Weighted aggregation:
A_sum = w_1*A_1 + w_2*A_2 + w_3*A_3

# Optional batch-wise renormalization:
A_final = (A_sum - mean(A_sum)) / std(A_sum)
```

The paper proves this preserves more distinct advantage groups. With 3 rewards and 16 rollouts (MITS config), GDPO provides ~4x more distinct advantage levels than vanilla GRPO.

### For MITS (correctness=0.7, format=0.15, socratic=0.15)

**Use GDPO-style independent normalization.** The three rewards have very different difficulty:
- Correctness: hard (0 or 1, model often wrong)
- Format (boxed + steps): medium-easy (model often gets this right with instruction tuning)
- Socratic (guiding questions): subjective, medium difficulty

Without independent normalization, format reward (high variance=easy) would dominate and dilute correctness signal.

### TRL Implementation

In TRL v0.27+, `multi_objective_aggregation="normalize_then_sum"` enables GDPO-style normalization. If this parameter is not available in the installed TRL version, implement manually in a custom reward wrapper:

```python
def gdpo_aggregate(rewards_list: list[torch.Tensor], weights: list[float]) -> torch.Tensor:
    normalized = []
    for r in rewards_list:
        mu, std = r.mean(), r.std() + 1e-8
        normalized.append((r - mu) / std)
    return sum(w * n for w, n in zip(weights, normalized))
```

**Verdict: GDPO-style (normalize independently, then aggregate) is definitively correct for multi-reward GRPO. The MITS notebook already implements this.**

---

## Q6: GRPO-LEAD Curriculum Learning — Is Difficulty Reweighting Recommended?

### Paper Summary (arXiv 2504.09696, EMNLP 2025)

GRPO-LEAD adds three enhancements to GRPO:
1. **Length regularization:** exponential penalty `exp(-alpha * z)` where `z` is standardized response length.
2. **Explicit incorrect penalty:** -1 for wrong answers.
3. **Difficulty-aware advantage reweighting:** logistic function of per-question correctness rate.

### Reweighting Formula

```python
def difficulty_weight(rho_q: float, A=0.4, B=1.5, rho0=0.75, k=10) -> float:
    """
    rho_q: fraction of correct completions for question q (0=hardest, 1=easiest)
    Returns: weight in [A, B] = [0.4, 1.5]
    """
    return A + (B - A) / (1 + math.exp(k * (rho_q - rho0)))
```

- Easy problems (rho_q close to 1.0): weight ~0.4 (de-emphasized)
- Hard problems (rho_q close to 0.0): weight ~1.5 (emphasized)
- The logistic inflection at rho_q=0.75 creates a sharp transition

For negative advantages (incorrect answers), the paper applies `w(1 - rho_q)` instead, so incorrect answers on EASY problems are penalized more strongly.

### Results

GRPO-LEAD on AIME24: 0.867 vs 0.833 baseline (+4%). Conciseness: 8267 vs 10194 tokens (19% reduction). Published EMNLP 2025 — peer-reviewed.

### Assessment

**Recommended with caveats:**
- Reweighting hard=1.5x, easy=0.4x (not 2x/0.5x as previously used in MITS notebook header) is the validated setting.
- Requires per-question correctness tracking across rollouts, which adds state to the training loop.
- Requires a warm-up period (at least 50-100 steps) before computing stable correctness estimates.
- For STEM with multi-domain data, compute `rho_q` per domain separately, not globally.

**The "hard=2x, easy=0.5x" simple version** described in the MITS notebook header deviates from the paper formula. The actual paper uses `B=1.5, A=0.4` with a logistic curve, not binary step weights. The logistic function is more stable and avoids extreme gradient magnitudes.

---

## Q7: High clipped_ratio with Thinking Models (Qwen3.5-9B)

### Problem

Qwen3.5-9B generates `<think>...</think>` blocks before the final answer. These thinking traces routinely reach 2000-8000 tokens. If `max_completion_length=4096`, even modest thinking before a correct answer will exceed the limit, causing clipped_ratio > 90%.

### Strategy Comparison

| Strategy | Pros | Cons |
|----------|------|------|
| Disable thinking (`enable_thinking=False`) | Clean training, no truncation | Model loses reasoning; defeats purpose |
| Set `max_completion_length=12288-16384` | Accommodates thinking | High VRAM; slower; still some truncation |
| Thinking budget tokens | Cap think length; force answer | Requires custom logits processor during training |
| Overlong reward shaping | Trains model to be concise | Requires careful `L_max`/`L_cache` tuning |
| S-GRPO early exit (arXiv 2505.07686) | 35-61% length reduction | Complex implementation; different algorithm |

### Recommended Approach for MITS

**Use a combination:**

1. **Do NOT disable thinking during GRPO training.** Thinking traces are how the model solves hard STEM problems. Disabling thinking defeats the goal.

2. **Increase `max_completion_length` to 12288** (for A100 80GB with batch_size=1, num_generations=16, this stays within ~40-45GB VRAM with bf16). Monitor VRAM with `nvidia-smi`.

3. **Add overlong reward shaping** as a soft penalty reward term (not a main reward, but added to the aggregated reward):
   ```python
   def overlong_penalty(completion_len: int, L_max: int = 12288, L_cache: int = 3072) -> float:
       """Returns 0 if under budget, -1 at max, linear ramp in between."""
       if completion_len <= L_max - L_cache:
           return 0.0
       elif completion_len >= L_max:
           return -1.0
       else:
           return -(completion_len - (L_max - L_cache)) / L_cache
   ```

4. **Consider adding a `<think>` length penalty reward** that encourages shorter thinking traces when the answer is correct: `r_think_length = -alpha * (think_token_count / max_think_tokens)` added only when correctness reward = 1.

5. **Monitor S-GRPO** (arXiv 2505.07686) as a future upgrade — it explicitly trains early thinking exit using a serial group reward scheme and reduces think tokens by 35-61% without accuracy loss. Compatible with Qwen3.

---

## Q8: Unsloth + GRPO Known Issues

### Issue 1: batch_size vs. num_generations constraint

**Unsloth behavior (as of 2025-2026):** Unsloth enforces that `per_device_train_batch_size` must be a multiple of `num_generations`. If you set `per_device_train_batch_size=1` and `num_generations=16`, Unsloth will silently change `per_device_train_batch_size` to 16. This affects memory estimates and effective batch size.

**TRL behavior (v0.15+):** Enforces that `(num_processes * per_device_batch_size * gradient_accumulation_steps)` must be divisible by `num_generations`. Does NOT require batch_size == num_generations.

**Impact on training quality:** Using batch_size=num_generations means each optimization step sees exactly one group of completions for each prompt. With `gradient_accumulation_steps=4`, the effective batch covers 4 prompts. This is functionally correct but limits batch diversity — you want multiple prompts per gradient update.

**Workaround:** Set `per_device_train_batch_size=1` and `num_generations=4-8` (not 16) if Unsloth forces them to be equal. Or use standard TRL (not Unsloth's patched version) if you need independent control.

### Issue 2: `mask_truncated_completions=True` can cause KL=NaN

If all completions in a group are truncated, masking them all results in zero-masked KL computation. TRL may produce NaN loss. Unsloth issue #3149 (2025) confirms this.

**Mitigation:** Also set `overlong_filter=True` (when available) which skips entire groups with all-truncated completions rather than producing NaN.

### Issue 3: VRAM growth over steps (OOM)

Unsloth issue #3864 (2025): VRAM usage increases with each training step in some configurations, eventually OOM. Typically caused by KV cache not being cleared between rollout batches.

**Mitigation:** Set `torch.cuda.empty_cache()` in the training callback, or use Unsloth's `FastLanguageModel` with `max_seq_length` parameter set to the actual maximum sequence length.

### Issue 4: gradient_accumulation_steps not counted in batch validation

Unsloth doesn't account for `gradient_accumulation_steps` when checking batch/num_generations divisibility (issue #3149). This means the actual effective batch size may differ from what Unsloth validates.

### Recommendation

For MITS A100 training, consider switching from Unsloth's patched GRPOTrainer to standard TRL's GRPOTrainer directly, which has more predictable batch handling. Unsloth's memory optimizations (Flash Attention 2, gradient checkpointing) can be enabled independently via `model = AutoModelForCausalLM.from_pretrained(..., attn_implementation="flash_attention_2")`.

---

## Q9: LoRA Rank for 9B Models in GRPO

### Evidence from Literature

**Tina paper (arXiv 2504.15777, LoRA GRPO on DeepSeek-R1-Distill-1.5B):**

| Rank | Avg Performance |
|------|-----------------|
| 4 | 47.72% |
| 8 | 47.89% |
| 16 | **48.92% (peak)** |
| 32 | 48.47% |
| 64 | 46.95% |

LoRA r=16 is optimal; r=64 actually underperforms r=16 (likely due to overfitting / optimization instability at high ranks with RL).

**Scale caveat:** The Tina experiments used 1.5B. For 9B models, the intrinsic dimensionality of the update direction scales roughly with sqrt(model_size), suggesting r=16-32 remains appropriate. Full fine-tuning is only beneficial for very large datasets (>50K examples) at this scale.

**Unsloth LoRA guide (2025):** Recommends r=16 as default with lora_alpha=16 or lora_alpha=32. For RL (GRPO) specifically, recommends lower learning rates than SFT (5e-6 vs 2e-4).

**GRPO-specific consideration:** RL training is more susceptible to catastrophic forgetting than SFT. Lower ranks act as a regularizer — the bottleneck prevents the policy from drifting too far from the base distribution, which is especially important when KL `beta=0`.

### Recommendation

**Reduce LoRA rank from r=32 to r=16 for GRPO fine-tuning of Qwen3.5-9B.**

Configuration:
```python
r = 16
lora_alpha = 32  # alpha = 2*r is standard
target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                  "gate_proj", "up_proj", "down_proj"]
lora_dropout = 0.0  # Standard for RL, dropout hurts exploration
bias = "none"
```

If accuracy on hard STEM problems plateaus after 200 steps, increase to r=32 and restart from checkpoint.

---

## Comparison Table

| Topic | Current MITS Config | Research Finding | Action Required |
|-------|-------------------|-----------------|-----------------|
| clipped_ratio | `mask_truncated_completions=True` | Masking alone causes NaN if clipped_ratio>95%; need overlong reward shaping | Add soft penalty reward |
| GSPO epsilon | `epsilon=3e-4`, `epsilon_high=4e-4` | Correct per arXiv 2507.18071 Section 5.1 | None |
| GSPO IS level | `importance_sampling_level="sequence"` | Correct | None |
| Dr. GRPO loss | `loss_type="dr_grpo"` | Correct per arXiv 2503.20783 | Verify std normalization also disabled |
| Dr. GRPO std | Unknown | Should set `norm_adv_by_std=False` | Verify/add |
| ReDit sigma | `sigma=0.05` | Paper optimal is `a=0.05` (uniform) ≈ `sigma=0.029` Gaussian; 0.05 is slightly high but safe | Optional: test sigma=0.03 |
| GDPO normalization | Implemented | Correct per arXiv 2601.05242 | None |
| Curriculum weights | hard=2x, easy=0.5x | Paper uses logistic: B=1.5, A=0.4, rho0=0.75, k=10 | Fix weights formula |
| Thinking truncation | `max_completion_length` unknown | Needs 12288+; add overlong penalty | Increase length, add penalty |
| Unsloth batch | batch_size forced = num_generations | Known limitation; consider standard TRL | Monitor or migrate |
| LoRA rank | r=32 | r=16 is optimal per ablations | Reduce to r=16 |

---

## Priority Recommendations

### High Priority (Training Stability)

1. **Overlong reward shaping:** Add a soft penalty function that starts penalizing at `max_completion_length - 3072` tokens. This is the primary fix for high clipped_ratio and thinking model truncation. DAPO validated this in production.

2. **Increase `max_completion_length` to 12288:** Necessary for Qwen3.5-9B thinking traces to complete. Monitor VRAM consumption.

3. **Verify std normalization is disabled:** `loss_type="dr_grpo"` handles length normalization but not std normalization. Ensure `norm_adv_by_std=False` or equivalent is set.

### Medium Priority (Training Quality)

4. **Reduce LoRA rank to r=16:** Small but consistent improvement per Tina ablations. Easy change.

5. **Fix GRPO-LEAD weights to logistic formula:** Replace simple 2x/0.5x step with proper logistic function (A=0.4, B=1.5, rho0=0.75, k=10).

### Low Priority / Future Work

6. **Investigate S-GRPO** (arXiv 2505.07686): Reduces think tokens by 35-61% with +accuracy. Compatible with Qwen3. High implementation complexity but potentially major throughput improvement.

7. **Consider switching to standard TRL** (without Unsloth patching) to avoid batch size forcing and KL NaN bugs. Keep Unsloth only for model loading (Flash Attention, quantization).

8. **ReDit sigma tuning:** Test sigma=0.03 vs current 0.05 on a 50-step ablation.

---

## Key References

- GSPO: [arXiv 2507.18071](https://arxiv.org/abs/2507.18071) — Chujie Zheng et al., Qwen team
- GSPO Qwen blog: [qwenlm.github.io/blog/gspo](https://qwenlm.github.io/blog/gspo/)
- Dr. GRPO: [arXiv 2503.20783](https://arxiv.org/abs/2503.20783) — SAIL group, COLM 2025
- DAPO: [arXiv 2503.14476](https://arxiv.org/pdf/2503.14476) — ByteDance/Tsinghua
- ReDit: [arXiv 2506.18631](https://arxiv.org/abs/2506.18631)
- GDPO: [arXiv 2601.05242](https://arxiv.org/abs/2601.05242) — NVLabs
- GRPO-LEAD: [arXiv 2504.09696](https://arxiv.org/abs/2504.09696) — EMNLP 2025
- S-GRPO: [arXiv 2505.07686](https://arxiv.org/abs/2505.07686)
- Tina (LoRA rank): [arXiv 2504.15777](https://arxiv.org/html/2504.15777v1)
- TRL GRPOConfig: [HuggingFace docs](https://huggingface.co/docs/trl/en/grpo_trainer)
- GRPO++ tricks: [Cameron Wolfe Substack](https://cameronrwolfe.substack.com/p/grpo-tricks)
- Unsloth GRPO issues: [Issue #2583](https://github.com/unslothai/unsloth/issues/2583), [Issue #3149](https://github.com/unslothai/unsloth/issues/3149)
- GSPO in ms-swift: [swift docs](https://swift.readthedocs.io/en/latest/Instruction/GRPO/AdvancedResearch/GSPO.html)
