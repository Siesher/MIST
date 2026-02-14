# Research: Next.js UI Migration

**Feature**: 011-nextjs-ui-migration
**Date**: 2026-02-04

## 1. FastAPI Backend Architecture

### Decision: Service Layer Pattern

**Rationale**: Wrap existing MITS agents in thin service classes to avoid duplicating business logic.

**Implementation**:
```python
# backend/app/services/orchestrator_service.py
from src.agents.orchestrator import AgentOrchestrator

class OrchestratorService:
    def __init__(self):
        self._orchestrator = AgentOrchestrator()

    async def process_message(self, session_id: str, message: str) -> TurnResult:
        context = TurnContext(student_input=message, ...)
        return self._orchestrator.process_turn(context, session_id)
```

**Alternatives Considered**:
- Direct agent imports in routes: Rejected - tight coupling, harder to test
- Full rewrite of agents: Rejected - unnecessary, core logic works well

### Decision: WebSocket for Streaming

**Rationale**: Real-time token-by-token display requires bidirectional communication.

**Implementation**:
- FastAPI WebSocket endpoint at `/api/v1/ws/{session_id}`
- Uses existing `LLMClient.chat_stream()` generator
- Message format: JSON with `type` field (token, complete, error)

**Alternatives Considered**:
- Server-Sent Events (SSE): Simpler but unidirectional; harder to handle reconnection
- HTTP polling: Too slow for token streaming; poor UX

### Decision: No Authentication (MVP)

**Rationale**: Single-user diploma demo doesn't require auth complexity.

**Implementation**:
- Session identified by UUID in URL/localStorage
- No JWT tokens for MVP
- Can add auth layer later without API changes

**Alternatives Considered**:
- Full JWT auth: Overkill for demo; adds development time
- Basic auth: No benefit over session-based for single user

---

## 2. Next.js Frontend Architecture

### Decision: App Router (Next.js 14)

**Rationale**: Modern routing with React Server Components support, better layouts.

**Implementation**:
```
src/app/
├── layout.tsx          # Root layout with providers
├── page.tsx            # Redirect to /chat
├── chat/
│   ├── layout.tsx      # Chat layout with sidebar
│   ├── page.tsx        # New chat
│   └── [sessionId]/
│       └── page.tsx    # Existing session
├── profile/
│   └── page.tsx
└── settings/
    └── page.tsx
```

**Alternatives Considered**:
- Pages Router: Legacy, missing RSC benefits
- Remix: Good but less ecosystem support than Next.js

### Decision: Zustand for State Management

**Rationale**: Lightweight, simple API, excellent TypeScript support.

**Implementation**:
```typescript
// src/store/chatStore.ts
export const useChatStore = create<ChatState>()((set) => ({
  messages: {},
  addMessage: (sessionId, message) => set((state) => ({
    messages: { ...state.messages, [sessionId]: [...(state.messages[sessionId] || []), message] }
  }))
}));
```

**Alternatives Considered**:
- Redux Toolkit: Overkill for app scale; more boilerplate
- Jotai: Similar to Zustand but less intuitive for this use case
- React Context: No persistence, prop drilling issues

### Decision: shadcn/ui Component Library

**Rationale**: Tailwind-native, copy-paste components, fully customizable.

**Implementation**:
- Install base components: Button, Input, Card, ScrollArea, Dialog
- Customize theme colors for dark/light modes
- No runtime dependency - components owned by project

**Alternatives Considered**:
- Material UI: Heavy bundle, opinionated styling
- Chakra UI: Good but not Tailwind-native
- Radix UI only: Need to style everything from scratch

### Decision: KaTeX for Math Rendering

**Rationale**: Faster than MathJax, sufficient for our math notation needs.

**Implementation**:
```typescript
// src/components/chat/MathRenderer.tsx
import katex from 'katex';

function renderMath(content: string): string {
  return content.replace(/\$(.+?)\$/g, (_, tex) =>
    katex.renderToString(tex, { throwOnError: false })
  );
}
```

**Alternatives Considered**:
- MathJax: Slower rendering, larger bundle
- Custom parser: Unnecessary complexity

---

## 3. API Contract Design

### Decision: RESTful Conventions

