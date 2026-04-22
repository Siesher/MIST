# MITS Architecture — Central Navigation Index

**Last updated**: 2026-04-18 (feature 017-tom-tutor planning)

This is the master index for the MITS (Math Intelligent Tutoring System)
codebase. Use it to orient yourself quickly when returning to the project.

---

## 1. System at a Glance

```text
┌──────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 14 + shadcn/ui + Zustand)                 │
├──────────────────────────────────────────────────────────────┤
│  Backend (FastAPI, WebSocket streaming)                      │
├──────────────────────────────────────────────────────────────┤
│  Multi-Agent Orchestrator                                    │
│    ROUTING → PROFILER → [MENTAL_MODEL] → PLANNER             │
│                      → GRAPH_NAV → RAG → TUTOR → VERIFIER    │
├──────────────────────────────────────────────────────────────┤
│  LLM: Qwen3.5-9B (GSPO + KTO + DPO fine-tuned) via Ollama    │
│  Student Memory: BKT + DKT in SQLite                         │
│  Knowledge Forge: graph of 83 nodes, 88 edges (living)       │
└──────────────────────────────────────────────────────────────┘
```

## 2. Feature Timeline

| Feature | Status | Specs | Key Capability |
|---------|:------:|-------|----------------|
| 001-015 | DONE | [specs/](../specs/) | Foundation (agents, RAG, BKT, pipeline) |
| **016** | **DONE** | [specs/016-knowledge-forge/](../specs/016-knowledge-forge/) | **Knowledge Forge + Living KG + Resource Profiles** |
| **017** | **US1 CALIBRATED** | [specs/017-tom-tutor/](../specs/017-tom-tutor/) | **ToM-Tutor — 95% root-hit, 90% misconception accuracy on 20 scenarios** |
| 018 | planned | — | PathSlime — Lévy-Gaussian SMA for alternative learning paths |

### Feature 017 A/B Results (latest)

| Metric | Target | Baseline | ToM | Result |
|--------|:------:|:--------:|:---:|:------:|
| Root-hit rate | ≥80% | 70% | **95%** | ✅ |
| Misconception accuracy | ≥75% | — | **90%** | ✅ |
| No regressions | required | — | **0/20** | ✅ |
| Improvements | — | — | **5/20** | — |

Full evaluation: [evaluation/reports/tom_ab_2026-04-18.md](../evaluation/reports/tom_ab_2026-04-18.md)

---

## 3. Directory Map

### `src/agents/` — Multi-agent pipeline

| File | Agent | Role |
|------|-------|------|
| `base_agent.py` | `BaseAgent` | Abstract base (health, metrics, logging) |
| `orchestrator.py` | `AgentOrchestrator` | Coordinates all agents, owns pipeline stages |
| `profiler.py` | `ProfilerAgent` | Diagnoses student errors, produces `StudentProfile` |
| `planner.py` | `PlannerAgent` | Selects teaching strategy (13 rule-based + graph_context + belief_state) |
| `tutor_agent.py` | `SocraticTutorAgent` | Generates Socratic responses; uses SKI + navigator tools |
| `verifier.py` | `VerifierAgent` | Quality control before response delivery |
| `affective_agent.py` | `AffectiveDetector` | Rule-based + RuBERT emotion detection |
| `task_generator.py` | `TaskGenerator` | Auto-generates practice tasks |
| `mental_model_agent.py` | `MentalModelAgent` | **NEW (017)** Theory-of-Mind student state |

### `src/knowledge/` — Knowledge & RAG

| File | Purpose | Feature |
|------|---------|---------|
| `knowledge_forge.py` | Graph core: 6 node types, 10 edge types, persistence | 016 |
| `navigator.py` | `PersonalizedNavigator` — frontier, gap diagnosis, Dijkstra pathfinding | 016 |
| `session_analyzer.py` | Extracts graph-refinement signals from tutoring sessions | 016 |
| `graph_evolution.py` | Proposal queue + rule-based verifier + auto-accept | 016 |
| `source_extractor.py` | LLM-based document → graph ingestion (two-pass) | 016 |
| `rag_retriever.py` | Legacy RAG — kept for fallback | pre-016 |
| `ski.py` | Structured Knowledge Index (cards) | pre-016 |

### `src/tools/` — Ollama tool calling

| File | Tools |
|------|-------|
| `navigator_tools.py` | 5 tools: explore_concept, diagnose_gap, suggest_next, find_learning_path, get_learning_frontier |
| `ski_tools.py` | 5 tools: lookup_concept, get_worked_example, get_formula, get_prerequisites, get_solution_method |
| `calculator.py` | Safe math evaluation |
| `web_search.py` | Optional web search |

