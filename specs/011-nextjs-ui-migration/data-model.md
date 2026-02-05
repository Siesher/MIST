# Data Model: Next.js UI Migration

**Feature**: 011-nextjs-ui-migration
**Date**: 2026-02-04

## Overview

This document defines API-level data models. Core domain models remain in `src/data/schemas.py` unchanged.

---

## API Schemas

### Session

Represents a tutoring conversation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (UUID) | Yes | Unique session identifier |
| created_at | datetime | Yes | Creation timestamp |
| updated_at | datetime | Yes | Last activity timestamp |
| topic | string | No | Math topic (derivatives, integrals, etc.) |
| difficulty | enum | No | easy, medium, hard, olympiad |
| task_id | string | No | Associated task ID if structured problem |
| status | enum | Yes | active, completed, abandoned |
| message_count | integer | Yes | Total messages in session |
| is_solved | boolean | Yes | Whether task was solved |
| hints_used | integer | Yes | Number of hints requested |

**Example**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-02-04T10:30:00Z",
  "updated_at": "2026-02-04T10:45:00Z",
  "topic": "derivatives",
  "difficulty": "medium",
  "task_id": "task_deriv_001",
  "status": "active",
  "message_count": 12,
  "is_solved": false,
  "hints_used": 1
}
```

---

### Message

Individual chat message.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (UUID) | Yes | Message identifier |
| session_id | string | Yes | Parent session ID |
| role | enum | Yes | user, tutor, system |
| content | string | Yes | Message text (may include LaTeX) |
| timestamp | datetime | Yes | Message creation time |
| move_type | enum | No | Tutor move type (scaffolding, hint, etc.) |
| is_correct | boolean | No | If answer attempt, whether correct |
| thinking | string | No | Chain-of-thought reasoning (optional display) |

**Example**:
```json
{
  "id": "msg_001",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "tutor",
  "content": "Отлично! А что ты знаешь о правиле степени? $\\frac{d}{dx}x^n = nx^{n-1}$",
  "timestamp": "2026-02-04T10:31:15Z",
  "move_type": "scaffolding",
  "is_correct": null,
  "thinking": null
}
```

---

### Task

Math problem for structured practice.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Task identifier |
| topic | string | Yes | Math topic |
| difficulty | enum | Yes | Difficulty level |
| problem | string | Yes | Problem statement (with LaTeX) |
| hints | array[string] | Yes | Progressive hints (max 3) |
| answer | string | Yes | Correct answer |
| solution | string | No | Step-by-step solution |
| skills | array[string] | Yes | Skills tested |

**Example**:
```json
{
  "id": "task_deriv_001",
  "topic": "derivatives",
  "difficulty": "medium",
  "problem": "Найдите производную функции $f(x) = x^3 \\sin(x)$",
  "hints": [
    "Подумай, какое правило применяется для произведения двух функций?",
    "Правило произведения: $(uv)' = u'v + uv'$",
    "Производная $x^3$ равна $3x^2$, а производная $\\sin(x)$ равна $\\cos(x)$"
  ],
  "answer": "3x^2 \\sin(x) + x^3 \\cos(x)",
  "solution": "По правилу произведения...",
  "skills": ["product_rule", "power_rule", "trig_derivatives"]
}
```

---

### StudentProfile

Aggregated learning data.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| student_id | string | Yes | Student identifier |
| total_sessions | integer | Yes | Lifetime session count |
| success_rate | float | Yes | Percentage of solved tasks |
| total_time_minutes | integer | Yes | Total study time |
| streak_days | integer | Yes | Current daily streak |
| mastery_by_topic | object | Yes | Topic → mastery score (0.0-1.0) |
| weak_skills | array[string] | Yes | Skills needing practice |
| strong_skills | array[string] | Yes | Mastered skills |
| recommended_topic | string | No | Suggested next topic |

**Example**:
```json
{
  "student_id": "student_001",
  "total_sessions": 45,
  "success_rate": 0.73,
  "total_time_minutes": 1250,
  "streak_days": 7,
  "mastery_by_topic": {
    "derivatives": 0.85,
    "integrals": 0.62,
    "limits": 0.71
  },
  "weak_skills": ["integration_by_parts", "trig_substitution"],
  "strong_skills": ["power_rule", "chain_rule", "basic_limits"],
  "recommended_topic": "integrals"
}
```

---

### SessionAnalytics

Detailed analytics for a time period.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| period_start | datetime | Yes | Analytics period start |
| period_end | datetime | Yes | Analytics period end |
| sessions_count | integer | Yes | Sessions in period |
| tasks_attempted | integer | Yes | Tasks started |
| tasks_solved | integer | Yes | Tasks completed |
| avg_session_minutes | float | Yes | Average session duration |
| avg_hints_per_task | float | Yes | Average hints used |
| progress_by_day | array | Yes | Daily progress data |
| mastery_trend | array | Yes | Mastery changes over time |

---

## Enums

### Difficulty
- `easy`
- `medium`
- `hard`
- `olympiad`

### MessageRole
- `user`
- `tutor`
- `system`

### SessionStatus
- `active`
- `completed`
- `abandoned`

### TutorMoveType
- `scaffolding` - Guide with questions
- `problematize` - Challenge assumptions
- `rectify` - Point out errors
- `encourage` - Celebrate progress
- `hint` - Provide progressive hint
- `tell` - Reveal answer (last resort)
- `clarify` - Explain concept

---

## WebSocket Message Types

### Client → Server

| Type | Fields | Description |
|------|--------|-------------|
| message | content, timestamp | Send chat message |
| hint_request | - | Request next hint |
| typing_start | - | User started typing |
| typing_stop | - | User stopped typing |

### Server → Client

| Type | Fields | Description |
|------|--------|-------------|
| token | content, is_thinking | Streaming token |
| response_complete | response, session_state | Full response |
| knowledge_update | mastery_changes | Skill updates |
| error | code, message | Error notification |

---

## State Transitions

### Session Lifecycle

```
[Created] → [Active] → [Completed]
                    ↘ [Abandoned]

Created: New session initialized
Active: Ongoing tutoring conversation
Completed: Task solved or session ended normally
Abandoned: Session inactive for >24 hours
```

### Task Solving Flow

```
[No Task] → [Task Loaded] → [Attempting] → [Solved]
                         ↘ [Hint Used] ↗
                         ↘ [Answer Revealed]

Attempting: Student working on problem
Hint Used: Hint requested (up to 3)
Answer Revealed: Solution shown (penalized)
Solved: Correct answer submitted
```

---

## Relationships

```
StudentProfile 1 ←──→ N Session
Session 1 ←──→ N Message
Session 0..1 ←──→ 1 Task
```

- One student has many sessions
- One session has many messages
- One session optionally references one task
- Tasks are shared (read from task bank, not owned by session)

---

## Validation Rules

### Session
- topic: Must be from known topics list
- difficulty: Must be valid enum value
- hints_used: 0 ≤ hints_used ≤ 3

### Message
- content: 1-10000 characters
- role: Must be valid enum
- move_type: Required if role is "tutor"

### Task
- hints: Array of 1-3 strings
- difficulty: Must match topic availability

### StudentProfile
- mastery values: 0.0 ≤ mastery ≤ 1.0
- success_rate: 0.0 ≤ rate ≤ 1.0
