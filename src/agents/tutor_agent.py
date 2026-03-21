"""
MITS Socratic Tutor Agent

The core tutoring agent that implements the Socratic method.
Guides students through questions, not answers.

Обновлено для поддержки новой многоагентной архитектуры:
- Интеграция с Orchestrator для координации агентов
- Поддержка RAG контекста
- Использование Profiler и Planner агентов
"""

from typing import Optional, List, Dict, Any, TYPE_CHECKING
import json
import logging
from datetime import datetime, timedelta

from src.agents.base_agent import BaseAgent
from src.models.llm_client import LLMClient
from src.models.prompts import (
    SOCRATIC_TUTOR_SYSTEM, TUTOR_RESPONSE_PROMPT,
    SOCRATIC_QUESTION_TEMPLATES, ScaffoldingLevel, detect_frustration,
    convert_to_russian_notation, RUSSIAN_MATH_NOTATION
)

# T051: Language Detection
try:
    from src.utils.language_detector import (
        detect_language, Language, should_use_russian_notation
    )
    HAS_LANGUAGE_DETECTOR = True
except ImportError:
    HAS_LANGUAGE_DETECTOR = False
    detect_language = None
    Language = None
from src.data.schemas import (
    Task, TutorMove, TutorResponse, ConversationTurn,
    TutoringSession, StudentProfile, VerificationResult
)
from src.config import settings

# Innovation imports (009-groundbreaking-innovations)
try:
    from src.models.affective_detector import AffectiveDetector
    HAS_AFFECTIVE = True
except ImportError:
    HAS_AFFECTIVE = False
    AffectiveDetector = None

try:
    from src.models.metacognitive_tracker import MetacognitiveTracker
    HAS_METACOGNITIVE = True
except ImportError:
    HAS_METACOGNITIVE = False
    MetacognitiveTracker = None

try:
    from src.models.counterfactual_engine import CounterfactualEngine
    HAS_COUNTERFACTUAL = True
except ImportError:
    HAS_COUNTERFACTUAL = False
    CounterfactualEngine = None

# T031: Tool Integration
try:
    from src.tools import (
        tool_registry, ensure_tools_registered,
        ToolResult, ToolType, BaseTool
    )
    HAS_TOOLS = True
except ImportError:
    HAS_TOOLS = False
    tool_registry = None
    ensure_tools_registered = None
    ToolResult = None
    ToolType = None

# Native SKI tool calling
try:
    from src.tools.ski_tools import SKI_TOOL_DEFINITIONS, SKI_FUNCTIONS
    HAS_SKI_TOOLS = True
except ImportError:
    HAS_SKI_TOOLS = False
    SKI_TOOL_DEFINITIONS = []
    SKI_FUNCTIONS = {}

if TYPE_CHECKING:
    from src.memory.session_memory import SessionMemory

# Опциональные импорты для новой архитектуры
try:
    from src.agents.orchestrator import AgentOrchestrator, TurnContext, create_orchestrator
    HAS_ORCHESTRATOR = True
except ImportError:
    HAS_ORCHESTRATOR = False
    AgentOrchestrator = None
    TurnContext = None

try:
    from src.knowledge.rag_retriever import TutoringRAG
    HAS_RAG = True
except ImportError:
    HAS_RAG = False
    TutoringRAG = None

logger = logging.getLogger(__name__)


