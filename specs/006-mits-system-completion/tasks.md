# Tasks: MITS System Completion

**Input**: Design documents from `/specs/006-mits-system-completion/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root (per plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project structure verification and new module initialization

- [x] T001 Verify existing project structure matches plan.md layout
- [x] T002 [P] Create src/memory/ directory for dual-memory system
- [x] T003 [P] Add new dependencies to requirements.txt (torch for DKT if not present)
- [x] T004 [P] Create data/knowledge/hints/ directory structure
- [x] T005 [P] Create data/knowledge/misconceptions/ directory structure
- [x] T006 Update src/config.py with new DKT and memory configuration parameters

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T007 Extend src/data/schemas.py with CognitiveLoad, TopicMastery, SessionSummary models from data-model.md
- [x] T008 [P] Create database migration script for SQLite schema in scripts/init_db.py
- [x] T009 [P] Add Topic entity with prerequisites to src/data/schemas.py
- [x] T010 Create src/memory/__init__.py with module exports
- [x] T011 Add ISessionMemory and IStudentMemory interfaces to src/memory/interfaces.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Adaptive Socratic Tutoring (Priority: P1) 🎯 MVP

**Goal**: Student completes tutoring session with guided Socratic questions, not direct answers

**Independent Test**: Run a full tutoring dialogue and verify tutor asks questions instead of giving answers

### Implementation for User Story 1

- [x] T012 [US1] Enhance src/agents/tutor_agent.py with improved Socratic prompts based on SocraticLLM research
- [x] T013 [US1] Add progressive scaffolding levels (conceptual → procedural → specific) to src/agents/tutor_agent.py
- [x] T014 [US1] Update src/agents/verifier.py with stricter answer-leak detection checks
- [x] T015 [US1] Add TutorMove enum with SCAFFOLDING, PROBLEMATIZE, RECTIFY, ENCOURAGE, HINT values to src/data/schemas.py
- [x] T016 [US1] Implement frustration detection in src/agents/profiler.py based on consecutive errors
- [x] T017 [US1] Add Socratic question templates to src/models/prompts.py for algebra, calculus, geometry

**Checkpoint**: User Story 1 complete - Socratic tutoring functional

---

## Phase 4: User Story 2 - Knowledge State Tracking (Priority: P1)

**Goal**: System tracks and updates student mastery across topics, influencing task selection

**Independent Test**: Student solves problems; verify mastery values update and affect next task difficulty

### Implementation for User Story 2

- [x] T018 [US2] Implement DKT model class in src/models/dkt_model.py using lightweight LSTM
- [x] T019 [US2] Extend src/models/knowledge_tracing.py with BKT→DKT transition logic (threshold: 10 responses)
- [x] T020 [US2] Add knowledge decay model to src/models/knowledge_tracing.py (Ebbinghaus forgetting curve)
- [x] T021 [US2] Create CognitiveLoad estimation class in src/models/cognitive_load.py
- [x] T022 [US2] Update src/agents/profiler.py to use enhanced knowledge tracer
- [x] T023 [US2] Add topic mastery visualization data to session response in src/agents/orchestrator.py
- [x] T024 [US2] Implement adaptive difficulty selection in src/agents/task_generator.py based on knowledge state

**Checkpoint**: User Story 2 complete - Knowledge tracking functional ✓

---

## Phase 5: User Story 3 - RAG-Enhanced Hint Delivery (Priority: P2)

**Goal**: Hints retrieved from knowledge base are relevant and grounded, reducing hallucinations

**Independent Test**: Request hints on specific topics; verify retrieved content matches problem context

### Implementation for User Story 3

- [x] T025 [P] [US3] Create hint data schema in data/knowledge/hints/algebra.json with 20+ algebra hints
- [x] T026 [P] [US3] Create hint data schema in data/knowledge/hints/calculus.json with 15+ calculus hints
- [x] T027 [P] [US3] Create misconception data in data/knowledge/misconceptions/common_errors.json
- [x] T028 [US3] Enhance src/knowledge/rag_retriever.py with context-aware re-ranking based on student knowledge state
- [x] T029 [US3] Add hint progression tracking (conceptual→procedural→specific) to src/knowledge/rag_retriever.py
- [x] T030 [US3] Implement fallback mechanism in src/knowledge/rag_retriever.py when RAG score < threshold
- [x] T031 [US3] Add embedding pre-computation script in scripts/precompute_embeddings.py

**Checkpoint**: User Story 3 complete - RAG hint delivery functional ✓✓

---

## Phase 6: User Story 4 - Cognitive Load Management (Priority: P2)

**Goal**: System detects cognitive overload and adjusts difficulty automatically

**Independent Test**: Simulate high cognitive load signals; verify system offers simpler tasks

### Implementation for User Story 4

- [x] T032 [US4] Implement multi-signal cognitive load estimation in src/models/cognitive_load.py
- [x] T033 [US4] Add response time tracking to session context in src/memory/session_memory.py
- [x] T034 [US4] Update src/agents/planner.py to incorporate cognitive load signals in strategy selection
- [x] T035 [US4] Add difficulty adjustment logic to src/agents/task_generator.py based on cognitive load
- [x] T036 [US4] Implement break suggestion feature in src/agents/tutor_agent.py when overload detected

**Checkpoint**: User Story 4 complete - Cognitive load management functional ✓

---

## Phase 7: User Story 5 - Multi-Agent Orchestration (Priority: P2)

**Goal**: Agents communicate correctly through orchestrator producing coherent behavior

**Independent Test**: Trace agent pipeline; verify correct routing and response generation

### Implementation for User Story 5

- [x] T037 [US5] Update src/agents/orchestrator.py with improved agent routing based on query type
- [x] T038 [US5] Add pipeline tracing to src/agents/orchestrator.py for debugging
- [x] T039 [US5] Implement graceful degradation in src/agents/orchestrator.py when agents fail
- [x] T040 [US5] Add agent health check mechanism to src/agents/base_agent.py
- [x] T041 [US5] Update agent interfaces per contracts/agent-interfaces.md

**Checkpoint**: User Story 5 complete - Multi-agent orchestration functional ✓

---

## Phase 8: User Story 6 - Dual-Memory Personalization (Priority: P3)

**Goal**: System maintains session and long-term memory for personalized experience

**Independent Test**: End session, start new one; verify previous context and preferences restored

### Implementation for User Story 6

- [x] T042 [P] [US6] Implement SessionMemory class in src/memory/session_memory.py per contracts/memory-interfaces.md
- [x] T043 [P] [US6] Implement StudentMemory class in src/memory/student_memory.py with SQLite persistence
- [x] T044 [US6] Create MemoryManager class in src/memory/manager.py to coordinate both memories
- [x] T045 [US6] Integrate MemoryManager with src/agents/orchestrator.py for context injection
- [x] T046 [US6] Add knowledge decay application on session start in src/memory/student_memory.py
- [x] T047 [US6] Implement preference learning from session interactions in src/memory/student_memory.py

**Checkpoint**: User Story 6 complete - Dual-memory personalization functional ✓

---

## Phase 9: User Story 7 - Russian Language Support (Priority: P3)

**Goal**: Full Russian language support with proper mathematical terminology

**Independent Test**: Conduct session in Russian; verify proper terminology and notation

### Implementation for User Story 7

- [x] T048 [US7] Add Russian mathematical notation mappings to src/models/prompts.py (tg, ctg, lg)
- [x] T049 [US7] Create Russian hint templates in data/knowledge/hints/russian_templates.json
- [x] T050 [US7] Add language detection utility to src/utils/language_detector.py
- [x] T051 [US7] Update src/agents/tutor_agent.py to use detected language for responses
- [x] T052 [US7] Add Russian terminology glossary to data/knowledge/glossary_ru.json

**Checkpoint**: User Story 7 complete - Russian language support functional ✓

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements affecting multiple user stories

- [x] T053 [P] Update quickstart.md with final setup instructions
- [x] T054 [P] Add integration test for full tutoring session in tests/test_integration.py
- [x] T055 [P] Create evaluation script for Success Criteria metrics in evaluation/run_evaluation.py
- [x] T056 Performance optimization: add caching for frequent RAG queries in src/inference/cache.py
- [x] T057 Add error handling for edge cases (empty input, Ollama unavailable) across all agents
- [x] T058 Update interface/unified_app.py with memory and cognitive load displays
- [x] T059 Run quickstart.md validation end-to-end

**Checkpoint**: Phase 10 complete - System fully configured and validated!

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3-9)**: All depend on Foundational completion
  - US1 (Socratic) and US2 (Knowledge Tracking) can run in parallel (both P1)
  - US3 (RAG) can start after US2 (needs knowledge state for re-ranking)
  - US4 (Cognitive Load) can start after US2 (needs KT infrastructure)
  - US5 (Orchestration) can start after US1 (needs enhanced agents)
  - US6 (Memory) can start after US2 (needs knowledge state persistence)
  - US7 (Russian) can start any time after Foundational
- **Polish (Phase 10)**: Depends on all user stories complete

### User Story Dependencies

```
Phase 2 (Foundational)
        │
        ├───────┬───────┐
        ▼       ▼       ▼
      US1     US2     US7
   (Socratic) (KT)  (Russian)
        │       │
        ▼       ├───────┬───────┐
      US5       ▼       ▼       ▼
   (Orchestr)  US3     US4     US6
               (RAG) (CogLoad) (Memory)
        │       │       │       │
        └───────┴───────┴───────┘
                    │
                    ▼
             Phase 10 (Polish)
