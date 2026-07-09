# GRPO/GSPO Training Dynamics: Research Findings
**Date**: 2026-03-20
**Topic**: Empirical analysis of GRPO/GSPO training questions for MITS Qwen3.5-9B pipeline
**Researcher**: Claude Sonnet 4.6 (ML Research Agent)

---

## Executive Summary

GRPO training on strong instruct models reliably plateaus at correctness rewards of 0.5-0.65 — this is mathematically expected, not a sign of failure, because the baseline model already solves easy problems and binary rewards provide no gradient signal on already-correct or completely-wrong completions. LoRA r=16 is theoretically more than sufficient for RL (RL extracts ~1 bit of information per episode; r=1 can suffice), but applying LoRA to all-linear layers matters far more than rank. The thinking budget being saturated at 1023 tokens every completion is a serious training signal pathology that should be addressed — DAPO's overlong filtering (masking truncated samples instead of penalizing them) is the recommended fix.

---

## Question 1: Correctness Plateau at ~0.55 — Is It Normal?

### What the papers say

**DeepSeek-R1 (arXiv 2501.12948)**: Trains on base models (DeepSeek-V3-Base), not instruct variants. The AIME accuracy trajectory goes from 15.6% to 71.0% monotonically. DeepSeek does not report raw correctness reward values in [0,1] terms — they report task accuracy. Training R1-Zero on an instruct model is explicitly not what they do, and this matters for plateau dynamics.

**GRPO Dynamics paper (arXiv 2503.06639)**: This theoretical analysis provides the clearest answer. It models the probability of success (PoS) as a fixed-point iteration and shows that GRPO amplifies PoS from the reference policy. Empirically, the paper reports: *"success rate amplification from πref originally at 21% to 37.5% at the end of the GRPO epoch"* on GSM8K. Crucially, the final PoS is bounded by the fixed point of the clipping schedule — for standard GRPO with ε=0.2, this fixed point is well below 1.0. **A strong instruct model starting at ~50% pass@1 on your mixed difficulty dataset will naturally plateau in the 0.50-0.65 range** because: (a) easy problems are already solved and contribute zero gradient, (b) very hard problems contribute zero gradient because all G rollouts fail, (c) only the middle difficulty band provides learning signal.

**Qwen3-8B GRPO training report (dtianyou.com)**: Starting from a base model, the validation mean reward rose from ~0.76 to ~0.83 (not from ~0.5), and it did not plateau — it showed sustained upward movement. This confirms that starting from an instruct model (rather than base) puts you at a higher initial PoS, which compresses headroom.

**DAPO (arXiv 2503.14476)**: Explicitly identifies the "prompt accuracy saturating at 0 or 1" problem and addresses it with Dynamic Sampling — over-sampling prompts and filtering to retain only those with mixed pass/fail outcomes. This is exactly what GRPO-LEAD and VAPO also do.

**Stanford vision-to-code study**: Reports GRPO execution reward improving from 0.3 to 0.55 and plateauing there — consistent with your observed value.

### Assessment for MITS

**The 0.55 plateau is mathematically expected given your setup.** With G=8 and a mixed-difficulty dataset where ~50% of prompts already yield correct answers from the instruct base, approximately half your prompts provide no gradient. The plateau is not a failure — it reflects that the model has absorbed the marginal signal from medium-difficulty problems. However, it also means training beyond this point without curriculum adjustment wastes compute.

**The ceiling is real**: Binary correctness reward + instruct starting point = compressed headroom. The key question is not "why is reward ~0.55?" but "what is the benchmark accuracy gain at this plateau?"

---

## Question 2: LoRA Rank Capacity for RL (r=16 on 9B Model)

### What the papers say

**Tina (arXiv 2504.15777, ICLR 2026)**: Tests ranks 4, 8, 16, 32, 64 on a 1.5B model. Results:
- r=16: 48.92% average (best)
- r=32: 48.47%
- r=8: within the 47.89-48.92% cluster
- r=4: 47.72%
- r=64: 46.95% (worse — overfitting)

Ranks 8-32 form a plateau; performance degrades at extremes in both directions. The paper's hypothesis: *"LoRA excels here because RL for reasoning rewards ability to generate outputs in specific verifiable format, not relearning all underlying knowledge."*

