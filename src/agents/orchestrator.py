#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Оркестратор агентов MITS.

Координирует работу всех агентов системы:
- Профайлер → Диагностика ошибок + знания + когнитивная нагрузка
- Планировщик → Выбор стратегии
- Репетитор → Генерация ответа
- Верификатор → Контроль качества

Основан на паттерне GenMentor (WWW 2025).

Улучшения T037-T039:
- Intelligent query routing based on query type
- Full pipeline tracing for debugging
- Graceful degradation when agents fail
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.agents.planner import (
    PlannerAgent,
    TeachingMove,
    TeachingPlan,
    TeachingStrategy,
)
from src.agents.planner import (
    SessionContext as PlannerSessionContext,
)
from src.agents.profiler import ProfilerAgent, StudentProfile
from src.agents.verifier import VerificationResult, VerifierAgent

# Import base agent types
try:
    from src.agents.base_agent import AgentError, AgentStatus, HealthCheckResult

    HAS_BASE_AGENT = True
except ImportError:
    HAS_BASE_AGENT = False
    AgentStatus = None
    AgentError = Exception
    HealthCheckResult = None

# Опциональный RAG
try:
    from src.knowledge.rag_retriever import TutoringContext, TutoringRAG

    HAS_RAG = True
except ImportError:
    HAS_RAG = False
    TutoringRAG = None
    TutoringContext = None

# Опциональный Knowledge Tracker
try:
    from src.models.knowledge_tracing import KnowledgeTracker

    HAS_KT = True
except ImportError:
    HAS_KT = False
    KnowledgeTracker = None

# Опциональный Cognitive Load Estimator
try:
    from src.models.cognitive_load import CognitiveLoadEstimator

    HAS_CL = True
except ImportError:
    HAS_CL = False
    CognitiveLoadEstimator = None

logger = logging.getLogger(__name__)


class OrchestratorMode(Enum):
    """Режимы работы оркестратора."""

    FULL = "full"  # Все агенты
    FAST = "fast"  # Только репетитор + верификатор
    DIAGNOSTIC = "diagnostic"  # Профайлер + планировщик (без ответа)


class QueryType(Enum):
    """Тип запроса ученика для интеллектуальной маршрутизации (T037)."""

    QUESTION = "question"  # Вопрос о задаче
    ANSWER_ATTEMPT = "answer_attempt"  # Попытка ответа
    HINT_REQUEST = "hint_request"  # Запрос подсказки
    CONFUSION = "confusion"  # Выражение непонимания
    OFF_TOPIC = "off_topic"  # Не по теме
    GREETING = "greeting"  # Приветствие
    CLARIFICATION = "clarification"  # Уточнение
    SOLUTION_CHECK = "solution_check"  # Проверка решения
    NEXT_TASK = "next_task"  # Запрос следующей задачи


class AgentStage(Enum):
    """Стадии пайплайна агентов."""

    ROUTING = "routing"
    PROFILER = "profiler"
    MENTAL_MODEL = "mental_model"  # ToM-Tutor (017) — между PROFILER и PLANNER
    PLANNER = "planner"
    RAG = "rag"
    TUTOR = "tutor"
    VERIFIER = "verifier"
    FALLBACK = "fallback"


@dataclass
class StageTrace:
    """Трейс одной стадии пайплайна."""

    stage: AgentStage
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    success: bool = False
    error: Optional[str] = None
    output_summary: Optional[str] = None

    def complete(
        self, success: bool, error: Optional[str] = None, output_summary: Optional[str] = None
    ):
        """Mark stage as complete."""
        self.completed_at = datetime.now()
        self.duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000
        self.success = success
        self.error = error
        self.output_summary = output_summary


@dataclass
class PipelineTrace:
    """Трейс выполнения пайплайна агентов (T038)."""

    trace_id: str
    session_id: Optional[str] = None
    student_id: Optional[str] = None
    query_type: Optional[QueryType] = None
    mode: OrchestratorMode = OrchestratorMode.FULL
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    total_duration_ms: float = 0.0
    stages: List[StageTrace] = field(default_factory=list)
    agents_called: List[str] = field(default_factory=list)
    retries: int = 0
    final_success: bool = False
    final_error: Optional[str] = None

    def start_stage(self, stage: AgentStage) -> StageTrace:
        """Start tracing a new stage."""
        trace = StageTrace(stage=stage)
        self.stages.append(trace)
        self.agents_called.append(stage.value)
        return trace

    def complete(self, success: bool, error: Optional[str] = None):
        """Mark pipeline as complete."""
        self.completed_at = datetime.now()
        self.total_duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000
        self.final_success = success
        self.final_error = error

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "query_type": self.query_type.value if self.query_type else None,
            "mode": self.mode.value,
            "total_duration_ms": self.total_duration_ms,
            "agents_called": self.agents_called,
            "retries": self.retries,
            "final_success": self.final_success,
            "final_error": self.final_error,
            "stages": [
                {
                    "stage": s.stage.value,
                    "duration_ms": s.duration_ms,
                    "success": s.success,
                    "error": s.error,
                    "output_summary": s.output_summary,
                }
                for s in self.stages
            ],
        }

    def summary(self) -> str:
        """Human-readable summary."""
        status = "✓" if self.final_success else "✗"
        stages_str = " → ".join(
            [f"{s.stage.value}({'✓' if s.success else '✗'})" for s in self.stages]
        )
        return f"[{status}] {self.total_duration_ms:.0f}ms | {stages_str}"


@dataclass
class TurnContext:
    """Контекст одного хода диалога."""

    problem: str  # Текст задачи
    student_input: str  # Ввод ученика
    correct_answer: Optional[str] = None  # Правильный ответ
    history: List[Dict[str, str]] = field(default_factory=list)  # История диалога
    student_id: Optional[str] = None  # ID ученика
    topic: Optional[str] = None  # Тема задачи


@dataclass
class TopicMasteryVisualization:
    """Данные для визуализации освоения топиков."""

    skill_name: str
    mastery: float  # 0-1
    dkt_mastery: Optional[float] = None  # DKT prediction
    attempts: int = 0
    success_rate: float = 0.0
    trend: str = "stable"  # "improving", "declining", "stable"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "mastery": self.mastery,
            "dkt_mastery": self.dkt_mastery,
            "attempts": self.attempts,
            "success_rate": self.success_rate,
            "trend": self.trend,
        }


