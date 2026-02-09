# Feature Specification: Model Training Strategy for Lightweight MITS

**Feature Branch**: `014-model-training-strategy`
**Created**: 2026-02-07
**Status**: Draft
**Input**: Research on Qwen3-1.7B/4B fine-tuning, GRPO, distillation, and modern RL techniques

## Problem Statement

MITS currently uses GLM-4.7-Flash (30B MoE, ~13GB GGUF) via Ollama for tutoring. This:
- Requires 16+ GB VRAM for acceptable speed
- Cannot run on weak devices (CPU + 8/16 GB RAM)
- Is not fine-tuned for Socratic pedagogy
- Has no domain-specific training for Russian math/STEM

Existing fine-tune `Siesher/qwen3-1.7b-reasoning-lora` showed:
- Math: **100%** (5/5 perfect on our test suite)
- Physics: **33%** (calculation errors, weak explanations)
- Chemistry: **67%** (fractional coefficients in balancing)
- CS: **67%** (typos in terminology)
- Biology: **0%** (hallucinated terms like "энолифильные связи")

**Goal**: Train lightweight models (1.7B/4B) that deliver high-quality Socratic tutoring across **all STEM disciplines** (Math, Physics, Chemistry, CS, Biology) on Russian, while running on 8-16 GB RAM devices.

## Model Selection

### Primary: Qwen3-4B (16 GB RAM target)

| Property | Value |
|----------|-------|
| Parameters | 4.0B (3.6B non-embedding) |
| Architecture | Dense Transformer, 36 layers |
| Attention | 32 Q / 8 KV (GQA) |
| Context | 32K native, 131K with YaRN |
| GGUF Q4_K_M | **2.5 GB** download, ~4.5 GB RAM |
| MATH-500 (thinking) | **97.0%** |
| AIME 2025 (thinking) | **65.6%** (81.3% with Thinking-2507) |
| GPQA Diamond | **55.9%** (65.8% with Thinking-2507) |
| Multilingual | 119 languages including Russian |
| License | Apache 2.0 |

### Fallback: Qwen3-1.7B (8 GB RAM target)

| Property | Value |
|----------|-------|
| Parameters | 2.0B |
| Architecture | Dense Transformer, 28 layers |
| GGUF Q4_K_M | **1.1 GB** download, ~3 GB RAM |
| MATH-500 (thinking) | ~95% |
| Comparable to | Qwen2.5-3B |

### Why Qwen3 over alternatives

| Model | Pros | Cons |
|-------|------|------|
| **Qwen3-4B** | Best math benchmarks, Russian support, thinking mode, Apache 2.0 | Dense (not MoE) |
| Phi-4-mini (3.8B) | Strong reasoning | Weak multilingual, MIT license limits |
| SmolLM3-3B | Efficient | Weaker on math, limited Russian |
| Qwen2.5-Math-1.5B | Math-specialized | No general STEM, no Russian tuning |
| Gemma-3-4B | Google backing | Weaker Russian than Qwen3 |

## Training Strategy: Multi-Stage Pipeline

Based on Light-R1 (ACL Industry 2025), DeepSeek-R1 distillation, and GRPO research.

```
Stage 0: Data Generation          ← Synthetic + Distillation
    ↓
Stage 1: SFT with Curriculum      ← Foundation (Socratic style + STEM knowledge)
    ↓
Stage 2: SimPO                    ← Preference alignment (Socratic vs Direct)
    ↓
Stage 3: GRPO (Dr. GRPO)          ← RL with math verification rewards
    ↓
Stage 4: Self-Improvement (STaR)  ← Iterative bootstrap (optional)
    ↓
Stage 5: Export + Integration      ← GGUF → Ollama → MITS
```

### Stage 0: Data Generation

**Goal**: Create 50-100K high-quality Russian STEM training examples.

**Sources**:
1. **Knowledge Distillation** from DeepSeek-R1 / Qwen3-235B API
   - Generate detailed CoT solutions on Russian math/STEM problems
   - Include `<think>...</think>` reasoning traces
   - Verify all answers via SymPy / code execution
   - Rejection sampling: keep only verified-correct solutions

