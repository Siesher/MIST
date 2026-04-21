"""
Metacognitive Scaffolding Module

Tracks student metacognitive state and provides structured scaffolding
to develop self-regulation and reflection skills.

Key features:
- Detects "stuck points" where students need help
- Provides metacognitive prompts instead of direct answers
- Tracks intervention effectiveness
- Generates end-of-session reflections
"""

import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from collections import defaultdict
import uuid

from src.data.schemas import (
    MetacognitiveLevel,
    StuckPointType,
    StuckPoint,
    MetacognitiveProfile,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# METACOGNITIVE PROMPTS (Russian)
# ═══════════════════════════════════════════════════════════════════════════

METACOGNITIVE_PROMPTS: Dict[str, Dict[str, List[str]]] = {
    # Understanding prompts - help identify what's unclear
    "understanding": {
        "initial": [
            "Давай разберёмся. Что именно тебе непонятно в этой задаче?",
            "Попробуй своими словами пересказать условие задачи.",
            "Какую часть условия ты понимаешь, а какая вызывает затруднения?",
            "Что ты уже знаешь о данном типе задач?",
        ],
        "deeper": [
            "Какие понятия из условия тебе знакомы? Какие — новые?",
            "Можешь ли ты выделить данные и то, что нужно найти?",
            "Если бы ты объяснял эту задачу другу, с чего бы начал?",
        ],
        "reframe": [
            "Попробуй переформулировать задачу проще.",
            "Какой похожий пример ты бы привёл для этой ситуации?",
            "Можешь представить эту задачу визуально — схемой или рисунком?",
        ],
    },

    # Strategy prompts - help select approach
    "strategy": {
        "initial": [
            "Какие методы решения подобных задач ты знаешь?",
            "С чего обычно начинается решение такого типа задач?",
            "Какой первый шаг приходит тебе в голову?",
            "Можешь ли ты вспомнить похожую задачу и как её решали?",
        ],
        "deeper": [
            "Почему ты выбрал именно этот метод?",
            "Какие ещё способы решения могли бы сработать?",
            "Что изменится, если попробовать другой подход?",
        ],
        "compare": [
            "Сравни свой подход с тем, что мы изучали ранее.",
            "Какой метод был бы проще? Какой — точнее?",
            "В каких случаях твой метод работает лучше всего?",
        ],
    },

    # Monitoring prompts - help track progress
    "monitoring": {
        "initial": [
            "Ты уверен в этом шаге? Как можно проверить?",
            "Что произойдёт, если подставить полученный ответ обратно?",
            "Давай остановимся — всё ли идёт по плану?",
            "На каком этапе решения ты сейчас находишься?",
        ],
        "check": [
            "Твой промежуточный результат кажется правильным?",
            "Можно ли упростить то, что получилось?",
            "Не пропустил ли ты какой-нибудь шаг?",
        ],
        "evaluate": [
            "Ответ получился разумным? Соответствует ожиданиям?",
            "Как можно проверить правильность ответа другим способом?",
            "Если ответ неверный, на каком шаге могла быть ошибка?",
        ],
    },

    # Regulation prompts - help adjust approach
    "regulation": {
        "initial": [
            "Кажется, что-то не работает. Что можно изменить?",
            "Может быть, стоит попробовать другой подход?",
            "Давай сделаем паузу и подумаем, что пошло не так.",
        ],
        "pivot": [
            "Какая альтернативная стратегия могла бы помочь?",
            "Что ты узнал из этой попытки?",
            "Как можно использовать эту информацию для новой попытки?",
        ],
        "simplify": [
            "Можно ли упростить задачу, решив сначала более простой случай?",
            "Какую часть задачи ты точно умеешь решать?",
            "Начнём с того, что ты знаешь наверняка.",
        ],
    },
}

# Stuck point detection patterns
STUCK_PATTERNS: Dict[StuckPointType, List[str]] = {
    StuckPointType.CONCEPTUAL: [
        r"не понима[юеш]",
        r"что это значит",
        r"что такое",
        r"непонятно",
        r"не знаю что это",
        r"как это понять",
        r"что означает",
        r"в чём смысл",
    ],
    StuckPointType.PROCEDURAL: [
        r"не знаю как",
        r"что делать",
        r"какой метод",
        r"как начать",
        r"с чего начать",
        r"как решать",
        r"какой способ",
        r"какую формулу",
        r"что применить",
    ],
    StuckPointType.MONITORING: [
        r"правильно\s*\?",
        r"верно\s*\?",
        r"так\s*\?",
        r"не уверен",
        r"сомнева[юеш]сь",
        r"не знаю правильно ли",
        r"можно так\s*\?",
    ],
    StuckPointType.MOTIVATION: [
        r"не могу",
        r"сдаюсь",
        r"слишком сложно",
        r"не получается",
        r"не выходит",
        r"невозможно",
        r"бесполезно",
        r"ненавижу",
        r"устал",
        r"надоело",
    ],
}


class MetacognitiveTracker:
    """
    Tracks student metacognitive state and provides scaffolding.

    Instead of giving direct answers when a student is stuck,
    this module asks structured questions to develop self-regulation skills.
    """

    def __init__(
        self,
        student_memory: Optional[object] = None,
        prompt_cooldown: int = 3,
        max_prompts_per_type: int = 2,
    ):
        """
        Initialize the tracker.

        Args:
            student_memory: Optional StudentMemory for personalization
            prompt_cooldown: Minimum messages between metacognitive prompts
            max_prompts_per_type: Maximum prompts of same type before switching
        """
        self.student_memory = student_memory
        self.prompt_cooldown = prompt_cooldown
        self.max_prompts_per_type = max_prompts_per_type

        # Session state
        self.stuck_points: List[StuckPoint] = []
        self.interventions: List[Dict[str, Any]] = []
        self.messages_since_prompt = 0
        self.prompt_counts: Dict[str, int] = defaultdict(int)
        self.session_start = datetime.now()

        # Profile tracking
        self.correct_after_prompt = 0
        self.total_prompts = 0

        logger.info("MetacognitiveTracker initialized")

    def detect_stuck_point(
        self,
        message: str,
        context: Optional[List[Dict[str, str]]] = None,
        error_count: int = 0,
        time_on_task_seconds: float = 0,
    ) -> Optional[StuckPoint]:
        """
        Detect if student is at a stuck point.

        Args:
            message: Student's current message
            context: Recent conversation history
            error_count: Number of recent errors
            time_on_task_seconds: Time spent on current task

        Returns:
            StuckPoint if detected, None otherwise
        """
        message_lower = message.lower().strip()

        # Check each stuck type pattern
        detected_type: Optional[StuckPointType] = None
        confidence = 0.0
        trigger_phrase = ""

        for stuck_type, patterns in STUCK_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, message_lower)
                if match:
                    detected_type = stuck_type
                    trigger_phrase = match.group()
                    confidence = 0.8
                    break
            if detected_type:
                break

        # Implicit stuck detection from behavior
        if not detected_type:
            # Short, frustrated messages
            if len(message) < 20 and any(c in message for c in "?!..."):
                detected_type = StuckPointType.MONITORING
                confidence = 0.5
                trigger_phrase = "[implicit: short questioning message]"

            # Long time without progress
            elif time_on_task_seconds > 300 and error_count > 2:  # 5 min + errors
                detected_type = StuckPointType.PROCEDURAL
                confidence = 0.6
                trigger_phrase = "[implicit: extended time with errors]"

            # Repeated errors suggest conceptual gap
            elif error_count >= 3:
                detected_type = StuckPointType.CONCEPTUAL
                confidence = 0.5
                trigger_phrase = "[implicit: repeated errors]"

        if not detected_type:
            return None

        # Create stuck point record
        stuck_point = StuckPoint(
            id=str(uuid.uuid4()),
            student_id="",  # Will be set by caller
            session_id="",  # Will be set by caller
            type=detected_type,
            trigger_message=message,
            trigger_phrase=trigger_phrase,
            confidence=confidence,
            context_messages=context[-3:] if context else [],
            intervention_type=None,
            intervention_message=None,
            resolved=False,
            resolution_message=None,
            created_at=datetime.now(),
        )

        self.stuck_points.append(stuck_point)
        logger.debug(f"Detected stuck point: {detected_type.value} (conf={confidence:.2f})")

        return stuck_point

    def get_metacognitive_prompt(
        self,
        stuck_point: StuckPoint,
        task_topic: str = "",
        previous_prompts: Optional[List[str]] = None,
    ) -> str:
        """
        Get appropriate metacognitive prompt for the stuck point.

        Args:
            stuck_point: The detected stuck point
            task_topic: Current task topic for context
            previous_prompts: Prompts already used this session

        Returns:
            Metacognitive prompt string
        """
        previous_prompts = previous_prompts or []

        # Map stuck type to prompt category
        type_to_category = {
            StuckPointType.CONCEPTUAL: "understanding",
            StuckPointType.PROCEDURAL: "strategy",
            StuckPointType.MONITORING: "monitoring",
            StuckPointType.MOTIVATION: "regulation",
        }

        category = type_to_category.get(stuck_point.type, "understanding")

        # Select subcategory based on confidence and history
        if stuck_point.confidence < 0.6:
            subcategory = "initial"
        elif self.prompt_counts[category] > 1:
            # Already tried initial prompts, go deeper
            subcategory = "deeper" if "deeper" in METACOGNITIVE_PROMPTS[category] else "initial"
        else:
            subcategory = "initial"

        # Get available prompts
        available_prompts = METACOGNITIVE_PROMPTS[category].get(subcategory, [])
        if not available_prompts:
            available_prompts = METACOGNITIVE_PROMPTS[category]["initial"]

        # Filter out already used prompts
        unused_prompts = [p for p in available_prompts if p not in previous_prompts]
        if not unused_prompts:
            unused_prompts = available_prompts  # Reset if all used

        # Select prompt
        import random
        prompt = random.choice(unused_prompts)

        # Track usage
        self.prompt_counts[category] += 1
        self.total_prompts += 1
        self.messages_since_prompt = 0

        logger.debug(f"Selected metacognitive prompt: category={category}, sub={subcategory}")

        return prompt

    def should_provide_prompt(self) -> bool:
        """Check if we should provide a metacognitive prompt now."""
        # Cooldown check
        if self.messages_since_prompt < self.prompt_cooldown:
            return True  # Recently stuck, prompt is okay

        return True  # Default to allowing prompts

    def record_intervention(
        self,
        stuck_point: StuckPoint,
        intervention_type: str,
        intervention_message: str,
        was_helpful: Optional[bool] = None,
    ) -> None:
        """
        Record an intervention for effectiveness tracking.

        Args:
            stuck_point: The stuck point being addressed
            intervention_type: Type of intervention (prompt, hint, explanation)
            intervention_message: The actual intervention text
            was_helpful: Whether it helped (if known)
        """
        intervention = {
            "stuck_point_id": stuck_point.id,
            "type": intervention_type,
            "message": intervention_message,
            "timestamp": datetime.now(),
            "was_helpful": was_helpful,
        }

        self.interventions.append(intervention)

        # Update stuck point
        stuck_point.intervention_type = intervention_type
        stuck_point.intervention_message = intervention_message

        logger.debug(f"Recorded intervention: type={intervention_type}")

    def mark_resolved(
        self,
        stuck_point: StuckPoint,
        resolution_message: str,
        was_correct: bool,
    ) -> None:
        """
        Mark a stuck point as resolved.

        Args:
            stuck_point: The stuck point to resolve
            resolution_message: Student's resolving message
            was_correct: Whether the student got the answer correct
        """
        stuck_point.resolved = True
        stuck_point.resolution_message = resolution_message
        stuck_point.resolved_at = datetime.now()

        if was_correct:
            self.correct_after_prompt += 1

        logger.debug(f"Stuck point resolved: correct={was_correct}")

    def get_reflection_prompt(
        self,
        session_duration_minutes: float,
        tasks_attempted: int,
        tasks_correct: int,
        topics_covered: List[str],
    ) -> str:
        """
        Generate end-of-session reflection prompt.

        Args:
            session_duration_minutes: Total session length
            tasks_attempted: Number of tasks tried
            tasks_correct: Number of tasks solved correctly
            topics_covered: Topics worked on

        Returns:
            Reflection prompt for the student
        """
        # Calculate metrics
        accuracy = tasks_correct / tasks_attempted if tasks_attempted > 0 else 0
        stuck_count = len(self.stuck_points)
        resolved_count = sum(1 for sp in self.stuck_points if sp.resolved)

        # Build reflection
        lines = ["## 🪞 Рефлексия после занятия", ""]

        # Session summary
        lines.append(f"**Продолжительность:** {session_duration_minutes:.0f} минут")
        lines.append(f"**Задач решено:** {tasks_correct} из {tasks_attempted}")

        if topics_covered:
            lines.append(f"**Темы:** {', '.join(topics_covered[:3])}")
        lines.append("")

        # Metacognitive questions based on session
        lines.append("**Вопросы для размышления:**")
        lines.append("")

        if accuracy >= 0.8:
            lines.append("1. Какая стратегия помогла тебе сегодня больше всего?")
            lines.append("2. Какую тему ты теперь понимаешь лучше?")
            lines.append("3. Что было самым интересным?")
        elif accuracy >= 0.5:
            lines.append("1. Какие задачи показались сложнее? Почему?")
            lines.append("2. Что помогло тебе справиться с трудностями?")
            lines.append("3. Какую тему стоит повторить?")
        else:
            lines.append("1. Какие понятия вызвали наибольшие затруднения?")
            lines.append("2. Какой способ решения был для тебя новым?")
            lines.append("3. Что бы ты сделал по-другому в следующий раз?")

        # Stuck point analysis
        if stuck_count > 0:
            lines.append("")
            lines.append(f"**Моменты затруднений:** {stuck_count}")

            # Group by type
            type_counts = defaultdict(int)
            for sp in self.stuck_points:
                type_counts[sp.type.value] += 1

            if StuckPointType.CONCEPTUAL.value in type_counts:
                lines.append(f"- Понимание понятий: {type_counts[StuckPointType.CONCEPTUAL.value]}")
            if StuckPointType.PROCEDURAL.value in type_counts:
                lines.append(f"- Выбор метода: {type_counts[StuckPointType.PROCEDURAL.value]}")
            if StuckPointType.MONITORING.value in type_counts:
                lines.append(f"- Проверка решения: {type_counts[StuckPointType.MONITORING.value]}")

            if resolved_count > 0:
                lines.append(f"")
                lines.append(f"Ты справился с {resolved_count} из {stuck_count} затруднений!")

        lines.append("")
        lines.append("---")
        lines.append("*Рефлексия помогает учиться эффективнее. Попробуй ответить на вопросы письменно.*")

        return "\n".join(lines)

    def update_profile(self) -> MetacognitiveProfile:
        """
        Calculate metacognitive profile from session history.

        Returns:
            MetacognitiveProfile with assessed levels
        """
        # Calculate metrics
        total_stuck = len(self.stuck_points)
        resolved = sum(1 for sp in self.stuck_points if sp.resolved)
        self_initiated = sum(
            1 for sp in self.stuck_points
            if sp.confidence >= 0.7  # Explicit requests for help show awareness
        )

        # Assess each dimension
        # Awareness: How well does student recognize when stuck?
        if total_stuck == 0:
            awareness = MetacognitiveLevel.EMERGING
        elif self_initiated / max(total_stuck, 1) >= 0.7:
            awareness = MetacognitiveLevel.PROFICIENT
        elif self_initiated / max(total_stuck, 1) >= 0.4:
            awareness = MetacognitiveLevel.DEVELOPING
        else:
            awareness = MetacognitiveLevel.EMERGING

        # Regulation: How well does student recover?
        if total_stuck == 0:
            regulation = MetacognitiveLevel.EMERGING
        elif resolved / max(total_stuck, 1) >= 0.8:
            regulation = MetacognitiveLevel.PROFICIENT
        elif resolved / max(total_stuck, 1) >= 0.5:
            regulation = MetacognitiveLevel.DEVELOPING
        else:
            regulation = MetacognitiveLevel.EMERGING

        # Evaluation: Does student check work?
        monitoring_stuck = sum(
            1 for sp in self.stuck_points
            if sp.type == StuckPointType.MONITORING
        )
        if monitoring_stuck >= 2:
            evaluation = MetacognitiveLevel.DEVELOPING  # Shows monitoring behavior
        else:
            evaluation = MetacognitiveLevel.EMERGING

        # Overall level
        levels = [awareness, regulation, evaluation]
        level_values = {
            MetacognitiveLevel.EMERGING: 1,
            MetacognitiveLevel.DEVELOPING: 2,
            MetacognitiveLevel.PROFICIENT: 3,
            MetacognitiveLevel.ADVANCED: 4,
        }

        avg_level = sum(level_values[l] for l in levels) / len(levels)
        if avg_level >= 3.5:
            overall = MetacognitiveLevel.ADVANCED
        elif avg_level >= 2.5:
            overall = MetacognitiveLevel.PROFICIENT
        elif avg_level >= 1.5:
            overall = MetacognitiveLevel.DEVELOPING
        else:
            overall = MetacognitiveLevel.EMERGING

        profile = MetacognitiveProfile(
            student_id="",  # Set by caller
            overall_level=overall,
            awareness_level=awareness,
            regulation_level=regulation,
            evaluation_level=evaluation,
            stuck_points_count=total_stuck,
            successful_recoveries=resolved,
            intervention_effectiveness=self.correct_after_prompt / max(self.total_prompts, 1),
            last_updated=datetime.now(),
        )

        logger.debug(f"Updated metacognitive profile: {overall.value}")

        return profile

    def increment_message_count(self) -> None:
        """Increment the message counter (call after each student message)."""
        self.messages_since_prompt += 1

    def reset_session(self) -> None:
        """Reset tracker for a new session."""
        self.stuck_points = []
        self.interventions = []
        self.messages_since_prompt = 0
        self.prompt_counts = defaultdict(int)
        self.session_start = datetime.now()
        self.correct_after_prompt = 0
        self.total_prompts = 0

        logger.debug("MetacognitiveTracker session reset")

    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        return {
            "total_stuck_points": len(self.stuck_points),
            "resolved_stuck_points": sum(1 for sp in self.stuck_points if sp.resolved),
            "total_interventions": len(self.interventions),
            "total_prompts": self.total_prompts,
            "correct_after_prompt": self.correct_after_prompt,
            "session_duration_seconds": (datetime.now() - self.session_start).total_seconds(),
            "stuck_by_type": {
                t.value: sum(1 for sp in self.stuck_points if sp.type == t)
                for t in StuckPointType
            },
        }


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    tracker = MetacognitiveTracker()

    # Simulate stuck student
    messages = [
        "не понимаю что делать",
        "как это решить?",
        "правильно?",
        "не могу, слишком сложно",
    ]

    for msg in messages:
        print(f"\n=== Student: {msg} ===")
        stuck = tracker.detect_stuck_point(msg)

        if stuck:
            print(f"Stuck type: {stuck.type.value}")
            print(f"Confidence: {stuck.confidence:.2f}")

            prompt = tracker.get_metacognitive_prompt(stuck)
            print(f"Metacognitive prompt: {prompt}")

            tracker.record_intervention(stuck, "metacognitive_prompt", prompt)

        tracker.increment_message_count()

    # End-of-session reflection
    print("\n" + "=" * 50)
    print(tracker.get_reflection_prompt(
        session_duration_minutes=45,
        tasks_attempted=8,
        tasks_correct=5,
        topics_covered=["производные", "интегралы"],
    ))

    # Profile
    print("\n=== Metacognitive Profile ===")
    profile = tracker.update_profile()
    print(f"Overall: {profile.overall_level.value}")
    print(f"Awareness: {profile.awareness_level.value}")
    print(f"Regulation: {profile.regulation_level.value}")
    print(f"Evaluation: {profile.evaluation_level.value}")

    print("\n=== Session Stats ===")
    print(tracker.get_session_stats())
