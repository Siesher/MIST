# Tasks: Claude-Style UI Redesign

**Input**: Design documents from `/specs/008-claude-ui-redesign/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested - focusing on implementation tasks.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1-US6) this task belongs to
- Paths follow single-project structure from plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create new directories and base files for Claude-style UI

- [X] T001 Create directory structure: interface/themes/, interface/styles/, interface/assets/
- [X] T002 [P] Create user avatar SVG in interface/assets/user_avatar.svg
- [X] T003 [P] Create bot avatar SVG in interface/assets/bot_avatar.svg
- [X] T004 [P] Create base CSS file in interface/styles/claude.css with CSS variables from data-model.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core theme infrastructure that ALL user stories depend on

**CRITICAL**: Complete before starting any user story

- [X] T005 Create dark theme in interface/themes/claude_dark.py using gr.themes.Base
- [X] T006 [P] Create light theme in interface/themes/claude_light.py using gr.themes.Base
- [X] T007 Create interface/themes/__init__.py with theme exports and get_theme() helper
- [X] T008 Add UI settings to src/config.py (default_theme, animation_enabled, etc.)
- [X] T009 Create JavaScript utilities in interface/styles/claude.js for localStorage and DOM manipulation

**Checkpoint**: Foundation ready - user story implementation can begin

---

## Phase 3: User Story 1 - Минималистичный чат-интерфейс (Priority: P1) MVP

**Goal**: Центрированный чат с тёмной темой, sticky input, аватары

**Independent Test**: Открыть приложение, проверить тёмный фон, центрирование (800px), sticky input внизу, аватары у сообщений

### Implementation for User Story 1

- [X] T010 [US1] Update interface/unified_app.py to import and apply dark theme from interface/themes/
- [X] T011 [US1] Add CSS injection to gr.Blocks() for centered chat layout in interface/unified_app.py
- [X] T012 [US1] Configure gr.Chatbot with avatar_images parameter in interface/unified_app.py
- [X] T013 [US1] Add sticky input CSS to interface/styles/claude.css (position: sticky, bottom: 0)
- [X] T014 [US1] Add message styling CSS to interface/styles/claude.css (border-radius, shadows, spacing)
- [X] T015 [US1] Add responsive container CSS to interface/styles/claude.css (max-width: 800px, centered)

**Checkpoint**: User Story 1 complete - минималистичный чат работает

---

## Phase 4: User Story 2 - Индикатор генерации ответа (Priority: P1)

**Goal**: Анимированный индикатор "Думаю..." при генерации

**Independent Test**: Отправить сообщение, увидеть индикатор, затем плавное появление ответа

### Implementation for User Story 2

- [X] T016 [US2] Add typing indicator CSS animation to interface/styles/claude.css
- [X] T017 [US2] Update chat_stream() in interface/unified_app.py to show "Думаю..." placeholder initially
- [X] T018 [US2] Add streaming cursor CSS (blinking cursor at end of streaming text) to interface/styles/claude.css
- [X] T019 [US2] Update streaming logic in interface/unified_app.py for smooth text appearance

**Checkpoint**: User Story 2 complete - индикатор генерации работает

---

## Phase 5: User Story 3 - Копирование блоков кода (Priority: P2)

**Goal**: Кнопка копирования на блоках кода при наведении

**Independent Test**: Получить ответ с кодом, навести курсор, нажать кнопку, проверить буфер обмена

### Implementation for User Story 3

- [X] T020 [US3] Add copy button JavaScript to interface/styles/claude.js (MutationObserver + Clipboard API)
- [X] T021 [US3] Add copy button CSS styling to interface/styles/claude.css (position, hover effects)
- [X] T022 [US3] Add "Скопировано!" confirmation CSS and animation to interface/styles/claude.css
- [X] T023 [US3] Inject JavaScript into gr.Blocks() in interface/unified_app.py

**Checkpoint**: User Story 3 complete - копирование кода работает

---

## Phase 6: User Story 4 - Тёмная/Светлая тема (Priority: P2)

**Goal**: Переключатель темы с сохранением в localStorage

**Independent Test**: Переключить тему, перезагрузить страницу, проверить сохранение выбора

### Implementation for User Story 4

- [X] T024 [US4] Add theme toggle switch component to sidebar in interface/unified_app.py
- [X] T025 [US4] Add theme switching JavaScript to interface/styles/claude.js (toggle CSS variables)
- [X] T026 [US4] Add localStorage save/load for theme preference in interface/styles/claude.js
- [X] T027 [US4] Add theme transition CSS (300ms fade) to interface/styles/claude.css
- [X] T028 [US4] Connect Gradio toggle event to JavaScript theme switch in interface/unified_app.py

**Checkpoint**: User Story 4 complete - переключение тем работает

---

## Phase 7: User Story 5 - Сворачиваемый sidebar (Priority: P3)

**Goal**: Sidebar с кнопкой сворачивания/разворачивания

**Independent Test**: Нажать кнопку сворачивания, проверить анимацию, состояние сохраняется

### Implementation for User Story 5

- [X] T029 [US5] Refactor interface/unified_app.py layout to separate sidebar gr.Column
- [X] T030 [US5] Add sidebar collapse button to interface/unified_app.py
- [X] T031 [US5] Add sidebar toggle Gradio state and callback in interface/unified_app.py
- [X] T032 [US5] Add sidebar collapse CSS animation to interface/styles/claude.css (width transition)
- [X] T033 [US5] Add sidebar state localStorage persistence in interface/styles/claude.js
- [X] T034 [US5] Add mobile responsive CSS (hide sidebar by default on width < 768px) to interface/styles/claude.css

**Checkpoint**: User Story 5 complete - сворачиваемый sidebar работает

---

## Phase 8: User Story 6 - Плавные анимации (Priority: P3)

**Goal**: Анимации появления сообщений, переключения тем, сворачивания

**Independent Test**: Выполнить любое действие, наблюдать плавные переходы (60fps)

### Implementation for User Story 6

- [X] T035 [US6] Add message appear animation CSS to interface/styles/claude.css (@keyframes slideUp)
- [X] T036 [US6] Add MutationObserver for new message animation trigger in interface/styles/claude.js
- [X] T037 [US6] Ensure all transitions use GPU acceleration (transform, opacity) in interface/styles/claude.css
- [X] T038 [US6] Add reduced-motion media query support to interface/styles/claude.css

**Checkpoint**: User Story 6 complete - все анимации плавные

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases, responsive design, final touches

- [X] T039 [P] Add LaTeX formula styling to interface/styles/claude.css
- [X] T040 [P] Add long message text wrapping CSS to interface/styles/claude.css
- [X] T041 [P] Add horizontal scroll for long code blocks in interface/styles/claude.css
- [X] T042 Test and fix mobile layout (320px - 768px) in interface/styles/claude.css
- [X] T043 Test and fix wide screen layout (1920px - 2560px) in interface/styles/claude.css
- [X] T044 Run quickstart.md validation checklist

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **US1-US6 (Phase 3-8)**: All depend on Foundational completion
- **Polish (Phase 9)**: Depends on all user stories

### User Story Dependencies

- **US1 (P1)**: Independent after Foundational
- **US2 (P1)**: Independent after Foundational
- **US3 (P2)**: Independent after Foundational
- **US4 (P2)**: Independent after Foundational (uses themes from Foundational)
- **US5 (P3)**: Independent after Foundational
- **US6 (P3)**: Independent after Foundational (enhances existing animations)

### Parallel Opportunities

Within each phase, tasks marked [P] can run in parallel:
- Phase 1: T002, T003, T004 (different files)
- Phase 2: T005, T006 (different theme files)

---

## Parallel Example: Setup Phase

```bash
# Launch in parallel (different files):
Task: "Create user avatar SVG in interface/assets/user_avatar.svg"
Task: "Create bot avatar SVG in interface/assets/bot_avatar.svg"
Task: "Create base CSS file in interface/styles/claude.css"
```

## Parallel Example: User Stories

```bash
# After Foundational complete, can work on stories in parallel:
# Developer A: US1 (чат-интерфейс)
# Developer B: US3 (копирование кода)
# Developer C: US4 (темы)
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup (4 tasks)
2. Complete Phase 2: Foundational (5 tasks)
3. Complete Phase 3: US1 - Минималистичный чат (6 tasks)
4. Complete Phase 4: US2 - Индикатор генерации (4 tasks)
5. **STOP and VALIDATE**: Минимальный Claude-like интерфейс готов
6. Deploy/demo MVP

**MVP Total**: 19 tasks

### Full Implementation

1. MVP (19 tasks)
2. Add US3: Копирование кода (+4 tasks)
3. Add US4: Темы (+5 tasks)
4. Add US5: Sidebar (+6 tasks)
5. Add US6: Анимации (+4 tasks)
6. Polish (+6 tasks)

**Full Total**: 44 tasks

---

## Notes

- [P] tasks = different files, no dependencies
- [US#] label maps task to specific user story
- Each user story should be independently testable
- CSS files can be edited by multiple tasks (merge carefully)
- JavaScript in claude.js accumulates features
- Commit after each task or logical group
