# Implementation Plan: ToM-Tutor

**Branch**: `017-tom-tutor` | **Date**: 2026-04-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/017-tom-tutor/spec.md`

## Summary

Add a Theory-of-Mind reasoning stage to the MITS tutoring pipeline using prompt-only inference on the existing Qwen3.5-9B model. Between the Profiler and Planner stages, a new `MentalModelAgent` produces a structured `BeliefState` describing the student's active misconception, current understanding, and predicted reactions to candidate teaching strategies. This belief state informs both Planner strategy selection and Navigator gap re-ranking. Goal: raise gap root-hit rate from 60% (baseline) to ≥80%.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Ollama (JSON-mode inference via `LLMClient.generate()`), existing multi-agent pipeline, Knowledge Forge navigator
**Storage**: No new persistence — belief state lives in session memory only (ephemeral)
**Testing**: pytest (unit + integration); A/B evaluation via existing `evaluation/` infrastructure
**Target Platform**: Windows 11 / Linux, all three resource profiles (lite/standard/max)
**Project Type**: Extension of existing Python multi-agent architecture
**Performance Goals**: ≤1.5 s per ToM inference on lite profile, ≤0.7 s on standard
**Constraints**: Must respect resource profiles; full graceful degradation when LLM unavailable; no new training data required (prompt-only)
**Scale/Scope**: 1 new agent (~300 LOC), 2 integration points (Planner + Navigator), 1 new eval script, ~20 new test scenarios

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Socratic Pedagogy | PASS | ToM improves Socratic choice by selecting strategies predicted to induce reasoning rather than tell answers. Success criterion SC-003 explicitly guards telling-rate regression. |
| II. Multi-Agent Architecture | PASS | Adds one new agent (`MentalModelAgent`) in the canonical pipeline position between Profiler and Planner. No agent bypass. |
| III. Knowledge-Grounded Responses | PASS | Belief state draws from Knowledge Forge (misconception nodes, related concepts) and BKT mastery. Not free-form speculation — structurally grounded. |
| IV. Hardware Constraint Compliance | PASS | Profile-aware: simplified prompt on lite (≤200 tokens output) keeps CPU inference under 1.5 s budget. No VRAM increase — reuses existing LLM instance. |
| V. Metrics-Driven Quality | PASS | Explicit measurable targets: root-hit 60%→80%, misconception accuracy ≥75%, Socratic quality +10% without telling-rate regression. |
| VI. STEM Domain Coverage | PASS | ToM reasoning is domain-agnostic. Baseline scenarios cover math; can extend to physics/chem/bio/cs as seed data grows. |

All principles satisfied. No complexity justification required.

## Project Structure

### Documentation (this feature)

```text
specs/017-tom-tutor/
├── plan.md                          # This file
├── research.md                      # Phase 0: 6 research decisions
├── data-model.md                    # Phase 1: BeliefState entity
├── quickstart.md                    # Phase 1: Getting started guide
├── contracts/
│   └── mental-model-agent.md        # Agent I/O contract
└── tasks.md                         # Phase 2 output (speckit.tasks)
```

### Source Code (repository root)

```text
src/agents/
├── mental_model_agent.py            # NEW — the ToM agent (core deliverable)
├── profiler.py                      # EXISTING — called before ToM
├── planner.py                       # MODIFIED — accepts belief_state param
└── orchestrator.py                  # MODIFIED — add MENTAL_MODEL pipeline stage

src/knowledge/
└── navigator.py                     # MODIFIED — diagnose_gap accepts optional belief_state for re-ranking

src/resource_profiles.py             # MODIFIED — add enable_tom_agent flag + tom_prompt_style field

src/data/
└── schemas.py                       # MODIFIED — add BeliefState dataclass

evaluation/
├── baseline_eval.py                 # EXISTING — reused for before/after comparison
├── tom_ab_eval.py                   # NEW — A/B evaluation runner
└── scenarios/
    └── tom_scenarios.json           # NEW — 15+ ToM-specific ground-truth scenarios

tests/
├── test_mental_model_agent.py       # NEW — unit tests for agent
├── test_tom_integration.py          # NEW — integration with Planner + Navigator
└── test_navigator.py                # EXISTING — extend with belief_state tests

docs/
├── ARCHITECTURE.md                  # NEW — central index of all features & components
└── TOM_TUTOR.md                     # NEW — detailed feature docs
```

**Structure Decision**: Extends existing `src/agents/`, `src/knowledge/`, and `evaluation/` directories. No new top-level packages. Central `docs/ARCHITECTURE.md` added as navigation index for long-term orientation across all features (016, 017, and future).

## Complexity Tracking

No constitution violations. This feature is a clean architectural extension with clear measurable goals.