class SocraticTutorAgent(BaseAgent):
    """
    Main tutoring agent implementing the Socratic method.
    
    Teaching Structure (from SocraticLLM):
    1. Review - Understand student's current state
    2. Guidance/Heuristic - Lead with questions
    3. Rectification - Correct misconceptions gently
    4. Summarization - Reinforce learning after success
    """
    
    def __init__(
        self,
        llm_client: LLMClient,
        use_orchestrator: bool = True,
        use_rag: bool = True,
        use_affective: bool = True,
        use_metacognitive: bool = True,
        use_counterfactual: bool = True
    ):
        """
        Инициализация агента репетитора.

        Args:
            llm_client: Клиент LLM для генерации ответов
            use_orchestrator: Использовать многоагентный оркестратор
            use_rag: Использовать RAG для контекста
            use_affective: Использовать детектор эмоционального состояния
            use_metacognitive: Использовать метакогнитивный трекер
            use_counterfactual: Использовать контрфактуальные объяснения
        """
        super().__init__(
            name="SocraticTutor",
            llm_client=llm_client,
            system_prompt=SOCRATIC_TUTOR_SYSTEM
        )

        # Strategy thresholds
        self.max_attempts_before_hint = 2
        self.max_hints_before_tell = settings.MAX_HINTS
        self.frustration_threshold = 3

        # Progressive scaffolding state
        self.current_scaffolding_level = ScaffoldingLevel.CONCEPTUAL
        self.scaffolding_attempts_at_level = 0
        self.max_attempts_per_level = 2

        # Новая архитектура
        self.use_orchestrator = use_orchestrator and HAS_ORCHESTRATOR
        self.use_rag = use_rag and HAS_RAG

        # Инициализация оркестратора
        self.orchestrator = None
        if self.use_orchestrator:
            try:
                self.orchestrator = create_orchestrator(
                    llm_client=llm_client,
                    mode="full",
                    verify=True
                )
                logger.info("Оркестратор агентов инициализирован")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать оркестратор: {e}")
                self.use_orchestrator = False

        # Инициализация RAG (если не через оркестратор)
        self.rag = None
        if self.use_rag and not self.use_orchestrator:
            try:
                self.rag = TutoringRAG()
                logger.info("RAG система инициализирована")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать RAG: {e}")
                self.use_rag = False

        # T031: Инициализация инструментов
        self.use_tools = HAS_TOOLS
        if self.use_tools:
            try:
                ensure_tools_registered()
                logger.info("Инструменты репетитора зарегистрированы")
            except Exception as e:
                logger.warning(f"Не удалось зарегистрировать инструменты: {e}")
                self.use_tools = False

        # Native SKI tool calling via Ollama Tools API
        self.use_native_tools = HAS_SKI_TOOLS
        self._ski_tool_defs = SKI_TOOL_DEFINITIONS if HAS_SKI_TOOLS else []
        self._ski_functions = SKI_FUNCTIONS if HAS_SKI_TOOLS else {}

        # === Innovation Features (009) ===

        # Affective State Detection
        self.use_affective = use_affective and HAS_AFFECTIVE
        self.affective_detector = None
        if self.use_affective:
            try:
                self.affective_detector = AffectiveDetector(
                    llm_client=llm_client,
                    confidence_threshold=settings.AFFECTIVE_CONFIDENCE_THRESHOLD if hasattr(settings, 'AFFECTIVE_CONFIDENCE_THRESHOLD') else 0.6,
                )
                logger.info("Детектор эмоционального состояния инициализирован")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать AffectiveDetector: {e}")
                self.use_affective = False

        # Metacognitive Tracker
        self.use_metacognitive = use_metacognitive and HAS_METACOGNITIVE
        self.metacognitive_tracker = None
        if self.use_metacognitive:
            try:
                self.metacognitive_tracker = MetacognitiveTracker()
                logger.info("Метакогнитивный трекер инициализирован")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать MetacognitiveTracker: {e}")
                self.use_metacognitive = False

        # Counterfactual Engine
        self.use_counterfactual = use_counterfactual and HAS_COUNTERFACTUAL
        self.counterfactual_engine = None
        if self.use_counterfactual:
            try:
                self.counterfactual_engine = CounterfactualEngine(llm_client=llm_client)
                logger.info("Контрфактуальный движок инициализирован")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать CounterfactualEngine: {e}")
                self.use_counterfactual = False

        # Track response timing for affective analysis
        self._last_message_time: Optional[datetime] = None
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process student message and generate tutoring response.
        
        Args:
            input_data: {
                "session": TutoringSession,
                "student_message": str,
                "student_profile": StudentProfile (optional),
                "verification": VerificationResult (optional)
            }
            
        Returns:
            {"response": TutorResponse}
        """
        session = input_data["session"]
        student_message = input_data["student_message"]
        student_profile = input_data.get("student_profile")
        verification = input_data.get("verification")
        
        response = self.generate_response(
            session=session,
            student_message=student_message,
            student_profile=student_profile,
            verification_result=verification
        )
        
        return {"response": response}
    
    def generate_response(
        self,
        session: TutoringSession,
        student_message: str,
        student_profile: Optional[StudentProfile] = None,
        verification_result: Optional[VerificationResult] = None
    ) -> TutorResponse:
        """
        Generate a Socratic tutoring response.

        Args:
            session: Current tutoring session
            student_message: Latest student message
            student_profile: Student's profile (optional)
            verification_result: Verification of student's answer (optional)

        Returns:
            TutorResponse with move and message
        """
        # Calculate response time for affective analysis
        response_time_ms = 0
        if self._last_message_time:
            response_time_ms = int((datetime.now() - self._last_message_time).total_seconds() * 1000)
        self._last_message_time = datetime.now()

        # === Innovation: Affective State Detection ===
        affective_context = {}
        if self.use_affective and self.affective_detector:
            try:
                affective_state = self.affective_detector.analyze_message(
                    message=student_message,
                    response_time_ms=response_time_ms,
                    context=[{"role": t.role, "content": t.content} for t in session.conversation[-5:]],
                    was_correct=verification_result.is_correct if verification_result else None
                )
                affective_context = {
                    "state": affective_state.state_type.value,
                    "should_simplify": affective_state.should_simplify,
                    "should_encourage": affective_state.should_encourage,
                    "adaptation_prompt": self.affective_detector.get_adaptation_prompt(affective_state),
                }
                logger.debug(f"Affective state: {affective_state.state_type.value}")
            except Exception as e:
                logger.warning(f"Affective detection failed: {e}")

        # === Innovation: Metacognitive Scaffolding ===
        metacognitive_prompt = None
        if self.use_metacognitive and self.metacognitive_tracker:
            try:
                stuck_point = self.metacognitive_tracker.detect_stuck_point(
                    message=student_message,
                    context=[{"role": t.role, "content": t.content} for t in session.conversation[-3:]],
                    error_count=session.attempts - (1 if verification_result and verification_result.is_correct else 0),
                )
                if stuck_point:
                    metacognitive_prompt = self.metacognitive_tracker.get_metacognitive_prompt(stuck_point)
                    self.metacognitive_tracker.record_intervention(
                        stuck_point, "metacognitive_prompt", metacognitive_prompt
                    )
                    logger.debug(f"Stuck point detected: {stuck_point.type.value}")
                self.metacognitive_tracker.increment_message_count()
            except Exception as e:
                logger.warning(f"Metacognitive tracking failed: {e}")

        # Используем оркестратор если доступен
        if self.use_orchestrator and self.orchestrator:
            response = self._generate_with_orchestrator(
                session, student_message, student_profile
            )
        else:
            # Иначе используем классический подход
            response = self._generate_classic(
                session, student_message, student_profile, verification_result,
                affective_context=affective_context,
                metacognitive_prompt=metacognitive_prompt
            )

        # === Innovation: Counterfactual Explanations ===
        if (self.use_counterfactual and self.counterfactual_engine
            and verification_result and not verification_result.is_correct):
            try:
                counterfactual = self.counterfactual_engine.analyze_error(
                    student_answer=student_message,
                    correct_answer=str(session.task.answer) if session.task.answer else "",
                    task=session.task,
                    student_id=str(student_profile.id) if student_profile else "",
                    session_id=str(session.id) if hasattr(session, 'id') else ""
                )
                # Append counterfactual to response
                cf_display = self.counterfactual_engine.format_explanation_for_display(counterfactual)
                response.message = response.message + "\n\n" + cf_display
                response.internal_reasoning = (response.internal_reasoning or "") + f"\nCounterfactual: {counterfactual.missing_skill}"
                logger.debug(f"Counterfactual added: {counterfactual.missing_skill}")
            except Exception as e:
                logger.warning(f"Counterfactual generation failed: {e}")

        return response

    def _generate_with_orchestrator(
        self,
        session: TutoringSession,
        student_message: str,
        student_profile: Optional[StudentProfile] = None
    ) -> TutorResponse:
        """
        Генерация ответа через многоагентный оркестратор.

        Использует:
        - Profiler для диагностики ошибок
        - Planner для выбора стратегии
        - RAG для контекста
        - Verifier для проверки качества
        """
        # Конвертируем историю сессии
        history = []
        for turn in session.conversation[-10:]:
            history.append({
                "role": turn.role,
                "content": turn.content
            })

        # Создаём контекст для оркестратора
        context = TurnContext(
            problem=session.task.problem,
            student_input=student_message,
            correct_answer=str(session.task.answer) if session.task.answer else None,
            history=history,
            topic=session.task.topic if hasattr(session.task, 'topic') else None
        )

        # Обрабатываем через оркестратор
        result = self.orchestrator.process_turn(
            context,
            session_id=str(session.id) if hasattr(session, 'id') else None
        )

        # Конвертируем результат в TutorResponse
        try:
            move = TutorMove(result.move_type)
        except ValueError:
            move = TutorMove.SCAFFOLDING

        response = TutorResponse(
            move=move,
            message=result.response,
            internal_reasoning=f"Strategy: {result.plan.strategy.value if result.plan else 'unknown'}",
            hint_number=session.hints_used + 1 if move == TutorMove.HINT else None,
            is_telling=move == TutorMove.TELL
        )

        # Логируем метрики
        if result.metrics:
            logger.info(
                "Orchestrator response generated",
                extra={
                    "total_ms": result.metrics.get("total_ms", 0),
                    "move": result.move_type,
                    "verified": result.verification.is_valid if result.verification else "skipped"
                }
            )

        return response

    def _generate_with_native_tools(
        self,
        session: TutoringSession,
        student_message: str,
        strategy: str,
        rag_context: Optional[Any] = None,
        few_shot_prompt: str = "",
    ) -> Optional[TutorResponse]:
        """
        LLM-driven tool calling via Ollama Tools API.

        The model decides which SKI tools to call based on the conversation.
        Returns None on failure so caller can fallback to classic flow.
        """
        if not self.use_native_tools or not self._ski_tool_defs:
            return None

        # Build messages for tool-calling conversation
        history_turns = session.conversation[-8:]
        messages = [
            {"role": "system", "content": SOCRATIC_TUTOR_SYSTEM},
        ]

        # Add few-shot examples if available
        if few_shot_prompt:
            messages[0]["content"] += "\n\n" + few_shot_prompt

        # Add notation context from SKI
        try:
            from src.knowledge.ski import get_ski as _get_ski_instance
            _ski = _get_ski_instance()
            _topic = session.task.topic if session.task and hasattr(session.task, 'topic') else None
            if _topic:
                _notation = _ski.get_notation_context(_topic)
                if _notation:
                    _lines = ["\n## НОТАЦИЯ (используй эти обозначения):"]
                    for _sym, _desc in _notation.items():
                        _lines.append(f"- {_sym}: {_desc}")
                    messages[0]["content"] += "\n".join(_lines)
        except Exception:
            pass

        # Add task context as system info
        if session.task:
            task_context = (
                f"\n\n## ТЕКУЩАЯ ЗАДАЧА (для тебя, НЕ раскрывай ответ!):\n"
                f"Условие: {session.task.problem}\n"
                f"Рекомендуемая стратегия: {strategy}\n"
                f"Подсказок использовано: {session.hints_used}"
            )
            messages[0]["content"] += task_context

        # Add conversation history
        for turn in history_turns:
            messages.append({
                "role": "user" if turn.role == "student" else "assistant",
                "content": turn.content,
            })

        # Add current student message
        messages.append({"role": "user", "content": student_message})

        try:
            result = self.llm.chat_with_tools(
                messages=messages,
                tools=self._ski_tool_defs,
                available_functions=self._ski_functions,
                max_tool_rounds=3,
            )

            content = result.get("content", "")
            if not content:
                return None

            # Try to parse as JSON (structured response)
            try:
                response_data = json.loads(content)
                tool_info = ""
                if result.get("tool_calls_made"):
                    tool_names = [tc["function"] for tc in result["tool_calls_made"]]
                    tool_info = f" | Tools used: {', '.join(tool_names)}"

                return TutorResponse(
                    move=TutorMove(response_data.get("move", strategy)),
                    message=response_data["message"],
                    internal_reasoning=response_data.get("reasoning", "") + tool_info,
                    hint_number=session.hints_used + 1 if strategy == "hint" else None,
                    is_telling=response_data.get("move") == "tell",
                )
            except (json.JSONDecodeError, KeyError):
                # Model returned plain text — wrap it
                tool_info = ""
                if result.get("tool_calls_made"):
                    tool_names = [tc["function"] for tc in result["tool_calls_made"]]
                    tool_info = f"Tools used: {', '.join(tool_names)}"

                return TutorResponse(
                    move=TutorMove.SCAFFOLDING,
                    message=content,
                    internal_reasoning=f"Native tool response (plain text). {tool_info}",
                    is_telling=False,
                )

        except Exception as e:
            logger.warning("Native tool calling failed, will fallback: %s", e)
            return None

    def _generate_classic(
        self,
        session: TutoringSession,
        student_message: str,
        student_profile: Optional[StudentProfile] = None,
        verification_result: Optional[VerificationResult] = None,
        affective_context: Optional[Dict[str, Any]] = None,
        metacognitive_prompt: Optional[str] = None
    ) -> TutorResponse:
        """
        Классическая генерация ответа (без оркестратора).

        Args:
            affective_context: Контекст эмоционального состояния студента
            metacognitive_prompt: Метакогнитивный промпт если студент "застрял"
        """
        # If we have a metacognitive prompt, use it directly
        if metacognitive_prompt:
            return TutorResponse(
                move=TutorMove.SCAFFOLDING,
                message=metacognitive_prompt,
                internal_reasoning="Metacognitive scaffolding - student stuck",
                is_telling=False
            )
        # T031: Check if tools are needed and use them
        if self.use_tools:
            tool_name = self._detect_tool_need(student_message, session)
            if tool_name:
                logger.info(f"Tool detected: {tool_name}")
                tool_result = self._execute_tool(tool_name, student_message, session)
                if tool_result and tool_result.success:
                    tool_response = self._integrate_tool_in_response(
                        session, student_message, tool_name, tool_result
                    )
                    if tool_response:
                        self._log_action("tool_response_generated", {
                            "tool": tool_name,
                            "move": tool_response.move.value
                        })
                        return tool_response

        # 1. Analyze current situation
        situation = self._analyze_situation(
            session, student_message, verification_result
        )

        # 2. Select teaching strategy
        strategy = self._select_strategy(situation, session)

        self._log_action("strategy_selected", {
            "strategy": strategy,
            "situation": situation
        })

        # 2.5. Try native tool calling first (LLM decides what to look up)
        if self.use_native_tools:
            native_response = self._generate_with_native_tools(
                session, student_message, strategy
            )
            if native_response:
                # Safety check
                if self._is_revealing_answer(native_response.message, session.task):
                    logger.warning("answer_leak_in_tool_response")
                    native_response = self._sanitize_response(native_response, session.task)
                return native_response

        # 3. Получаем RAG контекст (если доступен)
        rag_context = None
        if self.use_rag and self.rag:
            try:
                rag_context = self.rag.retrieve_context(
                    problem=session.task.problem,
                    student_response=student_message,
                    topic=session.task.topic if hasattr(session.task, 'topic') else None
                )
            except Exception as e:
                logger.warning(f"RAG error: {e}")

        # 4. Generate response using LLM
        prompt = self._build_prompt(
            session=session,
            student_message=student_message,
            situation=situation,
            strategy=strategy,
            student_profile=student_profile,
            rag_context=rag_context
        )

        raw_response = self._call_llm(prompt, json_mode=True)

        # 5. Parse and validate response
        try:
            response_data = json.loads(raw_response)

            response = TutorResponse(
                move=TutorMove(response_data.get("move", strategy)),
                message=response_data["message"],
                internal_reasoning=response_data.get("reasoning"),
                hint_number=session.hints_used + 1 if strategy == "hint" else None,
                is_telling=response_data.get("move") == "tell"
            )

            # Safety check: Ensure we're not accidentally revealing the answer
            if self._is_revealing_answer(response.message, session.task):
                self.logger.warning("answer_leak_detected", move=response.move)
                response = self._sanitize_response(response, session.task)

            self._log_action("response_generated", {
                "move": response.move.value,
                "is_telling": response.is_telling
            })

            return response

        except json.JSONDecodeError:
            # Fallback to simple scaffolding response
            self.logger.warning("json_parse_failed", response=raw_response[:200])
            return TutorResponse(
                move=TutorMove.SCAFFOLDING,
                message=raw_response,
                is_telling=False
            )
    
    def _analyze_situation(
        self,
        session: TutoringSession,
        student_message: str,
        verification: Optional[VerificationResult]
    ) -> Dict[str, Any]:
        """Analyze current tutoring situation."""

        situation = {
            "attempts": session.attempts,
            "hints_used": session.hints_used,
            "conversation_length": len(session.conversation),
            "student_state": "working",
            "scaffolding_level": self.current_scaffolding_level
        }

        # Check verification result
        if verification:
            if verification.is_correct:
                situation["student_state"] = "solved"
                # Reset scaffolding on success
                self._reset_scaffolding()
            elif verification.is_partial:
                situation["student_state"] = "partial_progress"
            elif verification.has_error:
                situation["student_state"] = "made_error"
                situation["error_type"] = verification.error_type

        # Check for frustration signals using enhanced detection
        if detect_frustration(student_message):
            situation["emotional_state"] = "frustrated"
            # Progress scaffolding when frustrated
            self._progress_scaffolding()

        # Check if student is asking a question
        if "?" in student_message:
            situation["is_asking_question"] = True

        # Track consecutive errors for cognitive load
        situation["consecutive_errors"] = self._count_consecutive_errors(session)

        return situation

    def _reset_scaffolding(self) -> None:
        """Reset scaffolding level after success."""
        self.current_scaffolding_level = ScaffoldingLevel.CONCEPTUAL
        self.scaffolding_attempts_at_level = 0

    def _progress_scaffolding(self) -> None:
        """Progress to more specific scaffolding level."""
        self.scaffolding_attempts_at_level += 1
        if self.scaffolding_attempts_at_level >= self.max_attempts_per_level:
            self.current_scaffolding_level = ScaffoldingLevel.next_level(
                self.current_scaffolding_level
            )
            self.scaffolding_attempts_at_level = 0
            logger.info(f"Scaffolding progressed to: {self.current_scaffolding_level}")

    def _count_consecutive_errors(self, session: TutoringSession) -> int:
        """Count consecutive errors from recent conversation."""
        count = 0
        for turn in reversed(session.conversation):
            if turn.role == "tutor" and turn.move == TutorMove.RECTIFY:
                count += 1
            elif turn.role == "tutor" and turn.move == TutorMove.ENCOURAGE:
                break  # Stop counting after last success
        return count

    def _get_socratic_questions(self, topic: str) -> list:
        """Get Socratic questions for current topic and scaffolding level."""
        return ScaffoldingLevel.get_questions(topic, self.current_scaffolding_level)

    # === T031: Tool Integration Methods ===

    # Patterns indicating calculator is needed
    CALCULATOR_PATTERNS = [
        r'\d+\s*[\+\-\*\/\^]\s*\d+',  # 2 + 3, 5 * 4
        r'\d+!',  # factorial
        r'sqrt|sin|cos|tan|log|exp',  # math functions
        r'вычисл|посчита|чему равн|сколько будет',  # Russian: calculate
        r'calculate|compute|what is|solve',  # English
        r'производн|derivative|интеграл|integral',  # calculus
        r'упрост|simplify|factor|expand',  # algebra
    ]

    # Patterns indicating web search might help
    WEB_SEARCH_PATTERNS = [
        r'найди|поищи|search|find|look up',  # search commands
        r'что такое|what is|who is|когда',  # definition questions
        r'олимпиад|olympiad|егэ|огэ',  # exam-related
        r'последн|recent|новост|2024|2025|2026',  # current info
    ]

    # Patterns for knowledge base search
    KNOWLEDGE_PATTERNS = [
        r'подсказк|hint|объясн|explain',  # hints/explanations
        r'как решать|how to solve|метод',  # methods
        r'ошибк|mistake|misconception',  # errors
        r'пример|example|формул|formula',  # examples/formulas
    ]

    def _detect_tool_need(
        self,
        student_message: str,
        session: "TutoringSession"
    ) -> Optional[str]:
        """
        Detect if a tool is needed based on student message.

        Args:
            student_message: The student's message
            session: Current tutoring session

        Returns:
            Tool name if needed, None otherwise
        """
        import re

        if not self.use_tools or not HAS_TOOLS:
            return None

        message_lower = student_message.lower()

        # Check calculator patterns
        for pattern in self.CALCULATOR_PATTERNS:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return "calculator"

        # Check if student explicitly asks for calculation in context
        if session.task and hasattr(session.task, 'topic'):
            topic = session.task.topic.lower() if session.task.topic else ""
            # If working on calculus/algebra, calculator might help
            if topic in ['calculus', 'algebra', 'derivatives', 'integrals']:
                if any(word in message_lower for word in ['проверь', 'check', 'verify', 'покажи', 'show']):
                    return "calculator"

        # Check web search patterns (only when explicitly requested)
        for pattern in self.WEB_SEARCH_PATTERNS:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return "web_search"

        # Check knowledge base patterns
        for pattern in self.KNOWLEDGE_PATTERNS:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return "knowledge_search"

        return None

    def _execute_tool(
        self,
        tool_name: str,
        query: str,
        session: Optional["TutoringSession"] = None
    ) -> Optional["ToolResult"]:
        """
        Execute a tool and return its result.

        Args:
            tool_name: Name of the tool to execute
            query: Query/expression for the tool
            session: Current tutoring session for context

        Returns:
            ToolResult or None if tool not found/failed
        """
        if not self.use_tools or not HAS_TOOLS:
            return None

        tool = tool_registry.get(tool_name)
        if not tool:
            logger.warning(f"Tool not found: {tool_name}")
            return None

        try:
            # Prepare kwargs based on tool type
            kwargs = {}
            if session and session.task:
                if hasattr(session.task, 'topic'):
                    kwargs['topic'] = session.task.topic
                if tool_name == "knowledge_search":
                    kwargs['student_response'] = query

            result = tool.execute(query, **kwargs)

            logger.info(
                "tool_executed",
                extra={
                    "tool": tool_name,
                    "success": result.success,
                    "execution_time_ms": result.execution_time_ms
                }
            )

            return result

        except Exception as e:
            logger.error(f"Tool execution error: {tool_name} - {e}")
            return None

    def _format_tool_result(
        self,
        tool_result: "ToolResult",
        tool_name: str
    ) -> str:
        """
        Format tool result for inclusion in tutor response.

        Args:
            tool_result: Result from tool execution
            tool_name: Name of the tool

        Returns:
            Formatted string for context
        """
        if not tool_result or not tool_result.success:
            error_msg = tool_result.error if tool_result else "Неизвестная ошибка"
            return f"[Инструмент {tool_name}]: Ошибка - {error_msg}"

        result = tool_result.result

        if tool_name == "calculator":
            return f"[Калькулятор]: {result}"

        elif tool_name == "web_search":
            if isinstance(result, dict):
                summary = result.get("summary", "")
                count = result.get("count", 0)
                return f"[Веб-поиск]: Найдено {count} результатов.\n{summary}"
            return f"[Веб-поиск]: {result}"

        elif tool_name == "knowledge_search":
            if isinstance(result, dict):
                summary = result.get("summary", "")
                hints = result.get("hints", [])
                if hints:
                    hint_texts = [h.get("content", "") for h in hints[:2]]
                    return f"[База знаний]: {summary}\nПодсказки: {'; '.join(hint_texts)}"
                return f"[База знаний]: {summary}"
            return f"[База знаний]: {result}"

        return f"[{tool_name}]: {result}"

    def get_available_tools(self) -> List[Dict[str, str]]:
        """
        Get list of available tools for display.

        Returns:
            List of tool info dictionaries with name and description
        """
        if not self.use_tools or not HAS_TOOLS:
            return []

        tools = []
        for name, tool in tool_registry.get_all().items():
            tools.append({
                "name": name,
                "description": tool.description
            })
        return tools

    def _integrate_tool_in_response(
        self,
        session: "TutoringSession",
        student_message: str,
        tool_name: str,
        tool_result: "ToolResult"
    ) -> Optional[TutorResponse]:
        """
        Generate a response that integrates tool results.

        The tutor uses tool results as context but doesn't just show raw results.
        Instead, it uses them to guide the student Socratically.

        Args:
            session: Current tutoring session
            student_message: Student's original message
            tool_name: Name of tool that was used
            tool_result: Result from tool execution

        Returns:
            TutorResponse incorporating tool results
        """
        if not tool_result or not tool_result.success:
            return None

        formatted_result = self._format_tool_result(tool_result, tool_name)

        # Build prompt that incorporates tool result
        prompt = f"""Ты — сократический репетитор. Ученик задал вопрос, и ты использовал инструмент для получения информации.

