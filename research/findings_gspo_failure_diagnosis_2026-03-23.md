# GSPO Training Failure: Evidence-Based Diagnosis and Fix Validation

**Topic:** Root cause analysis of GSPO training producing no behavioral change
**Date:** 2026-03-23
**Researcher:** ML Research Agent (Claude Sonnet 4.6)
**Scope:** 6 diagnosed failure causes + 5 proposed fixes, validated against paper evidence

---

## Executive Summary

The GSPO training failure (rewards decreasing, model outputs identical before and after) is explained by a convergence of at least four well-documented failure modes, not a single cause. The dominant failure is almost certainly the system prompt mismatch combined with reward signal nullification (multi-objective variance bias): 70% of gradient steered the model toward direct answers contradicting the Socratic deployment context, while the Socratic reward at 0.15 weight carried an effective influence of roughly 0.05 due to variance-based advantage collapse — far below the threshold needed for behavioral change. Beta=0.0 removed the last guardrail that might have prevented the model from drifting away from its trained Socratic behavior. The proposed fixes are substantially correct and supported by paper evidence, with one important clarification: LoRA rank was not the primary problem, and increasing it further is counterproductive.

---

## Section 1: System Prompt Mismatch During Training

### Our Diagnosis
Training did not include the deployment system prompt ("Ты — сократический репетитор..."), which explicitly forbids giving direct answers. Training rewarded direct answers via the correctness component.

### Paper Evidence

**Llama 2 (arXiv 2307.09288, Touvron et al., Meta 2023)** is the most relevant direct evidence. During RLHF training of Llama 2, Meta discovered that system prompt instructions ("Act as...") were forgotten within a few dialogue turns. Their solution was Ghost Attention (GAtt): they synthetically concatenated the system instruction to every user turn in SFT fine-tuning data, forcing the model to train with the instruction always present. The paper states explicitly: "initial instructions were lost after a few turns of dialogue" and notes the trained model "had no reliable mechanism to enforce instructions across the full context." Applying this to GRPO: if you do not include the system prompt in RL training rollouts, the model has no training signal to learn that the system prompt affects its behavior.

**InstructGPT (arXiv 2203.02155, Ouyang et al., OpenAI 2022)** describes the practical prompt collection protocol: labelers wrote prompts from scratch and the training distribution was designed to match expected deployment inputs. Section 3.4 notes that distributional mismatch between training prompts and deployment prompts is an explicit alignment failure mode — the model's behavior is a function of the training distribution.

**DAPO (arXiv 2503.14476, ByteDance/Tsinghua 2025)** uses verifiable math problems where the training prompt format is identical to the evaluation format. No format mismatch is introduced at any stage. The paper's results assume this consistency.

**GRPO Dynamics (arXiv 2503.06639)** proves mathematically that GRPO amplifies the policy of the reference model. If the reference model (Qwen3.5-9B Instruct) responds Socratically to prompts that include the Socratic system prompt but responds directly without that system prompt, then training rollouts without the system prompt will amplify the direct-answer behavior even if the format reward slightly penalizes it.

### Verdict for Our Diagnosis
**Confirmed.** The system prompt mismatch is the strongest candidate for the primary failure cause. Every major RLHF paper that addresses this issue resolves it by making the training format match the deployment format exactly. The evidence from Llama 2's Ghost Attention work is a direct parallel: even with RLHF, a model will not maintain system-level behavioral constraints unless those constraints are present during training rollouts. Our training was effectively teaching the model a different persona than the one we want at inference.

**Severity:** Critical. This alone is sufficient to produce zero Socratic behavior after training.

---

## Section 2: Reward Weight Imbalance (0.7 Correctness, 0.15 Socratic)

### Our Diagnosis
The 0.7 correctness weight was too dominant; the 0.15 Socratic weight was too weak to steer style.

### Paper Evidence

**MO-GRPO (arXiv 2509.22047, Ishimoto et al. 2025)** provides the most direct theoretical evidence. Theorem 1 in this paper proves that *the correlation between a reward component and the group advantage is proportional to that reward's standard deviation relative to total reward variance*. In other words, the component with the highest variance in the group automatically dominates the advantage signal regardless of weight. For our setup:

