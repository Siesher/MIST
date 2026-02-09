# Research Summary: Techniques Evaluation

**Date**: 2026-02-07

## Technique Comparison Matrix

Priority scoring: Impact (1-5) x Feasibility (1-5) / Effort (1-5) = **Score**

| # | Technique | Impact | Feasibility | Effort | **Score** | Stage | Status |
|---|-----------|--------|-------------|--------|-----------|-------|--------|
| 1 | SFT + QLoRA (curriculum) | 4 | 5 | 2 | **10.0** | 1 | **Selected** |
| 2 | Knowledge Distillation (data gen) | 5 | 4 | 3 | **6.7** | 0 | **Selected** |
| 3 | Dr. GRPO | 5 | 4 | 3 | **6.7** | 3 | **Selected** |
| 4 | SimPO | 3 | 5 | 2 | **7.5** | 2 | **Selected** |
| 5 | STaR self-improvement | 3 | 4 | 3 | **4.0** | 4 | **Optional** |
| 6 | Re-distillation (logits) | 2 | 3 | 1 | **6.0** | — | Deferred |
| 7 | Scaf-GRPO | 4 | 3 | 3 | **4.0** | 3b | Fallback |
| 8 | Budget Forcing (inference) | 3 | 5 | 1 | **15.0** | 5 | **Selected** (inference only) |
| 9 | PRM (Process Reward Model) | 3 | 2 | 4 | **1.5** | — | Deferred |
| 10 | Model Merging (TIES/DARE) | 2 | 4 | 2 | **4.0** | — | Deferred |
| 11 | rStar-Math (MCTS) | 5 | 2 | 5 | **2.0** | — | Too compute-heavy |
| 12 | DPO (over SimPO) | 3 | 4 | 3 | **4.0** | — | SimPO preferred |
| 13 | Full RL (PPO) | 4 | 2 | 5 | **1.6** | — | GRPO preferred |

## Selected Pipeline (ordered by priority score)

```
[Score 10.0] SFT + QLoRA with curriculum learning
[Score  7.5] SimPO preference alignment
[Score  6.7] Knowledge Distillation (data generation)
[Score  6.7] Dr. GRPO reinforcement learning
[Score 15.0] Budget Forcing (inference-time, zero training cost)
[Score  4.0] STaR self-improvement (optional, diminishing returns)
```

## Key Empirical Results from Literature

### GRPO effectiveness on small models

| Model | Technique | MATH-500 Before | MATH-500 After | Delta |
|-------|-----------|----------------|----------------|-------|
| Qwen2.5-Math-1.5B | Dr. GRPO | 36.0% | 73.6% | **+37.6%** |
| Qwen2.5-Math-7B | GRPO | ~60% | ~85% | **+25%** |
| Qwen2.5-Math-7B | Scaf-GRPO | AIME24: baseline | AIME24: +44.3% | **+44.3%** |
| DeepSeek-R1-Distill-1.5B | Distill+GRPO | — | beats GPT-4o | breakthrough |

### Model size scaling

| Model | MATH-500 | AIME 2025 | RAM (Q4) |
|-------|----------|-----------|----------|
| Qwen3-0.6B | ~70% | ~15% | 1.5 GB |
| Qwen3-1.7B | ~85-95% | ~30% | 3 GB |
| **Qwen3-4B** | **97%** | **65.6%** | **4.5 GB** |
| Qwen3-4B-Thinking | ~97% | **81.3%** | 4.5 GB |
| Qwen3-8B | ~98% | ~75% | 8 GB |

**Insight**: The 1.7B→4B jump gives the biggest quality/size ratio improvement, especially on hard math (AIME: 30%→66%).

### Distillation vs RL

| Approach | Pros | Cons | Best for |
|----------|------|------|----------|
| Distillation (SFT on teacher data) | Simple, stable, cheap | Bounded by teacher quality | Knowledge transfer, broad coverage |
| RL (GRPO) | Exceeds teacher, self-improving | Unstable for small models, needs verifier | Reasoning quality, math accuracy |
| **Combined** | Best of both worlds | More complex pipeline | **Our use case** |

DeepSeek-R1 conclusion: "Pure RL can discover reasoning, but distillation provides a stronger starting point. The optimal approach is distillation first, then RL refinement."

## Rejected Alternatives

### 1. rStar-Math (MCTS self-play)
- **Why rejected**: Requires thousands of MCTS rollouts per problem. For 20K problems x 64 rollouts = 1.28M inferences. Even on A100, this takes days and is impractical for our compute budget.
- **Keep in mind**: If compute becomes available, this is the most powerful technique (90% MATH with 7B model).

