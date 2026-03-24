# Research Findings: Training Thinking LLMs with GRPO/GSPO
**Topic**: Thinking/Reasoning LLM Training — GRPO/GSPO Deep Dive
**Date**: 2026-03-19
**Researcher**: ML Research Agent (claude-sonnet-4-6)
**Scope**: 6 specific questions on DeepSeek-R1, Qwen3, TRL/Unsloth training practices

---

## Executive Summary

Thinking tokens in GRPO are **included in the policy gradient loss** (not masked) — the reward signal applies to the entire completion; this is the standard DeepSeek-R1, Qwen3, and TRL behavior. The unbounded thinking generation problem is a real and documented issue (vLLM issue #15418) with logits-processor workarounds available but not natively supported in TRL's GRPO rollout. ReDit dithering noise intentionally **replaces** zero-variance masking rather than interacting poorly with it — the two approaches are philosophically opposite and should not be combined directly; the paper suggests using noise instead of masking for zero-gradient groups.

---

## Question 1: Thinking Tokens in GRPO — Masked or Included?

### What DeepSeek-R1 does

DeepSeek-R1 (arXiv 2501.12948) uses a structured template with `<think>...</think>` and `<answer>...</answer>` tags. The GRPO objective applies over the **entire completion** (thinking + answer). The reward is computed only from the **final answer** (outcome-based), but the policy gradient loss propagates through **all tokens** in the completion, including thinking tokens.

Key quote from the paper (via multiple secondary sources): "the reward signal is solely based on the correctness of final predictions against ground-truth answers, without imposing constraints on the reasoning process itself." This means: reward is computed on answer only, but gradient flows through thinking tokens too.

This is the same approach used by Qwen3's GRPO stage (arXiv 2505.09388) and by open-r1 (HuggingFace). In TRL's GRPOTrainer, the default behavior is to apply policy gradient to all completion tokens; the reward function (user-defined) computes a scalar per completion, applied uniformly to all tokens in that completion.

### DuP-PO approach (token-level advantage scaling)

The paper "Do Thinking Tokens Help or Trap?" (arXiv 2506.23840) shows that thinking tokens in incorrect responses contain 2x as many tokens as in correct responses, suggesting quality issues. Their method DuP-PO introduces **token-level advantage scaling**:
- Amplify gradient for thinking-free correct responses
- Suppress gradient (magnify negative advantage) for thinking tokens in failed responses
- Zero out gradient for thinking tokens when equivalent thinking-free solutions exist

This is an improvement over vanilla GRPO, but requires custom implementation. The result: +3.5 accuracy points on MATH500 with -24.7% token reduction vs base model.

### Practical implication for MITS

The current MITS notebook uses `enable_thinking=True` with thinking tokens included in loss — **this is correct per DeepSeek-R1 and Qwen3 precedent**. The model needs thinking to solve STEM (verified: accuracy ~0% without thinking). There is no need to mask thinking tokens from the policy gradient; the standard approach is to let the reward signal propagate through them.

### Max Completion Lengths Used in Practice

| System | Max Completion | Notes |
|---|---|---|
| DeepSeek-R1 (full) | 32,768 tokens | From Azure/deployment config |
| DAPO (arXiv 2503.14476) | 20,480 tokens | 16,384 expected + 4,096 cache |
| Dr. GRPO recipe | 3,000–8,000 tokens | Smaller models, math tasks |
| Tina (1.5B LoRA) | 3,584 tokens | Minimal viable setting |
| Qwen3 inference | 16,384–32,768 tokens | Model card defaults |
| MITS notebook | 2,048 tokens | Constrained by A100 memory + curriculum stage |

**Note on MITS 2,048 tokens**: This is deliberately small (curriculum stage 1). The truncation penalty (0 correctness reward on truncated completions) trains conciseness. This is a valid training signal. The DAPO overlong reward shaping strategy achieves the same goal with a smoother gradient.

---

## Question 2: Unbounded Thinking Generation — Real Issue?

### Confirmed problem

The vLLM issue #15418 "Feature: Limit thinking tokens" (open, active PR #20859 "limit thinking tokens hard limit") confirms this is a real and documented problem. Key findings:

- **Root cause**: Thinking models (Qwen3, DeepSeek-R1 distills) can enter "looping or other bad modes" during rollout, generating indefinitely without emitting `</think>`
- **Impact in GRPO training**: If rollout uses vLLM/huggingface generate without a hard stop, a single bad rollout can consume all GPU VRAM and stall training
- **Frequency**: More common with bad checkpoints mid-training or when the model is being pushed outside distribution

### Known workarounds

**Workaround A: LogitsProcessor injection (inference-time)**
Zach Mueller's `ThinkingTokenBudgetProcessor` (blog post: muellerzr.github.io/til/end_thinking.html):
- Tracks generated token count
- At 95% of budget: boosts logits for `\n` and `</think>` tokens
- At budget limit: sets all logits to -inf except `\n` (budget-1) and `</think>` (budget), forcing emission
- Critical edge case: the model expects `\n</think>` as a two-token sequence, not bare `</think>`

```python
# Pseudo-code for GRPO rollout integration
from transformers import LogitsProcessor

class ThinkingBudgetProcessor(LogitsProcessor):
    def __init__(self, think_end_token_id, newline_id, max_thinking_tokens):
        self.think_end_id = think_end_token_id
        self.newline_id = newline_id
        self.max_thinking = max_thinking_tokens
        self.count = 0
        self.in_think = True

    def __call__(self, input_ids, scores):
        self.count += 1
        if not self.in_think:
            return scores
        if self.count >= self.max_thinking:
            # Force </think>
            scores[:] = float('-inf')
            scores[:, self.think_end_id] = 0.0
            self.in_think = False
        elif self.count >= int(0.95 * self.max_thinking):
            # Nudge toward ending
            scores[:, self.think_end_id] += 5.0
            scores[:, self.newline_id] += 3.0
        return scores
```

**Workaround B: max_new_tokens hard cap (blunt but simple)**
In TRL GRPOTrainer, set `max_completion_length` to limit total completion. If the model spends all tokens in `<think>` without emitting `</think>`, the completion is truncated. With `mask_truncated_completions=False` (MITS current setting), truncated completions get 0 correctness reward — this is a negative signal that trains the model to be concise. Effectively, the truncation budget acts as a soft upper bound on thinking length.

**Workaround C: Qwen3 native `enable_thinking=False` with explicit CoT**
Disable thinking mode and ask the model to reason explicitly in the answer. See Question 6.

**Status in TRL/vLLM**: Native `max_thinking_tokens` support in vLLM is in an open PR. TRL does not currently support a dedicated per-phase token budget during rollout. The cleanest solution for MITS is Workaround B (already implemented) combined with tracking whether completions are truncated-in-thinking vs truncated-in-answer during logging.

---

## Question 3: GRPO with Very Sparse Reward (~5% Correct)

### Why 5% is particularly dangerous

At 5% accuracy, within a group of G=8 completions, the probability of all completions being wrong = 0.95^8 ≈ 66%. This means ~66% of groups will have zero-gradient (all wrong, zero variance), and ~34% have exactly 1-2 correct completions but with very high variance in advantages. The result: oscillating, noisy training with frequent gradient spikes.

### Approaches from the literature

**Approach A: Cold-start SFT (DeepSeek-R1 approach)**
Before RL, collect a small set of long-CoT examples via rejection sampling and SFT on them. This "cold start" raises baseline accuracy to 15-30% before RL begins, putting you in a much more tractable reward density regime.
- Effort: 200-500 SFT steps on 1k-10k rejection-sampled correct solutions
- Effect: Shifts problem from "can the model ever get it right?" to "can the model do it more reliably?"
- DeepSeek-R1 paper explicitly states: "to prevent the early unstable cold start phase...the team started with supervised fine-tuning"

**Approach B: Curriculum learning (GRPO-LEAD, arXiv 2504.09696)**
Train only on easy and medium problems in Stage 1. Easy problems have 40-80% accuracy — ideal reward density. Introduce hard problems in Stage 2 with difficulty-aware advantage reweighting.
- Practical: 60% easy / 40% medium in early training, then add hard
- MITS notebook already implements this (Stage 1: easy+medium, Stage 2: all)

**Approach C: HAPO — Hindsight-Anchored Policy Optimization (arXiv 2603.11321)**
When group confidence (success rate) falls below threshold γ=0.8, inject a verified teacher demonstration into the group by replacing the worst trajectory with a known-correct solution. This provides anchor gradients during low-confidence failure modes.
- Results: +9.7 AIME2024 points, +4.0 MATH-500 points over vanilla GRPO
- Implementation: Requires access to correct solutions during training (available in MITS via verifier)

**Approach D: Dynamic Sampling (DAPO technique)**
Filter out groups where all completions are wrong (0% accuracy) or all correct (100% accuracy) from the batch. Keep re-sampling until batch is filled with "informative" groups (partial success). This doubles effective training signal but may slow down batch construction.
- Implemented in TRL as conceptual basis for filtering
- In practice: use `num_generations > batch_size` and filter, or pre-filter problem set

**Approach E: ReDit noise (arXiv 2506.18631)**
Add Gaussian noise N(0, 0.05^2) to rewards before advantage computation. This converts zero-variance groups (all 0 reward) into low-variance groups with small but non-zero gradients. Empirically achieves ~10x faster convergence to same performance level.
- Compatible with curriculum learning (can be applied on top of other methods)
- Does not fully solve the cold-start problem — if accuracy is 0%, noise merely adds exploration noise rather than correct signal

**Approach F: Higher learning rate (not recommended)**
Increasing LR with sparse reward tends to cause instability (policy collapse or entropy explosion) rather than helping. The real problem is lack of gradient signal, not magnitude. Lower LR (1e-6 to 5e-6) is more stable with sparse reward.

### Recommended strategy for MITS at 5% accuracy

1. Run 100-300 SFT steps on rejection-sampled correct solutions (cold start) to raise baseline to ~15-25%
2. Enable curriculum (easy+medium only, Stage 1) — MITS already has this
3. Use ReDit noise (sigma=0.05) — MITS already has this
4. Use dynamic sampling: set `num_generations=16` with filtering to get 8 informative completions per step
5. LR = 5e-7 to 1e-6 (very conservative) in early training; increase after first 100 steps

---

## Question 4: ReDit Noise vs Zero-Variance Group Masking

### The fundamental conflict

ReDit (arXiv 2506.18631) and zero-variance group masking (DAPO dynamic sampling) address the same problem — zero-gradient all-wrong or all-right groups — but with opposite strategies:

| Approach | Mechanism | Effect on Zero-Variance Groups |
|---|---|---|
| Zero-variance masking (DAPO) | Remove groups from batch | Group excluded; no gradient contribution |
| ReDit noise | Add N(0, σ²) to all rewards | Group gets small non-zero gradient from noise |

**If you use both simultaneously**, here is what happens:
- A group with all-0 rewards becomes [noise_1, noise_2, ..., noise_8] after ReDit
- These noise values have non-zero variance, so the masking threshold (std < epsilon) would NOT trigger
- The group passes through to gradient computation with noise-only advantages
- Effectively, ReDit **defeats zero-variance masking** on bad groups

### ReDit paper's position on this

The ReDit paper explicitly frames noise as a **replacement** for zero-variance masking, not a complement. The paper states that noise "provides informative, non-zero gradients even when discrete rewards are sparse or identical within a batch, mitigating gradient vanishing" and shows this is sufficient without masking. The paper's experiments do not use dynamic sampling alongside ReDit.

### Recommendation for MITS

**Do not use both simultaneously in their pure forms.** Three options:

**Option A: ReDit only, no masking** (paper-recommended)
Add noise sigma=0.05 to all rewards. Zero-variance groups get exploration gradients from noise. Simple, validated in paper.

**Option B: Masking only, no ReDit** (DAPO-recommended)
Filter zero-variance groups from batch. Slower batch construction but purer gradient signal.

**Option C: Adaptive combination** (not in literature, use with caution)
Apply masking to fully-saturated groups (all correct, 100%: definitely skip, pure noise would be harmful). Apply ReDit to all-wrong groups (0%: exploration noise may help). This requires custom logic:
```python
if group_accuracy == 1.0:
    skip_group()  # no gradient, model already correct
elif group_accuracy == 0.0:
    apply_redit_noise(sigma=0.02)  # small exploration noise
else:
    apply_redit_noise(sigma=0.05)  # standard ReDit
```

**MITS current config uses ReDit; remove any zero-variance masking (dynamic sampling) to avoid conflict**, or use Option C above.

---

## Question 5: Best LoRA Rank for RL Fine-tuning

### Empirical evidence

**Tina ablation (arXiv 2504.15777) — most rigorous source**
Tested r=4, 8, 16, 32, 64 on 1.5B model for reasoning RL:
- r=16: **48.92%** (peak)
- r=32: 48.47% (-0.45% vs r=16)
- r=8: 47.89% (-1.03% vs r=16)
- r=64: 46.95% (**underperforms** r=16 by -1.97%)
- r=4: 47.72%

Key finding: "r=16 or r=32 are effective; r=64 shows degraded performance"

**ESSA/SVD-GRPO comparison**
"SVD-GRPO with rank 16 plateaus around 0.5 accuracy and degrades further as the rank decreases" — suggesting even r=16 can plateau; ESSA's r=2 evolutionary approach outperformed all LoRA ranks but requires very different methodology.

**BF16 vs FP16 stability finding**
"BF16-based LoRA training collapses after roughly 600 steps, whereas FP16 maintains stable training throughout." This is a more impactful variable than rank choice. Switch to FP16 or use mixed precision.

### Why high rank (r=64) underperforms for RL

1. More parameters = harder to stabilize under RL's noisy gradients
2. RL training is more susceptible to catastrophic forgetting than SFT; higher rank = more capacity for forgetting base model behaviors
3. Without KL regularization (beta=0.0 in GSPO/DAPO), higher rank adapters can diverge from the initial distribution faster
4. The policy needs **regularization** more than **capacity** for RL

### Recommendation for MITS (9B model)

**Primary: r=16, lora_alpha=32 (alpha = 2x rank)**
- Strongest evidence from Tina ablation (peak performance)
- Good regularization without underfitting
- Lower memory footprint than r=32

**Alternative: r=32, lora_alpha=32 (alpha = 1x rank)**
- Use if performance plateaus at r=16 after 200+ steps
- MITS current notebook uses r=32 — this is acceptable but r=16 may be better

**Targets for LoRA**: query, key, value, dense (all attention weights). Adding gate/up/down_proj (MLP) generally hurts RL stability without benefit for reasoning tasks.

**Precision**: Use FP16 or mixed-precision (bf16 for forward, fp32 for LoRA weights) to avoid training collapse at step 600.

---

## Question 6: CoT Prompting vs Thinking Mode for GRPO

### What Qwen3 "thinking mode" actually is

`enable_thinking=True` in Qwen3 causes the model to:
1. Begin with `<think>` token
2. Generate free-form reasoning until `</think>`
3. Then generate the final answer

This is **trained behavior** from Qwen3's 4-stage training pipeline (Stage 2: reasoning RL with thinking). The model has strong priors for this pattern.

`enable_thinking=False` causes the model to skip thinking and answer directly, which for STEM problems leads to ~0% accuracy (as verified in MITS experiments).

### Can explicit CoT (in-answer reasoning) replace thinking mode?

**Theory**: Instead of `<think>reasoning</think>answer`, use a format where reasoning is embedded in the answer:
```
Step 1: ...
Step 2: ...
...
Therefore: [final answer]
```

**Evidence for feasibility**:
- MATH and GSM8K training with explicit CoT in output (no special tokens) achieves competitive results with trained reasoning models on smaller tasks (DAPO paper)
- OpenReasonerZero trains base models from scratch with pure GRPO using visible CoT format
- SofT-GRPO (arXiv 2511.06411) replaces discrete tokens with soft thinking embeddings — shows the mechanism is flexible

**Evidence against for Qwen3-Instruct**:
- Qwen3 Instruct has strong priors for thinking mode; forcing it out of thinking mode for complex STEM causes near-0% accuracy
- The model's reasoning capability is deeply tied to its `<think>` phase (trained in Stage 2 of Qwen3 pipeline)
- "merely adding a reasoning chain does not yield substantial improvements" without RL training (from Qwen3 technical report context)

**Practical conclusion**:
For a **base model** (Qwen3.5-9B-Base) or a model you are training from scratch, explicit CoT format is a viable alternative to thinking mode — it avoids the `</think>` generation problem entirely and keeps all reasoning visible in the output for reward computation. For **Qwen3.5-9B-Instruct** (MITS current model), switching to explicit CoT would require a cold-start SFT phase to teach the new format, and would sacrifice the thinking capability the Instruct model already has.

**Recommendation for MITS**: Stay with `enable_thinking=True`. The verified ~0% accuracy without thinking confirms the model genuinely needs its thinking phase for STEM. Use `max_completion_length=2048` (current setting) as a hard cap to prevent unbounded thinking. The truncation penalty (0 reward on truncated completions) implicitly limits thinking length over training.

---

## Comparison Table

| Topic | Best Practice | Source | MITS Current Setting | Status |
|---|---|---|---|---|
| Thinking tokens in loss | Include all tokens in PG loss, reward from answer only | DeepSeek-R1, Qwen3, TRL default | Correct (TRL default) | OK |
| Max completion length | 2k-32k depending on hardware; 8k+ for harder problems | DAPO, DeepSeek-R1 | 2,048 (Stage 1) | OK for Stage 1; consider 4k-8k for Stage 2 |
| Unbounded thinking fix | LogitsProcessor hard-force `</think>`, or max_completion truncation | vLLM #15418, muellerzr blog | max_completion=2048 hard cap | Acceptable workaround |
| Sparse reward (<10%) | Cold-start SFT + curriculum + dynamic sampling / HAPO | DeepSeek-R1, GRPO-LEAD, HAPO | Curriculum yes; cold-start no | Add cold-start SFT if training from base |
| ReDit + zero-var masking | Use one or the other, not both | ReDit paper | ReDit only (remove masking) | OK (no dynamic sampling in config) |
| LoRA rank | r=16 optimal; r=32 acceptable; r=64 degrades | Tina arXiv 2504.15777 | r=32 | Acceptable; try r=16 |
| CoT vs thinking mode | Keep thinking mode for Instruct models; CoT fine for base models | Qwen3 tech report, MITS experiments | enable_thinking=True | OK |

---

## Key Papers Referenced

| Paper | arXiv ID | Relevance |
|---|---|---|
| DeepSeek-R1 | 2501.12948 | Canonical GRPO+thinking training reference |
| DAPO | 2503.14476 | 4 key GRPO improvements; max_completion 20480; Clip-Higher |
| Dr. GRPO | 2503.20783 | Length+difficulty bias removal; 3000 token budget; 43.3% AIME7B |
| GSPO | 2507.18071 | Qwen3's algorithm; sequence-level IS; epsilon=3e-4/4e-4 |
| Tina | 2504.15777 | LoRA rank ablation: r=16 optimal, r=64 degrades |
| ReDit | 2506.18631 | Reward dithering; sigma=0.05 optimal; 10x faster convergence |
| S-GRPO | 2505.07686 | Early exit from thinking; 35-61% token reduction |
| DuP-PO | 2506.23840 | Token-level advantage scaling for thinking tokens |
| HAPO | 2603.11321 | Sparse reward via teacher injection; +9.7 AIME points |
| Noise-corrected GRPO | 2510.18924 | Noisy reward correction; different from ReDit |
| Elastic Reasoning | 2505.05315 | Separate thinking/answer budgets; force </think> at budget |
| GRPO-LEAD | 2504.09696 | Difficulty-aware advantage reweighting |
| Qwen3 technical report | 2505.09388 | 4-stage training pipeline; GSPO for reasoning RL |

---

## Implementation Recommendations for MITS

### Immediate (before next training run)

1. **Check ReDit + masking conflict**: Confirm the current notebook does not apply both dynamic sampling (zero-variance masking) and ReDit. If it does, disable dynamic sampling.

2. **Logging for truncation analysis**: Add a reward logging component that tracks *where* completions are truncated (in `<think>` phase vs in answer phase). This helps diagnose whether 2048 tokens is sufficient.

3. **LoRA precision**: Verify LoRA weights are in FP16 or mixed precision. BF16 LoRA collapses after ~600 steps.

### Stage 2 adjustments

4. **Increase max_completion to 4096-8192 for Stage 2** (harder problems need more thinking space). Re-evaluate memory budget on A100 80GB.

5. **Consider cold-start SFT if GSPO Stage 1 results show stagnation at <10% accuracy after 50+ steps**. Collect correct solutions via temperature=0.7 sampling and SFT for 200 steps before resuming RL.

6. **LoRA rank**: Experiment with r=16 if r=32 shows instability after step 600 (BF16 collapse marker).

---

## References

- [DeepSeek-R1 paper (arXiv 2501.12948)](https://arxiv.org/abs/2501.12948)
- [DAPO paper (arXiv 2503.14476)](https://arxiv.org/abs/2503.14476)
- [Dr. GRPO / Understanding R1-Zero (arXiv 2503.20783)](https://arxiv.org/abs/2503.20783)
- [GSPO paper (arXiv 2507.18071)](https://arxiv.org/abs/2507.18071)
- [Qwen3 technical report (arXiv 2505.09388)](https://arxiv.org/abs/2505.09388)
- [Tina: Tiny Reasoning via LoRA (arXiv 2504.15777)](https://arxiv.org/abs/2504.15777)
- [ReDit: Reward Dithering (arXiv 2506.18631)](https://arxiv.org/abs/2506.18631)
- [S-GRPO: Early Exit (arXiv 2505.07686)](https://arxiv.org/abs/2505.07686)
- [DuP-PO: Do Thinking Tokens Help or Trap? (arXiv 2506.23840)](https://arxiv.org/abs/2506.23840)
- [HAPO: Hindsight-Anchored PO (arXiv 2603.11321)](https://arxiv.org/abs/2603.11321)
- [Elastic Reasoning (arXiv 2505.05315)](https://arxiv.org/abs/2505.05315)
- [GRPO-LEAD (arXiv 2504.09696)](https://arxiv.org/abs/2504.09696)
- [Noise-corrected GRPO (arXiv 2510.18924)](https://arxiv.org/abs/2510.18924)
- [Limiting Qwen3 Thinking (muellerzr blog)](https://muellerzr.github.io/til/end_thinking.html)
- [vLLM limit thinking tokens issue #15418](https://github.com/vllm-project/vllm/issues/15418)
- [DAPO comparison analysis (arXiv 2512.07611)](https://arxiv.org/abs/2512.07611)
- [TRL open-r1 update #2](https://huggingface.co/blog/open-r1/update-2)
- [GRPO++ practical tricks](https://cameronrwolfe.substack.com/p/grpo-tricks)
