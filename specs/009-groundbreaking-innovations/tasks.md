# Tasks: Groundbreaking Innovations for MITS

**Input**: Design documents from `/specs/009-groundbreaking-innovations/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US6)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install dependencies and prepare project structure for innovations

- [x] T001 Install new dependencies: `pip install sympy networkx`
- [ ] T002 [P] Pull vision model for OCR: `ollama pull minicpm-v`
- [x] T003 [P] Add innovation settings to src/config.py (AFFECTIVE_DETECTION_ENABLED, TASK_SYNTHESIS_ENABLED, etc.)
- [x] T004 [P] Add new Pydantic models to src/data/schemas.py (AffectiveStateType, AffectiveSignals, AffectiveState enums and base classes)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that ALL innovations depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Create knowledge graph structure in src/data/knowledge_graph.py with SKILL_GRAPH dictionary (40+ skills with prerequisites)
- [x] T006 [P] Add VerificationStatus enum to src/data/schemas.py
- [x] T007 [P] Add GeneratedTask model to src/data/schemas.py (extends Task with verification fields)
- [x] T008 [P] Add MetacognitiveLevel, StuckPointType enums to src/data/schemas.py
- [x] T009 [P] Add StuckPoint, MetacognitiveProfile models to src/data/schemas.py
- [x] T010 [P] Add LearningPathStatus enum, SkillNode, LearningPath models to src/data/schemas.py
- [x] T011 [P] Add RecognitionConfidence enum, SolutionStep, HandwrittenSolution models to src/data/schemas.py
- [x] T012 [P] Add CounterfactualExplanation model to src/data/schemas.py
- [x] T013 Create SymPy helper utilities in src/utils/sympy_utils.py (parse_expr wrapper, safe_diff, safe_integrate, verify_equality)

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Affective State Detection (Priority: P1) 🎯 MVP

**Goal**: Система определяет эмоциональное состояние студента и адаптирует ответы

**Independent Test**: Симулировать различные паттерны сообщений (короткие с опечатками → фрустрация, быстрые правильные → скука) и проверить, что система корректно классифицирует состояние и адаптирует тон

### Implementation for User Story 1

- [x] T014 [P] [US1] Create AffectiveDetector class in src/models/affective_detector.py with __init__, analyze_message, _extract_text_signals methods
- [x] T015 [P] [US1] Add _calculate_typo_density method to src/models/affective_detector.py (Russian language aware)
- [x] T016 [US1] Add _classify_state method to src/models/affective_detector.py (rule-based classification with weighted signals)
- [x] T017 [US1] Add _semantic_analysis method to src/models/affective_detector.py (optional LLM analysis for edge cases)
- [x] T018 [US1] Add get_adaptation_prompt method to src/models/affective_detector.py (returns prompt modifier for tutor)
- [x] T019 [US1] Add reset_session, get_state_history methods to src/models/affective_detector.py
- [x] T020 [P] [US1] Create AffectiveAgent wrapper in src/agents/affective_agent.py (integrates with orchestrator)
- [x] T021 [US1] Modify SocraticTutor.__init__ in src/agents/tutor_agent.py to accept optional AffectiveDetector
- [x] T022 [US1] Modify SocraticTutor.respond in src/agents/tutor_agent.py to call AffectiveDetector.analyze_message and adapt response
- [x] T023 [US1] Add affective state display to interface/unified_app.py (subtle indicator in chat header)

**Checkpoint**: Affective State Detection fully functional and testable independently

---

## Phase 4: User Story 2 - Generative Task Synthesis (Priority: P1) 🎯 MVP

**Goal**: Система генерирует математические задачи с верифицированными SymPy решениями

**Independent Test**: Запросить генерацию 10 задач по разным темам, проверить что 100% имеют sympy_verified=True

### Implementation for User Story 2

- [x] T024 [P] [US2] Create TaskSynthesizer class in src/models/task_synthesizer.py with __init__, generate_task methods
- [x] T025 [US2] Add _generate_problem_structure method to src/models/task_synthesizer.py (LLM generates topic-appropriate structure)
- [x] T026 [US2] Add _compute_answer_sympy method to src/models/task_synthesizer.py (SymPy computes verified answer)
- [x] T027 [US2] Add verify_task method to src/models/task_synthesizer.py (compare LLM answer with SymPy)
- [x] T028 [US2] Add generate_variation method to src/models/task_synthesizer.py (create isomorphic variations)
- [x] T029 [US2] Add generate_hints method to src/models/task_synthesizer.py (auto-generate progressive hints from solution steps)
- [x] T030 [US2] Add topic-specific generators: _generate_derivative_task, _generate_integral_task, _generate_limit_task in src/models/task_synthesizer.py
- [x] T031 [US2] Add _generate_equation_task, _generate_trig_task methods to src/models/task_synthesizer.py
- [x] T032 [US2] Add "🎲 Новая задача" tab to interface/unified_app.py with topic/difficulty selectors and generate button
- [x] T033 [US2] Connect TaskSynthesizer to math module in interface/unified_app.py (generate task on demand)

**Checkpoint**: Task Synthesis fully functional - can generate infinite verified tasks

---

## Phase 5: User Story 3 - Counterfactual Explanations (Priority: P2)

**Goal**: Система объясняет ошибки через контрфактуалы ("Если бы ты применил X...")

**Independent Test**: Подать заведомо неправильное решение (например, (fg)' = f'g'), проверить что система генерирует корректный контрфактуал с указанием product_rule

### Implementation for User Story 3

- [x] T034 [P] [US3] Create CounterfactualEngine class in src/models/counterfactual_engine.py with __init__ accepting knowledge_graph
- [x] T035 [US3] Add analyze_error method to src/models/counterfactual_engine.py (main entry point)
- [x] T036 [US3] Add _parse_solution_steps method to src/models/counterfactual_engine.py (split solution into steps)
- [x] T037 [US3] Add _find_divergence_point method to src/models/counterfactual_engine.py (compare student vs correct steps)
- [x] T038 [US3] Add _identify_missing_skill method to src/models/counterfactual_engine.py (map error pattern to skill)
- [x] T039 [US3] Add _generate_counterfactual_statement method to src/models/counterfactual_engine.py (LLM generates Russian explanation)
- [x] T040 [US3] Add get_remediation_tasks method to src/models/counterfactual_engine.py (find practice tasks for missing skill)
- [x] T041 [US3] Create SKILL_ERROR_MAPPING dictionary in src/data/knowledge_graph.py (maps error patterns to skills)
- [x] T042 [US3] Integrate CounterfactualEngine into SocraticTutor.respond in src/agents/tutor_agent.py (call on incorrect answers)
- [x] T043 [US3] Add counterfactual display formatting in interface/unified_app.py (collapsible comparison view)

**Checkpoint**: Counterfactual Explanations functional - errors explained with "if-then" statements

---

## Phase 6: User Story 4 - Metacognitive Scaffolding (Priority: P2)

**Goal**: Система обучает метакогнитивным навыкам через структурированные вопросы

**Independent Test**: Написать "не понимаю" и проверить что система задаёт структурированные вопросы о процессе мышления вместо прямой подсказки

### Implementation for User Story 4

- [x] T044 [P] [US4] Create MetacognitiveTracker class in src/models/metacognitive_tracker.py with __init__ accepting StudentMemory
- [x] T045 [US4] Add detect_stuck_point method to src/models/metacognitive_tracker.py (analyze message for stuck indicators)
- [x] T046 [US4] Add METACOGNITIVE_PROMPTS dictionary to src/models/metacognitive_tracker.py (understanding, strategy, monitoring questions in Russian)
- [x] T047 [US4] Add get_metacognitive_prompt method to src/models/metacognitive_tracker.py (select appropriate question based on stuck_type)
- [x] T048 [US4] Add record_intervention method to src/models/metacognitive_tracker.py (track what helped)
- [x] T049 [US4] Add get_reflection_prompt method to src/models/metacognitive_tracker.py (end-of-session reflection questions)
- [x] T050 [US4] Add update_profile method to src/models/metacognitive_tracker.py (calculate metacognitive level from history)
- [x] T051 [US4] Integrate MetacognitiveTracker into SocraticTutor in src/agents/tutor_agent.py (detect stuck, add scaffolding)
- [x] T052 [US4] Add end-of-session reflection dialog to interface/unified_app.py (popup after 30+ min session)
- [x] T053 [US4] Add metacognitive level indicator to student profile display in interface/unified_app.py

**Checkpoint**: Metacognitive Scaffolding functional - students guided through thinking process

---

## Phase 7: User Story 5 - Learning Path Optimization (Priority: P3)

**Goal**: Система строит оптимальный индивидуальный путь обучения

**Independent Test**: Создать профиль студента с mastery={algebra: 0.8, trig: 0.3}, запросить путь к integrals, проверить что trig включена как prerequisite

### Implementation for User Story 5

- [x] T054 [P] [US5] Create LearningPathOptimizer class in src/models/learning_path_optimizer.py with __init__ accepting knowledge_graph, knowledge_tracer
- [x] T055 [US5] Add _get_transitive_prerequisites method to src/models/learning_path_optimizer.py (networkx transitive closure)
- [x] T056 [US5] Add _filter_mastered_skills method to src/models/learning_path_optimizer.py (exclude skills with mastery > 0.7)
- [x] T057 [US5] Add _topological_sort_skills method to src/models/learning_path_optimizer.py (order by prerequisites)
- [x] T058 [US5] Add create_path method to src/models/learning_path_optimizer.py (main path creation)
- [x] T059 [US5] Add get_next_skill method to src/models/learning_path_optimizer.py (return next skill in path)
- [x] T060 [US5] Add update_progress method to src/models/learning_path_optimizer.py (update path when skill mastered)
- [x] T061 [US5] Add visualize_path method to src/models/learning_path_optimizer.py (generate Mermaid diagram)
- [x] T062 [US5] Add "🗺️ Путь обучения" tab to interface/unified_app.py with target skill selector
- [x] T063 [US5] Add path visualization (Mermaid or ASCII) to interface/unified_app.py
- [x] T064 [US5] Connect LearningPathOptimizer to task selection in interface/unified_app.py (auto-suggest next topic)

**Checkpoint**: Learning Path Optimization functional - personalized curriculum generated

---

## Phase 8: User Story 6 - Multi-Modal Math Input (Priority: P3)

**Goal**: Студент загружает фото рукописного решения, система анализирует и находит ошибки

**Independent Test**: Загрузить фото с известным решением (например, ∫sin(x)dx = cos(x) с ошибкой в знаке), проверить что система находит ошибку

### Implementation for User Story 6

- [x] T065 [P] [US6] Create VisionAnalyzer class in src/models/vision_analyzer.py with __init__ accepting vision_model name
- [x] T066 [US6] Add is_available method to src/models/vision_analyzer.py (check if vision model installed in Ollama)
- [x] T067 [US6] Add _preprocess_image method to src/models/vision_analyzer.py (resize, enhance contrast)
- [x] T068 [US6] Add extract_latex method to src/models/vision_analyzer.py (vision model extracts LaTeX per line)
- [x] T069 [US6] Add _build_vision_prompt method to src/models/vision_analyzer.py (structured prompt for math OCR)
- [x] T070 [US6] Add verify_steps method to src/models/vision_analyzer.py (SymPy validates each step)
- [x] T071 [US6] Add analyze_image method to src/models/vision_analyzer.py (main entry: OCR + verification)
- [x] T072 [US6] Add get_unclear_regions method to src/models/vision_analyzer.py (identify low-confidence areas)
- [x] T073 [US6] Add "📷 Проверка решения" tab to interface/unified_app.py with gr.Image upload component
- [x] T074 [US6] Add analysis result display to interface/unified_app.py (recognized LaTeX, errors highlighted)
- [x] T075 [US6] Add VRAM management for vision model in src/models/vision_analyzer.py (load/unload on demand)

**Checkpoint**: Multi-Modal Input functional - handwritten solutions analyzed

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Integration, optimization, and final touches

- [x] T076 [P] Add comprehensive docstrings to all new modules
- [x] T077 [P] Update src/config.py with all innovation-related settings and defaults
- [x] T078 Integrate all 6 innovations into orchestrator flow in src/agents/orchestrator.py
- [x] T079 Add feature toggle UI to interface/unified_app.py (enable/disable each innovation)
- [x] T080 Performance optimization: lazy loading of vision model in src/models/vision_analyzer.py
- [x] T081 Add innovation status indicators to main dashboard in interface/unified_app.py
- [x] T082 Run quickstart.md validation (verify all code examples work)
- [x] T083 Create demo script scripts/demo_innovations.py showcasing all 6 features

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational completion
  - US1 (Affective) and US2 (Task Synthesis) are P1 priority - do first
  - US3 (Counterfactuals) and US4 (Metacognitive) are P2 priority - do second
  - US5 (Learning Path) and US6 (Multi-Modal) are P3 priority - do last
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (Affective)**: Independent - no dependencies on other stories
- **US2 (Task Synthesis)**: Independent - no dependencies on other stories
- **US3 (Counterfactuals)**: Can integrate with US1 affective state but independently testable
- **US4 (Metacognitive)**: Can integrate with US1 affective state but independently testable
- **US5 (Learning Path)**: Uses knowledge_graph from Foundational - independently testable
- **US6 (Multi-Modal)**: Independent - no dependencies on other stories

### Within Each User Story

- Models/utilities first
- Core logic second
- Integration with tutor third
- UI integration last

### Parallel Opportunities

**Setup Phase (parallel):**
- T002, T003, T004 can run in parallel

**Foundational Phase (parallel):**
- T006, T007, T008, T009, T010, T011, T012 can run in parallel (all schema additions)

**User Stories (parallel):**
- US1 and US2 can be developed in parallel (both P1)
- US3 and US4 can be developed in parallel (both P2)
- US5 and US6 can be developed in parallel (both P3)

---

## Parallel Example: User Story 2 (Task Synthesis)

```bash
# Launch models in parallel:
Task: "Create TaskSynthesizer class in src/models/task_synthesizer.py"

