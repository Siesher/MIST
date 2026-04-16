#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Агент Планировщик - выбор педагогической стратегии.

На основе профиля ученика и контекста задачи выбирает
оптимальную стратегию обучения и последовательность действий.

Учитывает:
- Профиль ошибок ученика
- Уровень уверенности
- Когнитивную нагрузку
- Историю сессии

На основе исследований:
- Cognitive Load Theory (Sweller)
- Zone of Proximal Development (Vygotsky)
- GenMentor (WWW 2025)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.agents.profiler import ConfidenceLevel, ErrorType, StudentProfile

logger = logging.getLogger(__name__)


class CognitiveLoadLevel(Enum):
    """Уровни когнитивной нагрузки."""

    LOW = "low"
    OPTIMAL = "optimal"
    HIGH = "high"
    OVERLOAD = "overload"


class TeachingStrategy(Enum):
    """Стратегии обучения."""

    GUIDED_DISCOVERY = "guided_discovery"  # Направляемое открытие
    SCAFFOLDED = "scaffolded"  # Пошаговый скаффолдинг
    ERROR_CORRECTION = "error_correction"  # Исправление ошибок
    CONCEPTUAL_REPAIR = "conceptual_repair"  # Ремонт концепций
    ENCOURAGEMENT = "encouragement"  # Поддержка и мотивация
    REVIEW = "review"  # Повторение материала
    DIRECT_INSTRUCTION = "direct_instruction"  # Прямое объяснение
    COGNITIVE_OFFLOAD = "cognitive_offload"  # Разгрузка когнитивной нагрузки
    BREAK_SUGGESTED = "break_suggested"  # Предложение перерыва


class TeachingMove(Enum):
    """Педагогические ходы."""

    SCAFFOLDING = "scaffolding"
    PROBLEMATIZE = "problematize"
    RECTIFY = "rectify"
    ENCOURAGE = "encourage"
    HINT = "hint"
    TELL = "tell"


@dataclass
class TeachingPlan:
    """План обучения для текущего взаимодействия."""

    strategy: TeachingStrategy
    primary_move: TeachingMove
    move_sequence: List[TeachingMove] = field(default_factory=list)
    focus_areas: List[str] = field(default_factory=list)
    avoid_areas: List[str] = field(default_factory=list)
    tone: str = "supportive"  # supportive, neutral, challenging
    hints_to_use: List[str] = field(default_factory=list)
    max_hints_before_tell: int = 3
    should_check_understanding: bool = True
    prerequisites_to_review: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "primary_move": self.primary_move.value,
            "move_sequence": [m.value for m in self.move_sequence],
            "focus_areas": self.focus_areas,
            "avoid_areas": self.avoid_areas,
            "tone": self.tone,
            "hints_to_use": self.hints_to_use,
            "max_hints_before_tell": self.max_hints_before_tell,
            "should_check_understanding": self.should_check_understanding,
            "prerequisites_to_review": self.prerequisites_to_review,
        }

    def to_prompt_context(self) -> str:
        """Преобразование в контекст для промпта репетитора."""
        parts = [
            f"СТРАТЕГИЯ: {self.strategy.value}",
            f"ОСНОВНОЙ ХОД: {self.primary_move.value}",
            f"ТОН: {self.tone}",
        ]

        if self.focus_areas:
            parts.append(f"ФОКУС: {', '.join(self.focus_areas)}")

        if self.avoid_areas:
            parts.append(f"ИЗБЕГАТЬ: {', '.join(self.avoid_areas)}")

        if self.hints_to_use:
            parts.append(f"ПОДСКАЗКИ: {self.hints_to_use[0]}")

        return "\n".join(parts)


@dataclass
class SessionContext:
    """Контекст сессии обучения."""

    topic: str
    difficulty: str
    turn_number: int = 0
    hints_given: int = 0
    errors_made: int = 0
    correct_steps: int = 0
    student_frustrated: bool = False
    problem_almost_solved: bool = False

    # Cognitive load signals
    cognitive_load_level: CognitiveLoadLevel = CognitiveLoadLevel.OPTIMAL
    cognitive_load_score: float = 0.5
    should_simplify: bool = False
    should_offer_break: bool = False
    response_time_trend: str = "stable"  # increasing, decreasing, stable
    session_duration_minutes: float = 0.0


