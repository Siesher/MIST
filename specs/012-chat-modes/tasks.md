# Tasks: Universal Chat Modes

**Input**: Design documents from `/specs/012-chat-modes/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Backend and frontend type definitions shared across all modes

- [x] T001 Add ChatMode enum and ModeConfig dataclass to backend/app/schemas/chat.py
- [x] T002 [P] Add ChatMode TypeScript type and MODES constant to frontend/src/types/api.ts
- [x] T003 [P] Add three mode-specific system prompts (CHAT_MODE_SYSTEM, GUIDED_LEARNING_SYSTEM, TASK_GENERATOR_SYSTEM) to src/models/prompts.py
- [x] T004 Add MODE_CONFIGS dictionary mapping ChatMode to ModeConfig in backend/app/services/orchestrator_service.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Session model and orchestrator must support mode before any user story can work

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Add `mode: str = "guided_learning"` field to StoredSession dataclass in backend/app/services/orchestrator_service.py
- [x] T006 Update `create_session()` in backend/app/services/orchestrator_service.py to accept and store mode parameter
- [x] T007 Update `process_message_stream()` in backend/app/services/orchestrator_service.py to select system prompt based on session mode using MODE_CONFIGS
- [x] T008 Update `process_message()` in backend/app/services/orchestrator_service.py to select system prompt based on session mode
- [x] T009 Add `mode` field to CreateSessionRequest schema in backend/app/schemas/chat.py
- [x] T010 Update POST /api/v1/sessions endpoint in backend/app/api/v1/sessions.py to pass mode to create_session()
- [x] T011 Add mode to session state in Zustand store (add `mode` to SessionState interface) in frontend/src/store/chatStore.ts

**Checkpoint**: Foundation ready — mode is stored and affects prompt selection

---

## Phase 3: User Story 1 — Mode Switching UI (Priority: P1) MVP

**Goal**: Users can see and switch between three modes via dropdown in chat interface

**Independent Test**: Click mode dropdown, verify three options appear. Select each, verify visual indicator changes.

### Implementation for User Story 1

- [x] T012 [US1] Create ModeSelector dropdown component in frontend/src/components/chat/ModeSelector.tsx with three modes, icons (MessageCircle/GraduationCap/FileText), color indicators, and onChange callback
- [x] T013 [US1] Add `setMode` action to Zustand chatStore that updates session mode and sends PATCH to backend in frontend/src/store/chatStore.ts
- [x] T014 [US1] Integrate ModeSelector into ChatInput component — place dropdown left of textarea in frontend/src/components/chat/ChatInput.tsx
- [x] T015 [US1] Update ChatInput placeholder text dynamically based on selected mode using MODES constant in frontend/src/components/chat/ChatInput.tsx
- [x] T016 [US1] Add PATCH /api/v1/sessions/{session_id}/mode endpoint in backend/app/api/v1/sessions.py that updates StoredSession.mode and returns ChangeModeResponse
- [x] T017 [US1] Handle `mode_change` WebSocket message type in backend/app/api/v1/websocket.py — update session mode and respond with `mode_changed` confirmation
- [x] T018 [US1] Handle `mode_changed` WebSocket server message in frontend/src/hooks/useChat.ts — update store mode and placeholder

**Checkpoint**: Mode selector visible, clickable. Mode persists per session. Visual feedback works.

---

## Phase 4: User Story 2 — Free Chat Mode (Priority: P1)

**Goal**: In Chat mode, assistant responds directly without Socratic constraints

**Independent Test**: Switch to "Обычный чат", ask "Как работает нейросеть?" — verify direct helpful answer, not guiding questions.

### Implementation for User Story 2

- [x] T019 [US2] Write CHAT_MODE_SYSTEM prompt in src/models/prompts.py — friendly Russian assistant, direct answers, LaTeX for math, no Socratic constraints
- [x] T020 [US2] Update orchestrator pipeline in src/agents/orchestrator.py: when mode is `chat`, skip profiler/planner/verifier stages — use only tutor with chat prompt
- [x] T021 [US2] In chat mode, make `process_message_stream()` in backend/app/services/orchestrator_service.py yield plain text tokens (not JSON move format)
- [x] T022 [US2] Ensure ChatContainer in frontend/src/components/chat/ChatContainer.tsx renders chat-mode responses as plain markdown (no move_type parsing)

**Checkpoint**: Chat mode delivers direct, helpful answers. No Socratic questioning. Streaming works.

---

## Phase 5: User Story 3 — Guided Learning Mode (Priority: P1)

**Goal**: Guided Learning mode preserves existing Socratic tutor behavior exactly

**Independent Test**: Switch to "Guided Learning", ask about derivatives — verify tutor asks guiding questions, provides hints on request.

### Implementation for User Story 3

- [x] T023 [US3] Rename existing SOCRATIC_TUTOR_SYSTEM to GUIDED_LEARNING_SYSTEM in src/models/prompts.py and update all references
- [x] T024 [US3] Ensure full orchestrator pipeline (profiler → planner → tutor → verifier) runs when mode is `guided_learning` in src/agents/orchestrator.py
- [x] T025 [US3] Verify hint request flow works correctly when mode is `guided_learning` — test in backend/app/api/v1/websocket.py that hint_request is only processed in guided mode

**Checkpoint**: Guided Learning works identically to current behavior. Hints, moves, and Socratic flow preserved.

---

## Phase 6: User Story 4 — Task Generation Mode (Priority: P2)

**Goal**: In Task Generator mode, user specifies topic/difficulty and receives generated problems with solutions

**Independent Test**: Switch to "Генерация задач", ask "3 задачи по интегралам, средняя сложность" — verify problems generated with solutions.

### Implementation for User Story 4

- [x] T026 [US4] Write TASK_GENERATOR_SYSTEM prompt in src/models/prompts.py — generates problems by topic/difficulty, includes step-by-step solutions, Russian language
- [x] T027 [US4] Update orchestrator pipeline in src/agents/orchestrator.py: when mode is `task_generator`, skip profiler/verifier — use tutor with task generation prompt, optionally query RAG for problem templates
- [x] T028 [US4] In task_generator mode, make `process_message_stream()` in backend/app/services/orchestrator_service.py format output as structured problems (markdown with numbered problems and collapsible solutions)
- [x] T029 [US4] Ensure ChatContainer in frontend/src/components/chat/ChatContainer.tsx renders task generation output with proper formatting (collapsible solution sections)

**Checkpoint**: Task Generator produces well-formatted problems. Solutions are accessible. Topic/difficulty respected.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases, UX improvements, validation

- [x] T030 Handle mode switch during active streaming in frontend/src/hooks/useChat.ts — cancel current stream before switching mode
- [x] T031 [P] Persist user's preferred mode to localStorage in frontend/src/store/chatStore.ts — restore on page reload
- [x] T032 [P] Add mode indicator badge to session list sidebar showing current mode per session in frontend/src/components/layout/Sidebar.tsx
- [x] T033 Add mode-specific welcome message when mode changes mid-session in backend/app/api/v1/websocket.py (sends message from change_mode result)
- [ ] T034 Run quickstart.md validation — test all three modes end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 Mode Switching (Phase 3)**: Depends on Phase 2 — BLOCKS US2/US3/US4 (need dropdown to select modes)
- **US2 Chat Mode (Phase 4)**: Depends on Phase 3 — can run in parallel with US3, US4
- **US3 Guided Learning (Phase 5)**: Depends on Phase 3 — can run in parallel with US2, US4
- **US4 Task Generator (Phase 6)**: Depends on Phase 3 — can run in parallel with US2, US3
- **Polish (Phase 7)**: Depends on all user stories complete

### Within Each User Story

- Backend changes before frontend changes
- Prompts before orchestrator logic
- Orchestrator logic before API endpoints
- API endpoints before frontend integration

### Parallel Opportunities

Within Phase 1:
```
T002 (frontend types) || T003 (prompts) — different files
```

Within Phase 4-6 (after Phase 3 complete):
```
US2 (Chat Mode) || US3 (Guided Learning) || US4 (Task Generator) — independent modes
```

Within Phase 7:
```
T031 (localStorage) || T032 (sidebar badge) — different files
```

---

## Implementation Strategy

### MVP First (Phase 1 + 2 + 3)

1. Complete Phase 1: Shared types and enums
2. Complete Phase 2: Session mode storage and prompt selection
3. Complete Phase 3: Mode selector UI
4. **STOP and VALIDATE**: Dropdown works, mode persists, prompt changes
5. This alone delivers value — users can switch modes even if Chat/TaskGen prompts are basic

### Incremental Delivery

1. Phase 1 + 2 + 3 → Mode switching works (MVP)
2. Add Phase 4 (US2) → Chat mode with proper direct-answer behavior
3. Add Phase 5 (US3) → Verify Guided Learning preserved
4. Add Phase 6 (US4) → Task generation operational
5. Phase 7 → Polish and edge cases

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Total: 34 tasks across 7 phases
- Default mode: `guided_learning` (backward compatible)
- All modes use same LLM — only prompts and pipeline stages differ
