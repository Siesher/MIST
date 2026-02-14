# Tasks: MITS Extended Features

**Input**: Design documents from `/specs/007-mits-extended-features/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested - focusing on implementation tasks.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1-US10) this task belongs to
- Paths follow single-project structure from plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, new directories, dependencies

- [ ] T001 Create new module directories: src/tools/, src/gamification/, src/spaced_repetition/, src/voice/, src/export/
- [ ] T002 [P] Create interface/components/ directory for dashboard UI components
- [ ] T003 [P] Create interface/api/ directory for REST API
- [ ] T004 [P] Create telegram_bot/ directory structure with handlers/ and utils/
- [ ] T005 [P] Create data/gamification/ and data/embeddings_cache/ directories
- [ ] T006 Update requirements.txt with new dependencies (sympy, duckduckgo-search, vosk, gTTS, plotly, python-telegram-bot, fastapi, slowapi, python-jose)
- [ ] T007 [P] Add new environment variables to .env.example (TELEGRAM_BOT_TOKEN, API_SECRET_KEY, VOICE_ENABLED, VOSK_MODEL_PATH)
- [ ] T008 Update src/config.py with new settings classes for extended features

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database schema extensions and shared utilities that ALL user stories depend on

**CRITICAL**: Complete before starting any user story

- [ ] T009 Create database migration for gamification tables (student_xp, achievements, student_achievements, streaks) in scripts/migrations/
- [ ] T010 [P] Create database migration for spaced_repetition tables (review_cards, review_history) in scripts/migrations/
- [ ] T011 [P] Create database migration for activity_log and api_tokens tables in scripts/migrations/
- [ ] T012 [P] Create database migration for embedding_cache table in scripts/migrations/
- [ ] T013 Create data/gamification/achievements.json with initial achievement definitions
- [ ] T014 [P] Create src/tools/__init__.py with ToolRegistry base class
- [ ] T015 [P] Create src/gamification/__init__.py with module exports
- [ ] T016 [P] Create src/spaced_repetition/__init__.py with module exports
- [ ] T017 [P] Create src/voice/__init__.py with module exports
- [ ] T018 [P] Create src/export/__init__.py with module exports
- [ ] T019 Run all migrations to update database schema via scripts/init_db.py --extended

**Checkpoint**: Foundation ready - user story implementation can begin

---

## Phase 3: User Story 1 - Real-time Streaming (Priority: P1) MVP

**Goal**: Tokens stream progressively with visible thinking process

**Independent Test**: Ask any math question, verify tokens appear word-by-word, expand thinking section

### Implementation for User Story 1

- [ ] T020 [US1] Update src/models/llm_client.py to add generate_stream() method using Ollama stream=True
- [ ] T021 [US1] Update src/agents/tutor_agent.py to support streaming mode with yield
- [ ] T022 [US1] Update src/agents/orchestrator.py to pass streaming flag through agent pipeline
- [ ] T023 [US1] Create streaming chat handler in interface/unified_app.py with gr.ChatInterface stream support
- [ ] T024 [US1] Add thinking accordion component to display reasoning in interface/unified_app.py
- [ ] T025 [US1] Implement graceful error recovery for interrupted streams in src/models/llm_client.py
- [ ] T026 [US1] Add streaming toggle to UI settings in interface/unified_app.py

**Checkpoint**: User Story 1 complete - streaming works independently

---

## Phase 4: User Story 2 - Calculator and Web Search Tools (Priority: P1)

**Goal**: Precise calculations and web search for educational content

**Independent Test**: Ask "What is 17!/15?" and verify exact answer 272. Ask about recent math topics.

### Implementation for User Story 2

- [ ] T027 [P] [US2] Create src/tools/calculator.py with SymPy-based calculate() function
- [ ] T028 [P] [US2] Create src/tools/web_search.py with DuckDuckGo search() function
- [ ] T029 [P] [US2] Create src/tools/knowledge_search.py for RAG-based hint retrieval
- [ ] T030 [US2] Update src/tools/__init__.py with tool registration and discovery
- [ ] T031 [US2] Update src/agents/tutor_agent.py to detect when tools are needed and call them
- [ ] T032 [US2] Add tool result formatting and error handling in src/agents/tutor_agent.py
- [ ] T033 [US2] Add tool usage display in chat interface in interface/unified_app.py

**Checkpoint**: User Story 2 complete - tools work independently

---

## Phase 5: User Story 10 - Performance Optimizations (Priority: P1)

**Goal**: Caching, batch inference, hint prefetching for responsive tutoring

**Independent Test**: Ask same question twice, verify second response <200ms. Verify embeddings persist across restart.

### Implementation for User Story 10

- [ ] T034 [P] [US10] Create src/inference/embedding_cache.py with persistent ChromaDB-based cache
- [ ] T035 [P] [US10] Create src/inference/response_cache.py with LRU cache for similar queries
- [ ] T036 [P] [US10] Create src/inference/batch_processor.py for batching multiple queries
- [ ] T037 [P] [US10] Create src/inference/hint_prefetcher.py for background hint loading
- [ ] T038 [US10] Update src/knowledge/rag_retriever.py to use embedding cache
- [ ] T039 [US10] Update src/models/llm_client.py to support batch inference
- [ ] T040 [US10] Integrate prefetching into problem display flow in interface/unified_app.py
- [ ] T041 [US10] Add cache statistics display in interface/unified_app.py settings

**Checkpoint**: User Story 10 complete - performance optimizations active

---

## Phase 6: User Story 3 - Progress Dashboard (Priority: P2)

**Goal**: Visual charts for mastery, learning velocity, skill tree

**Independent Test**: Complete several sessions, view dashboard, verify charts reflect activity

### Implementation for User Story 3

- [ ] T042 [P] [US3] Create interface/components/dashboard.py with Plotly mastery charts
- [ ] T043 [P] [US3] Create interface/components/skill_tree.py with networkx graph visualization
- [ ] T044 [P] [US3] Create interface/components/heatmap.py with activity calendar view
- [ ] T045 [US3] Create src/gamification/activity_tracker.py for logging and querying activities
- [ ] T046 [US3] Update src/memory/student_memory.py to provide dashboard data aggregations
- [ ] T047 [US3] Create dashboard tab in interface/unified_app.py integrating all components
- [ ] T048 [US3] Add learning velocity chart (problems/session trend) to interface/components/dashboard.py

**Checkpoint**: User Story 3 complete - dashboard viewable and accurate

---

## Phase 7: User Story 4 - Spaced Repetition (Priority: P2)

**Goal**: SM-2 algorithm schedules reviews, notifications when due

**Independent Test**: Master a topic, wait 1 day, verify topic appears in "Due for Review"

### Implementation for User Story 4

- [ ] T049 [P] [US4] Create src/spaced_repetition/sm2.py with SM-2 algorithm implementation
- [ ] T050 [P] [US4] Create src/spaced_repetition/scheduler.py for managing review cards
- [ ] T051 [US4] Create src/spaced_repetition/review_manager.py for CRUD operations on review cards
- [ ] T052 [US4] Integrate review card creation when topic is mastered in src/knowledge/tracer.py
- [ ] T053 [US4] Create review UI section in interface/unified_app.py showing due reviews
- [ ] T054 [US4] Add review quality rating (0-5) UI component in interface/unified_app.py
- [ ] T055 [US4] Update review intervals after each review in src/spaced_repetition/scheduler.py

**Checkpoint**: User Story 4 complete - spaced repetition functional

---

## Phase 8: User Story 5 - Gamification (Priority: P2)

**Goal**: XP, levels, achievements, streaks, badges

**Independent Test**: Solve problems, verify XP awarded, check achievements unlocked, maintain streak

### Implementation for User Story 5

- [ ] T056 [P] [US5] Create src/gamification/xp_system.py with XP calculation and level progression
- [ ] T057 [P] [US5] Create src/gamification/achievements.py with achievement checking logic
- [ ] T058 [P] [US5] Create src/gamification/streaks.py with daily streak tracking
- [ ] T059 [P] [US5] Create src/gamification/levels.py with level thresholds and rewards
- [ ] T060 [US5] Create interface/components/achievements.py with badge display UI
- [ ] T061 [US5] Integrate XP awarding after problem completion in src/agents/orchestrator.py
- [ ] T062 [US5] Add achievement unlock notifications in interface/unified_app.py
- [ ] T063 [US5] Add streak display and freeze protection UI in interface/unified_app.py
- [ ] T064 [US5] Add level-up celebration animation in interface/unified_app.py

**Checkpoint**: User Story 5 complete - gamification fully functional

---

## Phase 9: User Story 6 - Voice I/O (Priority: P3)

**Goal**: Speech-to-text and text-to-speech for Russian, math verbalization

**Independent Test**: Speak Russian math question, verify transcription, hear spoken response

### Implementation for User Story 6

- [ ] T065 [P] [US6] Create src/voice/speech_to_text.py with Vosk (offline) and Google STT (fallback)
- [ ] T066 [P] [US6] Create src/voice/text_to_speech.py with gTTS and pyttsx3 fallback
- [ ] T067 [US6] Create src/voice/math_verbalizer.py for converting LaTeX to spoken text
- [ ] T068 [US6] Add microphone input button to chat in interface/unified_app.py
- [ ] T069 [US6] Add audio playback for responses in interface/unified_app.py
- [ ] T070 [US6] Add voice settings (enable/disable, speed) in interface/unified_app.py
- [ ] T071 [US6] Handle voice recognition errors gracefully with fallback prompts

**Checkpoint**: User Story 6 complete - voice I/O works for Russian

---

## Phase 10: User Story 7 - Telegram Bot (Priority: P3)

**Goal**: Full tutoring via Telegram with LaTeX rendering and voice support

**Independent Test**: Send /start to bot, ask math question, verify LaTeX image and Socratic response

### Implementation for User Story 7

- [ ] T072 [P] [US7] Create telegram_bot/bot.py with main bot setup and polling/webhook modes
- [ ] T073 [P] [US7] Create telegram_bot/handlers/commands.py with /start, /help, /stats, /review handlers
- [ ] T074 [P] [US7] Create telegram_bot/handlers/messages.py for tutoring conversation handling
- [ ] T075 [P] [US7] Create telegram_bot/handlers/voice.py for voice message transcription
- [ ] T076 [US7] Create telegram_bot/utils/latex_render.py for rendering LaTeX to PNG
- [ ] T077 [US7] Integrate with existing orchestrator for tutoring in telegram_bot/handlers/messages.py
- [ ] T078 [US7] Add user session management for Telegram users in telegram_bot/bot.py
- [ ] T079 [US7] Add review due notifications for Telegram users in telegram_bot/handlers/commands.py

**Checkpoint**: User Story 7 complete - Telegram bot functional

---

## Phase 11: User Story 8 - Profile Export/Import (Priority: P3)

**Goal**: Export profile to JSON/Obsidian/Notion, import to restore

**Independent Test**: Export profile, delete data, import profile, verify all progress restored

### Implementation for User Story 8

- [ ] T080 [P] [US8] Create src/export/json_export.py with export_profile() and import_profile()
- [ ] T081 [P] [US8] Create src/export/obsidian_export.py with markdown vault generation
- [ ] T082 [P] [US8] Create src/export/notion_export.py with database structure export
- [ ] T083 [US8] Create export schema validation in src/export/json_export.py
- [ ] T084 [US8] Add export buttons (JSON, Obsidian, Notion) to settings in interface/unified_app.py
- [ ] T085 [US8] Add import file upload component in interface/unified_app.py
- [ ] T086 [US8] Add import conflict resolution UI (merge vs replace) in interface/unified_app.py

**Checkpoint**: User Story 8 complete - export/import functional

---

## Phase 12: User Story 9 - REST API (Priority: P3)

**Goal**: FastAPI REST API with JWT auth, rate limiting, OpenAPI docs

**Independent Test**: Get token, call /api/v1/chat, receive tutoring response

### Implementation for User Story 9

- [ ] T087 [P] [US9] Create interface/api/main.py with FastAPI app setup and CORS
- [ ] T088 [P] [US9] Create interface/api/auth.py with JWT token generation and validation
- [ ] T089 [P] [US9] Create interface/api/routes/chat.py with /chat and /chat/stream endpoints
- [ ] T090 [P] [US9] Create interface/api/routes/profile.py with profile CRUD endpoints
- [ ] T091 [P] [US9] Create interface/api/routes/progress.py with gamification/review endpoints
- [ ] T092 [US9] Add rate limiting middleware using slowapi in interface/api/main.py
- [ ] T093 [US9] Add OpenAPI documentation customization in interface/api/main.py
- [ ] T094 [US9] Create API token management table and endpoints in interface/api/auth.py

**Checkpoint**: User Story 9 complete - REST API functional with auth

---

## Phase 13: Polish & Cross-Cutting Concerns

**Purpose**: Integration, documentation, cleanup

- [ ] T095 Update README.md with new features documentation
- [ ] T096 [P] Update CLAUDE.md with new dependencies and commands
- [ ] T097 [P] Create scripts/run_api.py for starting REST API server
- [ ] T098 [P] Create scripts/run_telegram.py for starting Telegram bot
- [ ] T099 Verify all features work together in unified_app.py
- [ ] T100 Add feature flags to enable/disable optional features (voice, telegram) in src/config.py
- [ ] T101 [P] Create scripts/download_vosk_model.py for voice model setup
- [ ] T102 Final integration testing of all user stories
- [ ] T103 Run quickstart.md validation to ensure setup guide is accurate

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
     │
     ▼
Phase 2 (Foundational) ◄── BLOCKS ALL USER STORIES
     │
     ├──────────────────────────────────────────────┐
     ▼                                              ▼
Phase 3-5 (P1 Stories)                    Phase 6-8 (P2 Stories)
 - US1: Streaming                          - US3: Dashboard
 - US2: Tools                              - US4: Spaced Rep
 - US10: Performance                       - US5: Gamification
     │                                              │
     └──────────────────┬───────────────────────────┘
                        ▼
              Phase 9-12 (P3 Stories)
               - US6: Voice
               - US7: Telegram
               - US8: Export
               - US9: REST API
                        │
                        ▼
              Phase 13 (Polish)
```

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|------------|-------------------|
| US1 (Streaming) | Foundational | US2, US10 |
| US2 (Tools) | Foundational | US1, US10 |
| US10 (Performance) | Foundational | US1, US2 |
| US3 (Dashboard) | Foundational | US4, US5 |
| US4 (Spaced Rep) | Foundational | US3, US5 |
| US5 (Gamification) | Foundational | US3, US4 |
| US6 (Voice) | Foundational | US7, US8, US9 |
| US7 (Telegram) | US1, US2 (for tutoring) | US6, US8, US9 |
| US8 (Export) | US5 (for gamification data) | US6, US7, US9 |
| US9 (REST API) | US1, US2 (for tutoring) | US6, US7, US8 |

