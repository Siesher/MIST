# Data Model: MITS System Completion

**Feature**: 006-mits-system-completion
**Date**: 2026-02-02

## Entity Relationship Diagram

```
┌─────────────┐       ┌──────────────────┐       ┌─────────────┐
│   Student   │──1:1──│  KnowledgeState  │──N:1──│    Topic    │
└─────────────┘       └──────────────────┘       └─────────────┘
       │                                                │
       │1:N                                            │1:N
       ▼                                                ▼
┌─────────────┐       ┌──────────────────┐       ┌─────────────┐
│   Session   │──N:N──│      Task        │──N:N──│Misconception│
└─────────────┘       └──────────────────┘       └─────────────┘
       │                      │
       │1:N                   │1:N
       ▼                      ▼
┌─────────────┐       ┌──────────────────┐
│    Turn     │       │      Hint        │
└─────────────┘       └──────────────────┘
```

## Core Entities

### Student (Enhanced)

Represents a learner with persistent profile and preferences.

```python
class Student(BaseModel):
    """Student profile with learning history and preferences."""

    # Identity
    student_id: str = Field(description="Unique identifier (UUID)")
    name: Optional[str] = Field(default=None, description="Display name")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Learning Profile
    preferred_language: str = Field(default="ru", description="ru/en")
    learning_style: LearningStyle = Field(default=LearningStyle.BALANCED)
    difficulty_preference: Difficulty = Field(default=Difficulty.MEDIUM)

    # Cognitive Profile
    avg_response_time: float = Field(default=60.0, description="Seconds")
    frustration_threshold: int = Field(default=3, description="Errors before simplify")

    # Statistics
    total_sessions: int = Field(default=0)
    total_tasks_attempted: int = Field(default=0)
    total_tasks_solved: int = Field(default=0)
    last_active: Optional[datetime] = Field(default=None)

class LearningStyle(str, Enum):
    VISUAL = "visual"         # Prefers diagrams, step-by-step
    CONCEPTUAL = "conceptual" # Prefers theory first
    PRACTICAL = "practical"   # Prefers examples first
    BALANCED = "balanced"     # No strong preference
```

### KnowledgeState (New - DKT Enhanced)

Tracks mastery level for each topic with temporal decay.

```python
class TopicMastery(BaseModel):
    """Mastery state for a single topic."""

    topic_id: str
    mastery: float = Field(ge=0.0, le=1.0, default=0.3)

    # BKT Parameters (per-topic tunable)
    p_learn: float = Field(default=0.1, description="Learning rate")
    p_forget: float = Field(default=0.05, description="Forgetting rate")
    p_guess: float = Field(default=0.2, description="Guessing probability")
    p_slip: float = Field(default=0.1, description="Slip probability")

    # Temporal tracking
    last_practiced: Optional[datetime] = None
    practice_count: int = 0
    correct_count: int = 0

    # DKT-specific
    learning_velocity: float = Field(default=0.0, description="Rate of improvement")
    difficulty_history: List[float] = Field(default_factory=list)

class KnowledgeState(BaseModel):
    """Complete knowledge state for a student."""

    student_id: str
    topics: Dict[str, TopicMastery] = Field(default_factory=dict)

    # DKT Model State (after 10+ interactions)
    use_dkt: bool = Field(default=False)
    dkt_hidden_state: Optional[List[float]] = None  # LSTM hidden state
    interaction_count: int = Field(default=0)

    # Aggregate metrics
    overall_mastery: float = Field(default=0.3)
    strongest_topics: List[str] = Field(default_factory=list)
    weakest_topics: List[str] = Field(default_factory=list)

    def apply_decay(self, decay_rate: float = 0.05) -> None:
        """Apply Ebbinghaus forgetting curve to all topics."""
        now = datetime.utcnow()
        for topic in self.topics.values():
            if topic.last_practiced:
                days = (now - topic.last_practiced).days
                topic.mastery *= math.exp(-decay_rate * days)
```

### CognitiveLoad (New)

Estimates current cognitive load for adaptive difficulty.

```python
class CognitiveLoadLevel(str, Enum):
    LOW = "low"           # Can increase difficulty
    OPTIMAL = "optimal"   # Ideal learning zone
    HIGH = "high"         # Signs of struggle
    OVERLOAD = "overload" # Simplify immediately

class CognitiveLoad(BaseModel):
    """Real-time cognitive load estimation."""

    level: CognitiveLoadLevel = CognitiveLoadLevel.OPTIMAL
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)

    # Contributing signals
    response_time_ratio: float = Field(default=1.0, description="Actual/expected time")
    consecutive_errors: int = Field(default=0)
    hint_requests: int = Field(default=0)
    task_complexity: float = Field(default=0.5, description="0-1 scale")

    # Thresholds for level determination
    @classmethod
    def estimate(cls, signals: Dict[str, float]) -> "CognitiveLoad":
        """Estimate cognitive load from multiple signals."""
        score = 0.0

        # Response time contribution (40%)
        time_ratio = signals.get("response_time_ratio", 1.0)
        if time_ratio > 2.0:
            score += 0.4
        elif time_ratio > 1.5:
            score += 0.2

        # Error contribution (30%)
        errors = signals.get("consecutive_errors", 0)
        score += min(errors * 0.1, 0.3)

        # Hint requests (20%)
        hints = signals.get("hint_requests", 0)
        score += min(hints * 0.05, 0.2)

        # Task complexity (10%)
        score += signals.get("task_complexity", 0.5) * 0.1

        # Determine level
        if score < 0.25:
            level = CognitiveLoadLevel.LOW
        elif score < 0.5:
            level = CognitiveLoadLevel.OPTIMAL
        elif score < 0.75:
            level = CognitiveLoadLevel.HIGH
        else:
            level = CognitiveLoadLevel.OVERLOAD

        return cls(level=level, confidence=0.7)
```

