# Quickstart: Universal Chat Modes

**Feature**: 012-chat-modes

## Overview

Adds a mode selector dropdown to the chat interface with three modes:
- **Обычный чат** (Chat) - free-form conversation
- **Guided Learning** - Socratic tutoring
- **Генерация задач** (Task Generator) - problem generation

## Key Changes

### Backend
1. `ChatMode` enum added to schemas
2. `StoredSession` gains `mode` field (default: `guided_learning`)
3. New `PATCH /api/v1/sessions/{id}/mode` endpoint
4. WebSocket handles `mode_change` message type
5. Orchestrator selects system prompt based on session mode

### Frontend
1. New `ModeSelector` dropdown component
2. `ChatInput` integrates mode selector left of text field
3. Zustand store tracks `mode` per session
4. Mode change sends WS message, updates placeholder text

## Quick Test

1. Start backend: `cd backend && uvicorn app.main:app --reload --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Open http://localhost:3000, create session
4. Click mode dropdown (defaults to "Guided Learning")
5. Switch to "Обычный чат", ask "How do neural networks work?"
6. Verify direct answer (not Socratic questions)
7. Switch to "Генерация задач", ask "3 задачи по производным"
8. Verify problems are generated with solutions

## Dependencies

- No new packages required
- Uses existing Ollama LLM client
- Uses existing WebSocket infrastructure
