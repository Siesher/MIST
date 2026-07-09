# Feature Specification: PathSlime — bio-inspired multi-path learning path generation

**Feature Branch**: `018-path-slime`  
**Created**: 2026-04-18  
**Status**: Draft  
**Input**: Add bio-inspired Slime Mould Algorithm variant (Lévy-Gaussian hybrid) as an alternative pathfinder — returns k diverse learning paths instead of one optimum, enabling pedagogical choice for students.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Студент выбирает путь обучения (Priority: P1)

Студент хочет изучить целевой концепт (например, "определённые интегралы") и просит тьютора показать **несколько вариантов** маршрута. Тьютор возвращает 3 качественно разных пути: один короткий через мастер-путь, второй постепенный через дополнительные примеры, третий через альтернативные prerequisite chains. Студент выбирает путь, подходящий его стилю обучения.

**Why this priority**: Это отличает ITS от статичных learning paths — даёт студенту autonomy и соответствует Self-Determination Theory (Deci & Ryan). Главная diploma value этой фичи.

**Independent Test**: Запросить 3 альтернативных пути к целевому концепту на реальном графе. Проверить, что пути **заметно отличаются** (Jaccard distance ≥ 0.3 попарно) и все валидны (уважают prerequisite order).

**Acceptance Scenarios**:

1. **Given** студент с частичным mastery запрашивает путь к "определённым интегралам", **When** вызывается `find_alternative_paths(k=3)`, **Then** получены 3 пути с pairwise Jaccard distance ≥ 0.3.
2. **Given** k=3 альтернативных пути найдены, **When** проверяется валидность каждого, **Then** для каждой пары (A, B) в пути A — prerequisite B или A уже освоен студентом.
3. **Given** все prerequisites студент уже освоил, **When** запрошены альтернативы, **Then** метод возвращает 1 пустой путь (target достигнут) вместо k путей.

---

### User Story 2 — Стили обучения (quick / gradual / example-rich) (Priority: P2)

Разные студенты предпочитают разные подходы к обучению: одни хотят минимум концептов (quick), другие — постепенный переход (gradual), третьи — больше примеров (example-rich). Система позволяет запросить пути, соответствующие выбранному стилю.

**Why this priority**: Расширяет P1 feature — разные веса в multi-objective fitness дают разные оптимумы. Основа для персонализации путей.

**Independent Test**: Для одного и того же целевого концепта запросить пути по 3 стилям ("quick", "gradual", "example_rich"). Проверить, что "quick" имеет наименьшую длину, "example_rich" — наибольшую плотность примеров.

**Acceptance Scenarios**:

1. **Given** target concept и student mastery, **When** запрошен путь style="quick", **Then** средняя длина пути меньше чем у style="gradual".
2. **Given** путь с примерами, **When** запрошен style="example_rich", **Then** плотность EXAMPLE-узлов в пути выше, чем у style="quick".

---

### User Story 3 — Тьютор использует альтернативные пути через tool (Priority: P2)

LLM-тьютор, обрабатывая запрос студента "какие есть варианты изучить интегралы", вызывает инструмент `find_alternative_paths` и получает структурированные пути. Тьютор представляет их студенту читабельно ("Вариант A — быстрый, ...; Вариант B — через примеры, ...").

**Why this priority**: Делает bio-inspired pathfinder **доступным модели**. Без этого integration с MITS pipeline нет.

**Independent Test**: Вызвать новый tool `find_alternative_paths` через `chat_with_tools()`. Проверить, что возврат JSON валиден и содержит k путей с readable metadata.

**Acceptance Scenarios**:

1. **Given** navigator tools зарегистрированы, **When** LLM вызывает `find_alternative_paths`, **Then** получает валидный JSON с k путями, каждый содержит titles, costs, diversity_score.
2. **Given** invalid target_concept_id, **When** tool вызван, **Then** возвращает ошибку в JSON без падения pipeline.

---

### User Story 4 — Latency соответствует resource profile (Priority: P3)

Система адаптирует параметры алгоритма (число итераций, k, размер колонии) к активному resource profile. На Lite — меньше итераций и k=2, на Standard/Max — полная конфигурация с k=5.

**Why this priority**: Guaranteed usability на low-resource hardware. Но даже без этого фича работает на всех профилях с default параметрами.

**Independent Test**: Измерить p95 latency на 20 сценариях для каждого профиля. Lite ≤1500ms, Standard ≤500ms, Max ≤300ms.

**Acceptance Scenarios**:

1. **Given** active profile = "lite", **When** `find_alternative_paths()` вызвана, **Then** p95 latency ≤ 1500ms на 83-узловом графе.
2. **Given** active profile = "standard" с k=3, **When** `find_alternative_paths()` вызвана, **Then** p95 latency ≤ 500ms.

---

### Edge Cases

- **Target уже мастерован** — возвращаем 1 путь (сам target), diversity_score=1.0 (нет альтернатив).
- **Нет start nodes** (cold start, нет mastery) — используем графовые "точки входа" (узлы без prerequisites).
- **k больше числа существующих путей** — возвращаем все уникальные, не генерируя дубликаты.
- **Таймаут алгоритма** (превышен latency budget) — возвращаем best-so-far, помечаем флагом `truncated=True`.
- **Невалидный target** — возвращаем пустой список с описательной ошибкой.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST generate k diverse learning paths between current student knowledge and a target concept, using bio-inspired optimization (Slime Mould family).
- **FR-002**: System MUST guarantee path validity — каждый путь respects prerequisite relationships on the underlying knowledge graph.
- **FR-003**: System MUST support user-selected learning styles (quick / gradual / example-rich / mixed), each biasing the multi-objective fitness differently.
- **FR-004**: System MUST expose alternative-paths generation as a tool callable by the tutor LLM, with the same interface pattern as existing navigator tools.
- **FR-005**: System MUST measure and return a diversity score (pairwise Jaccard distance) for the returned path set.
- **FR-006**: System MUST respect active resource profile — lower iteration count / smaller k on resource-constrained profiles.
- **FR-007**: System MUST remain backward-compatible with existing `find_optimal_path()` (Dijkstra) — the new method is additive, not replacing.
- **FR-008**: System MUST gracefully degrade to Dijkstra when bio-inspired search fails to converge or exceeds timeout.

### Key Entities

- **PathSlime engine** — bio-inspired optimizer maintaining k evolving colonies, each seeking a path from start to target.
- **Colony** — represents one candidate path currently explored by a "slime" agent; tracks conductivity of edges it has used.
- **Alternative Paths Result** — data structure containing k LearningPath objects plus diversity score and generation metadata.
- **Learning Style** — named fitness weight configuration (quick / gradual / example-rich / mixed).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Для k=3 paths, попарная Jaccard distance между путями ≥ 0.3 в 90% test scenarios.
- **SC-002**: 100% возвращённых путей проходят prerequisite validity check (не появляются концепты до их prerequisites).
- **SC-003**: На 20 path scenarios, diversity в среднем на ≥50% выше, чем у random-perturbed Dijkstra baseline (k independent runs с Gaussian noise на edge weights).
- **SC-004**: Latency p95 ≤ 500ms на Standard profile для k=3 на 83-узловом графе; ≤ 1500ms на Lite.
- **SC-005**: Для style="quick" средняя длина пути на ≥20% короче чем style="gradual" в 80% сценариев.
- **SC-006**: При таймауте алгоритма возвращается валидный truncated result — ни один вызов не приводит к исключению в pipeline тьютора.
- **SC-007**: Tool `find_alternative_paths` доступен LLM-тьютору — тьютор может вызывать его через multi-round tool calling и парсить JSON-результат.
