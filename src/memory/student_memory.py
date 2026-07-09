#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Student Memory для MITS.

Реализует долгосрочную память студента с SQLite персистентностью:
- Профиль студента
- Состояние знаний (Knowledge State)
- История сессий
- Предпочтения и стиль обучения

Основано на:
- IStudentMemory interface (contracts/memory-interfaces.md)
- Ebbinghaus Forgetting Curve для decay
- Preference Learning для персонализации

T043, T046, T047: Student Memory Implementation
"""

import json
import logging
import math
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.data.schemas import (
    CognitiveLoadLevel,
    HintType,
    KnowledgeState,
    SessionSummary,
    TopicMastery,
)
from src.memory.interfaces import IStudentMemory

logger = logging.getLogger(__name__)


# === Database Schema ===

SCHEMA_SQL = """
-- Students table
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_session TIMESTAMP,
    total_learning_hours REAL DEFAULT 0.0,
    lifetime_tasks_attempted INTEGER DEFAULT 0,
    lifetime_tasks_solved INTEGER DEFAULT 0,
    streak_days INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    learning_style TEXT DEFAULT 'visual',
    preferences_json TEXT DEFAULT '{}'
);

-- Topic mastery table
CREATE TABLE IF NOT EXISTS topic_mastery (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    mastery REAL DEFAULT 0.3,
    dkt_mastery REAL,
    attempts INTEGER DEFAULT 0,
    correct_attempts INTEGER DEFAULT 0,
    last_practice TIMESTAMP,
    last_decay_applied TIMESTAMP,
    hints_used_total INTEGER DEFAULT 0,
    avg_response_time_ms REAL,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    UNIQUE(student_id, topic_id)
);

-- Session history table
CREATE TABLE IF NOT EXISTS session_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    session_id TEXT UNIQUE NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    duration_seconds INTEGER,
    tasks_attempted INTEGER DEFAULT 0,
    tasks_solved INTEGER DEFAULT 0,
    success_rate REAL,
    avg_hints_per_task REAL,
    telling_rate REAL,
    topics_practiced_json TEXT,
    avg_cognitive_load TEXT,
    frustration_events INTEGER DEFAULT 0,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

-- Hint effectiveness tracking
CREATE TABLE IF NOT EXISTS hint_effectiveness (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    hint_type TEXT NOT NULL,
    times_given INTEGER DEFAULT 0,
    times_effective INTEGER DEFAULT 0,
    effectiveness_score REAL DEFAULT 0.5,
    last_updated TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    UNIQUE(student_id, hint_type)
);

-- Preference learning table
CREATE TABLE IF NOT EXISTS preference_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    preference_key TEXT NOT NULL,
    preference_value TEXT,
    confidence REAL DEFAULT 0.5,
    observation_count INTEGER DEFAULT 1,
    last_updated TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    UNIQUE(student_id, preference_key)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_topic_mastery_student ON topic_mastery(student_id);
