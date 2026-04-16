# Tasks: Knowledge Forge — Personalized Knowledge Graph Navigator

**Input**: Design documents from `/specs/016-knowledge-forge/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — tests are important for graph navigation correctness (pathfinding, scoring, gap diagnosis).

**Organization**: Tasks grouped by user story. US2 (seed data) precedes US1 (tutor navigation) since navigation requires graph data.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 1: Setup

**Purpose**: Verify existing code compiles, resolve imports, ensure test infrastructure works.

- [x] T001 Verify existing knowledge_forge.py and navigator.py import correctly — run `python -c "from src.knowledge.knowledge_forge import KnowledgeGraph, NodeType, EdgeType; from src.knowledge.navigator import PersonalizedNavigator; print('OK')"`
- [x] T002 [P] Create empty test files: `tests/test_knowledge_forge.py`, `tests/test_navigator.py`, `tests/test_navigator_tools.py` with basic pytest imports and one placeholder test each
- [x] T003 [P] Verify existing data files are readable: `data/knowledge/skill_graph.json`, `data/knowledge/textbooks/*.json` — write a quick smoke-test script

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Complete core scoring functions and tool definitions that ALL user stories depend on.

**CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 Implement `_score_frontier_node()` in `src/knowledge/navigator.py` — replace placeholder with weighted composite: prerequisite gate (min ratio > 0.5), quality factor (prereq_mastery_avg), novelty factor (1 - own_mastery), difficulty penalty. See research.md R5
- [x] T005 Refine `_compute_edge_cost()` in `src/knowledge/navigator.py` — verify mastery-weighted cost formula: knowledge_cost = 1 - mastery, difficulty_factor = 0.5 + 0.5 * difficulty, return max(0.01, knowledge_cost * difficulty_factor)
- [x] T006 [P] Create `src/tools/navigator_tools.py` — define NAVIGATOR_TOOL_DEFINITIONS (Ollama format) and NAVIGATOR_FUNCTIONS dispatch dict for 5 tools: explore_concept, diagnose_gap, suggest_next, find_learning_path, get_learning_frontier. Use contract from `specs/016-knowledge-forge/contracts/navigator-tools.json`
- [x] T007 [P] Implement tool dispatch functions in `src/tools/navigator_tools.py` — each function instantiates or receives PersonalizedNavigator, calls the appropriate method, and returns JSON-serializable results. Functions must accept keyword args matching the Ollama tool parameter schemas
- [x] T008 Write unit tests for `_score_frontier_node()` in `tests/test_navigator.py` — test: no prereqs (entry point), all prereqs mastered, partial prereqs, zero own mastery, high own mastery, high difficulty with weak prereqs
- [x] T009 [P] Write unit tests for `_compute_edge_cost()` in `tests/test_navigator.py` — test: fully mastered (cost near 0), unknown (cost near 1), easy vs hard concepts, boundary values

**Checkpoint**: Core scoring and tool definitions ready. Migration and integration can begin.

---

## Phase 3: User Story 2 — Seed Graph from Existing Data (Priority: P1)

**Goal**: Migrate existing skill_graph.json (40+ skills) and SKI knowledge cards into forge.json so the navigator has data to work with.

**Independent Test**: Load forge.json, verify node count >= 40 concepts, verify all skill_graph prerequisites appear as PREREQUISITE edges, verify SKI card formulas/examples appear as linked nodes.

### Tests for User Story 2

- [x] T010 [P] [US2] Write test for migration completeness in `tests/test_knowledge_forge.py` — assert all skills from skill_graph.json are present as CONCEPT nodes with matching `name_ru`, `difficulty`, `category`
- [x] T011 [P] [US2] Write test for edge correctness in `tests/test_knowledge_forge.py` — assert every `prerequisites` entry in skill_graph.json becomes a PREREQUISITE edge in the graph
- [x] T012 [P] [US2] Write test for SKI card decomposition in `tests/test_knowledge_forge.py` — assert key_formulas become FORMULA nodes with DERIVED_FROM edges, worked_examples become EXAMPLE nodes with ILLUSTRATES edges, common_errors become MISCONCEPTION nodes with COMMON_ERROR_FOR edges

### Implementation for User Story 2

- [x] T013 [US2] Create `scripts/migrate_to_forge.py` — load `data/knowledge/skill_graph.json`, create CONCEPT node for each skill (id format: `{category}:{skill_id}:definition`, title from name_ru, difficulty from skill difficulty, domain from category). Create PREREQUISITE edges from `prerequisites` lists
- [x] T014 [US2] Extend `scripts/migrate_to_forge.py` — load each JSON file from `data/knowledge/textbooks/`, parse KnowledgeCard fields, create child nodes (FORMULA from key_formulas, EXAMPLE from worked_examples, METHOD from solution_methods, MISCONCEPTION from common_errors) and link to parent CONCEPT with appropriate EdgeType
- [x] T015 [US2] Add idempotency to `scripts/migrate_to_forge.py` — check if node ID already exists before adding, log skipped duplicates
- [x] T016 [US2] Run migration: `python scripts/migrate_to_forge.py` — output `data/knowledge/forge.json`. Verify with `KnowledgeGraph.stats` that node/edge counts match expectations
- [x] T017 [US2] Write graph persistence round-trip test in `tests/test_knowledge_forge.py` — save graph to temp file, reload, verify all nodes and edges match original

**Checkpoint**: forge.json exists with 40+ CONCEPT nodes, prerequisite edges, and linked FORMULA/EXAMPLE/METHOD/MISCONCEPTION nodes. Graph loads successfully.

---

## Phase 4: User Story 1 — Tutor Navigates Knowledge Graph During Session (Priority: P1)

**Goal**: Tutor LLM can invoke navigator tools during sessions to explore concepts, diagnose gaps, and get personalized recommendations.

**Independent Test**: Call `explore_concept` tool with a concept ID and mock student mastery — verify response includes concept content, prerequisite mastery status, and related misconceptions.

### Tests for User Story 1

- [x] T018 [P] [US1] Write integration test for `explore_concept` tool in `tests/test_navigator_tools.py` — load forge.json, create mock mastery dict, call explore_concept, assert response contains concept content and prerequisite mastery annotations
- [x] T019 [P] [US1] Write integration test for `diagnose_gap` tool in `tests/test_navigator_tools.py` — create student with mastered algebra but not calculus, call diagnose_gap for "definite_integrals", assert root_gap is in the expected prerequisite chain
- [x] T020 [P] [US1] Write integration test for `suggest_next` tool in `tests/test_navigator_tools.py` — create student with partial mastery, call suggest_next, assert returned concept has high readiness score and unmastered status

### Implementation for User Story 1

- [x] T021 [US1] Create navigator singleton/factory in `src/tools/navigator_tools.py` — function `get_navigator()` that loads forge.json graph + accepts StudentMemory or mock dict, caches instance for session reuse
- [x] T022 [US1] Integrate navigator tools into `src/agents/tutor_agent.py` — import NAVIGATOR_TOOL_DEFINITIONS and NAVIGATOR_FUNCTIONS, merge with SKI tools: `all_tools = self._ski_tool_defs + navigator_defs`, `all_functions = {**self._ski_functions, **navigator_fns}`. Pass merged lists to `llm.chat_with_tools()`
- [x] T023 [US1] Pass student_id context to navigator tools in `src/agents/tutor_agent.py` — ensure student_id from session is available to tool dispatch functions (via closure, partial, or session context)
- [x] T024 [US1] Add GRAPH_NAV stage to orchestrator pipeline in `src/agents/orchestrator.py` — after ROUTING stage, before PLANNER: call navigator's `get_concept_context()` for the current topic, pass result to planner and tutor. Wrap in try/except for graceful degradation
- [x] T025 [US1] Test graceful degradation in `tests/test_navigator_tools.py` — verify tutor agent works normally when forge.json doesn't exist or navigator raises an exception

**Checkpoint**: Tutor can invoke explore_concept, diagnose_gap, suggest_next during sessions. Falls back gracefully when graph is unavailable.

---

## Phase 5: User Story 3 — Personalized Learning Path Computation (Priority: P2)

**Goal**: Compute optimal mastery-weighted paths from current knowledge to any target concept.

**Independent Test**: Create student with mastered algebra, request path to "integration_by_parts". Verify path respects dependency order (no concept before its prerequisites).

### Tests for User Story 3

- [ ] T026 [P] [US3] Write pathfinding correctness test in `tests/test_navigator.py` — verify path from algebra to definite_integrals goes through limits and derivatives, not around them
- [ ] T027 [P] [US3] Write path dependency-order test in `tests/test_navigator.py` — for every consecutive pair (A, B) in path, verify A is a prerequisite of B or BEST_TAUGHT_AFTER B
- [ ] T028 [P] [US3] Write path optimality test in `tests/test_navigator.py` — with student who has mastered half the prerequisites, verify path cost is lower than path for a student with no mastery
- [ ] T029 [P] [US3] Write edge case tests in `tests/test_navigator.py` — already mastered target (empty path), unreachable target (returns None), no mastery data (cold start)

### Implementation for User Story 3

- [ ] T030 [US3] Verify `find_optimal_path()` works with real forge.json — load graph, test with various mock mastery profiles, fix any issues with edge traversal direction (PREREQUISITE edges point from prereq → concept)
- [ ] T031 [US3] Wire `find_learning_path` tool in `src/tools/navigator_tools.py` — implement dispatch function that calls `navigator.find_optimal_path()` and formats LearningPath as JSON response with path titles, costs, and mastery values
- [ ] T032 [US3] Wire `get_learning_frontier` tool in `src/tools/navigator_tools.py` — implement dispatch function that calls `navigator.get_learning_frontier()` and returns ranked FrontierNode list as JSON

**Checkpoint**: find_learning_path and get_learning_frontier tools work end-to-end with real forge.json data.

---

## Phase 6: User Story 4 — Planner Uses Graph for Strategy Selection (Priority: P2)

**Goal**: Planner receives graph context (gap diagnosis, misconceptions, frontier) and uses it to enhance strategy selection.

**Independent Test**: Simulate student failing at chain_rule with missing product_rule prerequisite. Verify planner includes "product_rule" in prerequisites_to_review and selects appropriate strategy.

### Tests for User Story 4

- [ ] T033 [P] [US4] Write planner enrichment test in `tests/test_navigator.py` — create mock graph context with gap diagnosis, pass to planner, verify prerequisites_to_review populated
- [ ] T034 [P] [US4] Write fallback test in `tests/test_navigator.py` — pass graph_context=None to planner, verify existing rule-based logic produces valid TeachingPlan without errors

### Implementation for User Story 4

- [ ] T035 [US4] Add `graph_context: Optional[Dict] = None` parameter to `create_plan()` in `src/agents/planner.py` — accept gap diagnosis, frontier info, and misconception data from orchestrator
- [ ] T036 [US4] Enhance strategy selection in `src/agents/planner.py` — when graph_context contains missing_prerequisites, populate `TeachingPlan.prerequisites_to_review`. When graph_context contains misconceptions linked to current concept, bias strategy toward CONCEPTUAL_REPAIR
- [ ] T037 [US4] Pass graph context from orchestrator to planner in `src/agents/orchestrator.py` — in the PLANNER stage, include graph navigation results (from GRAPH_NAV stage added in T024) as graph_context parameter

**Checkpoint**: Planner uses graph data when available, falls back to rules when not. TeachingPlan includes prerequisite review data from gap diagnosis.

---

## Phase 7: User Story 5 — Source Document Extraction (Priority: P3)

**Goal**: LLM agent reads source documents and extracts structured knowledge nodes + edges for graph ingestion.

**Independent Test**: Feed a short textbook section on "limits" to the extractor. Verify it produces CONCEPT, FORMULA, and EXAMPLE nodes with correct relationships.

### Tests for User Story 5

- [ ] T038 [P] [US5] Write extraction test in `tests/test_source_extractor.py` — use a hardcoded sample text about quadratic equations, mock LLM response with expected JSON, verify correct nodes/edges created
- [ ] T039 [P] [US5] Write deduplication test in `tests/test_source_extractor.py` — extract same text twice, verify no duplicate nodes created

### Implementation for User Story 5

- [ ] T040 [US5] Create `src/knowledge/source_extractor.py` — class SourceExtractor with `extract(text: str, domain: str) -> Tuple[List[KnowledgeNode], List[KnowledgeEdge]]`. Uses LLMClient with JSON mode for structured output
- [ ] T041 [US5] Implement two-pass extraction in `src/knowledge/source_extractor.py` — Pass 1: extract entities (concepts, formulas, theorems, examples). Pass 2: extract relationships between identified entities. Each pass uses a focused prompt with expected JSON schema
- [ ] T042 [US5] Add confidence scoring and deduplication in `src/knowledge/source_extractor.py` — extracted nodes get confidence < 1.0, fuzzy match on title + domain to detect duplicates, merge or flag as needed
- [ ] T043 [US5] Add `ingest_document(text, domain, source_name)` method to `KnowledgeGraph` in `src/knowledge/knowledge_forge.py` — accepts extraction results, adds nodes/edges, saves graph. Returns summary of added/merged/skipped counts

**Checkpoint**: Source extractor can process text documents and add structured knowledge to the graph. Extracted nodes have confidence < 1.0.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Quality improvements across all user stories.

- [ ] T044 [P] Run `ruff check .` and `ruff format .` on all new/modified files
- [ ] T045 [P] Add type hints to all public functions in navigator_tools.py and source_extractor.py (per CLAUDE.md Python Standards)
- [ ] T046 [P] Add structlog logging to navigator_tools.py — log each tool invocation with concept_id, student_id, and response summary
- [ ] T047 Run full test suite: `cd src && pytest tests/test_knowledge_forge.py tests/test_navigator.py tests/test_navigator_tools.py tests/test_source_extractor.py -v`
- [ ] T048 Run quickstart.md validation — execute all code blocks from `specs/016-knowledge-forge/quickstart.md` and verify expected output
- [ ] T049 Update `CLAUDE.md` Recent Changes section with Knowledge Forge summary

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US2 - Seed Data (Phase 3)**: Depends on Phase 2 — BLOCKS US1 (navigator needs data)
- **US1 - Tutor Navigation (Phase 4)**: Depends on Phase 2 + Phase 3
- **US3 - Learning Paths (Phase 5)**: Depends on Phase 2 + Phase 3 — can parallel with US1
- **US4 - Planner Integration (Phase 6)**: Depends on Phase 4 (GRAPH_NAV stage in orchestrator)
- **US5 - Source Extraction (Phase 7)**: Depends on Phase 2 only — can parallel with US1/US3/US4
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

```text
Phase 1 (Setup)
    ↓
Phase 2 (Foundational: scoring + tools)
    ↓
Phase 3 (US2: seed data) ──────────→ Phase 7 (US5: extraction) [parallel]
    ↓
Phase 4 (US1: tutor nav) ←→ Phase 5 (US3: learning paths) [parallel]
    ↓
Phase 6 (US4: planner integration)
    ↓
Phase 8 (Polish)
```

### Parallel Opportunities

- **Phase 2**: T006 + T007 (tool defs) parallel with T004 + T005 (scoring). T008 + T009 parallel (tests).
- **Phase 3**: T010 + T011 + T012 parallel (tests). T013 parallel with nothing (sequential migration).
- **Phase 4**: T018 + T019 + T020 parallel (tests).
- **Phase 5**: T026 + T027 + T028 + T029 parallel (tests). Entire Phase 5 parallel with Phase 4.
- **Phase 7**: Entire Phase 7 can run parallel with Phases 4-6 (only depends on Phase 2).
- **Phase 8**: T044 + T045 + T046 parallel.

---

## Parallel Example: Phase 2 (Foundational)

```text
# Group A: Scoring functions (sequential)
T004: Implement _score_frontier_node() in src/knowledge/navigator.py
T005: Refine _compute_edge_cost() in src/knowledge/navigator.py

# Group B: Tool definitions (parallel, different file)
T006: Create NAVIGATOR_TOOL_DEFINITIONS in src/tools/navigator_tools.py
T007: Implement tool dispatch functions in src/tools/navigator_tools.py

# Group C: Tests (parallel, different test file)
T008: Tests for _score_frontier_node() in tests/test_navigator.py
T009: Tests for _compute_edge_cost() in tests/test_navigator.py

# Groups A, B, C can run in parallel (different files)
```

---

## Implementation Strategy

### MVP First (US2 + US1)

1. Complete Phase 1: Setup (verify existing code)
2. Complete Phase 2: Foundational (scoring + tools)
3. Complete Phase 3: US2 — Seed forge.json from existing data
4. Complete Phase 4: US1 — Tutor navigates graph during sessions
5. **STOP and VALIDATE**: Test tutor tool calling with real student session
6. This delivers the core value: personalized graph-aware tutoring

### Incremental Delivery

1. Setup + Foundational → Core ready
2. + US2 (seed data) → Graph exists with 40+ concepts
3. + US1 (tutor nav) → **MVP: Tutor uses graph tools**
4. + US3 (learning paths) → Students get personalized paths
5. + US4 (planner integration) → Strategy selection uses graph
6. + US5 (source extraction) → Graph grows from documents
7. Each increment is independently testable and deployable

---

## Notes

- `knowledge_forge.py` and `navigator.py` already exist (partially implemented). Tasks build on them.
- US2 (seed data) must complete before US1 (navigation) — navigator needs graph data.
- US5 (extraction) is independent of US1/US3/US4 — can be developed in parallel.
- All tool definitions follow Ollama format from `specs/016-knowledge-forge/contracts/navigator-tools.json`.
- Graceful degradation (T025) is critical: system must work when graph is empty/unavailable.
