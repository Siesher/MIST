# Tasks: Model Training Strategy

**Feature**: `014-model-training-strategy` | **Plan**: [plan.md](plan.md) | **Generated**: 2026-02-07

## Phase 0: Data Generation & Infrastructure (Colab A100)

- [X] **T001** Create STEM data generation notebook `notebooks/generate_stem_data.ipynb`
  - Load DeepSeek-R1-Distill-Qwen-32B (4-bit) on A100
  - **Balanced** prompt templates per domain:
    - Math: 15K (algebra, calculus, geometry, number theory)
    - Physics: 12K (mechanics, thermodynamics, EM, optics)
    - Chemistry: 10K (stoichiometry, organic, inorganic, solutions)
    - CS: 10K (algorithms, data structures, complexity, code)
    - Biology: 8K (cell biology, genetics, ecology, anatomy)
  - Each domain: ~50% calculation/verifiable + ~50% conceptual/explanatory
  - Russian language, ChatML format with `<think>` tags
  - Output: `training/data/raw_stem.jsonl` with `domain` and `type` fields
  - **Depends on**: Colab A100 access

- [X] **T002** Create hybrid STEM verification module `training/scripts/verify_answers.py`
  - `extract_answer(text)` — parse final answer from `</think>` section
  - **Math**: `verify_math(answer, truth)` — SymPy symbolic comparison
  - **Physics**: `verify_physics(answer, truth, tol)` — numeric + unit check
  - **Chemistry**: `verify_chemistry(answer, truth)` — ChemPy stoichiometry + numeric
  - **CS**: `verify_code(code, test_cases)` — sandbox execution with unit tests
  - **Biology/Conceptual**: `verify_mc(answer, truth)` — MC exact match
  - **Conceptual open-ended**: `rubric_judge(completion, reference, rubric)` — LLM-as-judge with structured rubric (RaR approach)
  - Domain router: `verify(answer, truth, domain, question_type)` → dispatches to correct verifier
  - Unit tests for each verifier
  - **Depends on**: —

- [X] **T003** Create curriculum sorter `training/scripts/sort_curriculum.py`
  - Input: verified JSONL dataset
  - Classify difficulty: easy (grades 5-7), medium (8-9), hard (10-11+)
  - Heuristics: grade level, solution token count, step count
  - **Per-domain** difficulty distribution (not just overall)
  - Output: `{domain}_{difficulty}.jsonl` files
  - **Depends on**: T002

- [ ] **T004** Build balanced STEM training dataset (65K+ examples)
  - Augment `Siesher/Adaptive_Skip_thinking_Reasoning` (7.79K → 20K+)
  - Translate + solve MMLU-STEM subset via teacher model (Physics, Chemistry, Biology, CS)
  - Generate 10K Socratic multi-turn dialogs **across ALL STEM domains** (not just math)
  - Merge all sources into `training/data/combined_stem.jsonl`
  - **Balance check**: no single domain > 25% of total, each domain >= 12%
  - Each example tagged: `{domain, difficulty, type: "calc"|"conceptual", verified: bool}`
  - **Depends on**: T001, T002, T003

- [ ] **T005** Create SimPO preference pairs dataset (all STEM)
  - 10K pairs balanced across domains:
    - Math: 2K (Socratic vs Direct)
    - Physics: 2K (Socratic vs Direct + correct vs incorrect calculations)
    - Chemistry: 1.5K (correct equations vs incorrect + explanation quality)
    - CS: 1.5K (working code vs buggy + theory quality)
    - Biology: 1.5K (accurate terminology vs hallucinated)
    - Mixed: 1.5K (various quality dimensions)
  - Format: `{"prompt": "...", "chosen": "...", "rejected": "...", "domain": "..."}`
  - Output: `training/data/preference_pairs.jsonl`
  - **Depends on**: T001

- [X] **T005b** Create STEM-30 benchmark test suite `evaluation/benchmarks/stem_30.json`
  - 30 questions total: 6 per domain (3 calc + 3 conceptual)
  - Math: 3 calc (algebra, calculus, geometry) + 3 conceptual
  - Physics: 3 calc (mechanics, thermo, EM) + 3 conceptual
  - Chemistry: 3 calc (stoichiometry, molarity, equations) + 3 conceptual
  - CS: 3 code (algorithms, data structures) + 3 conceptual
  - Biology: 3 MC (genetics, ecology, cell) + 3 conceptual
  - Each question has: `ground_truth`, `domain`, `type`, `difficulty`, `verification_method`
  - Automated scoring script: `evaluation/benchmarks/run_stem_30.py`
  - **Depends on**: T002

