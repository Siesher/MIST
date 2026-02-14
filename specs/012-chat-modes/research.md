# Research: Universal Chat Modes

**Feature**: 012-chat-modes
**Date**: 2026-02-05

## Research Tasks Completed

### 1. Existing Mode Infrastructure

**Question**: Does MITS already have mode support?

**Finding**: Yes, partial support exists:
- `OrchestratorMode` enum in `src/agents/orchestrator.py` (lines 73-77):
  - `FULL` - All agents (default)
  - `FAST` - Only tutor + verifier
  - `DIAGNOSTIC` - Profile + planner only
- This is for pipeline optimization, not user-facing mode selection

**Decision**: Create new `ChatMode` enum for user-facing modes, separate from `OrchestratorMode`

**Rationale**: Separation of concerns - user modes (chat, guided, tasks) are different from pipeline optimization modes

### 2. System Prompt Architecture

**Question**: Where are system prompts defined and how to add mode-specific prompts?

**Finding**: Prompts defined in `src/models/prompts.py`:
- `SOCRATIC_TUTOR_SYSTEM` (lines 12-50) - Current Socratic prompt
- `TUTOR_RESPONSE_PROMPT` (lines 53-85) - Dynamic template
- `TASK_GENERATOR_SYSTEM` (lines 92+) - Task generation

**Decision**: Add three mode-specific prompts:
1. `CHAT_MODE_SYSTEM` - General helpful assistant
2. `GUIDED_LEARNING_SYSTEM` - Existing Socratic prompt (rename)
3. `TASK_GENERATOR_SYSTEM` - Existing task generation prompt

**Rationale**: Centralized prompt management, easy to modify per mode

### 3. Session Storage

**Question**: How to persist mode per session?

**Finding**: `StoredSession` dataclass in `orchestrator_service.py`:
- Currently has: id, topic, difficulty, status, hints_used, attempts, etc.
- Missing: mode field

**Decision**: Add `mode: str = "guided_learning"` to StoredSession
- Default to guided_learning for backward compatibility
- Store as string enum value

**Rationale**: Simple addition, no schema migration needed for in-memory storage

### 4. Frontend State Management

**Question**: How to manage mode in frontend?

**Finding**: Zustand store in `frontend/src/store/chatStore.ts`:
- Per-session message storage: `messages: Record<string, Message[]>`
- Session states: `sessionStates: Record<string, SessionState>`

**Decision**: Add mode to session state:
```typescript
interface SessionState {
  // existing...
  mode: ChatMode;
}
```

**Rationale**: Mode is session-scoped, fits existing pattern

### 5. Mode Change API

**Question**: How should mode changes be communicated?

**Finding**: Current endpoints:
- `POST /api/v1/sessions` - Create session
- `POST /api/v1/chat/{id}/message` - Send message
- WebSocket for streaming

**Decision**:
1. Add `mode` field to `CreateSessionRequest`
2. Add `PATCH /api/v1/sessions/{id}/mode` endpoint for mode changes
3. WebSocket message type for mode change: `{"type": "mode_change", "mode": "chat"}`

**Rationale**: REST for explicit changes, WS for real-time sync

### 6. UI Component Design

**Question**: Where to place mode selector?

**Finding**: ChatInput component has space for additional controls (hint button exists)

**Decision**: Add dropdown left of input field:
```
[Mode: Guided Learning ▾] [                Input field                ] [Send]
```

**Alternatives Considered**:
- Sidebar toggle: Rejected - less discoverable
- Header dropdown: Rejected - too far from input context
- Modal selector: Rejected - interrupts flow

**Rationale**: Inline with input maintains chat context, always visible

### 7. Mode-Specific Behaviors

**Question**: What should each mode do differently?

**Finding**: Based on spec and existing code analysis:

| Behavior | Chat | Guided Learning | Task Generator |
|----------|------|-----------------|----------------|
| System Prompt | Helpful assistant | Socratic tutor | Task creator |
| Use RAG | Optional | Required | For problems |
| Track hints | No | Yes | No |
| JSON response | No | Yes (move type) | Yes (task format) |
| Allow direct answers | Yes | No | N/A |

**Decision**: Implement mode-specific prompt selection in orchestrator service

### 8. Prompt Designs

**Chat Mode System Prompt**:
```
Ты — умный и дружелюбный ассистент. Отвечай на любые вопросы прямо и полезно.
Используй LaTeX для математических формул ($...$).
Отвечай на русском языке.
```

**Guided Learning (existing, enhanced)**:
```
Ты — сократический репетитор по математике и STEM.
НИКОГДА не давай прямых ответов. Веди ученика через вопросы.
[Existing Socratic prompt content]
```

**Task Generator (existing, enhanced)**:
```
Ты — генератор учебных задач по математике и STEM.
Создавай задачи заданной сложности с пошаговыми решениями.
[Existing task generation prompt]
```

## Summary of Decisions

| Item | Decision | Impact |
|------|----------|--------|
| Mode enum | New `ChatMode` separate from `OrchestratorMode` | Backend schema |
| Storage | Add `mode` field to `StoredSession` | Minimal change |
| API | `PATCH /sessions/{id}/mode` + WS message | New endpoint |
| UI | Dropdown in ChatInput area | New component |
| Prompts | Three distinct system prompts | Prompt file update |
| Default | Guided Learning mode | Backward compatible |
