# Data Model: Claude-Style UI Redesign

**Feature**: 008-claude-ui-redesign
**Date**: 2026-02-03

## Entities

### UserPreferences

Настройки пользовательского интерфейса, сохраняемые в localStorage.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| theme | enum | "dark" | Текущая тема: "dark" \| "light" |
| sidebarCollapsed | boolean | false | Состояние sidebar |
| streamingEnabled | boolean | true | Включён ли стриминг |
| showThinking | boolean | true | Показывать размышления модели |

**Storage**: localStorage под ключом `mits_preferences`

**Example**:
```json
{
  "theme": "dark",
  "sidebarCollapsed": false,
  "streamingEnabled": true,
  "showThinking": true
}
```

---

### ThemeColors

Цветовая палитра темы (CSS variables).

| Variable | Dark Value | Light Value | Usage |
|----------|------------|-------------|-------|
| --bg-primary | #1a1a1a | #ffffff | Основной фон |
| --bg-secondary | #2d2d2d | #f5f5f5 | Фон сообщений |
| --bg-input | #3d3d3d | #e8e8e8 | Фон поля ввода |
| --text-primary | #e8e8e8 | #1a1a1a | Основной текст |
| --text-secondary | #a0a0a0 | #666666 | Вторичный текст |
| --accent | #10a37f | #10a37f | Акцентный цвет (Claude green) |
| --border | #404040 | #d0d0d0 | Границы |
| --shadow | rgba(0,0,0,0.3) | rgba(0,0,0,0.1) | Тени |

---

### Message (existing, extended)

Расширение существующей модели сообщения для UI.

| Field | Type | Description |
|-------|------|-------------|
| role | string | "user" \| "assistant" |
| content | string | Текст сообщения (markdown) |
| timestamp | datetime | Время отправки |
| isStreaming | boolean | Сообщение в процессе генерации |

---

### AnimationConfig

Параметры анимаций.

| Animation | Duration | Easing | Description |
|-----------|----------|--------|-------------|
| messageAppear | 200ms | ease-out | Появление сообщения |
| themeTransition | 300ms | ease-in-out | Переключение темы |
| sidebarToggle | 250ms | ease-in-out | Сворачивание sidebar |
| copyConfirm | 1500ms | - | Длительность "Скопировано!" |

---

## State Diagram: Theme Switching

```
[Dark Theme] ---(click toggle)---> [Transition 300ms] ---> [Light Theme]
     ^                                                           |
     |___________________(click toggle)__________________________|
```

## State Diagram: Sidebar

```
[Expanded] ---(click collapse)---> [Collapsed]
    ^                                   |
    |_______(click expand)______________|
```

## Storage Schema

### localStorage Keys

| Key | Type | Description |
|-----|------|-------------|
| mits_preferences | JSON string | UserPreferences объект |
| mits_theme | string | Shortcut для быстрого доступа к теме |

### Migration Strategy

При первом запуске с новым UI:
1. Проверить наличие `mits_preferences` в localStorage
2. Если нет — создать с default values
3. Применить сохранённые настройки к интерфейсу
