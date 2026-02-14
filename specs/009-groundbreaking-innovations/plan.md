# Implementation Plan: Groundbreaking Innovations for MITS

**Branch**: `009-groundbreaking-innovations` | **Date**: 2026-02-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-groundbreaking-innovations/spec.md`

## Summary

Implement 6 innovative features for MITS diploma project:
1. **Affective State Detection** — Text-based emotion recognition for adaptive tutoring
2. **Generative Task Synthesis** — SymPy-verified infinite task generation
3. **Counterfactual Explanations** — XAI-based error explanation system
4. **Metacognitive Scaffolding** — Teaching students to "learn how to learn"
5. **Learning Path Optimization** — Personalized curriculum based on knowledge graph
6. **Multi-Modal Math Input** — OCR for handwritten solutions via vision models

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Gradio 4.x, Ollama, SymPy, sentence-transformers, ChromaDB, pydantic
**Storage**: SQLite (student profiles), ChromaDB (vectors), JSON (configs)
**Testing**: pytest
**Target Platform**: Windows/Linux desktop (Ryzen 9 9950x, RTX 2080 8GB)
**Project Type**: single
**Performance Goals**: <3s response time, <6GB VRAM usage
**Constraints**: RTX 2080 8GB VRAM limit, 32GB RAM
**Scale/Scope**: Single user, local deployment

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Socratic Pedagogy | ✅ PASS | All features maintain Socratic approach; Metacognitive Scaffolding enhances it |
| II. Multi-Agent Architecture | ✅ PASS | New components integrate as agents (AffectiveAgent, TaskSynthesizer, etc.) |
| III. Knowledge-Grounded Responses | ✅ PASS | Counterfactuals & Learning Path use existing knowledge base |
| IV. Hardware Constraint Compliance | ⚠️ REVIEW | Vision model for OCR needs VRAM budget; use smaller model (minicpm-v) |
| V. Metrics-Driven Quality | ✅ PASS | SC-001 to SC-012 define measurable outcomes |
| VI. STEM Domain Coverage | ✅ PASS | Generative Tasks support all math topics |

**Gate Result**: PASS with VRAM monitoring required for Multi-Modal Input

## Project Structure

### Documentation (this feature)

```text
specs/009-groundbreaking-innovations/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/
├── models/
│   ├── affective_detector.py      # NEW: Affective State Detection
│   ├── task_synthesizer.py        # NEW: Generative Task Synthesis
│   ├── counterfactual_engine.py   # NEW: Counterfactual Explanations
│   ├── metacognitive_tracker.py   # NEW: Metacognitive Scaffolding
│   ├── learning_path_optimizer.py # NEW: Learning Path Optimization
│   ├── vision_analyzer.py         # NEW: Multi-Modal Math Input
│   ├── cognitive_load.py          # EXISTING: Enhance with affective signals
│   └── knowledge_tracing.py       # EXISTING: Enhance for Learning Path
├── agents/
│   ├── affective_agent.py         # NEW: Agent wrapper for affective detection
│   └── tutor_agent.py             # MODIFY: Integrate affective adaptation
├── data/
│   ├── schemas.py                 # MODIFY: Add new data models
│   └── knowledge_graph.py         # NEW: Knowledge graph for Learning Path
└── interface/
    └── unified_app.py             # MODIFY: Add image upload, visualizations

tests/
├── unit/
│   ├── test_affective_detector.py
│   ├── test_task_synthesizer.py
│   ├── test_counterfactual.py
│   ├── test_metacognitive.py
│   ├── test_learning_path.py
│   └── test_vision_analyzer.py
└── integration/
    └── test_innovations_pipeline.py
```

**Structure Decision**: Single project structure maintained; new modules added to existing `src/models/` and `src/agents/` directories.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Vision model for OCR | Required for Multi-Modal Input feature | Text-only input insufficient for handwritten solutions |
| SymPy integration | Required for formal verification | LLM-only verification unreliable for math correctness |
