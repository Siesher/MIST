# ML Research Agent Knowledge Base
**Project**: MITS (Qwen3.5-9B GSPO/GRPO pipeline)
**Last updated**: 2026-03-25

## TRL GRPOConfig: reward_weights

- `reward_weights: list[float] | None = None` introduced in **TRL v0.15.0** (PR #2676)
- Present in all versions from 0.15.0 onward, including 0.24.0
- Validates that len(reward_weights) == len(reward_functions)
- Default None = all weights 1.0

## TRL GRPOConfig: multi_objective_aggregation (GDPO)

- String field, default "sum_then_normalize"
- "normalize_then_sum" = GDPO paper approach (normalize each reward independently, then weighted sum)
- Confirmed present in v0.29.0; NOT in v0.15.2 docs
- Exact introduction version unknown but <= 0.29.0
- May NOT be in TRL 0.27.1 (Unsloth default) -- needs verification

## TRL GRPOConfig: loss_type options (as of v0.27+)

- `grpo` - per-sequence length normalization, biased, NOT recommended
- `dr_grpo` - global constant (max_completion_length), Dr. GRPO paper (arXiv 2503.20783)
- `dapo` - active tokens in global accumulated batch, DAPO default
- `bnpo` - active tokens in local batch
- `cispo` - clips IS weights separately
- `sapo` - soft temperature-controlled gating (Qwen SAPO paper)
- **For MITS: use `dr_grpo`** (already configured correctly)

## TRL GRPOConfig: norm_adv_by_std

- `dr_grpo` loss_type handles length normalization but does NOT automatically disable std normalization
- Must also set `norm_adv_by_std_in_grpo=False` (veRL param name) or equivalent
- In TRL this may be set via `scale_rewards` or a custom trainer modification
- Removing std normalization: advantages on high-variance questions (some right, some wrong) become larger -- correct behavior

## TRL Release Timeline (recent)

- 0.24.0: Oct 16, 2025
- 0.25.0: Nov 5, 2025
- 0.27.1: Jan 24, 2026 (Unsloth's best-tested)
- 0.29.0: Feb 25, 2026 (latest as of 2026-03-15)

## Unsloth 2026.3.x

- Latest: 2026.3.4 (Mar 8, 2026)
- Requires TRL >= 0.25.0
- Best tested with TRL 0.27.1 + transformers 5.1.0

## GDPO in MITS

- Triple reward: correctness [0.7] + format [0.15] + Socratic [0.15]
- reward_weights safe to use with any TRL >= 0.15.0
- multi_objective_aggregation="normalize_then_sum" requires TRL >= ~0.27.x (verify)
- Notebook: grpo_qwen3.5_9b.ipynb
- GDPO approach is definitively correct for 3 objectives with different difficulty levels

---

## GSPO (arXiv 2507.18071)

**What it is**: Group Sequence Policy Optimization. Qwen team algorithm that powers Qwen3. Sequence-level IS instead of token-level.

**Key parameters:**
- `epsilon=3e-4`, `epsilon_high=4e-4` (1000x smaller than GRPO's 0.2/0.28 due to sequence-level ratio definition)
- `importance_sampling_level="sequence"` (must be set explicitly)
- `beta=0.0` (no KL regularization, same as DAPO)
- `steps_per_generation=4` (minibatch partitioning)

**Why epsilon is ~1000x smaller**: Sequence-level IS ratio = exp(mean log-prob of sequence), numerically much smaller than per-token ratios. Using GRPO's 0.2 would clip nothing.

**Implementation**: ms-swift supports via `--importance_sampling_level sequence`; TRL v0.25+ supports natively

**LIMITATION (2026-03-21)**: beta=0.0 is correct for pure math reasoning models BUT causes
instruction-following degradation for conversational tutoring applications. For MITS, use beta=0.04.

---

## Dr. GRPO (arXiv 2503.20783)

**Two biases fixed:**
1. Length bias: `loss_type="dr_grpo"` normalizes by `max_completion_length` constant (not per-sample length)
2. Difficulty bias: removing std normalization from advantage computation prevents easy-question dominance

**TRL setting**: `loss_type="dr_grpo"` in GRPOConfig
**Also needed**: Disable std normalization separately (not automatic with dr_grpo loss_type)

---

## ReDit (arXiv 2506.18631)

**What**: Add Gaussian noise N(0, sigma^2) to rewards before advantage computation.

**Validated sigma range for binary rewards**: sigma in [0.01, 0.1]; optimal a=0.05 (uniform) = sigma~0.029 (Gaussian)

**MITS sigma=0.05 (Gaussian)**: slightly above optimal but within safe range, acceptable

**Apply to**: each reward component BEFORE weighting, not to aggregated reward

**Result**: ~10x faster convergence to same performance level in paper experiments

**CRITICAL**: ReDit is INCOMPATIBLE with zero-variance group masking (DAPO dynamic sampling).
- ReDit converts all-zero groups to low-noise groups, defeating the masking threshold check
- Use one or the other. ReDit is the preferred approach for MITS (already configured).
- Exception: can mask all-correct groups (accuracy=1.0) while using ReDit on all-wrong groups

---

## GRPO-LEAD (arXiv 2504.09696, EMNLP 2025)

**Difficulty reweighting formula** (correct version, not 2x/0.5x step):
```python
def difficulty_weight(rho_q, A=0.4, B=1.5, rho0=0.75, k=10):
    # rho_q = fraction of correct completions (0=hard, 1=easy)
    return A + (B - A) / (1 + math.exp(k * (rho_q - rho0)))
    # Hard (rho_q=0): weight ~1.5; Easy (rho_q=1): weight ~0.4
```

For negative advantages: use `w(1 - rho_q)` instead

**Results**: +4% AIME24, -19% token count vs baseline

**3-stage curriculum**:
- Stage 1 (100 steps): ~9,000 problems with difficulty >= 2.5 (no easy problems)
- Stage 2 (100 steps): ~2,283 problems where model accuracy <= 75%
- Stage 3 (140 steps): repetition/format correction

---

## Overlong Reward Shaping (DAPO, arXiv 2503.14476)

**Why needed**: When `max_completion_length` is reached, truncated completions either cause biased loss (if included) or NaN KL (if all masked). Overlong shaping trains model to be concise.

**Formula**:
```python
def overlong_penalty(length, L_max, L_cache=4096):
    if length <= L_max - L_cache: return 0.0
    elif length >= L_max: return -1.0
    else: return -(length - (L_max - L_cache)) / L_cache
```

**DAPO production values**: L_max=16384, L_cache=4096 (total budget: 20480 tokens)
**MITS recommendation**: L_max=12288, L_cache=3072 for A100 80GB memory constraint

**CRITICAL FINDING (2026-03-20)**: When max_thinking_tokens=1024 and model always hits this limit, every completion is truncated. This creates systematic negative signal on deep thinking (all truncated = 0 correctness reward = all below-average advantage = model learns to think shallowly). Fix: increase max_thinking_tokens to 4096+ or apply DAPO overlong MASKING (not penalty) for truncated samples.

---

## Thinking Tokens in GRPO Loss Computation

**Standard approach (DeepSeek-R1, Qwen3, TRL default)**:
- Policy gradient loss applies to ALL completion tokens (including <think>...</think>)
- Reward is computed from the FINAL ANSWER only (outcome reward)
- Thinking tokens receive the same scalar advantage as answer tokens
- This is correct: gradient flows through thinking to improve reasoning quality

**DuP-PO (arXiv 2506.23840)** -- token-level advantage scaling for thinking tokens:
- Suppress gradient for thinking tokens in INCORRECT responses (they just waste tokens)
- Amplify gradient for correct answers that don't need thinking
- Zero out advantage for thinking when equivalent no-think solution exists
- Result: +3.5 accuracy points on MATH500, -24.7% token reduction

**Key finding**: Incorrect responses generate 2x as many thinking tokens as correct ones.
For MITS: standard inclusion is fine; DuP-PO is an enhancement worth implementing in Stage 2.

---

## Unbounded Thinking Generation (vLLM issue #15418)

**Real documented problem**: Thinking models can generate indefinitely without emitting </think>.

**Three workarounds:**
1. **LogitsProcessor** (best): Force </think> after max_thinking_tokens. Must emit \n then </think> (two-token sequence).
   - ThinkingTokenBudgetProcessor implementation: muellerzr.github.io/til/end_thinking.html
2. **max_completion_length hard cap** (MITS current): Truncated completions get 0 correctness reward = negative signal = trains conciseness
3. **enable_thinking=False**: Only for models where thinking isn't needed; kills accuracy for STEM

**Native vLLM support**: PR #20859 (hard limit) is in progress, not yet merged as of 2026-03.

---

## Sparse Reward Solutions (near-zero accuracy ~5%)

**Root problem**: At 5% accuracy, ~66% of G=8 groups are all-wrong (zero gradient).

**Ordered by effectiveness:**
1. **Cold-start SFT** (DeepSeek-R1 approach): 200-500 SFT steps on rejection-sampled correct solutions raises baseline to 15-30%. Must be done BEFORE RL.
2. **Curriculum learning** (GRPO-LEAD): Easy+medium only in Stage 1 (easy problems have 40-80% accuracy = good gradient density)
3. **HAPO** (arXiv 2603.11321): Inject teacher demonstrations when group confidence < 0.8. +9.7 AIME points. Requires correct solutions available at training time.
4. **ReDit noise**: Converts zero-gradient groups to low-gradient. Exploration without correct signal.
5. **Dynamic sampling** (DAPO): Filter all-wrong groups. Do NOT combine with ReDit.
6. **Higher LR**: NOT recommended for sparse reward. Causes policy collapse.

**For MITS**: Curriculum is already configured. If stagnating at <10% after 50 steps, add cold-start SFT.

---

## LoRA Rank for GRPO (9B models)

**Tina ablation (1.5B, 2025)**:
- r=4: 47.72%; r=8: 47.89%; r=16: 48.92% (peak); r=32: 48.47%; r=64: 46.95%
- r=16 is optimal; r=64 UNDERPERFORMS due to RL optimization instability at high rank

**LoRA Without Regret (Schulman, Thinking Machines Lab, 2025) -- KEY FINDINGS FOR RL**:
- RL extracts ~1 bit of information per episode (scalar reward) -- r=1 to r=32 are all sufficient
- SFT needs r=256; RL needs r=1-32 (fundamentally different capacity requirements)
- MOST IMPORTANT: target_modules="all-linear" >> attention-only LoRA, even at same rank
- LoRA less tolerant of large effective batch sizes: keep effective batch < 32 unique prompts/step
- LR for LoRA ~10x higher than full fine-tuning (1/r scaling makes it rank-independent)

**LoRA Safety Alignment (arXiv 2507.17075) -- KEY FINDING FOR STYLE/BEHAVIOR**:
- r=1 is sufficient for safety/style behavior change in reasoning LLMs
- "Safety behavior mediated by a single direction" -- behavior changes need minimal rank
- r=1 best for behavior; full-rank risks interfering with existing reasoning weights
- Implication: r=16 is MORE than sufficient for Socratic style alignment

**Recommendation for 9B**: r=16 with lora_alpha=32
- Lower rank = stronger regularizer = prevents policy drift (especially important with beta=0)
- RL training more susceptible to forgetting than SFT
- Increase to r=32 only if performance plateaus after 200+ steps
- DO NOT use r=64: demonstrably underperforms r=16

**BF16 collapse warning**: BF16 LoRA training collapses at ~600 steps. Use FP16 or mixed precision for LoRA weights.

**MITS current**: r=32, acceptable. Consider r=16 if instability observed at step 600.

**Multi-objective consideration (2026-03-21)**: MTL-LoRA (AAAI 2025) shows standard LoRA
has no orthogonality constraints between task-specific directions. For MITS (3 objectives:
math, format, Socratic), opposing directions compete within the same rank dimensions.
If Socratic behavior degrades, increase to r=32 + add orthogonality regularization.

---

## S-GRPO (arXiv 2505.07686)

**What**: Serial-Group Decaying-Reward Policy Optimization. Trains early exit from thinking traces.

**How**: Instead of parallel rollouts, samples 1 path and selects multiple temporal exit points. Correct-earlier gets higher reward than correct-later.

**Results**: 35-61% thinking token reduction + 0.72-6.08% accuracy improvement on AIME/MATH-500

**Compatible with**: Qwen3, DeepSeek-distill

**Complexity**: High -- requires custom rollout logic. Future work for MITS.

---

## Unsloth GRPO Known Issues

1. **batch_size forced = num_generations**: Unsloth changes `per_device_train_batch_size` to `num_generations` if not a multiple. Affects memory estimates and diversity per step.
2. **KL NaN bug**: `mask_truncated_completions=True` + high clipped_ratio = all completions masked = NaN KL (issue #3149)
3. **VRAM growth over steps**: OOM after many steps in some configs (issue #3864)
4. **gradient_accumulation_steps not counted**: In batch/num_generations divisibility check
5. **TRL issue #3823**: GSPO loss incorrect with default `loss_type="bnpo"` when `importance_sampling_level="sequence"` and multi-step training. Check if using multi-step gradient accumulation with GSPO.

**Mitigation**: Use standard TRL GRPOTrainer for training; use Unsloth only for model loading (Flash Attention, quantization).

---

## OpenEvolve (2026-03-16)

**What it is**: Open-source implementation of DeepMind's AlphaEvolve. An evolutionary coding agent where LLMs replace mutation operators. Evolves full code files (not just functions) toward a user-defined quantitative fitness metric.

**Lineage**: FunSearch (Nature 2023, single functions, small LLMs, millions of samples) -> AlphaEvolve (May 2025, closed, Gemini, full codebases, thousands of samples) -> OpenEvolve (May 2025+, Apache 2.0, codelion)

**Primary repo**: https://github.com/codelion/openevolve (Asankhaya Sharma)
**Install**: `pip install openevolve`
**License**: Apache 2.0

**Core architecture (5 components)**:
1. Prompt Sampler: builds LLM context with parent code + top performers + diverse inspirations + execution artifacts + history
2. LLM Ensemble: weighted probabilistic model selection (e.g. 60% Flash, 40% Pro); any OpenAI-compatible API
3. Evaluator Pool: user-defined evaluate(path) -> Dict[str, float]; cascade stages; timeout; artifact capture
4. Program Database: MAP-Elites grid (quality-diversity) + Island Model (parallel isolated populations + ring migration)
5. Controller: orchestrates loop, checkpoints, seeding (default seed=42)

**Key mechanisms**:
- Diff-based mutations (default) vs. full rewrites: controlled by `diff_based_evolution` config flag
- EVOLVE-BLOCK-START / EVOLVE-BLOCK-END markers in code tell the LLM what it can modify
- Cascade evaluation: fast cheap checks first, expensive benchmarks last
- Artifacts (stderr, tracebacks, profiling) are fed back into next prompts -- self-debugging loop
- Double-selection: high-fitness parent + diverse inspiration set (prevents premature convergence)

**Compute**: No GPU needed for OpenEvolve itself. GPU only needed if your evaluator measures GPU performance. Python 3.10+ only.

**LLM costs**: ~$10-20 / 1000 iterations with Gemini Flash Lite. Local Ollama/vLLM is free.

**Proven results**:
- AlgoTune: 321x (JAX JIT auto-discovered), 256x (FFT auto-discovered), 95.78x (graph), 2.04x geomean (Gemini 2.5 Flash)
- Circle packing n=26: 2.634 (AlphaEvolve: 2.635, 99.96% parity)
- GPU kernel (Apple M-series GQA): +12.5% avg decode speed, +106% peak
- Prompt optimization (GEPA): +10.69% HotpotQA, +6.42% overall

**Limitations**:
- No built-in sandbox (add Docker for side-effect-heavy code)
- High-D MAP-Elites grids can be sparse (keep feature dimensions to 2-4)
- Cost balloons with Pro-tier LLMs at scale
- Hardware-specific kernel results do not generalize across GPU vendors
- Workers use DB snapshots, not live state (minor selection lag in parallel mode)

**Relevance to MITS**:
- NOT a replacement for GSPO/KTO/DPO training (operates on code, not model weights)
- Potential uses: reward function design search (evolve correctness/format/Socratic reward weights), Socratic prompt template evolution (GEPA-style), verify_answers.py speed optimization

**Related papers**:
- AlphaEvolve: arXiv 2506.13131
- CodeEvolve (related open-source framework): arXiv 2510.14150
- FunSearch: Romera-Paredes et al., Nature 2023

---

## Qwen3.5-9B DeltaNet LoRA Module Names (2026-03-19)

**Source**: `modeling_qwen3_5.py` raw file from HuggingFace Transformers (verified twice).

**Architecture**: 32 layers = 24 GatedDeltaNet (linear attention) + 8 standard Attention (3:1 pattern).
**Paper**: Gated Delta Networks: Improving Mamba2 with Delta Rule (arXiv:2412.06464)

### DeltaNet layer class: `Qwen3_5GatedDeltaNet`

All 5 nn.Linear layers (exact attribute names):
- `in_proj_qkv` -- fused Q+K+V projection (hidden_size -> key_dim*2 + value_dim)
- `in_proj_z` -- gate projection (hidden_size -> value_dim)
- `in_proj_b` -- beta/write-strength per head (hidden_size -> num_v_heads, small)
- `in_proj_a` -- alpha/decay per head (hidden_size -> num_v_heads, small)
- `out_proj` -- output projection (value_dim -> hidden_size)

### Standard attention layer class: `Qwen3_5Attention`

- `q_proj` -- (hidden_size -> num_attention_heads * head_dim * 2, the *2 is for QNorm)
- `k_proj` -- (hidden_size -> num_key_value_heads * head_dim)
- `v_proj` -- (hidden_size -> num_key_value_heads * head_dim)
- `o_proj` -- (num_attention_heads * head_dim -> hidden_size)

### CRITICAL: Naming differs from sibling model Qwen3Next

| Model | DeltaNet projection names |
|---|---|
| Qwen3.5 (this one) | `in_proj_qkv`, `in_proj_z`, `in_proj_b`, `in_proj_a` (4 separate) |
| Qwen3Next (different) | `in_proj_qkvz`, `in_proj_ba` (2 fused) |

Do NOT confuse them. Qwen3Next is a different model family.

### Recommended TARGET_MODULES for MITS (all 3 stages: GSPO, KTO, DPO)

```python
TARGET_MODULES = [
    # Standard attention (8 layers)
    "q_proj", "k_proj", "v_proj", "o_proj",
    # DeltaNet linear attention (24 layers)
    "in_proj_qkv", "in_proj_z", "in_proj_b", "in_proj_a", "out_proj",
    # MLP (32 layers)
    "gate_proj", "up_proj", "down_proj",
]
```

**WARNING**: Using only `["q_proj", "k_proj", "v_proj", "o_proj", ...]` (Qwen3 standard recipe) silently skips all 24 DeltaNet layers -- 75% of token-mixing capacity is frozen. PEFT does not raise an error.

**Alternative safe option**: `target_modules = "all-linear"` (Unsloth-confirmed for Qwen3.5).

**Trainable params at r=16**: ~340M with full coverage vs ~85M with attention-only. Both fit A100 80GB.

---

## GRPO Training Dynamics: Reward Plateau and Instruct Models (2026-03-20)

**Key insight**: Binary correctness reward on instruct model creates a mathematical ceiling.
- Instruct model at ~50-60% pass@1 on mixed-difficulty dataset
- Easy problems: all G rollouts correct = zero advantage = no gradient
- Hard problems: all G rollouts wrong = near-zero advantage = no gradient
- Only medium difficulty (20-80% correctness) provides learning signal
- Result: correctness reward plateau at 0.50-0.65 is EXPECTED and NORMAL

**Reference numbers**:
- GRPO Dynamics paper (arXiv 2503.06639): GSM8K success rate 21% -> 37.5% in one epoch
- Stanford vision-to-code GRPO: reward 0.3 -> 0.55, then plateau
- Qwen3-8B base+GRPO: mean reward 0.76 -> 0.83 (from higher starting point)
- VAPO/DAPO: use binary {0,1} rewards but don't report raw reward values

**Fix if plateau is unwanted**: DAPO Dynamic Sampling -- filter prompts where all G rollouts
succeed (trivial, no gradient) or all fail (no gradient). Keeps only the "teachable zone."

---

## Thinking Budget Saturation = Training Pathology (2026-03-20)

**Problem**: If max_thinking_tokens=1024 and model always hits it:
1. Truncated completions receive 0 correctness reward (wrong format or incomplete answer)
2. All G=8 rollouts = truncated = 0 reward = normalized advantage pushes model AWAY from deep thinking
3. Self-reinforcing: model learns to produce shallow 100-200 token reasoning to avoid truncation
4. Equivalent to training the model NOT to think

**Evidence from DAPO (arXiv 2503.14476)**:
- Production max_length = 16384 + 4096 cache = 20480 tokens
- Overlong FILTERING (masking, not penalty) significantly stabilizes training
- "Maintaining slow upward trend in entropy is conducive to improvement"

**Evidence from BRPO (arXiv 2505.13438)**:
- "Biased advantage estimation due to substantial reward noise, especially in early stages when many responses are abruptly cut off"
- BRPO designed to fix this; outperforms standard GRPO under all thinking budgets

**Fix (in order of priority)**:
1. Increase max_thinking_tokens to 4096 minimum, 8192 recommended
2. Apply DAPO overlong MASKING: completions hitting budget contribute zero gradient (not negative)
3. If budget truly constrained to 1024: add bonus reward for using less than the budget
   (incentivizes efficient reasoning, not truncation avoidance)

---

## Optimizer Choice for GRPO/RLHF (2026-03-25, UPDATED)

**Universal finding**: ZERO major RL papers use Lion. Every paper that discloses its optimizer uses AdamW.

### Verified optimizer choices in RL papers

| Paper | Optimizer | Actor LR | Beta1/Beta2 | Weight Decay |
|---|---|---|---|---|
| DeepSeek-R1 (2501.12948) | AdamW | 3e-6 | Not disclosed | Not disclosed |
| VAPO (2504.05118) | AdamW | 1e-6 | Not disclosed | Not disclosed |
| Open-Reasoner-Zero (2503.24290) | AdamW | 1e-6 | 0.9/0.95 | 0.0 |
| Kimi K2 (2507.20534) | Muon | Not disclosed | N/A | N/A |

### Why Lion is NOT recommended for GRPO (structural risks)

1. **Sign update discards advantage magnitude**: GRPO gradients are weighted by advantage A_i = (r - mean)/std. Lion's sign() collapses all magnitudes to +-lr. A high-advantage correct response and a barely-above-average one produce identical update steps. Reward signal magnitude is information -- discarding it is structurally wrong for policy gradient.

2. **Sign function non-convergence in noisy settings**: RL gradients are 3-5x noisier than SFT gradients. Documented instability from sign discreteness (RLion paper, PMC12215452) applies more strongly.

3. **LR recalibration required**: Lion needs 3-10x SMALLER lr than AdamW AND 10x LARGER weight decay. Standard RL LR (1e-6) would need to become 1e-7 to 3e-7 for Lion -- dangerously slow.

4. **No empirical validation**: optimi.dev Lion docs note "negative results seem to be with problems outside of what was evaluated -- RL, feedforward networks, weird hybrid architectures." This is documented, not speculative.

### Memory comparison for MITS (LoRA r=16, ~170M trainable params)

| Optimizer | States per param | Optimizer VRAM (LoRA) | Full 9B FT |
|---|---|---|---|
| AdamW fp32 | 2 | 1.36 GB | 72 GB |
| 8-bit AdamW | 2 (quantized) | 0.34 GB | 18 GB |
| Lion / AdamS | 1 | 0.68 GB | 36 GB |

**Conclusion for MITS**: LoRA r=16 means 1.36 GB optimizer states vs 80 GB VRAM. Memory is NOT the constraint. Do not change optimizer for memory reasons.

### AdamS (arXiv 2505.16363, EMNLP 2025) -- best alternative

**What**: Replaces second moment with squared momentum as normalizer. Eliminates m2 entirely.
**GRPO validation**: YES -- tested on GRPO with Qwen2.5-3B and DeepSeek-R1-Distill-Llama-8B on Countdown task. Results match or exceed AdamW.
**Memory**: Same as Lion (-50% optimizer states vs AdamW).
**Hyperparameter compatibility**: Directly inherits AdamW lr, beta1, weight_decay -- zero recalibration.
**Status**: EMNLP 2025 paper; not yet in TRL optim presets -- requires custom optimizer object.

### AdamW hyperparameters for MITS GRPO

```python
GRPOConfig(
    learning_rate=3e-6,       # Conservative, matches VAPO actor LR
    optim="adamw_torch",
    warmup_ratio=0.05,
    weight_decay=0.01,
    adam_beta1=0.9,
    adam_beta2=0.95,          # DeepSeek / Open-Reasoner-Zero: 0.95, not 0.999
    adam_epsilon=1e-8,
)
```

Note: beta2=0.95 (not 0.999) reduces EMA window for second moment -- more responsive to non-stationary RL objectives.

---

## Expected Accuracy Gains from GRPO on 9B Instruct Model (2026-03-20)

**Qwen3-8B instruct + GRPO (Qwen team internal)**:
- AIME24: 73.3% -> 83.3% (+10 pp)
- AIME25: 66.66% -> 73.3% (+6.6 pp)

**GRPO-LEAD 14B (340 steps, curriculum)**:
- AIME24 Pass@1: 0.614 -> 0.650 (+3.6 pp)
- AIME25 Pass@1: 0.429 -> 0.539 (+11.0 pp)

**Scaling law**: Average gain decreases 4.4% -> 1.9% as model grows 9B -> 200B (arXiv 2412.06000).
9B model has better relative headroom than larger models.

**Realistic MITS expectations** (LoRA r=16, 800 steps, curriculum):
- Hard math (AIME-like): +3-10 pp
- Medium math (AMC, standard olympiad): +10-20 pp
- Easy math (GSM8K): minimal gain (already near ceiling)
- STEM domain: +5-15 pp depending on curriculum coverage

---

## GRPO/GSPO Failure Modes for Socratic Tutor (2026-03-21)

**Full analysis**: research/findings_grpo_failure_modes_2026-03-21.md

### Critical finding: System prompt conflict is the dominant failure mode

Training system prompt requires `\boxed{answer}` (direct answer).
Deployment system prompt forbids direct answers ("НИКОГДА не давай готовых ответов").
These are diametrically opposed. 70% of reward signal trained the model to give direct answers.
No amount of inference-time prompting fully overrides this: RL updates token distributions,
not just instruction-following rules.

### KL penalty (beta=0.0) for conversational tutor = wrong configuration

- beta=0.0 is correct for math-only reasoning models (DeepSeek-R1, DAPO use case)
- beta=0.0 is WRONG for conversational tutors that need to preserve instruction-following
- For MITS: set beta=0.04 in GSPO config
- Tradeoff: ~2-5 pp lower math accuracy, preserved Socratic behavior compliance

### Reward hacking taxonomy for MITS rewards

| Reward | Hacking Pattern | Risk |
|---|---|---|
| Correctness (0.7) | Append `\boxed{X}` even to incomplete reasoning | HIGH |
| Format (0.15) | Insert `\boxed{}` + step markers; target 50-800 word window | HIGH |
| Socratic (0.15) | Append "Как ты думаешь? Почему?" suffix to direct answer | MEDIUM |

### MO-GRPO dominant reward bias

GRPO's advantage function is biased toward highest-variance reward (arXiv:2509.22047).
Correctness (binary, ~50% accuracy = max variance) dominates even with 0.7 explicit weight.
Effective weight on correctness in early training may be 0.85-0.90 due to variance bias.
This exacerbates the direct-answer training problem.

### Recommended fixes (ranked)

1. Change training system prompt to match Socratic deployment context
2. Add 4th reward component: negative penalty for direct answers without scaffolding (-0.5)
3. Set beta=0.04 in GSPO config
4. Add Socratic compliance metric to evaluate_stage.py
5. Replace score_socratic() question-mark heuristic with semantic LLM judge

### Papers cited in failure modes analysis

- DAPO (arXiv:2503.14476): entropy collapse, length hacking, 4 GRPO fixes
- GDPO (arXiv:2601.05242): multi-reward normalization, reward signal collapse
- MO-GRPO (arXiv:2509.22047): variance-bias dominant reward in multi-objective GRPO
- "Mitigating Alignment Tax" (arXiv:2309.06256): quantified reward-forgetting tradeoff
- "Comedy of Estimators" (arXiv:2512.21852): KL collapse conditions
- "Hidden Objective Biases" (arXiv:2601.05002): systematic gradient biases in group-based RL
- DeepSeek-R1 (arXiv:2501.12948): cold-start SFT rationale, format prior necessity
- MTL-LoRA (AAAI 2025): multi-task LoRA orthogonality requirements

---

## GSPO Training Failure Post-Mortem (2026-03-23)

**Full analysis**: research/findings_gspo_failure_diagnosis_2026-03-23.md

### Summary of verdict per failure cause

| Cause | Verdict | Evidence |
|---|---|---|
| System prompt mismatch | CONFIRMED CRITICAL | Llama 2 Ghost Attention (2307.09288), InstructGPT (2203.02155) |
| Reward weight imbalance | PARTIALLY CONFIRMED | MO-GRPO (2509.22047) variance theorem, GDPO (2601.05242) |
| Beta=0.0 | CONFIRMED for tutor use case | DeepSeek-R1 uses 0.001, DAPO justification only for base-model math |
| Rewards decreasing | CONFIRMED AS SYMPTOM | LLD death spiral (2512.04220), GTPO (2508.03772) |
| LoRA r=16 too small | NOT CONFIRMED | r=1 sufficient for behavior (2507.17075), r=64 WORSE than r=16 (Tina) |
| GRPO-specific issues | PARTIALLY RELEVANT | TRL issue #3823 (GSPO multi-step bug), group variance issue |

### New papers discovered (2026-03-23)

- **LLD Death Spiral** (arXiv 2512.04220): Mechanism for reward decrease in GRPO. Three phases: stagnation → steady decay → catastrophic collapse. Negative gradients from incorrect responses suppress correct response likelihood.
- **GTPO** (arXiv 2508.03772): Policy collapse mechanism in GRPO -- entropy collapse in second half of training. GRPO performance drops sharply; GTPO fixes via gradient/entropy control.
- **MO-GRPO** (arXiv 2509.22047): Multi-objective reward hacking. Theorem 1: advantage dominated by reward with highest variance, regardless of explicit weight. Proved empirically: readability dominated translation accuracy.
- **Llama 2 Ghost Attention** (arXiv 2307.09288): System prompt must be included in every training rollout during RLHF to maintain instructional consistency. Zero-loss training on intermediate turns when synthetic data injected.
- **"LoRA is All You Need for Safety Alignment"** (arXiv 2507.17075): r=1 optimal for style/behavior alignment. Behavior change mediated by single direction. Knowledge requires higher rank, behavior does not.
- **TRL issue #3823**: GSPO loss computed incorrectly with default bnpo loss_type when using sequence-level IS + multi-step. Check TRL version.

### Cold-start SFT necessity (DeepSeek-R1 evidence)

DeepSeek-R1 Section 3.2: "without cold start, the model has no behavioral prior for the desired output format, and RL may not converge toward the target distribution." For Socratic style: Qwen3.5-9B Instruct has no trained prior for Socratic behavior. Run 200-300 SFT steps on dialogs.jsonl BEFORE GSPO.

### GDPO weight threshold finding

GDPO (arXiv 2601.05242): "reducing secondary weight to 0.25 has little impact on the primary objective." Threshold where secondary reward becomes effectively ignored: ~0.25. With GDPO normalization, 0.15 Socratic weight is slightly above this threshold but only marginally. Boost to 0.45 is well-justified.

### Beta values across major papers

| Paper | Beta | Context |
|---|---|---|
| DeepSeek-R1 Stage 1 | 0.001 | Math reasoning from base model |
| DeepSeek-R1-Zero | 0.0 | Pure RL, suffers language mixing |
| DAPO | 0.0 | Math from base model, explicitly justified |
| GSPO | 0.0 | Math from base model, clipping as substitute |
| TRL v0.15.2 default | 0.04 | Generic RLHF applications |
| TRL v0.27+ default | 0.0 | Changed to follow DAPO/DeepSeek practice |
| MITS recommendation | 0.04 | Socratic tutoring, instruction-following preservation |