CREATE INDEX IF NOT EXISTS idx_session_history_student ON session_history(student_id);
CREATE INDEX IF NOT EXISTS idx_session_history_date ON session_history(started_at);
"""


# === Knowledge Decay Constants (T046) ===

# Ebbinghaus forgetting curve parameters
DECAY_BASE_STRENGTH = 24.0  # Hours for 50% retention
DECAY_MASTERY_MULTIPLIER = 1.5  # High mastery = slower decay
DECAY_PRACTICE_MULTIPLIER = 0.2  # Each practice adds stability
DECAY_MINIMUM_MASTERY = 0.1  # Never decay below this


@dataclass
class StudentData:
    """Student profile data."""
    student_id: str
    name: Optional[str] = None
    created_at: Optional[datetime] = None
    last_session: Optional[datetime] = None
    total_learning_hours: float = 0.0
    lifetime_tasks_attempted: int = 0
    lifetime_tasks_solved: int = 0
    streak_days: int = 0
    longest_streak: int = 0
    learning_style: str = "visual"
    preferences: Dict[str, Any] = field(default_factory=dict)


class StudentMemory(IStudentMemory):
    """
    SQLite-backed student memory implementation.

    Provides persistent storage for:
    - Student profiles
    - Knowledge state (mastery per topic)
    - Session history
    - Learned preferences

    Features:
    - Ebbinghaus forgetting curve for knowledge decay (T046)
    - Preference learning from interactions (T047)
    - ZPD-based topic recommendations
    """

    def __init__(self, db_path: str = "data/mits.db"):
        """
        Initialize student memory.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()
        logger.info(f"StudentMemory initialized: {self.db_path}")

    def _init_database(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection with context management."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # === Student CRUD ===

    def create_student(self, student_id: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Create new student profile."""
        with self._get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO students (student_id, name, created_at, preferences_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (student_id, name, datetime.now(), "{}")
                )
                conn.commit()
                logger.info(f"Created student: {student_id}")
            except sqlite3.IntegrityError:
                logger.warning(f"Student already exists: {student_id}")

        return self.get_student(student_id)

    def get_student(self, student_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve student by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM students WHERE student_id = ?",
                (student_id,)
            ).fetchone()

            if not row:
                return None

            return {
                "student_id": row["student_id"],
                "name": row["name"],
                "created_at": row["created_at"],
                "last_session": row["last_session"],
                "total_learning_hours": row["total_learning_hours"],
                "lifetime_tasks_attempted": row["lifetime_tasks_attempted"],
                "lifetime_tasks_solved": row["lifetime_tasks_solved"],
                "streak_days": row["streak_days"],
                "longest_streak": row["longest_streak"],
                "learning_style": row["learning_style"],
                "preferences": json.loads(row["preferences_json"] or "{}")
            }

    def update_student(self, student_id: str, **updates) -> None:
        """Update student profile fields."""
        if not updates:
            return

        # Handle preferences separately
        if "preferences" in updates:
            updates["preferences_json"] = json.dumps(updates.pop("preferences"))

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [student_id]

        with self._get_connection() as conn:
            conn.execute(
                f"UPDATE students SET {set_clause} WHERE student_id = ?",
                values
            )
            conn.commit()

    def delete_student(self, student_id: str) -> bool:
        """Delete student and all associated data."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM students WHERE student_id = ?",
                (student_id,)
            )
            conn.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Deleted student: {student_id}")

        return deleted

    # === Knowledge State ===

    def get_knowledge_state(self, student_id: str) -> KnowledgeState:
        """Get student's current knowledge state."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM topic_mastery WHERE student_id = ?",
                (student_id,)
            ).fetchall()

        topic_masteries = {}
        for row in rows:
            # Имена kwargs должны совпадать с полями TopicMastery (pydantic v2
            # молча игнорирует лишние — данные терялись без ошибки)
            topic_masteries[row["topic_id"]] = TopicMastery(
                topic_id=row["topic_id"],
                mastery=row["mastery"],
                practice_count=row["attempts"],
                correct_count=row["correct_attempts"],
                last_practiced=datetime.fromisoformat(row["last_practice"]) if row["last_practice"] else None,
            )

        # Calculate overall mastery
        if topic_masteries:
            overall = sum(tm.mastery for tm in topic_masteries.values()) / len(topic_masteries)
        else:
            overall = 0.3  # Default for new students

        return KnowledgeState(
            student_id=student_id,
            topics=topic_masteries,
            overall_mastery=overall,
        )

    def update_knowledge_state(
        self,
        student_id: str,
        topic_id: str,
        correct: bool,
        response_time_ms: int,
        hints_used: int
    ) -> TopicMastery:
        """
        Update knowledge state after interaction.

        Uses BKT-style update with performance factors.
        """
        with self._get_connection() as conn:
            # Get current state
            row = conn.execute(
                "SELECT * FROM topic_mastery WHERE student_id = ? AND topic_id = ?",
                (student_id, topic_id)
            ).fetchone()

            if row:
                current_mastery = row["mastery"]
                attempts = row["attempts"]
                correct_attempts = row["correct_attempts"]
                hints_total = row["hints_used_total"]
                avg_rt = row["avg_response_time_ms"] or response_time_ms
            else:
                current_mastery = 0.3
                attempts = 0
                correct_attempts = 0
                hints_total = 0
                avg_rt = response_time_ms

            # Update counts
            attempts += 1
            if correct:
                correct_attempts += 1
            hints_total += hints_used

            # Calculate new mastery (simplified BKT)
            p_learn = 0.1  # Learning rate
            p_guess = 0.25
            p_slip = 0.1

            if correct:
                # P(L|correct) = P(L) * (1-slip) / P(correct)
                p_correct = current_mastery * (1 - p_slip) + (1 - current_mastery) * p_guess
                new_mastery = (current_mastery * (1 - p_slip)) / p_correct if p_correct > 0 else current_mastery
            else:
                # P(L|incorrect) = P(L) * slip / P(incorrect)
                p_incorrect = current_mastery * p_slip + (1 - current_mastery) * (1 - p_guess)
                new_mastery = (current_mastery * p_slip) / p_incorrect if p_incorrect > 0 else current_mastery

            # Apply learning
            new_mastery = new_mastery + (1 - new_mastery) * p_learn

            # Penalty for hints (but not too harsh)
            if hints_used > 0:
                hint_penalty = 0.02 * hints_used
                new_mastery = max(new_mastery - hint_penalty, current_mastery * 0.8)

            # Clamp to valid range
            new_mastery = max(0.1, min(0.95, new_mastery))

            # Update average response time
            avg_rt = (avg_rt * (attempts - 1) + response_time_ms) / attempts

            # Upsert
            conn.execute(
                """
                INSERT INTO topic_mastery
                (student_id, topic_id, mastery, attempts, correct_attempts, last_practice, hints_used_total, avg_response_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(student_id, topic_id) DO UPDATE SET
                    mastery = excluded.mastery,
                    attempts = excluded.attempts,
                    correct_attempts = excluded.correct_attempts,
                    last_practice = excluded.last_practice,
                    hints_used_total = excluded.hints_used_total,
                    avg_response_time_ms = excluded.avg_response_time_ms
                """,
                (student_id, topic_id, new_mastery, attempts, correct_attempts,
                 datetime.now(), hints_total, avg_rt)
            )
            conn.commit()

        return TopicMastery(
            topic_id=topic_id,
            mastery=new_mastery,
            attempts=attempts,
            correct=correct_attempts,
            last_practice=datetime.now(),
            hints_used=hints_total
        )

    def apply_knowledge_decay(self, student_id: str) -> None:
        """
        Apply Ebbinghaus forgetting curve to all topics (T046).

        R = e^(-t/S) where:
        - R is retention
        - t is time since last practice
        - S is memory strength (based on mastery and practice count)
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT topic_id, mastery, attempts, last_practice, last_decay_applied
                FROM topic_mastery
                WHERE student_id = ?
                """,
                (student_id,)
            ).fetchall()

            now = datetime.now()
            updates = []

            for row in rows:
                last_practice = datetime.fromisoformat(row["last_practice"]) if row["last_practice"] else now
                last_decay = datetime.fromisoformat(row["last_decay_applied"]) if row["last_decay_applied"] else last_practice

                # Calculate hours since last decay application
                hours_since = (now - last_decay).total_seconds() / 3600

                if hours_since < 1:  # Skip if less than 1 hour
                    continue

                # Calculate memory strength
                mastery = row["mastery"]
                practice_count = row["attempts"]

                # Higher mastery = slower decay
                mastery_multiplier = 1.0 + (mastery * DECAY_MASTERY_MULTIPLIER)

                # More practice = slower decay
                practice_multiplier = 1.0 + (practice_count * DECAY_PRACTICE_MULTIPLIER)

                memory_strength = DECAY_BASE_STRENGTH * mastery_multiplier * practice_multiplier

                # Calculate decay factor: R = e^(-t/S)
                decay_factor = math.exp(-hours_since / memory_strength)

                # Apply decay
                new_mastery = mastery * decay_factor
                new_mastery = max(new_mastery, DECAY_MINIMUM_MASTERY)

                # Only update if significant change
                if abs(new_mastery - mastery) > 0.001:
                    updates.append((new_mastery, now, student_id, row["topic_id"]))
                    logger.debug(
                        f"Decay applied: {row['topic_id']} {mastery:.3f} -> {new_mastery:.3f} "
                        f"(hours={hours_since:.1f}, strength={memory_strength:.1f})"
                    )

            # Batch update
            if updates:
                conn.executemany(
                    """
                    UPDATE topic_mastery
                    SET mastery = ?, last_decay_applied = ?
                    WHERE student_id = ? AND topic_id = ?
                    """,
                    updates
                )
                conn.commit()
                logger.info(f"Applied decay to {len(updates)} topics for student {student_id}")

    def get_recommended_topics(self, student_id: str, n: int = 5) -> List[str]:
        """
        Get topics recommended for practice.

        Prioritizes topics in the Zone of Proximal Development (ZPD):
        - Mastery between 0.3 and 0.7 (learnable but challenging)
        - Longest time since practice
        - Prerequisites are mastered
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT topic_id, mastery, last_practice
                FROM topic_mastery
                WHERE student_id = ?
                AND mastery BETWEEN 0.2 AND 0.8
                ORDER BY
                    -- ZPD priority: closer to 0.5 is better
                    ABS(mastery - 0.5) ASC,
                    -- Older practice = higher priority
                    last_practice ASC
                LIMIT ?
                """,
                (student_id, n)
            ).fetchall()

        return [row["topic_id"] for row in rows]

    # === Session History ===

    def add_session_summary(self, summary: SessionSummary) -> None:
        """Store completed session summary."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO session_history
                (student_id, session_id, started_at, ended_at, duration_seconds,
                 tasks_attempted, tasks_solved, success_rate, avg_hints_per_task,
                 telling_rate, topics_practiced_json, avg_cognitive_load, frustration_events)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.student_id,
                    summary.session_id,
                    summary.started_at,
                    summary.ended_at,
                    summary.duration_seconds,
                    summary.tasks_attempted,
                    summary.tasks_solved,
                    summary.success_rate,
                    summary.avg_hints_per_task,
                    summary.telling_rate,
                    json.dumps(summary.topics_practiced),
                    summary.avg_cognitive_load.value if summary.avg_cognitive_load else "optimal",
                    summary.frustration_events
                )
            )

            # Update student stats
            conn.execute(
                """
                UPDATE students SET
                    last_session = ?,
                    total_learning_hours = total_learning_hours + ?,
                    lifetime_tasks_attempted = lifetime_tasks_attempted + ?,
                    lifetime_tasks_solved = lifetime_tasks_solved + ?
                WHERE student_id = ?
                """,
                (
                    summary.ended_at,
                    summary.duration_seconds / 3600,
                    summary.tasks_attempted,
                    summary.tasks_solved,
                    summary.student_id
                )
            )

            # Update streak
            self._update_streak(conn, summary.student_id)

            conn.commit()

        logger.info(f"Session summary saved: {summary.session_id}")

    def _update_streak(self, conn, student_id: str):
        """Update learning streak for student."""
        # Get last two sessions
        rows = conn.execute(
            """
            SELECT started_at FROM session_history
            WHERE student_id = ?
            ORDER BY started_at DESC
            LIMIT 2
            """,
            (student_id,)
        ).fetchall()

        if len(rows) < 2:
            conn.execute(
                "UPDATE students SET streak_days = 1 WHERE student_id = ?",
                (student_id,)
            )
            return

        current = datetime.fromisoformat(rows[0]["started_at"]) if isinstance(rows[0]["started_at"], str) else rows[0]["started_at"]
        previous = datetime.fromisoformat(rows[1]["started_at"]) if isinstance(rows[1]["started_at"], str) else rows[1]["started_at"]

        days_diff = (current.date() - previous.date()).days

        if days_diff <= 1:
            # Continue streak
            conn.execute(
                """
                UPDATE students SET
                    streak_days = streak_days + 1,
                    longest_streak = MAX(longest_streak, streak_days + 1)
                WHERE student_id = ?
                """,
                (student_id,)
            )
        else:
            # Reset streak
            conn.execute(
                "UPDATE students SET streak_days = 1 WHERE student_id = ?",
                (student_id,)
            )

    def get_session_history(
        self,
        student_id: str,
        limit: int = 10,
        since: Optional[datetime] = None
    ) -> List[SessionSummary]:
        """Get recent session summaries."""
        with self._get_connection() as conn:
            if since:
                rows = conn.execute(
                    """
                    SELECT * FROM session_history
                    WHERE student_id = ? AND started_at >= ?
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    (student_id, since, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM session_history
                    WHERE student_id = ?
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    (student_id, limit)
                ).fetchall()

        summaries = []
        for row in rows:
            summaries.append(SessionSummary(
                session_id=row["session_id"],
                student_id=row["student_id"],
                started_at=datetime.fromisoformat(row["started_at"]) if isinstance(row["started_at"], str) else row["started_at"],
                ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] and isinstance(row["ended_at"], str) else row["ended_at"],
                duration_seconds=row["duration_seconds"],
                tasks_attempted=row["tasks_attempted"],
                tasks_solved=row["tasks_solved"],
                success_rate=row["success_rate"],
                avg_hints_per_task=row["avg_hints_per_task"],
                telling_rate=row["telling_rate"],
                topics_practiced=json.loads(row["topics_practiced_json"] or "[]"),
                avg_cognitive_load=CognitiveLoadLevel(row["avg_cognitive_load"]) if row["avg_cognitive_load"] else CognitiveLoadLevel.OPTIMAL,
                frustration_events=row["frustration_events"]
            ))

        return summaries

    # === Preferences (T047) ===

    def get_preferences(self, student_id: str) -> Dict[str, Any]:
        """Get student preferences."""
        student = self.get_student(student_id)
        if not student:
            return {}

        # Combine stored preferences with learned preferences
        preferences = student.get("preferences", {})

        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT preference_key, preference_value, confidence
                FROM preference_history
                WHERE student_id = ? AND confidence > 0.5
                """,
                (student_id,)
            ).fetchall()

        for row in rows:
            key = row["preference_key"]
            if key not in preferences:  # Don't override explicit preferences
                try:
                    preferences[key] = json.loads(row["preference_value"])
                except json.JSONDecodeError:
                    preferences[key] = row["preference_value"]

        return preferences

    def update_preference(self, student_id: str, key: str, value: Any) -> None:
        """Update a single preference."""
        with self._get_connection() as conn:
            # Update in preferences JSON
            row = conn.execute(
                "SELECT preferences_json FROM students WHERE student_id = ?",
                (student_id,)
            ).fetchone()

            if row:
                prefs = json.loads(row["preferences_json"] or "{}")
                prefs[key] = value
                conn.execute(
                    "UPDATE students SET preferences_json = ? WHERE student_id = ?",
                    (json.dumps(prefs), student_id)
                )
                conn.commit()

    def learn_preference(
        self,
        student_id: str,
        key: str,
        observed_value: Any,
        weight: float = 1.0
    ) -> None:
        """
        Learn a preference from interaction observation (T047).

        Uses exponential moving average for confidence.
        """
        value_json = json.dumps(observed_value)

        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT preference_value, confidence, observation_count
                FROM preference_history
                WHERE student_id = ? AND preference_key = ?
                """,
                (student_id, key)
            ).fetchone()

            if row:
                # Update existing
                old_value = row["preference_value"]
                old_confidence = row["confidence"]
                count = row["observation_count"]

                if old_value == value_json:
                    # Same value observed, increase confidence
                    new_confidence = min(0.95, old_confidence + (1 - old_confidence) * 0.1 * weight)
                else:
                    # Different value, decrease confidence
                    new_confidence = max(0.1, old_confidence - 0.1 * weight)
                    if new_confidence < 0.5:
                        # Switch to new value
                        value_json = value_json
                    else:
                        value_json = old_value

                conn.execute(
                    """
                    UPDATE preference_history SET
                        preference_value = ?,
                        confidence = ?,
                        observation_count = ?,
                        last_updated = ?
                    WHERE student_id = ? AND preference_key = ?
                    """,
                    (value_json, new_confidence, count + 1, datetime.now(), student_id, key)
                )
            else:
                # Insert new
                conn.execute(
                    """
                    INSERT INTO preference_history
                    (student_id, preference_key, preference_value, confidence, observation_count, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (student_id, key, value_json, 0.5, 1, datetime.now())
                )

            conn.commit()

    def get_effective_hint_types(self, student_id: str) -> Dict[HintType, float]:
        """Get effectiveness scores for hint types."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT hint_type, effectiveness_score
                FROM hint_effectiveness
                WHERE student_id = ?
                """,
                (student_id,)
            ).fetchall()

        result = {ht: 0.5 for ht in HintType}  # Default scores

        for row in rows:
            try:
                hint_type = HintType(row["hint_type"])
                result[hint_type] = row["effectiveness_score"]
            except (ValueError, KeyError):
                pass

        return result

    def update_hint_effectiveness(
        self,
        student_id: str,
        hint_type: HintType,
        was_effective: bool
    ) -> None:
        """Update hint effectiveness tracking."""
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT times_given, times_effective, effectiveness_score
                FROM hint_effectiveness
                WHERE student_id = ? AND hint_type = ?
                """,
                (student_id, hint_type.value)
            ).fetchone()

            if row:
                times_given = row["times_given"] + 1
                times_effective = row["times_effective"] + (1 if was_effective else 0)
                # Moving average
                old_score = row["effectiveness_score"]
                new_score = old_score * 0.8 + (1.0 if was_effective else 0.0) * 0.2

                conn.execute(
                    """
                    UPDATE hint_effectiveness SET
                        times_given = ?,
                        times_effective = ?,
                        effectiveness_score = ?,
                        last_updated = ?
                    WHERE student_id = ? AND hint_type = ?
                    """,
                    (times_given, times_effective, new_score, datetime.now(),
                     student_id, hint_type.value)
                )
            else:
                conn.execute(
                    """
                    INSERT INTO hint_effectiveness
                    (student_id, hint_type, times_given, times_effective, effectiveness_score, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (student_id, hint_type.value, 1, 1 if was_effective else 0,
                     0.5, datetime.now())
                )

            conn.commit()


def create_student_memory(db_path: str = "data/mits.db") -> StudentMemory:
    """Factory function for creating StudentMemory."""
    return StudentMemory(db_path=db_path)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== Student Memory Demo ===\n")

    memory = create_student_memory("data/test_student.db")

    # Create student
    student = memory.create_student("test-student-1", "Иван")
    print(f"Created student: {student}")

    # Update knowledge
    mastery = memory.update_knowledge_state(
        "test-student-1",
        "quadratic_equations",
        correct=True,
        response_time_ms=30000,
        hints_used=1
    )
    print(f"Updated mastery: {mastery}")

    # Get knowledge state
    state = memory.get_knowledge_state("test-student-1")
    print(f"Knowledge state: {state}")

    # Apply decay (simulated)
    memory.apply_knowledge_decay("test-student-1")

    # Get recommendations
    topics = memory.get_recommended_topics("test-student-1")
    print(f"Recommended topics: {topics}")

    # Learn preference
    memory.learn_preference("test-student-1", "preferred_hint_style", "visual")
    prefs = memory.get_preferences("test-student-1")
    print(f"Preferences: {prefs}")

    print("\nDone!")