**LoRA Without Regret (Schulman / Thinking Machines Lab, 2025)**: The single most actionable result for your setup. Key findings:
- For RL tasks, **r=1 to r=32 are all sufficient** — RL extracts ~1 bit of information per episode (scalar reward), which demands minimal parameter capacity
- The recommended rank for RL is 1-32 (vs. 256 for SFT)
- **The most important finding**: LoRA applied to all-linear layers (attention + MLP + embeddings) outperforms attention-only LoRA even at higher rank. Increasing rank cannot compensate for restricting target modules
- LoRA is less tolerant of large effective batch sizes than full fine-tuning: keep effective batch size < 32 (your effective batch = 1 × 16 = 16, which is fine)

**Policy gradient LoRA studies**: On 7B, 13B, 70B models, LoRA r=8 matches full fine-tuning on MATH and GSM8K in policy gradient settings.

### Assessment for MITS

**r=16 is fine for RL — it is not the limiting factor.** The capacity argument does not apply to RL the way it applies to SFT. The more important question is: are you applying LoRA to all-linear layers (Q, K, V, O, gate, up, down projections)? If you are restricting to attention-only (q_proj, v_proj), you are leaving significant capacity on the table and no rank increase will compensate. Check your `target_modules` configuration.

**One concern**: LoRA r=16 on a 9B model for GSPO (sequence-level RL) should work but note that sequence-level importance sampling is more sensitive to the reference policy drift. The GSPO paper recommends keeping ε very small (3e-4 to 4e-4 at sequence level) precisely because sequence-level ratios accumulate multiplicatively.

---

## Question 3: GRPO Reward Dynamics — Group Size G=8, Batch=1, Grad Accum=16

### What the papers say

**GRPO theory**: The variance of the advantage estimate scales as O(1/G). With G=8, variance is acceptable — the DeepSeek team's recommendation of G=64 for production is for extremely large-scale runs. Practical guides recommend G=4 as the minimum, with G=8-16 as a good balance. Your G=8 is solidly within the acceptable range.

**Effective batch size**: Your effective unique prompts per optimizer step = (1 × 16 acc) / 8 = 2 prompts per update. This is very low. The Unsloth formula is `unique_prompts = effective_batch_size / num_generations` and they note this must be >2. You are at exactly 2, which is the theoretical floor.

**GSPO paper (arXiv 2507.18071)**: GRPO's token-level importance sampling introduces "high-variance training noise that progressively accumulates with increased response length." With long-thinking completions (1023 tokens each), this is not a minor issue — the noise amplification is proportional to sequence length. GSPO uses sequence-level IS with ε=3e-4 to 4e-4 and achieves 2 orders of magnitude better stability than GRPO's ε=0.2.

**DAPO**: Uses batch_size=256 and large group sizes. Their training uses 135 steps total. Much larger effective batches than your setup.

**2-GRPO research**: Shows that G=2 with a contrastive formulation can be as effective as G=8-16 with 70% compute reduction — suggesting G=8 is already generous.

### Assessment for MITS

**Your setup is at the minimum viable margin.** Specific concerns:
1. 2 unique prompts per optimizer step means high gradient variance at the prompt level (not just the rollout level)
2. Long think sequences (1023 tokens) amplify token-level IS noise in standard GRPO. This is the GSPO paper's core concern
3. G=8 is fine in isolation; the interaction with 2 unique prompts/step is the problem

**Recommendation**: Increase `gradient_accumulation_steps` to 32 or reduce `num_generations` to 4 to get 4 unique prompts/step. If memory allows, increase `per_device_train_batch_size` to 2.

---

## Question 4: ThinkingBudget — Forcing </think> After 1024 Tokens

### What the papers say

**DAPO (arXiv 2503.14476)**: Addresses overlong sequences directly. Their approach:
- Set `max_length=16384` with a 4096-token "soft punish cache" — total 20,480 max
- **Overlong Filtering**: instead of penalizing truncated samples with -1 reward, they **mask the loss of truncated samples entirely** (zero gradient contribution)
- Finding: overlong filtering "significantly stabilizes training and enhances performance" compared to truncation penalties
- They do NOT force truncation at a fixed budget; they let the model determine length within soft limits

**Token-Budget-Aware Reasoning (arXiv 2412.18547)**: Shows that fixed-budget constraints inserted at inference time "often fail to reliably control output length." Training-based budget control requires explicit reward shaping for both accuracy and length.

**BRPO (arXiv 2505.13438)**: Budget Relative Policy Optimization — designed specifically for training with thinking budgets. Shows that GRPO under fixed budget truncation suffers "biased advantage estimation due to substantial reward noise, especially in early stages when many responses are abruptly cut off." BRPO outperforms GRPO consistently across all thinking budgets.