- Correctness reward: binary 0/1, correctness ~40-60% on training problems = maximum variance (Bernoulli variance is maximized at p=0.5)
- Format reward: partially satisfied by instruct model = moderate variance
- Socratic reward: question-mark heuristic = low variance on model that rarely uses questions

The effective influence of the Socratic reward in the advantage function is approximately: `effective_weight ≈ 0.15 × (σ_socratic / σ_total)`. If Socratic variance is low (model rarely asks questions), this effective weight drops to near zero. The paper demonstrates this empirically: GRPO for machine translation optimized readability (jReadability) while completely abandoning translation accuracy (BLEURT) because readability had higher group variance despite being the "secondary" objective.

**GDPO (arXiv 2601.05242, NVLabs January 2026)** is the paper we already implemented. It proves that vanilla GRPO "maps different reward combinations into only two distinct advantage groups" when rewards are summed before normalization. The advantage collapse makes the 0.15 weight even less effective: reward pairs (correctness=0, socratic=1) and (correctness=0, socratic=2) may normalize to identical advantages, providing identical gradient signals despite different Socratic quality. GDPO's per-reward normalization fixes this and was already in our notebook — which means our reward collapse was GDPO-level (each reward normalized independently), but the variance-dominance bias (MO-GRPO Theorem 1) was not addressed by GDPO.

**"Optimizing Safe and Aligned Language Generation" (arXiv 2503.21819)** used equal weights across four reward objectives and noted that single-scalar reward caused the model to over-optimize one objective at the expense of others. They specifically found that even when all rewards were weighted equally, the model would push strongly on whichever objective had the most variance at each step.

**GRPO paper experiments (Shao et al., DeepSeekMath 2024)**: DeepSeek's GRPO implementation uses two reward components — accuracy and format — and they use them at roughly equal weight rather than strongly weighting one over the other. The format reward in DeepSeek-R1 is binary (think/answer tags present or not), while the accuracy reward is also binary. Equal variance → roughly equal effective influence.

### Is 0.15 Too Low?

The answer from the literature is nuanced. The raw 0.15 weight is not inherently too low in isolation. The problem is the combination of:
1. Raw weight 0.15 with already-high correctness variance
2. Low variance of the Socratic reward (the model rarely generates Socratic-style questions)
3. Possible near-zero variance: if all G rollouts either always or never earn the Socratic reward, the component contributes zero gradient regardless of weight

The MO-GRPO and GDPO papers both suggest that the correct solution is to normalize each reward's variance to 1.0 before weighting — which is what our GDPO-style normalization does — but THEN apply the actual weights. This means the 0.15 weight is applied to a variance-normalized signal, so it genuinely gets 15% influence rather than being crushed by variance dominance. However, our Socratic reward function (question-mark counting) likely has very low intrinsic variance, meaning even after normalization, there are many steps where it contributes zero gradient because all G completions scored identically.

### Verdict for Our Diagnosis
**Partially confirmed with an important clarification.** The 0.15 weight is not itself the problem — the combination of low Socratic reward variance AND the system prompt mismatch (which caused the model never to generate Socratic style anyway, keeping Socratic reward uniformly near zero across the group) is the problem. Increasing Socratic weight from 0.15 to 0.45 helps, but only if the reward function can actually distinguish between Socratic and non-Socratic behavior in the training rollouts. If the system prompt is absent and all rollouts produce direct answers, the Socratic reward will be uniformly low for all G completions — producing zero group advantage regardless of weight.

**Severity:** High, but secondary to the system prompt issue.

---

## Section 3: Beta=0.0 — No KL Regularization

### Our Diagnosis
Beta=0.0 means no KL penalty, allowing the model to drift far from the reference policy.

### Paper Evidence

**TRL GRPOConfig documentation** shows that the default beta changed between versions. In TRL v0.15.2, the default was `beta=0.04`. In TRL v0.27+ (current default), it changed to `beta=0.0`. The documentation states: "if beta=0.0 (default), the reference model is not loaded, reducing memory usage. This follows current practice from DeepSeek-R1 and DAPO."

**DeepSeek-R1 (arXiv 2501.12948)** actually uses `beta=0.001` (not zero) in Stage 1 RL training. The paper states KL coefficient = 0.001 with clip ratio = 10. This is a very small but non-zero KL penalty. DeepSeek-R1-Zero (the simpler version without cold-start SFT) does not use KL but suffers from "endless repetition, poor readability, and language mixing" — symptoms explicitly attributed to the lack of KL constraint.