Задача: {session.task.problem if session.task else "Нет активной задачи"}
Сообщение ученика: {student_message}
Результат инструмента: {formatted_result}

ВАЖНО: Не показывай ученику сырой результат инструмента напрямую!
Используй эту информацию, чтобы задать наводящий вопрос или дать подсказку.
Придерживайся сократического метода — направляй, а не давай ответ.

Ответь в JSON формате:
{{"move": "scaffolding|hint|problematize|encourage", "message": "твой ответ ученику"}}
"""

        try:
            raw_response = self._call_llm(prompt, json_mode=True)
            response_data = json.loads(raw_response)

            return TutorResponse(
                move=TutorMove(response_data.get("move", "scaffolding")),
                message=response_data["message"],
                internal_reasoning=f"Tool used: {tool_name}",
                is_telling=False
            )

        except Exception as e:
            logger.warning(f"Failed to integrate tool result: {e}")
            return None

    # === Break Suggestion Feature (T036) ===

    # Break suggestion thresholds
    BREAK_SUGGESTION_THRESHOLDS = {
        "session_duration_minutes": 30,      # Suggest break after 30 minutes
        "max_consecutive_errors": 4,         # Suggest break after 4 errors in a row
        "cognitive_overload_score": 0.85,    # Suggest break at high cognitive load
        "response_time_increase_ratio": 1.5, # 50% slowdown triggers suggestion
    }

    # Break suggestion messages (Russian)
    BREAK_MESSAGES = {
        "long_session": (
            "Ты уже занимаешься довольно долго! Может, стоит сделать небольшой перерыв? "
            "Отдых помогает лучше усваивать материал. Вернёшься через 5-10 минут?"
        ),
        "cognitive_overload": (
            "Я заметил, что задача даётся сложнее. Это нормально! "
            "Иногда полезно отвлечься на несколько минут - мозг продолжает работать в фоне. "
            "Хочешь сделать перерыв?"
        ),
        "frustration": (
            "Вижу, что ты устал или расстроен. Давай отдохнём немного! "
            "После перерыва всё станет понятнее. Вернёшься когда будешь готов."
        ),
        "encouragement_after_break": (
            "С возвращением! Давай продолжим. Где мы остановились?"
        ),
    }

    def should_suggest_break(
        self,
        session: TutoringSession,
        session_memory: Optional["SessionMemory"] = None,
        cognitive_load_score: float = 0.5
    ) -> tuple[bool, str]:
        """
        Check if a break should be suggested.

        Args:
            session: Current tutoring session
            session_memory: Session memory with timing data (optional)
            cognitive_load_score: Current cognitive load score (0-1)

        Returns:
            Tuple of (should_suggest, reason)
        """
        # Check cognitive overload
        if cognitive_load_score >= self.BREAK_SUGGESTION_THRESHOLDS["cognitive_overload_score"]:
            return True, "cognitive_overload"

        # Check consecutive errors
        consecutive_errors = self._count_consecutive_errors(session)
        if consecutive_errors >= self.BREAK_SUGGESTION_THRESHOLDS["max_consecutive_errors"]:
            return True, "frustration"

        # Check session duration (if session_memory available)
        if session_memory:
            duration = session_memory.get_session_duration_minutes()
            if duration >= self.BREAK_SUGGESTION_THRESHOLDS["session_duration_minutes"]:
                # Also check if response times are increasing
                trend = session_memory.get_response_time_trend()
                if trend == "increasing":
                    return True, "long_session"

            # Check explicit should_suggest_break from session memory
            if session_memory.should_suggest_break():
                return True, "long_session"

        # Check session based indicators
        if len(session.conversation) > 20:  # Many turns
            # Calculate rough duration based on turns
            estimated_minutes = len(session.conversation) * 1.5  # ~1.5 min per turn
            if estimated_minutes >= self.BREAK_SUGGESTION_THRESHOLDS["session_duration_minutes"]:
                return True, "long_session"

        return False, ""

    def generate_break_suggestion(self, reason: str) -> TutorResponse:
        """
        Generate a break suggestion response.

        Args:
            reason: The reason for suggesting a break

        Returns:
            TutorResponse with break suggestion message
        """
        message = self.BREAK_MESSAGES.get(reason, self.BREAK_MESSAGES["cognitive_overload"])

        return TutorResponse(
            move=TutorMove.ENCOURAGE,  # Break suggestion is a form of encouragement
            message=message,
            internal_reasoning=f"Break suggested due to: {reason}",
            is_telling=False
        )

    def handle_return_from_break(self, session: TutoringSession) -> TutorResponse:
        """
        Handle student returning from a break.

        Args:
            session: Current tutoring session

        Returns:
            Welcome-back response
        """
        # Reset scaffolding state for fresh start
        self._reset_scaffolding()

        # Generate encouraging welcome back message
        last_topic = session.task.topic if hasattr(session.task, 'topic') else "задача"

        return TutorResponse(
            move=TutorMove.ENCOURAGE,
            message=f"С возвращением! Ты отдохнул? Давай продолжим работать над темой '{last_topic}'. "
                    f"Напомни, где ты остановился или просто попробуй ещё раз.",
            internal_reasoning="Welcoming student back from break",
            is_telling=False
        )

    def _check_and_suggest_break(
        self,
        session: TutoringSession,
        student_message: str,
        session_memory: Optional["SessionMemory"] = None,
        cognitive_load_score: float = 0.5
    ) -> Optional[TutorResponse]:
        """
        Check if break should be suggested and return response if so.

        This is called at the beginning of generate_response to potentially
        intercept normal response generation with a break suggestion.

        Args:
            session: Current tutoring session
            student_message: Latest student message
            session_memory: Session memory for timing data
            cognitive_load_score: Current cognitive load score

        Returns:
            TutorResponse if break should be suggested, None otherwise
        """
        # Don't suggest break if student just returned or is on first message
        if len(session.conversation) < 4:
            return None

        # Don't suggest break if we just suggested one
        if session.conversation:
            last_tutor_msg = None
            for turn in reversed(session.conversation):
                if turn.role == "tutor":
                    last_tutor_msg = turn.content
                    break

            if last_tutor_msg and "перерыв" in last_tutor_msg.lower():
                return None

        # Check if student is responding to break suggestion
        if any(phrase in student_message.lower() for phrase in
               ["вернулся", "готов", "продолжим", "продолжать", "после перерыва"]):
            return self.handle_return_from_break(session)

        # Check if break should be suggested
        should_break, reason = self.should_suggest_break(
            session, session_memory, cognitive_load_score
        )

        if should_break:
            logger.info(f"Suggesting break to student: reason={reason}")
            return self.generate_break_suggestion(reason)

        return None

    def _select_strategy(
        self,
        situation: Dict[str, Any],
        session: TutoringSession
    ) -> str:
        """
        Select tutoring strategy based on situation.
        
        Priority:
        1. Student solved → encourage
        2. Student frustrated → hint or tell (last resort)
        3. Student made error → rectify
        4. Student making progress → encourage + scaffold
        5. Student asking question → problematize
        6. Too many attempts → hint
        7. Default → scaffolding
        """
        
        # Student solved it!
        if situation.get("student_state") == "solved":
            return "encourage"
        
        # Student is frustrated - be supportive
        if situation.get("emotional_state") == "frustrated":
            if session.hints_used < self.max_hints_before_tell:
                return "hint"
            else:
                return "tell"  # ⚠️ Last resort
        
        # Student used wrong method (answer correct but method wrong)
        if situation.get("error_type") == "wrong_method":
            return "rectify"

        # Student made an error
        if situation.get("student_state") == "made_error":
            return "rectify"
        
        # Student is making progress
        if situation.get("student_state") == "partial_progress":
            return "encourage"
        
        # Student is asking a question - answer with a question!
        if situation.get("is_asking_question"):
            return "problematize"
        
        # Too many attempts without progress
        if session.attempts > self.max_attempts_before_hint:
            if session.hints_used < self.max_hints_before_tell:
                return "hint"
            elif session.hints_used >= self.max_hints_before_tell:
                return "tell"  # ⚠️ Only after all hints exhausted
        
        # Default: Guide with questions
        return "scaffolding"
    
    def _build_prompt(
        self,
        session: TutoringSession,
        student_message: str,
        situation: Dict[str, Any],
        strategy: str,
        student_profile: Optional[StudentProfile],
        rag_context: Optional[Any] = None
    ) -> str:
        """Build prompt for LLM."""

        # Format conversation history (last 10 turns)
        history_turns = session.conversation[-10:]
        history = "\n".join([
            f"{turn.role.upper()}: {turn.content}"
            for turn in history_turns
        ]) if history_turns else "No previous conversation."

        # Get available hints (из задачи + из RAG)
        available_hints = session.task.hints[session.hints_used:] if session.task.hints else []

        # Добавляем подсказки из RAG
        if rag_context and hasattr(rag_context, 'hints'):
            for hint in rag_context.hints[:2]:  # Максимум 2 из RAG
                if hasattr(hint, 'content'):
                    available_hints.append(f"[RAG] {hint.content}")

        hints_str = "\n".join([
            f"{i+1}. {hint}"
            for i, hint in enumerate(available_hints)
        ]) if available_hints else "No hints available."

        # Build common mistakes string (из задачи + из RAG)
        mistakes_list = list(session.task.common_mistakes) if session.task.common_mistakes else []

        # Добавляем типичные ошибки из RAG
        if rag_context and hasattr(rag_context, 'misconceptions'):
            for misc in rag_context.misconceptions[:2]:  # Максимум 2 из RAG
                if hasattr(misc, 'error_pattern'):
                    mistakes_list.append(f"[RAG] {misc.error_pattern}")

        mistakes_str = "\n".join(mistakes_list) if mistakes_list else "None specified."

        # Notation context from SKI
        notation_text = ""
        try:
            from src.knowledge.ski import get_ski
            ski = get_ski()
            topic = session.task.topic if hasattr(session.task, 'topic') else None
            if topic:
                notation = ski.get_notation_context(topic)
                if notation:
                    lines = ["## НОТАЦИЯ (используй эти обозначения):"]
                    for sym, desc in notation.items():
                        lines.append(f"- {sym}: {desc}")
                    notation_text = "\n".join(lines)
        except Exception as e:
            logger.debug(f"Notation retrieval skipped: {e}")

        # Dynamic few-shot examples
        few_shot_text = ""
        try:
            from src.knowledge.few_shot_bank import get_few_shot_bank
            bank = get_few_shot_bank()
            topic = session.task.topic if hasattr(session.task, 'topic') else None
            skill = None
            if hasattr(session.task, 'skills') and session.task.skills:
                skill = session.task.skills[0]
            examples = bank.retrieve_structured(
                topic=topic,
                difficulty=session.task.difficulty if hasattr(session.task, 'difficulty') else None,
                skill=skill,
                limit=2,
            )
            if examples:
                few_shot_text = bank.format_for_prompt(examples)
        except Exception as e:
            logger.debug(f"Few-shot retrieval skipped: {e}")

        prompt = TUTOR_RESPONSE_PROMPT.format(
            problem=session.task.problem,
            solution=session.task.solution,
            answer=session.task.answer,
            common_mistakes=mistakes_str,
            few_shot_examples=few_shot_text,
            notation_context=notation_text,
            conversation_history=history,
            student_message=student_message,
            attempts=session.attempts,
            hints_used=session.hints_used,
            max_hints=len(session.task.hints) if session.task.hints else 0,
            student_state=situation.get("student_state", "unknown"),
            strategy=strategy,
            available_hints=hints_str
        )

        return prompt
    
    def _is_revealing_answer(self, message: str, task: Task) -> bool:
        """
        Check if response accidentally reveals the answer.
        
        This is a safety check to ensure we maintain Socratic method.
        """
        answer_str = str(task.answer).lower().strip()
        message_lower = message.lower()
        
        # Skip check for very short answers (could be coincidental)
        if len(answer_str) < 3:
            return False
        
        # Direct answer check
        if answer_str in message_lower:
            return True
        
        # Check for solution-revealing patterns
        revealing_patterns = [
            f"the answer is",
            f"solution is",
            f"equals {answer_str}",
            f"= {answer_str}",
            f"result is {answer_str}",
        ]
        
        for pattern in revealing_patterns:
            if pattern in message_lower:
                return True
        
        return False
    
    def _sanitize_response(
        self,
        response: TutorResponse,
        task: Task
    ) -> TutorResponse:
        """
        Sanitize response that might reveal the answer.
        
        Replace with a safe scaffolding response.
        """
        safe_message = (
            "Let's think about this step by step. "
            "What approach have you tried so far? "
            "What do you think is the key insight needed here?"
        )
        
        return TutorResponse(
            move=TutorMove.SCAFFOLDING,
            message=safe_message,
            internal_reasoning="Original response sanitized to avoid answer leak",
            is_telling=False
        )

    # === T051: Language-Aware Response Formatting ===

    def format_response_for_language(
        self,
        message: str,
        student_input: str,
        force_russian: bool = True
    ) -> str:
        """
        Format response with appropriate language and math notation.

        Args:
            message: Response text to format
            student_input: Student's input (for language detection)
            force_russian: Force Russian notation (default for MITS)

        Returns:
            Formatted message with correct notation
        """
        if not HAS_LANGUAGE_DETECTOR:
            # Fallback: assume Russian
            return convert_to_russian_notation(message) if force_russian else message

        # Detect language from student input
        detection = detect_language(student_input)

        # Determine if we should use Russian notation
        use_russian = (
            force_russian or
            detection.language == Language.RUSSIAN or
            should_use_russian_notation(student_input)
        )

        if use_russian:
            return convert_to_russian_notation(message)

        return message

    def get_language_context(self, student_input: str) -> Dict[str, Any]:
        """
        Get language context for response generation.

        Returns:
            Dictionary with language detection results
        """
        if not HAS_LANGUAGE_DETECTOR:
            return {
                "language": "ru",
                "use_russian_notation": True,
                "confidence": 1.0
            }

        detection = detect_language(student_input)

        return {
            "language": detection.language.value,
            "use_russian_notation": should_use_russian_notation(student_input),
            "confidence": detection.confidence,
            "math_notation": detection.math_notation.value,
            "has_russian_math": detection.has_russian_math,
            "has_english_math": detection.has_english_math
        }

    def generate_localized_hint(
        self,
        hint_template: str,
        topic: str,
        level: str = "conceptual",
        context: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Generate a localized hint from template.

        Args:
            hint_template: Template string with placeholders
            topic: Mathematical topic
            level: Scaffolding level (conceptual, procedural, specific)
            context: Variables to substitute in template

        Returns:
            Formatted hint in Russian
        """
        # Load Russian templates
        try:
            import json
            from pathlib import Path

            templates_path = Path("data/knowledge/hints/russian_templates.json")
            if templates_path.exists():
                with open(templates_path, "r", encoding="utf-8") as f:
                    templates = json.load(f)

                # Get topic-specific hints if available
                topic_hints = templates.get("topic_specific_hints", {}).get(topic, {})
                level_hints = topic_hints.get(level, [])

                if level_hints:
                    import random
                    hint_template = random.choice(level_hints)

        except Exception as e:
            logger.warning(f"Could not load Russian templates: {e}")

        # Substitute context variables
        if context:
            for key, value in context.items():
                hint_template = hint_template.replace(f"{{{key}}}", str(value))

        # Convert to Russian notation
        return convert_to_russian_notation(hint_template)
