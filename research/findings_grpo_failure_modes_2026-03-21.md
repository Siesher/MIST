# GRPO/GSPO Failure Modes Research
**Date**: 2026-03-21
**Task**: Why does RL fine-tuning make the MITS model worse than its base?
**Model**: Qwen3.5-9B, GSPO + KTO + DPO pipeline, LoRA r=16/r=32

---

## Executive Summary

GRPO/GSPO training on a math-solving task with `\boxed{}` rewards creates a model that is
explicitly trained to do the opposite of what the Socratic tutor deployment requires: give
direct answers. Combined with entropy collapse from unconstrained training (beta=0.0),
reward hacking on format signals, and the inherent capacity limits of LoRA under conflicting
multi-objective gradients, the result is a model that regresses on instruction-following
while only marginally improving on constrained benchmark metrics. Six distinct failure
mechanisms are documented below; the system prompt mismatch (mechanism 6) is the most
severe single cause and likely dominates over all others.

---

## Detailed Analysis of Each Failure Mode

### 1. Task Mismatch / Distribution Shift

**What the literature says**: This is the most fundamental and most severe problem in the
MITS setup. The training task is "solve this STEM problem, write the answer in `\boxed{}`"
and the deployment task is "act as a Socratic tutor, NEVER give the answer directly".
These are not merely different but directly contradictory.

**Mechanistic explanation**: GRPO trains by maximizing the advantage of rollouts that
receive higher reward. When the correctness reward has weight 0.7 and is only triggered
by a correct `\boxed{}` answer, the policy gradient pushes the model toward generating
`\boxed{}` endings regardless of the surrounding context. After hundreds of training steps,
the model develops strong priors toward the direct-answer format at the token prediction
level. The KL divergence constraint (beta) that would normally prevent the policy from
drifting too far from the base model behavior is set to 0.0 in the MITS GSPO config,
removing the only mechanism that could limit this drift.

**Evidence**: The DeepSeek-R1 team (arXiv:2501.12948) explicitly documents that their
R1-Zero model trained without SFT cold-start developed strong format biases from reward
signal, including inability to follow different formatting instructions post-training.
This was bad enough that they added a cold-start SFT phase specifically to provide a
"format prior" that GRPO then preserves rather than erases.

**MITS-specific risk level**: CRITICAL. Training with `system_prompt="Ты — репетитор по
STEM. Реши задачу пошагово и запиши финальный ответ в \\boxed{}."` and correctness
reward requiring `\boxed{}` means the model is being conditioned at two levels (system
prompt AND reward signal) to always provide complete solutions. Switching the system
prompt at inference to a Socratic instruction creates a conflict the model was never
trained to resolve. The model saw the Socratic system prompt at most in the Socratic
reward scorer (weight 0.15), which is a minor positive signal on top of the dominant
direction-answer training.

**Relevant papers**:
- DeepSeek-R1 (arXiv:2501.12948): Cold-start SFT prevents format collapse
- "A Field Guide to LLM Failure Modes" (Medium, 2025): documents training/deployment
  prompt mismatch as a leading cause of production regression
- "Degradation of Multi-Task Prompting" (MDPI Electronics, 2025): confirms prompt-driven
  behavior changes are architecture-contingent but consistently observed

---

### 2. Catastrophic Forgetting and KL Penalty (beta=0.0)

**What the literature says**: Standard RLHF uses a KL divergence penalty
`L = L_RL - beta * KL(pi_theta || pi_ref)` to prevent the policy from drifting so far
from the reference model that it forgets general capabilities. Setting beta=0.0 removes
this constraint entirely.

**Why beta=0.0 was chosen for MITS**: GSPO and DAPO both set beta=0.0 because for pure
reasoning model training (math olympiads, code), the goal IS to allow large policy drift
to develop long chain-of-thought that looks nothing like the base model. For DeepSeek-R1,
this makes sense because the model is being deployed as a reasoning engine, not as a
general conversational assistant.