class PlannerAgent:
    """
    Агент для планирования педагогической стратегии.

    Использует:
    - Профиль ученика от ProfilerAgent
    - Контекст сессии
    - Правила педагогики

    Выдаёт план действий для SocraticTutorAgent.
    """

    # Правила выбора стратегии
    STRATEGY_RULES = {
        # (error_type, confidence, needs_encouragement) -> strategy
        (ErrorType.CONCEPTUAL, ConfidenceLevel.LOW, False): TeachingStrategy.SCAFFOLDED,
        (ErrorType.CONCEPTUAL, ConfidenceLevel.LOW, True): TeachingStrategy.ENCOURAGEMENT,
        (ErrorType.CONCEPTUAL, ConfidenceLevel.HIGH, False): TeachingStrategy.CONCEPTUAL_REPAIR,
        (ErrorType.MISCONCEPTION, ConfidenceLevel.HIGH, False): TeachingStrategy.CONCEPTUAL_REPAIR,
        (ErrorType.PROCEDURAL, ConfidenceLevel.MEDIUM, False): TeachingStrategy.GUIDED_DISCOVERY,
        (ErrorType.CARELESS, ConfidenceLevel.HIGH, False): TeachingStrategy.ERROR_CORRECTION,
        (ErrorType.INCOMPLETE, ConfidenceLevel.MEDIUM, False): TeachingStrategy.GUIDED_DISCOVERY,
    }

    # Последовательности ходов для стратегий
    MOVE_SEQUENCES = {
        TeachingStrategy.GUIDED_DISCOVERY: [
            TeachingMove.SCAFFOLDING,
            TeachingMove.HINT,
            TeachingMove.ENCOURAGE,
            TeachingMove.HINT,
        ],
        TeachingStrategy.SCAFFOLDED: [
            TeachingMove.SCAFFOLDING,
            TeachingMove.SCAFFOLDING,
            TeachingMove.HINT,
            TeachingMove.ENCOURAGE,
        ],
        TeachingStrategy.ERROR_CORRECTION: [
            TeachingMove.RECTIFY,
            TeachingMove.HINT,
            TeachingMove.SCAFFOLDING,
        ],
        TeachingStrategy.CONCEPTUAL_REPAIR: [
            TeachingMove.PROBLEMATIZE,
            TeachingMove.SCAFFOLDING,
            TeachingMove.RECTIFY,
            TeachingMove.ENCOURAGE,
        ],
        TeachingStrategy.ENCOURAGEMENT: [
            TeachingMove.ENCOURAGE,
            TeachingMove.SCAFFOLDING,
            TeachingMove.HINT,
            TeachingMove.ENCOURAGE,
        ],
        TeachingStrategy.REVIEW: [
            TeachingMove.TELL,
            TeachingMove.SCAFFOLDING,
            TeachingMove.HINT,
        ],
        TeachingStrategy.DIRECT_INSTRUCTION: [
            TeachingMove.TELL,
            TeachingMove.SCAFFOLDING,
            TeachingMove.HINT,
        ],
        TeachingStrategy.COGNITIVE_OFFLOAD: [
            TeachingMove.ENCOURAGE,
            TeachingMove.SCAFFOLDING,  # Simplified scaffolding
            TeachingMove.HINT,  # More direct hints
            TeachingMove.TELL,  # Willing to tell sooner
        ],
        TeachingStrategy.BREAK_SUGGESTED: [
            TeachingMove.ENCOURAGE,
            TeachingMove.ENCOURAGE,
        ],
    }

    # Cognitive load thresholds for strategy adjustment
    COGNITIVE_LOAD_THRESHOLDS = {
        CognitiveLoadLevel.LOW: 0.3,
        CognitiveLoadLevel.OPTIMAL: 0.5,
        CognitiveLoadLevel.HIGH: 0.7,
        CognitiveLoadLevel.OVERLOAD: 0.85,
    }

    # Тон для разных ситуаций
    TONE_RULES = {
        ConfidenceLevel.LOW: "supportive",
        ConfidenceLevel.CONFUSED: "supportive",
        ConfidenceLevel.MEDIUM: "neutral",
        ConfidenceLevel.HIGH: "challenging",
    }

    def __init__(self, llm_client=None, use_llm: bool = False):
        """
        Инициализация планировщика.

        Args:
            llm_client: Клиент LLM (опционально, для сложного планирования)
            use_llm: Использовать LLM для планирования
        """
        self.llm = llm_client
        self.use_llm = use_llm and llm_client is not None

        logger.info(f"PlannerAgent инициализирован (use_llm={self.use_llm})")

    def create_plan(
        self,
        profile: StudentProfile,
        context: SessionContext,
        available_hints: Optional[List[str]] = None,
        graph_context: Optional[Dict] = None,
    ) -> TeachingPlan:
        """
        Создание плана обучения.

        Args:
            profile: Профиль ученика от ProfilerAgent
            context: Контекст текущей сессии
            available_hints: Доступные подсказки из RAG
            graph_context: Knowledge Forge graph context (from navigator)

        Returns:
            TeachingPlan с рекомендациями
        """
        # Определяем стратегию
        strategy = self._select_strategy(profile, context)

        # Определяем основной ход
        primary_move = self._select_primary_move(profile, strategy, context)

        # Получаем последовательность ходов
        move_sequence = self._get_move_sequence(strategy, context)

        # Определяем тон
        tone = self._select_tone(profile, context)

        # Определяем фокус и ограничения
        focus_areas = self._get_focus_areas(profile, context)
        avoid_areas = self._get_avoid_areas(profile, context)

        # Выбираем подсказки
        hints = self._select_hints(profile, available_hints or [])

        # Enrich with Knowledge Forge graph context (if available)
        prereqs_to_review = list(profile.topic_gaps) if profile.topic_gaps else []
        if graph_context:
            # Add missing prerequisites from graph gap diagnosis
            student_data = graph_context.get("student", {})
            if student_data.get("has_gaps"):
                for prereq in student_data.get("prerequisites", []):
                    if prereq.get("status") == "gap" and prereq["id"] not in prereqs_to_review:
                        prereqs_to_review.append(prereq["id"])

            # If graph shows misconceptions, bias toward CONCEPTUAL_REPAIR
            misconceptions = graph_context.get("misconceptions", [])
            if misconceptions and strategy != TeachingStrategy.CONCEPTUAL_REPAIR:
                strategy = TeachingStrategy.CONCEPTUAL_REPAIR
                primary_move = TeachingMove.RECTIFY
                move_sequence = self._get_move_sequence(strategy, context)
                logger.info(
                    f"Strategy adjusted to CONCEPTUAL_REPAIR based on "
                    f"{len(misconceptions)} misconceptions from knowledge graph"
                )

        # Собираем план
        plan = TeachingPlan(
            strategy=strategy,
            primary_move=primary_move,
            move_sequence=move_sequence,
            focus_areas=focus_areas,
            avoid_areas=avoid_areas,
            tone=tone,
            hints_to_use=hints,
            max_hints_before_tell=self._calc_max_hints(profile, context),
            should_check_understanding=profile.understanding_score < 0.6,
            prerequisites_to_review=prereqs_to_review,
        )

        logger.info(
            f"План создан: strategy={strategy.value}, move={primary_move.value}, tone={tone}"
        )

        return plan

    def _select_strategy(
        self, profile: StudentProfile, context: SessionContext
    ) -> TeachingStrategy:
        """Выбор основной стратегии обучения с учётом когнитивной нагрузки."""

        # CRITICAL: Проверяем когнитивную нагрузку в первую очередь
        cognitive_strategy = self._check_cognitive_load_strategy(profile, context)
        if cognitive_strategy:
            return cognitive_strategy

        # Особые случаи
        if profile.needs_encouragement or context.student_frustrated:
            return TeachingStrategy.ENCOURAGEMENT

        if context.hints_given >= 3 and context.errors_made > 2:
            return TeachingStrategy.DIRECT_INSTRUCTION

        if context.problem_almost_solved:
            return TeachingStrategy.GUIDED_DISCOVERY

        # Выбор по правилам
        if profile.errors:
            main_error = profile.errors[0]
            key = (main_error.error_type, profile.confidence_level, profile.needs_encouragement)

            if key in self.STRATEGY_RULES:
                base_strategy = self.STRATEGY_RULES[key]
            else:
                # Fallback по типу ошибки
                error_strategies = {
                    ErrorType.CONCEPTUAL: TeachingStrategy.SCAFFOLDED,
                    ErrorType.MISCONCEPTION: TeachingStrategy.CONCEPTUAL_REPAIR,
                    ErrorType.PROCEDURAL: TeachingStrategy.GUIDED_DISCOVERY,
                    ErrorType.CARELESS: TeachingStrategy.ERROR_CORRECTION,
                    ErrorType.INCOMPLETE: TeachingStrategy.GUIDED_DISCOVERY,
                    ErrorType.NOTATION: TeachingStrategy.ERROR_CORRECTION,
                }
                base_strategy = error_strategies.get(
                    main_error.error_type, TeachingStrategy.SCAFFOLDED
                )

            # Корректируем стратегию на основе когнитивной нагрузки
            return self._adjust_strategy_for_cognitive_load(base_strategy, context)

        # По умолчанию
        return TeachingStrategy.GUIDED_DISCOVERY

    def _check_cognitive_load_strategy(
        self, profile: StudentProfile, context: SessionContext
    ) -> Optional[TeachingStrategy]:
        """
        Проверить, нужна ли специальная стратегия для когнитивной нагрузки.

        Returns:
            TeachingStrategy если нужна специальная обработка, иначе None
        """
        # Предложить перерыв при перегрузке
        if context.should_offer_break:
            logger.info("Cognitive overload detected - suggesting break")
            return TeachingStrategy.BREAK_SUGGESTED

        # Когнитивная разгрузка при высокой нагрузке
        if context.cognitive_load_level == CognitiveLoadLevel.OVERLOAD:
            logger.info("Cognitive overload - switching to offload strategy")
            return TeachingStrategy.COGNITIVE_OFFLOAD

        if context.cognitive_load_level == CognitiveLoadLevel.HIGH:
            # При высокой нагрузке + увеличивающемся времени ответа
            if context.response_time_trend == "increasing":
                logger.info("High cognitive load with increasing response time")
                return TeachingStrategy.COGNITIVE_OFFLOAD

        # Длинная сессия без перерыва
        if context.session_duration_minutes > 45:
            logger.info("Long session - suggesting break")
            return TeachingStrategy.BREAK_SUGGESTED

        return None

    def _adjust_strategy_for_cognitive_load(
        self, strategy: TeachingStrategy, context: SessionContext
    ) -> TeachingStrategy:
        """
        Скорректировать стратегию на основе когнитивной нагрузки.

        При высокой нагрузке упрощаем стратегию.
        """
        if context.cognitive_load_level in [CognitiveLoadLevel.HIGH, CognitiveLoadLevel.OVERLOAD]:
            # Сложные стратегии заменяем на более простые
            simplification_map = {
                TeachingStrategy.GUIDED_DISCOVERY: TeachingStrategy.SCAFFOLDED,
                TeachingStrategy.CONCEPTUAL_REPAIR: TeachingStrategy.SCAFFOLDED,
            }
            simplified = simplification_map.get(strategy, strategy)
            if simplified != strategy:
                logger.debug(
                    f"Simplified strategy due to cognitive load: {strategy.value} -> {simplified.value}"
                )
            return simplified

        return strategy

    def _select_primary_move(
        self, profile: StudentProfile, strategy: TeachingStrategy, context: SessionContext
    ) -> TeachingMove:
        """Выбор основного педагогического хода."""

        # Из профиля если есть
        if profile.recommended_approach:
            try:
                return TeachingMove(profile.recommended_approach)
            except ValueError:
                pass

        # Из последовательности стратегии
        sequence = self.MOVE_SEQUENCES.get(strategy, [TeachingMove.SCAFFOLDING])

        # Учитываем номер хода в сессии
        idx = min(context.turn_number, len(sequence) - 1)
        return sequence[idx]

    def _get_move_sequence(
        self, strategy: TeachingStrategy, context: SessionContext
    ) -> List[TeachingMove]:
        """Получение последовательности ходов для стратегии."""
        base_sequence = self.MOVE_SEQUENCES.get(
            strategy, [TeachingMove.SCAFFOLDING, TeachingMove.HINT]
        )

        # Адаптируем под контекст
        if context.turn_number > 0:
            # Пропускаем уже сделанные ходы
            return base_sequence[context.turn_number % len(base_sequence) :]

        return base_sequence

    def _select_tone(self, profile: StudentProfile, context: SessionContext) -> str:
        """Выбор тона общения."""

        if profile.needs_encouragement or context.student_frustrated:
            return "supportive"

        if context.errors_made == 0 and context.correct_steps > 2:
            return "challenging"  # Можно усложнить

        return self.TONE_RULES.get(profile.confidence_level, "neutral")

    def _get_focus_areas(self, profile: StudentProfile, context: SessionContext) -> List[str]:
        """Определение областей фокуса."""
        focus = []

        # Из ошибок
        for error in profile.errors[:2]:
            if error.location:
                focus.append(f"Место ошибки: {error.location}")
            if error.suggested_hint:
                focus.append(error.suggested_hint)

        # Из пробелов в знаниях
        focus.extend(profile.topic_gaps[:2])

        return focus

    def _get_avoid_areas(self, profile: StudentProfile, context: SessionContext) -> List[str]:
        """Определение того, чего следует избегать."""
        avoid = []

        # Не давать прямой ответ если ученик близок к решению
        if context.problem_almost_solved:
            avoid.append("Не давать прямой ответ - ученик близок к решению")

        # Не усложнять если ученик расстроен
        if profile.needs_encouragement:
            avoid.append("Не критиковать и не указывать на все ошибки сразу")

        # Не упрощать слишком если уверенность высокая
        if profile.confidence_level == ConfidenceLevel.HIGH:
            avoid.append("Не быть снисходительным")

        return avoid

    def _select_hints(self, profile: StudentProfile, available_hints: List[str]) -> List[str]:
        """Выбор подходящих подсказок."""
        hints = []

        # Из профиля
        for error in profile.errors:
            if error.suggested_hint:
                hints.append(error.suggested_hint)

        # Из доступных
        hints.extend(available_hints[:2])

        return hints[:3]  # Максимум 3 подсказки

    def _calc_max_hints(self, profile: StudentProfile, context: SessionContext) -> int:
        """Расчёт максимального количества подсказок до tell."""

        base = 3

        # Больше подсказок для сложных концептуальных ошибок
        if any(e.error_type == ErrorType.CONCEPTUAL for e in profile.errors):
            base += 1

        # Меньше подсказок если ученик уже много получил
        if context.hints_given >= 2:
            base -= 1

        # Больше терпения для расстроенных учеников
        if profile.needs_encouragement:
            base += 1

        return max(2, min(5, base))

    def update_plan(self, plan: TeachingPlan, new_response: str, was_correct: bool) -> TeachingPlan:
        """
        Обновление плана на основе нового ответа.

        Args:
            plan: Текущий план
            new_response: Новый ответ ученика
            was_correct: Был ли ответ правильным

        Returns:
            Обновлённый план
        """
        if was_correct:
            # Переходим к следующему шагу или поощрению
            if plan.move_sequence:
                plan.move_sequence = plan.move_sequence[1:]
            plan.primary_move = TeachingMove.ENCOURAGE
            plan.should_check_understanding = False
        else:
            # Продолжаем текущую стратегию
            if plan.move_sequence:
                plan.primary_move = plan.move_sequence[0]

        return plan


