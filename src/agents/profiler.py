#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Агент Профайлер - диагностика ошибок ученика.

Анализирует ответы ученика и определяет:
- Тип ошибки (концептуальная, процедурная, невнимательность)
- Возможные заблуждения
- Рекомендуемый педагогический подход
- Когнитивную нагрузку (на основе сигналов)
- Состояние знаний (интеграция с KnowledgeTracker)

На основе исследований:
- GenMentor (WWW 2025) - многоагентное профилирование
- RL-DKT (2025) - интеграция с knowledge tracing
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from enum import Enum
from datetime import datetime
import logging

if TYPE_CHECKING:
    from src.models.knowledge_tracing import KnowledgeTracker, StudentModel
    from src.models.cognitive_load import CognitiveLoadEstimator, CognitiveLoad, CognitiveLoadSignals

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Типы ошибок ученика."""
    CONCEPTUAL = "conceptual"       # Непонимание концепции
    PROCEDURAL = "procedural"       # Ошибка в процедуре/алгоритме
    CARELESS = "careless"          # Невнимательность/опечатка
    NOTATION = "notation"          # Ошибка в записи/нотации
    INCOMPLETE = "incomplete"      # Неполное решение
    MISCONCEPTION = "misconception" # Устойчивое заблуждение
    UNKNOWN = "unknown"            # Не удалось определить


class ConfidenceLevel(Enum):
    """Уровень уверенности ученика."""
    LOW = "low"           # Низкая уверенность, много вопросов
    MEDIUM = "medium"     # Средняя уверенность
    HIGH = "high"         # Высокая уверенность (может быть ложной)
    CONFUSED = "confused" # Запутался, противоречивые ответы


@dataclass
class StudentError:
    """Диагностированная ошибка."""
    error_type: ErrorType
    description: str
    location: str = ""            # Где в решении ошибка
    severity: float = 0.5         # 0-1, насколько критична
    suggested_move: str = "hint"  # Рекомендуемый педагогический ход
    suggested_hint: str = ""      # Рекомендуемая подсказка

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.error_type.value,
            "description": self.description,
            "location": self.location,
            "severity": self.severity,
            "suggested_move": self.suggested_move,
            "suggested_hint": self.suggested_hint
        }


@dataclass
class StudentProfile:
    """Профиль ученика на основе диагностики."""
    errors: List[StudentError] = field(default_factory=list)
    misconceptions: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    recommended_approach: str = "scaffolding"
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    understanding_score: float = 0.5  # 0-1, оценка понимания
    needs_encouragement: bool = False
    topic_gaps: List[str] = field(default_factory=list)

    # Knowledge tracking integration
    mastery_by_skill: Dict[str, float] = field(default_factory=dict)
    recommended_difficulty: str = "medium"
    using_dkt: bool = False

    # Cognitive load integration
    cognitive_load_level: str = "optimal"
    cognitive_load_score: float = 0.5
    should_simplify: bool = False
    should_offer_break: bool = False

    # Session tracking
    consecutive_errors: int = 0
    response_time_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "errors": [e.to_dict() for e in self.errors],
            "misconceptions": self.misconceptions,
            "strengths": self.strengths,
            "recommended_approach": self.recommended_approach,
            "confidence_level": self.confidence_level.value,
            "understanding_score": self.understanding_score,
            "needs_encouragement": self.needs_encouragement,
            "topic_gaps": self.topic_gaps,
            # Knowledge tracking
            "mastery_by_skill": self.mastery_by_skill,
            "recommended_difficulty": self.recommended_difficulty,
            "using_dkt": self.using_dkt,
            # Cognitive load
            "cognitive_load_level": self.cognitive_load_level,
            "cognitive_load_score": self.cognitive_load_score,
            "should_simplify": self.should_simplify,
            "should_offer_break": self.should_offer_break,
            # Session
            "consecutive_errors": self.consecutive_errors,
            "response_time_ms": self.response_time_ms
        }


class ProfilerAgent:
    """
    Агент для диагностики ошибок и создания профиля ученика.

    Анализирует:
    - Ответ ученика на задачу
    - Историю взаимодействий
    - Типичные заблуждения по теме

    Может работать в двух режимах:
    1. С LLM - более точный анализ через промпт
    2. Rule-based - быстрый анализ на основе паттернов
    """

    PROFILER_PROMPT = """Ты — диагност ошибок в математике. Твоя задача — проанализировать ответ ученика и определить характер ошибки.

