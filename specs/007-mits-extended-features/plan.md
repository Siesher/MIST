# Implementation Plan: MITS Extended Features

**Branch**: `007-mits-extended-features` | **Date**: 2026-02-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-mits-extended-features/spec.md`

## Summary

Comprehensive enhancement of the Math Intelligent Tutoring System with 17 feature areas across 4 categories:

1. **Core UX** (P1): Streaming responses, tool integration (calculator, web search), performance optimizations
2. **Learning Analytics** (P2): Progress dashboard, spaced repetition (SM-2), gamification (XP, achievements, streaks)
3. **Accessibility** (P3): Voice I/O (Russian), Telegram bot integration
4. **Integration** (P3): REST API, profile export/import, Notion/Obsidian export

Technical approach: Extend existing multi-agent architecture with new services for gamification, spaced repetition, and external integrations while maintaining <6GB VRAM constraint.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- Gradio 4.x (UI + streaming)
- Ollama (LLM inference)
- ChromaDB (RAG vectors)
- sentence-transformers (embeddings)
- python-telegram-bot (Telegram)
- FastAPI (REST API)
- SpeechRecognition + gTTS (voice I/O)
- DuckDuckGo Search (web search tool)
- sympy (calculator tool)
- pydantic (data models)
- structlog (logging)

**Storage**:
- SQLite (student profiles, metrics, gamification)
- ChromaDB (RAG vectors, embedding cache)
- JSON (configs, task banks, skill graph)
- Filesystem (profile exports)

**Testing**: pytest with pytest-asyncio
**Target Platform**: Windows/Linux desktop, web browser
**Project Type**: Single monolith with modular services
**Performance Goals**:
- First token <500ms (streaming)
- Cached responses <200ms
- Batch inference +50% throughput
- Telegram: 100+ concurrent users

**Constraints**:
- RTX 2080 8GB VRAM (max 6GB for inference)
- Russian language support required
- Offline-capable for core tutoring
- Free external services (DuckDuckGo, no paid APIs)

**Scale/Scope**:
- Single-user local deployment initially
- REST API for multi-user expansion

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Socratic Pedagogy | PASS | Features enhance tutoring, don't bypass Socratic method |
| II. Multi-Agent Architecture | PASS | New features integrate with existing orchestrator pipeline |
| III. Knowledge-Grounded Responses | PASS | RAG retriever used for hints, tools supplement not replace |
| IV. Hardware Constraint Compliance | PASS | All features designed for 8GB VRAM; embedding cache reduces load |
| V. Metrics-Driven Quality | PASS | New metrics (streaks, XP) complement existing educational metrics |
| VI. STEM Domain Coverage | PASS | Features apply equally across all STEM domains |

**Pre-Design Gate**: PASSED - All principles satisfied.

## Project Structure

### Documentation (this feature)

```text
specs/007-mits-extended-features/
├── plan.md              # This file
├── research.md          # Phase 0: Technology decisions
├── data-model.md        # Phase 1: Entity definitions
├── quickstart.md        # Phase 1: Setup guide
├── contracts/           # Phase 1: API contracts
│   ├── rest-api.yaml    # OpenAPI spec
│   └── telegram-bot.md  # Bot command reference
└── tasks.md             # Phase 2: Implementation tasks
```

### Source Code (repository root)

```text
src/
├── agents/              # Existing multi-agent system
│   ├── orchestrator.py  # Coordination
│   ├── profiler.py      # Diagnosis
│   ├── planner.py       # Strategy
│   ├── tutor_agent.py   # Main tutoring
│   └── verifier.py      # Quality check
├── models/              # LLM clients
│   ├── llm_client.py    # Ollama client
│   └── client_factory.py
├── knowledge/           # RAG and knowledge
│   ├── rag_retriever.py
│   └── tracer.py        # Knowledge tracing (BKT)
├── memory/              # Session/student memory
│   ├── session_memory.py
│   └── student_memory.py
├── inference/           # Performance optimizations
│   ├── cache.py         # Response cache
│   └── metrics.py
├── tools/               # NEW: Tool integrations
│   ├── __init__.py
│   ├── calculator.py    # Sympy-based calculator
│   ├── web_search.py    # DuckDuckGo search
│   └── knowledge_search.py
├── gamification/        # NEW: XP, achievements, streaks
│   ├── __init__.py
│   ├── xp_system.py
│   ├── achievements.py
│   ├── streaks.py
│   └── levels.py
├── spaced_repetition/   # NEW: SM-2 algorithm
│   ├── __init__.py
│   ├── sm2.py
│   └── scheduler.py
├── voice/               # NEW: Voice I/O
│   ├── __init__.py
│   ├── speech_to_text.py
│   └── text_to_speech.py
├── export/              # NEW: Profile export/import
│   ├── __init__.py
│   ├── json_export.py
│   ├── obsidian_export.py
│   └── notion_export.py
└── config.py

interface/
├── unified_app.py       # Main Gradio app (UPDATE)
├── components/          # NEW: Reusable UI components
│   ├── __init__.py
│   ├── dashboard.py     # Progress dashboard
│   ├── skill_tree.py    # Knowledge graph viz
│   ├── heatmap.py       # Activity heatmap
│   └── achievements.py  # Badge display
└── api/                 # NEW: REST API
    ├── __init__.py
    ├── main.py          # FastAPI app
    ├── routes/
    │   ├── chat.py
    │   ├── profile.py
    │   └── progress.py
    └── auth.py          # JWT authentication

telegram_bot/            # NEW: Telegram integration
├── __init__.py
├── bot.py               # Main bot
├── handlers/
│   ├── commands.py
│   ├── messages.py
│   └── voice.py
└── utils/
    └── latex_render.py

tests/
├── unit/
│   ├── test_tools.py
│   ├── test_gamification.py
│   ├── test_spaced_repetition.py
│   └── test_export.py
├── integration/
│   ├── test_streaming.py
│   ├── test_api.py
│   └── test_telegram.py
└── contract/
    └── test_api_contracts.py

data/
├── knowledge/           # Existing RAG data
├── gamification/        # NEW: Achievement definitions
│   └── achievements.json
└── embeddings_cache/    # NEW: Persistent cache
    └── .gitkeep
```

**Structure Decision**: Extended single-project structure. New modules added as separate packages (`tools/`, `gamification/`, `spaced_repetition/`, `voice/`, `export/`) to maintain modularity. REST API and Telegram bot as separate entry points sharing core services.

## Complexity Tracking

> No constitution violations requiring justification.

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| REST API added | FastAPI alongside Gradio | Needed for third-party integrations; lightweight, shares core services |
| Telegram bot | Separate entry point | Different runtime (polling/webhooks); clean separation from web UI |
| Voice I/O | Optional feature | Only activated when hardware available; graceful degradation |

---

## Phase 0: Research Summary

See [research.md](./research.md) for detailed findings.

## Phase 1: Design Artifacts

See:
- [data-model.md](./data-model.md) - Entity definitions
- [contracts/rest-api.yaml](./contracts/rest-api.yaml) - OpenAPI specification
- [quickstart.md](./quickstart.md) - Development setup