## Phase 1: SFT Fine-Tuning (Colab A100)

- [X] **T006** Create Qwen3-4B SFT notebook `notebooks/sft_qwen3_4b.ipynb`
  - Unsloth FastLanguageModel + QLoRA (r=32, alpha=64, all-linear)
  - 4-bit NF4 quantization, gradient checkpointing
  - Curriculum: epoch 1 (easy+medium), epoch 2 (all), epoch 3 (hard 2x)
  - **Domain-balanced sampling**: each batch contains examples from ALL domains
  - SFTTrainer from TRL, max_seq_length=2048
  - Save checkpoints every 500 steps + end of each epoch
  - **Depends on**: T004

- [X] **T007** Create Qwen3-1.7B SFT notebook `notebooks/sft_qwen3_1.7b.ipynb`
  - Same pipeline as T006, adjusted batch size
  - Can also run on RTX 2080 (batch=1, seq=1024)
  - **Depends on**: T004

- [ ] **T008** Run SFT training on Colab A100
  - Train both models (4B: ~1h, 1.7B: ~30min)
  - Save LoRA adapters to Google Drive + HuggingFace
  - Log: training loss, validation loss, learning rate
  - **Depends on**: T006, T007

- [ ] **T009** Intermediate STEM-30 evaluation (per-domain gates)
  - Run **30-question** STEM benchmark (6 per domain: 3 calc + 3 conceptual)
  - Per-domain scores: Math, Physics, Chemistry, CS, Biology
  - Gate: overall > 65%, **each domain individually > 50%**
  - If any domain < 50%: increase that domain's data proportion and retrain
  - **Depends on**: T008

## Phase 2: SimPO Preference Alignment (Colab A100)

- [X] **T010** Create SimPO notebook `notebooks/simpo_qwen3.ipynb`
  - TRL CPOTrainer with `loss_type="simpo"`
  - Load SFT LoRA from Phase 1
  - Hyperparameters: LR=5e-7, beta=2.0, gamma=1.0, 1 epoch
  - **Domain-balanced** preference pair batches
  - Supports both 4B and 1.7B via config variable
  - **Depends on**: T005, T008

- [ ] **T011** Run SimPO training for both models
  - ~30 min each on A100
  - Save updated LoRA adapters
  - Log: preference accuracy on held-out pairs **per domain**
  - **Depends on**: T010

- [ ] **T012** Evaluate Socratic quality + STEM accuracy post-SimPO
  - Socratic Score: % of responses with guiding questions (per domain)
  - Telling Rate: % of direct answers without questions
  - **Anti-regression check**: per-domain STEM scores must not drop vs Phase 1
  - Gate: Telling Rate < 30%, no domain regression > 5%
  - **Depends on**: T011

## Phase 3: GRPO Reinforcement Learning (Colab A100)

- [X] **T013** Create hybrid STEM reward module `training/scripts/stem_rewards.py`
  - **Math**: `verify_with_sympy(answer, truth)` → exact
  - **Physics (calc)**: `verify_numeric(answer, truth, tol=0.02)` → numeric
  - **Chemistry (calc)**: `verify_stoichiometry(answer, truth)` via ChemPy → exact
  - **CS (code)**: `run_code_tests(code, test_cases)` → pass/fail
  - **MC questions (all domains)**: `exact_match(answer, truth)` → exact
  - **Conceptual**: `rubric_judge(completion, reference, rubric)` → LLM-as-judge (0-1 score)
  - `score_reasoning(completion)` → 0.0-1.0 (step quality)
  - `score_socratic(completion)` → 0.0-1.0 (question presence in answer)
  - Combined: `1.0*correct + 0.2*reasoning + 0.1*socratic - 0.5*wrong`
  - Domain router: auto-dispatches based on `domain` and `type` fields
  - **Imports verification primitives from T002** (`training/scripts/verify_answers.py`) — reuse `verify_math`, `verify_physics`, `verify_chemistry`, `verify_code`, `verify_mc` functions
  - Unit tests for each domain verifier
  - **Depends on**: T002