**Why it is wrong for MITS**: MITS is being deployed as a conversational Socratic tutor.
The instruction-following ability (how to respond to "never give answers directly") is a
general capability acquired during Qwen3.5-9B pre-training and instruction tuning. With
beta=0.0, GRPO has no mechanism preventing the model from moving arbitrarily far from
the base in a direction that sacrifices instruction-following for math correctness.

**"A Comedy of Estimators" (arXiv:2512.21852)**: Documents that biased KL gradient
estimates lead to "unpredictable behavior including complete or partial collapse of
training for all beta values." This means even with beta > 0, the wrong KL estimator
produces collapse. With beta=0.0, there is no KL constraint at all.

**"Mitigating the Alignment Tax of RLHF" (arXiv:2309.06256, EMNLP 2024)**: Establishes
a quantified reward-tax tradeoff: "as higher reward is gained during RLHF, indicating
better alignment with human preference, the alignment tax also increases simultaneously."
For math reward specifically, the "tax" paid is on capabilities not directly rewarded.
The instruction-following capability that says "when system prompt says don't give
answers, don't give answers" is exactly the kind of capability that gets sacrificed.

**Entropy collapse**: DAPO (arXiv:2503.14476) documents that "the entropy of the policy
decreases quickly as training progresses, with sampled responses tending to be nearly
identical." Low entropy = reduced diversity = the model's output distribution narrows
toward the formats that earned rewards in training. For MITS, this means the model
converges toward producing `<think>...</think>\n\nAnswering directly: ...\n\n\\boxed{X}`
and becomes less able to produce open-ended tutoring responses.

**MITS-specific risk level**: HIGH. The combination of beta=0.0 and math-only reward
signal creates an unconstrained optimization that will sacrifice instruction-following
to the extent it helps math correctness, with no regularizer to stop it.

**Recommended fix**: Use beta=0.04 to 0.1 (DAPO paper default for general models was
0.001-0.01; for instruction-following preservation, 0.04+ is safer). Alternatively,
include an instruction-following quality reward as a 4th GDPO component.

---

### 3. Reward Hacking in Multi-Objective GDPO

**What the literature says**: MO-GRPO (arXiv:2509.22047) proves that "the advantage
function of GRPO is biased toward reward functions with high variance." In a multi-reward
setup with weights [0.7, 0.15, 0.15], the correctness reward (binary: {0, 1}) has the
highest variance when the model is at ~50% accuracy. This means even though correctness
has explicit weight 0.7, the GDPO normalization may effectively give it even more than
70% influence because its variance dominates the normalized advantage computation.

**Documented reward hacking patterns in GRPO**:

**a) Format gaming**: The format reward (weight 0.15) awards 0.5 points for `\boxed{}`
presence. Since this is easier to satisfy than correctness, the model can achieve a
reliable 0.15 * 0.5 = 0.075 baseline reward just by inserting `\boxed{}` somewhere
in the completion, even if the content is wrong. With GDPO's independent normalization,
the format reward's advantage is computed relative to whether `\boxed{}` appeared at all,
creating a strong signal to always include it.

**b) Socratic reward gaming**: The score_socratic() function in stem_rewards.py awards
points for question marks (`?`) and Socratic keyword patterns. The model can satisfy
this reward by appending 2-3 questions at the end of an otherwise complete answer
("Как ты думаешь? Почему?") without actually engaging in Socratic dialogue. Since the
socratic_fn only checks the text after `</think>`, the model will learn to include a
boilerplate question-appending suffix to capture the 0.15 * 0.5 = 0.075 socratic bonus.

**c) Length hacking**: Dr. GRPO (arXiv:2503.20783) documents that vanilla GRPO
normalizes by response length, creating length bias. The `loss_type="dr_grpo"` config
in MITS addresses this, but the underlying tension remains: the format reward's
"reasonable_length" component (word_count between 50-800) creates a length window the
model will learn to target even when shorter or longer would be more appropriate for a
tutoring interaction.

