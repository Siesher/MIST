# Tasks: GLM STEM Pruning

**Input**: Design documents from `/specs/003-glm-math-pruning/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Optional tests included for critical validation tasks.

**Organization**: Tasks grouped by user story (P1-P4) for independent implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project structure and dependencies

- [x] T001 Create directory structure per plan.md (`training/`, `training/prompts/`, `training/calibration_data/`, `notebooks/`, `evaluation/`, `evaluation/data/`, `models/glm-stem-pruned/`)
- [x] T002 [P] Install Python dependencies: `cerebras-cloud-sdk`, `openai`, `python-dotenv`, `jsonschema`, `tqdm`
- [x] T003 [P] Verify Cerebras API keys in `.env` (CEREBRAS_API_KEY_1..10) are valid
- [x] T004 [P] Create `.gitignore` entries for `training/calibration_data/`, `models/*.gguf`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core utilities and schemas that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Create Cerebras API client wrapper with key rotation in `training/cerebras_client.py`
- [x] T006 [P] Create dataset validation module in `training/validate_dataset.py` (uses `contracts/calibration-dataset-schema.json`)
- [x] T007 [P] Create domain prompt base templates structure in `training/prompts/base_template.py`

**Checkpoint**: Foundation ready - user story implementation can begin

---

## Phase 3: User Story 1 - Multi-Domain Model Generation (Priority: P1) MVP

**Goal**: Generate calibration dataset via Cerebras API and run REAP pruning on A100

**Independent Test**: Run dataset generation locally, then execute Colab notebook with dataset to produce pruned model checkpoint

### Implementation for User Story 1

**Dataset Generation (Local)**

- [x] T008 [P] [US1] Create code domain prompts in `training/prompts/code_prompts.json` (40 prompt templates for Python, algorithms, debugging, data structures, OOP)
- [x] T009 [P] [US1] Create math domain prompts in `training/prompts/math_prompts.json` (40 prompt templates for algebra, calculus, statistics, probability, linear algebra)
- [x] T010 [P] [US1] Create physics domain prompts in `training/prompts/physics_prompts.json` (30 prompt templates for mechanics, thermodynamics, electromagnetism, waves)
- [x] T011 [P] [US1] Create chemistry domain prompts in `training/prompts/chemistry_prompts.json` (30 prompt templates for organic, inorganic, biochemistry, stoichiometry)
- [x] T012 [P] [US1] Create biology domain prompts in `training/prompts/biology_prompts.json` (30 prompt templates for molecular, genetics, ecology, anatomy)
- [x] T013 [P] [US1] Create socratic domain prompts in `training/prompts/socratic_prompts.json` (30 prompt templates for hints, guided questions, misconception handling)
- [x] T014 [US1] Implement main generation script with key rotation in `training/generate_calibration.py`
- [x] T015 [US1] Add checkpoint/resume support to `training/generate_calibration.py`
- [x] T016 [US1] Add progress tracking and ETA display to `training/generate_calibration.py`
- [ ] T017 [US1] Run dataset generation: `python training/generate_calibration.py --num-examples 1000`
- [ ] T018 [US1] Validate generated dataset against schema in `contracts/calibration-dataset-schema.json`
- [ ] T019 [US1] Verify domain distribution is balanced (±5% of targets)

**REAP Pruning (Colab)**

- [x] T020 [US1] Create Colab notebook skeleton in `notebooks/glm_stem_pruning.ipynb` with sections: Setup, Dataset, Pruning, Validation, Export
- [x] T021 [US1] Add Drive mounting and checkpoint cells to `notebooks/glm_stem_pruning.ipynb`
- [x] T022 [US1] Add REAP repository clone and setup cells to `notebooks/glm_stem_pruning.ipynb`
- [x] T023 [US1] Add GLM-4.7-Flash model download cell to `notebooks/glm_stem_pruning.ipynb`
- [x] T024 [US1] Add REAP pruning execution cell (35% pruning rate) to `notebooks/glm_stem_pruning.ipynb`
- [x] T025 [US1] Add quick validation cell (10 samples per domain) to `notebooks/glm_stem_pruning.ipynb`
- [x] T026 [US1] Add model export to Drive cell to `notebooks/glm_stem_pruning.ipynb`
- [ ] T027 [US1] Execute notebook on A100 and verify pruned model is created

**Checkpoint**: User Story 1 complete - Pruned model checkpoint exists on Google Drive

---

## Phase 4: User Story 2 - GGUF Conversion for Local Deployment (Priority: P2)

**Goal**: Convert pruned HuggingFace model to GGUF and register with Ollama

**Independent Test**: Run `ollama run glm-stem-pruned "2+2=?"` and verify response

### Implementation for User Story 2

- [x] T028 [US2] Add llama.cpp clone and build cells to `notebooks/glm_stem_pruning.ipynb`
- [x] T029 [US2] Add GGUF conversion cell (FP16 first) to `notebooks/glm_stem_pruning.ipynb`
- [x] T030 [US2] Add Q4_K_M quantization cell to `notebooks/glm_stem_pruning.ipynb`
- [x] T031 [US2] Add GGUF export to Drive cell to `notebooks/glm_stem_pruning.ipynb`
- [ ] T032 [US2] Download GGUF file from Drive to local machine `models/glm-stem-pruned/`
- [x] T033 [US2] Create Ollama Modelfile in `models/glm-stem-pruned/Modelfile` with GLM-specific parameters
- [x] T034 [US2] Create model README in `models/glm-stem-pruned/README.md` with model card info
- [ ] T035 [US2] Register model with Ollama: `ollama create glm-stem-pruned -f Modelfile`
- [ ] T036 [US2] Verify model loads and responds: `ollama run glm-stem-pruned "Solve: 2x + 3 = 7"`
- [ ] T037 [US2] Measure TTFT and token rate on RTX 2080, verify targets (TTFT < 3s, >= 5 t/s)

**Checkpoint**: User Story 2 complete - Model available in Ollama with acceptable performance

---

## Phase 5: User Story 3 - Multi-Domain Quality Validation (Priority: P3)

**Goal**: Validate pruned model quality across all STEM domains vs baseline

**Independent Test**: Run benchmark script and verify all domains show >= 95% retention

### Implementation for User Story 3

- [ ] T038 [P] [US3] Create validation sample files in `evaluation/data/validation_samples/` (50 samples per benchmark)
- [x] T039 [US3] Implement benchmark runner skeleton in `evaluation/benchmark_models.py`
- [x] T040 [US3] Add GSM8K evaluation function to `evaluation/benchmark_models.py`
- [x] T041 [US3] Add HumanEval evaluation function to `evaluation/benchmark_models.py`
- [x] T042 [US3] Add SciQ evaluation function to `evaluation/benchmark_models.py`
- [x] T043 [US3] Add MMLU-STEM evaluation function to `evaluation/benchmark_models.py`
- [x] T044 [US3] Add model comparison and retention rate calculation to `evaluation/benchmark_models.py`
- [x] T045 [US3] Add results output (JSON + console table) to `evaluation/benchmark_models.py`
- [ ] T046 [US3] Run benchmark: `glm-stem-pruned` vs `glm-4.7-flash` baseline
- [ ] T047 [US3] Verify all domains show >= 95% retention rate
- [ ] T048 [US3] Create benchmark results documentation in `docs/MODEL_BENCHMARK_RESULTS.md`

**Checkpoint**: User Story 3 complete - Quality validated across all domains

---

## Phase 6: User Story 4 - Reproducible Colab Notebook (Priority: P4)

**Goal**: Ensure notebook is fully documented and reproducible

**Independent Test**: Open notebook in fresh Colab, run all cells, verify model is produced

### Implementation for User Story 4

- [ ] T049 [US4] Add comprehensive markdown documentation to each notebook section
- [ ] T050 [US4] Add error handling and recovery instructions to notebook cells
- [ ] T051 [US4] Add compute unit tracking cell to estimate remaining budget
- [ ] T052 [US4] Add environment verification cell (A100 check, Drive space, dependencies)
- [ ] T053 [US4] Test notebook from scratch on fresh Colab session with A100
- [ ] T054 [US4] Document any issues/fixes discovered during fresh run

**Checkpoint**: User Story 4 complete - Notebook is fully reproducible

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, edge cases, integration

- [ ] T055 [P] Handle Cerebras API rate limit gracefully with backoff in `training/cerebras_client.py`
- [ ] T056 [P] Handle partial dataset generation (resume from checkpoint) in `training/generate_calibration.py`
- [ ] T057 [P] Add GGUF conversion error handling to notebook (architecture changes)
- [ ] T058 Update `src/config.py` to use `glm-stem-pruned` as MODEL_PRIMARY option
- [ ] T059 Update `README.md` with GLM STEM pruning capabilities
- [ ] T060 Run quickstart.md validation (full setup on clean system)
- [ ] T061 Final code review and cleanup

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ─────────────────────────────────────► No dependencies
        │
        ▼
Phase 2 (Foundational) ──────────────────────────────► Blocks all user stories
        │
        ├──────────────┬──────────────┬──────────────┐
        ▼              ▼              ▼              ▼
Phase 3 (US1)    Phase 4 (US2)   Phase 5 (US3)   Phase 6 (US4)
   P1 MVP           P2              P3              P4
        │              │              │              │
        │              │              │              │
        ▼──────────────┘              │              │
     US2 needs US1 output             │              │
                       │              │              │
                       ▼──────────────┘              │
                    US3 needs US2 model              │
                                      │              │
                                      └──────────────┘
                                │
                                ▼
                    Phase 7 (Polish)
```

### User Story Dependencies

| Story | Depends On | Can Run In Parallel With |
|-------|------------|--------------------------|
| US1 (P1) | Phase 2 only | None (MVP) |
| US2 (P2) | US1 (needs pruned model) | None |
| US3 (P3) | US2 (needs Ollama model) | None |
| US4 (P4) | US1-US3 complete | None |

**Note**: Unlike typical web features, this ML pipeline has sequential dependencies: Dataset → Pruning → Conversion → Validation

### Within Each User Story

1. Prompt templates first (parallelizable)
2. Core scripts/cells
3. Execution and validation last

### Parallel Opportunities

**Phase 1**: T002, T003, T004 can run in parallel
**Phase 2**: T006, T007 can run in parallel
**Phase 3 (US1)**: T008-T013 (all prompt files) can run in parallel
**Phase 5 (US3)**: T038 can run in parallel with T039-T045
**Phase 7**: T055, T056, T057 can run in parallel

---

## Parallel Example: User Story 1 Prompt Generation

```bash
# Launch all prompt template tasks in parallel:
Task: "Create code domain prompts in training/prompts/code_prompts.json"
Task: "Create math domain prompts in training/prompts/math_prompts.json"
Task: "Create physics domain prompts in training/prompts/physics_prompts.json"
Task: "Create chemistry domain prompts in training/prompts/chemistry_prompts.json"
Task: "Create biology domain prompts in training/prompts/biology_prompts.json"
Task: "Create socratic domain prompts in training/prompts/socratic_prompts.json"

# Then sequential (depends on prompts):
Task: "Implement main generation script in training/generate_calibration.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (dataset + pruning)
4. **STOP and VALIDATE**: Verify pruned model checkpoint exists on Drive
5. Continue to US2 for local deployment

**MVP delivers**: Pruned GLM model optimized for STEM tutoring

### Incremental Delivery

| Milestone | Deliverable | Value |
|-----------|-------------|-------|
| MVP (US1) | Pruned model on Drive | Core asset created |
| +US2 | GGUF in Ollama | Local deployment ready |
| +US3 | Benchmark results | Quality validated |
| +US4 | Reproducible notebook | Maintainable pipeline |

### Effort Estimates

| Phase | Tasks | Complexity |
|-------|-------|------------|
| Setup | 4 | Low |
| Foundational | 3 | Medium |
| US1 | 20 | High |
| US2 | 10 | Medium |
| US3 | 11 | Medium |
| US4 | 6 | Low |
| Polish | 7 | Low |
| **Total** | **61** | |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- This is a sequential ML pipeline (not parallel web features)
- Commit after each task or logical group
- Stop at any checkpoint to validate
- Hardware: A100 40GB (Colab) → RTX 2080 8GB (local)
- API Keys: 10 Cerebras keys in `.env` for 300 req/min effective rate