- [X] **T014** Create GRPO notebook `notebooks/grpo_qwen3_4b.ipynb`
  - TRL GRPOTrainer + Unsloth
  - Dr. GRPO: `scale_rewards=False`
  - Group size G=8, max_completion=2048
  - LR=5e-6, KL_coeff=0.01
  - **Phase 3a**: GRPO on verifiable-only problems (math calc + physics calc + chem calc + CS code + MC)
  - **Phase 3b**: Add conceptual problems with RaR rewards (if 3a stable)
  - Curriculum: start with 30-70% pass rate problems, **balanced across domains**
  - Load SimPO checkpoint from Phase 2
  - **Depends on**: T011, T013, T015

- [ ] **T015** Prepare GRPO training problems (all STEM)
  - Select 15-20K problems with known ground truth, balanced:
    - Math: 4K (all verifiable)
    - Physics: 3K calc + 1K MC
    - Chemistry: 2K calc + 1K MC
    - CS: 2K code + 1K MC
    - Biology: 2K MC + 1K rubric-verified
  - Format: `{"prompt": "...", "answer": "...", "domain": "...", "type": "calc|code|mc|conceptual"}`
  - Curriculum ordering: easy→medium→hard **within each domain**
  - Output: `training/data/grpo_problems.jsonl`
  - **Depends on**: T003, T004

- [ ] **T016** Run GRPO training
  - Phase 3a: ~2 hours on A100 (verifiable only)
  - Phase 3b: +1-2 hours (add conceptual with RaR)
  - Monitor: reward curve **per domain**, KL divergence, response length
  - Early stop if KL > 0.1 or any domain's reward collapses
  - **Anti-forgetting**: include math replay data in every GRPO batch
  - Save final LoRA adapters
  - **Depends on**: T014

- [ ] **T017** Post-GRPO per-domain evaluation
  - STEM-30 benchmark with **per-domain breakdown**:
    - Math target: >= 83% (5/6)
    - Physics target: >= 67% (4/6)
    - Chemistry target: >= 67% (4/6)
    - CS target: >= 83% (5/6)
    - Biology target: >= 67% (4/6)
  - MATH-100 subset (target: > 90%)
  - Socratic Score + Telling Rate (should maintain Phase 2 levels)
  - Compare full pipeline: base → SFT → SimPO → GRPO **per domain**
  - Gate: improvement in at least 3/5 domains, no domain drops > 10%
  - **Depends on**: T016

## Phase 4: Self-Improvement — STaR (Colab A100, Optional)

- [X] **T018** Create STEM STaR/ReST^EM notebook `notebooks/star_loop.ipynb`
  - For each iteration (2-3x):
    1. Generate 16 completions per problem (from current model)
    2. Verify via hybrid STEM verifier (T002):
       - Math/Physics/Chem calc: exact verification
       - CS: code tests
       - MC: exact match
       - Conceptual: rubric_judge (score >= 0.6)
    3. Keep correct/high-quality completions only
    4. SFT 1 epoch on verified data, **domain-balanced**
  - **Problem set balanced across all 5 STEM domains**
  - Track: accuracy per iteration **per domain**
  - **Depends on**: T016, T013

- [ ] **T019** Run STaR iterations and evaluate
  - Run 2-3 iterations
  - Stop when improvement < 2% between iterations
  - Final STEM-30 + MATH-100 evaluation with per-domain breakdown
  - **Anti-regression**: verify no domain drops between iterations
  - **Depends on**: T018

## Phase 5: Export & MITS Integration

- [X] **T020** GGUF export script `training/scripts/export_gguf_qwen3.py`
  - Export Q4_K_M, Q5_K_M, Q8_0 variants
  - Unsloth `save_pretrained_gguf()` method
  - Verify: load GGUF, test **5 prompts per STEM domain** (25 total), compare to LoRA output
  - Both 4B and 1.7B models
  - **Depends on**: T016 or T019

- [X] **T021** Create Ollama Modelfiles
  - `models/Modelfile.mits-tutor-qwen3-4b`
  - `models/Modelfile.mits-tutor-qwen3-1.7b`
  - System prompt: **"Ты — сократический репетитор по математике, физике, химии, информатике и биологии."**
  - Temperature, top_p, num_ctx
  - Test: `ollama create` + `ollama run` + questions from ALL STEM domains
  - **Depends on**: T020

