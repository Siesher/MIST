# Tasks: GLM Model Integration

**Input**: Design documents from `/specs/002-glm-model-integration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Optional tests included for critical functionality.

**Organization**: Tasks grouped by user story (P1-P4) for independent implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Model download and environment configuration

- [x] T001 Pull GLM-4.7-Flash model via `ollama pull glm-4.7-flash`
- [x] T002 Pull DeepSeek-R1-8B fallback via `ollama pull deepseek-r1:8b`
- [x] T003 [P] Verify Ollama version >= 0.14.3 via `ollama --version`
- [x] T004 [P] Update `.env.example` with new GLM model settings

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models and configuration that all stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Add GLM model settings to `src/config.py` (MODEL_PRIMARY, GPU_LAYERS, TEMPERATURE, etc.)
- [x] T006 [P] Create `ModelConfiguration` dataclass in `src/inference/model_config.py`
- [x] T007 [P] Create `InferenceMetrics` dataclass in `src/inference/metrics.py`
- [x] T008 Add GLM and DeepSeek presets to `MODEL_PRESETS` in `src/inference/model_manager.py`
- [x] T009 Update `LLMClient` with GLM-specific sampling (temp=0.2, rep_penalty=1.0) in `src/models/llm_client.py`
- [x] T010 Add model-specific thinking mode handling for GLM in `src/models/llm_client.py`

**Checkpoint**: Foundation ready - user story implementation can begin

---

## Phase 3: User Story 1 - Higher Quality Math Explanations (Priority: P1) MVP

**Goal**: GLM model provides accurate Socratic math tutoring with GSM8K 90%+ accuracy

**Independent Test**: Submit math problems via Gradio UI and verify step-by-step hints are mathematically correct

### Implementation for User Story 1

- [x] T011 [US1] Test GLM model inference with basic math prompt in `src/models/llm_client.py`
- [x] T012 [US1] Verify Socratic prompts work with GLM (no changes expected) in `src/models/prompts.py`
- [x] T013 [US1] Test tutor agent generates correct hints with GLM in `src/agents/tutor_agent.py`
- [x] T014 [US1] Validate response quality on 10 GSM8K-style problems (manual test)
- [x] T015 [US1] Document GLM-specific behavior in comments if any adjustments needed

**Checkpoint**: User Story 1 complete - GLM provides quality math tutoring

---

## Phase 4: User Story 2 - Acceptable Response Time (Priority: P2)

**Goal**: First token < 3 seconds, generation >= 5 tokens/second with partial offload

**Independent Test**: Measure latency with timing instrumentation during tutoring session

### Implementation for User Story 2

- [ ] T016 [US2] Add timing instrumentation to `LLMClient.generate()` in `src/models/llm_client.py`
- [ ] T017 [US2] Add timing instrumentation to `LLMClient.generate_stream()` in `src/models/llm_client.py`
- [ ] T018 [US2] Implement `InferenceMetricsCollector` class in `src/inference/metrics.py`
- [ ] T019 [US2] Add metrics logging to SQLite in `src/inference/metrics.py`
- [ ] T020 [US2] Configure Ollama environment for partial offload (`OLLAMA_GPU_LAYER_COUNT=25`)
- [ ] T021 [US2] Test and validate TTFT < 3s on target hardware (RTX 2080 + Ryzen 9)
- [ ] T022 [US2] Test and validate token rate >= 5 t/s on target hardware
- [ ] T023 [US2] Add performance warning if metrics exceed thresholds in `src/inference/metrics.py`

**Checkpoint**: User Story 2 complete - Performance meets requirements

---

## Phase 5: User Story 3 - Model Switching (Priority: P3)

**Goal**: Admin can switch between GLM and DeepSeek-R1 via config or UI

**Independent Test**: Change MODEL_PRIMARY in .env and verify system uses new model

### Implementation for User Story 3

- [ ] T024 [US3] Add `get_model_by_name()` function to `src/inference/model_manager.py`
- [ ] T025 [US3] Add `switch_model()` method to `ModelManager` class in `src/inference/model_manager.py`
- [ ] T026 [US3] Implement automatic fallback on model load failure in `src/inference/model_manager.py`
- [ ] T027 [P] [US3] Add model selector dropdown to Gradio UI in `interface/gradio_app.py`
- [ ] T028 [US3] Add model info display (name, VRAM, speed) to Gradio UI in `interface/gradio_app.py`
- [ ] T029 [US3] Connect model selector to `ModelManager.switch_model()` in `interface/gradio_app.py`
- [ ] T030 [US3] Test model switching without full restart
- [ ] T031 [US3] Test automatic fallback when GLM unavailable

**Checkpoint**: User Story 3 complete - Model switching works via config and UI

---

## Phase 6: User Story 4 - Benchmark Comparison (Priority: P4)

**Goal**: Automated benchmarks validate GLM performance vs baseline models

**Independent Test**: Run benchmark script and compare accuracy percentages

### Implementation for User Story 4

- [ ] T032 [P] [US4] Create benchmark dataset (50 GSM8K-style problems) in `evaluation/data/gsm8k_sample.json`
- [ ] T033 [P] [US4] Create benchmark runner script skeleton in `evaluation/benchmark_models.py`
- [ ] T034 [US4] Implement `evaluate_model()` function in `evaluation/benchmark_models.py`
- [ ] T035 [US4] Implement `compare_models()` function in `evaluation/benchmark_models.py`
- [ ] T036 [US4] Add results output (JSON + console table) in `evaluation/benchmark_models.py`
- [ ] T037 [US4] Run benchmark: GLM vs Qwen2.5-7B (baseline)
- [ ] T038 [US4] Run benchmark: GLM vs DeepSeek-R1-8B (fallback)
- [ ] T039 [US4] Document results in `docs/MODEL_BENCHMARK_RESULTS.md`

**Checkpoint**: User Story 4 complete - Benchmark validates model selection

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases, documentation, cleanup

- [ ] T040 [P] Handle GPU memory overflow gracefully in `src/inference/model_manager.py`
- [ ] T041 [P] Handle model file corruption/missing with clear error in `src/inference/model_manager.py`
- [ ] T042 [P] Handle context overflow with truncation in `src/models/llm_client.py`
- [ ] T043 Update `docs/architecture/MODEL_SELECTION.md` with GLM rationale
- [ ] T044 Update `README.md` with new model capabilities
- [ ] T045 Run quickstart.md validation (full setup on clean system)
- [ ] T046 [P] Create test file `tests/test_glm_integration.py` with basic inference test
- [ ] T047 [P] Create test file `tests/test_model_switching.py` with fallback test
- [ ] T048 Final code review and cleanup

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
        └──────────────┴──────────────┴──────────────┘
                                │
                                ▼
                    Phase 7 (Polish)
```