@dataclass
class KnowledgeStateData:
    """Данные о состоянии знаний для UI."""

    total_interactions: int = 0
    using_dkt: bool = False
    mastery_visualization: List[TopicMasteryVisualization] = field(default_factory=list)
    weakest_skills: List[tuple] = field(default_factory=list)
    strongest_skills: List[tuple] = field(default_factory=list)
    recommended_skill: Optional[str] = None
    recommended_difficulty: str = "medium"
    cognitive_load_level: str = "optimal"
    cognitive_load_score: float = 0.5
    should_simplify: bool = False
    should_offer_break: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_interactions": self.total_interactions,
            "using_dkt": self.using_dkt,
            "mastery_visualization": [m.to_dict() for m in self.mastery_visualization],
            "weakest_skills": self.weakest_skills,
            "strongest_skills": self.strongest_skills,
            "recommended_skill": self.recommended_skill,
            "recommended_difficulty": self.recommended_difficulty,
            "cognitive_load": {
                "level": self.cognitive_load_level,
                "score": self.cognitive_load_score,
                "should_simplify": self.should_simplify,
                "should_offer_break": self.should_offer_break,
            },
        }


@dataclass
class TurnResult:
    """Результат обработки хода."""

    response: str  # Ответ репетитора
    move_type: str  # Тип хода
    profile: Optional[StudentProfile] = None  # Профиль ученика
    plan: Optional[TeachingPlan] = None  # План обучения
    verification: Optional[VerificationResult] = None  # Результат верификации
    rag_context: Optional[Any] = None  # RAG контекст (TutoringContext)
    metrics: Dict[str, Any] = field(default_factory=dict)  # Метрики
    knowledge_state: Optional[KnowledgeStateData] = None  # Состояние знаний для UI
    pipeline_trace: Optional[PipelineTrace] = None  # Трейс пайплайна (T038)
    query_type: Optional[QueryType] = None  # Тип запроса (T037)

    def to_json(self) -> str:
        """Сериализация в JSON."""
        return json.dumps({"move": self.move_type, "message": self.response}, ensure_ascii=False)

    def to_full_dict(self) -> Dict[str, Any]:
        """Полная сериализация для API."""
        result = {"move": self.move_type, "message": self.response, "metrics": self.metrics}

        if self.query_type:
            result["query_type"] = self.query_type.value

        if self.knowledge_state:
            result["knowledge_state"] = self.knowledge_state.to_dict()

        if self.profile:
            result["profile"] = self.profile.to_dict()

        if self.pipeline_trace:
            result["pipeline_trace"] = self.pipeline_trace.to_dict()

        return result


@dataclass
class SessionState:
    """Состояние сессии обучения."""

    session_id: str
    student_id: Optional[str] = None
    current_problem: Optional[str] = None
    current_topic: Optional[str] = None
    turn_count: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)
    profiles: List[StudentProfile] = field(default_factory=list)
    total_latency_ms: float = 0.0

    def add_turn(self, context: TurnContext, result: TurnResult):
        """Добавление хода в историю."""
        self.turn_count += 1
        self.history.append(
            {
                "turn": self.turn_count,
                "student_input": context.student_input,
                "tutor_response": result.response,
                "move_type": result.move_type,
                "timestamp": time.time(),
            }
        )
        if result.profile:
            self.profiles.append(result.profile)