### 2. Full PPO
- **Why rejected**: Needs critic model (doubles VRAM), more complex to tune, GRPO achieves same results with less memory.

### 3. Process Reward Models (PRM)
- **Why rejected**: Needs step-level annotations (~100K annotated steps), expensive to create. ORM (outcome-based rewards via SymPy) is sufficient for training. PRM can be added later for inference-time scaling.

### 4. Continued Pretraining on Russian
- **Why rejected**: Qwen3 already supports 119 languages, Russian is well-represented. Fine-tuning on Russian task data (our SFT) is more efficient than continued pretraining.

### 5. Model Merging (TIES/DARE)
- **Why rejected**: Training a single adapter on mixed data outperforms merging separate adapters. Merging adds unpredictability.

## STEM Verification Strategy (Critical Addition)

GRPO requires verifiable rewards. The core challenge: **math is verifiable, but biology/conceptual physics/chemistry are not.**

### Solution: Hybrid Domain-Aware Verification

| Domain | Verifiable Subset | Verification Method | Non-Verifiable Subset | Method |
|--------|-------------------|--------------------|-----------------------|--------|
| Math | Equations, proofs, calculations | **SymPy** (exact) | Explanations | RaR LLM-judge |
| Physics | Kinematics, circuits, thermo calcs | **Python/numeric** (tol=2%) | Laws, concepts | RaR LLM-judge |
| Chemistry | Balancing, stoichiometry, molarity | **ChemPy** (exact) | Bonds, reactions, organic | RaR LLM-judge |
| CS | Code output, algorithms | **Unit tests** (exact) | Complexity theory | RaR LLM-judge |
| Biology | Multiple-choice | **Exact match** | Processes, terminology | RaR LLM-judge |

### Key Libraries
- **SymPy**: symbolic math verification (existing)
- **ChemPy**: `balance_stoichiometry()`, molecular weights, equilibrium — [PyPI](https://pypi.org/project/chempy/)
- **PhysiPy**: physics formula calculations — [GitHub](https://github.com/rohankishore/PhysiPy)
- **RaR (Rubrics as Rewards)**: [arXiv:2507.17746](https://arxiv.org/pdf/2507.17746)
  - LLM-as-judge with structured rubric criteria
  - +31% on HealthBench, +7% on GPQA-Diamond
  - Rubric format: 7-20 criteria with weights (Essential/Important/Optional/Pitfall)

### GRPO Two-Phase Approach
- **Phase 3a**: GRPO on verifiable problems ONLY (math calc, physics calc, chem calc, code, MC) — exact rewards, stable training
- **Phase 3b**: Add conceptual problems with RaR rewards (if Phase 3a is stable)
- **Fallback**: If RaR is too noisy, use conceptual data only for SFT (Phase 1), not GRPO

### STEM Data Sources
- **MMLU-STEM** ([TIGER-Lab/MMLU-STEM](https://huggingface.co/datasets/TIGER-Lab/MMLU-STEM)) — verified MC across all STEM, translate to Russian
- **MMLU-Pro** ([TIGER-Lab/MMLU-Pro](https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro)) — 12K expert-curated questions, 14 domains
- No ready-made Russian STEM datasets found → must generate via distillation

## Open Questions

1. **Data generation model**: Use DeepSeek-R1-Distill-Qwen-32B (free, local on A100) vs DeepSeek API (paid, faster)?
   - **Recommendation**: Start local, switch to API if quality insufficient

2. **GRPO group size**: G=8 (faster, less diverse) vs G=16 (more diverse, 2x compute)?
   - **Recommendation**: Start G=8, increase if reward variance is too high

3. **Which STaR loop**: STaR (with rationalization) vs ReST^EM (simpler)?
   - **Recommendation**: ReST^EM — simpler, well-tested, sufficient for our scale

4. **Budget Forcing at inference**: How many "Wait" tokens to append?
   - **Recommendation**: Test 0, 1, 3, 5 "Wait" appends, pick optimal via eval

5. **RaR judge model for GRPO**: Use same model (self-judge) vs external model?
   - **Recommendation**: External judge (Qwen3-8B or API) — self-judging causes reward hacking

6. **Biology coverage depth**: Focus on school-level (ЕГЭ) or broader?
   - **Recommendation**: School-level (grades 5-11) — matches MITS target audience