### `src/memory/`

| File | Purpose |
|------|---------|
| `student_memory.py` | SQLite-backed BKT + DKT + Ebbinghaus decay + preferences |
| `session_memory.py` | In-memory session state, conversation turns |
| `interfaces.py` | `IStudentMemory`, `ISessionMemory` contracts |

### `src/inference/` — Performance optimizations

| File | Purpose |
|------|---------|
| `turbo_quant.py` | Online KV cache quantization (arXiv 2504.19874) |
| `turbo_quant_cache.py` | HF-compatible cache wrapper |
| `cache.py` | Semantic similarity response cache |
| `context_compressor.py` | Conversation compression (sliding window + LLM summary) |
| `batch_processor.py` | Batched embedding generation |
| `hint_prefetcher.py` | Pre-compute likely hints |
| `metrics.py` | Performance metrics collection |

### `src/models/`

| File | Purpose |
|------|---------|
| `llm_client.py` | Ollama client — streaming, tool calling, JSON mode, multi-model |
| `client_factory.py` | Factory for LLM clients |

### `src/data/`

| File | Purpose |
|------|---------|
| `schemas.py` | All dataclasses: `Task`, `StudentProfile`, `TutorResponse`, `TeachingPlan`, `BeliefState` (017) |
| `knowledge_graph.py` | `SKILL_GRAPH` Python dict (51 skills) — source for migration |

### `src/resource_profiles.py` (016)

Three profiles: `lite` (16 GB RAM/CPU), `standard` (32 GB + 6 GB VRAM),
`max` (64+ GB + 24 GB VRAM). Auto-detection via psutil + torch.cuda.
Feature flags: `enable_rubert_affect`, `enable_dkt`, `enable_llm_verifier`,
`enable_tom_agent` (017), `enable_batch_inference`,
`enable_speculative_decoding`.

### `evaluation/`

| File | Purpose |
|------|---------|
| `baseline_eval.py` | 4 navigator metrics (gap, frontier, path, Living KG) |
| `tom_ab_eval.py` | **NEW (017)** A/B comparison ToM on/off |
| `scenarios/` | JSON scenario files for reproducible evaluation |
| `reports/` | Generated Markdown + JSON reports |

### `scripts/`

| File | Purpose |
|------|---------|
| `migrate_to_forge.py` | One-time migration: skill_graph + SKI → forge.json |
| `grow_knowledge_graph.py` | Run Living KG on synthetic (or real) sessions |
| `detect_resources.py` | Print recommended resource profile |

### `training/`

| Subdir | Purpose |
|--------|---------|
| `scripts/` | ML pipeline: evaluate_stage.py, build_eval_benchmark.py, verify_answers.py |
| `data/` | ~1.1 GB JSONL training data |
| `Modelfile.*` | Ollama model configurations |

### `data/knowledge/`

| File | Purpose | Generated by |
|------|---------|--------------|
| `skill_graph.json` | Original 21-skill JSON graph | pre-016 (manual) |
| `forge.json` | Knowledge Forge persistence (83 nodes, 88 edges) | 016 migration |
| `forge_proposals.json` | Pending Living KG proposals with evidence | 016 (auto) |
| `forge_growth.jsonl` | Event log: accept/reject decisions | 016 (auto) |
| `textbooks/*.json` | SKI knowledge cards (source for migration) | pre-016 |
| `hints/` | Progressive hint templates (legacy RAG) | pre-016 |
| `misconceptions/` | Error patterns (legacy RAG) | pre-016 |

---

## 4. Pipeline Stages (Orchestrator)

```text
Student input
    │
    ▼
1. ROUTING          — classify query type (question/answer_attempt/hint_request/etc.)
    │
    ▼
2. PROFILER         — diagnose errors, confidence, cognitive load → StudentProfile
    │
    ▼
3. MENTAL_MODEL ◄── NEW 017 — produce BeliefState (if enable_tom_agent)
    │
    ▼
4. GRAPH_NAV        — fetch concept_context from Knowledge Forge (if forge.json exists)
    │
    ▼
5. PLANNER          — select teaching strategy (rules + graph_context + belief_state)
    │
    ▼
6. RAG              — retrieve hints/misconceptions (legacy, fallback)
    │
    ▼
7. TUTOR            — generate response with tool calling (SKI + navigator)
    │
    ▼
8. VERIFIER         — quality control
    │
    ▼
Response to student
```

Each stage has graceful degradation — if it fails, the pipeline continues
with whatever context is available.

---