```

### Parallel Opportunities

**Phase 1 (Setup)**:
```bash
# Run in parallel:
T002 Create src/memory/ directory
T003 Add dependencies to requirements.txt
T004 Create data/knowledge/hints/ directory
T005 Create data/knowledge/misconceptions/ directory
```

**Phase 2 (Foundational)**:
```bash
# Run in parallel:
T008 Create database migration script
T009 Add Topic entity to schemas
```

**Phase 3 (US1) + Phase 4 (US2)**:
```bash
# Can run both user stories in parallel after Foundational
```

**Phase 5 (US3)**:
```bash
# Run in parallel:
T025 Create algebra hints JSON
T026 Create calculus hints JSON
T027 Create misconceptions JSON
```

**Phase 8 (US6)**:
```bash
# Run in parallel:
T042 Implement SessionMemory
T043 Implement StudentMemory
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: User Story 1 (Socratic Tutoring)
4. Complete Phase 4: User Story 2 (Knowledge Tracking)
5. **STOP and VALIDATE**: Test core tutoring loop
6. Demo with basic functionality

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (Socratic) → Test → Demo
3. Add US2 (Knowledge) → Test → Demo
4. Add US3 (RAG) → Test → Demo (Hints grounded)
5. Add US4 (Cognitive) → Test → Demo (Adaptive difficulty)
6. Add US5 (Orchestration) → Test → Demo (Clean architecture)
7. Add US6 (Memory) → Test → Demo (Personalization)
8. Add US7 (Russian) → Test → Demo (Full localization)
9. Polish → Final release

---

## Summary

| Phase | Story | Task Count | Parallel Tasks |
|-------|-------|------------|----------------|
| 1 | Setup | 6 | 4 |
| 2 | Foundational | 5 | 2 |
| 3 | US1 - Socratic | 6 | 0 |
| 4 | US2 - Knowledge | 7 | 0 |
| 5 | US3 - RAG | 7 | 3 |
| 6 | US4 - Cognitive | 5 | 0 |
| 7 | US5 - Orchestration | 5 | 0 |
| 8 | US6 - Memory | 6 | 2 |
| 9 | US7 - Russian | 5 | 0 |
| 10 | Polish | 7 | 3 |
| **Total** | | **59** | **14** |

**MVP Scope**: Phases 1-4 (User Stories 1 + 2) = 24 tasks
**Full Scope**: All phases = 59 tasks

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Existing code (✅ in plan.md) should be enhanced, not rewritten