# Пример использования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    from src.agents.profiler import ConfidenceLevel, ErrorType, StudentError, StudentProfile

    print("\n=== Planner Agent Demo ===\n")

    planner = PlannerAgent()

    # Тест 1: Концептуальная ошибка с низкой уверенностью
    profile = StudentProfile(
        errors=[
            StudentError(
                error_type=ErrorType.CONCEPTUAL,
                description="Не понимает, что такое производная",
                severity=0.7,
            )
        ],
        confidence_level=ConfidenceLevel.LOW,
        understanding_score=0.3,
        needs_encouragement=False,
    )

    context = SessionContext(topic="derivatives", difficulty="medium", turn_number=0)

    plan = planner.create_plan(profile, context)

    print("Тест 1: Концептуальная ошибка")
    print(f"  Стратегия: {plan.strategy.value}")
    print(f"  Основной ход: {plan.primary_move.value}")
    print(f"  Тон: {plan.tone}")
    print(f"  Последовательность: {[m.value for m in plan.move_sequence]}")

    # Тест 2: Заблуждение с высокой уверенностью
    profile = StudentProfile(
        errors=[
            StudentError(
                error_type=ErrorType.MISCONCEPTION,
                description="Уверен, что (a+b)² = a² + b²",
                severity=0.8,
            )
        ],
        confidence_level=ConfidenceLevel.HIGH,
        understanding_score=0.4,
    )

    plan = planner.create_plan(profile, context)

    print("\nТест 2: Заблуждение с высокой уверенностью")
    print(f"  Стратегия: {plan.strategy.value}")
    print(f"  Основной ход: {plan.primary_move.value}")
    print(f"  Тон: {plan.tone}")

    # Тест 3: Расстроенный ученик
    profile = StudentProfile(
        errors=[],
        confidence_level=ConfidenceLevel.LOW,
        needs_encouragement=True,
        understanding_score=0.5,
    )

    context = SessionContext(
        topic="quadratic_equations", difficulty="hard", turn_number=2, student_frustrated=True
    )

    plan = planner.create_plan(profile, context)

    print("\nТест 3: Расстроенный ученик")
    print(f"  Стратегия: {plan.strategy.value}")
    print(f"  Тон: {plan.tone}")
    print(f"  Избегать: {plan.avoid_areas}")

    print("\n=== Контекст для промпта ===")
    print(plan.to_prompt_context())