### Within Each User Story

1. Create module __init__.py
2. Core logic files (can parallel if different files)
3. Integration with existing system
4. UI components
5. Final integration in unified_app.py

---

## Parallel Execution Examples

### P1 Stories (Can run simultaneously after Phase 2)

```bash
# Developer A: Streaming (US1)
T020-T026

# Developer B: Tools (US2)
T027-T033

# Developer C: Performance (US10)
T034-T041
```

### P2 Stories (Can run simultaneously)

```bash
# Developer A: Dashboard (US3)
T042-T048

# Developer B: Spaced Repetition (US4)
T049-T055

# Developer C: Gamification (US5)
T056-T064
```

### P3 Stories (Can run simultaneously)

```bash
# Developer A: Voice (US6)
T065-T071

# Developer B: Telegram (US7)
T072-T079

# Developer C: Export (US8)
T080-T086

# Developer D: REST API (US9)
T087-T094
```

---

## Implementation Strategy

### MVP First (P1 Stories Only)

1. Complete Phase 1: Setup (T001-T008)
2. Complete Phase 2: Foundational (T009-T019)
3. Complete Phase 3: US1 Streaming (T020-T026)
4. **VALIDATE**: Test streaming independently
5. Complete Phase 4: US2 Tools (T027-T033)
6. **VALIDATE**: Test tools independently
7. Complete Phase 5: US10 Performance (T034-T041)
8. **VALIDATE**: Test caching and performance
9. **MVP COMPLETE** - Core tutoring with streaming, tools, optimizations

