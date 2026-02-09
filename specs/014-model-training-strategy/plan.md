# Implementation Plan: Model Training Strategy

**Branch**: `014-model-training-strategy` | **Date**: 2026-02-07 | **Spec**: [spec.md](spec.md)

## Summary

Multi-stage training pipeline for Qwen3-4B and Qwen3-1.7B models: synthetic data generation via knowledge distillation, SFT with curriculum learning, SimPO preference alignment, GRPO reinforcement learning, and integration into MITS with auto-detection of hardware capabilities.

## Technical Context

**Training Platform**: Google Colab Pro+ (A100 80GB)
**Inference Platform**: Windows local (RTX 2080 8GB / CPU 8-16GB RAM)
**Primary Dependencies**: Unsloth, TRL >= 0.12, PEFT, Transformers >= 4.46, SymPy, ChemPy, Ollama
**Base Models**: Qwen/Qwen3-4B, Qwen/Qwen3-1.7B
**Existing Assets**: Siesher/qwen3-1.7b-reasoning-lora, Siesher/Adaptive_Skip_thinking_Reasoning

## Decision Log

| # | Decision | Rationale | Alternatives Considered |
|---|----------|-----------|------------------------|
| D1 | Qwen3-4B as primary, 1.7B as fallback | Best math/STEM benchmarks + Russian support in size class | Phi-4-mini (weak multilingual), SmolLM3 (weaker math) |
| D2 | Dr. GRPO over vanilla GRPO | Removes length bias (+37.6%), proven on math | PPO (needs critic model, 2x VRAM), DPO (offline only) |
| D3 | SimPO over DPO for preferences | No reference model needed, +6.4% over DPO | DPO (needs ref model), ORPO (less tested) |
| D4 | Knowledge distillation from DeepSeek-R1 | Proven: R1-Distill-Qwen-1.5B beats GPT-4o on math | Qwen3-235B API (expensive), manual curation (slow) |
| D5 | Curriculum learning (easy→hard) | Scaf-GRPO: +44.3% on AIME24 with scaffolding | Random ordering (baseline), hard-only (unstable) |
| D6 | Hybrid STEM verification (SymPy + ChemPy + code tests + RaR) | Each domain gets appropriate verifier; RaR for conceptual | SymPy-only (math bias), LLM-as-judge-only (noisy) |
| D7 | 4-stage pipeline (SFT→SimPO→GRPO→STaR) | Light-R1 proven pipeline, each stage additive | SFT-only (weak), GRPO-only (needs warm start) |
| D8 | Unsloth + TRL stack | 70% VRAM reduction, GRPO support, Qwen3 compatible | Raw HuggingFace (more VRAM), vLLM (inference only) |

## Constitution Check

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Socratic Pedagogy | **COMPLIANT** | Telling Rate target set to <=15% (matches Telling@10 <15%). SimPO stage explicitly trains for Socratic style. GRPO reward includes +0.1 Socratic bonus. |
| II. Multi-Agent Architecture | **JUSTIFIED DEVIATION** | Fine-tuned models operate within the existing Tutor Agent role. The multi-agent pipeline (Profiler → Planner → Tutor → Verifier) remains unchanged — the model is the LLM inside the Tutor Agent, not a replacement for the pipeline. No agent bypass occurs. |
| III. Knowledge-Grounded Responses | **JUSTIFIED DEVIATION** | RAG grounding is handled at the Orchestrator level (existing `orchestrator_service.py`), not at the model level. The trained model generates responses; the Orchestrator injects RAG context into prompts before calling the model. This separation is by design — the model should perform well with OR without RAG context. |
| IV. Hardware Constraints | **COMPLIANT** | Qwen3-4B Q4_K_M uses ~4.5 GB RAM / ~3.5 GB VRAM, well within the 6 GB VRAM limit. Qwen3-1.7B uses ~3 GB RAM. T027 includes VRAM profiling step. |
| V. Metrics-Driven Quality | **COMPLIANT** | Per-domain quality gates after every training stage. STEM-30 benchmark with per-domain breakdown. Anti-regression checks enforced. |
| VI. STEM Domain Coverage | **COMPLIANT** | Dataset balanced across 5 domains (no domain >25%, each >=12%). Per-domain evaluation gates. STEM Balance Invariants enforced at every stage. |

### Model Change Justification (Qwen3-4B vs Constitution's Qwen3-8B)

The constitution specifies "Qwen3-8B-Instruct (or equivalent MoE with <6GB VRAM)" as primary model. We select **Qwen3-4B** instead because:

1. **VRAM compliance**: Qwen3-8B Q4_K_M requires ~8 GB VRAM, **exceeding the constitution's own 6 GB VRAM limit**. Qwen3-4B Q4_K_M needs ~3.5 GB VRAM, fully compliant.
2. **Benchmark parity**: Qwen3-4B achieves 97% on MATH-500 (vs Qwen3-8B's ~98%), with only ~1% difference — negligible after fine-tuning.
3. **Fine-tuning advantage**: A fine-tuned 4B model on Socratic STEM data will outperform an untuned 8B model on our specific tasks.
4. **Target audience**: MITS targets devices with 8-16 GB RAM. Qwen3-4B fits comfortably; Qwen3-8B would struggle on 8 GB devices.

This constitutes a PATCH-level constitution update (constraint adjustment) that should be ratified after successful deployment benchmarks.

## Phases

### Phase 0: Infrastructure & Data Generation (Colab)

**Goal**: Prepare training data pipeline and verification system.

**Tasks**:
- T001: Create data generation notebook (`notebooks/generate_stem_data.ipynb`)
  - Load DeepSeek-R1-Distill-Qwen-32B (quantized) on A100
  - Prompt templates for Math, Physics, Chemistry, CS, Biology
  - Russian language, ChatML format with `<think>` tags
  - Output: raw completions in JSONL

- T002: Create hybrid STEM verification module (`training/scripts/verify_answers.py`)
  - Math: SymPy symbolic comparison
  - Physics: numeric verification with tolerance + unit check
  - Chemistry: ChemPy stoichiometry verification
  - CS: code execution sandbox with unit tests
  - Biology/Conceptual: MC exact match + RaR LLM-as-judge with rubrics
  - Domain router dispatches to correct verifier
  - Rejection sampling: filter only verified-correct

- T003: Create curriculum sorter (`training/scripts/sort_curriculum.py`)
  - Classify problems by difficulty (easy/medium/hard)
  - Based on: grade level, solution length, number of steps
  - Output: three JSONL files (easy.jsonl, medium.jsonl, hard.jsonl)

- T004: Build balanced STEM training dataset (65K+ examples)
  - Augment `Siesher/Adaptive_Skip_thinking_Reasoning` (7.79K → 20K+)
  - Translate + solve MMLU-STEM subset via teacher model
  - Generate 10K Socratic multi-turn dialogs across ALL STEM domains
  - Balance check: no single domain > 25%, each domain >= 12%

- T005: Create SimPO preference pairs dataset (all STEM)
  - 10K pairs balanced across domains (Math 2K, Physics 2K, Chemistry 1.5K, CS 1.5K, Biology 1.5K, Mixed 1.5K)
  - Format: `{"prompt": "...", "chosen": "...", "rejected": "...", "domain": "..."}`
  - Output: `training/data/preference_pairs.jsonl`

**Verification**: `len(dataset) >= 65000`, `verification_rate >= 95%`, each domain >= 12%

---

### Phase 1: SFT Fine-Tuning (Colab A100)

**Goal**: Train base Socratic tutoring capabilities.

**Tasks**:
- T006: Create Qwen3-4B SFT notebook (`notebooks/sft_qwen3_4b.ipynb`)
  - Unsloth + QLoRA (r=32, alpha=64, all-linear)
  - Curriculum: epoch 1 (easy+medium), epoch 2 (full), epoch 3 (hard weighted 2x)
  - Checkpointing every 500 steps
  - Validation split: 5% held-out

- T007: Create Qwen3-1.7B SFT notebook (`notebooks/sft_qwen3_1.7b.ipynb`)
  - Same hyperparameters as 4B
  - Can also run on RTX 2080 (batch=1, seq=1024)

- T008: Run SFT training for both models
  - Save LoRA adapters to Google Drive
  - Log training curves (loss, learning rate)
  - Evaluate on held-out validation set

- T009: Intermediate STEM-30 evaluation (per-domain gates)
  - Run 30-question STEM benchmark (6 per domain: 3 calc + 3 conceptual)
  - Per-domain scores: Math, Physics, Chemistry, CS, Biology
  - Gate: overall > 65%, each domain individually > 50%

**Verification**: val_loss decreasing, STEM-30 overall > 65%, each domain > 50%

---

### Phase 2: SimPO Preference Alignment (Colab A100)

**Goal**: Align model to prefer Socratic tutoring style over direct answers.

**Tasks**:
- T010: Create SimPO notebook (`notebooks/simpo_qwen3.ipynb`)
  - TRL CPOTrainer with `loss_type="simpo"`
  - Load SFT LoRA from Phase 1
  - Domain-balanced preference pair batches
  - Supports both 4B and 1.7B via config variable
  - LR=5e-7, beta=2.0, gamma=1.0

- T011: Run SimPO for both models
  - Save updated LoRA adapters
  - Log preference accuracy on held-out pairs

- T012: Evaluate Socratic quality + STEM accuracy post-SimPO
  - Socratic Score: % of responses with guiding questions (per domain)
  - Telling Rate: % of direct answers without questions
  - Anti-regression check: per-domain STEM scores must not drop vs Phase 1
  - Gate: Telling Rate < 15% (4B) / < 25% (1.7B), no domain regression > 5%

**Verification**: Socratic Score > 50%, Telling Rate < 15% (4B), no domain regression

---

### Phase 3: GRPO Reinforcement Learning (Colab A100)

**Goal**: Maximize STEM reasoning through RL with hybrid domain-aware verifiable rewards.

**Tasks**:
- T013: Create hybrid STEM reward module (`training/scripts/stem_rewards.py`)
  - Math: SymPy exact, Physics: numeric+tolerance, Chemistry: ChemPy, CS: code tests, MC: exact match
  - Conceptual: rubric_judge (RaR LLM-as-judge)
  - Combined: `1.0*correct + 0.2*reasoning + 0.1*socratic - 0.5*wrong`
  - Domain router dispatches to correct verifier
  - **Imports verification primitives from T002** (`training/scripts/verify_answers.py`)

- T014: Create GRPO notebook (`notebooks/grpo_qwen3_4b.ipynb`)
  - TRL GRPOTrainer + Unsloth, Dr. GRPO: `scale_rewards=False`
  - Group size G=8, max_completion=2048, LR=5e-6, KL_coeff=0.01
  - Phase 3a: verifiable-only problems; Phase 3b: add conceptual with RaR
  - Curriculum: 30-70% pass rate problems, balanced across domains
  - Load SimPO checkpoint from Phase 2

- T015: Prepare GRPO training problems (all STEM)
  - 15-20K problems with ground truth, balanced: Math 4K, Physics 4K, Chemistry 3K, CS 3K, Biology 3K
  - Curriculum ordering: easy→medium→hard within each domain
  - Output: `training/data/grpo_problems.jsonl`

- T016: Run GRPO training
  - Phase 3a: ~2 hours on A100 (verifiable only)
  - Phase 3b: +1-2 hours (add conceptual with RaR)
  - Monitor: reward curve **per domain**, KL divergence, response length
  - Early stop if KL > 0.1 or any domain's reward collapses
  - Anti-forgetting: include math replay data in every GRPO batch

- T017: Post-GRPO per-domain evaluation
  - STEM-30 benchmark with per-domain breakdown
  - MATH-100 subset (target: > 90%)
  - Gate: improvement in at least 3/5 domains, no domain drops > 10%

**Verification**: MATH-100 > 90%, STEM-30 overall > 73%, per-domain targets met

---

### Phase 4: Self-Improvement — STaR (Colab A100, Optional)

**Goal**: Further improve through iterative self-training across all STEM domains.

**Tasks**:
- T018: Create STEM STaR/ReST^EM notebook (`notebooks/star_loop.ipynb`)
  - For each iteration (2-3x):
    1. Generate 16 completions per problem (from current model)
    2. Verify via hybrid STEM verifier (T002):
       - Math/Physics/Chem calc: exact verification
       - CS: code tests
       - MC: exact match
       - Conceptual: rubric_judge (score >= 0.6)
    3. Keep correct/high-quality completions only
    4. SFT 1 epoch on verified data, domain-balanced
  - Problem set balanced across all 5 STEM domains

- T019: Run STaR iterations and evaluate
  - Run 2-3 iterations, stop when improvement < 2%
  - Final STEM-30 + MATH-100 evaluation with per-domain breakdown
  - Anti-regression: verify no domain drops between iterations

**Verification**: Measurable improvement over Phase 3 results, no domain regression

---

### Phase 5: Export & Integration into MITS

**Goal**: Deploy trained models into production MITS system.

**Tasks**:
- T020: GGUF export script (`training/scripts/export_gguf_qwen3.py`)
  - Export Q4_K_M, Q5_K_M, Q8_0 variants for both 4B and 1.7B
  - Unsloth `save_pretrained_gguf()` method
  - Verify: load GGUF, test 5 prompts per STEM domain (25 total)

- T021: Create Ollama Modelfiles
  - `models/Modelfile.mits-tutor-qwen3-4b` and `models/Modelfile.mits-tutor-qwen3-1.7b`
  - System prompt: "Ты — сократический репетитор по математике, физике, химии, информатике и биологии."
  - Test: `ollama create` + `ollama run` + questions from ALL STEM domains

- T022: Upload to HuggingFace
  - `Siesher/mits-tutor-qwen3-4b` and `Siesher/mits-tutor-qwen3-1.7b`
  - Model cards with per-domain benchmark results

- T023: Add hardware auto-detection to backend
  - `backend/app/services/hardware_detector.py`
  - Detect RAM, VRAM (if GPU), available Ollama models
  - Auto-select: 4B (16GB+), 1.7B (8GB+), GLM fallback

- T024: Update orchestrator for Qwen3 thinking tags
  - Parse `<think>...</think>` from Qwen3 responses
  - Strip thinking tokens before sending to frontend (unless debug mode)
  - Handle both GLM and Qwen3 thinking formats

- T025: Update frontend thinking display
  - `frontend/src/utils/parseThinking.ts` — support Qwen3 format
  - Collapsible thinking block in chat messages

- T026: Update model pull script
  - `scripts/pull-models.sh` — add Qwen3 models
  - Auto-detect which models to pull based on hardware

- T027: End-to-end integration test (all STEM)
  - Start MITS with each model (GLM, Qwen3-4B, Qwen3-1.7B)
  - Test all modes: chat, guided_learning, task_generator
  - Test STEM questions from each domain
  - Verify: streaming, thinking display, Socratic style, math rendering
  - **VRAM profiling**: measure actual VRAM usage per model, verify <6 GB limit
  - Measure: latency, tokens/sec, RAM usage

**Verification**: All modes working, STEM-30 score matches training evaluation, VRAM <6 GB

---

### Phase 6: Documentation & Benchmarks

**Tasks**:
- T028: Create per-domain benchmark comparison report
  - Table: GLM-4.7-Flash vs Qwen3-4B-tutor vs Qwen3-1.7B-tutor
  - Per-domain rows: Math, Physics, Chemistry, CS, Biology
  - Metrics: STEM-30 (per domain), Socratic Score, Telling Rate, latency, RAM
  - Training pipeline progression chart (base → SFT → SimPO → GRPO → STaR)
  - Charts for diploma thesis

- T029: Update project documentation
  - README.md: add Qwen3 model options, hardware requirements, STEM coverage
  - CLAUDE.md: update tech stack
  - Training reproducibility guide (Colab notebook links)

- T030: Publish training dataset
  - Upload to `Siesher/mits-stem-training-data`
  - Include: train/val/test splits, domain labels, difficulty labels
  - Per-domain statistics in dataset card

## Timeline

| Phase | Duration | Blocker | Deliverable |
|-------|----------|---------|-------------|
| Phase 0 | 3-5 days | Colab access | 50K+ verified training examples |
| Phase 1 | 1-2 days | Phase 0 | SFT LoRA adapters |
| Phase 2 | 0.5-1 day | Phase 1 | SimPO-aligned adapters |
| Phase 3 | 1-2 days | Phase 2 | GRPO-optimized adapters |
| Phase 4 | 1-2 days | Phase 3 | Self-improved adapters (optional) |
| Phase 5 | 2-3 days | Phase 3/4 | MITS with Qwen3 models |
| Phase 6 | 1 day | Phase 5 | Benchmark report + docs |
| **Total** | **~10-16 days** | | **Production-ready lightweight MITS** |

## Estimated Costs

| Item | Cost |
|------|------|
| Colab Pro+ (1 month) | ~$50 |
| DeepSeek API (data gen, if used) | ~$10-20 |
| HuggingFace storage (free tier) | $0 |
| **Total** | **~$50-70** |

## Rollback Plan

If training fails or models underperform:
1. **Fallback to SFT-only**: Skip SimPO/GRPO, use SFT model (still better than base)
2. **Fallback to 1.7B**: If 4B doesn't fit target hardware, use 1.7B with more data
3. **Keep GLM-4.7-Flash**: Existing model remains available as high-quality option
4. **Use DeepSeek-R1-Distill-Qwen-7B**: Pre-distilled model, no training needed, just GGUF export
