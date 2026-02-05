#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Session Memory для MITS.

Реализует краткосрочную память сессии с отслеживанием:
- Истории диалога
- Времени ответов
- Когнитивной нагрузки
- Подсказок и ошибок

На основе исследований:
- Working Memory Theory (Baddeley)
- Dual-Memory ITS Architecture (2025)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Deque
from collections import deque
from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)


class TurnType(Enum):
    """Типы ходов в диалоге."""
    STUDENT_INPUT = "student_input"
    TUTOR_RESPONSE = "tutor_response"
    HINT_REQUEST = "hint_request"
    TASK_CHANGE = "task_change"
    SYSTEM_MESSAGE = "system_message"


@dataclass
class ResponseTimeSample:
    """Образец времени ответа."""
    timestamp: datetime
    response_time_ms: int
    turn_number: int
    task_difficulty: str = "medium"


@dataclass
class Turn:
    """Один ход диалога."""
    turn_number: int
    turn_type: TurnType
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    response_time_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_number": self.turn_number,
            "turn_type": self.turn_type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "response_time_ms": self.response_time_ms,
            "metadata": self.metadata
        }


@dataclass
class SessionContext:
    """Контекст текущей сессии."""
    session_id: str
    student_id: Optional[str] = None
    current_task_id: Optional[str] = None
    current_topic: Optional[str] = None
    current_skill: Optional[str] = None
    current_difficulty: str = "medium"
    started_at: datetime = field(default_factory=datetime.now)


