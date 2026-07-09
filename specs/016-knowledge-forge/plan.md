# Implementation Plan: Knowledge Forge

**Branch**: `016-knowledge-forge` | **Date**: 2026-04-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/016-knowledge-forge/spec.md`

## Summary

Replace passive RAG retrieval with an active Knowledge Forge — a structured knowledge graph that the tutor LLM navigates using tool calling, personalized to each student's BKT mastery state. The navigator bridges the knowledge graph (static structure) with StudentMemory (dynamic mastery) to provide learning frontiers, gap diagnosis, optimal learning paths, and rich concept context. Integrates into the existing multi-agent pipeline at the Planner and Tutor stages.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Ollama (tool calling API), existing StudentMemory (BKT), existing LLMClient
**Storage**: JSON file (`data/knowledge/forge.json`) for graph persistence, SQLite for student mastery (existing)
**Testing**: pytest (unit + integration tests for navigator, graph, migration, tools)
**Target Platform**: Windows 11 / Linux (local Ollama inference)
**Project Type**: Single Python project with existing multi-agent architecture
**Performance Goals**: Graph queries < 100ms for 200+ nodes; tool round-trip within single LLM turn
**Constraints**: RTX 2080 (8GB VRAM) — graph is CPU/RAM only, no VRAM impact; Ollama tool calling format
**Scale/Scope**: 40-200 graph nodes (initial seed), growing via source extraction; 5 STEM domains

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Socratic Pedagogy | PASS | Navigator provides knowledge to tutor agent; tutor still generates Socratic questions. No direct answers to students. |
| II. Multi-Agent Architecture | PASS | Integrates into existing pipeline: Orchestrator → Planner (with graph) → Tutor (with graph tools) → Verifier. No agent bypass. |
| III. Knowledge-Grounded Responses | JUSTIFIED EVOLUTION | Constitution says "grounded in RAG knowledge base." We evolve RAG → structured Knowledge Graph. Spirit maintained (responses grounded in curated knowledge), mechanism upgraded. See Complexity Tracking. |
| IV. Hardware Constraint Compliance | PASS | Graph is in-memory Python (CPU/RAM only). Zero VRAM impact. JSON persistence ~100KB for 200 nodes. |
| V. Metrics-Driven Quality | PASS | Must evaluate against existing metrics (Success@10, Telling@10, Hint Efficiency). Graph-enhanced planner should maintain or improve metrics. |
| VI. STEM Domain Coverage | PASS | Seed data covers math + programming (existing skill_graph). Other domains added via source extractor (P3 story). Graceful degradation for domains without graph data. |

## Project Structure

### Documentation (this feature)

```text
specs/016-knowledge-forge/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (tool schemas)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/knowledge/
├── knowledge_forge.py       # DONE — KnowledgeGraph, NodeType, EdgeType, KnowledgeNode, KnowledgeEdge
├── navigator.py             # DONE — PersonalizedNavigator, MasteryProvider, scoring functions
├── source_extractor.py      # NEW — LLM agent for document → graph extraction
├── rag_retriever.py         # EXISTING — kept for fallback (graceful degradation)
└── ski.py                   # EXISTING — kept, data migrates to graph

src/tools/
├── navigator_tools.py       # NEW — Ollama tool definitions + dispatch for navigator
├── ski_tools.py             # EXISTING — kept for backward compat
└── ski_tool_adapters.py     # EXISTING

src/agents/
├── orchestrator.py          # MODIFIED — add GRAPH_NAV stage, pass to planner/tutor
├── planner.py               # MODIFIED — accept graph context, enhance strategy selection
└── tutor_agent.py           # MODIFIED — register navigator tools alongside SKI tools

scripts/
└── migrate_to_forge.py      # NEW — migration script: skill_graph + SKI → forge.json

data/knowledge/
├── forge.json               # NEW — persisted knowledge graph
├── skill_graph.json         # EXISTING — source for migration
├── textbooks/               # EXISTING — source for migration
├── hints/                   # EXISTING — kept
└── misconceptions/          # EXISTING — kept

tests/
├── test_knowledge_forge.py  # NEW — graph CRUD, persistence, navigation
├── test_navigator.py        # NEW — frontier, gap diagnosis, pathfinding, scoring
└── test_navigator_tools.py  # NEW — tool definitions, dispatch, integration
```

**Structure Decision**: Extends existing `src/knowledge/` and `src/tools/` directories. No new top-level packages. Migration script in `scripts/` follows existing pattern. Graph data in `data/knowledge/` alongside existing knowledge files.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| III. "RAG knowledge base" → Knowledge Graph | Structured graph navigation replaces chunk-based retrieval. Enables personalized learning paths, gap diagnosis, and prerequisite-aware tutoring that RAG cannot provide. | RAG cannot traverse prerequisite chains, compute learning frontiers, or overlay student mastery. The graph is not more complex than RAG — it's more structured. Fallback to existing RAG is preserved. |