## 5. Data Flow for One Tutoring Turn

```text
student_message
    │
    ├─→ Profiler: parse errors, compare with solution
    │       ↓
    │    StudentProfile (errors, confidence, cognitive_load)
    │       ↓
    ├─→ MentalModelAgent (017): infer what student thinks
    │       ↓
    │    BeliefState (misconception, predictions, confidence)
    │       ↓
    ├─→ Navigator: diagnose_gap(belief_state) → GapDiagnosis (re-ranked)
    │       ↓
    ├─→ Planner: create_plan(profile, graph_context, belief_state)
    │       ↓
    │    TeachingPlan (strategy, moves, prerequisites_to_review, tone)
    │       ↓
    └─→ Tutor: generate response with SKI + Navigator tools
        │
        └─→ Verifier: check quality → ok
                ↓
            Response sent
                ↓
            StudentMemory.update_knowledge_state() updates BKT
```

---

## 6. Where to Look First

**Want to understand tutoring logic?** → `src/agents/orchestrator.py` (pipeline coordinator)

**Want to add/modify knowledge?** → `data/knowledge/forge.json` + `scripts/migrate_to_forge.py`

**Want to see how Knowledge Forge works?** → `src/knowledge/knowledge_forge.py` + `src/knowledge/navigator.py`

**Want to see how the graph grows?** → `src/knowledge/session_analyzer.py` + `src/knowledge/graph_evolution.py`

**Want to see resource scaling?** → `src/resource_profiles.py` + `docs/architecture/RESOURCE_PROFILES.md`

**Want to see baseline metrics?** → `evaluation/baseline_eval.py` + `evaluation/reports/baseline_*.md`

**Want the research rationale?** → `specs/<feature>/research.md`

**Want the diploma text scaffolding?** → TBD (generate from specs + evaluation reports)

---

## 7. Feature Deep-Dive Documents

| Doc | Scope |
|-----|-------|
| [`docs/architecture/RESOURCE_PROFILES.md`](RESOURCE_PROFILES.md) | 3-tier resource system (lite/standard/max) |
| `docs/architecture/TOM_TUTOR.md` | **TBD (017)** Theory-of-Mind agent details |
| [`docs/training/TRAINING_PIPELINE.md`](../training/TRAINING_PIPELINE.md) | GSPO → KTO → DPO fine-tuning |
| `docs/architecture/MODEL_SELECTION.md` | Rationale for Qwen3.5-9B choice |

---

## 8. Conventions

### Imports

```python
# stdlib
import logging
from pathlib import Path

# third-party
import pytest

# local — always absolute from src.
from src.knowledge.knowledge_forge import KnowledgeGraph
from src.agents.base_agent import BaseAgent
```

### Feature gating

```python
from src.resource_profiles import feature_enabled

if feature_enabled("enable_tom_agent"):
    # heavy path
```

### Graceful degradation pattern

```python
try:
    result = expensive_operation()
except Exception as e:
    logger.warning(f"Degraded: {e}")
    result = empty_fallback()
# pipeline continues regardless
```

### Commit messages

`type(scope): description`
- type: feat, fix, refactor, docs, test, chore, perf, eval
- scope: e.g. `knowledge`, `agents`, `config`

### Branch naming

`NNN-short-feature-name` (matches speckit spec dir).

---

## 9. Spec-Driven Development Flow

```text
1. /speckit.specify  →  spec.md     (WHAT + WHY, business language)
2. /speckit.plan     →  plan.md     (architecture + tech context)
                        research.md (decisions with citations)
                        data-model.md (entities)
                        contracts/  (I/O contracts)
                        quickstart.md (getting started)
3. /speckit.tasks    →  tasks.md    (executable task list)
4. /speckit.implement → actual code + tests + commits
```

This is the MITS workflow. Don't skip phases — the artifacts are the
research trail for the diploma.

---

## 10. Quick Commands

```bash
# Environment
python scripts/detect_resources.py --list     # check profile

# Knowledge Forge
python scripts/migrate_to_forge.py            # seed graph from skill_graph
python scripts/grow_knowledge_graph.py        # run Living KG on synthetic sessions

# Evaluation
python evaluation/baseline_eval.py            # run 4 deterministic metrics
python evaluation/tom_ab_eval.py              # TBD (017) A/B comparison

# Tests
python -m pytest tests/ -v                    # all tests
python -m pytest tests/test_knowledge_forge.py tests/test_navigator.py tests/test_graph_evolution.py -v   # Knowledge Forge only

# Lint
python -m ruff check src/ tests/
python -m ruff format src/ tests/
```