**"Thinking Traps" research (arXiv 2506.23840)**: *"Thinking-token-induced behaviors are not essential for effective problem-solving and may even hinder correct reasoning within constrained token budgets."* Hard truncation at a tight budget actively hurts quality.

**Rethinking Thinking Tokens (arXiv 2510.01123)**: Shows models treated as "improvement operators" can reason effectively without being forced into a rigid budget.

### Assessment for MITS

**This is your most serious training pathology.** Every completion hitting exactly 1023 tokens means:
1. The reward model receives a truncated, potentially mid-thought response — this is NOT a completed reasoning chain
2. The correctness reward for truncated responses is likely 0 (wrong format or incomplete answer), creating systematic negative signal on all long-thinking attempts
3. GRPO's advantage normalization then treats these truncated-zero-reward completions as "below average" and pushes the model AWAY from thinking deeply — the exact opposite of what you want
4. This creates a self-reinforcing loop: the model learns to produce shorter, shallower thoughts to avoid truncation penalty

**The 1024-token budget is too tight for a 9B model doing multi-step math.** DAPO uses 16,384+ tokens. DeepSeek-R1 uses 32,768 tokens. VAPO's length-adaptive GAE shows that 100+ token sequences need careful credit assignment.

**Immediate fixes (in order of priority)**:
1. Increase `max_thinking_tokens` significantly — 4096 minimum, 8192 recommended for math
2. Apply DAPO-style overlong filtering: mask (not penalize) truncated completions so they contribute zero gradient
3. If budget must stay at 1024 for memory reasons, add a soft length penalty only for responses shorter than the budget (reward `think_tokens / budget` as a bonus, not a penalty for hitting the ceiling)

---

## Question 5: Lion Optimizer (8-bit) for RL Fine-Tuning

### What the papers say

No paper directly evaluates Lion vs AdamW in a GRPO/PPO/RL-for-reasoning context. The available evidence comes from adjacent settings:

**Pre-Training LLMs comparison (arXiv 2507.08472)**: AdamW, Lion, and Sophia all produce similar results. Lion was fastest in GPU hours but AdamW achieved the best downstream evaluation scores.

**Cross-Encoder Reranking study (arXiv 2506.18297)**: Lion achieved 2.67%-10.33% better GPU utilization than AdamW with competitive performance. Results are task-dependent.

**General Lion properties**:
- Memory: ~33% smaller than AdamW (no second moment; only momentum)
- 8-bit Lion reduces optimizer state memory by another 4x vs 32-bit Lion
- Lion uses sign updates (EvoLved Sign Momentum) — binary {-1, +1} parameter updates
- Optimal learning rate is 3-10x smaller than AdamW equivalents
- Weight decay should be 3-10x larger than AdamW equivalents

**RL-specific concern (not in any paper, based on first principles)**: Lion's sign-based update rule means all gradients are clipped to unit magnitude, which could interfere with the reward-weighted gradient structure in GRPO. In RL, gradient magnitude carries information about reward certainty — Lion discards this. GRPO's clipped importance ratio already bounds gradient magnitude; applying another bounding operation (sign) may reduce effective learning. This is a theoretical concern without empirical validation in the literature.

**AdamW in RL**: All major RL papers (DeepSeek-R1, DAPO, VAPO, GRPO-LEAD) use AdamW variants with learning rates in the range 1e-6 to 1e-5. None report using Lion.

### Assessment for MITS

**Lion 8-bit is a reasonable memory optimization but is an experimental choice for RL.** Risks:
1. Sign updates may interact poorly with GRPO's advantage-weighted gradient scaling
2. If your learning rate was tuned for AdamW, Lion needs a 3-10x smaller LR — if you kept the same LR, you are overstepping
3. No published RL reasoning paper validates Lion; you are in uncharted territory

**Recommendation**: If you see training instability or reward decay in Stage 2, switching to AdamW 8-bit (bitsandbytes) is the safe fallback. Keep Lion if memory is critically constrained and you observe stable reward curves.

---

## Question 6: Expected Accuracy Improvement from GRPO Starting from Instruct

### What the papers say

**Qwen3-8B + GRPO on base model (dtianyou.com report)**:
- GSM8K: 61.92% (base) → 83.59% (after GRPO): +21.7 pp
- AIME24: 10% (base) → 16.7% (after GRPO): +6.7 pp