ЗАДАЧА:
{problem}

ПРАВИЛЬНЫЙ ПОДХОД/ОТВЕТ:
{correct_approach}

ОТВЕТ УЧЕНИКА:
{student_response}

ИСТОРИЯ ДИАЛОГА:
{history}

Проанализируй ответ и верни JSON:
{{
    "errors": [
        {{
            "type": "conceptual|procedural|careless|notation|incomplete|misconception",
            "description": "Описание ошибки на русском",
            "location": "Где именно в решении ошибка",
            "severity": 0.0-1.0,
            "suggested_move": "scaffolding|problematize|rectify|encourage|hint|tell",
            "suggested_hint": "Вопрос или подсказка для исправления"
        }}
    ],
    "misconceptions": ["Список возможных заблуждений"],
    "strengths": ["Что ученик делает правильно"],
    "recommended_approach": "scaffolding|problematize|rectify|encourage|hint|tell",
    "confidence_level": "low|medium|high|confused",
    "understanding_score": 0.0-1.0,
    "needs_encouragement": true|false,
    "topic_gaps": ["Темы, которые нужно повторить"]
}}

ПРАВИЛА ДИАГНОСТИКИ:
1. conceptual - ученик не понимает саму концепцию (например, что такое производная)
2. procedural - знает концепцию, но ошибается в шагах решения
3. careless - простая невнимательность (2+2=5)
4. notation - неправильная запись, но понимание верное
5. incomplete - начал правильно, но не довёл до конца
6. misconception - устойчивое неправильное понимание (например, (a+b)²=a²+b²)

РЕКОМЕНДАЦИИ ПО ХОДАМ:
- scaffolding: ученику нужна структура, разбить на шаги
- problematize: ученик уверен в неправильном - нужно показать противоречие
- rectify: мягко исправить ошибку через вопрос
- encourage: ученик расстроен или неуверен - поддержать
- hint: нужна небольшая подсказка
- tell: только если ученик совсем не понимает базу