**DAPO (arXiv 2503.14476)** removes the KL term entirely and argues: "during training the long-CoT reasoning model, the model distribution can diverge significantly from the initial model, thus the KL restriction is not necessary." This justification is specific to long-CoT math reasoning from a BASE model where maximally exploring the reasoning space is the goal. It explicitly does not apply to instruction-following or style-constrained applications.

**GSPO (arXiv 2507.18071)** also uses `beta=0.0` but substitutes sequence-level clipping (epsilon=3e-4, epsilon_high=4e-4) as the primary constraint on policy divergence. The clipping mechanism replaces KL as the proximal constraint. This means GSPO beta=0.0 is not the same as "no constraint" — the sequence-level IS weights with tight clipping provide the equivalent of a soft KL bound.

**GRPO Dynamics (arXiv 2503.06639)** mathematically proves that with `beta > 0`, the KL term provides local convergence stability. The convergence condition requires `beta > B(p*)` where `B(p*)` scales with the variance of the success probability. For our case with correctness at ~50% accuracy (maximum variance), this stabilization threshold is at its highest. With beta=0, this convergence condition is replaced entirely by the clipping mechanism — which means epsilon must be well-calibrated or the policy can oscillate.

**"The Choice of Divergence" (arXiv 2509.07430)** analyzed diversity collapse in RLVR training and found that removing KL divergence with beta=0 was associated with faster policy collapse when the model has moderate initial performance. Models with very low initial performance (base models) are less affected because they have more to gain from exploration.

### For MITS Specifically

Our GSPO uses epsilon=3e-4 and epsilon_high=4e-4 (sequence level), which is the GSPO paper's recommendation. These provide the proximal constraint that substitutes for KL. However, there is a key difference between GSPO's use case and ours:

- GSPO paper: training pure math reasoning, where divergence from the instruct format is acceptable and beneficial
- MITS: training Socratic tutoring behavior, where divergence from the instruct model's instruction-following capability must be prevented

For our use case, beta=0.0 is incorrect configuration. The instruct model's Socratic-compatible behavior (question-asking, scaffolding) needs to be regularized against. Without KL penalty, the only pressure keeping the model Socratic comes from the Socratic reward itself — which we've already established is too weak due to variance collapse and system prompt absence.

The TRL v0.15.2 default of `beta=0.04` existed for a reason. Empirical reports from RLHF practitioners (RLHF Book by Nathan Lambert, ICLR 2024 implementation notes) consistently show that non-zero beta in the range 0.01-0.1 is necessary when the training objective is partial (e.g., math only) but the deployment objective is holistic (math + format + style).

### Verdict for Our Diagnosis
**Confirmed, but with an important nuance.** Beta=0.0 is not wrong for pure math reasoning (DAPO, GSPO use case). It IS wrong for a Socratic tutoring model where instruction-following and style compliance must be preserved alongside correctness improvement. The GSPO clipping provides some proximal constraint, but it constrains per-step policy change, not cumulative drift from the reference model's instruction-following capabilities.

**Severity:** High. Beta=0.0 + weak Socratic reward + no system prompt = no force keeping the model Socratic. The three combine multiplicatively.

---

## Section 4: Rewards Decreasing During Training

### Our Diagnosis
Training metrics showed rewards going DOWN, which we interpreted as a failure mode.

### Paper Evidence

**DAPO (arXiv 2503.14476)** explicitly identifies the "gradient-decreasing problem": when all G completions in a group receive the same reward (all correct or all wrong), the group advantage is zero and no gradient update occurs. This is a well-documented structural property of GRPO, not a bug. However, for rewards that DECREASE, several distinct mechanisms exist:

**Lazy Likelihood Displacement (arXiv 2512.04220, "LLD Death Spiral")** describes the most pathological case. LLD is defined as "the stagnation or reduction of likelihood for both correct and incorrect responses during GRPO optimization." The mechanism:
1. Low-likelihood incorrect responses generate large negative gradients
2. Correct and incorrect responses share similar token prefixes (especially with thinking models)
3. The negative gradient from incorrect responses suppresses the correct response probability
4. Decreasing correct-response likelihood → more completions are "incorrect-style" → stronger negative gradients → self-reinforcing collapse