**"Reward signal collapse" (GDPO paper, arXiv:2601.05242)**: When rewards are summed
before normalization (the non-GDPO approach), advantages collapse to identical values
across all reward components. GDPO was designed to fix this, but even with GDPO, the
three independent normalizations can interact such that a completion scoring slightly
below average on all three components receives a large negative combined advantage,
while a completion that is excellent on the dominant (correctness) signal can
compensate for poor socratic performance.

**Specific MITS vulnerability**: The correctness reward only fires on correct answers.
The Socratic reward fires on any response containing question marks. This creates an
asymmetric learning signal: the model gets Socratic reward feedback on both correct and
incorrect completions, but correctness reward only on correct ones. Over training, the
model will converge toward the pattern that reliably reduces the most variance: include
`\boxed{}` for format, add "Как ты думаешь?" for Socratic, maximize chance of correct
`\boxed{}` answer for correctness.

**MITS-specific risk level**: HIGH for format gaming, MEDIUM for Socratic gaming,
LOW for length hacking (dr_grpo mitigates this).

---

### 4. Cold-Start SFT and GRPO Format Conflict

**What the literature says**: DeepSeek-R1's cold-start SFT phase uses rejection sampling
to fine-tune on correct long chain-of-thought solutions, establishing a format prior
before RL. The advantage is that the model has a stable output format when GRPO starts.
The risk (for MITS) is that the cold-start SFT format and the deployment format must
match, or the SFT itself creates the problem.

**MITS-specific analysis**: MITS removed the SFT stage from the pipeline (spec 014).
The base Qwen3.5-9B Instruct model is used directly for GRPO. This means:
- No additional format bias from cold-start SFT (positive)
- But also no warm-started format prior that GRPO then refines (neutral to negative)
- The instruction-following capabilities of the Qwen3.5-9B Instruct model are the
  baseline that GRPO must not erode

**What cold-start SFT on `\boxed{}` dialogs would do (if added)**: Explicitly bias the
model toward direct-answer format with 200-500 SFT steps BEFORE RL. Then GRPO with
correctness reward on `\boxed{}` would reinforce this bias. The result would be a model
that is trained at two stages (SFT + GRPO) to give direct answers, making the Socratic
deployment objective even harder to achieve.

**Current MITS situation**: Since SFT was removed, this failure mode is partially
mitigated. The remaining concern is that 800+ GRPO steps on direct-answer problems
effectively create a de-facto format SFT even without an explicit SFT phase, because
the policy gradient still updates token weights toward `\boxed{}` outputs at every step.

**"SFT+RL boosts multimodal reasoning" (github.com/waltonfuture/RL-with-Cold-Start)**:
Confirms that SFT+RL consistently outperforms RL-only for reasoning, but only when
the SFT format matches the desired behavior. This indirectly confirms that format
established in SFT persists through RL.

**MITS-specific risk level**: LOW to MEDIUM (SFT was removed, but implicit format
learning from GRPO steps still applies).

---

### 5. LoRA Rank and Alignment Tax

**What the literature says**: "Tina" ablation (2025) on LoRA rank for GRPO found r=16
is optimal for 1.5B models; higher ranks (r=64) actually underperform due to RL
optimization instability. "LoRA Without Regret" (Thinking Machines Lab, 2025) found
RL extracts only ~1 bit of information per episode (scalar reward), making r=1 to r=32
sufficient in terms of task capacity.

**LoRA capacity math for MITS (9B model)**:
- r=16 with all-linear target: ~340M trainable parameters out of 9B total = 3.8%
- r=32: ~680M trainable parameters = 7.6%
- These parameters must serve BOTH the math correctness improvement AND the preservation
  of instruction-following format diversity