Отвечай ТОЛЬКО валидным JSON."""

    # Паттерны для rule-based анализа
    ERROR_PATTERNS = {
        # Арифметические ошибки
        r'(\d+)\s*\+\s*(\d+)\s*=\s*(\d+)': 'careless',
        r'(\d+)\s*-\s*(\d+)\s*=\s*(\d+)': 'careless',
        r'(\d+)\s*[*×]\s*(\d+)\s*=\s*(\d+)': 'careless',

        # Типичные заблуждения
        r'\(a\s*\+\s*b\)\s*[²\^2]\s*=\s*a[²\^2]\s*\+\s*b[²\^2]': 'misconception',
        r'\\sqrt\{a\s*\+\s*b\}\s*=\s*\\sqrt\{a\}\s*\+\s*\\sqrt\{b\}': 'misconception',

        # Незаконченное решение
        r'\.{3}|…|и так далее|не знаю дальше': 'incomplete',

        # Признаки непонимания
        r'не понимаю|что это|зачем|почему так': 'conceptual',

        # Невнимательность со знаками
        r'(\+\s*=\s*-|-\s*=\s*\+)': 'careless',
    }

    CONFIDENCE_INDICATORS = {
        ConfidenceLevel.LOW: [
            r'не уверен', r'может быть', r'наверное', r'не знаю',
            r'правильно\?', r'так\?', r'\?{2,}'
        ],
        ConfidenceLevel.HIGH: [
            r'точно', r'конечно', r'очевидно', r'ясно что',
            r'всегда так', r'это просто'
        ],
        ConfidenceLevel.CONFUSED: [
            r'запутался', r'не понимаю', r'сначала думал',
            r'а может', r'или нет', r'хотя'
        ]
    }

    ENCOURAGEMENT_INDICATORS = [
        r'не получается', r'глупый', r'тупой', r'не смогу',
        r'сложно', r'трудно', r'не понимаю ничего', r'сдаюсь',
        r':(', r'😢', r'😞'
    ]

    def __init__(
        self,
        llm_client=None,
        use_llm: bool = True,
        knowledge_tracker: Optional["KnowledgeTracker"] = None,
        cognitive_load_estimator: Optional["CognitiveLoadEstimator"] = None
    ):
        """
        Инициализация профайлера.

        Args:
            llm_client: Клиент LLM для анализа (опционально)
            use_llm: Использовать LLM для анализа (иначе rule-based)
            knowledge_tracker: KnowledgeTracker для состояния знаний
            cognitive_load_estimator: CognitiveLoadEstimator для когнитивной нагрузки
        """
        self.llm = llm_client
        self.use_llm = use_llm and llm_client is not None
        self.knowledge_tracker = knowledge_tracker
        self.cognitive_load_estimator = cognitive_load_estimator

        # Session tracking
        self._consecutive_errors: Dict[str, int] = {}  # student_id -> count
        self._last_response_time: Dict[str, datetime] = {}  # student_id -> timestamp

        logger.info(
            f"ProfilerAgent инициализирован (use_llm={self.use_llm}, "
            f"knowledge_tracker={'yes' if knowledge_tracker else 'no'}, "
            f"cognitive_load={'yes' if cognitive_load_estimator else 'no'})"
        )

    def set_knowledge_tracker(self, tracker: "KnowledgeTracker"):
        """Set or update the knowledge tracker."""
        self.knowledge_tracker = tracker

    def set_cognitive_load_estimator(self, estimator: "CognitiveLoadEstimator"):
        """Set or update the cognitive load estimator."""
        self.cognitive_load_estimator = estimator

    def diagnose(
        self,
        problem: str,
        student_response: str,
        correct_approach: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        topic: Optional[str] = None,
        student_id: Optional[str] = None,
        skills: Optional[List[str]] = None,
        is_correct: Optional[bool] = None,
        response_time_ms: int = 0,
        task_difficulty: str = "medium"
    ) -> StudentProfile:
        """
        Диагностика ответа ученика с интеграцией Knowledge Tracing и Cognitive Load.

        Args:
            problem: Текст задачи
            student_response: Ответ ученика
            correct_approach: Правильный подход (опционально)
            history: История диалога
            topic: Тема задачи
            student_id: ID ученика для knowledge tracking
            skills: Навыки задействованные в задаче
            is_correct: Правильность ответа (для обновления KT)
            response_time_ms: Время ответа в миллисекундах
            task_difficulty: Сложность задачи

        Returns:
            StudentProfile с диагностикой, знаниями и когнитивной нагрузкой
        """
        # Base diagnosis
        if self.use_llm:
            profile = self._diagnose_with_llm(
                problem, student_response, correct_approach, history
            )
        else:
            profile = self._diagnose_rule_based(
                problem, student_response, topic
            )

        # Update consecutive errors tracking
        if student_id:
            if is_correct is False:
                self._consecutive_errors[student_id] = \
                    self._consecutive_errors.get(student_id, 0) + 1
            elif is_correct is True:
                self._consecutive_errors[student_id] = 0

            profile.consecutive_errors = self._consecutive_errors.get(student_id, 0)

        # Response time tracking
        profile.response_time_ms = response_time_ms

        # Knowledge Tracking integration
        if self.knowledge_tracker and student_id:
            profile = self._enhance_with_knowledge_tracking(
                profile, student_id, skills, is_correct
            )

        # Cognitive Load integration
        if self.cognitive_load_estimator:
            profile = self._enhance_with_cognitive_load(
                profile, response_time_ms, task_difficulty
            )

        # Adjust recommendations based on integrated signals
        profile = self._adjust_recommendations(profile)

        return profile

    def _enhance_with_knowledge_tracking(
        self,
        profile: StudentProfile,
        student_id: str,
        skills: Optional[List[str]],
        is_correct: Optional[bool]
    ) -> StudentProfile:
        """Enhance profile with knowledge tracking data."""
        try:
            # Update knowledge state if we have correctness info
            if skills and is_correct is not None:
                self.knowledge_tracker.record_attempt(student_id, skills, is_correct)

            # Get knowledge state summary
            kt_summary = self.knowledge_tracker.get_knowledge_state_summary(student_id)

            # Update profile with KT data
            profile.mastery_by_skill = {
                skill: data["mastery"]
                for skill, data in kt_summary.get("mastery_by_skill", {}).items()
            }
            profile.recommended_difficulty = kt_summary.get("recommended_difficulty", "medium")
            profile.using_dkt = kt_summary.get("using_dkt", False)

            # Add weak skills to topic_gaps
            weak_skills = kt_summary.get("weakest_skills", [])
            profile.topic_gaps = [skill for skill, mastery in weak_skills if mastery < 0.4]

            logger.debug(
                f"KT enhanced: using_dkt={profile.using_dkt}, "
                f"recommended_difficulty={profile.recommended_difficulty}"
            )

        except Exception as e:
            logger.warning(f"Knowledge tracking enhancement failed: {e}")

        return profile

    def _enhance_with_cognitive_load(
        self,
        profile: StudentProfile,
        response_time_ms: int,
        task_difficulty: str
    ) -> StudentProfile:
        """Enhance profile with cognitive load estimation."""
        try:
            from src.models.cognitive_load import CognitiveLoadSignals, estimate_task_complexity

            # Build signals
            signals = CognitiveLoadSignals(
                response_time_ms=response_time_ms,
                consecutive_errors=profile.consecutive_errors,
                hint_requests=0,  # Would need to track this
                task_complexity=estimate_task_complexity(task_difficulty)
            )

            # Estimate cognitive load
            cognitive_load = self.cognitive_load_estimator.estimate(signals)

            # Update profile
            profile.cognitive_load_level = cognitive_load.level.value
            profile.cognitive_load_score = cognitive_load.score
            profile.should_simplify = cognitive_load.should_simplify
            profile.should_offer_break = cognitive_load.should_offer_break

            logger.debug(
                f"Cognitive load: {profile.cognitive_load_level} "
                f"(score={profile.cognitive_load_score:.2f})"
            )

        except Exception as e:
            logger.warning(f"Cognitive load enhancement failed: {e}")

        return profile

    def _adjust_recommendations(self, profile: StudentProfile) -> StudentProfile:
        """Adjust recommendations based on integrated signals."""
        # If cognitive overload, prioritize simplification
        if profile.should_simplify:
            if profile.recommended_approach not in ["encourage", "tell"]:
                profile.recommended_approach = "scaffolding"
            profile.needs_encouragement = True

        # If should offer break, add to recommendation
        if profile.should_offer_break:
            profile.needs_encouragement = True

        # Adjust for consecutive errors
        if profile.consecutive_errors >= 3:
            profile.needs_encouragement = True
            if profile.recommended_approach == "problematize":
                # Don't challenge if already struggling
                profile.recommended_approach = "scaffolding"

        return profile

    def _diagnose_with_llm(
        self,
        problem: str,
        student_response: str,
        correct_approach: Optional[str],
        history: Optional[List[Dict[str, str]]]
    ) -> StudentProfile:
        """Диагностика с использованием LLM."""
        # Форматируем историю
        history_str = ""
        if history:
            history_str = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in history[-6:]  # Последние 6 сообщений
            ])

        prompt = self.PROFILER_PROMPT.format(
            problem=problem,
            correct_approach=correct_approach or "Не указан",
            student_response=student_response,
            history=history_str or "Нет истории"
        )

        try:
            response = self.llm.generate(
                prompt=prompt,
                temperature=0.3,  # Низкая для точности
                max_tokens=1000
            )

            # Парсим JSON
            data = self._parse_json_response(response)
            return self._create_profile_from_dict(data)

        except Exception as e:
            logger.warning(f"Ошибка LLM диагностики: {e}. Fallback на rule-based.")
            return self._diagnose_rule_based(problem, student_response, None)

    def _diagnose_rule_based(
        self,
        problem: str,
        student_response: str,
        topic: Optional[str]
    ) -> StudentProfile:
        """Rule-based диагностика без LLM."""
        errors = []
        misconceptions = []
        strengths = []

        response_lower = student_response.lower()

        # Проверяем паттерны ошибок
        for pattern, error_type in self.ERROR_PATTERNS.items():
            try:
                if re.search(pattern, student_response, re.IGNORECASE):
                    errors.append(StudentError(
                        error_type=ErrorType(error_type),
                        description=f"Обнаружен паттерн: {error_type}",
                        severity=0.6 if error_type == 'misconception' else 0.4
                    ))
            except re.error:
                pass  # Skip invalid regex matches (e.g., unbalanced parentheses in input)

        # Определяем уровень уверенности
        confidence = self._detect_confidence(response_lower)

        # Проверяем, нужна ли поддержка
        def safe_search(pattern, text):
            try:
                return re.search(pattern, text)
            except re.error:
                return None
        needs_encouragement = any(
            safe_search(p, response_lower)
            for p in self.ENCOURAGEMENT_INDICATORS
        )

        # Определяем рекомендуемый подход
        if needs_encouragement:
            recommended = "encourage"
        elif any(e.error_type == ErrorType.MISCONCEPTION for e in errors):
            recommended = "problematize"
        elif any(e.error_type == ErrorType.CONCEPTUAL for e in errors):
            recommended = "scaffolding"
        elif any(e.error_type == ErrorType.INCOMPLETE for e in errors):
            recommended = "hint"
        else:
            recommended = "scaffolding"

        # Оценка понимания
        understanding = self._estimate_understanding(errors, student_response)

        # Если ответ содержит правильные элементы
        if any(word in response_lower for word in ['уравнение', 'решение', 'найти', 'подставить']):
            strengths.append("Понимает структуру задачи")

        return StudentProfile(
            errors=errors,
            misconceptions=misconceptions,
            strengths=strengths,
            recommended_approach=recommended,
            confidence_level=confidence,
            understanding_score=understanding,
            needs_encouragement=needs_encouragement,
            topic_gaps=[]
        )

    def _detect_confidence(self, response: str) -> ConfidenceLevel:
        """Определение уровня уверенности по ответу."""
        for level, patterns in self.CONFIDENCE_INDICATORS.items():
            if any(re.search(p, response) for p in patterns):
                return level
        return ConfidenceLevel.MEDIUM

    def _estimate_understanding(
        self,
        errors: List[StudentError],
        response: str
    ) -> float:
        """Оценка уровня понимания."""
        if not errors:
            return 0.7  # Нет явных ошибок

        # Считаем средневзвешенную серьёзность ошибок
        if errors:
            avg_severity = sum(e.severity for e in errors) / len(errors)
            return max(0.1, 1.0 - avg_severity)

        return 0.5

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Парсинг JSON из ответа LLM."""
        # Удаляем markdown
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        response = response.strip()

        # Ищем JSON объект
        start = response.find('{')
        end = response.rfind('}')
        if start != -1 and end != -1:
            response = response[start:end+1]

        # Удаляем trailing commas
        response = re.sub(r',(\s*[}\]])', r'\1', response)

        return json.loads(response)

    def _create_profile_from_dict(self, data: Dict[str, Any]) -> StudentProfile:
        """Создание профиля из словаря."""
        errors = []
        for e in data.get("errors", []):
            try:
                errors.append(StudentError(
                    error_type=ErrorType(e.get("type", "unknown")),
                    description=e.get("description", ""),
                    location=e.get("location", ""),
                    severity=float(e.get("severity", 0.5)),
                    suggested_move=e.get("suggested_move", "hint"),
                    suggested_hint=e.get("suggested_hint", "")
                ))
            except (ValueError, KeyError) as ex:
                logger.warning(f"Ошибка парсинга ошибки: {ex}")

        try:
            confidence = ConfidenceLevel(data.get("confidence_level", "medium"))
        except ValueError:
            confidence = ConfidenceLevel.MEDIUM

        return StudentProfile(
            errors=errors,
            misconceptions=data.get("misconceptions", []),
            strengths=data.get("strengths", []),
            recommended_approach=data.get("recommended_approach", "scaffolding"),
            confidence_level=confidence,
            understanding_score=float(data.get("understanding_score", 0.5)),
            needs_encouragement=bool(data.get("needs_encouragement", False)),
            topic_gaps=data.get("topic_gaps", [])
        )

    def get_suggested_response(self, profile: StudentProfile) -> Dict[str, str]:
        """
        Получение рекомендации для ответа на основе профиля.

        Args:
            profile: Профиль ученика

        Returns:
            Словарь с рекомендуемым ходом и шаблоном
        """
        templates = {
            "scaffolding": "Давай разберём это шаг за шагом. Начнём с...",
            "problematize": "Интересно... А что получится, если...",
            "rectify": "Хорошая попытка! А давай проверим: если...",
            "encourage": "Ты на правильном пути! Уже видно, что понимаешь...",
            "hint": "Подсказка: обрати внимание на...",
            "tell": "Давай я объясню эту концепцию..."
        }

        move = profile.recommended_approach
        template = templates.get(move, templates["scaffolding"])

        # Добавляем конкретную подсказку если есть
        if profile.errors and profile.errors[0].suggested_hint:
            specific_hint = profile.errors[0].suggested_hint
        else:
            specific_hint = ""

        return {
            "move": move,
            "template": template,
            "specific_hint": specific_hint,
            "needs_encouragement": profile.needs_encouragement
        }