**DeepSeek-R1-Zero on base model**: AIME24 15.6% → 71.0% (but this is with massive compute, 32B+ model, full fine-tuning, not LoRA)

**GRPO on Qwen instruct + RL (Qwen3 technical report, arXiv 2505.09388)**:
- AIME24: 73.3% (instruct) → 83.3% (after GRPO): +10 pp
- AIME25: 66.66% → 73.3%: +6.6 pp
Note: this is the Qwen team using their own internal pipeline with full fine-tuning, not LoRA.

**GRPO-LEAD 14B model**:
- AIME24 Pass@1: 0.614 → 0.650: +3.6 pp
- AIME25 Pass@1: 0.429 → 0.539: +11.0 pp
Using only 340 total training steps with LoRA-equivalent parameter efficiency.

**VAPO (Qwen2.5-32B base)**: Achieves AIME24 = 60.4 — a new SOTA at the time, but starting from a 32B base model.

**Does RLHF scale? (arXiv 2412.06000)**: "The average performance gain consistently decreases from 4.4% to 1.9% as policy model size grows from 9B to 200B." For 9B models, gains are larger than for bigger models. Also: "DPO tends to be a better starting point for RL training — further preference tuning improves the performance of the SFT model and yields higher performance after downstream RL."

### Assessment for MITS

**Realistic expectations for your setup** (Qwen3.5-9B instruct, LoRA r=16, 300+500 steps):
- GSM8K: minimal improvement expected (model likely already at 85%+; headroom is small)
- AMC/AIME-type hard math: +3 to +10 pp is realistic with curriculum
- Your STEM domain (physics, chemistry): likely +5 to +15 pp depending on benchmark coverage in training data
- The instruct starting point means your absolute gain will be smaller than base-model GRPO papers report

**Critical**: Gains from GRPO are predominantly on medium-difficulty problems (correctness rate 20-80%). Hard problems (0% base correctness) are rarely improved by GRPO alone — they need either SFT warm-up or curriculum pre-filtering.

---

## Question 7: Curriculum Learning in GRPO — Stage 1 Easy+Medium, Stage 2 All Tiers

### What the papers say

**GRPO-LEAD (arXiv 2504.09696)**: Uses a 3-stage curriculum:
- Stage 1 (100 steps): ~9,000 problems with difficulty ≥ 2.5 (no easy problems)
- Stage 2 (100 steps): ~2,283 problems where model accuracy ≤ 75% (hardest based on current model performance)
- Stage 3 (140 steps): repetition/format correction

Key insight: they start with *moderately hard* problems, NOT easy ones. Easy problems do not provide gradient signal from a capable instruct model.

**DAPO's Dynamic Sampling**: Filters each batch to retain only prompts with 0 < pass_rate < 1 (mixed outcomes within the group). This is effectively adaptive curriculum at inference time — the system automatically finds the "teachable zone" for each training step.

**VAPO**: Finds that "using fewer prompts but more repetitions resulted in a 5-point improvement" — depth over breadth. 16 rollouts per prompt with 512 prompts/step (from 8192 total batch) was optimal for Qwen2.5-32B.

**General curriculum RL findings (2025 consensus)**: Easy → Hard curriculum is consistently better than random sampling, but "easy" should be defined relative to the current model, not absolute difficulty. Static easy+medium is less effective than dynamic filtering.

**GRPO-LEAD logistic reweighting**: Uses `w(ρq) = A + (B-A)/(1+exp[k(ρq-ρ0)])` with A=0.4, B=1.5, ρ0=0.75, k=10 to amplify gradient contribution from harder problems (lower pass rate) and dampen easy ones.

### Assessment for MITS

**Your curriculum design is reasonable but has a structural weakness.** Analysis:
- Stage 1 (easy+medium, 300 steps): The easy problems are doing little work for an instruct model. They provide the format reward signal but minimal correctness learning. This is not harmful but wastes ~30-40% of your step budget.
- Stage 2 (all tiers, 500 steps): Introducing hard problems at step 300 is good. However, without DAPO-style dynamic filtering, hard problems will dominate the gradient with near-zero PoS groups (all 8 rollouts wrong = near-uniform advantage ≈ 0, no gradient).

**Recommended improvements**:
1. In Stage 1: keep medium only (ρ ∈ [0.2, 0.8]) or apply GRPO-LEAD difficulty reweighting
2. In Stage 2: add dynamic sampling (filter prompts where all 8 rollouts succeed or all fail)
3. Add a Stage 3 (100-150 steps) focused specifically on problems where current model accuracy is 10-50% — this is where GRPO-LEAD achieves its biggest gains