2. **Existing datasets** (augmentation):
   - `Siesher/Adaptive_Skip_thinking_Reasoning` (7.79K) — expand 5-10x
   - Russian school math (grades 5-11) from open textbooks
   - Physics/Chemistry problem banks (ЕГЭ, ОГЭ format)

3. **Socratic dialog generation**:
   - System prompt: "Generate a tutoring dialog where tutor asks guiding questions"
   - Format: multi-turn `[student, tutor, student, tutor, ...]`
   - Include scaffolding: hints → leading questions → partial reveals → full solution

4. **Ready-made Russian STEM datasets** (MC with verified answers):
   - [NLPCoreTeam/mmlu_ru](https://huggingface.co/datasets/NLPCoreTeam/mmlu_ru) — MMLU translated to Russian, ~3.5K STEM questions
   - [ai-forever/MERA](https://huggingface.co/datasets/ai-forever/MERA) — ruMMLU with human-verified translations (Yandex.Toloka)
   - [allenai/sciq](https://huggingface.co/datasets/allenai/sciq) — 13,679 MC science questions (English → translate)
   - [TIGER-Lab/MMLU-STEM](https://huggingface.co/datasets/TIGER-Lab/MMLU-STEM) — dedicated STEM MC subset
   - Generate CoT solutions for each MC question via teacher model

**Dataset composition target (STEM-balanced)**:

| Domain | Count | Calc / Verifiable | Conceptual | Source |
|--------|-------|-------------------|------------|--------|
| Math (algebra, calculus, geometry) | 15K | 12K | 3K | Distillation + textbooks |
| Physics (mechanics, thermo, EM) | 12K | 7K | 5K | Distillation + ЕГЭ + MMLU |
| Chemistry (stoichiometry, organic) | 10K | 5K | 5K | Distillation + ЕГЭ + MMLU |
| CS / Algorithms | 10K | 6K (code) | 4K | Distillation + coding + MMLU |
| Biology (cell, genetics, ecology) | 8K | 2K (MC) | 6K | Distillation + MMLU |
| Socratic dialogs (multi-turn, all STEM) | 10K | — | 10K | Synthetic generation |
| **Total** | **~65K** | **32K** | **33K** | |

**Key principle**: Each STEM discipline gets 8-15K examples (no single domain > 25% of total). Socratic dialogs cover ALL disciplines, not just math.

**Difficulty distribution**: 30% easy (grades 5-7), 40% medium (grades 8-9), 30% hard (grades 10-11, олимпиады)

**Verification split**:
- **Verifiable** (32K): math equations, physics calculations, chemistry stoichiometry, code tests → exact automated verification
- **Conceptual** (33K): explanations, definitions, processes → verified by teacher model during generation (rejection sampling with rubric-based LLM-as-judge)

**Format**: ChatML with adaptive reasoning tags:
```
<|im_start|>user
Реши уравнение x² - 5x + 6 = 0
<|im_end|>
<|im_start|>assistant
<think>
<thought_type>CoT</thought_type>
Для решения квадратного уравнения ax² + bx + c = 0...
Дискриминант D = b² - 4ac = 25 - 24 = 1...
</think>
А ты знаешь формулу дискриминанта? Попробуй вычислить D = b² - 4ac для этого уравнения.
<|im_end|>
```

### Stage 1: Supervised Fine-Tuning (SFT) with Curriculum

**Method**: QLoRA via Unsloth + TRL SFTTrainer
**Hardware**: Colab A100 (80 GB) or RTX 2080 (8 GB, batch=1)

**Hyperparameters**:

| Parameter | Qwen3-4B | Qwen3-1.7B |
|-----------|----------|-------------|
| LoRA rank (r) | 32 | 32 |
| LoRA alpha | 64 | 64 |
| Target modules | all-linear | all-linear |
| Quantization | 4-bit NF4 | 4-bit NF4 |
| Max seq length | 2048 | 2048 |
| Batch size (A100) | 4 | 8 |
| Gradient accumulation | 4 | 4 |
| Learning rate | 2e-4 | 2e-4 |
| Scheduler | cosine | cosine |
| Warmup steps | 50 | 50 |
| Epochs | 3 | 3 |
| Optimizer | adamw_8bit | adamw_8bit |
| Gradient checkpointing | unsloth | unsloth |

**Curriculum schedule**:
- Epoch 1: Easy + Medium examples (grades 5-9)
- Epoch 2: Full dataset (grades 5-11)
- Epoch 3: Hard examples weighted 2x (grades 10-11, олимпиады)

**VRAM estimate**: ~6 GB (4B QLoRA), ~4 GB (1.7B QLoRA)
**Time estimate**: ~30-60 min on A100, ~2-4 hours on RTX 2080

### Stage 2: SimPO (Preference Optimization)

**Method**: SimPO via TRL CPOTrainer (no reference model needed)
**Why SimPO over DPO**: No reference model = less VRAM, +6.4% over DPO on AlpacaEval

**Preference pairs generation (all STEM disciplines)**:
- **Chosen**: Socratic response (guiding question, step-by-step hints, accurate STEM facts)
- **Rejected**: Direct answer (just gives the solution) OR factually incorrect response
- Generate 5-10K pairs across all domains:
  - Math: 2K pairs (Socratic vs Direct)
  - Physics: 2K pairs (Socratic vs Direct + correct vs incorrect calculations)
  - Chemistry: 1.5K pairs (correct vs incorrect equations/explanations)
  - CS: 1.5K pairs (working code vs buggy + explanation quality)
  - Biology: 1.5K pairs (accurate vs hallucinated terminology)
  - Mixed: 1.5K pairs (various quality dimensions)

**Hyperparameters**:

| Parameter | Value |
|-----------|-------|
| Loss type | simpo |
| Beta | 2.0 |
| Gamma (reward margin) | 1.0 |
| Learning rate | 5e-7 |
| Epochs | 1 |
| Batch size | 4 |

**Expected improvement**: +3-8% on Socratic Score (more guiding questions, fewer direct answers)

### Stage 3: GRPO (Group Relative Policy Optimization)

**Method**: Dr. GRPO via TRL GRPOTrainer + Unsloth
**Why Dr. GRPO**: Removes length bias, +37.6% improvement over vanilla GRPO (DeepSeekMath)

**Hybrid STEM Reward System**:

GRPO requires verifiable rewards. For STEM, we use a **domain-aware hybrid verifier**:

| Domain | Verifiable Part | Method | Conceptual Part | Method |
|--------|----------------|--------|-----------------|--------|
| Math | Equations, integrals, proofs | SymPy | Explanations | RaR |
| Physics | Formulas, calculations | Python/PhysiPy | Laws, concepts | RaR |
| Chemistry | Balancing, stoichiometry | ChemPy | Bonds, reactions | RaR |
| CS | Code output | Unit tests | Complexity, theory | RaR |
| Biology | MC answers | Exact match | Processes, terms | RaR |

**RaR = Rubrics as Rewards** ([arXiv:2507.17746](https://arxiv.org/pdf/2507.17746)): LLM-as-judge evaluates response against structured rubric criteria. Achieved +31% on medical tasks, +7% on GPQA-Diamond.

```python
def stem_reward(completion, ground_truth, domain, rubric=None):
    answer = extract_final_answer(completion)

    # 1. Domain-specific exact verification (where possible)
    if domain == "math":
        correct = verify_with_sympy(answer, ground_truth)
    elif domain == "physics" and is_numeric(ground_truth):
        correct = verify_numeric(answer, ground_truth, tol=0.02)
    elif domain == "chemistry" and is_equation(ground_truth):
        correct = verify_stoichiometry(answer, ground_truth)  # ChemPy
    elif domain == "cs" and has_test_cases(ground_truth):
        correct = run_code_tests(answer, ground_truth)
    elif domain in ("biology", "physics", "chemistry", "cs"):
        # Conceptual questions: MC exact match or rubric-based judge
        if is_multiple_choice(ground_truth):
            correct = answer.strip().upper() == ground_truth.strip().upper()
        else:
            correct = rubric_judge(completion, ground_truth, rubric)
    else:
        correct = False

    # 2. Base reward
    reward = 1.0 if correct else -0.5

    # 3. Reasoning quality bonus
    has_steps = "<think>" in completion and "</think>" in completion
    if has_steps:
        reward += 0.2

    # 4. Socratic style bonus
    visible_answer = completion.split("</think>")[-1] if "</think>" in completion else completion
    if correct and "?" in visible_answer:
        reward += 0.1

    return reward


def rubric_judge(completion, reference, rubric):
    """Use LLM-as-judge with structured rubric for conceptual questions.
    Returns True/False based on rubric score threshold."""
    # Uses a smaller judge model (Qwen3-8B) or teacher API
    # Rubric format: list of (criterion, weight) pairs
    # Score = weighted sum of criterion passes / max possible
    # Threshold: score >= 0.6 → correct
    ...
```

**GRPO training split by verification type**:
- **Phase 3a**: GRPO on verifiable problems only (32K) — exact rewards, most stable
- **Phase 3b**: GRPO on mixed problems (32K verifiable + 10K conceptual with RaR) — adds breadth
- **Fallback**: If RaR rewards are too noisy, use conceptual data only in SFT (Phase 1), not GRPO

**Hyperparameters**:

| Parameter | Value |
|-----------|-------|
| Group size (G) | 8 |
| Max completion length | 2048 |
| Learning rate | 5e-6 |
| scale_rewards | False (Dr. GRPO) |
| Epochs | 1 |
| KL coefficient | 0.01 |

**Curriculum for GRPO**: Start with problems where model gets 30-70% correct (most informative), gradually increase difficulty.

**VRAM estimate**: ~20-30 GB (4B, needs A100)
**Time estimate**: ~2-4 hours on A100

**Expected improvement**: +15-40% on math benchmarks (based on DeepSeekMath results)

### Stage 4: Self-Improvement (STaR) — Optional

**Method**: Iterative bootstrap (STaR / ReST^EM)

**Loop** (2-3 iterations):
1. Generate 16 solutions per problem (from current model)
2. Verify correctness via hybrid STEM verifier:
   - Math: SymPy, Physics: numeric check, Chemistry: ChemPy, CS: unit tests
   - Conceptual STEM: rubric-based LLM-as-judge (score >= 0.6)
3. Keep only correct/high-quality solutions
4. Fine-tune on verified solutions (1 epoch SFT)
5. Repeat with improved model

**STaR problem set**: Balanced across all STEM domains (not just math).

**Expected improvement**: +10-20% per iteration (diminishing returns after 3)

### Stage 5: Export + Integration

1. **GGUF export** via Unsloth:
   ```python
   model.save_pretrained_gguf("output/", tokenizer, quantization_method="q4_k_m")
   ```

2. **Ollama Modelfile**:
   ```
   FROM ./mits-tutor-qwen3-4b-q4_k_m.gguf
   PARAMETER temperature 0.7
   PARAMETER top_p 0.9
   PARAMETER num_ctx 4096
   SYSTEM "Ты — сократический репетитор по математике и STEM предметам."
   ```

3. **MITS integration**: Config-based model selection in `backend/app/config.py`:
   ```python
   # Auto-detect available VRAM / RAM
   if available_ram >= 16:
       MODEL = "mits-tutor-qwen3-4b"
   elif available_ram >= 8:
       MODEL = "mits-tutor-qwen3-1.7b"
   else:
       MODEL = "mits-tutor-qwen3-0.6b"  # minimal fallback
   ```

## Evaluation Plan

### STEM Benchmark (expanded, 30 questions)

Expanded from 15 to 30 questions for statistical significance. Equal weight per discipline.

| Domain | Calc Questions | Conceptual Questions | Total | Pass (4B) | Pass (1.7B) |
|--------|---------------|---------------------|-------|-----------|-------------|
| Math | 4 | 2 | 6 | >= 5/6 (83%) | >= 4/6 (67%) |
| Physics | 3 | 3 | 6 | >= 4/6 (67%) | >= 3/6 (50%) |
| Chemistry | 3 | 3 | 6 | >= 4/6 (67%) | >= 3/6 (50%) |
| CS | 3 | 3 | 6 | >= 5/6 (83%) | >= 4/6 (67%) |
| Biology | 2 | 4 | 6 | >= 4/6 (67%) | >= 3/6 (50%) |
| **Total** | **15** | **15** | **30** | **>= 22/30 (73%)** | **>= 17/30 (57%)** |

### Standardized Benchmarks

| Benchmark | Target (4B) | Target (1.7B) | Method |
|-----------|-------------|---------------|--------|
| MATH-500 | >= 95% | >= 90% | thinking mode, pass@1 |
| GSM8K | >= 90% | >= 85% | thinking mode, pass@1 |
| MMLU-STEM subset (Ru) | >= 60% | >= 45% | translated, MC format |
| Socratic Score | >= 60% | >= 50% | % responses with guiding questions |
| Telling Rate | <= 15% | <= 25% | % direct answers (constitution MUST: <15%) |

### Per-Domain Quality Gates (after each training stage)

| Stage | Math | Physics | Chemistry | CS | Biology | Overall |
|-------|------|---------|-----------|----|---------|---------|
| Base (pre-training) | 70% | 40% | 35% | 50% | 30% | 45% |
| After SFT | 90% | 60% | 55% | 70% | 50% | **65%** |
| After SimPO | 90% | 60% | 55% | 70% | 50% | **65%** (+ Socratic) |
| After GRPO | **95%** | **67%** | **67%** | **83%** | **60%** | **73%** |
| After STaR | 97% | 70% | 70% | 85% | 65% | **77%** |

**Gate rule**: If any discipline drops below its previous stage score after training, investigate catastrophic forgetting and adjust data mix.

### Comparison Matrix

| Model | MATH-500 | STEM-30 | Physics | Biology | RAM | Speed | Socratic |
|-------|----------|---------|---------|---------|-----|-------|----------|
| GLM-4.7-Flash (baseline) | ? | ? | ? | ? | 16 GB | ~15 tok/s | Low |
| Qwen3-1.7B base | ~85% | ~45% | ~40% | ~30% | 3 GB | ~30 tok/s | None |
| Qwen3-1.7B + SFT (current) | ~90% | ~53% | ~33% | ~0% | 3 GB | ~21 tok/s | Medium |
| **Qwen3-4B + full pipeline** | **>=95%** | **>=73%** | **>=67%** | **>=60%** | **4.5 GB** | **~20 tok/s** | **High** |

## Hardware & Compute Requirements

### Training (Colab A100 80GB)

| Stage | VRAM | Time | Cost (Colab Pro+) |
|-------|------|------|-------------------|
| Data generation (DeepSeek-R1 inference) | ~40 GB | 2-3 days | ~$30 |
| SFT (QLoRA) | ~6 GB | 1 hour | ~$1 |
| SimPO | ~8 GB | 30 min | ~$0.5 |
| GRPO | ~25 GB | 3 hours | ~$5 |
| STaR (3 iterations) | ~10 GB | 3 hours | ~$5 |
| GGUF export | ~20 GB | 15 min | ~$0.5 |
| **Total** | | **~3-4 days** | **~$42** |

### Inference (target devices)

| Device | Model | GGUF | RAM Used | Speed |
|--------|-------|------|----------|-------|
| CPU + 8 GB RAM | Qwen3-1.7B | Q4_K_M (1.1 GB) | ~3 GB | ~10-15 tok/s |
| CPU + 16 GB RAM | Qwen3-4B | Q4_K_M (2.5 GB) | ~4.5 GB | ~8-12 tok/s |
| RTX 2080 8 GB | Qwen3-4B | Q4_K_M (2.5 GB) | ~3.5 GB VRAM | ~40-60 tok/s |

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| GRPO unstable for 4B model | Medium | High | Use Scaf-GRPO / G2RPO-A for guided training |
| Synthetic STEM data has errors | Medium | High | Hybrid verification: SymPy + ChemPy + code tests + RaR |
| GGUF export quality loss | Low | Medium | Test Q4/Q5/Q8, compare with fp16 baseline |
| Biology/Physics still weak after SFT | Medium | **High** | Balanced dataset (8-15K per domain), MMLU-STEM data, RAG fallback |
| RaR (LLM-as-judge) rewards too noisy | Medium | Medium | Use RaR only in SFT data filtering, not in GRPO; fall back to MC-only for GRPO |
| Catastrophic forgetting (math drops when adding STEM) | Medium | High | Per-domain quality gates after each stage; replay math data in every stage |
| Colab disconnects during training | Medium | Low | Checkpoint every 500 steps, resume from checkpoint |
| Socratic style lost after GRPO | Low | High | Include Socratic reward in GRPO reward function |
| STEM knowledge shallow (memorized not understood) | Medium | Medium | Include "explain why" questions, not just "calculate" |

## Dependencies

- **Unsloth** >= 2024.11 (GRPO support)
- **TRL** >= 0.12.0 (GRPOTrainer, CPOTrainer with SimPO)
- **PEFT** >= 0.13.0 (LoRA)
- **Transformers** >= 4.46.0 (Qwen3 support)
- **SymPy** (math verification)
- **ChemPy** (chemistry equation balancing & stoichiometry)
- **Pint** (physics unit-aware numeric comparison)
- **Ollama** >= 0.5.0 (GGUF serving)
- **Colab Pro+** with A100 GPU

## References

### Core Papers
1. [DeepSeekMath: GRPO for Math](https://arxiv.org/abs/2402.03300)
2. [Dr. GRPO: Removing Length Bias](https://arxiv.org/abs/2503.20783)
3. [Light-R1: Multi-stage Pipeline](https://arxiv.org/abs/2503.10460)
4. [SimPO: Simple Preference Optimization](https://arxiv.org/abs/2405.14734)
5. [Scaf-GRPO: Scaffolded RL for Small Models](https://arxiv.org/abs/2510.19807)
6. [G2RPO-A: Guided GRPO for SLMs](https://arxiv.org/abs/2508.13023)
7. [STaR: Self-Taught Reasoner](https://arxiv.org/abs/2203.14465)
8. [rStar-Math: Self-Evolution for Math](https://arxiv.org/abs/2501.04519)
9. [RL for Reasoning in Small LLMs](https://arxiv.org/abs/2503.16219) — 52 upvotes
10. [Prompt Augmentation for GRPO Stability](https://arxiv.org/abs/2602.03190)
11. [Rubrics as Rewards: RL Beyond Verifiable Domains](https://arxiv.org/abs/2507.17746) — key for STEM conceptual questions
12. [J1: LLM-as-Judge via RL](https://arxiv.org/abs/2505.10320) — verifiable rewards for non-math domains
13. [Crossing the Reward Bridge: RLVR Beyond Math/Code](https://arxiv.org/abs/2503.23829) — soft rewards from generative verifier for all STEM

### Implementation Resources
- [TRL GRPOTrainer docs](https://huggingface.co/docs/trl/grpo_trainer)
- [Unsloth GRPO notebook for Qwen3-4B](https://colab.research.google.com/github/unslothai/notebooks/blob/main/nb/Qwen3_(4B)-GRPO.ipynb)
- [Unsloth RL Guide](https://docs.unsloth.ai/get-started/reinforcement-learning-rl-guide)
- [Re-Distilling R1 (Mobius)](https://mobiusml.github.io/r1_redistill_blogpost/)

### Existing MITS Resources
- `Siesher/qwen3-1.7b-reasoning-lora` — current fine-tuned model
- `Siesher/Adaptive_Skip_thinking_Reasoning` — 7.79K training examples
- `notebooks/finetuning_glm.ipynb` — existing training notebook template
- `notebooks/synthetic_dialogs.ipynb` — dialog generation pipeline