### Topic (Enhanced)

Mathematical/programming concept with prerequisites.

```python
class Topic(BaseModel):
    """Educational topic with skill graph connections."""

    topic_id: str
    name: str
    name_ru: str  # Russian name

    # Classification
    subject: Subject  # MATH, PROGRAMMING, PHYSICS, etc.
    category: str     # e.g., "algebra", "calculus", "algorithms"
    difficulty: Difficulty

    # Skill Graph
    prerequisites: List[str] = Field(default_factory=list, description="Topic IDs")
    related_topics: List[str] = Field(default_factory=list)

    # Educational Content
    description: str
    description_ru: str
    key_concepts: List[str] = Field(default_factory=list)
    common_misconceptions: List[str] = Field(default_factory=list, description="Misconception IDs")

    # BKT Defaults
    default_p_learn: float = 0.1
    default_p_forget: float = 0.05
```

### Session (Enhanced)

Single tutoring interaction with metrics.

```python
class Session(BaseModel):
    """Tutoring session with full context."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    student_id: str

    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None

    # State
    status: SessionStatus = SessionStatus.ACTIVE
    current_task: Optional[Task] = None
    conversation: List[Turn] = Field(default_factory=list)

    # Metrics
    tasks_attempted: int = 0
    tasks_solved: int = 0
    hints_given: int = 0
    socratic_questions: int = 0
    direct_answers: int = 0  # Should be near 0

    # Cognitive tracking
    cognitive_load_history: List[CognitiveLoad] = Field(default_factory=list)
    avg_response_time: float = 0.0

    # Quality metrics
    telling_rate: float = Field(default=0.0, description="direct_answers/total_responses")

class SessionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
```

### Turn (Conversation Turn)

```python
class Turn(BaseModel):
    """Single conversation turn."""

    turn_id: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Content
    role: TurnRole  # STUDENT, TUTOR, SYSTEM
    content: str
    content_type: ContentType = ContentType.TEXT

    # Metadata
    task_id: Optional[str] = None
    hint_ids: List[str] = Field(default_factory=list)
    tutor_move: Optional[TutorMove] = None

    # Timing
    response_time_ms: Optional[int] = None

class TurnRole(str, Enum):
    STUDENT = "student"
    TUTOR = "tutor"
    SYSTEM = "system"

class ContentType(str, Enum):
    TEXT = "text"
    CODE = "code"
    MATH = "math"  # LaTeX
    MIXED = "mixed"
```

### Task (Enhanced)

```python
class Task(BaseModel):
    """Educational task with full metadata."""

    task_id: str

    # Content
    title: str
    title_ru: str
    problem: str  # May contain LaTeX
    problem_ru: str

    # Classification
    subject: Subject
    topics: List[str]  # Topic IDs
    difficulty: Difficulty

    # Solution
    solution: Optional[str] = None
    solution_steps: List[str] = Field(default_factory=list)
    answer: Optional[str] = None

    # For programming tasks
    test_cases: List[TestCase] = Field(default_factory=list)
    starter_code: Optional[str] = None

    # Hints (progressive)
    hints: List[str] = Field(default_factory=list, description="Hint IDs, ordered")
    common_errors: List[str] = Field(default_factory=list, description="Misconception IDs")

    # Metrics
    avg_attempts: float = 3.0
    success_rate: float = 0.5
```

### Hint (RAG Entity)

```python
class Hint(BaseModel):
    """Educational hint for RAG retrieval."""

    hint_id: str

    # Content
    content: str
    content_ru: str

    # Classification
    topic_id: str
    hint_level: HintLevel
    hint_type: HintType

    # RAG
    embedding: Optional[List[float]] = None
    keywords: List[str] = Field(default_factory=list)

    # Usage tracking
    retrieval_count: int = 0
    effectiveness_score: float = 0.5

class HintLevel(str, Enum):
    CONCEPTUAL = "conceptual"   # High-level, theoretical
    PROCEDURAL = "procedural"   # Step-by-step guidance
    SPECIFIC = "specific"       # Detailed, near-answer

class HintType(str, Enum):
    QUESTION = "question"       # Socratic question
    EXAMPLE = "example"         # Worked example reference
    REMINDER = "reminder"       # Concept reminder
    VISUALIZATION = "visualization"  # Suggest diagram/visualization
```

