# Implementation Plan: PathSlime

**Branch**: `018-path-slime` | **Date**: 2026-04-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/018-path-slime/spec.md`

## Summary

Добавить bio-inspired optimization метод `find_alternative_paths()` в `PersonalizedNavigator`, возвращающий **k diverse learning paths** вместо единственного оптимума (существующий `find_optimal_path()` через Dijkstra). Реализация — Lévy-Gaussian гибрид Slime Mould Algorithm: k "колоний" эволюционируют на графе через Lévy-flight perturbation + Gaussian mutation + diversity pressure. Multi-objective fitness объединяет длину, mastery, difficulty и плотность примеров. Target: k=3 diverse paths с Jaccard distance ≥ 0.3, latency ≤ 500ms Standard profile.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: numpy (random walk, vectorization), scipy.stats (Lévy distribution), existing Knowledge Forge / PersonalizedNavigator
**Storage**: In-memory only — алгоритм stateless, не персистит между вызовами
**Testing**: pytest (unit tests for algorithm components, integration tests via navigator)
**Target Platform**: Windows 11 / Linux, все три resource profiles (lite/standard/max)
**Project Type**: Extension of existing Python navigator architecture
**Performance Goals**: k=3 за ≤500ms Standard (GPU), ≤1500ms Lite (CPU); p95 on 83-node graph
**Constraints**: no external optimization libraries (только numpy + scipy.stats); graceful fallback to Dijkstra on timeout/failure; добавляется, не заменяет Dijkstra
**Scale/Scope**: 83 узла / 88 рёбер (Knowledge Forge), k ≤ 5, colony_size = 10 slime agents, iterations ≤ 50

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Socratic Pedagogy | PASS | PathSlime не участвует в response generation — только pathfinding. Даёт тьютору выбор путей для Socratic navigation, не генерирует answers. |
| II. Multi-Agent Architecture | PASS | Расширяет Navigator (неагент) — invoked via existing tool calling pattern. Orchestrator pipeline не меняется. |
| III. Knowledge-Grounded Responses | PASS | Все пути — обходы **реального** Knowledge Forge графа. Нет hallucinated concepts. |
| IV. Hardware Constraint Compliance | PASS | Pure Python + numpy, без VRAM. Scale-adapted: lite k=2+20iter, std k=3+35iter, max k=5+50iter. |
| V. Metrics-Driven Quality | PASS | Explicit SCs: diversity ≥0.3, validity 100%, +50% diversity vs random-perturbed Dijkstra. Measurable. |
| VI. STEM Domain Coverage | PASS | Алгоритм domain-agnostic. Работает на любом подграфе (math, physics, cs). |

Все 6/6 PASS. No complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/018-path-slime/
├── plan.md              # This file
├── research.md          # Phase 0: 5 decisions с citations
├── data-model.md        # Phase 1: Colony, AlternativePaths, StyleConfig
├── contracts/
│   └── path-slime-tool.md  # Ollama tool definition
├── quickstart.md        # Phase 1: usage guide
└── tasks.md             # Phase 2 (speckit.tasks)
```

### Source Code (repository root)

```text
src/knowledge/
├── path_slime.py           # NEW — PathSlime engine (Lévy-Gaussian SMA)
├── levy_sampler.py         # NEW — discrete Lévy flight sampling на графе
├── navigator.py            # MODIFIED — find_alternative_paths() метод
└── knowledge_forge.py      # UNCHANGED

src/tools/
└── navigator_tools.py      # MODIFIED — новый tool find_alternative_paths

src/resource_profiles.py    # MODIFIED — enable_path_slime flag + style settings

evaluation/
├── path_slime_eval.py      # NEW — A/B PathSlime vs Dijkstra-perturbed
└── scenarios/
    └── path_scenarios.json # NEW — 20 pathfinding scenarios

tests/
└── test_path_slime.py      # NEW — unit + integration tests

docs/
└── PATH_SLIME.md           # NEW — algorithm explanation + results
```

**Structure Decision**: Extends `src/knowledge/` и `src/tools/`. No new top-level packages. Algorithm isolated in `path_slime.py` с helper `levy_sampler.py` для повторного использования Lévy distribution. Integration point — `navigator.py` как optional secondary pathfinder (Dijkstra остаётся primary для single-path).

## Complexity Tracking

No constitution violations. Clean architectural extension.
