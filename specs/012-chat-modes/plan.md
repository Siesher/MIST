# Implementation Plan: Universal Chat Modes

**Branch**: `012-chat-modes` | **Date**: 2026-02-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/012-chat-modes/spec.md`

## Summary

Add three selectable chat modes to MITS: Free Chat (general assistant), Guided Learning (Socratic tutor), and Task Generator. Users select mode via dropdown in chat input area. Each mode uses distinct system prompts while sharing the same LLM and session infrastructure.

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, Next.js 14, Zustand, Ollama
**Storage**: In-memory sessions (StoredSession dataclass), SQLite for persistence
**Testing**: pytest (backend), vitest (frontend)
**Target Platform**: Web application (localhost)
**Project Type**: Web application (frontend + backend)
**Performance Goals**: Mode switch <500ms, no page reload
**Constraints**: RTX 2080 8GB VRAM, single LLM instance
**Scale/Scope**: Single user, 3 modes, ~10 files modified

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Socratic Pedagogy | **PARTIAL** | Guided Learning mode preserves Socratic method; Chat mode intentionally bypasses it |
| II. Multi-Agent Architecture | **PASS** | All modes route through Orchestrator |
| III. Knowledge-Grounded | **PASS** | Guided Learning uses RAG; Chat mode may skip for non-math |
| IV. Hardware Constraints | **PASS** | No new models; same VRAM footprint |
| V. Metrics-Driven | **PASS** | Metrics apply to Guided Learning mode |
| VI. STEM Domain Coverage | **PASS** | Task Generator covers all STEM topics |

**Partial Compliance Justification**: Principle I (Socratic Pedagogy) is marked NON-NEGOTIABLE, but the spec explicitly adds Chat mode for non-pedagogical use cases. This is justified because:
1. Chat mode is opt-in, not default (Guided Learning remains default)
2. Chat mode serves different user intent (general questions, not learning)
3. The Socratic principle applies to tutoring contexts, not all interactions

## Project Structure

### Documentation (this feature)

```text
specs/012-chat-modes/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/v1/
│   │   ├── chat.py           # Add mode change endpoint
│   │   ├── sessions.py       # Update create with mode
│   │   └── websocket.py      # Handle mode in WS
│   ├── schemas/
│   │   └── chat.py           # Add ChatMode enum, update schemas
│   └── services/
│       └── orchestrator_service.py  # Add mode to StoredSession
└── tests/
    └── test_chat_modes.py    # New tests

frontend/
├── src/
│   ├── components/
│   │   └── chat/
│   │       ├── ChatInput.tsx      # Add mode selector dropdown
│   │       ├── ModeSelector.tsx   # New component
│   │       └── ChatContainer.tsx  # Pass mode to input
│   ├── store/
│   │   └── chatStore.ts           # Add mode state
│   ├── types/
│   │   └── api.ts                 # Add ChatMode type
│   └── hooks/
│       └── useChat.ts             # Send mode with messages
└── tests/
    └── chat-modes.test.ts         # New tests

src/
├── models/
│   └── prompts.py                 # Add mode-specific prompts
└── agents/
    └── orchestrator.py            # Respect mode in pipeline
```

**Structure Decision**: Web application structure with existing backend/frontend split. Mode logic added to orchestrator service and schemas.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Chat mode bypasses Socratic method | User requested general chat capability | Forcing Socratic on all queries frustrates users asking non-learning questions |
