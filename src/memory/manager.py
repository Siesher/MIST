#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory Manager для MITS.

Координирует работу Session Memory и Student Memory:
- Создание/завершение сессий
- Синхронизация данных между памятями
- Применение decay при старте сессии
- Контекстная инъекция для агентов

T044: Memory Manager Implementation
T045: Orchestrator Integration
T046: Knowledge Decay on Session Start
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.data.schemas import (
    CognitiveLoad,
    CognitiveLoadLevel,
    ConversationTurn,
    Difficulty,
    KnowledgeState,
    SessionSummary,
    Task,
)
from src.memory.interfaces import MemoryContext
from src.memory.session_memory import SessionMemory, TurnType, create_session_memory
from src.memory.student_memory import StudentMemory, create_student_memory

logger = logging.getLogger(__name__)


@dataclass
class MemoryEvent:
    """Base event for memory system."""
    event_type: str
    timestamp: datetime = field(default_factory=datetime.now)
    student_id: str = ""
    session_id: Optional[str] = None


@dataclass
class SessionStartedEvent(MemoryEvent):
    """Event fired when session starts."""
    event_type: str = "session_started"
    knowledge_state_snapshot: Dict[str, float] = field(default_factory=dict)
    decay_applied: bool = False


@dataclass
class SessionEndedEvent(MemoryEvent):
    """Event fired when session ends."""
    event_type: str = "session_ended"
    summary: Optional[SessionSummary] = None