### Incremental Delivery

| Milestone | Stories | Value Delivered |
|-----------|---------|-----------------|
| MVP | US1, US2, US10 | Fast, accurate tutoring with tools |
| v1.1 | +US3, US5 | Dashboard and gamification |
| v1.2 | +US4 | Spaced repetition for retention |
| v1.3 | +US6 | Voice accessibility |
| v1.4 | +US7, US9 | Telegram and API integrations |
| v1.5 | +US8 | Export/import for portability |

---

## Task Summary

| Phase | Tasks | Parallel Tasks |
|-------|-------|----------------|
| 1. Setup | 8 | 6 |
| 2. Foundational | 11 | 9 |
| 3. US1 Streaming | 7 | 0 |
| 4. US2 Tools | 7 | 3 |
| 5. US10 Performance | 8 | 4 |
| 6. US3 Dashboard | 7 | 3 |
| 7. US4 Spaced Rep | 7 | 2 |
| 8. US5 Gamification | 9 | 4 |
| 9. US6 Voice | 7 | 2 |
| 10. US7 Telegram | 8 | 4 |
| 11. US8 Export | 7 | 3 |
| 12. US9 REST API | 8 | 5 |
| 13. Polish | 9 | 4 |
| **Total** | **103** | **49 (48%)** |

---

## Notes

- [P] tasks can run in parallel (different files, no blocking dependencies)
- [USx] label maps task to specific user story
- Complete Foundational phase before ANY user story work
- MVP = US1 + US2 + US10 (streaming, tools, performance)
- Each user story checkpoint enables independent testing
- Commit after each task or logical group