# Пример использования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== Profiler Agent Demo ===\n")

    # Rule-based режим (без LLM)
    profiler = ProfilerAgent(use_llm=False)

    # Тест 1: Запутавшийся ученик
    profile = profiler.diagnose(
        problem="Решить уравнение x + 5 = 10",
        student_response="Не знаю как начать, наверное x = 15? Не уверен..."
    )

    print("Тест 1: Неуверенный ученик")
    print(f"  Уверенность: {profile.confidence_level.value}")
    print(f"  Рекомендуемый ход: {profile.recommended_approach}")
    print(f"  Нужна поддержка: {profile.needs_encouragement}")

    # Тест 2: Типичное заблуждение
    profile = profiler.diagnose(
        problem="Раскрыть скобки: (a + b)²",
        student_response="(a + b)² = a² + b², это же очевидно!"
    )

    print("\nТест 2: Заблуждение")
    print(f"  Ошибки: {[e.error_type.value for e in profile.errors]}")
    print(f"  Уверенность: {profile.confidence_level.value}")
    print(f"  Рекомендуемый ход: {profile.recommended_approach}")

    # Тест 3: Расстроенный ученик
    profile = profiler.diagnose(
        problem="Найти производную f(x) = x³",
        student_response="Я ничего не понимаю, это слишком сложно :( Сдаюсь"
    )

    print("\nТест 3: Расстроенный ученик")
    print(f"  Нужна поддержка: {profile.needs_encouragement}")
    print(f"  Рекомендуемый ход: {profile.recommended_approach}")

    # Рекомендация для ответа
    suggestion = profiler.get_suggested_response(profile)
    print(f"  Шаблон ответа: {suggestion['template']}")