- [ ] **T022** Upload to HuggingFace
  - `Siesher/mits-tutor-qwen3-4b` (LoRA adapter + GGUF files)
  - `Siesher/mits-tutor-qwen3-1.7b` (LoRA adapter + GGUF files)
  - Model cards with **per-domain** benchmark results and usage instructions
  - **Depends on**: T020

- [X] **T023** Add hardware auto-detection to backend
  - `backend/app/services/hardware_detector.py`
  - Detect: RAM, VRAM (if GPU), available Ollama models
  - Auto-select: 4B (16GB+), 1.7B (8GB+), GLM fallback
  - Config integration in `backend/app/config.py`
  - **Depends on**: —

- [X] **T024** Update orchestrator for Qwen3 thinking tags
  - Parse `<think>...</think>` from Qwen3 responses
  - Strip thinking tokens before sending to frontend (unless debug mode)
  - Handle both GLM and Qwen3 thinking formats
  - Update `backend/app/services/orchestrator_service.py`
  - **Depends on**: T021

- [X] **T025** Update frontend thinking display
  - `frontend/src/utils/parseThinking.ts` — support Qwen3 format
  - Collapsible thinking block in chat messages
  - Show thinking duration (tokens in think block)
  - **Depends on**: —

- [X] **T026** Update model pull script
  - `scripts/pull-models.sh` — add Qwen3 models
  - Auto-detect which models to pull based on hardware
  - **Depends on**: T021

- [ ] **T027** End-to-end integration test (all STEM)
  - Start MITS with each model (GLM, Qwen3-4B, Qwen3-1.7B)
  - Test all modes: chat, guided_learning, task_generator
  - Test **STEM questions from each domain** (not just math)
  - Verify: streaming, thinking display, Socratic style, math rendering
  - **VRAM profiling**: measure actual VRAM usage per model via `torch.cuda.max_memory_allocated()`, verify <6 GB (constitution IV)
  - Measure: latency, tokens/sec, RAM usage
  - **Depends on**: T021, T023, T024, T025, T026

## Phase 6: Documentation & Benchmarks

- [ ] **T028** Create per-domain benchmark comparison report
  - Table: GLM-4.7-Flash vs Qwen3-4B-tutor vs Qwen3-1.7B-tutor
  - **Per-domain rows**: Math, Physics, Chemistry, CS, Biology
  - Metrics: STEM-30 (per domain), Socratic Score, Telling Rate, latency, RAM
  - Training pipeline progression chart (base → SFT → SimPO → GRPO → STaR)
  - Charts for diploma thesis
  - **Depends on**: T027

- [ ] **T029** Update project documentation
  - README.md: add Qwen3 model options, hardware requirements, **STEM coverage**
  - CLAUDE.md: update tech stack
  - Training reproducibility guide (Colab notebook links)
  - **Depends on**: T028

- [ ] **T030** Publish training dataset
  - Upload to `Siesher/mits-stem-training-data`
  - Include: train/val/test splits, **domain labels**, difficulty labels, verification type
  - Per-domain statistics in dataset card
  - **Depends on**: T004

## Summary

| Phase | Tasks | Critical Path | Est. Time |
|-------|-------|---------------|-----------|
| 0: Data Generation | T001-T005, T005b | T001→T004 | 3-5 days |
| 1: SFT | T006-T009 | T006→T008→T009 | 1-2 days |
| 2: SimPO | T010-T012 | T010→T011→T012 | 0.5-1 day |
| 3: GRPO | T013-T017 | T014→T016→T017 | 1-2 days |
| 4: STaR (optional) | T018-T019 | T018→T019 | 1-2 days |
| 5: Integration | T020-T027 | T020→T021→T027 | 2-3 days |
| 6: Docs | T028-T030 | T028→T029 | 1 day |
| **Total** | **31 tasks** | | **~10-16 days** |

## STEM Balance Invariants

These rules MUST hold at every stage:

1. **Dataset**: No single domain > 25% of total, each domain >= 12%
2. **Evaluation**: Per-domain scores tracked separately; gate decisions per-domain
3. **Anti-regression**: No domain score may drop > 10% between consecutive stages
4. **GRPO batches**: Domain-balanced (each batch contains problems from >= 3 domains)
5. **Preference pairs**: Cover all 5 STEM domains (not just math)
6. **Socratic dialogs**: Spread across all STEM domains (not just math)
