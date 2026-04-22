# Tasks: ITS Integration

**Input**: Design documents from `/specs/001-its-integration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in spec. Tests omitted unless needed for validation.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/`, `interface/`, `training/`, `data/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, configuration, and shared data models

- [ ] T001 Create project directory structure per plan.md layout
- [ ] T002 Update requirements.txt with all dependencies (Gradio 4.x, ChromaDB, sentence-transformers, Unsloth, TRL, bitsandbytes)
- [ ] T003 [P] Create src/config.py with environment configuration (OLLAMA_HOST, VRAM limits, timeouts)
- [ ] T004 [P] Create .env.example with documented environment variables
- [ ] T005 [P] Create shared enums and types in src/models/enums.py (Discipline, Difficulty, ErrorType, TeachingStrategy, HintLevel, SessionMode)
- [ ] T006 [P] Create base data models in src/models/base.py (StudentSession, StudentProfile, Task, Hint, Misconception)
- [ ] T007 [P] Create agent output models in src/models/agent_outputs.py (ProfilerOutput, PlannerOutput, VerifierOutput, AgentTrace)
- [ ] T008 Create session and metrics models in src/models/session.py (DialogTurn, SessionMetrics, SkillMastery)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T009 Create Ollama client wrapper in src/inference/ollama_client.py with retry logic and timeout handling
- [ ] T010 [P] Create base agent interface in src/agents/base_agent.py with async process method signature
- [ ] T011 [P] Create session storage manager in src/data/session_store.py (in-memory sessions, persistence hooks)
- [ ] T012 [P] Create student profile persistence in src/data/student_store.py (JSON/SQLite backend)
- [ ] T013 Create ChromaDB vector store setup in src/knowledge/vector_store.py with embedding initialization
- [ ] T014 Create basic RAG retriever in src/knowledge/rag_retriever.py with dense search (no hybrid yet)
- [ ] T015 [P] Create math task bank loader in src/data/task_bank.py (load from data/tasks/math.jsonl)
- [ ] T016 [P] Create math hints knowledge base in data/knowledge/hints/math.jsonl (minimum 50 hints covering algebra, calculus, geometry)
- [ ] T017 [P] Create math misconceptions knowledge base in data/knowledge/misconceptions/math.jsonl (minimum 20 misconceptions)
- [ ] T018 Index knowledge base documents into ChromaDB via src/knowledge/rag_retriever.py --index

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Базовая сессия обучения математике (Priority: P1) MVP

**Goal**: Student solves math problems with Socratic tutoring through 4-agent pipeline

**Independent Test**: Launch Gradio, select algebra task, enter wrong answer, verify system asks guiding questions without revealing answer

### Core Agents (US1)

- [ ] T019 [US1] Implement ProfilerAgent in src/agents/profiler.py with 6 error types classification (CONCEPTUAL, PROCEDURAL, CARELESS, NOTATION, INCOMPLETE, MISCONCEPTION)
- [ ] T020 [US1] Implement PlannerAgent in src/agents/planner.py with 7 teaching strategies (GUIDED_DISCOVERY, SCAFFOLDED, ERROR_CORRECTION, CONCEPTUAL_REPAIR, ENCOURAGEMENT, REVIEW, DIRECT_INSTRUCTION)
- [ ] T021 [US1] Implement TutorAgent in src/agents/tutor_agent.py with Socratic response generation and RAG context injection
- [ ] T022 [US1] Implement VerifierAgent in src/agents/verifier.py with answer leak detection patterns
- [ ] T023 [US1] Implement AgentOrchestrator in src/agents/orchestrator.py coordinating Profiler → Planner → Tutor → Verifier pipeline

### Progressive Hints (US1)

- [ ] T024 [US1] Add 4-level hint progression logic in src/knowledge/hint_selector.py (CONCEPTUAL → PROCEDURAL → SPECIFIC → WORKED_EXAMPLE)
- [ ] T025 [US1] Integrate hint selector with TutorAgent for graduated hint delivery

### Gradio Interface (US1)

- [ ] T026 [US1] Create main Gradio app in interface/unified_app.py with discipline selector, task display, chat interface
- [ ] T027 [US1] Add topic and difficulty selectors to interface/unified_app.py
- [ ] T028 [US1] Implement new_task action handler in interface/unified_app.py
- [ ] T029 [US1] Implement submit_response action handler connecting to AgentOrchestrator
- [ ] T030 [US1] Implement request_hint action handler with hint level tracking
- [ ] T031 [US1] Add session state management to Gradio app (session_id, dialog_history)

### Answer Validation (US1)

- [ ] T032 [US1] Create answer validator in src/utils/answer_validator.py for math expressions (symbolic comparison)
- [ ] T033 [US1] Integrate answer validator with orchestrator for task completion detection

**Checkpoint**: User Story 1 complete - math tutoring with Socratic method functional

---

## Phase 4: User Story 2 - Сессия программирования с выполнением кода (Priority: P2)

**Goal**: Student solves coding problems with code execution in sandbox

**Independent Test**: Select sorting task, submit buggy code, verify system runs tests, shows failures, asks about logic

### Code Execution Sandbox (US2)

- [ ] T034 [P] [US2] Create secure code sandbox in src/execution/sandbox.py with subprocess isolation
- [ ] T035 [US2] Add timeout handling (30s) and resource limits to sandbox
- [ ] T036 [US2] Add dangerous operation blocking (file I/O, network, imports blacklist) to sandbox
- [ ] T037 [US2] Create test runner in src/execution/test_runner.py executing unit tests against student code

### Coding Task Bank (US2)

- [ ] T038 [P] [US2] Create coding task bank loader in src/data/algo_task_bank.py
- [ ] T039 [P] [US2] Create coding tasks data file in data/tasks/coding.jsonl (minimum 30 algorithm tasks with test cases)
- [ ] T040 [P] [US2] Create coding hints knowledge base in data/knowledge/hints/coding.jsonl (minimum 30 hints for algorithms, data structures)

### Coding-Specific Agents (US2)

- [ ] T041 [US2] Extend ProfilerAgent to analyze code execution results and detect logic errors
- [ ] T042 [US2] Extend TutorAgent prompts for code-specific Socratic questions (complexity, edge cases)
- [ ] T043 [US2] Add code efficiency analysis to VerifierAgent (detect O(n^2) when O(n) possible)

### Gradio Coding Interface (US2)

- [ ] T044 [US2] Add code editor component to interface/unified_app.py (Monaco/CodeMirror style)
- [ ] T045 [US2] Add conditional visibility for code editor (show only when discipline=CODING)
- [ ] T046 [US2] Integrate code submission with sandbox execution and test results display

**Checkpoint**: User Story 2 complete - coding tutoring with code execution functional

---

## Phase 5: User Story 3 - Диагностика и адаптивное обучение (Priority: P3)

**Goal**: System tracks student knowledge, detects misconceptions, adapts difficulty

**Independent Test**: Complete 10 tasks, verify system identifies error patterns and adjusts task difficulty

### Bayesian Knowledge Tracing (US3)

- [ ] T047 [P] [US3] Implement BKT algorithm in src/knowledge/knowledge_tracing.py with 4 parameters (p_L0, p_T, p_S, p_G)
- [ ] T048 [US3] Add mastery update logic on correct/incorrect attempts
- [ ] T049 [US3] Add mastery threshold check (p_mastery >= 0.85 for skill completion)

### Skill Graph (US3)

- [ ] T050 [P] [US3] Create skill dependency graph in data/knowledge/skill_graph.json (prerequisite edges)
- [ ] T051 [US3] Implement skill graph traversal for next-skill recommendation in src/knowledge/skill_recommender.py

### Adaptive Task Selection (US3)

- [ ] T052 [US3] Create adaptive task selector in src/data/task_selector.py based on skill mastery and difficulty
- [ ] T053 [US3] Integrate task selector with get_next_task orchestrator method

### Misconception Detection Enhancement (US3)

- [ ] T054 [US3] Enhance ProfilerAgent with pattern-based misconception detection from knowledge base
- [ ] T055 [US3] Add misconception history tracking to StudentProfile
- [ ] T056 [US3] Create targeted remediation task selection when misconception detected

### Adaptive Strategy Selection (US3)

- [ ] T057 [US3] Enhance PlannerAgent to consider student confidence level and misconception history
- [ ] T058 [US3] Implement ENCOURAGEMENT strategy for low-confidence students

### Progress Display (US3)

- [ ] T059 [US3] Add skill mastery progress panel to interface/unified_app.py
- [ ] T060 [US3] Add session statistics display (turns, hints used, time spent)

**Checkpoint**: User Story 3 complete - adaptive learning with knowledge tracing functional

---

## Phase 6: User Story 4 - Мультидисциплинарная поддержка STEM (Priority: P4)

**Goal**: Extend to all 5 STEM disciplines with discipline-specific knowledge bases

**Independent Test**: Switch between disciplines, solve one task in each, verify relevant hints

### Physics Support (US4)

- [ ] T061 [P] [US4] Create physics task bank in data/tasks/physics.jsonl (minimum 20 tasks)
- [ ] T062 [P] [US4] Create physics hints in data/knowledge/hints/physics.jsonl (minimum 30 hints)
- [ ] T063 [P] [US4] Create physics misconceptions in data/knowledge/misconceptions/physics.jsonl

### Chemistry Support (US4)

- [ ] T064 [P] [US4] Create chemistry task bank in data/tasks/chemistry.jsonl (minimum 20 tasks)
- [ ] T065 [P] [US4] Create chemistry hints in data/knowledge/hints/chemistry.jsonl (minimum 30 hints)
- [ ] T066 [P] [US4] Create chemistry misconceptions in data/knowledge/misconceptions/chemistry.jsonl

### Biology Support (US4)

- [ ] T067 [P] [US4] Create biology task bank in data/tasks/biology.jsonl (minimum 20 tasks)
- [ ] T068 [P] [US4] Create biology hints in data/knowledge/hints/biology.jsonl (minimum 30 hints)
- [ ] T069 [P] [US4] Create biology misconceptions in data/knowledge/misconceptions/biology.jsonl

### Discipline-Specific Prompting (US4)

- [ ] T070 [US4] Create discipline-specific prompt templates in src/agents/prompts/ directory
- [ ] T071 [US4] Update TutorAgent to load discipline-appropriate prompts and terminology
- [ ] T072 [US4] Add discipline-specific answer validators (chemistry equations, biology terms)

### Cross-Discipline Profiles (US4)

- [ ] T073 [US4] Extend StudentProfile to track per-discipline skill masteries
- [ ] T074 [US4] Update Gradio interface to show discipline-specific progress

### Knowledge Base Indexing (US4)

- [ ] T075 [US4] Re-index all discipline knowledge bases into ChromaDB with discipline metadata

**Checkpoint**: User Story 4 complete - all 5 STEM disciplines functional

---

## Phase 7: Quality & Training Infrastructure

**Purpose**: Fine-tuning pipeline, metrics, and evaluation (supports Success@10 >60%, Telling@10 <15%)

### Metrics Logging (Quality)

- [ ] T076 [P] Create metrics logger in src/logging/metrics_logger.py tracking Success@10, Telling@10, Hint Efficiency
- [ ] T077 Add latency tracking to AgentOrchestrator for <5s p95 monitoring
- [ ] T078 Create session analytics aggregator for quality dashboard

### Hybrid RAG Enhancement (Quality)

- [ ] T079 Add BM25 search component to src/knowledge/rag_retriever.py
- [ ] T080 Implement RRF fusion (k=60) combining BM25 and dense results
- [ ] T081 Add optional cross-encoder reranking for high-stakes retrieval

### Training Data Generation (Quality)

- [ ] T082 [P] Create Cerebras dialog generator in training/scripts/cerebras_dialog_generator.py
- [ ] T083 [P] Create dialog quality filter in training/scripts/quality_filter.py (no direct answers, has questions, proper structure)
- [ ] T084 Generate 10K synthetic Socratic dialogs across math and coding disciplines

### QLoRA Fine-tuning (Quality)

- [ ] T085 [P] Create QLoRA training config in training/configs/qlora_rtx2080.yaml (r=16, alpha=32, lr=2e-4)
- [ ] T086 Create QLoRA training script in training/scripts/train_qlora.py with Unsloth
- [ ] T087 Create Colab notebook for L4/A100 training at training/notebooks/train_colab.ipynb

### Evaluation Framework (Quality)

- [ ] T088 [P] Create evaluation script in evaluation/evaluate_model.py computing Success@10, Telling@10
- [ ] T089 Create evaluation test set in data/evaluation/test_dialogs.jsonl (500 held-out samples)
- [ ] T090 Run baseline evaluation and document results

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Error handling, edge cases, documentation

### Error Handling & Edge Cases

- [ ] T091 Add Ollama connection failure handling with graceful degradation message
- [ ] T092 Add empty/invalid input validation in orchestrator
- [ ] T093 Add code execution timeout handling with user-friendly message
- [ ] T094 Add "give me the answer" request detection and refusal in VerifierAgent
- [ ] T095 Add missing knowledge base fallback (generic Socratic prompts when no specific hints)
- [ ] T096 Add VRAM monitoring and context truncation for long dialogs

### Session Management

- [ ] T097 Add session persistence to disk for crash recovery
- [ ] T098 Add session timeout handling (8-hour max per constitution)
- [ ] T099 Add turn limit warning at 20 turns and enforcement at 50

### Documentation

- [ ] T100 Update README.md with quickstart instructions
- [ ] T101 Create docs/architecture/MODEL_SELECTION.md documenting Qwen2.5-7B choice
- [ ] T102 Run quickstart.md validation end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)         → No dependencies
Phase 2 (Foundational)  → Depends on Phase 1
Phase 3 (US1 - Math)    → Depends on Phase 2 ⭐ MVP
Phase 4 (US2 - Coding)  → Depends on Phase 2 (can parallel with US1)
Phase 5 (US3 - Adaptive)→ Depends on US1 complete
Phase 6 (US4 - STEM)    → Depends on US1 complete
Phase 7 (Quality)       → Depends on US1+US2 complete
Phase 8 (Polish)        → Depends on all user stories
```

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|------------|-------------------|
| US1 (Math) | Foundational only | US2 |
| US2 (Coding) | Foundational only | US1 |
| US3 (Adaptive) | US1 complete | US4 |
| US4 (STEM) | US1 complete | US3 |

