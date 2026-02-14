# Data Model: ITS Integration

**Feature**: 001-its-integration
**Date**: 2026-01-30

## Entity Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  StudentSession │────▶│  StudentProfile │────▶│   SkillMastery  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │
        │                       │
        ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│   DialogTurn    │     │ MisconceptionLog│
└─────────────────┘     └─────────────────┘
        │
        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│      Task       │────▶│      Hint       │────▶│  Misconception  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## Core Entities

### StudentSession

Active tutoring session tracking.

| Field | Type | Description |
|-------|------|-------------|
| session_id | UUID | Unique session identifier |
| student_id | string | Student identifier (anonymous or authenticated) |
| discipline | enum | MATH, CODING, PHYSICS, CHEMISTRY, BIOLOGY |
| current_task_id | UUID? | Currently active task |
| started_at | datetime | Session start timestamp |
| last_activity_at | datetime | Last interaction timestamp |
| mode | enum | FULL, FAST, DIAGNOSTIC |
| dialog_history | DialogTurn[] | Conversation turns in session |
| metrics | SessionMetrics | Computed session metrics |

**State Transitions**:
- `ACTIVE` → Student is engaged
- `IDLE` → No activity for 5+ minutes
- `COMPLETED` → Task solved successfully
- `ABANDONED` → Session ended without completion

---

### StudentProfile

Persistent learner model across sessions.

| Field | Type | Description |
|-------|------|-------------|
| student_id | string | Unique student identifier |
| created_at | datetime | Profile creation date |
| skill_masteries | SkillMastery[] | Per-skill BKT probabilities |
| misconception_history | MisconceptionLog[] | Detected misconceptions |
| preferred_strategy | enum? | GUIDED_DISCOVERY, SCAFFOLDED, etc. |
| total_sessions | int | Total session count |
| total_tasks_attempted | int | Total tasks tried |
| total_tasks_solved | int | Successfully completed tasks |
| average_hints_per_task | float | Mean hints used |
| disciplines_studied | set[Discipline] | Disciplines engaged with |

---

### SkillMastery

BKT-based skill mastery tracking.

| Field | Type | Description |
|-------|------|-------------|
| skill_id | string | Skill identifier (e.g., "linear_equations") |
| student_id | string | Owner student |
| p_mastery | float | Current mastery probability [0, 1] |
| p_L0 | float | Initial learning probability |
| p_T | float | Transition (learning) probability |
| p_S | float | Slip probability |
| p_G | float | Guess probability |
| attempts | int | Total attempts on this skill |
| successes | int | Successful attempts |
| last_updated | datetime | Last update timestamp |

**Validation Rules**:
- All probabilities ∈ [0.0, 1.0]
- `p_mastery` updated via BKT formula after each attempt
- Threshold for mastery: p_mastery ≥ 0.85

---

### Task

Educational problem definition.

| Field | Type | Description |
|-------|------|-------------|
| task_id | UUID | Unique task identifier |
| discipline | enum | MATH, CODING, etc. |
| topic | string | Topic category (e.g., "quadratic_equations") |
| difficulty | enum | EASY, MEDIUM, HARD |
| statement | string | Problem text (markdown supported) |
| correct_answer | string | Expected answer (for validation) |
| answer_validator | string? | Custom validation function name |
| related_skills | string[] | Skills required/practiced |
| hints | HintReference[] | Associated hint IDs |
| misconceptions | string[] | Common misconception IDs |
| created_at | datetime | Task creation date |
| usage_count | int | Times presented to students |
| success_rate | float | Historical success rate |

**Task Types**:
- `MATH_ALGEBRAIC`: Equation solving
- `MATH_CALCULUS`: Derivatives, integrals
- `MATH_GEOMETRY`: Proofs, calculations
- `CODING_ALGORITHM`: Algorithm implementation
- `CODING_DEBUG`: Bug finding/fixing
- `PHYSICS_KINEMATICS`, etc.

---

### Hint

Progressive hint from knowledge base.

| Field | Type | Description |
|-------|------|-------------|
| hint_id | UUID | Unique hint identifier |
| topic | string | Associated topic |
| level | enum | CONCEPTUAL, PROCEDURAL, SPECIFIC, WORKED_EXAMPLE |
| content | string | Hint text (markdown) |
| triggers | string[] | Patterns that trigger this hint |
| related_misconceptions | string[] | Misconceptions this addresses |
| tags | string[] | Searchable tags |
| embedding | float[] | Vector embedding for RAG |

**Level Progression**:
1. `CONCEPTUAL`: General principle reminder
2. `PROCEDURAL`: Step-by-step guidance
3. `SPECIFIC`: Task-specific clue
4. `WORKED_EXAMPLE`: Similar solved problem

---

### Misconception

Common student error pattern.

| Field | Type | Description |
|-------|------|-------------|
| misconception_id | string | Unique identifier |
| name | string | Short descriptive name |
| description | string | Detailed explanation |
| detection_patterns | string[] | Regex patterns to detect |
| discipline | enum | Associated discipline |
| topics | string[] | Topics where this occurs |
| correction_strategy | string | How to address this |
| frequency | int | Times detected across all students |
| embedding | float[] | Vector embedding for matching |

---

### DialogTurn

Single exchange in tutoring conversation.

