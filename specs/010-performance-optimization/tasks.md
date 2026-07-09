# Tasks: Performance Optimization

**Input**: Design documents from `/specs/010-performance-optimization/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested - tests are NOT included.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Paths follow existing MITS structure per plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and directory structure

- [x] T001 Create data directories: `data/few_shot/`, `data/reports/`
- [x] T002 [P] Install additional dependencies (pynvml, psutil, matplotlib, seaborn) in requirements.txt
- [x] T003 [P] Add performance optimization settings to src/config.py (cache thresholds, compression limits, monitoring intervals)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database schema and shared models that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Extend CacheEntry model with new fields (context_hash, teaching_strategy, response_time_ms, variant_id) in src/data/schemas.py
- [x] T005 [P] Add SessionMetrics extended fields to src/data/schemas.py
- [x] T006 [P] Create ABExperiment and ABVariant models in src/data/schemas.py
- [x] T007 [P] Create CompressedContext and KeyEvent models in src/data/schemas.py
- [x] T008 [P] Create FewShotExample model in src/data/schemas.py
- [x] T009 [P] Create MetricsReport and ChartData models in src/data/schemas.py
- [x] T010 [P] Create ResourceSample model in src/data/schemas.py
- [x] T011 Create database migration script for new SQLite tables (ab_experiments, ab_assignments, resource_samples, metrics_reports) in scripts/migrate_010.py
- [x] T012 Run database migration and verify schema in data/metrics.db

**Checkpoint**: Foundation ready - all models defined, database schema updated

---

## Phase 3: User Story 1 - Быстрые ответы тьютора (Priority: P1) MVP

**Goal**: Время ответа <2 сек для новых запросов, <0.5 сек для кэшированных

**Independent Test**: Измерить время ответа на типовые запросы до и после оптимизации

### Implementation for User Story 1

- [x] T013 [US1] Extend ResponseCache with context_hash computation and matching in src/inference/cache.py
- [x] T014 [US1] Increase similarity threshold to 0.90 and add cache stats tracking in src/inference/cache.py
- [x] T015 [US1] Add cache_hit_rate metric to InferenceMetrics in src/inference/metrics.py
- [x] T016 [P] [US1] Optimize hint_prefetcher with skill graph-based prediction in src/inference/hint_prefetcher.py
- [x] T017 [P] [US1] Implement time-windowed batch embedding processing in src/inference/batch_processor.py
- [ ] T018 [US1] Add system prompt caching to LLM client in src/models/llm_client.py
- [ ] T019 [US1] Integrate cache lookup before LLM generation in src/agents/tutor_agent.py
- [ ] T020 [US1] Add prefetch trigger on task load and error detection in src/agents/tutor_agent.py
- [ ] T021 [US1] Update config.py with Ollama optimization parameters (num_ctx=4096, num_batch=512)

**Checkpoint**: Response time optimization complete - can measure <2s responses

---

## Phase 4: User Story 2 - Сбор метрик для диплома (Priority: P1)

**Goal**: Полный сбор метрик и автоматическая генерация отчётов для дипломной работы

**Independent Test**: Запустить сессию и проверить наличие логов с метриками

### Implementation for User Story 2

- [x] T022 [US2] Create A/B testing module with experiment management in src/inference/ab_testing.py
- [x] T023 [US2] Implement variant assignment (deterministic hash-based) in src/inference/ab_testing.py
- [x] T024 [US2] Add experiment results aggregation and statistical analysis in src/inference/ab_testing.py
- [x] T025 [P] [US2] Extend session_logger with new metric fields (response_time, cache_hits, tokens, VRAM) in src/logging/session_logger.py
- [x] T026 [P] [US2] Create ResourceMonitor with psutil/pynvml sampling in src/inference/metrics.py
- [x] T027 [US2] Implement background resource monitoring thread in src/inference/metrics.py
- [x] T028 [US2] Create report_generator module with matplotlib charts in src/logging/report_generator.py
- [x] T029 [US2] Implement daily/weekly report aggregation in src/logging/report_generator.py
- [x] T030 [US2] Add JSON/CSV/PNG export functionality in src/logging/report_generator.py
- [ ] T031 [US2] Integrate A/B variant assignment into tutor session flow in src/agents/tutor_agent.py
- [ ] T032 [US2] Add metrics dashboard tab to UI in interface/unified_app.py

**Checkpoint**: Metrics collection complete - can generate diploma-ready reports

---

## Phase 5: User Story 3 - Качественные ответы с примерами (Priority: P2)

**Goal**: Улучшение качества ответов через few-shot prompting и Chain-of-Thought

**Independent Test**: Оценить полноту и корректность объяснений на наборе задач

### Implementation for User Story 3

- [x] T033 [US3] Create few_shot_bank module with JSON loading in src/knowledge/few_shot_bank.py
- [x] T034 [US3] Implement semantic retrieval for few-shot examples in src/knowledge/few_shot_bank.py
- [x] T035 [US3] Add few-shot prompt formatting utility in src/knowledge/few_shot_bank.py
- [x] T036 [P] [US3] Create few-shot examples for derivatives in data/few_shot/derivatives.json
- [x] T037 [P] [US3] Create few-shot examples for integrals in data/few_shot/integrals.json
- [x] T038 [P] [US3] Create few-shot examples for limits in data/few_shot/limits.json
- [x] T039 [US3] Create Chain-of-Thought templates (Russian) in src/knowledge/cot_templates.py
- [x] T040 [US3] Implement CoT decision logic (use for difficulty >= medium) in src/knowledge/cot_templates.py
- [ ] T041 [US3] Integrate few-shot retrieval into RAG pipeline in src/knowledge/rag_retriever.py
- [ ] T042 [US3] Integrate CoT into tutor agent prompt building in src/agents/tutor_agent.py
- [ ] T043 [US3] Add few_shot_used and cot_used tracking to session metrics in src/agents/tutor_agent.py

**Checkpoint**: Response quality improvements complete - can evaluate on test tasks

---

## Phase 6: User Story 4 - Эффективное использование ресурсов (Priority: P2)

**Goal**: Стабильная работа с VRAM <7GB и без утечек памяти в течение 2+ часов

**Independent Test**: Мониторинг VRAM и RAM при длительной работе

### Implementation for User Story 4

- [x] T044 [US4] Create context_compressor module with sliding window in src/inference/context_compressor.py
- [x] T045 [US4] Implement key event extraction (errors, hints, progress) in src/inference/context_compressor.py
- [x] T046 [US4] Add token counting and compression threshold check in src/inference/context_compressor.py
- [x] T047 [US4] Implement context rebuild for LLM prompt in src/inference/context_compressor.py
- [x] T048 [US4] Add VRAM/RAM alert thresholds and notifications in src/inference/metrics.py
- [ ] T049 [US4] Integrate context compression into tutor agent conversation handling in src/agents/tutor_agent.py
- [ ] T050 [US4] Add compression metrics logging (compression_ratio, context_compressions count) in src/agents/tutor_agent.py
- [x] T051 [US4] Verify Ollama Flash Attention environment setup in scripts/check_ollama_config.py

**Checkpoint**: Resource optimization complete - can run 2+ hour sessions stably

---

## Phase 7: User Story 5 - Работа без интернета (Priority: P3)

**Goal**: Полностью офлайн функционирование системы

**Independent Test**: Отключить сеть и проверить работоспособность

### Implementation for User Story 5

- [x] T052 [US5] Add offline mode detection utility in src/utils/offline_mode.py
- [ ] T053 [US5] Ensure all embeddings use local sentence-transformers (verify no external API calls) in src/knowledge/rag_retriever.py
- [ ] T054 [US5] Add cache warm-up from disk on startup in src/inference/cache.py
- [ ] T055 [US5] Verify Ollama local-only configuration in src/config.py
- [ ] T056 [US5] Add offline mode indicator to UI in interface/unified_app.py

**Checkpoint**: Offline mode complete - system works without internet

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, documentation, and verification

- [x] T057 Create demo script for performance features in scripts/demo_performance.py
- [ ] T058 [P] Update quickstart.md with actual usage examples in specs/010-performance-optimization/quickstart.md
- [ ] T059 [P] Add performance settings documentation to README section
- [ ] T060 Run end-to-end performance validation (response time, cache hit rate, VRAM)
- [ ] T061 Generate sample diploma report with charts in data/reports/

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 and US2 are both P1 priority - can run in parallel
  - US3 and US4 are both P2 priority - can run in parallel after US1/US2
  - US5 is P3 - can start after Foundational but lower priority
- **Polish (Phase 8)**: Depends on at least US1 and US2 being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 3 (P2)**: Can start after Foundational - May use cache from US1 but independently testable
- **User Story 4 (P2)**: Can start after Foundational - Integrates with metrics from US2 but independently testable
- **User Story 5 (P3)**: Can start after Foundational - Uses cache/RAG from US1/US3 but independently testable

### Within Each User Story

- Models/schemas defined in Foundational phase
- Core module before integration
- Integration into tutor_agent after core module
- Metrics/logging after main functionality

### Parallel Opportunities

**Phase 2 (Foundational)** - Models can be created in parallel:
```
T004, T005, T006, T007, T008, T009, T010 → all [P], run together
```

**Phase 3 (US1)** - Independent optimizations:
```
T016 (hint_prefetcher) || T017 (batch_processor) → both [P]
```

**Phase 4 (US2)** - Independent metrics components:
```
T025 (session_logger) || T026 (ResourceMonitor) → both [P]
```

**Phase 5 (US3)** - Few-shot data files:
```
T036 (derivatives.json) || T037 (integrals.json) || T038 (limits.json) → all [P]
```

**Phase 8 (Polish)** - Documentation:
```
T058 (quickstart) || T059 (README) → both [P]
```

---

## Parallel Example: User Story 1

```bash
# After T015 completes, launch parallel optimization tasks:
Task T016: "Optimize hint_prefetcher with skill graph-based prediction in src/inference/hint_prefetcher.py"
Task T017: "Implement time-windowed batch embedding processing in src/inference/batch_processor.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (fast responses)
4. Complete Phase 4: User Story 2 (metrics collection)
5. **STOP and VALIDATE**: Test response time + verify metrics logging
6. Generate initial diploma report

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test response times → MVP for speed!
3. Add User Story 2 → Test metrics → MVP for diploma data!
4. Add User Story 3 → Test response quality → Enhanced tutoring
5. Add User Story 4 → Test stability → Production-ready
6. Add User Story 5 → Test offline → Full feature set

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (caching, prefetch)
   - Developer B: User Story 2 (metrics, A/B testing)
3. After US1/US2:
   - Developer A: User Story 3 (few-shot, CoT)
   - Developer B: User Story 4 (compression, monitoring)
4. Developer A or B: User Story 5 (offline mode)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Existing files to EXTEND: cache.py, metrics.py, hint_prefetcher.py, batch_processor.py, session_logger.py, rag_retriever.py, tutor_agent.py, schemas.py, config.py, unified_app.py
- New files to CREATE: ab_testing.py, context_compressor.py, report_generator.py, few_shot_bank.py, cot_templates.py, offline_mode.py, demo_performance.py, migrate_010.py, check_ollama_config.py
