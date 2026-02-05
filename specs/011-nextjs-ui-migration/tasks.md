# Tasks: Next.js UI Migration

**Feature**: 011-nextjs-ui-migration
**Created**: 2026-02-04
**Plan**: [plan.md](plan.md)

## Phase 1: Backend Setup

- [x] T001: Create backend directory structure and requirements.txt
  - Files: `backend/`, `backend/requirements.txt`, `backend/app/__init__.py`
- [x] T002: Create FastAPI main app with CORS and error handling
  - Files: `backend/app/main.py`, `backend/app/config.py`
- [x] T003: Create API schemas (Pydantic models for requests/responses) [P]
  - Files: `backend/app/schemas/`
- [x] T004: Create OrchestratorService wrapper [P]
  - Files: `backend/app/services/orchestrator_service.py`
- [x] T005: Create session endpoints (CRUD)
  - Files: `backend/app/api/v1/sessions.py`
  - Depends: T002, T003, T004
- [x] T006: Create chat endpoints (message, hint, solution)
  - Files: `backend/app/api/v1/chat.py`
  - Depends: T002, T003, T004
- [x] T007: Create task endpoints (topics, generate, recommended)
  - Files: `backend/app/api/v1/tasks.py`
  - Depends: T002, T003
- [x] T008: Create student endpoints (profile, analytics, knowledge)
  - Files: `backend/app/api/v1/students.py`
  - Depends: T002, T003
- [x] T009: Create API router and wire all endpoints
  - Files: `backend/app/api/v1/router.py`
  - Depends: T005, T006, T007, T008
- [x] T010: Create WebSocket endpoint for streaming
  - Files: `backend/app/api/v1/websocket.py`
  - Depends: T004

## Phase 2: Frontend Setup

- [x] T011: Initialize Next.js project with TypeScript and Tailwind
  - Files: `frontend/`
- [x] T012: Install and configure shadcn/ui components
  - Depends: T011
- [x] T013: Create TypeScript types matching API schemas [P]
  - Files: `frontend/src/types/api.ts`
- [x] T014: Create API client library [P]
  - Files: `frontend/src/lib/api.ts`
- [x] T015: Create Zustand chat store
  - Files: `frontend/src/store/chatStore.ts`
  - Depends: T013

## Phase 3: Frontend Core Components

- [x] T016: Create root layout with theme provider
  - Files: `frontend/src/app/layout.tsx`, `frontend/src/app/globals.css`
  - Depends: T011
- [x] T017: Create Sidebar component with session list
  - Files: `frontend/src/components/layout/Sidebar.tsx`
  - Depends: T012, T015
- [x] T018: Create MathRenderer component (KaTeX)
  - Files: `frontend/src/components/chat/MathRenderer.tsx`
  - Depends: T011
- [x] T019: Create Message component
  - Files: `frontend/src/components/chat/Message.tsx`
  - Depends: T018
- [x] T020: Create ChatInput component
  - Files: `frontend/src/components/chat/ChatInput.tsx`
  - Depends: T012
- [x] T021: Create ChatContainer component
  - Files: `frontend/src/components/chat/ChatContainer.tsx`
  - Depends: T019, T020, T015
- [x] T022: Create chat page with session routing
  - Files: `frontend/src/app/chat/[sessionId]/page.tsx`, `frontend/src/app/page.tsx`
  - Depends: T016, T017, T021

## Phase 4: WebSocket & Streaming

- [x] T023: Create useWebSocket hook
  - Files: `frontend/src/hooks/useWebSocket.ts`
  - Depends: T013
- [x] T024: Create useChat hook integrating REST + WebSocket
  - Files: `frontend/src/hooks/useChat.ts`
  - Depends: T014, T015, T023
- [x] T025: Add streaming message display to ChatContainer
  - Depends: T021, T024

## Phase 5: Additional Features

- [x] T026: Create profile page with mastery charts
  - Files: `frontend/src/app/profile/page.tsx`
- [x] T027: Create settings page with theme toggle
  - Files: `frontend/src/app/settings/page.tsx`
- [x] T028: Add dark/light theme support via CSS variables
  - Depends: T016
- [x] T029: Add mobile responsive design
  - Depends: T017, T022

## Phase 6: Polish

- [x] T030: Add error handling and loading states
- [x] T031: Add keyboard shortcuts (Enter to send, Shift+Enter new line)
  - Depends: T020
- [x] T032: Update .gitignore for frontend/backend artifacts