| Field | Type | Description |
|-------|------|-------------|
| turn_id | int | Turn number in session (1-indexed) |
| session_id | UUID | Parent session |
| timestamp | datetime | Turn timestamp |
| student_message | string | Student input |
| student_code | string? | Code submission (if coding task) |
| profiler_result | ProfilerOutput | Diagnosis from ProfilerAgent |
| planner_result | PlannerOutput | Strategy from PlannerAgent |
| tutor_response | string | Generated tutor message |
| verifier_result | VerifierOutput | Quality check results |
| hints_used | string[] | Hint IDs retrieved/used |
| rag_context | string[] | RAG-retrieved document IDs |
| latency_ms | int | Total response generation time |

---

### AgentOutput (Abstract)

Base structure for agent outputs.

#### ProfilerOutput

| Field | Type | Description |
|-------|------|-------------|
| error_type | enum? | CONCEPTUAL, PROCEDURAL, CARELESS, NOTATION, INCOMPLETE, MISCONCEPTION |
| confidence_level | enum | LOW, MEDIUM, HIGH, CONFUSED |
| detected_misconceptions | string[] | Matched misconception IDs |
| knowledge_gaps | string[] | Missing prerequisite skills |
| analysis_reasoning | string | Explanation of diagnosis |

#### PlannerOutput

| Field | Type | Description |
|-------|------|-------------|
| strategy | enum | Teaching strategy selected |
| teaching_moves | string[] | Sequence of moves |
| tone | enum | SUPPORTIVE, NEUTRAL, CHALLENGING |
| hint_level | enum | Recommended hint level |
| reasoning | string | Why this strategy |

#### VerifierOutput

| Field | Type | Description |
|-------|------|-------------|
| approved | bool | Response passes quality check |
| issues | QualityIssue[] | Detected issues |
| severity | enum | INFO, WARNING, CRITICAL |
| suggestions | string[] | Improvement suggestions |
| answer_leak_detected | bool | Direct answer found |

---

### SessionMetrics

Computed metrics for a session.

| Field | Type | Description |
|-------|------|-------------|
| turn_count | int | Total dialog turns |
| hints_requested | int | Explicit hint requests |
| hints_provided | int | Hints given (includes proactive) |
| time_to_solution_sec | int? | Time to correct answer |
| success | bool | Task completed successfully |
| answer_revealed | bool | Direct answer given (Telling) |
| student_satisfaction | int? | 1-5 rating if collected |

---

## Enumerations

### Discipline
```
MATH, CODING, PHYSICS, CHEMISTRY, BIOLOGY
```

### Difficulty
```
EASY, MEDIUM, HARD
```

### ErrorType
```
CONCEPTUAL, PROCEDURAL, CARELESS, NOTATION, INCOMPLETE, MISCONCEPTION
```

### ConfidenceLevel
```
LOW, MEDIUM, HIGH, CONFUSED
```

### TeachingStrategy
```
GUIDED_DISCOVERY, SCAFFOLDED, ERROR_CORRECTION, CONCEPTUAL_REPAIR,
ENCOURAGEMENT, REVIEW, DIRECT_INSTRUCTION
```

### HintLevel
```
CONCEPTUAL, PROCEDURAL, SPECIFIC, WORKED_EXAMPLE
```

### QualityIssueType
```
ANSWER_LEAK, TOO_VERBOSE, OFF_TOPIC, MISSING_QUESTION,
INAPPROPRIATE_TONE, FACTUAL_ERROR, UNSUPPORTED_CLAIM
```

### SessionMode
```
FULL      # All agents active
FAST      # Skip some verification for speed
DIAGNOSTIC # Extra logging for debugging
```

---

## Relationships

| From | To | Cardinality | Description |
|------|-----|-------------|-------------|
| StudentSession | StudentProfile | N:1 | Sessions belong to a student |
| StudentSession | Task | N:1 | Active task in session |
| StudentSession | DialogTurn | 1:N | Session contains turns |
| StudentProfile | SkillMastery | 1:N | Student has skill masteries |
| StudentProfile | MisconceptionLog | 1:N | History of misconceptions |
| Task | Hint | N:M | Tasks reference hints |
| Task | Misconception | N:M | Tasks map to misconceptions |
| Hint | Misconception | N:M | Hints address misconceptions |
| SkillMastery | Skill (graph) | N:1 | Mastery for specific skill |

---

## Data Storage

### Persistent Storage (JSON/SQLite)

- `StudentProfile`: Long-term persistence
- `SkillMastery`: Per-student skill state
- `Task`: Task bank (read-mostly)
- `Hint`: Knowledge base (read-only)
- `Misconception`: Error patterns (read-only)

### Session Storage (In-Memory)

- `StudentSession`: Active sessions
- `DialogTurn`: Current session turns
- `AgentOutputs`: Temporary agent results

### Vector Storage (ChromaDB)

- Hint embeddings for RAG retrieval
- Misconception embeddings for matching
- Task embeddings for similarity search

---

## Validation Rules

1. **Skill Probabilities**: All BKT probabilities ∈ [0.0, 1.0]
2. **Session Duration**: Max 8 hours before forced closure
3. **Turn Limit**: Warning at 20 turns, limit at 50 turns
4. **Hint Progression**: Must follow level order (1→2→3→4)
5. **Answer Validation**: Task `correct_answer` or `answer_validator` required
6. **Misconception Detection**: At least one detection pattern required
7. **Task Completeness**: All tasks must have `related_skills` populated