**Rationale**: Standard patterns, easy to understand and document.

**Endpoints Summary**:
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | /api/v1/sessions | Create session |
| GET | /api/v1/sessions | List sessions |
| GET | /api/v1/sessions/{id} | Get session |
| DELETE | /api/v1/sessions/{id} | Delete session |
| POST | /api/v1/chat/{id}/message | Send message (REST) |
| WS | /api/v1/ws/{id} | Chat stream (WebSocket) |
| GET | /api/v1/chat/{id}/hint | Get hint |
| GET | /api/v1/tasks/topics | List topics |
| POST | /api/v1/tasks/generate | Generate task |
| GET | /api/v1/students/me/profile | Get profile |
| GET | /api/v1/students/me/analytics | Get analytics |

### Decision: Pydantic v2 Schemas

**Rationale**: Already used in MITS core; consistent validation.

**Implementation**:
- Extend existing schemas from `src/data/schemas.py`
- Add API-specific wrappers for request/response

---

## 4. Real-time Communication

### Decision: Native WebSocket with JSON Messages

**Rationale**: Simple, no additional dependencies, full control.

**Message Types**:

**Client → Server**:
```json
{ "type": "message", "content": "2x", "timestamp": 1706745600000 }
{ "type": "hint_request" }
{ "type": "typing_start" }
```

**Server → Client**:
```json
{ "type": "token", "content": "Отлично", "is_thinking": false }
{ "type": "response_complete", "response": {...}, "session_state": {...} }
{ "type": "error", "code": "LLM_UNAVAILABLE", "message": "..." }
```

**Alternatives Considered**:
- Socket.IO: Additional abstraction layer not needed
- GraphQL Subscriptions: Overkill for single subscription type

---

## 5. Development Environment

### Decision: Separate Package Managers

**Rationale**: Python (pip) and Node.js (npm) are standard for each ecosystem.

**Setup**:
```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend && npm install
npm run dev
```

### Decision: Concurrent Development Server

**Rationale**: Need both servers running during development.

**Implementation**: Use `concurrently` or separate terminals
- Backend: http://localhost:8000
- Frontend: http://localhost:3000
- Frontend proxies API calls to backend

---

## 6. Styling and Theming

### Decision: CSS Variables for Theme

**Rationale**: Runtime theme switching without JavaScript reload.

**Implementation**:
```css
:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
}

.dark {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
}
```

**Color Palette** (matching existing claude.css):
- Background: #212121 (dark), #ffffff (light)
- Accent: #d97706 (orange/gold)
- Success: #10b981 (green)
- Error: #ef4444 (red)

---

## 7. Error Handling

### Decision: Graceful Degradation

**Rationale**: User should see helpful messages, not technical errors.

**Implementation**:
- Backend: Return structured error responses with codes
- Frontend: Display user-friendly messages
- Fallback: If WebSocket fails, offer REST alternative

**Error Response Format**:
```json
{
  "error": {
    "code": "OLLAMA_UNAVAILABLE",
    "message": "Репетитор временно недоступен. Проверьте, запущен ли Ollama.",
    "retry_after": 5
  }
}
```

---

## 8. Performance Considerations

### Decision: Message Virtualization for Long Conversations

**Rationale**: Hundreds of messages could slow down rendering.

**Implementation**:
- Use `react-virtual` or similar for message list
- Only render visible messages + buffer
- Trigger at 100+ messages threshold

### Decision: Debounced Input

**Rationale**: Prevent accidental double-sends.

**Implementation**:
- Disable send button during request
- 300ms debounce on typing indicator updates

---

## Summary of Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Backend Framework | FastAPI | Async, WebSocket support, OpenAPI |
| Backend Streaming | Native WebSocket | Full control, no dependencies |
| Frontend Framework | Next.js 14 (App Router) | Modern React, great DX |
| UI Components | shadcn/ui + Tailwind | Customizable, lightweight |
| State Management | Zustand | Simple, TypeScript-friendly |
| Math Rendering | KaTeX | Fast, sufficient coverage |
| API Format | REST + WebSocket | Standard patterns |

All technology choices prioritize simplicity, maintainability, and alignment with existing MITS architecture.