### User Story Dependencies

| Story | Depends On | Can Run In Parallel With |
|-------|------------|--------------------------|
| US1 (P1) | Phase 2 only | US2, US3, US4 |
| US2 (P2) | Phase 2 only | US1, US3, US4 |
| US3 (P3) | Phase 2 only | US1, US2, US4 |
| US4 (P4) | Phase 2 only | US1, US2, US3 |

### Within Each User Story

1. Configuration/setup tasks first
2. Core implementation tasks
3. Testing/validation tasks last

### Parallel Opportunities

**Phase 1**: T003 and T004 can run in parallel with T001/T002
**Phase 2**: T006 and T007 can run in parallel (different files)
**Phase 5**: T027 can run in parallel (UI work separate from backend)
**Phase 6**: T032 and T033 can run in parallel (data vs code)
**Phase 7**: T040, T041, T042, T046, T047 all can run in parallel

---

## Parallel Example: Phase 2 Foundation

```bash
# Launch models in parallel:
Task: "Create ModelConfiguration dataclass in src/inference/model_config.py"
Task: "Create InferenceMetrics dataclass in src/inference/metrics.py"

# Then sequential (depends on models):
Task: "Add GLM and DeepSeek presets to MODEL_PRESETS"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (model downloads)
2. Complete Phase 2: Foundational (config + presets)
3. Complete Phase 3: User Story 1 (core tutoring with GLM)
4. **STOP and VALIDATE**: Test GLM tutoring quality
5. Demo if ready

**MVP delivers**: GLM-powered math tutoring with improved accuracy

### Incremental Delivery

| Milestone | Deliverable | Value |
|-----------|-------------|-------|
| MVP (US1) | GLM tutoring works | 90%+ GSM8K accuracy |
| +US2 | Performance monitoring | Latency tracking |
| +US3 | Model switching | Fallback reliability |
| +US4 | Benchmarks | Validation evidence |

### Effort Estimates

| Phase | Tasks | Complexity |
|-------|-------|------------|
| Setup | 4 | Low |
| Foundational | 6 | Medium |
| US1 | 5 | Low |
| US2 | 8 | Medium |
| US3 | 8 | Medium |
| US4 | 8 | Medium |
| Polish | 9 | Low |
| **Total** | **48** | |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Each user story independently testable
- Commit after each task or logical group
- Stop at any checkpoint to validate
- Hardware: RTX 2080 8GB + 32GB RAM + Ryzen 9 9950X