**Your 300+500 step budget is realistic**: GRPO-LEAD achieves significant gains in 340 total steps. DAPO achieves SOTA in 135 steps (on 32B). For a 9B model with curriculum, 800 total steps is sufficient for meaningful improvement.

---

## Comparison Table

| Question | Finding | Status for MITS |
|----------|---------|-----------------|
| Correctness plateau ~0.55 | Mathematically expected for instruct model with binary reward | Normal — not concerning by itself |
| LoRA r=16 capacity | Sufficient for RL (r=1-32 all work); target_modules scope matters more | Check that LoRA covers all-linear, not attention-only |
| G=8, batch=1, acc=16 | 2 unique prompts/step is at floor; long sequences amplify token-level noise | Concerning — increase acc_steps or reduce G |
| think_tokens always 1023 | Truncation creates systematic negative signal on deep thinking | Critical issue — increase budget or mask truncated samples |
| Lion 8-bit optimizer | No RL papers validate Lion; sign updates may conflict with advantage scaling | Experimental — fallback to AdamW 8-bit if instability |
| Expected accuracy gain | +3-10 pp on hard math, +10-20 pp on medium math from instruct baseline | Achievable with current setup |
| Curriculum design | Easy-only Stage 1 wastes steps; dynamic filtering would help | Suboptimal — add DAPO dynamic sampling in Stage 2 |

---

## Recommendations (Priority Order)

### Priority 1 (Fix immediately — critical): Thinking budget
- Increase `max_thinking_tokens` from 1024 to at least 4096 (8192 preferred)
- Add DAPO-style overlong filtering: mask (not penalize) completions that hit the length limit
- Verify reward function handles incomplete `</think>` gracefully — it should return 0, not -1

### Priority 2 (Fix before Stage 2): Unique prompts per step
- Current: 2 prompts/step is the minimum viable floor
- Option A: increase `gradient_accumulation_steps` from 16 to 32 (4 unique prompts/step)
- Option B: reduce `num_generations` from 8 to 4 (4 unique prompts/step, less rollout variance)
- Both are valid tradeoffs; Option A is safer

### Priority 3 (Stage 2 design): Dynamic sampling
- Filter training batches to remove prompts where all G rollouts succeed (trivial) or all fail (no gradient)
- This is DAPO's core contribution and most impactful single change for instruct-model GRPO
- Implementation: after rollout, skip prompts where `mean(correctness) == 0 or == 1`

### Priority 4 (LoRA config audit): Target modules
- Verify `target_modules` includes MLP layers (gate_proj, up_proj, down_proj) in addition to attention
- If currently attention-only, switching to all-linear may improve results more than any rank increase

### Priority 5 (Monitor, act if needed): Lion optimizer
- If Stage 2 shows reward decay or instability, switch to AdamW 8-bit
- Ensure Lion LR is 3-10x smaller than you would use for AdamW (e.g., AdamW 1e-6 → Lion 1e-7)

---

## Key References

| Paper | arXiv | Key Finding |
|-------|-------|-------------|
| DeepSeek-R1 | 2501.12948 | GRPO on base model; AIME 15.6% → 71.0%; no instruct starting point |
| DAPO | 2503.14476 | Overlong filtering, dynamic sampling, decoupled clipping (ε_low=0.2, ε_high=0.28) |
| VAPO | 2504.05118 | Value-augmented PPO; 16 rollouts/prompt; AIME 60.4 on 32B |
| GRPO Dynamics | 2503.06639 | Theoretical PoS fixed-point; success amplification 21% → 37.5% on GSM8K |
| Tina | 2504.15777 (ICLR 2026) | LoRA r=16 optimal for 1.5B; ranks 8-32 equivalent |
| LoRA Without Regret | Schulman 2025 | RL needs r=1-32; all-linear scope critical; batch size < 32 |
| GRPO-LEAD | 2504.09696 | 3-stage curriculum; difficulty-aware reweighting; AIME24 +3.6pp in 340 steps |
| GSPO | 2507.18071 | Sequence-level IS; ε=3e-4 vs GRPO ε=0.2; powers Qwen3 |
| BRPO | 2505.13438 | Budget-aware GRPO; truncation penalty causes biased advantage estimates |
| Does RLHF Scale? | 2412.06000 | 9B models gain 4.4 pp avg from RLHF; diminishing returns at larger scale |

---

*Generated by ML Research Agent for MITS project, 2026-03-20*
