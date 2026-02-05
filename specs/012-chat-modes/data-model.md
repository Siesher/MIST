# Data Model: Universal Chat Modes

**Feature**: 012-chat-modes
**Date**: 2026-02-05

## Entities

### ChatMode (New Enum)

Represents the user-selectable chat modes.

| Value | Display Name (RU) | Icon | Color | Description |
|-------|-------------------|------|-------|-------------|
| `chat` | Обычный чат | MessageCircle | blue | Free-form conversation |
| `guided_learning` | Guided Learning | GraduationCap | green | Socratic tutoring |
| `task_generator` | Генерация задач | FileText | purple | Problem generation |

**Validation Rules**:
- Must be one of the three defined values
- Default: `guided_learning`

### Session (Extended)

Add `mode` field to existing StoredSession.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| mode | ChatMode | Yes | `guided_learning` | Current session mode |

**State Transitions**:
```
Any Mode → Any Mode (instant, preserves history)
```

**Validation Rules**:
- Mode can be changed at any time during active session
- Mode change does not clear message history
- Mode change takes effect on next user message

### ModeConfig (New)

Configuration for each mode's behavior.

| Field | Type | Description |
|-------|------|-------------|
| mode | ChatMode | Mode identifier |
| system_prompt | str | Mode-specific system prompt |
| use_rag | bool | Whether to query knowledge base |
| track_hints | bool | Whether to track hint usage |
| require_json_response | bool | Whether LLM must return JSON |
| allow_direct_answers | bool | Whether tutor can give direct answers |
| placeholder_text | str | Input field placeholder |

**Default Configurations**:

```python
MODE_CONFIGS = {
    "chat": ModeConfig(
        mode="chat",
        system_prompt=CHAT_MODE_SYSTEM,
        use_rag=False,
        track_hints=False,
        require_json_response=False,
        allow_direct_answers=True,
        placeholder_text="Напишите сообщение..."
    ),
    "guided_learning": ModeConfig(
        mode="guided_learning",
        system_prompt=GUIDED_LEARNING_SYSTEM,
        use_rag=True,
        track_hints=True,
        require_json_response=True,
        allow_direct_answers=False,
        placeholder_text="Ваш ответ или вопрос..."
    ),
    "task_generator": ModeConfig(
        mode="task_generator",
        system_prompt=TASK_GENERATOR_SYSTEM,
        use_rag=True,
        track_hints=False,
        require_json_response=True,
        allow_direct_answers=True,
        placeholder_text="Какую тему и сложность задач?"
    )
}
```

## Relationships

```
Session 1──1 ChatMode (current mode)
ChatMode 1──1 ModeConfig (configuration)
```

## Frontend Types

### TypeScript Definitions

```typescript
type ChatMode = "chat" | "guided_learning" | "task_generator";

interface ModeInfo {
  value: ChatMode;
  label: string;
  icon: string;
  color: string;
  placeholder: string;
}

const MODES: ModeInfo[] = [
  {
    value: "chat",
    label: "Обычный чат",
    icon: "MessageCircle",
    color: "blue",
    placeholder: "Напишите сообщение..."
  },
  {
    value: "guided_learning",
    label: "Guided Learning",
    icon: "GraduationCap",
    color: "green",
    placeholder: "Ваш ответ или вопрос..."
  },
  {
    value: "task_generator",
    label: "Генерация задач",
    icon: "FileText",
    color: "purple",
    placeholder: "Какую тему и сложность задач?"
  }
];
```

## Migration Notes

- No database migration required (in-memory storage)
- Existing sessions default to `guided_learning` mode
- Frontend localStorage may store preferred mode per user