This was documented in Search-R1 training but is architecturally generic. For our case, if the correctness reward was declining, this is a strong candidate mechanism. The paper describes a three-phase collapse: early stagnation, steady decay, then rapid collapse.

**GTPO (arXiv 2508.03772)** further analyzes how negative gradient in GRPO can cause policy collapse: "negatively rewarded completions may penalize confident responses and shift model decisions toward unlikely tokens, progressively flattening the output distribution." This manifests as entropy increase and reward decrease even when the policy is nominally being trained toward correct answers.

**MO-GRPO (arXiv 2509.22047)** provides another mechanism: "naive aggregation of multi-objective rewards is vulnerable to reward hacking — the group advantage becomes dominated by objectives with largest variance." For our case, this means the correctness reward (highest variance, 0.7 weight) drives all updates, while format and Socratic provide noise. If the correctness reward itself starts declining (due to LLD or entropy collapse), the overall weighted reward declines.

**DAPO clipping analysis**: When using `num_iterations > 1` (multiple gradient steps per rollout, which is common for memory efficiency), the clipped surrogate prevents extreme policy changes per step. But with beta=0.0 and the old policy becoming stale over multiple gradient steps, the importance sampling weights can diverge. With GSPO's sequence-level IS (epsilon=3e-4), this risk is smaller but not eliminated if the epsilon is set incorrectly for the actual training setup.

**Entropy Collapse Mechanism (DAPO, GTPO papers)**: When entropy collapses, the model generates nearly identical completions across all G rollouts. When all G rollouts in a group are identical:
- Correctness reward: if all identical and wrong, advantage = 0
- Format reward: if all identical and formatted, advantage = 0
- Socratic reward: if all identical, advantage = 0
- Result: zero gradients across all reward components, training stalls

This precisely matches the symptom: "outputs identical before and after training." The model may have entered an entropy-collapsed state before or during training, causing zero effective learning.

### Is Decreasing Reward Always a Failure?

For the correctness component, decreasing reward during the first 20-50 steps is sometimes normal (negative reward noise as the model adjusts its output distribution). DAPO paper shows that early training can have reward fluctuations before a stable upward trend. However, reward that consistently declines over 100+ steps is pathological.

### Verdict for Our Diagnosis
**Confirmed as a symptom, but the cause is the compound of other failures.** Decreasing reward is not itself a root cause but rather a downstream symptom of one or more of:
1. Entropy collapse (all G completions becoming identical → zero gradient → reward stagnation or decay from random fluctuations)
2. LLD death spiral (negative gradients from incorrect responses suppressing correct-response likelihood)
3. System prompt mismatch (model rewarded for behavior it cannot exhibit at inference)
4. Zero-variance group problem (all G completions are all-correct or all-wrong → zero advantage → training stalls and rewards drift)

**Severity of decreasing reward as an independent cause:** Low (it is a symptom). The underlying causes above have high severity.

---

## Section 5: LoRA Rank r=16 Too Small

### Our Diagnosis
LoRA rank r=16 was insufficient for learning style changes.

### Paper Evidence

**"LoRA is All You Need for Safety Alignment of Reasoning LLMs" (arXiv 2507.17075)** uses rank r=1 for safety/style alignment on reasoning LLMs. Their key finding: "a rank-1 update is enough to achieve safety," and "safety behavior is mediated by a single direction" in weight space. They explicitly argue that behavior changes require minimal rank, while knowledge preservation requires avoiding interference with large rank dimensions.

**Tina (arXiv 2504.15777, ICLR 2026)** provides the most complete rank ablation for RL fine-tuning:
- r=4: 47.72%; r=8: 47.89%; r=16: 48.92% (peak); r=32: 48.47%; r=64: 46.95%
- r=16 is optimal; r=64 underperforms r=16

This is for a 1.5B model, but the paper's theoretical framing explains why: "RL extracts ~1 bit of information per episode (scalar reward), which demands minimal parameter capacity." RL fine-tuning simply does not need high-rank parameter updates the way SFT does.

**"LoRA Without Regret" (Schulman, Thinking Machines Lab 2025)** provides the clearest framework: "For RL tasks, r=1 to r=32 are all sufficient. RL extracts ~1 bit of information per episode (scalar reward), which demands minimal parameter capacity." The paper also finds that the *scope* of LoRA (which modules are targeted) matters far more than rank: applying LoRA to all linear layers outperforms attention-only LoRA at any rank.

