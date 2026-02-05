# Memory System Contracts

**Feature**: 006-mits-system-completion
**Date**: 2026-02-02

## Overview

The dual-memory system provides both short-term (session) and long-term (persistent) storage for student data and learning context.

## Session Memory Interface

Short-term, in-memory storage for current session context.

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

class ISessionMemory(ABC):
    """Interface for session memory operations."""

    @abstractmethod
    def create_session(self, student_id: str) -> str:
        """Create new session, return session_id."""
        pass

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[SessionMemory]:
        """Retrieve session by ID."""
        pass

    @abstractmethod
    def add_turn(self, session_id: str, turn: Turn) -> None:
        """Add conversation turn to session."""
        pass

    @abstractmethod
    def get_recent_turns(self, session_id: str, n: int = 10) -> List[Turn]:
        """Get N most recent conversation turns."""
        pass

    @abstractmethod
    def set_current_task(self, session_id: str, task: Task) -> None:
        """Set the current active task."""
        pass

    @abstractmethod
    def get_current_task(self, session_id: str) -> Optional[Task]:
        """Get the current active task."""
        pass

    @abstractmethod
    def update_cognitive_load(self, session_id: str, load: CognitiveLoad) -> None:
        """Update cognitive load estimate."""
        pass

    @abstractmethod
    def add_given_hint(self, session_id: str, hint_id: str) -> None:
        """Record that a hint was given."""
        pass

    @abstractmethod
    def get_given_hints(self, session_id: str) -> List[str]:
        """Get all hints given in this session."""
        pass

    @abstractmethod
    def get_context_for_llm(self, session_id: str, max_turns: int = 10) -> str:
        """Format session context for LLM prompt injection."""
        pass

    @abstractmethod
    def end_session(self, session_id: str) -> SessionSummary:
        """End session and return summary for long-term storage."""
        pass
```

### Session Memory Models

```python
class SessionMemory(BaseModel):
    """In-memory session state."""

    session_id: str
    student_id: str
    started_at: datetime
    status: SessionStatus = SessionStatus.ACTIVE

    # Conversation
    turns: List[Turn] = []
    current_task: Optional[Task] = None

    # State tracking
    given_hints: List[str] = []
    attempted_approaches: List[str] = []
    identified_errors: List[str] = []

    # Real-time metrics
    current_cognitive_load: CognitiveLoad = CognitiveLoad()
    time_on_current_task_seconds: float = 0.0
    last_interaction: datetime = None

    # Session totals
    tasks_attempted: int = 0
    tasks_solved: int = 0
    hints_given: int = 0
    questions_asked: int = 0
    direct_answers_given: int = 0

class SessionSummary(BaseModel):
    """Summary of completed session for long-term storage."""

    session_id: str
    student_id: str
    started_at: datetime
    ended_at: datetime
    duration_seconds: int

    # Performance
    tasks_attempted: int
    tasks_solved: int
    success_rate: float
    avg_hints_per_task: float
    telling_rate: float

    # Topics covered
    topics_practiced: List[str]
    topics_mastered: List[str]  # New mastery > 0.7
    topics_struggled: List[str] # Errors without resolution

    # Cognitive metrics
    avg_cognitive_load: CognitiveLoadLevel
    frustration_events: int
```

## Student Memory Interface

Long-term, persistent storage for student profiles and history.

```python
class IStudentMemory(ABC):
    """Interface for persistent student data."""

    @abstractmethod
    def create_student(self, student_id: str, name: Optional[str] = None) -> Student:
        """Create new student profile."""
        pass

    @abstractmethod
    def get_student(self, student_id: str) -> Optional[Student]:
        """Retrieve student by ID."""
        pass

    @abstractmethod
    def update_student(self, student: Student) -> None:
        """Update student profile."""
        pass

    @abstractmethod
    def delete_student(self, student_id: str) -> bool:
        """Delete student and all associated data."""
        pass

    # Knowledge State
    @abstractmethod
    def get_knowledge_state(self, student_id: str) -> KnowledgeState:
        """Get student's current knowledge state."""
        pass

    @abstractmethod
    def update_knowledge_state(
        self,
        student_id: str,
        topic_id: str,
        correct: bool,
        response_time_ms: int,
        hints_used: int
    ) -> TopicMastery:
        """Update knowledge state after interaction."""
        pass

    @abstractmethod
    def apply_knowledge_decay(self, student_id: str) -> None:
        """Apply forgetting curve to all topics."""
        pass

    @abstractmethod
    def get_recommended_topics(self, student_id: str, n: int = 5) -> List[str]:
        """Get topics recommended for practice."""
        pass

    # Learning History
    @abstractmethod
    def add_session_summary(self, summary: SessionSummary) -> None:
        """Store completed session summary."""
        pass

    @abstractmethod
    def get_session_history(
        self,
        student_id: str,
        limit: int = 10,
        since: Optional[datetime] = None
    ) -> List[SessionSummary]:
        """Get recent session summaries."""
        pass

    # Preferences
    @abstractmethod
    def get_preferences(self, student_id: str) -> Dict[str, Any]:
        """Get student preferences."""
        pass

    @abstractmethod
    def update_preference(self, student_id: str, key: str, value: Any) -> None:
        """Update a single preference."""
        pass

    @abstractmethod
    def get_effective_hint_types(self, student_id: str) -> Dict[HintType, float]:
        """Get effectiveness scores for hint types."""
        pass
