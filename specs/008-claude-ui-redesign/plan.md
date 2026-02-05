# Implementation Plan: Claude-Style UI Redesign

**Branch**: `008-claude-ui-redesign` | **Date**: 2026-02-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-claude-ui-redesign/spec.md`

## Summary

Редизайн интерфейса MITS для создания минималистичного, современного UI в стиле Claude Desktop. Основные изменения: центрированный чат с тёмной темой, sticky input внизу экрана, аватары для сообщений, индикатор генерации, кнопки копирования кода, сворачиваемый sidebar и плавные анимации. Реализация через Gradio 4.x custom CSS/themes и JavaScript.

## Technical Context

**Language/Version**: Python 3.11+ (Gradio backend), CSS3, JavaScript ES6
**Primary Dependencies**: Gradio 4.x, custom CSS themes
**Storage**: localStorage (user preferences), existing SQLite (session data)
**Testing**: Visual testing, pytest for backend logic
**Target Platform**: Web (Chrome, Firefox, Safari, Edge - last 2 versions)
**Project Type**: Single project (модификация существующего interface/unified_app.py)
**Performance Goals**: 60fps анимации, <2s загрузка, <300ms переключение темы
**Constraints**: Совместимость с Gradio 4.x API, поддержка экранов 320px-2560px
**Scale/Scope**: Один основной интерфейс чата с настройками

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Socratic Pedagogy | ✅ PASS | UI изменения не затрагивают педагогическую логику |
| II. Multi-Agent Architecture | ✅ PASS | Архитектура агентов не изменяется |
| III. Knowledge-Grounded Responses | ✅ PASS | RAG система остаётся неизменной |
| IV. Hardware Constraint Compliance | ✅ PASS | Только frontend изменения, VRAM не затрагивается |
| V. Metrics-Driven Quality | ✅ PASS | SC-001-007 определяют измеримые метрики |
| VI. STEM Domain Coverage | ✅ PASS | Контент не изменяется, только UI |

**Gate Result**: ✅ PASSED - все принципы соблюдены

## Project Structure

### Documentation (this feature)

```text
specs/008-claude-ui-redesign/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
interface/
├── unified_app.py       # Основной файл приложения (модификация)
├── themes/              # NEW: Gradio themes
│   ├── claude_dark.py   # Тёмная тема в стиле Claude
│   └── claude_light.py  # Светлая тема
├── styles/              # NEW: Custom CSS
│   └── claude.css       # Стили для Claude-like интерфейса
└── assets/              # NEW: Статические ресурсы
    ├── user_avatar.svg  # Аватар пользователя
    └── bot_avatar.svg   # Аватар ассистента

src/
└── config.py            # Добавление настроек UI
```

**Structure Decision**: Расширение существующей структуры interface/ с добавлением themes/, styles/ и assets/ для модульной организации UI компонентов.

## Complexity Tracking

> Нет нарушений конституции - таблица не требуется.

---

## Phase 0: Research Complete

See [research.md](./research.md) for detailed findings.

## Phase 1: Design Complete

See:
- [data-model.md](./data-model.md) - Модель данных для preferences
- [contracts/](./contracts/) - API контракты (не требуются для frontend-only)
- [quickstart.md](./quickstart.md) - Быстрый старт разработки
