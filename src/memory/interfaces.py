"""
Memory System Interfaces

Abstract base classes defining contracts for session and student memory.
"""

import sys
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.schemas import (
    CognitiveLoad,
    ConversationTurn,
    Difficulty,
    HintType,
    KnowledgeState,
    SessionSummary,
    Task,
    TopicMastery,
)


class ISessionMemory(ABC):
    """Interface for session memory operations (short-term, in-memory)."""

    @abstractmethod
    def create_session(self, student_id: str) -> str:
        """Create new session, return session_id."""
        pass

    @abstractmethod
    def get_session_id(self) -> Optional[str]:
        """Get current session ID."""
        pass

    @abstractmethod
    def add_turn(self, role: str, content: str, task_id: Optional[str] = None,
                 tutor_move: Optional[str] = None, response_time_ms: Optional[int] = None) -> None:
        """Add conversation turn to session."""
        pass

    @abstractmethod
    def get_recent_turns(self, n: int = 10) -> List[ConversationTurn]:
        """Get N most recent conversation turns."""
        pass

    @abstractmethod
    def set_current_task(self, task: Task) -> None:
        """Set the current active task."""
        pass

    @abstractmethod
    def get_current_task(self) -> Optional[Task]:
        """Get the current active task."""
        pass

    @abstractmethod
    def update_cognitive_load(self, load: CognitiveLoad) -> None:
        """Update cognitive load estimate."""
        pass

    @abstractmethod
    def get_cognitive_load(self) -> CognitiveLoad:
        """Get current cognitive load."""
        pass

    @abstractmethod
    def add_given_hint(self, hint_id: str) -> None:
        """Record that a hint was given."""
        pass

    @abstractmethod
    def get_given_hints(self) -> List[str]:
        """Get all hints given in this session."""
        pass

    @abstractmethod
    def get_context_for_llm(self, max_turns: int = 10) -> str:
        """Format session context for LLM prompt injection."""
        pass

    @abstractmethod
    def end_session(self) -> SessionSummary:
        """End session and return summary for long-term storage."""
        pass

    @abstractmethod
    def record_task_attempt(self, correct: bool, response_time_ms: int) -> None:
        """Record a task attempt."""
        pass


class IStudentMemory(ABC):
    """Interface for persistent student data (long-term, SQLite)."""

    @abstractmethod
    def create_student(self, student_id: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Create new student profile."""
        pass

    @abstractmethod
    def get_student(self, student_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve student by ID."""
        pass

    @abstractmethod
    def update_student(self, student_id: str, **updates) -> None:
        """Update student profile fields."""
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


class MemoryContext:
    """Combined memory context for agents."""

    def __init__(
        self,
        session_id: str,
        student_id: str,
        recent_turns: List[ConversationTurn],
        current_task: Optional[Task],
        session_hints_given: List[str],
        current_cognitive_load: CognitiveLoad,
        knowledge_state: KnowledgeState,
        learning_style: str,
        effective_hint_types: Dict[HintType, float],
        recommended_difficulty: Difficulty,
        topics_to_avoid: List[str],
        topics_to_reinforce: List[str]
    ):
        self.session_id = session_id
        self.student_id = student_id
        self.recent_turns = recent_turns
        self.current_task = current_task
        self.session_hints_given = session_hints_given
        self.current_cognitive_load = current_cognitive_load
        self.knowledge_state = knowledge_state
        self.learning_style = learning_style
        self.effective_hint_types = effective_hint_types
        self.recommended_difficulty = recommended_difficulty
        self.topics_to_avoid = topics_to_avoid
        self.topics_to_reinforce = topics_to_reinforce

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "student_id": self.student_id,
            "turn_count": len(self.recent_turns),
            "current_task_id": self.current_task.id if self.current_task else None,
            "hints_given": len(self.session_hints_given),
            "cognitive_load": self.current_cognitive_load.level.value,
            "overall_mastery": self.knowledge_state.overall_mastery,
            "learning_style": self.learning_style,
            "recommended_difficulty": self.recommended_difficulty.value,
        }