class SessionMemory:
    """
    Краткосрочная память сессии обучения.

    Отслеживает:
    - Историю диалога (последние N ходов)
    - Время ответов для оценки когнитивной нагрузки
    - Количество подсказок и ошибок
    - Контекст текущей задачи

    Параметры:
    - max_turns: максимальное количество ходов в памяти (по умолчанию 20)
    - response_time_window: окно для анализа времени ответов (по умолчанию 10)
    """

    def __init__(
        self,
        session_id: str,
        student_id: Optional[str] = None,
        max_turns: int = 20,
        response_time_window: int = 10
    ):
        """
        Инициализация памяти сессии.

        Args:
            session_id: ID сессии
            student_id: ID студента
            max_turns: Максимальное количество ходов в памяти
            response_time_window: Окно для анализа времени ответов
        """
        self.context = SessionContext(
            session_id=session_id,
            student_id=student_id
        )
        self.max_turns = max_turns
        self.response_time_window = response_time_window

        # История диалога (FIFO очередь)
        self._turns: Deque[Turn] = deque(maxlen=max_turns)
        self._turn_counter = 0

        # Отслеживание времени ответов
        self._response_times: Deque[ResponseTimeSample] = deque(maxlen=response_time_window)
        self._last_message_time: Optional[datetime] = None

        # Счётчики
        self._hint_count = 0
        self._error_count = 0
        self._consecutive_errors = 0
        self._correct_count = 0

        # Tracking for cognitive load
        self._task_start_time: Optional[datetime] = None

        logger.info(f"SessionMemory created: session={session_id}, student={student_id}")

    def start_task(
        self,
        task_id: str,
        topic: Optional[str] = None,
        skill: Optional[str] = None,
        difficulty: str = "medium"
    ):
        """Начать новую задачу."""
        self.context.current_task_id = task_id
        self.context.current_topic = topic
        self.context.current_skill = skill
        self.context.current_difficulty = difficulty
        self._task_start_time = datetime.now()

        # Reset per-task counters
        self._consecutive_errors = 0

        self.add_turn(
            TurnType.TASK_CHANGE,
            f"Task started: {task_id}",
            metadata={"task_id": task_id, "topic": topic, "difficulty": difficulty}
        )

    def add_student_input(
        self,
        content: str,
        response_time_ms: Optional[int] = None,
        is_correct: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Turn:
        """
        Добавить ввод студента.

        Args:
            content: Текст ввода
            response_time_ms: Время ответа (вычисляется автоматически если None)
            is_correct: Правильность ответа
            metadata: Дополнительные метаданные

        Returns:
            Созданный Turn
        """
        now = datetime.now()

        # Calculate response time if not provided
        if response_time_ms is None and self._last_message_time:
            delta = now - self._last_message_time
            response_time_ms = int(delta.total_seconds() * 1000)
        elif response_time_ms is None:
            response_time_ms = 0

        # Track response time
        self._response_times.append(ResponseTimeSample(
            timestamp=now,
            response_time_ms=response_time_ms,
            turn_number=self._turn_counter + 1,
            task_difficulty=self.context.current_difficulty
        ))

        # Update correctness counters
        if is_correct is True:
            self._correct_count += 1
            self._consecutive_errors = 0
        elif is_correct is False:
            self._error_count += 1
            self._consecutive_errors += 1

        # Build metadata
        turn_metadata = metadata or {}
        turn_metadata["is_correct"] = is_correct

        turn = self.add_turn(
            TurnType.STUDENT_INPUT,
            content,
            response_time_ms=response_time_ms,
            metadata=turn_metadata
        )

        self._last_message_time = now
        return turn

    def add_tutor_response(
        self,
        content: str,
        move_type: str = "scaffolding",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Turn:
        """
        Добавить ответ репетитора.

        Args:
            content: Текст ответа
            move_type: Тип педагогического хода
            metadata: Дополнительные метаданные

        Returns:
            Созданный Turn
        """
        turn_metadata = metadata or {}
        turn_metadata["move_type"] = move_type

        turn = self.add_turn(
            TurnType.TUTOR_RESPONSE,
            content,
            metadata=turn_metadata
        )

        self._last_message_time = datetime.now()
        return turn

    def add_hint_request(self, hint_level: int = 1) -> Turn:
        """Зарегистрировать запрос подсказки."""
        self._hint_count += 1

        return self.add_turn(
            TurnType.HINT_REQUEST,
            f"Hint requested (level {hint_level})",
            metadata={"hint_level": hint_level, "total_hints": self._hint_count}
        )

    def add_turn(
        self,
        turn_type: TurnType,
        content: str,
        response_time_ms: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Turn:
        """Добавить ход в историю."""
        self._turn_counter += 1

        turn = Turn(
            turn_number=self._turn_counter,
            turn_type=turn_type,
            content=content,
            response_time_ms=response_time_ms,
            metadata=metadata or {}
        )

        self._turns.append(turn)
        return turn

    def get_history(
        self,
        last_n: Optional[int] = None,
        include_system: bool = False
    ) -> List[Turn]:
        """
        Получить историю диалога.

        Args:
            last_n: Количество последних ходов (None = все)
            include_system: Включать системные сообщения

        Returns:
            Список ходов
        """
        turns = list(self._turns)

        if not include_system:
            turns = [t for t in turns if t.turn_type != TurnType.SYSTEM_MESSAGE]

        if last_n:
            turns = turns[-last_n:]

        return turns

    def get_conversation_history(self, last_n: int = 6) -> List[Dict[str, str]]:
        """
        Получить историю в формате для LLM.

        Args:
            last_n: Количество последних ходов

        Returns:
            Список словарей {"role": ..., "content": ...}
        """
        history = []

        for turn in self.get_history(last_n):
            if turn.turn_type == TurnType.STUDENT_INPUT:
                history.append({"role": "student", "content": turn.content})
            elif turn.turn_type == TurnType.TUTOR_RESPONSE:
                history.append({"role": "tutor", "content": turn.content})

        return history

    # === Response Time Analysis ===

    def get_average_response_time(self) -> float:
        """Получить среднее время ответа (в мс)."""
        if not self._response_times:
            return 0.0

        times = [s.response_time_ms for s in self._response_times]
        return sum(times) / len(times)

    def get_response_time_trend(self) -> str:
        """
        Определить тренд времени ответов.

        Returns:
            "increasing" (замедление), "decreasing" (ускорение), "stable"
        """
        if len(self._response_times) < 3:
            return "stable"

        times = [s.response_time_ms for s in self._response_times]

        # Compare first half with second half
        mid = len(times) // 2
        first_half_avg = sum(times[:mid]) / mid if mid > 0 else 0
        second_half_avg = sum(times[mid:]) / (len(times) - mid)

        ratio = second_half_avg / first_half_avg if first_half_avg > 0 else 1.0

        if ratio > 1.3:
            return "increasing"  # Getting slower
        elif ratio < 0.7:
            return "decreasing"  # Getting faster
        else:
            return "stable"

    def get_last_response_time(self) -> int:
        """Получить время последнего ответа."""
        if self._response_times:
            return self._response_times[-1].response_time_ms
        return 0

    # === Cognitive Load Signals ===

    def get_cognitive_load_signals(self) -> Dict[str, Any]:
        """
        Получить сигналы для оценки когнитивной нагрузки.

        Returns:
            Словарь с сигналами для CognitiveLoadEstimator
        """
        return {
            "response_time_ms": self.get_last_response_time(),
            "average_response_time_ms": self.get_average_response_time(),
            "response_time_trend": self.get_response_time_trend(),
            "consecutive_errors": self._consecutive_errors,
            "hint_requests": self._hint_count,
            "task_difficulty": self.context.current_difficulty,
            "turns_in_session": self._turn_counter,
            "session_duration_minutes": self.get_session_duration_minutes()
        }

    def get_session_duration_minutes(self) -> float:
        """Получить длительность сессии в минутах."""
        delta = datetime.now() - self.context.started_at
        return delta.total_seconds() / 60

    # === Counters ===

    @property
    def hint_count(self) -> int:
        """Количество запрошенных подсказок."""
        return self._hint_count

    @property
    def error_count(self) -> int:
        """Общее количество ошибок."""
        return self._error_count

    @property
    def consecutive_errors(self) -> int:
        """Количество последовательных ошибок."""
        return self._consecutive_errors

    @property
    def correct_count(self) -> int:
        """Количество правильных ответов."""
        return self._correct_count

    @property
    def turn_count(self) -> int:
        """Общее количество ходов."""
        return self._turn_counter

    def should_suggest_break(self) -> bool:
        """
        Проверить, нужно ли предложить перерыв.

        Критерии:
        - Сессия длится более 30 минут
        - Время ответов увеличивается
        - Много последовательных ошибок
        """
        duration = self.get_session_duration_minutes()
        trend = self.get_response_time_trend()

        if duration > 30 and trend == "increasing":
            return True
        if self._consecutive_errors >= 4:
            return True
        if duration > 45:
            return True

        return False

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация состояния."""
        return {
            "session_id": self.context.session_id,
            "student_id": self.context.student_id,
            "current_task_id": self.context.current_task_id,
            "current_topic": self.context.current_topic,
            "turn_count": self._turn_counter,
            "hint_count": self._hint_count,
            "error_count": self._error_count,
            "correct_count": self._correct_count,
            "consecutive_errors": self._consecutive_errors,
            "average_response_time_ms": self.get_average_response_time(),
            "session_duration_minutes": self.get_session_duration_minutes(),
            "should_suggest_break": self.should_suggest_break(),
            "history": [t.to_dict() for t in self._turns]
        }


# Factory function
def create_session_memory(
    session_id: str,
    student_id: Optional[str] = None,
    max_turns: int = 20
) -> SessionMemory:
    """Create a new session memory instance."""
    return SessionMemory(
        session_id=session_id,
        student_id=student_id,
        max_turns=max_turns
    )


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== Session Memory Demo ===\n")

    # Create session
    session = create_session_memory("test-session", "student-1")

    # Start a task
    session.start_task(
        task_id="task-001",
        topic="quadratic_equations",
        skill="factoring",
        difficulty="medium"
    )

    # Simulate interaction
    import time

    time.sleep(0.5)  # Simulate thinking time
    session.add_student_input("Я не знаю как начать", is_correct=False)
    session.add_tutor_response("Давай разберём по шагам.", move_type="scaffolding")

    time.sleep(0.3)
    session.add_student_input("x^2 - 5x + 6 = (x-2)(x-3)?", is_correct=True)
    session.add_tutor_response("Отлично! Теперь найди корни.", move_type="encourage")

    time.sleep(0.2)
    session.add_hint_request(hint_level=1)
    session.add_student_input("x = 2 и x = 3", is_correct=True)

    # Print stats
    print(f"Turns: {session.turn_count}")
    print(f"Correct: {session.correct_count}")
    print(f"Errors: {session.error_count}")
    print(f"Hints: {session.hint_count}")
    print(f"Avg response time: {session.get_average_response_time():.0f}ms")
    print(f"Response trend: {session.get_response_time_trend()}")
    print(f"Should suggest break: {session.should_suggest_break()}")

    print("\nCognitive load signals:")
    print(session.get_cognitive_load_signals())