# Then sequentially:
Task: "Add _generate_problem_structure method"
Task: "Add _compute_answer_sympy method"
Task: "Add verify_task method"
# ... etc

# UI can be developed in parallel with logic:
Task: "Add '🎲 Новая задача' tab to interface/unified_app.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: User Story 1 (Affective Detection)
4. Complete Phase 4: User Story 2 (Task Synthesis)
5. **STOP and VALIDATE**: Both P1 stories functional
6. Deploy/demo MVP with 2 groundbreaking features

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (Affective) → Test → Demo: "Система понимает эмоции!"
3. Add US2 (Task Synthesis) → Test → Demo: "Бесконечные задачи с верификацией!"
4. Add US3 (Counterfactuals) → Test → Demo: "XAI объяснения ошибок!"
5. Add US4 (Metacognitive) → Test → Demo: "Обучение метакогнитивным навыкам!"
6. Add US5 (Learning Path) → Test → Demo: "Персонализированный curriculum!"
7. Add US6 (Multi-Modal) → Test → Demo: "OCR рукописных решений!"

### For Diploma Defense

Prioritize features with highest WOW-factor:
1. **Affective Detection** - easy to demo, impressive
2. **Task Synthesis** - practical, verifiable
3. **Counterfactuals** - scientific novelty (XAI)
4. Skip or simplify US5/US6 if time constrained

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Each user story independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Vision model (US6) requires VRAM management - load on demand
- SymPy verification (US2, US6) is critical for correctness claims