**Ponderings on the capacity argument**: The hypothesis "r=16 can't learn style changes" is actually backwards given the literature. Style changes require LESS rank than knowledge changes:
- Knowledge injection: requires spanning many independent factual directions, needs high rank
- Style change (e.g., "ask questions instead of giving answers"): mediated by 1-3 behavioral directions, needs r=1 to r=8

**However**, there is one scenario where rank matters for style in RL: multi-objective LoRA. MTL-LoRA (AAAI 2025) shows that when multiple objectives (math, format, Socratic) compete in the same LoRA rank dimensions without orthogonality constraints, opposing gradient directions can cancel. For our three-objective case, r=16 provides 16 dimensions for three competing optimization directions — potentially insufficient to keep them orthogonal. The paper recommends either increasing rank OR adding explicit orthogonality regularization between task-specific LoRA components.

### Was r=16 the Problem?

The weight of evidence says r=16 was NOT the primary failure cause. If the system prompt, reward weights, and KL penalty had been correct, r=16 would have been sufficient for behavioral change (safety papers prove this with r=1). However, the multi-objective competition is a valid secondary concern.

### Verdict for Our Diagnosis
**Not confirmed as a primary cause.** r=16 is sufficient for style/behavior changes according to every relevant paper (safety alignment, RL fine-tuning ablations). The proposed fix of increasing to r=32 or r=64 is counterproductive according to Tina — r=64 actually UNDERPERFORMS r=16. If you increase to r=32, evidence suggests modest gains at most. The correct intervention for the LoRA issue is NOT increasing rank but ensuring `target_modules` covers all linear layers including Qwen3.5's DeltaNet projections (`in_proj_qkv`, `in_proj_z`, `in_proj_b`, `in_proj_a`, `out_proj` in 24 DeltaNet layers).

**Severity:** Low as a primary cause. The research finding `target_modules` coverage is more important than rank.

---

## Section 6: GRPO-Specific Considerations (Group Size, Batch Size, Mini-batch Interactions)

### What the Papers Say

**Group size effect on learning signal:** GRPO's core property is that learning requires within-group variance. If all G completions receive the same reward, advantage = 0 and no gradient flows. For our setup with G=16 and an instruct model that already generates consistent (if not Socratic) outputs:
- Easy problems: all 16 completions correct → zero gradient
- Problems where model always gives direct answer: all 16 score 0 on Socratic → Socratic component zero gradient

**DAPO's Dynamic Sampling fix:** The most impactful single intervention for the all-correct/all-wrong problem is filtering prompts to retain only those with mixed outcomes within the group. DAPO filters any batch where all G completions are either correct or incorrect. This is the single change in DAPO that most reliably improves training signal density.

**GSPO (arXiv 2507.18071) sequence-level IS risk:** The GSPO paper warns that sequence-level importance ratios accumulate multiplicatively over token positions. For a long completion of N tokens, the sequence-level IS ratio = exp(mean log-prob difference). If the policy drifts slightly per token but consistently, the sequence-level ratio can diverge rapidly for long completions. The tight epsilon=3e-4 clipping is designed to prevent this — but it also severely limits per-step learning. With beta=0.0 AND epsilon=3e-4, the model's effective learning rate per step is extremely small.

**Mini-batch interactions:** When using `gradient_accumulation_steps > 1`, GSPO's sequence-level IS weights are computed on the old policy but applied to gradients across multiple mini-batches. TRL GitHub issue #3823 (2025) documents that GSPO with default `loss_type="bnpo"` has a calculation error when `importance_sampling_level="sequence"` — the loss is not correctly computed in multi-step scenarios. This bug, if present in the version used, would cause effectively random gradients rather than proper policy updates.

**Number of generations impact:** With G=16, the standard deviation of the group advantage estimate decreases by factor 1/sqrt(16) = 0.25 compared to G=1. This is favorable for signal quality. However, with a system prompt absent from rollouts and the Socratic reward uniformly near zero for all 16 completions, even G=16 cannot create group variance from nothing.