```

### Student Memory Models

```python
class StudentMemoryData(BaseModel):
    """Complete student memory data structure."""

    # Core profile
    student: Student
    knowledge_state: KnowledgeState

    # Learning history
    session_summaries: List[SessionSummary] = []
    total_learning_time_hours: float = 0.0
    first_session: Optional[datetime] = None
    last_session: Optional[datetime] = None

    # Learned preferences
    effective_hint_types: Dict[HintType, float] = {}
    preferred_difficulty_by_topic: Dict[str, Difficulty] = {}
    avg_session_duration_minutes: float = 20.0

    # Statistics
    lifetime_tasks_attempted: int = 0
    lifetime_tasks_solved: int = 0
    lifetime_success_rate: float = 0.0
    streak_days: int = 0
    longest_streak: int = 0
```

## Memory Manager Interface

Coordinates both memory systems.

```python
class IMemoryManager(ABC):
    """Unified interface for memory operations."""

    @abstractmethod
    def start_session(self, student_id: str) -> Tuple[str, SessionMemory, KnowledgeState]:
        """
        Start a new session for student.
        Returns (session_id, session_memory, knowledge_state).
        Applies knowledge decay before returning state.
        """
        pass

    @abstractmethod
    def end_session(self, session_id: str) -> None:
        """
        End session:
        1. Generate session summary
        2. Update knowledge state
        3. Store to long-term memory
        4. Clean up session memory
        """
        pass

    @abstractmethod
    def record_interaction(
        self,
        session_id: str,
        student_input: str,
        tutor_response: str,
        task: Optional[Task],
        correct: Optional[bool],
        hints_used: List[str],
        response_time_ms: int
    ) -> None:
        """Record a complete interaction to both memories."""
        pass

    @abstractmethod
    def get_full_context(self, session_id: str) -> MemoryContext:
        """Get combined context from both memories for agent use."""
        pass

class MemoryContext(BaseModel):
    """Combined memory context for agents."""

    # From session memory
    session_id: str
    recent_turns: List[Turn]
    current_task: Optional[Task]
    session_hints_given: List[str]
    current_cognitive_load: CognitiveLoad

    # From student memory
    student: Student
    knowledge_state: KnowledgeState
    learning_style: LearningStyle
    effective_hint_types: Dict[HintType, float]

    # Computed
    recommended_difficulty: Difficulty
    topics_to_avoid: List[str]  # Recently failed, frustrating
    topics_to_reinforce: List[str]  # Weak but nearly mastered
```

## SQLite Storage Contract

```python
class ISQLiteStorage(ABC):
    """Interface for SQLite persistence."""

    @abstractmethod
    def connect(self, db_path: str) -> None:
        """Connect to database, creating if needed."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close database connection."""
        pass

    # CRUD operations
    @abstractmethod
    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """Insert row, return rowid."""
        pass

    @abstractmethod
    def update(self, table: str, data: Dict[str, Any], where: Dict[str, Any]) -> int:
        """Update rows matching where clause, return count."""
        pass

    @abstractmethod
    def select(
        self,
        table: str,
        columns: List[str],
        where: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Select rows matching criteria."""
        pass

    @abstractmethod
    def delete(self, table: str, where: Dict[str, Any]) -> int:
        """Delete rows matching where clause, return count."""
        pass

    # Transactions
    @abstractmethod
    def begin_transaction(self) -> None:
        """Begin transaction."""
        pass

    @abstractmethod
    def commit(self) -> None:
        """Commit transaction."""
        pass

    @abstractmethod
    def rollback(self) -> None:
        """Rollback transaction."""
        pass
```

## Event Contracts

Memory system events for logging and analytics.

```python
class MemoryEvent(BaseModel):
    """Base class for memory events."""
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    student_id: str
    session_id: Optional[str] = None

class SessionStartedEvent(MemoryEvent):
    event_type: str = "session_started"
    knowledge_state_snapshot: Dict[str, float]

class SessionEndedEvent(MemoryEvent):
    event_type: str = "session_ended"
    summary: SessionSummary

class KnowledgeUpdatedEvent(MemoryEvent):
    event_type: str = "knowledge_updated"
    topic_id: str
    old_mastery: float
    new_mastery: float
    correct: bool

class KnowledgeDecayAppliedEvent(MemoryEvent):
    event_type: str = "knowledge_decay"
    topics_affected: List[str]
    avg_decay: float

class IMemoryEventHandler(ABC):
    """Interface for handling memory events."""

    @abstractmethod
    def handle(self, event: MemoryEvent) -> None:
        """Process a memory event."""
        pass
```

## Usage Example

```python
# Initialize memory manager
memory_manager = MemoryManager(
    session_memory=InMemorySessionStore(),
    student_memory=SQLiteStudentStore("data/mits.db"),
    event_handler=LoggingEventHandler()
)

# Start session
session_id, session, knowledge = memory_manager.start_session("student-123")

# During tutoring loop
memory_manager.record_interaction(
    session_id=session_id,
    student_input="x² - 5x + 6 = 0, так x = 2 или x = 3",
    tutor_response="Отлично! Как ты проверил эти корни?",
    task=current_task,
    correct=True,
    hints_used=["algebra.quadratic.factoring.001"],
    response_time_ms=45000
)

# Get context for next agent call
context = memory_manager.get_full_context(session_id)

# End session
memory_manager.end_session(session_id)
```