### Misconception (RAG Entity)

```python
class Misconception(BaseModel):
    """Common error pattern for targeted correction."""

    misconception_id: str

    # Content
    name: str
    name_ru: str
    description: str
    description_ru: str

    # Detection
    topic_id: str
    error_patterns: List[str]  # Regex or AST patterns
    triggers: List[str]        # Keywords that suggest this error

    # Correction
    correction_question: str     # Socratic question to address
    correction_question_ru: str
    correction_hints: List[str]  # Hint IDs for correction

    # RAG
    embedding: Optional[List[float]] = None

    # Statistics
    occurrence_count: int = 0
    correction_success_rate: float = 0.5
```

## Memory Models

### SessionMemory (Short-term)

```python
class SessionMemory(BaseModel):
    """In-memory session context."""

    session_id: str

    # Conversation context
    recent_turns: List[Turn] = Field(default_factory=list, max_items=20)
    current_topic: Optional[str] = None
    current_task: Optional[Task] = None

    # Problem-solving state
    attempted_approaches: List[str] = Field(default_factory=list)
    given_hints: List[str] = Field(default_factory=list)
    identified_errors: List[str] = Field(default_factory=list)

    # Real-time metrics
    current_cognitive_load: CognitiveLoad = Field(default_factory=CognitiveLoad)
    time_on_current_task: float = 0.0

    def get_context_for_llm(self, max_turns: int = 10) -> str:
        """Format recent context for LLM prompt."""
        ...
```

### StudentMemory (Long-term)

```python
class StudentMemory(BaseModel):
    """Persistent student data."""

    student: Student
    knowledge_state: KnowledgeState

    # Learning history
    session_summaries: List[SessionSummary] = Field(default_factory=list)
    topic_history: Dict[str, List[TopicInteraction]] = Field(default_factory=dict)

    # Preferences (learned over time)
    effective_hint_types: Dict[HintType, float] = Field(default_factory=dict)
    preferred_difficulty_by_topic: Dict[str, Difficulty] = Field(default_factory=dict)

    def save(self, db_path: str) -> None:
        """Persist to SQLite."""
        ...

    @classmethod
    def load(cls, student_id: str, db_path: str) -> Optional["StudentMemory"]:
        """Load from SQLite."""
        ...
```

## State Transitions

### Knowledge State Updates

```
Initial State (p_init=0.3)
         │
         ▼
    ┌─────────────────┐
    │ Student attempts│
    │     task        │
    └─────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
 Correct   Incorrect
    │         │
    ▼         ▼
p_mastery  p_mastery
increases  may decrease
    │         │
    └────┬────┘
         ▼
    ┌─────────────────┐
    │  Apply decay    │
    │ if time passed  │
    └─────────────────┘
         │
         ▼
    Updated KnowledgeState
```

### Cognitive Load State Machine

```
          LOW
           │
    ┌──────┼──────┐
    │      ▼      │
    │   OPTIMAL   │◄───┐
    │      │      │    │
    │      ▼      │    │
    │    HIGH     │────┘
    │      │      │ (successful
    │      ▼      │  problem)
    └► OVERLOAD ──┘
       (simplify
        task)
```

## Validation Rules

1. **Mastery bounds**: 0.0 ≤ mastery ≤ 1.0
2. **BKT probability bounds**: All p_* values in [0, 1]
3. **Topic prerequisites**: Cannot attempt topic if prerequisites < 0.5 mastery
4. **Hint progression**: Must give conceptual before procedural before specific
5. **Session integrity**: ended_at must be after started_at
6. **Telling rate**: Should remain < 0.15 (15%) per constitution

## Database Schema (SQLite)

```sql
-- Students table
CREATE TABLE students (
    student_id TEXT PRIMARY KEY,
    name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    preferred_language TEXT DEFAULT 'ru',
    learning_style TEXT DEFAULT 'balanced',
    total_sessions INTEGER DEFAULT 0,
    last_active TIMESTAMP
);

-- Knowledge state table
CREATE TABLE knowledge_state (
    student_id TEXT,
    topic_id TEXT,
    mastery REAL DEFAULT 0.3,
    p_learn REAL DEFAULT 0.1,
    p_forget REAL DEFAULT 0.05,
    last_practiced TIMESTAMP,
    practice_count INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    PRIMARY KEY (student_id, topic_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- Sessions table
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    student_id TEXT,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    status TEXT,
    tasks_attempted INTEGER DEFAULT 0,
    tasks_solved INTEGER DEFAULT 0,
    hints_given INTEGER DEFAULT 0,
    telling_rate REAL DEFAULT 0.0,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- Session turns (for history)
CREATE TABLE turns (
    turn_id INTEGER,
    session_id TEXT,
    timestamp TIMESTAMP,
    role TEXT,
    content TEXT,
    task_id TEXT,
    tutor_move TEXT,
    response_time_ms INTEGER,
    PRIMARY KEY (session_id, turn_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```