class AgentOrchestrator:
    """
    Центральный координатор агентов MITS.

    Реализует паттерн GenMentor:
    1. Профайлер диагностирует ошибки ученика
    2. Планировщик выбирает стратегию обучения
    3. Репетитор генерирует ответ
    4. Верификатор проверяет качество

    Особенности:
    - Конфигурируемые режимы работы
    - Метрики производительности
    - Кэширование результатов агентов
    - Graceful degradation при ошибках
    """

    def __init__(
        self,
        llm_client,
        profiler: Optional[ProfilerAgent] = None,
        planner: Optional[PlannerAgent] = None,
        verifier: Optional[VerifierAgent] = None,
        rag: Optional["TutoringRAG"] = None,
        knowledge_tracker: Optional["KnowledgeTracker"] = None,
        cognitive_load_estimator: Optional["CognitiveLoadEstimator"] = None,
        memory_manager: Optional[Any] = None,  # T045: MemoryManager integration
        mode: OrchestratorMode = OrchestratorMode.FULL,
        max_retries: int = 2,
        verify_responses: bool = True,
        use_rag: bool = True,
        use_knowledge_tracking: bool = True,
        use_memory_manager: bool = True,
    ):
        """
        Инициализация оркестратора.

        Args:
            llm_client: Клиент LLM для генерации ответов
            profiler: Агент профайлера (создаётся автоматически если None)
            planner: Агент планировщика (создаётся автоматически если None)
            verifier: Агент верификатора (создаётся автоматически если None)
            rag: RAG система для контекста (создаётся автоматически если None)
            knowledge_tracker: KnowledgeTracker для отслеживания знаний
            cognitive_load_estimator: Оценщик когнитивной нагрузки
            memory_manager: MemoryManager для персистентного контекста (T045)
            mode: Режим работы оркестратора
            max_retries: Максимум повторов при невалидном ответе
            verify_responses: Верифицировать ответы
            use_rag: Использовать RAG для контекста
            use_knowledge_tracking: Использовать Knowledge Tracking
            use_memory_manager: Использовать MemoryManager
        """
        self.llm = llm_client
        self.mode = mode
        self.max_retries = max_retries
        self.verify_responses = verify_responses
        self.use_rag = use_rag and HAS_RAG
        self.use_knowledge_tracking = use_knowledge_tracking and HAS_KT

        # Инициализация Knowledge Tracker
        self.knowledge_tracker = knowledge_tracker
        if self.use_knowledge_tracking and not self.knowledge_tracker:
            try:
                self.knowledge_tracker = KnowledgeTracker()
                logger.info("KnowledgeTracker инициализирован")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать KnowledgeTracker: {e}")
                self.use_knowledge_tracking = False

        # Инициализация Cognitive Load Estimator
        self.cognitive_load_estimator = cognitive_load_estimator
        if HAS_CL and not self.cognitive_load_estimator:
            try:
                self.cognitive_load_estimator = CognitiveLoadEstimator()
                logger.info("CognitiveLoadEstimator инициализирован")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать CognitiveLoadEstimator: {e}")

        # Инициализация агентов
        self.profiler = profiler or ProfilerAgent(
            llm_client,
            knowledge_tracker=self.knowledge_tracker,
            cognitive_load_estimator=self.cognitive_load_estimator,
        )
        self.planner = planner or PlannerAgent()
        self.verifier = verifier or VerifierAgent()

        # ToM-Tutor (017): MentalModelAgent if enabled in profile.
        # Использует отдельный base-model LLMClient (qwen3.5:9b), т.к.
        # thinking-модели конфликтуют с JSON mode.
        self.mental_model_agent = None
        try:
            from src.resource_profiles import feature_enabled

            if feature_enabled("enable_tom_agent"):
                from src.agents.mental_model_agent import MentalModelAgent
                from src.models.llm_client import LLMClient as _LLMClient

                tom_llm = _LLMClient(model="qwen3.5:9b")
                forge_graph = None
                try:
                    from pathlib import Path

                    from src.knowledge.knowledge_forge import KnowledgeGraph

                    forge_path = Path("data/knowledge/forge.json")
                    if forge_path.exists():
                        forge_graph = KnowledgeGraph(forge_path)
                except Exception:
                    pass
                self.mental_model_agent = MentalModelAgent(
                    llm_client=tom_llm, knowledge_graph=forge_graph
                )
                logger.info("MentalModelAgent инициализирован (ToM-Tutor 017)")
        except Exception as e:
            logger.warning(f"MentalModelAgent не доступен (graceful): {e}")

        # Инициализация RAG
        self.rag = None
        if self.use_rag:
            try:
                self.rag = rag or TutoringRAG()
                logger.info("RAG система инициализирована")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать RAG: {e}")
                self.use_rag = False

        # T045: Инициализация Memory Manager
        self.memory_manager = None
        self.use_memory_manager = use_memory_manager
        if use_memory_manager:
            try:
                if memory_manager:
                    self.memory_manager = memory_manager
                else:
                    from src.memory.manager import create_memory_manager

                    self.memory_manager = create_memory_manager()
                logger.info("MemoryManager инициализирован")
            except ImportError:
                logger.warning("MemoryManager не доступен (модуль не найден)")
                self.use_memory_manager = False
            except Exception as e:
                logger.warning(f"Не удалось инициализировать MemoryManager: {e}")
                self.use_memory_manager = False

        # Активные сессии
        self._sessions: Dict[str, SessionState] = {}

        # Callbacks для расширения
        self._pre_hooks: List[Callable] = []
        self._post_hooks: List[Callable] = []

        # Pipeline tracing (T038)
        self._trace_counter = 0
        self._pipeline_traces: List[PipelineTrace] = []
        self._max_trace_history = 100

        # Agent health tracking (T040)
        self._agent_health: Dict[str, HealthCheckResult] = {}

        # Query patterns for classification (T037)
        self._query_patterns = {
            QueryType.HINT_REQUEST: [
                r"подсказ",
                r"помог",
                r"не понимаю",
                r"hint",
                r"help",
                r"как.*начать",
                r"не знаю",
                r"затрудн",
            ],
            QueryType.GREETING: [r"^привет", r"^здравств", r"^добр", r"^hi\b", r"^hello"],
            QueryType.NEXT_TASK: [
                r"следующ.*задач",
                r"новую задач",
                r"другую задач",
                r"next.*task",
                r"ещё.*задач",
            ],
            QueryType.CONFUSION: [
                r"не понял",
                r"не понимаю",
                r"запутал",
                r"сложно",
                r"confused",
                r"don\'t understand",
            ],
            QueryType.SOLUTION_CHECK: [
                r"правильно\?",
                r"верно\?",
                r"так\?$",
                r"check",
                r"проверь",
                r"это.*ответ",
            ],
            QueryType.CLARIFICATION: [
                r"что.*значит",
                r"почему",
                r"зачем",
                r"как это",
                r"what.*mean",
                r"why",
                r"объясни",
            ],
        }

        logger.info(
            "AgentOrchestrator инициализирован",
            extra={
                "mode": mode.value,
                "verify": verify_responses,
                "rag": self.use_rag,
                "kt": self.use_knowledge_tracking,
            },
        )

    def create_session(
        self,
        session_id: str,
        student_id: Optional[str] = None,
        problem: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> SessionState:
        """
        Создание новой сессии обучения.

        Args:
            session_id: Уникальный ID сессии
            student_id: ID ученика
            problem: Начальная задача
            topic: Тема

        Returns:
            SessionState новой сессии
        """
        session = SessionState(
            session_id=session_id,
            student_id=student_id,
            current_problem=problem,
            current_topic=topic,
        )
        self._sessions[session_id] = session

        logger.info("Сессия создана", extra={"session_id": session_id})

        return session

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Получение сессии по ID."""
        return self._sessions.get(session_id)

    # === T037: Query Classification and Routing ===

    def _classify_query(self, student_input: str) -> QueryType:
        """
        Классификация запроса ученика для умной маршрутизации (T037).

        Args:
            student_input: Текст ввода ученика

        Returns:
            QueryType определяющий тип запроса
        """
        input_lower = student_input.lower().strip()

        # Check patterns
        for query_type, patterns in self._query_patterns.items():
            for pattern in patterns:
                if re.search(pattern, input_lower, re.IGNORECASE):
                    logger.debug(
                        f"Query classified as {query_type.value}", extra={"pattern": pattern}
                    )
                    return query_type

        # Check if it looks like a math expression/answer
        if re.search(r"[=\+\-\*/\^]|x\s*=|^\d+$|\d+[,\.]\d+", input_lower):
            return QueryType.ANSWER_ATTEMPT

        # Check if it's a question
        if "?" in student_input or input_lower.startswith(("как", "что", "где", "когда", "почему")):
            return QueryType.QUESTION

        # Default to answer attempt
        return QueryType.ANSWER_ATTEMPT

    def _get_routing_config(self, query_type: QueryType) -> Dict[str, Any]:
        """
        Получить конфигурацию маршрутизации для типа запроса (T037).

        Args:
            query_type: Тип запроса

        Returns:
            Словарь с флагами какие агенты запускать
        """
        routing_configs = {
            QueryType.HINT_REQUEST: {
                "use_profiler": True,
                "use_planner": True,
                "use_rag": True,  # Важно для подсказок
                "use_verifier": True,
                "suggested_move": "hint",
                "priority_rag": True,
            },
            QueryType.ANSWER_ATTEMPT: {
                "use_profiler": True,  # Диагностика ошибок
                "use_planner": True,
                "use_rag": True,
                "use_verifier": True,
                "suggested_move": None,  # Определяется профайлером
            },
            QueryType.CONFUSION: {
                "use_profiler": True,
                "use_planner": True,
                "use_rag": True,  # Поиск более простых объяснений
                "use_verifier": True,
                "suggested_move": "scaffolding",
                "simplify_response": True,
            },
            QueryType.GREETING: {
                "use_profiler": False,
                "use_planner": False,
                "use_rag": False,
                "use_verifier": False,
                "suggested_move": "encourage",
                "fast_response": True,
            },
            QueryType.NEXT_TASK: {
                "use_profiler": False,
                "use_planner": True,  # Для выбора сложности
                "use_rag": False,
                "use_verifier": False,
                "suggested_move": "tell",
                "generate_task": True,
            },
            QueryType.SOLUTION_CHECK: {
                "use_profiler": True,  # Проверка правильности
                "use_planner": True,
                "use_rag": False,
                "use_verifier": True,
                "suggested_move": None,
            },
            QueryType.CLARIFICATION: {
                "use_profiler": False,
                "use_planner": True,
                "use_rag": True,  # Поиск объяснений
                "use_verifier": True,
                "suggested_move": "clarify",
            },
            QueryType.QUESTION: {
                "use_profiler": False,
                "use_planner": True,
                "use_rag": True,
                "use_verifier": True,
                "suggested_move": "scaffolding",
            },
            QueryType.OFF_TOPIC: {
                "use_profiler": False,
                "use_planner": False,
                "use_rag": False,
                "use_verifier": False,
                "suggested_move": "clarify",
                "redirect_to_task": True,
            },
        }

        return routing_configs.get(query_type, routing_configs[QueryType.ANSWER_ATTEMPT])

    # === T038: Pipeline Tracing ===

    def _create_trace(self, session_id: Optional[str] = None) -> PipelineTrace:
        """Создать новый трейс пайплайна."""
        self._trace_counter += 1
        trace = PipelineTrace(
            trace_id=f"trace-{self._trace_counter}", session_id=session_id, mode=self.mode
        )

        # Maintain history limit
        self._pipeline_traces.append(trace)
        if len(self._pipeline_traces) > self._max_trace_history:
            self._pipeline_traces.pop(0)

        return trace

    def get_recent_traces(self, n: int = 10) -> List[PipelineTrace]:
        """Получить последние N трейсов для отладки."""
        return self._pipeline_traces[-n:]

    # === T039: Graceful Degradation ===

    def _handle_agent_failure(
        self, agent_name: str, error: Exception, trace: PipelineTrace, context: TurnContext
    ) -> Optional[Any]:
        """
        Обработка сбоя агента с graceful degradation (T039).

        Args:
            agent_name: Имя упавшего агента
            error: Исключение
            trace: Текущий трейс
            context: Контекст хода

        Returns:
            Fallback результат или None
        """
        logger.warning(
            f"Agent {agent_name} failed, attempting graceful degradation",
            extra={"error": str(error)},
        )

        # Record failure
        trace.retries += 1

        # Fallback strategies by agent
        fallback_strategies = {
            "profiler": self._fallback_profiler,
            "planner": self._fallback_planner,
            "rag": self._fallback_rag,
            "tutor": self._fallback_tutor,
            "verifier": self._fallback_verifier,
        }

        fallback_fn = fallback_strategies.get(agent_name)
        if fallback_fn:
            try:
                return fallback_fn(context, error)
            except Exception as fallback_error:
                logger.error(
                    f"Fallback for {agent_name} also failed", extra={"error": str(fallback_error)}
                )

        return None

    def _fallback_profiler(self, context: TurnContext, error: Exception) -> StudentProfile:
        """Fallback профайлера - минимальный профиль."""
        return StudentProfile(
            errors=[],
            misconceptions=[],
            strengths=[],
            recommended_approach="scaffolding",
            confidence_level=0.5,
        )

    def _fallback_planner(self, context: TurnContext, error: Exception) -> TeachingPlan:
        """Fallback планировщика - базовая стратегия."""
        return TeachingPlan(
            strategy=TeachingStrategy.SCAFFOLDED,
            primary_move=TeachingMove.SCAFFOLDING,
            move_sequence=[TeachingMove.SCAFFOLDING, TeachingMove.HINT],
            tone="supportive",
        )

    def _fallback_rag(self, context: TurnContext, error: Exception) -> Optional[Any]:
        """Fallback RAG - без контекста."""
        logger.info("RAG fallback: proceeding without RAG context")
        return None

    def _fallback_tutor(self, context: TurnContext, error: Exception) -> str:
        """Fallback репетитора - универсальный ответ."""
        fallback_messages = [
            "Давай попробуем разобраться вместе. Расскажи, что тебе уже понятно в этой задаче?",
            "Интересная мысль! Можешь объяснить свои рассуждения подробнее?",
            "Хороший вопрос. Давай начнём с самого начала — какие данные нам даны?",
        ]
        import random

        message = random.choice(fallback_messages)
        return json.dumps({"move": "scaffolding", "message": message}, ensure_ascii=False)

    def _fallback_verifier(self, context: TurnContext, error: Exception) -> VerificationResult:
        """Fallback верификатора - пропускаем проверку."""
        logger.info("Verifier fallback: skipping verification")
        return VerificationResult(
            is_valid=True,  # Assume valid
            critical_issues=[],
            warnings=[{"issue": "verification_skipped", "reason": str(error)}],
            quality_score=0.7,
        )

    # === T040: Agent Health Check ===

    def check_agents_health(self) -> Dict[str, Any]:
        """
        Проверка здоровья всех агентов (T040).

        Returns:
            Словарь со статусами агентов
        """
        health_status = {}

        # Check profiler
        if hasattr(self.profiler, "health_check"):
            health_status["profiler"] = self.profiler.health_check()
        else:
            health_status["profiler"] = {"status": "unknown", "has_health_check": False}

        # Check planner
        if hasattr(self.planner, "health_check"):
            health_status["planner"] = self.planner.health_check()
        else:
            health_status["planner"] = {"status": "unknown", "has_health_check": False}

        # Check verifier
        if hasattr(self.verifier, "health_check"):
            health_status["verifier"] = self.verifier.health_check()
        else:
            health_status["verifier"] = {"status": "unknown", "has_health_check": False}

        # Check RAG
        if self.rag:
            try:
                # Simple RAG health check
                health_status["rag"] = {"status": "healthy", "available": True}
            except Exception as e:
                health_status["rag"] = {"status": "unhealthy", "error": str(e)}
        else:
            health_status["rag"] = {"status": "disabled", "available": False}

        # Check LLM
        try:
            # Quick LLM ping
            if hasattr(self.llm, "ping") and callable(self.llm.ping):
                self.llm.ping()
                health_status["llm"] = {"status": "healthy"}
            else:
                health_status["llm"] = {"status": "unknown", "has_ping": False}
        except Exception as e:
            health_status["llm"] = {"status": "unhealthy", "error": str(e)}

        # Overall status
        unhealthy_count = sum(
            1
            for s in health_status.values()
            if isinstance(s, dict) and s.get("status") == "unhealthy"
        )

        health_status["overall"] = {
            "status": "degraded" if unhealthy_count > 0 else "healthy",
            "unhealthy_agents": unhealthy_count,
            "timestamp": datetime.now().isoformat(),
        }

        self._agent_health = health_status
        return health_status

    def is_operational(self) -> bool:
        """Проверка, работоспособен ли оркестратор."""
        health = self.check_agents_health()
        # Operational if LLM works (core requirement)
        llm_status = health.get("llm", {}).get("status", "unknown")
        return llm_status != "unhealthy"

    def process_turn(self, context: TurnContext, session_id: Optional[str] = None) -> TurnResult:
        """
        Обработка одного хода диалога.

        Основной метод оркестратора. Координирует работу всех агентов.
        Включает интеллектуальную маршрутизацию (T037), трейсинг (T038),
        и graceful degradation (T039).

        Args:
            context: Контекст хода (задача, ввод ученика, история)
            session_id: ID сессии (опционально)

        Returns:
            TurnResult с ответом и метаданными
        """
        start_time = time.time()
        metrics: Dict[str, Any] = {}

        # T038: Create pipeline trace
        trace = self._create_trace(session_id)
        trace.student_id = context.student_id

        # Получаем сессию
        session = self._sessions.get(session_id) if session_id else None

        # Выполняем pre-hooks
        for hook in self._pre_hooks:
            try:
                hook(context, session)
            except Exception as e:
                logger.warning(f"Pre-hook ошибка: {e}")

        # T037: Classify query and get routing config
        routing_stage = trace.start_stage(AgentStage.ROUTING)
        try:
            query_type = self._classify_query(context.student_input)
            routing_config = self._get_routing_config(query_type)
            trace.query_type = query_type
            metrics["query_type"] = query_type.value
            routing_stage.complete(True, output_summary=f"Classified as {query_type.value}")
            logger.debug(f"Query classified: {query_type.value}")
        except Exception as e:
            query_type = QueryType.ANSWER_ATTEMPT
            routing_config = self._get_routing_config(query_type)
            routing_stage.complete(False, error=str(e))

        # Handle fast response for simple queries (e.g., greeting)
        if routing_config.get("fast_response"):
            fast_response = self._generate_fast_response(context, query_type)
            trace.complete(True)
            return TurnResult(
                response=fast_response,
                move_type="encourage",
                metrics={"fast_path": True, "query_type": query_type.value},
                pipeline_trace=trace,
                query_type=query_type,
            )

        # 1. ПРОФАЙЛЕР: Диагностика ошибок
        profile = None
        should_profile = self.mode in [
            OrchestratorMode.FULL,
            OrchestratorMode.DIAGNOSTIC,
        ] and routing_config.get("use_profiler", True)

        if should_profile:
            profiler_stage = trace.start_stage(AgentStage.PROFILER)
            profile_start = time.time()
            try:
                profile = self.profiler.diagnose(
                    problem=context.problem,
                    correct_approach=context.correct_answer or "",
                    student_response=context.student_input,
                    history=context.history,
                )
                metrics["profiler_ms"] = (time.time() - profile_start) * 1000
                profiler_stage.complete(
                    True,
                    output_summary=f"{len(profile.errors)} errors, confidence={profile.confidence_level.value}",
                )
                logger.debug(
                    "Профайлер: диагностика завершена",
                    extra={"errors": len(profile.errors), "confidence": profile.confidence_level},
                )
            except Exception as e:
                logger.error(f"Ошибка профайлера: {e}")
                profiler_stage.complete(False, error=str(e))
                # T039: Graceful degradation
                profile = self._handle_agent_failure("profiler", e, trace, context)

        # 1.5. MENTAL_MODEL: ToM-Tutor inference (017)
        # Между PROFILER и PLANNER: выводим BeliefState для stratification.
        # Graceful degradation: при любой ошибке — empty BeliefState.
        belief_state = None
        try:
            from src.data.schemas import BeliefState as _BeliefState
            from src.resource_profiles import feature_enabled

            if (
                feature_enabled("enable_tom_agent")
                and getattr(self, "mental_model_agent", None) is not None
                and profile is not None
            ):
                mm_stage = trace.start_stage(AgentStage.MENTAL_MODEL)
                mm_start = time.time()
                try:
                    belief_state = self.mental_model_agent.infer(
                        student_message=context.student_input,
                        student_profile=profile,
                        history=(
                            session.recent_turns(3)
                            if session and hasattr(session, "recent_turns")
                            else []
                        ),
                        graph_context=graph_context,
                        topic=context.topic or "",
                    )
                    metrics["mental_model_ms"] = (time.time() - mm_start) * 1000
                    mm_stage.complete(
                        True,
                        output_summary=(
                            f"confidence={belief_state.confidence:.2f}, "
                            f"misconception={'yes' if belief_state.active_misconception else 'no'}"
                        ),
                    )
                except Exception as e:
                    logger.warning(f"MENTAL_MODEL stage failed (graceful): {e}")
                    mm_stage.complete(False, error=str(e))
                    belief_state = _BeliefState.empty()
        except ImportError:
            pass  # ToM-Tutor not installed — skip

        # 2. ПЛАНИРОВЩИК: Выбор стратегии
        plan = None
        should_plan = self.mode in [
            OrchestratorMode.FULL,
            OrchestratorMode.DIAGNOSTIC,
        ] and routing_config.get("use_planner", True)

        if should_plan:
            planner_stage = trace.start_stage(AgentStage.PLANNER)
            plan_start = time.time()
            try:
                planner_context = PlannerSessionContext(
                    topic=context.topic or "general",
                    difficulty="medium",
                    turn_number=session.turn_count if session else 0,
                )
                plan = self.planner.create_plan(
                    profile=profile or StudentProfile(),
                    context=planner_context,
                    graph_context=graph_context,
                    belief_state=belief_state,
                )
                metrics["planner_ms"] = (time.time() - plan_start) * 1000
                planner_stage.complete(
                    True,
                    output_summary=f"Strategy: {plan.strategy.value}, primary_move: {plan.primary_move.value}",
                )
                logger.debug(
                    "Планировщик: стратегия выбрана",
                    extra={
                        "strategy": plan.strategy.value,
                        "primary_move": plan.primary_move.value,
                    },
                )
            except Exception as e:
                logger.error(f"Ошибка планировщика: {e}")
                planner_stage.complete(False, error=str(e))
                # T039: Graceful degradation
                plan = self._handle_agent_failure("planner", e, trace, context)

        # Apply routing suggested move if no plan
        if not plan and routing_config.get("suggested_move"):
            try:
                primary = TeachingMove(routing_config["suggested_move"])
            except ValueError:
                primary = TeachingMove.SCAFFOLDING
            plan = TeachingPlan(
                strategy=TeachingStrategy.SCAFFOLDED,
                primary_move=primary,
                move_sequence=[primary],
            )

        # 2.4. Knowledge Forge: Graph navigation for context
        graph_context = None
        try:
            from src.tools.navigator_tools import get_navigator, set_mastery_source

            if session and hasattr(session, "student_id") and self.memory_manager:
                set_mastery_source(self.memory_manager)
            nav = get_navigator()
            if nav and context.topic:
                student_id = (
                    session.student_id
                    if session and hasattr(session, "student_id")
                    else "anonymous"
                )
                graph_context = nav.get_concept_context(
                    student_id, f"math:{context.topic}:definition"
                )
                if graph_context:
                    logger.debug(
                        "Knowledge Forge: graph context loaded", extra={"topic": context.topic}
                    )
        except Exception as e:
            logger.debug(f"Knowledge Forge unavailable (graceful skip): {e}")

        # 2.5. RAG: Извлечение контекста
        rag_context = None
        should_rag = self.use_rag and self.rag and routing_config.get("use_rag", True)

        if should_rag:
            rag_stage = trace.start_stage(AgentStage.RAG)
            rag_start = time.time()
            try:
                rag_context = self.rag.retrieve_context(
                    problem=context.problem,
                    student_response=context.student_input,
                    topic=context.topic,
                )
                metrics["rag_ms"] = (time.time() - rag_start) * 1000
                rag_stage.complete(
                    True,
                    output_summary=f"{len(rag_context.hints)} hints, {len(rag_context.misconceptions)} misconceptions",
                )
                logger.debug(
                    "RAG: контекст извлечён",
                    extra={
                        "hints": len(rag_context.hints),
                        "misconceptions": len(rag_context.misconceptions),
                    },
                )
            except Exception as e:
                logger.warning(f"Ошибка RAG: {e}")
                rag_stage.complete(False, error=str(e))
                # T039: Graceful degradation - RAG is optional
                rag_context = self._handle_agent_failure("rag", e, trace, context)

        # Если режим диагностики - возвращаем без ответа
        if self.mode == OrchestratorMode.DIAGNOSTIC:
            trace.complete(True)
            return TurnResult(
                response="",
                move_type="diagnostic",
                profile=profile,
                plan=plan,
                rag_context=rag_context,
                metrics=metrics,
                pipeline_trace=trace,
                query_type=query_type,
            )

        # 3. РЕПЕТИТОР: Генерация ответа
        tutor_stage = trace.start_stage(AgentStage.TUTOR)
        response = None
        move_type = plan.primary_move.value if plan else "scaffolding"
        verification = None
        should_verify = self.verify_responses and routing_config.get("use_verifier", True)

        for attempt in range(self.max_retries + 1):
            gen_start = time.time()
            try:
                response = self._generate_response(context, plan, profile, rag_context)
                metrics["generation_ms"] = (time.time() - gen_start) * 1000
                tutor_stage.complete(True, output_summary=f"Generated response, move={move_type}")

                # 4. ВЕРИФИКАТОР: Проверка качества
                if should_verify:
                    verifier_stage = trace.start_stage(AgentStage.VERIFIER)
                    verify_start = time.time()
                    try:
                        verification = self.verifier.verify(
                            response=response,
                            problem=context.problem,
                            correct_answer=context.correct_answer,
                            move_type=move_type,
                        )
                        metrics["verifier_ms"] = (time.time() - verify_start) * 1000

                        if not verification.is_valid:
                            verifier_stage.complete(
                                False,
                                output_summary=f"Invalid: {[c.issue.value for c in verification.critical_issues]}",
                            )
                            logger.warning(
                                f"Верификация не пройдена (попытка {attempt + 1})",
                                extra={
                                    "issues": [c.issue.value for c in verification.critical_issues]
                                },
                            )
                            trace.retries += 1
                            if attempt < self.max_retries:
                                continue  # Пробуем ещё раз
                        else:
                            verifier_stage.complete(
                                True,
                                output_summary=f"Valid, score={verification.quality_score:.2f}",
                            )
                    except Exception as e:
                        logger.error(f"Ошибка верификатора: {e}")
                        verifier_stage.complete(False, error=str(e))
                        # T039: Graceful degradation
                        verification = self._handle_agent_failure("verifier", e, trace, context)

                # Ответ готов
                break

            except Exception as e:
                logger.error(f"Ошибка генерации (попытка {attempt + 1}): {e}")
                tutor_stage.complete(False, error=str(e))

                if attempt == self.max_retries:
                    # T039: Graceful degradation
                    fallback_stage = trace.start_stage(AgentStage.FALLBACK)
                    response = self._handle_agent_failure("tutor", e, trace, context)
                    if not response:
                        response = self._fallback_response(context, plan)
                    fallback_stage.complete(True, output_summary="Used fallback response")

        # Извлекаем тип хода из ответа
        move_type = self._extract_move_type(response, move_type)

        # Вычисляем общее время
        total_ms = (time.time() - start_time) * 1000
        metrics["total_ms"] = total_ms

        # 5. KNOWLEDGE STATE: Собираем данные для визуализации
        knowledge_state = None
        if context.student_id and (self.use_knowledge_tracking or profile):
            knowledge_state = self._build_knowledge_state_data(context.student_id, profile)

        # T038: Complete trace
        trace.complete(True)

        # Создаём результат
        result = TurnResult(
            response=self._extract_message(response),
            move_type=move_type,
            profile=profile,
            plan=plan,
            verification=verification if self.verify_responses else None,
            rag_context=rag_context,
            metrics=metrics,
            knowledge_state=knowledge_state,
            pipeline_trace=trace,
            query_type=query_type,
        )

        # Обновляем сессию
        if session:
            session.add_turn(context, result)
            session.total_latency_ms += total_ms

        # Выполняем post-hooks
        for hook in self._post_hooks:
            try:
                hook(context, result, session)
            except Exception as e:
                logger.warning(f"Post-hook ошибка: {e}")

        logger.info(
            "Ход обработан",
            extra={
                "move": move_type,
                "total_ms": f"{total_ms:.1f}",
                "query_type": query_type.value,
                "verified": verification.is_valid if verification else "skipped",
                "trace": trace.summary(),
            },
        )

        return result

    def _generate_fast_response(self, context: TurnContext, query_type: QueryType) -> str:
        """
        Быстрый ответ для простых запросов (T037).

        Используется для приветствий, off-topic и других простых случаев.
        """
        fast_responses = {
            QueryType.GREETING: [
                "Привет! Готов помочь тебе с математикой. С какой задачей работаем?",
                "Здравствуй! Давай займёмся математикой. Над чем ты сейчас работаешь?",
                "Привет! Рад тебя видеть. Какую задачу будем решать?",
            ],
            QueryType.OFF_TOPIC: [
                "Давай вернёмся к нашей задаче. Посмотри на условие — что тебе уже понятно?",
                "Интересно, но давай сосредоточимся на математике. Где ты остановился в решении?",
                "Хороший вопрос, но сейчас давай сфокусируемся на задаче. С чего начнём?",
            ],
            QueryType.NEXT_TASK: [
                "Отлично, ты готов к новой задаче! Дай мне секунду, подберу подходящую.",
                "Хорошо, давай возьмём следующую задачу. Сейчас подготовлю.",
            ],
        }

        import random

        messages = fast_responses.get(query_type, fast_responses[QueryType.GREETING])
        return random.choice(messages)

    def _generate_response(
        self,
        context: TurnContext,
        plan: Optional[TeachingPlan],
        profile: Optional[StudentProfile],
        rag_context: Optional[Any] = None,
    ) -> str:
        """Генерация ответа репетитора."""
        # Формируем промпт
        system_prompt = self._build_system_prompt(plan)
        user_prompt = self._build_user_prompt(context, profile, rag_context)

        # Генерируем ответ
        response = self.llm.generate(
            prompt=user_prompt, system=system_prompt, temperature=0.7, max_tokens=500
        )

        return response

    def _build_system_prompt(self, plan: Optional[TeachingPlan]) -> str:
        """Построение системного промпта."""
        base_prompt = """Ты — сократический репетитор по STEM (математика, физика, химия, биология, информатика).

ЯЗЫК: Думай и отвечай ТОЛЬКО на русском языке. Все мысли, рассуждения и ответы — на русском (кириллица). Не используй английский ни для размышлений, ни для ответов.

ПРАВИЛА:
1. Никогда не давай прямых ответов — задавай наводящие вопросы
2. Используй LaTeX для формул: $inline$ и $$display$$
3. Помогай ученику прийти к ответу самостоятельно

ОБЪЁМ И ФОРМА:
- Длина ответа выбирается по сути: короткий наводящий вопрос — 1 предложение; разбор сложного шага — абзац или несколько. НЕ ограничивай себя «2-4 предложениями».
- Структурируй длинные ответы списками, **жирным**, заголовками.
- Можешь показать промежуточные выкладки и метод — финальный шаг оставь ученику.

ПЕДАГОГИЧЕСКИЕ ИНСТРУМЕНТЫ (не "answer-fetcher"):
- `lookup_concept(topic)` — определение + типичные ошибки → задай точечный вопрос про конкретный common_error.
- `get_solution_method(topic)` — алгоритм решения → СПРАШИВАЙ про каждый шаг по очереди, не выдавай весь.
- `get_worked_example(topic, difficulty)` — пример с решением → используй для аналогии.
- `get_formula(topic)`, `get_prerequisites(topic)` — справка для тебя.
- Knowledge Forge: `explore_concept`, `diagnose_gap`, `suggest_next`, `find_learning_path`, `get_learning_frontier`.
ВАЖНО: после tool НИКОГДА не выдавай прямой ответ. Tool — твоя подготовка, в ответе студенту — наводящий вопрос.

ВИЗУАЛИЗАЦИЯ (frontend сам отрисует):
Когда студент просит «нарисуй график/схему» — РИСУЙ через mermaid/plotly, НЕ говори «не умею».

**Mermaid** для блок-схем/процессов. КРИТИЧНО: в node labels используй ТОЛЬКО короткие фразы без скобок, знаков `=`, `(`, `)`, `<br>`, формул. Формулы оформляй ПОСЛЕ диаграммы отдельным `$LaTeX$`. Пример (КОПИРУЙ структуру):
```mermaid
flowchart TD
    A[Начало] --> B[Записать уравнение]
    B --> C[Найти коэффициенты a, b, c]
    C --> D[Вычислить дискриминант]
    D --> E{Знак D?}
    E -->|меньше 0| F[Нет корней]
    E -->|равен 0| G[Один корень]
    E -->|больше 0| H[Два корня]
    F --> I[Конец]
    G --> I
    H --> I
```

**Plotly** для графиков. КРИТИЧНО: JSON должен быть строго валидным — ровно ОДНА фигурная скобка в конце. Никаких лишних `}`, никаких комментариев внутри JSON. Пример (КОПИРУЙ структуру):
```plotly
{"data":[{"type":"scatter","mode":"lines","name":"y=x^2-3x+1","x":[-1,-0.5,0,0.5,1,1.5,2,2.5,3,3.5,4],"y":[5,2.75,1,-0.25,-1,-1.25,-1,-0.25,1,2.75,5]}],"layout":{"title":"График y=x^2-3x+1","xaxis":{"title":"x"},"yaxis":{"title":"y"}}}
```
Считай y-значения сам перед записью; пиши `^` как `^` (не `²`), чтобы JSON остался ASCII-безопасным где можно.

СТИЛЬ:
- Дружелюбный и поддерживающий тон
- Если ученик ошибся — мягко направь через вопрос
- Если на верном пути — похвали и спроси следующий шаг"""

        if plan:
            strategy_instructions = {
                TeachingStrategy.GUIDED_DISCOVERY: "\n\nСТРАТЕГИЯ: Направляй ученика к самостоятельному открытию через серию вопросов.",
                TeachingStrategy.SCAFFOLDED: "\n\nСТРАТЕГИЯ: Разбивай задачу на маленькие шаги, помогай на каждом этапе.",
                TeachingStrategy.ERROR_CORRECTION: "\n\nСТРАТЕГИЯ: Мягко указывай на ошибку через вопросы, помогай понять причину.",
                TeachingStrategy.CONCEPTUAL_REPAIR: "\n\nСТРАТЕГИЯ: Укрепляй понимание базовых концепций перед решением.",
                TeachingStrategy.ENCOURAGEMENT: "\n\nСТРАТЕГИЯ: Поддерживай и хвали за каждый шаг прогресса.",
                TeachingStrategy.DIRECT_INSTRUCTION: "\n\nСТРАТЕГИЯ: Объясняй напрямую, но всё равно задавай проверочные вопросы.",
            }
            base_prompt += strategy_instructions.get(plan.strategy, "")

            if plan.tone:
                base_prompt += f"\n\nТОН: {plan.tone}"

        return base_prompt

    def _build_user_prompt(
        self,
        context: TurnContext,
        profile: Optional[StudentProfile],
        rag_context: Optional[Any] = None,
    ) -> str:
        """Построение пользовательского промпта."""
        prompt_parts = [f"Задача: {context.problem}"]

        # Добавляем RAG контекст (подсказки и типичные ошибки)
        if rag_context:
            rag_text = rag_context.to_prompt_context()
            if rag_text:
                prompt_parts.append(f"\n{rag_text}")

        # Добавляем историю (последние 3 обмена)
        if context.history:
            prompt_parts.append("\nИстория диалога:")
            for turn in context.history[-6:]:  # Последние 3 пары
                role = turn.get("role", "unknown")
                content = turn.get("content", "")[:200]
                prompt_parts.append(f"{role}: {content}")

        # Добавляем информацию из профайлера
        if profile and profile.errors:
            prompt_parts.append("\nДиагностика ошибок:")
            for error in profile.errors[:2]:  # Максимум 2 ошибки
                prompt_parts.append(f"- {error.error_type.value}: {error.description}")

            if profile.misconceptions:
                prompt_parts.append(
                    f"Возможные заблуждения: {', '.join(profile.misconceptions[:2])}"
                )

        prompt_parts.append(f"\nУченик: {context.student_input}")

        return "\n".join(prompt_parts)

    def _fallback_response(self, context: TurnContext, plan: Optional[TeachingPlan]) -> str:
        """Запасной ответ при ошибках."""
        fallback_responses = {
            "scaffolding": "Давай разберём это по шагам. С чего бы ты хотел начать?",
            "hint": "Подумай о том, какую операцию нужно выполнить первой.",
            "encourage": "Ты на правильном пути! Продолжай рассуждать.",
            "clarify": "Не совсем понял твой ответ. Можешь объяснить подробнее?",
        }

        move = plan.primary_move.value if plan else "scaffolding"
        message = fallback_responses.get(move, fallback_responses["scaffolding"])

        return json.dumps({"move": move, "message": message}, ensure_ascii=False)

    def _extract_move_type(self, response: str, default: str) -> str:
        """Извлечение типа хода из ответа."""
        try:
            if response.strip().startswith("{"):
                data = json.loads(response)
                return data.get("move", default)
        except json.JSONDecodeError:
            pass
        return default

    def _extract_message(self, response: str) -> str:
        """Извлечение текста сообщения."""
        try:
            if response.strip().startswith("{"):
                data = json.loads(response)
                return data.get("message", response)
        except json.JSONDecodeError:
            pass
        return response

    def _build_knowledge_state_data(
        self, student_id: str, profile: Optional[StudentProfile]
    ) -> KnowledgeStateData:
        """
        Построение данных о состоянии знаний для UI.

        Args:
            student_id: ID ученика
            profile: Профиль ученика из профайлера

        Returns:
            KnowledgeStateData для визуализации
        """
        knowledge_state = KnowledgeStateData()

        # Данные из Knowledge Tracker
        if self.knowledge_tracker and self.use_knowledge_tracking:
            try:
                kt_summary = self.knowledge_tracker.get_knowledge_state_summary(student_id)

                knowledge_state.total_interactions = kt_summary.get("total_interactions", 0)
                knowledge_state.using_dkt = kt_summary.get("using_dkt", False)
                knowledge_state.weakest_skills = kt_summary.get("weakest_skills", [])
                knowledge_state.strongest_skills = kt_summary.get("strongest_skills", [])
                knowledge_state.recommended_skill = kt_summary.get("recommended_skill")
                knowledge_state.recommended_difficulty = kt_summary.get(
                    "recommended_difficulty", "medium"
                )

                # Построение визуализации навыков
                mastery_by_skill = kt_summary.get("mastery_by_skill", {})
                for skill_name, skill_data in mastery_by_skill.items():
                    knowledge_state.mastery_visualization.append(
                        TopicMasteryVisualization(
                            skill_name=skill_name,
                            mastery=skill_data.get("mastery", 0.5),
                            dkt_mastery=skill_data.get("dkt_mastery"),
                            attempts=skill_data.get("attempts", 0),
                            success_rate=skill_data.get("success_rate", 0.0),
                        )
                    )

            except Exception as e:
                logger.warning(f"Ошибка получения данных из KnowledgeTracker: {e}")

        # Данные из профиля (когнитивная нагрузка)
        if profile:
            knowledge_state.cognitive_load_level = profile.cognitive_load_level
            knowledge_state.cognitive_load_score = profile.cognitive_load_score
            knowledge_state.should_simplify = profile.should_simplify
            knowledge_state.should_offer_break = profile.should_offer_break

            # Если нет данных из KT, берём из профиля
            if not knowledge_state.mastery_visualization and profile.mastery_by_skill:
                for skill_name, mastery in profile.mastery_by_skill.items():
                    knowledge_state.mastery_visualization.append(
                        TopicMasteryVisualization(skill_name=skill_name, mastery=mastery)
                    )

            if not knowledge_state.recommended_difficulty:
                knowledge_state.recommended_difficulty = profile.recommended_difficulty

        return knowledge_state

    def add_pre_hook(self, hook: Callable):
        """Добавление pre-hook."""
        self._pre_hooks.append(hook)

    def add_post_hook(self, hook: Callable):
        """Добавление post-hook."""
        self._post_hooks.append(hook)

    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Получение статистики сессии.

        Args:
            session_id: ID сессии

        Returns:
            Словарь со статистикой или None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "turn_count": session.turn_count,
            "avg_latency_ms": session.total_latency_ms / session.turn_count
            if session.turn_count > 0
            else 0,
            "total_latency_ms": session.total_latency_ms,
            "student_id": session.student_id,
            "current_topic": session.current_topic,
        }

    def close_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Закрытие сессии.

        Args:
            session_id: ID сессии

        Returns:
            Финальная статистика сессии
        """
        stats = self.get_session_stats(session_id)

        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("Сессия закрыта", extra={"session_id": session_id})

        return stats


def create_orchestrator(llm_client, mode: str = "full", verify: bool = True) -> AgentOrchestrator:
    """
    Фабричная функция для создания оркестратора.

    Args:
        llm_client: Клиент LLM
        mode: Режим работы ("full", "fast", "diagnostic")
        verify: Верифицировать ответы

    Returns:
        Настроенный AgentOrchestrator
    """
    mode_enum = OrchestratorMode(mode)
    return AgentOrchestrator(llm_client=llm_client, mode=mode_enum, verify_responses=verify)


# Пример использования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Мок LLM клиент для тестирования
    class MockLLMClient:
        def generate(self, prompt, system_prompt=None, **kwargs):
            return json.dumps(
                {
                    "move": "scaffolding",
                    "message": "Давай посмотрим на это уравнение. Что ты видишь в левой части?",
                },
                ensure_ascii=False,
            )

    print("=== Тест AgentOrchestrator ===\n")

    # Создаём оркестратор
    llm = MockLLMClient()
    orchestrator = create_orchestrator(llm, mode="full", verify=True)

    # Создаём сессию
    session = orchestrator.create_session(
        session_id="test-001",
        student_id="student-1",
        problem="Решить уравнение: $2x + 5 = 13$",
        topic="linear_equations",
    )

    # Обрабатываем ход
    context = TurnContext(
        problem="Решить уравнение: $2x + 5 = 13$",
        student_input="Не знаю как начать",
        correct_answer="4",
        topic="linear_equations",
    )

    result = orchestrator.process_turn(context, session_id="test-001")

    print(f"Ответ: {result.response}")
    print(f"Тип хода: {result.move_type}")
    print(f"Метрики: {result.metrics}")

    if result.verification:
        print(f"Верификация: {result.verification.summary()}")

    # Статистика сессии
    stats = orchestrator.get_session_stats("test-001")
    print(f"\nСтатистика сессии: {stats}")
