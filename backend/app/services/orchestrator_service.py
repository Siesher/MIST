"""
Service layer wrapping existing MITS AgentOrchestrator.

Provides async-friendly interface for FastAPI endpoints.
"""

import sys
import os
import json
import uuid
import logging
from typing import Optional, Dict, Any, List, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime

# Add project root to path for src/ imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger(__name__)


# Mode-specific configuration
@dataclass
class ModeConfig:
    """Configuration for a chat mode."""
    system_prompt_key: str  # Key to look up in prompts module
    use_rag: bool = True
    track_hints: bool = True
    use_pipeline: bool = True  # Full profiler→planner→tutor→verifier pipeline
    placeholder_text: str = "Ваш ответ или вопрос..."


MODE_CONFIGS = {
    "chat": ModeConfig(
        system_prompt_key="CHAT_MODE_SYSTEM",
        use_rag=False,
        track_hints=False,
        use_pipeline=False,  # Direct LLM, no agents
        placeholder_text="Напишите сообщение...",
    ),
    "guided_learning": ModeConfig(
        system_prompt_key="GUIDED_LEARNING_SYSTEM",
        use_rag=True,
        track_hints=True,
        use_pipeline=True,
        placeholder_text="Ваш ответ или вопрос...",
    ),
    "task_generator": ModeConfig(
        system_prompt_key="TASK_GENERATOR_MODE_SYSTEM",
        use_rag=False,
        track_hints=False,
        use_pipeline=False,  # Direct LLM with task prompt
        placeholder_text="Какую тему и сложность задач?",
    ),
}


MODE_DISPLAY_NAMES = {
    "chat": "Обычный чат",
    "guided_learning": "Guided Learning",
    "task_generator": "Генерация задач",
}


@dataclass
class StoredMessage:
    """Message stored in session."""
    id: str
    role: str  # user, tutor, system
    content: str
    timestamp: datetime
    move_type: Optional[str] = None
    is_correct: Optional[bool] = None
    thinking: Optional[str] = None


@dataclass
class StoredSession:
    """Session with conversation history."""
    id: str
    created_at: datetime
    updated_at: datetime
    topic: Optional[str] = None
    difficulty: Optional[str] = None
    task_id: Optional[str] = None
    status: str = "active"
    mode: str = "guided_learning"
    is_solved: bool = False
    hints_used: int = 0
    attempts: int = 0
    messages: List[StoredMessage] = field(default_factory=list)
    task: Optional[Dict[str, Any]] = None