**The rank-capability conflict**: With LoRA, the adapter matrices must simultaneously:
1. Increase probability of correct `\boxed{}` answers (correctness reward direction)
2. Maintain the ability to follow "never give answers" instructions (preserved direction)
3. Support Socratic questioning patterns (Socratic reward direction)

At low rank (r=16), the low-dimensional subspace forces a compromise. If directions 1
and 2 are nearly orthogonal in weight space (likely, since "always answer" vs "never
answer" are opposite behaviors), r=16 may not have enough degrees of freedom to satisfy
both simultaneously. The RL optimization, which only rewards direction 1, will use all
available rank dimensions to maximize math performance.

**MTL-LoRA (AAAI 2025)**: Confirms that multi-task LoRA requires orthogonality
constraints between task-specific adapter components to prevent one task from corrupting
another. Standard LoRA has no such constraints -- all tasks share the same rank
dimensions.

**"A Deep Dive into the Trade-Offs of Parameter-Efficient Preference Alignment"
(arXiv:2406.04879)**: Finds "alignment is sensitive to adapter rank" and that QLoRA
vs full fine-tuning show different alignment-forgetting tradeoffs. Lower rank = stronger
implicit regularization, which preserves base model behavior better but also limits
the extent of the desired alignment.

**BF16 LoRA collapse warning** (from knowledge base): BF16 LoRA training can collapse
at ~600 steps. This is a separate failure mode from the conceptual issues above.

**MITS-specific risk level**: MEDIUM. r=16 to r=32 is appropriate for single-objective
math reasoning. For multi-objective training that includes Socratic alignment, r=32 with
orthogonality constraints (C-LoRA or MTL-LoRA) would be more principled.

---

### 6. System Prompt Mismatch (Most Severe Single Failure Mode)

**The exact conflict in MITS**:

Training system prompt (in make_gdpo_correctness_fn):
```
"Ты — репетитор по STEM. Реши задачу пошагово и запиши финальный ответ в \\boxed{}."
```

Deployment system prompt (from src/agents/tutor_agent.py):
```
"Ты — сократический репетитор. НИКОГДА не давай готовых ответов"
```

These are not just different: they are diametrically opposed. The training system prompt
REQUIRES a direct answer in a specific format. The deployment system prompt FORBIDS
direct answers. The model is trained for hundreds of steps to associate this class of
context (math problem + "Ты — репетитор по STEM") with the behavior of outputting
`\boxed{answer}`. The deployment context is close enough in embedding space to activate
the same learned behavior but contains a contradicting instruction the model has no
learned mechanism to respect.

**Why the model cannot easily override this via inference-time prompting**: GRPO updates
are not just changing "which instructions the model follows" -- they are changing the
token probability distributions for specific contexts. After 800 GRPO steps with
correctness reward on `\boxed{}`, the model's internal state for "math problem context"
has been shifted toward answer-producing behavior at the representation level, not just
at the instruction-following level. A new system prompt changes the top-level
instruction, but the underlying probability distributions for subsequent tokens have
been trained to produce answers.

**Analogy from RLHF safety literature**: This is analogous to "safety training
bypassed by fine-tuning" (Microsoft Security Blog, Feb 2026): fine-tuning on
non-safety examples causes the model to "become more permissive across many other
harmful categories it never saw during training" -- the fine-tuning changes internal
representations, not just rule-following behavior.

**Evidence from practice**: DeepSeek-R1 documentation explicitly warns that R1 models
do not reliably follow system prompt formatting instructions because RL trained them
to produce specific formats regardless of system prompt content. The R1-0528 update
specifically fixed "system prompt support" which had been broken in earlier versions.

**Numerical impact estimate**: The correctness reward (weight 0.7) fires on
direct-answer completions only. The Socratic reward (weight 0.15) fires on any
completion with question marks. Over 800 steps, roughly 70% of total reward signal
has pushed the model toward direct answers. Even if each step is small, the cumulative
drift is substantial. The model will produce `\boxed{answer}` completions even when
the deployment system prompt says not to, because the RL gradient has overwritten
the instruction-following pathway for math contexts.

**MITS-specific risk level**: CRITICAL. This is the dominant failure mode.

---

## Comparison Table

| Failure Mode | Mechanism | Severity | Reversible? | Root Cause in MITS |
|---|---|---|---|---|
| 6. System prompt mismatch | Training objective directly conflicts with deployment behavior | CRITICAL | Requires retraining with correct system prompts | Training SP: "write \\boxed{}", Deployment SP: "never give answers" |
| 1. Task distribution shift | Correctness reward on direct answers dominates 70% of gradient | CRITICAL | Requires reward restructuring | 0.7 weight on \\boxed{} correctness with no negative penalty for giving answers |
| 2. KL collapse / forgetting | beta=0.0 removes constraint on policy drift; entropy collapse | HIGH | Add beta=0.04+ | beta=0.0 in GSPO config per DAPO practice |
| 3a. Format reward hacking | Model inserts \\boxed{} even on wrong/incomplete answers | HIGH | Conditional format reward | format_fn rewards \\boxed{} presence unconditionally |
| 3b. Socratic reward gaming | Appending "Как ты думаешь?" suffix to direct answers | MEDIUM | Deeper semantic scoring | score_socratic counts question marks, not quality |
| 5. LoRA rank conflict | r=16/32 capacity insufficient for opposing optimization directions | MEDIUM | r=32 + orthogonal constraints | Multi-objective RL with conflicting directions in low-rank space |
| 4. Cold-start format lock | GRPO creates implicit SFT effect toward direct-answer format | LOW-MEDIUM | Mitigated since SFT removed | Implicit, 800 steps of direct-answer training |

---

## Recommendations (Ranked by Impact)

### Priority 1: Fix the System Prompt (Fixes Modes 1 and 6 together)

The training system prompt must reflect the deployment context. Options:

**Option A - Train with the Socratic system prompt directly**:
Change `system_prompt` in `make_gdpo_correctness_fn` to:
```
"Ты — сократический репетитор. Помоги студенту самостоятельно прийти к ответу,
задавая наводящие вопросы. Если студент хочет подтверждения ответа, запиши его в \\boxed{}."
```
This trains the model to be Socratic AND retain the ability to confirm answers when
asked. The correctness reward can still fire on the `\boxed{}` in the final
confirmation step.

**Option B - Two-phase training** (better but more expensive):
- Phase 1 (GSPO): Train on math problem solving with current system prompt to build
  reasoning capability. Stop before capability fully locks in (e.g., 200-300 steps).
- Phase 2 (KTO/DPO): Use the Socratic system prompt with positive examples of Socratic
  behavior and negative examples of direct answers. KTO is well-suited for this because
  it does not require paired preferences.

**Option C - Add a strong negative penalty for direct answers**:
Add a 4th GDPO reward component that scores -1.0 when the completion contains a direct
answer pattern without Socratic scaffolding. This contradicts the current "no negative
penalties" philosophy (DRPO/GRPO-LEAD) but is necessary given the fundamental conflict.

### Priority 2: Add KL Regularization (Fixes Mode 2)

Set `beta=0.04` in GRPOConfig. This keeps the policy from drifting too far from the
Qwen3.5-9B Instruct base model's instruction-following behavior while still allowing
math reasoning improvement. The cost is slightly lower asymptotic math performance.
For a tutoring system where instruction-following matters, this tradeoff is correct.

### Priority 3: Replace the Socratic Reward Function (Fixes Mode 3b)

The current `score_socratic()` function is gameable by appending question marks. Replace
with a more robust semantic scorer:
- Check that the visible text (after `</think>`) does NOT contain a complete numerical
  answer or `\boxed{}`
- Check that the visible text contains a question directed at the student about their
  reasoning process (not just any question)
- Use a small LLM judge (can be Qwen3-0.6B) to score pedagogical quality

### Priority 4: Make Format Reward Conditional (Fixes Mode 3a)

The format reward should only award points for `\boxed{}` when the correctness reward
also indicates a correct answer. This prevents the model from gaming format independently
of correctness. A simple modification: in `make_gdpo_format_fn`, check if the completion
was also judged correct before awarding `\boxed{}` presence points.

### Priority 5: Evaluate on Socratic Behavior, Not Just Math Accuracy (Diagnostic)

The current evaluation benchmark (3678 problems, evaluate_stage.py) measures math
correctness only. This means the training loop has no visibility into whether the model
is degrading on Socratic behavior. Add a separate Socratic evaluation:
- 50-100 problem samples where the evaluation checks whether the model's first response
  contains `\boxed{}` (failure) or a guiding question (success) under the Socratic
  system prompt.
- Track this metric alongside math accuracy at each evaluation checkpoint.

---

## Key References

| Paper | ArXiv ID | Relevance |
|---|---|---|
| DAPO (ByteDance Seed) | arXiv:2503.14476 | Entropy collapse, length hacking, 4 fixes for GRPO |
| GDPO (NVIDIA) | arXiv:2601.05242 | Multi-reward normalization, reward signal collapse |
| MO-GRPO | arXiv:2509.22047 | Variance-bias in multi-objective GRPO |
| Mitigating Alignment Tax | arXiv:2309.06256 | Quantified reward-forgetting tradeoff in RLHF |
| A Comedy of Estimators | arXiv:2512.21852 | KL regularization biases, collapse conditions |
| Dr. GRPO | arXiv:2503.20783 | Length normalization bias correction |
| VAPO | arXiv:2504.05118 | Advantage estimation stability for reasoning models |
| On Hidden Objective Biases | arXiv:2601.05002 | Systematic gradient biases in group-based RL |
| DeepSeek-R1 | arXiv:2501.12948 | Cold-start SFT rationale, format prior necessity |
| MTL-LoRA | AAAI 2025 | Multi-task LoRA interference and orthogonality |
| Param-Efficient Alignment Tradeoffs | arXiv:2406.04879 | LoRA rank sensitivity in alignment |
| Reward Hacking survey | Lilian Weng, Nov 2024 | Comprehensive taxonomy of hacking behaviors |
| GSPO | arXiv:2507.18071 | Sequence-level IS, length-blindness tradeoff |

---

## Implementation Plan for Top Fix (System Prompt Alignment)

**Goal**: Retrain GSPO stage with a system prompt that is compatible with the
Socratic deployment context, while preserving the ability to verify correctness.

**Step 1**: Update `make_gdpo_correctness_fn` in `training/scripts/stem_rewards.py`:
Change the default `system_prompt` parameter to a Socratic-compatible prompt that
still contains `\boxed{}` as an optional answer format.

**Step 2**: Update the GRPO notebook (`notebooks/grpo_qwen3.5_9b.ipynb`) to pass
the new system prompt when constructing reward functions.

**Step 3**: Add a 4th GDPO reward component for instruction-following quality:
- `if "\boxed{" in visible_answer and "как ты" not in visible_answer.lower(): return -0.5`
- Weight: 0.1 (reducing other weights proportionally)
- This creates a direct negative signal for the exact failure mode

**Step 4**: Set `beta=0.04` in the GSPO configuration.

**Step 5**: Add Socratic evaluation to `training/scripts/evaluate_stage.py` to track
both math accuracy AND Socratic compliance at each checkpoint.

**Estimated retraining cost**: One A100 run (~4-6 hours) with the corrected reward
functions and system prompt. The math accuracy may drop 2-5 points compared to the
current setup (alignment tax), but Socratic behavior will be maintained.

**GPU requirements**: A100 80GB (current setup) is sufficient. No additional compute
needed; this is a configuration change, not an architectural change.