### Within Each User Story

1. Core infrastructure/models (if new)
2. Agent implementations/extensions
3. Knowledge base content
4. Gradio interface additions
5. Integration and validation

---

## Parallel Opportunities

### Phase 1 (Setup) - All [P] tasks parallel

```
T003, T004, T005, T006, T007 can run simultaneously
```

### Phase 2 (Foundational) - Multiple parallel groups

```
Group A: T010, T011, T012 (storage/agents base)
Group B: T015, T016, T017 (knowledge content)
Then: T013 → T014 → T018 (vector store pipeline)
```

### Phase 3 (US1) - Agents parallel, then interface

```
Group A: T019, T020, T021, T022 (all 4 agents parallel)
Then: T023 (orchestrator combines them)
Then: T026-T031 (interface sequential)
```

### Phase 4 (US2) - Content parallel with sandbox

```
Group A: T034-T037 (sandbox pipeline)
Group B: T038, T039, T040 (content parallel)
Then: T041-T046 (integration)
```

### Phase 6 (US4) - All disciplines parallel

```
T061-T063 (Physics), T064-T066 (Chemistry), T067-T069 (Biology)
All 9 tasks can run in parallel
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T008)
2. Complete Phase 2: Foundational (T009-T018)
3. Complete Phase 3: User Story 1 (T019-T033)
4. **STOP and VALIDATE**: Test math tutoring independently
5. Deploy/demo if ready - this is a functional MVP

### Incremental Delivery

| Milestone | User Stories | Value Delivered |
|-----------|--------------|-----------------|
| MVP | US1 | Math tutoring with Socratic method |
| v0.2 | US1+US2 | Add coding problems with execution |
| v0.3 | US1+US2+US3 | Adaptive difficulty, knowledge tracking |
| v1.0 | All | Full 5-discipline STEM tutor |

### Estimated Task Counts

| Phase | Tasks | Parallel Opportunities |
|-------|-------|----------------------|
| Setup | 8 | 5 tasks parallel |
| Foundational | 10 | 6 tasks parallel |
| US1 (Math) | 15 | 4 agents parallel |
| US2 (Coding) | 13 | 6 content tasks parallel |
| US3 (Adaptive) | 14 | 3 BKT tasks parallel |
| US4 (STEM) | 15 | 9 disciplines parallel |
| Quality | 15 | 5 tasks parallel |
| Polish | 12 | Limited parallelism |
| **Total** | **102** | |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- VRAM constraint (<6GB) must be validated at each phase
- Constitution compliance verified at Phase 3 checkpoint (Telling@10 <15%)
