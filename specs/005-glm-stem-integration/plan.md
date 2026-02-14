# Implementation Plan: GLM-STEM Model Integration

**Branch**: `005-glm-stem-integration` | **Date**: 2026-02-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-glm-stem-integration/spec.md`

## Summary

Интеграция REAP-pruned GLM модели (42 эксперта вместо 64) в MITS для улучшения производительности математического репетитора. Включает скрипты установки, обновление конфигурации и тесты качества.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Ollama, huggingface_hub, requests
**Storage**: Файловая система (GGUF файлы ~13-21GB)
**Testing**: pytest с fixtures для Ollama
**Target Platform**: Windows/Linux/macOS с Ollama
**Project Type**: Single project (существующий MITS)
**Performance Goals**: TTFT <2s, accuracy >90% на STEM задачах
**Constraints**: 8GB VRAM (RTX 2080), 16GB RAM минимум
**Scale/Scope**: Локальная установка, один пользователь

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Socratic Pedagogy | ✅ PASS | Модель не влияет на педагогику, используется существующий tutor agent |
| II. Multi-Agent Architecture | ✅ PASS | Интеграция через ModelManager, не меняет pipeline |
| III. Knowledge-Grounded Responses | ✅ PASS | RAG система остаётся без изменений |
| IV. Hardware Constraint Compliance | ✅ PASS | Pruned модель ~5.5GB VRAM (33% меньше оригинала) |
| V. Metrics-Driven Quality | ✅ PASS | Добавляются тесты accuracy для валидации |
| VI. STEM Domain Coverage | ✅ PASS | Модель откалибрована на STEM датасете |

**Gate Status**: ✅ PASSED - No violations

## Project Structure

### Documentation (this feature)

```text
specs/005-glm-stem-integration/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A - no API changes)
├── checklists/          # Quality checklists
│   └── requirements.md
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
scripts/
├── install_glm_stem.sh      # NEW: Linux/macOS installation
└── install_glm_stem.ps1     # NEW: Windows installation

src/
├── config.py                # MODIFY: Default MODEL_NAME
├── inference/
│   └── model_manager.py     # MODIFY: Add glm-stem-42exp preset
└── models/
    └── llm_client.py        # NO CHANGE: Already handles GLM models

tests/
└── test_glm_stem.py         # NEW: Model quality tests
```

**Structure Decision**: Single project, minimal changes to existing structure. New scripts in `scripts/`, new tests in `tests/`.

## Complexity Tracking

> No violations - table not needed.
