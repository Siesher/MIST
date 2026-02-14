# Implementation Plan: Next.js UI Migration

**Branch**: `011-nextjs-ui-migration` | **Date**: 2026-02-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/011-nextjs-ui-migration/spec.md`

## Summary

Migrate MITS tutoring interface from Gradio to a modern FastAPI + Next.js architecture with chat-focused design. The backend wraps existing MITS core (agents, RAG, memory) with REST/WebSocket endpoints. The frontend provides a ChatGPT-like interface with streaming responses, math rendering, session management, and responsive design.

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript 5.x (frontend)
**Primary Dependencies**:
- Backend: FastAPI, python-jose (JWT), websockets, uvicorn
- Frontend: Next.js 14, React 18, Tailwind CSS, shadcn/ui, Zustand, KaTeX
**Storage**: SQLite (existing), browser localStorage (preferences)
**Testing**: pytest (backend), Jest + React Testing Library (frontend)
**Target Platform**: Modern browsers (Chrome, Firefox, Safari, Edge), Windows/Linux server
**Project Type**: Web application (frontend + backend)
**Performance Goals**: <3s first token response, <2s page load, 60fps UI
**Constraints**: Backend on same machine as Ollama, RTX 2080 8GB VRAM limit unchanged
**Scale/Scope**: Single user (diploma demo), ~10 screens, ~50 components

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Socratic Pedagogy | PASS | UI change only - core tutoring logic unchanged |
| II. Multi-Agent Architecture | PASS | Agents accessed via service layer, no bypass |
| III. Knowledge-Grounded Responses | PASS | RAG integration unchanged |
| IV. Hardware Constraint Compliance | PASS | No VRAM impact - UI runs separately |
| V. Metrics-Driven Quality | PASS | Session logging preserved, metrics unchanged |
| VI. STEM Domain Coverage | PASS | All subjects remain available |
| UI Framework (Gradio 4.x) | **VIOLATION** | Replacing with Next.js - see Complexity Tracking |

## Project Structure

### Documentation (this feature)

```text
specs/011-nextjs-ui-migration/
├── plan.md              # This file
├── research.md          # Phase 0: Technology decisions
├── data-model.md        # Phase 1: API schemas
├── quickstart.md        # Phase 1: Development setup
├── contracts/           # Phase 1: OpenAPI specs
│   ├── api.yaml         # REST API contract
│   └── websocket.md     # WebSocket message formats
└── tasks.md             # Phase 2: Implementation tasks
```

### Source Code (repository root)

```text
# Existing MITS core (unchanged)
src/
├── agents/              # Orchestrator, Tutor, Profiler, etc.
├── models/              # LLM client
├── knowledge/           # RAG, few-shot, CoT
├── memory/              # Session persistence
├── inference/           # Cache, metrics, A/B testing
└── data/                # Schemas

# New: FastAPI backend
backend/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI entry point
│   ├── config.py        # Settings
│   ├── dependencies.py  # DI container
│   ├── api/
│   │   └── v1/
│   │       ├── router.py
│   │       ├── sessions.py
│   │       ├── chat.py
│   │       ├── tasks.py
│   │       ├── students.py
│   │       └── websocket.py
│   ├── schemas/         # Pydantic models for API
│   └── services/        # Business logic wrappers
├── tests/
└── requirements.txt

# New: Next.js frontend
frontend/
├── src/
│   ├── app/             # Next.js App Router
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── chat/
│   │   │   └── [sessionId]/
│   │   ├── profile/
│   │   └── settings/
│   ├── components/
│   │   ├── ui/          # shadcn/ui base
│   │   ├── chat/        # Message, ChatInput, etc.
│   │   └── layout/      # Sidebar, Header
│   ├── hooks/           # useChat, useWebSocket
│   ├── store/           # Zustand stores
│   ├── lib/             # API client, utils
│   └── types/           # TypeScript interfaces
├── public/
├── package.json
├── tailwind.config.ts
└── tsconfig.json

# Existing interface (deprecated but functional)
interface/
├── gradio_app.py        # Keep for fallback
└── api.py               # Reference for new backend
```

**Structure Decision**: Web application pattern with separate frontend/backend directories. Existing `src/` remains unchanged - backend imports from it via service layer.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Gradio → Next.js | Professional diploma presentation; modern UX; streaming support; mobile responsiveness | Gradio cannot provide ChatGPT-like streaming UI; limited customization; no proper mobile support |

**Justification**: The constitution specifies Gradio 4.x as the UI framework. This migration is justified because:
1. **Diploma requirement**: Modern, professional UI for academic defense presentation
2. **Technical limitation**: Gradio lacks proper WebSocket streaming for token-by-token display
3. **User experience**: Chat-focused design not achievable with Gradio's form-based paradigm
4. **Maintainability**: React ecosystem provides better component architecture
5. **Backward compatibility**: Gradio app remains functional during transition

The core MITS logic (agents, RAG, memory) remains completely unchanged. Only the presentation layer is replaced.