class MemoryManager:
    """
    Unified interface for memory operations.

    Coordinates:
    - SessionMemory (short-term, in-memory)
    - StudentMemory (long-term, SQLite)

    Features:
    - Automatic knowledge decay on session start (T046)
    - Session lifecycle management
    - Context building for agents
    - Preference learning from interactions (T047)
    """

    def __init__(
        self,
        student_memory: Optional[StudentMemory] = None,
        db_path: str = "data/mits.db",
        apply_decay_on_start: bool = True
    ):
        """
        Initialize memory manager.

        Args:
            student_memory: Pre-configured student memory (or creates new)
            db_path: Path to SQLite database
            apply_decay_on_start: Apply knowledge decay when sessions start
        """
        self.student_memory = student_memory or create_student_memory(db_path)
        self.apply_decay_on_start = apply_decay_on_start

        # Active sessions: session_id -> SessionMemory
        self._sessions: Dict[str, SessionMemory] = {}

        # Event handlers
        self._event_handlers: List[callable] = []

        logger.info("MemoryManager initialized")

    def add_event_handler(self, handler: callable):
        """Add handler for memory events."""
        self._event_handlers.append(handler)

    def _emit_event(self, event: MemoryEvent):
        """Emit event to all handlers."""
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.warning(f"Event handler error: {e}")

    # === Session Lifecycle ===

    def start_session(
        self,
        student_id: str,
        create_student_if_missing: bool = True
    ) -> Tuple[str, SessionMemory, KnowledgeState]:
        """
        Start a new session for student.

        Returns:
            (session_id, session_memory, knowledge_state)

        Features:
        - Creates student if missing
        - Applies knowledge decay (T046)
        - Returns current knowledge state
        """
        # Ensure student exists
        student = self.student_memory.get_student(student_id)
        if not student:
            if create_student_if_missing:
                student = self.student_memory.create_student(student_id)
                logger.info(f"Created new student: {student_id}")
            else:
                raise ValueError(f"Student not found: {student_id}")

        # Apply knowledge decay (T046)
        decay_applied = False
        if self.apply_decay_on_start:
            try:
                self.student_memory.apply_knowledge_decay(student_id)
                decay_applied = True
            except Exception as e:
                logger.warning(f"Failed to apply decay: {e}")

        # Get current knowledge state
        knowledge_state = self.student_memory.get_knowledge_state(student_id)

        # Create session
        session_id = str(uuid.uuid4())
        session = create_session_memory(
            session_id=session_id,
            student_id=student_id
        )

        self._sessions[session_id] = session

        # Emit event
        self._emit_event(SessionStartedEvent(
            student_id=student_id,
            session_id=session_id,
            knowledge_state_snapshot={
                topic_id: tm.mastery
                for topic_id, tm in knowledge_state.topics.items()
            },
            decay_applied=decay_applied
        ))

        logger.info(
            f"Session started: {session_id}",
            extra={"student_id": student_id, "decay_applied": decay_applied}
        )

        return session_id, session, knowledge_state

    def end_session(self, session_id: str) -> Optional[SessionSummary]:
        """
        End session and persist summary.

        Returns:
            SessionSummary for the completed session
        """
        session = self._sessions.get(session_id)
        if not session:
            logger.warning(f"Session not found: {session_id}")
            return None

        # Build summary
        summary = self._build_session_summary(session)

        # Store in long-term memory
        if summary:
            self.student_memory.add_session_summary(summary)

        # Cleanup
        del self._sessions[session_id]

        # Emit event
        self._emit_event(SessionEndedEvent(
            student_id=summary.student_id if summary else "",
            session_id=session_id,
            summary=summary
        ))

        logger.info(f"Session ended: {session_id}")

        return summary

    def _build_session_summary(self, session: SessionMemory) -> Optional[SessionSummary]:
        """Build session summary from session memory."""
        if not session:
            return None

        state = session.to_dict()
        context = session.context

        # Calculate metrics
        tasks_attempted = state.get("turn_count", 0) // 2  # Rough estimate
        tasks_solved = state.get("correct_count", 0)
        success_rate = tasks_solved / max(tasks_attempted, 1)
        avg_hints = state.get("hint_count", 0) / max(tasks_attempted, 1)

        # Get topics practiced (from task changes)
        topics_practiced = []
        if context.current_topic:
            topics_practiced.append(context.current_topic)

        # Telling rate (direct answers vs questions)
        # This would need to be tracked in session
        telling_rate = 0.0

        return SessionSummary(
            session_id=context.session_id,
            student_id=context.student_id or "",
            started_at=context.started_at,
            ended_at=datetime.now(),
            duration_seconds=int(session.get_session_duration_minutes() * 60),
            tasks_attempted=tasks_attempted,
            tasks_solved=tasks_solved,
            success_rate=success_rate,
            avg_hints_per_task=avg_hints,
            telling_rate=telling_rate,
            topics_practiced=topics_practiced,
            avg_cognitive_load=CognitiveLoadLevel.OPTIMAL,  # Could calculate from history
            frustration_events=1 if session.consecutive_errors >= 3 else 0
        )

    # === Interaction Recording ===

    def record_interaction(
        self,
        session_id: str,
        student_input: str,
        tutor_response: str,
        task: Optional[Task] = None,
        correct: Optional[bool] = None,
        hints_used: List[str] = None,
        response_time_ms: int = 0,
        tutor_move: str = "scaffolding"
    ) -> None:
        """
        Record a complete interaction to both memories.

        Updates:
        - Session memory with turn data
        - Student memory with knowledge update (if correct is known)
        - Preference learning from interaction patterns
        """
        session = self._sessions.get(session_id)
        if not session:
            logger.warning(f"Session not found for recording: {session_id}")
            return

        # Record student input
        session.add_student_input(
            content=student_input,
            response_time_ms=response_time_ms,
            is_correct=correct
        )

        # Record tutor response
        session.add_tutor_response(
            content=tutor_response,
            move_type=tutor_move
        )

        # Record hints
        if hints_used:
            for hint_id in hints_used:
                session.add_hint_request()

        # Update knowledge state in long-term memory
        student_id = session.context.student_id
        if student_id and correct is not None and task:
            topic = task.topic if hasattr(task, 'topic') else session.context.current_topic
            if topic:
                self.student_memory.update_knowledge_state(
                    student_id=student_id,
                    topic_id=topic,
                    correct=correct,
                    response_time_ms=response_time_ms,
                    hints_used=len(hints_used) if hints_used else 0
                )

        # Learn preferences (T047)
        if student_id:
            self._learn_from_interaction(
                student_id=student_id,
                response_time_ms=response_time_ms,
                hints_used=hints_used or [],
                tutor_move=tutor_move
            )

    def _learn_from_interaction(
        self,
        student_id: str,
        response_time_ms: int,
        hints_used: List[str],
        tutor_move: str
    ):
        """Learn preferences from interaction patterns (T047)."""
        # Learn response time preference (fast vs slow)
        if response_time_ms > 0:
            if response_time_ms < 10000:  # Fast responder
                self.student_memory.learn_preference(
                    student_id, "pace", "fast", weight=0.5
                )
            elif response_time_ms > 60000:  # Slow, thoughtful
                self.student_memory.learn_preference(
                    student_id, "pace", "slow", weight=0.5
                )

        # Learn hint preference
        if len(hints_used) == 0:
            self.student_memory.learn_preference(
                student_id, "hint_preference", "minimal", weight=0.3
            )
        elif len(hints_used) > 2:
            self.student_memory.learn_preference(
                student_id, "hint_preference", "detailed", weight=0.3
            )

    # === Context Building (T045) ===

    def get_full_context(self, session_id: str) -> Optional[MemoryContext]:
        """
        Get combined context from both memories for agent use.

        Returns:
            MemoryContext with session and student data
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        student_id = session.context.student_id
        if not student_id:
            return None

        # Get knowledge state
        knowledge_state = self.student_memory.get_knowledge_state(student_id)

        # Get preferences
        preferences = self.student_memory.get_preferences(student_id)
        learning_style = preferences.get("learning_style", "visual")

        # Get hint effectiveness
        hint_effectiveness = self.student_memory.get_effective_hint_types(student_id)

        # Get recommended topics
        recommended = self.student_memory.get_recommended_topics(student_id, n=3)

        # Determine topics to avoid (recent failures)
        topics_to_avoid = []
        for topic_id, tm in knowledge_state.topics.items():
            if tm.mastery < 0.3 and tm.practice_count > 5:
                topics_to_avoid.append(topic_id)

        # Topics to reinforce (almost mastered)
        topics_to_reinforce = []
        for topic_id, tm in knowledge_state.topics.items():
            if 0.6 <= tm.mastery < 0.8:
                topics_to_reinforce.append(topic_id)

        # Determine recommended difficulty
        if knowledge_state.overall_mastery < 0.4:
            recommended_difficulty = Difficulty.EASY
        elif knowledge_state.overall_mastery > 0.7:
            recommended_difficulty = Difficulty.HARD
        else:
            recommended_difficulty = Difficulty.MEDIUM

        # Build conversation turns from session
        recent_turns = []
        for turn in session.get_history(last_n=10):
            recent_turns.append(ConversationTurn(
                role="student" if turn.turn_type == TurnType.STUDENT_INPUT else "tutor",
                content=turn.content,
                timestamp=turn.timestamp
            ))

        # Build cognitive load
        signals = session.get_cognitive_load_signals()
        cognitive_load = CognitiveLoad(
            level=CognitiveLoadLevel(signals.get("response_time_trend", "stable").upper())
            if signals.get("response_time_trend") in ["increasing", "decreasing", "stable"]
            else CognitiveLoadLevel.OPTIMAL,
            score=0.5,  # Default
            contributing_factors=signals
        )

        # Get current task
        current_task = None
        if session.context.current_task_id:
            current_task = Task(
                id=session.context.current_task_id,
                topic=session.context.current_topic or "",
                difficulty=Difficulty(session.context.current_difficulty)
            )

        return MemoryContext(
            session_id=session_id,
            student_id=student_id,
            recent_turns=recent_turns,
            current_task=current_task,
            session_hints_given=list(range(session.hint_count)),  # Placeholder
            current_cognitive_load=cognitive_load,
            knowledge_state=knowledge_state,
            learning_style=learning_style,
            effective_hint_types=hint_effectiveness,
            recommended_difficulty=recommended_difficulty,
            topics_to_avoid=topics_to_avoid,
            topics_to_reinforce=topics_to_reinforce
        )

    def get_session(self, session_id: str) -> Optional[SessionMemory]:
        """Get session memory by ID."""
        return self._sessions.get(session_id)

    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        return list(self._sessions.keys())

    def get_student_context(self, student_id: str) -> Dict[str, Any]:
        """
        Get student context without an active session.

        Useful for task generation and planning.
        """
        student = self.student_memory.get_student(student_id)
        if not student:
            return {}

        knowledge_state = self.student_memory.get_knowledge_state(student_id)
        preferences = self.student_memory.get_preferences(student_id)
        recommended = self.student_memory.get_recommended_topics(student_id)
        history = self.student_memory.get_session_history(student_id, limit=5)

        return {
            "student": student,
            "knowledge_state": knowledge_state,
            "preferences": preferences,
            "recommended_topics": recommended,
            "recent_sessions": len(history),
            "total_learning_hours": student.get("total_learning_hours", 0),
            "streak_days": student.get("streak_days", 0)
        }


def create_memory_manager(
    db_path: str = "data/mits.db",
    apply_decay: bool = True
) -> MemoryManager:
    """Factory function for creating MemoryManager."""
    return MemoryManager(db_path=db_path, apply_decay_on_start=apply_decay)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== Memory Manager Demo ===\n")

    manager = create_memory_manager("data/test_memory.db")

    # Start session
    session_id, session, knowledge = manager.start_session("demo-student")
    print(f"Session started: {session_id}")
    print(f"Knowledge state: {knowledge.overall_mastery:.2f}")

    # Record interactions
    manager.record_interaction(
        session_id=session_id,
        student_input="x^2 - 5x + 6 = 0, так x = 2 или x = 3",
        tutor_response="Отлично! Как ты проверил эти корни?",
        correct=True,
        response_time_ms=45000,
        tutor_move="encourage"
    )

    # Get context
    context = manager.get_full_context(session_id)
    print(f"\nContext: {context.to_dict()}")

    # End session
    summary = manager.end_session(session_id)
    print(f"\nSession summary: {summary}")

    print("\nDone!")