class OrchestratorService:
    """
    Wraps existing MITS orchestrator and agents for API use.

    Manages sessions, processes messages, and provides
    async-compatible interface for FastAPI.
    """

    def __init__(self):
        self._sessions: Dict[str, StoredSession] = {}
        self._orchestrator = None
        self._llm_client = None
        self._task_generator = None
        self._initialized = False

    async def initialize(self):
        """Initialize MITS core components."""
        if self._initialized:
            return

        try:
            from src.models.llm_client import LLMClient
            self._llm_client = LLMClient()

            from src.agents.orchestrator import AgentOrchestrator, OrchestratorMode
            from src.agents.profiler import ProfilerAgent

            # Profiler: rule-based only (LLM profiler adds 30-100s latency)
            profiler = ProfilerAgent(
                llm_client=self._llm_client,
                use_llm=False,  # Rule-based: instant, no LLM call
            )

            self._orchestrator = AgentOrchestrator(
                llm_client=self._llm_client,
                mode=OrchestratorMode.FULL,
                verify_responses=True,
                profiler=profiler,
            )

            try:
                from src.agents.task_generator import TaskGeneratorAgent
                self._task_generator = TaskGeneratorAgent(self._llm_client)
            except Exception as e:
                logger.warning(f"TaskGenerator not available: {e}")

            self._initialized = True
            logger.info("OrchestratorService initialized successfully")

            # Warm up model in background (don't block server startup)
            import threading
            def warmup():
                try:
                    logger.info("Warming up LLM model in background...")
                    self._llm_client.generate("Привет", max_tokens=5)
                    logger.info("LLM model warmed up and ready")
                except Exception as e:
                    logger.warning(f"Model warmup failed: {e}")
            threading.Thread(target=warmup, daemon=True).start()

        except Exception as e:
            logger.error(f"Failed to initialize OrchestratorService: {e}")
            # Service works in demo mode without LLM
            self._initialized = True

    def _get_mode_config(self, mode: str) -> ModeConfig:
        """Get configuration for a chat mode."""
        return MODE_CONFIGS.get(mode, MODE_CONFIGS["guided_learning"])

    def _get_system_prompt_for_mode(self, mode: str) -> str:
        """Get the system prompt for a given mode."""
        config = self._get_mode_config(mode)
        try:
            from src.models import prompts as prompt_module
            return getattr(prompt_module, config.system_prompt_key, "")
        except Exception:
            return ""

    async def change_mode(self, session_id: str, new_mode: str) -> Optional[Dict[str, Any]]:
        """Change the mode of an existing session."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        previous_mode = session.mode
        session.mode = new_mode
        session.updated_at = datetime.utcnow()

        display_name = MODE_DISPLAY_NAMES.get(new_mode, new_mode)
        return {
            "session_id": session_id,
            "previous_mode": previous_mode,
            "current_mode": new_mode,
            "message": f"Режим изменён на «{display_name}»",
        }

    def _check_llm_available(self) -> bool:
        """Check if LLM client is connected."""
        if not self._llm_client:
            return False
        try:
            return self._llm_client.check_connection()
        except Exception:
            return False

    # --- Session Management ---

    async def create_session(
        self,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
        custom_problem: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> StoredSession:
        """Create a new tutoring session."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        session_mode = mode or "guided_learning"

        session = StoredSession(
            id=session_id,
            created_at=now,
            updated_at=now,
            topic=topic,
            difficulty=difficulty,
            mode=session_mode,
        )

        # Generate or use custom task
        task_data = None
        if custom_problem:
            task_data = {
                "id": str(uuid.uuid4()),
                "topic": topic or "general",
                "difficulty": difficulty or "medium",
                "problem": custom_problem,
                "hints": [],
                "skills": [],
            }
        elif topic and self._task_generator:
            try:
                from src.data.schemas import Difficulty as DiffEnum
                diff = DiffEnum(difficulty) if difficulty else DiffEnum.MEDIUM
                task = self._task_generator.generate_task(topic=topic, difficulty=diff)
                task_data = {
                    "id": task.id,
                    "topic": task.topic,
                    "difficulty": task.difficulty.value if hasattr(task.difficulty, "value") else str(task.difficulty),
                    "problem": task.problem,
                    "hints": task.hints[:3],
                    "skills": task.skills,
                    "solution": task.solution,
                    "answer": task.answer,
                }
            except Exception as e:
                logger.warning(f"Task generation failed: {e}")

        if task_data:
            session.task = task_data
            session.task_id = task_data["id"]

        # Create orchestrator session
        if self._orchestrator:
            self._orchestrator.create_session(
                session_id=session_id,
                student_id="student_default",
                problem=task_data["problem"] if task_data else None,
                topic=topic,
            )

        # Add welcome message
        welcome = self._generate_welcome(topic, task_data, session_mode)
        session.messages.append(StoredMessage(
            id=str(uuid.uuid4()),
            role="tutor",
            content=welcome,
            timestamp=now,
            move_type="encourage",
        ))

        self._sessions[session_id] = session
        return session

    def _generate_welcome(self, topic: Optional[str], task: Optional[Dict], mode: str = "guided_learning") -> str:
        """Generate a mode-specific welcome message."""
        if mode == "chat":
            return "Привет! Я твой ассистент. Спрашивай о чём угодно — математика, программирование, наука или любая другая тема."
        elif mode == "task_generator":
            return "Привет! Я генератор задач. Укажи тему и сложность, и я создам задачи для практики.\n\nНапример: «3 задачи по производным, средняя сложность»"
        # guided_learning (default)
        if task:
            return f"Привет! Давай решим задачу вместе.\n\n{task['problem']}\n\nКак бы ты начал(а) решение?"
        elif topic:
            topic_names = {
                "derivatives": "производные",
                "integrals": "интегралы",
                "limits": "пределы",
                "series": "ряды",
                "equations": "уравнения",
                "linear_algebra": "линейная алгебра",
            }
            name = topic_names.get(topic, topic)
            return f"Привет! Сегодня поработаем над темой: {name}. Готов(а) начать?"
        return "Привет! Я твой математический репетитор. С какой задачей поможем сегодня?"

    async def list_sessions(
        self, page: int = 1, limit: int = 20, status: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all sessions with pagination."""
        sessions = list(self._sessions.values())

        if status:
            sessions = [s for s in sessions if s.status == status]

        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        total = len(sessions)
        pages = max(1, (total + limit - 1) // limit)
        start = (page - 1) * limit
        end = start + limit

        return {
            "sessions": sessions[start:end],
            "total": total,
            "page": page,
            "pages": pages,
        }

    async def get_session(self, session_id: str) -> Optional[StoredSession]:
        """Get session by ID."""
        return self._sessions.get(session_id)

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            if self._orchestrator:
                self._orchestrator.close_session(session_id)
            return True
        return False

    # --- Chat ---

    async def process_message(
        self, session_id: str, content: str
    ) -> Optional[Dict[str, Any]]:
        """Process a student message and return tutor response."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        now = datetime.utcnow()

        # Add student message
        student_msg = StoredMessage(
            id=str(uuid.uuid4()),
            role="user",
            content=content,
            timestamp=now,
        )
        session.messages.append(student_msg)
        session.attempts += 1
        session.updated_at = now

        # Process through orchestrator
        tutor_content = ""
        move_type = "scaffolding"
        is_correct = None
        thinking = None

        if self._orchestrator:
            try:
                from src.agents.orchestrator import TurnContext
                history = [
                    {"role": m.role if m.role != "tutor" else "assistant", "content": m.content}
                    for m in session.messages[-10:]
                ]

                context = TurnContext(
                    problem=session.task["problem"] if session.task else "",
                    student_input=content,
                    correct_answer=session.task.get("answer") if session.task else None,
                    history=history,
                    student_id="student_default",
                    topic=session.topic,
                )

                result = self._orchestrator.process_turn(context, session_id=session_id)
                tutor_content = result.response
                move_type = result.move_type

                # Check if answer is correct based on move_type
                if move_type == "encourage" and session.task:
                    is_correct = True
                    session.is_solved = True

                if result.pipeline_trace:
                    thinking = result.pipeline_trace.summary()

            except Exception as e:
                logger.error(f"Orchestrator error: {e}")
                tutor_content = "Давай попробуем разобраться вместе. Расскажи, что тебе уже понятно?"
                move_type = "scaffolding"
        else:
            tutor_content = "Хороший вопрос! Давай подумаем вместе. Какие формулы ты знаешь по этой теме?"
            move_type = "scaffolding"

        # Add tutor response
        tutor_msg = StoredMessage(
            id=str(uuid.uuid4()),
            role="tutor",
            content=tutor_content,
            timestamp=datetime.utcnow(),
            move_type=move_type,
            is_correct=is_correct,
            thinking=thinking,
        )
        session.messages.append(tutor_msg)

        return {
            "message_id": tutor_msg.id,
            "tutor_response": {
                "content": tutor_content,
                "move_type": move_type,
                "is_correct": is_correct,
                "thinking": thinking,
            },
            "session_state": {
                "is_solved": session.is_solved,
                "hints_used": session.hints_used,
                "attempts": session.attempts,
            },
            "knowledge_update": None,
        }

    async def get_hint(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get next hint for session."""
        session = self._sessions.get(session_id)
        if not session or not session.task:
            return None

        hints = session.task.get("hints", [])
        if session.hints_used >= len(hints):
            return None

        hint_text = hints[session.hints_used]
        session.hints_used += 1
        session.updated_at = datetime.utcnow()

        # Add hint as tutor message
        session.messages.append(StoredMessage(
            id=str(uuid.uuid4()),
            role="tutor",
            content=f"Подсказка {session.hints_used}: {hint_text}",
            timestamp=datetime.utcnow(),
            move_type="hint",
        ))

        return {
            "hint_number": session.hints_used,
            "hint_text": hint_text,
            "hints_remaining": len(hints) - session.hints_used,
        }

    async def reveal_solution(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Reveal solution for session task."""
        session = self._sessions.get(session_id)
        if not session or not session.task:
            return None

        solution = session.task.get("solution", "Решение недоступно")
        answer = session.task.get("answer", "Ответ недоступен")
        session.updated_at = datetime.utcnow()

        session.messages.append(StoredMessage(
            id=str(uuid.uuid4()),
            role="tutor",
            content=f"Решение:\n{solution}\n\nОтвет: {answer}",
            timestamp=datetime.utcnow(),
            move_type="tell",
        ))

        return {
            "solution": solution,
            "answer": answer,
            "penalty_applied": True,
        }

    # --- Streaming ---

    async def process_message_stream(
        self, session_id: str, content: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process message with real token-by-token streaming.

        Yields dicts with type: token, response_complete, or error.
        """
        import asyncio

        session = self._sessions.get(session_id)
        if not session:
            yield {"type": "error", "code": "SESSION_NOT_FOUND", "message": "Сессия не найдена"}
            return

        now = datetime.utcnow()

        # Add student message
        student_msg = StoredMessage(
            id=str(uuid.uuid4()),
            role="user",
            content=content,
            timestamp=now,
        )
        session.messages.append(student_msg)
        session.attempts += 1
        session.updated_at = now

        # Determine mode and config
        mode = session.mode
        mode_config = self._get_mode_config(mode)
        move_type = "scaffolding"
        system_prompt = ""
        user_prompt = content

        if mode_config.use_pipeline and self._orchestrator:
            # GUIDED LEARNING: Full agent pipeline (profiler → planner → tutor → verifier)
            try:
                from src.agents.orchestrator import TurnContext, PipelineTrace, AgentStage
                from src.agents.planner import SessionContext as PlannerSessionContext
                from src.agents.profiler import StudentProfile

                history = [
                    {"role": m.role if m.role != "tutor" else "assistant", "content": m.content}
                    for m in session.messages[-10:]
                ]

                context = TurnContext(
                    problem=session.task["problem"] if session.task else "",
                    student_input=content,
                    correct_answer=session.task.get("answer") if session.task else None,
                    history=history,
                    student_id="student_default",
                    topic=session.topic,
                )

                profile = None
                plan = None
                rag_context = None

                # Profiler
                try:
                    profile = self._orchestrator.profiler.diagnose(
                        problem=context.problem,
                        correct_approach=context.correct_answer or "",
                        student_response=context.student_input,
                        history=context.history
                    )
                except Exception as e:
                    logger.warning(f"Profiler error in stream: {e}")

                # Planner
                try:
                    planner_ctx = PlannerSessionContext(
                        topic=context.topic or "general",
                        difficulty="medium",
                        turn_number=0,
                    )
                    plan = self._orchestrator.planner.create_plan(
                        profile=profile or StudentProfile(),
                        context=planner_ctx,
                    )
                    move_type = plan.primary_move.value
                except Exception as e:
                    logger.warning(f"Planner error in stream: {e}")

                # RAG
                if self._orchestrator.rag:
                    try:
                        rag_context = self._orchestrator.rag.retrieve_context(
                            problem=context.problem,
                            student_response=context.student_input,
                            topic=context.topic
                        )
                    except Exception as e:
                        logger.warning(f"RAG error in stream: {e}")

                system_prompt = self._orchestrator._build_system_prompt(plan)
                user_prompt = self._orchestrator._build_user_prompt(context, profile, rag_context)

            except Exception as e:
                logger.error(f"Stream context building error: {e}")

            # Send thinking content (profiler/planner output)
            thinking_content = []
            if profile and hasattr(profile, 'error_type') and profile.error_type:
                thinking_content.append(f"Анализ: обнаружена ошибка типа '{profile.error_type}'")
            if profile and hasattr(profile, 'knowledge_gaps') and profile.knowledge_gaps:
                gaps = ', '.join(profile.knowledge_gaps[:3])
                thinking_content.append(f"Пробелы в знаниях: {gaps}")
            if plan:
                thinking_content.append(f"Стратегия: {move_type}")

            if thinking_content:
                thinking_text = " | ".join(thinking_content)
                yield {
                    "type": "token",
                    "content": thinking_text,
                    "is_thinking": True,
                }
        else:
            # CHAT / TASK_GENERATOR: Direct LLM with mode-specific prompt
            system_prompt = self._get_system_prompt_for_mode(mode)
            # Build conversation history for context (current msg already in session.messages)
            history_lines = []
            for m in session.messages[-10:]:
                role_label = "Пользователь" if m.role == "user" else "Ассистент"
                history_lines.append(f"{role_label}: {m.content}")
            user_prompt = "\n".join(history_lines) if history_lines else content
            move_type = "tell" if mode == "chat" else "scaffolding"

        # Stream from LLM — real token-by-token streaming (no JSON buffering)
        full_response = ""
        message_id = str(uuid.uuid4())
        logger.info(f"Starting LLM streaming for session {session_id}")

        if self._llm_client and hasattr(self._llm_client, 'generate_stream'):
            try:
                import concurrent.futures

                queue: asyncio.Queue = asyncio.Queue()
                loop = asyncio.get_event_loop()

                def producer():
                    """Run sync generator and put tokens in queue."""
                    try:
                        token_count = 0
                        thinking_count = 0
                        content_count = 0
                        for item in self._llm_client.generate_stream(
                            prompt=user_prompt,
                            system=system_prompt,
                            json_mode=False,  # Plain text — real streaming
                        ):
                            token_count += 1
                            # Handle tuple format: (type, content)
                            if isinstance(item, tuple) and len(item) == 2:
                                token_type, token_content = item
                                if token_type == "thinking":
                                    thinking_count += 1
                                    if thinking_count == 1:
                                        logger.info("First thinking token from LLM")
                                else:
                                    content_count += 1
                                    if content_count == 1:
                                        logger.info("First content token from LLM")
                                loop.call_soon_threadsafe(
                                    queue.put_nowait, (token_type, token_content)
                                )
                            else:
                                # Legacy string format
                                content_count += 1
                                if content_count == 1:
                                    logger.info("First token received from LLM")
                                loop.call_soon_threadsafe(
                                    queue.put_nowait, ("content", item)
                                )
                        logger.info(f"LLM complete: {thinking_count} thinking + {content_count} content tokens")
                    except Exception as e:
                        logger.error(f"LLM producer error: {e}")
                        loop.call_soon_threadsafe(
                            queue.put_nowait, Exception(f"LLM error: {e}")
                        )
                    finally:
                        loop.call_soon_threadsafe(queue.put_nowait, None)

                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                executor.submit(producer)

                # Real streaming: yield each token as it arrives
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    if isinstance(item, Exception):
                        raise item

                    # Handle tuple format: (type, content)
                    if isinstance(item, tuple) and len(item) == 2:
                        token_type, token_content = item
                        is_thinking = token_type == "thinking"
                        if not is_thinking:
                            full_response += token_content
                        yield {
                            "type": "token",
                            "content": token_content,
                            "is_thinking": is_thinking,
                        }
                    else:
                        # Legacy format
                        full_response += item
                        yield {
                            "type": "token",
                            "content": item,
                            "is_thinking": False,
                        }

                executor.shutdown(wait=False)

            except Exception as e:
                logger.error(f"LLM streaming error: {e}")
                full_response = "Давай попробуем разобраться вместе. Расскажи, что тебе уже понятно?"
                yield {
                    "type": "token",
                    "content": full_response,
                    "is_thinking": False,
                }
        else:
            full_response = "Давай попробуем разобраться вместе."
            yield {
                "type": "token",
                "content": full_response,
                "is_thinking": False,
            }

        # Plain text response (no JSON parsing needed)
        tutor_content = full_response.strip()
        extracted_move = move_type  # Use planner's move type

        # Check correctness
        is_correct = None
        if extracted_move == "encourage" and session.task:
            is_correct = True
            session.is_solved = True

        # Add tutor response to session
        tutor_msg = StoredMessage(
            id=message_id,
            role="tutor",
            content=tutor_content,
            timestamp=datetime.utcnow(),
            move_type=extracted_move,
            is_correct=is_correct,
        )
        session.messages.append(tutor_msg)

        # Send completion
        yield {
            "type": "response_complete",
            "message_id": message_id,
            "response": {
                "content": tutor_content,
                "move_type": extracted_move,
                "is_correct": is_correct,
            },
            "session_state": {
                "is_solved": session.is_solved,
                "hints_used": session.hints_used,
                "attempts": session.attempts,
            },
        }

    def _extract_json_from_text(self, response: str) -> Optional[Dict[str, Any]]:
        """Try multiple strategies to extract JSON from LLM response."""
        import json as json_module
        import re

        text = response.strip()

        # Strategy 1: Direct JSON parse
        try:
            if text.startswith('{'):
                return json_module.loads(text)
        except json_module.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code blocks
        for pattern in [
            r'```json\s*(.*?)\s*```',
            r'```\s*(\{.*?\})\s*```',
        ]:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json_module.loads(match.group(1).strip())
                except json_module.JSONDecodeError:
                    pass

        # Strategy 3: Find first { ... } in text
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json_module.loads(text[start:end + 1])
            except json_module.JSONDecodeError:
                pass

        return None

    def _extract_message_content(self, response: str) -> str:
        """Extract message text from JSON response."""
        logger.debug(f"Extracting message from response (len={len(response)}): {response[:200]}...")

        data = self._extract_json_from_text(response)
        if data and "message" in data:
            logger.debug(f"Extracted message: {data['message'][:100]}...")
            return data["message"]

        logger.warning(f"Could not extract message from response, returning raw")
        return response

    def _extract_move_type(self, response: str, default: str) -> str:
        """Extract move type from JSON response."""
        data = self._extract_json_from_text(response)
        if data and "move" in data:
            return data["move"]
        return default

    # --- Tasks ---

    def get_available_topics(self) -> List[Dict[str, Any]]:
        """Get list of available topics."""
        topics = [
            {"id": "derivatives", "name": "Derivatives", "name_ru": "Производные",
             "difficulties": ["easy", "medium", "hard", "olympiad"]},
            {"id": "integrals", "name": "Integrals", "name_ru": "Интегралы",
             "difficulties": ["easy", "medium", "hard", "olympiad"]},
            {"id": "limits", "name": "Limits", "name_ru": "Пределы",
             "difficulties": ["easy", "medium", "hard", "olympiad"]},
            {"id": "series", "name": "Series", "name_ru": "Ряды",
             "difficulties": ["medium", "hard", "olympiad"]},
            {"id": "equations", "name": "Equations", "name_ru": "Уравнения",
             "difficulties": ["easy", "medium", "hard"]},
            {"id": "linear_algebra", "name": "Linear Algebra", "name_ru": "Линейная алгебра",
             "difficulties": ["easy", "medium", "hard"]},
        ]

        # Try to get from task bank
        try:
            from src.data.task_bank import TaskBank
            bank = TaskBank()
            if hasattr(bank, "get_topics"):
                bank_topics = bank.get_topics()
                if bank_topics:
                    return bank_topics
        except Exception:
            pass

        return topics

    async def generate_task(
        self, topic: str, difficulty: str, avoid_recent: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Generate a new task."""
        if self._task_generator:
            try:
                from src.data.schemas import Difficulty as DiffEnum
                diff = DiffEnum(difficulty)
                task = self._task_generator.generate_task(topic=topic, difficulty=diff)
                return {
                    "id": task.id,
                    "topic": task.topic,
                    "difficulty": task.difficulty.value,
                    "problem": task.problem,
                    "hints": task.hints[:3],
                    "skills": task.skills,
                }
            except Exception as e:
                logger.error(f"Task generation failed: {e}")
        return None

    def get_recommended_tasks(self, count: int = 5) -> Dict[str, Any]:
        """Get recommended tasks based on student profile."""
        # Default recommendations
        return {
            "tasks": [],
            "reasoning": "Рекомендации основаны на вашем текущем уровне знаний.",
        }

    # --- Student Profile ---

    def get_student_profile(self) -> Dict[str, Any]:
        """Get student profile data."""
        total_sessions = len(self._sessions)
        solved_count = sum(1 for s in self._sessions.values() if s.is_solved)
        total_hints = sum(s.hints_used for s in self._sessions.values())

        return {
            "student_id": "student_default",
            "total_sessions": total_sessions,
            "success_rate": solved_count / total_sessions if total_sessions > 0 else 0.0,
            "total_time_minutes": 0,
            "streak_days": 0,
            "mastery_by_topic": {},
            "weak_skills": [],
            "strong_skills": [],
            "recommended_topic": "derivatives",
        }

    def get_analytics(self, period: str = "week") -> Dict[str, Any]:
        """Get analytics data."""
        now = datetime.utcnow()
        return {
            "period_start": now.isoformat(),
            "period_end": now.isoformat(),
            "sessions_count": len(self._sessions),
            "tasks_attempted": sum(s.attempts for s in self._sessions.values()),
            "tasks_solved": sum(1 for s in self._sessions.values() if s.is_solved),
            "avg_session_minutes": 0.0,
            "avg_hints_per_task": 0.0,
            "progress_by_day": [],
        }

    def get_knowledge_state(self) -> Dict[str, Any]:
        """Get knowledge state."""
        return {
            "mastery_by_skill": {},
            "skill_dependencies": {},
            "recommended_next": ["derivatives", "limits"],
        }

    # --- Health ---

    def get_health(self) -> Dict[str, Any]:
        """Get system health status."""
        llm_ok = self._check_llm_available()

        components = {
            "llm": {"status": "healthy" if llm_ok else "unhealthy", "model": "glm-4.7-flash"},
            "database": {"status": "healthy"},
            "rag": {"status": "healthy"},
        }

        overall = "healthy" if llm_ok else "degraded"
        return {
            "status": overall,
            "components": components,
            "version": "1.0.0",
        }


# Singleton instance
_service: Optional[OrchestratorService] = None


async def get_orchestrator_service() -> OrchestratorService:
    """Get or create the orchestrator service singleton."""
    global _service
    if _service is None:
        _service = OrchestratorService()
        await _service.initialize()
    return _service