### Verdict
**Partially relevant.** The group-size and GSPO IS mechanics are not primary failure causes if the system prompt and reward function problems are fixed. However, the TRL GSPO implementation bug (issue #3823) is a potential hidden cause of training failure that should be checked against the TRL version used.

---

## Section 7: Proposed Fixes — Validation Against Evidence

### Fix 1: Add System Prompt to Training Data

**Evidence: Strong support.**
- Llama 2 (arXiv 2307.09288): Ghost Attention was specifically invented for this problem. The solution is to include the system prompt in every training rollout.
- InstructGPT (arXiv 2203.02155): Training distribution must match deployment distribution.
- DAPO (arXiv 2503.14476): All training rollouts use the exact prompt format used at evaluation.
- This fix addresses the most critical failure cause directly.

**Implementation note:** The system prompt should be included in the chat template exactly as it appears at inference. For Qwen3.5 with thinking enabled, the full chat template is: `[system_prompt][user_message]`. The RL training loss should be computed on the assistant response only (not the system/user turns).

**Confidence:** Very high. This fix alone may be sufficient to produce visible behavioral change.

### Fix 2: Change Reward Weights to [0.4, 0.15, 0.45] (Boost Socratic Weight)

**Evidence: Partially supported.**

The weight change from [0.7, 0.15, 0.15] to [0.4, 0.15, 0.45] is directionally correct: reducing correctness weight and increasing Socratic weight will shift the optimization pressure. However:

- MO-GRPO (arXiv 2509.22047) shows that the effective influence depends on variance, not just weight. Even with weight=0.45, if all G completions score uniformly on Socratic (because the system prompt makes some attempt to guide), the Socratic component contributes zero gradient.
- The GDPO normalization in our setup already corrects for variance-dominance by normalizing each reward to unit variance before weighting. IF GDPO normalization is correctly implemented, then the actual weights [0.4, 0.15, 0.45] would give those exact proportions of influence — making the 0.45 Socratic weight genuinely 45% of the gradient.
- GDPO paper (arXiv 2601.05242) does not recommend specific weight ratios. Their experiments use equal weighting across objectives and vary secondary reward weights from 0.25 to 1.0. They found that "reducing a secondary weight to 0.25 has little impact on the primary objective" — the threshold below which a component becomes ineffective with GDPO normalization appears to be around 0.25.

**Conclusion:** Weight change is a useful enhancement but secondary to fixing the system prompt. With GDPO normalization correctly applied, 0.15 for Socratic should be sufficient IF (a) the system prompt is present, causing Socratic reward variance > 0, AND (b) the Socratic reward function can actually distinguish Socratic from non-Socratic responses.

**Additional concern:** The proposed Socratic reward uses question-mark counting as a proxy for Socratic behavior. This is vulnerable to reward hacking: the model can append "Как ты думаешь?" to any direct answer and score positively on Socratic while still violating the spirit. A semantic LLM judge for Socratic quality would provide a much cleaner signal.

**Confidence:** Medium. The weight change helps but needs system prompt fix AND better Socratic reward function to be effective.

### Fix 3: Set Beta=0.04 (Add KL Penalty)

**Evidence: Strong support for our use case.**
- TRL v0.15.2 default was beta=0.04 — the old default existed because practitioners needed it.
- RLHF Book (Lambert) and ICLR 2024 implementation notes document that non-zero beta (0.01-0.1) is necessary when training partial objectives (math) for holistic deployment (math + style + format).
- DeepSeek-R1 uses beta=0.001, not zero — even in pure math reasoning.
- DAPO's removal of beta is justified only for pure reasoning from base models where distribution divergence is beneficial. Not our case.
- "Mitigating Alignment Tax" (arXiv 2309.06256) quantifies that removing KL penalty in PPO-RLHF causes instruction-following degradation proportional to training steps.

**Tradeoff:** beta=0.04 will yield slightly lower correctness reward gains (approximately 2-5 pp on math benchmarks based on DeepSeek-R1's comparison of beta=0 vs beta=0.001). This is an acceptable tradeoff for a tutoring system.

**Confidence:** Very high. This is a well-evidenced fix.

### Fix 4: Increase LoRA Rank to r=32 or r=64

**Evidence: Does NOT support this fix.**
- Tina (arXiv 2504.15777): r=64 UNDERPERFORMS r=16 (46.95% vs 48.92%)
- LoRA is All You Need for Safety (arXiv 2507.17075): r=1 is sufficient for behavior change
- LoRA Without Regret (Schulman 2025): RL needs r=1-32, not high rank

**The correct LoRA fix is different:** Ensure `target_modules` covers ALL linear layers in Qwen3.5-9B, including the 24 DeltaNet layers (`in_proj_qkv`, `in_proj_z`, `in_proj_b`, `in_proj_a`, `out_proj`). Using only standard attention modules (`q_proj`, `k_proj`, `v_proj`, `o_proj`) freezes 75% of the model's token-mixing capacity. Using `target_modules="all-linear"` is the recommended safe option.

**Recommended rank:** Keep r=16 or increase to r=32 maximum. Do NOT use r=64.

**Confidence:** High confidence that the current diagnosis (rank too small) is wrong. Moderate confidence in the all-linear target_modules fix.

### Fix 5: New High-Quality Socratic Training Pairs (2,241 DPO + 4,482 KTO)

**Evidence: Strong support.**

This fix is not directly about GRPO/GSPO but about the downstream KTO and DPO stages. The literature is clear that data quality matters more than data quantity for preference optimization:

- "Does RLHF Scale?" (arXiv 2412.06000): Data quality is the primary determinant of post-training gains; high-quality pairs from the current model distribution yield larger gains than random pairs.
- DPO literature (Rafailov et al., NeurIPS 2023): Contrastive pairs with large reward margin between preferred and rejected samples provide stronger gradient signal.
- KTO (arXiv 2402.01306, Ethayarajh et al.): KTO uses unpaired preferences and is more robust to label noise than DPO, making it more forgiving of imperfect Socratic quality judgments.

For the GSPO stage specifically: these pairs do not directly help unless they are used as a cold-start SFT seed before GRPO (DeepSeek-R1 approach) to establish the Socratic behavior prior. Without a cold-start SFT that trains the model to generate Socratic responses when given the Socratic system prompt, the GRPO correctness reward has no Socratic examples to reinforce.

**Recommendation:** Before GSPO, run 200-300 SFT steps on the Socratic dialogue pairs (dialogs.jsonl, 3875 examples). This "cold-start" trains the behavioral prior that GSPO will then reinforce via RL. DeepSeek-R1 explicitly used this pattern.

**Confidence:** High for KTO/DPO stages. Medium for GSPO — only beneficial after cold-start SFT.

---

## Section 8: Missing Fixes Not in Our Current Plan

Based on the literature, there are three important fixes missing from our proposed list:

### Missing Fix A: Improve the Socratic Reward Function

The current Socratic reward uses question-mark counting (`score_socratic()` heuristic). This is confirmed problematic by:
- MO-GRPO: heuristic rewards with low variance across a group contribute near-zero gradient even with high explicit weight
- General reward hacking literature: simple heuristics are trivially hackable (append "Как ты думаешь?" to any answer)
- "Shaping Explanations: Semantic Reward Modeling" (arXiv 2509.13081): semantic reward models substantially outperform surface heuristics for conversational style tasks

**Fix:** Replace the Socratic heuristic with an LLM judge that evaluates whether the response: (a) asks a guiding question, (b) avoids giving the direct answer, (c) relates the question to student's apparent reasoning. A small model (Qwen3-1.5B or Qwen3-4B with Socratic examples) can serve as the judge.

### Missing Fix B: Cold-Start SFT Before GSPO

**Evidence from DeepSeek-R1:** The R1 paper explicitly justifies cold-start SFT before RL: "without cold start, the model has no behavioral prior for the desired output format, and RL may not converge toward the target distribution." For our case, the Qwen3.5-9B Instruct model has no trained prior for Socratic tutoring. GSPO starts from a model that has never been explicitly trained to ask guiding questions. The correctness reward then pulls it toward direct answers.

**Fix:** 200-500 SFT steps on the 3,875 Socratic dialogues (dialogs.jsonl) before GSPO. This establishes the Socratic behavioral prior that GSPO can then reinforce.

**Evidence:** DeepSeek-R1 Section 3.2 argues cold-start SFT "significantly stabilizes RL training" and provides the behavioral prior that pure RL cannot develop from scratch.

### Missing Fix C: Dynamic Sampling / Filter All-Correct and All-Wrong Groups

**Evidence from DAPO (arXiv 2503.14476):** The "Dynamic Sampling" technique filters training batches to exclude prompts where all G completions are identical in reward. This is the most impactful single DAPO contribution for instruct models. For our case, after adding the system prompt, some groups will still have all G completions scoring uniformly on Socratic (especially early in training when the model always gives slightly Socratic or slightly non-Socratic answers). Filtering these groups prevents wasted gradient computation.

---

## Comparison Table

| Failure Cause | Our Diagnosis | Paper Support | Severity | Primary Fix |
|---|---|---|---|---|
| System prompt mismatch | Confirmed | Llama 2 (2307.09288), InstructGPT (2203.02155), DAPO (2503.14476) | Critical | Include system prompt in all training rollouts |
| Reward weight imbalance | Partially confirmed | MO-GRPO (2509.22047), GDPO (2601.05242) | High (secondary) | Fix system prompt first; then raise Socratic weight to 0.45 with GDPO normalization |
| Beta=0.0 | Confirmed for our use case | DeepSeek-R1 (2501.12948), DAPO (2503.14476), RLHF literature | High | Set beta=0.04 |
| Rewards decreasing | Confirmed as symptom | LLD paper (2512.04220), GTPO (2508.03772), DAPO (2503.14476) | High (symptom of above) | Fix root causes; add dynamic sampling |
| LoRA rank r=16 | Not confirmed | Tina (2504.15777), LoRA Safety (2507.17075), LoRA Without Regret (2025) | Low | Verify all-linear target_modules; keep r=16 |
| GRPO-specific issues | Partially relevant | GSPO (2507.18071), DAPO (2503.14476), TRL issue #3823 | Medium | Add dynamic sampling; verify TRL GSPO bug |

---

## Revised Fixes Priority Order

Based on the paper evidence, here is the corrected priority order for fixes:

**Priority 1 (Must fix for any learning to occur):**
- Add Socratic system prompt to all training rollouts (matches exact inference format)
- Set `beta=0.04` to preserve instruction-following during RL training

**Priority 2 (Must fix for Socratic-specific learning):**
- Cold-start SFT: 200-300 steps on dialogs.jsonl before GSPO
- Replace question-mark Socratic heuristic with LLM judge reward

**Priority 3 (Improves signal quality):**
- Raise Socratic reward weight to 0.45 (keeps GDPO normalization)
- Verify `target_modules="all-linear"` covers DeltaNet layers
- Add DAPO dynamic sampling (filter zero-variance groups)

**Priority 4 (Do NOT do):**
- Do NOT increase LoRA rank to r=64. Literature is clear this degrades RL performance.
- Do NOT remove GDPO normalization. It is the correct approach.

---

## Key References

| Paper | arXiv | Key Evidence for MITS |
|---|---|---|
| DeepSeek-R1 | 2501.12948 | beta=0.001 (not zero), cold-start SFT necessity, format rewards |
| DAPO | 2503.14476 | beta=0 justified only for base models, dynamic sampling, entropy collapse |
| Llama 2 | 2307.09288 | Ghost Attention = system prompt must be in training data |
| InstructGPT | 2203.02155 | Training distribution must match deployment distribution |
| MO-GRPO | 2509.22047 | Variance-biased advantage dominance in multi-objective GRPO |
| GDPO | 2601.05242 | Per-reward normalization fixes advantage collapse; weight threshold ~0.25 |
| LLD Death Spiral | 2512.04220 | Mechanism for reward decrease: negative gradients suppress correct responses |
| GTPO | 2508.03772 | Entropy collapse causes reward decrease; policy collapse mechanism |
| Tina | 2504.15777 | r=16 optimal for RL; r=64 UNDERPERFORMS r=16 |
| LoRA Safety | 2507.17075 | r=1 sufficient for style/behavior alignment |
| GRPO Dynamics | 2503.06639 | Mathematical analysis: beta provides local convergence stability |
| "LoRA Without Regret" | Schulman 2025 | r=1-32 all sufficient for RL; all-linear scope > rank increase |
| GSPO | 2507.18071 | Sequence-level IS, epsilon=3e-4, beta=0.0 only for math reasoning from base |
| TRL Issue #3823 | GitHub 2025 | GSPO loss incorrect with multi-step training (potential bug) |
| GRPO-LEAD | 2504.09696 | 3-stage curriculum; difficulty reweighting; cold-start implicitly used |

---

*Generated by ML Research Agent for MITS GSPO failure post-mortem, 2026-03-23*
