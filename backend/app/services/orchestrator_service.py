"""
Service layer wrapping existing MITS AgentOrchestrator.

Provides async-friendly interface for FastAPI endpoints.
Sessions and messages are persisted to SQLite via SQLAlchemy.
"""

import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Add project root to path for src/ imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.models.tables import MessageTable, SessionTable  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Thinking tag utilities (supports GLM and Qwen3 formats)
# ---------------------------------------------------------------------------


def parse_thinking_tags(text: str) -> tuple:
    """Parse thinking tags from model response.

    Supports both GLM and Qwen3 formats:
    - Qwen3: <think>...</think>
    - GLM: <|思考|>...</|思考|> or similar

    Returns:
        (visible_content, thinking_content) tuple.
        If no thinking tags found, thinking_content is None.
    """
    import re

    # Qwen3 format: <think>...</think>
    think_match = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
    if think_match:
        thinking = think_match.group(1).strip()
        visible = text[think_match.end() :].strip()
        return visible, thinking

    # GLM format: various thinking markers
    for pattern in [
        r"<\|思考\|>(.*?)<\|/思考\|>",
        r"<thinking>(.*?)</thinking>",
        r"<thought>(.*?)</thought>",
    ]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            thinking = match.group(1).strip()
            visible = text[match.end() :].strip()
            return visible, thinking

    return text, None


def strip_thinking(text: str, show_thinking: bool = False) -> str:
    """Strip thinking tags from response unless debug mode.

    Args:
        text: Raw model response
        show_thinking: If True, keep thinking content (debug mode)
    """
    if show_thinking:
        return text

    visible, _ = parse_thinking_tags(text)
    return visible


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
    """Message DTO (maps to/from MessageTable)."""

    id: str
    role: str  # user, tutor, system
    content: str
    timestamp: datetime
    move_type: Optional[str] = None
    is_correct: Optional[bool] = None
    thinking: Optional[str] = None


@dataclass
class StoredSession:
    """Session DTO (maps to/from SessionTable)."""

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
    user_id: Optional[str] = None


def _row_to_session(row: SessionTable) -> StoredSession:
    """Convert ORM row to DTO."""
    messages = [
        StoredMessage(
            id=m.id,
            role=m.role,
            content=m.content,
            timestamp=m.timestamp,
            move_type=m.move_type,
            is_correct=m.is_correct,
            thinking=m.thinking,
        )
        for m in (row.messages or [])
    ]
    return StoredSession(
        id=row.id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        topic=row.topic,
        difficulty=row.difficulty,
        status=row.status,
        mode=row.mode,
        is_solved=row.is_solved,
        hints_used=row.hints_used,
        attempts=row.attempts,
        messages=messages,
        task=json.loads(row.task_json) if row.task_json else None,
        task_id=json.loads(row.task_json).get("id") if row.task_json else None,
        user_id=row.user_id,
    )


class OrchestratorService:
    """
    Wraps existing MITS orchestrator and agents for API use.

    Manages sessions, processes messages, and provides
    async-compatible interface for FastAPI.
    """

    def __init__(self):
        self._orchestrator = None
        self._llm_client = None
        self._task_generator = None
        self._initialized = False

    async def initialize(self):
        """Initialize MITS core components."""
        if self._initialized:
            return

        try:
            from backend.app.config import backend_settings
            from src.models.llm_client import LLMClient

            self._backend_kind = "ollama"
            self._backend_info: Dict[str, Any] = {}
            model_name = None

            # ─── EXPERIMENTAL: HuggingFace backend with TurboQuant ───
            if getattr(backend_settings, "USE_HF_BACKEND", False):
                logger.info("HF backend requested (USE_HF_BACKEND=True)")
                try:
                    from src.inference.model_config import get_model_config
                    from src.models.hf_client import create_client_from_config

                    cfg_name = backend_settings.HF_MODEL_CONFIG
                    cfg = get_model_config(cfg_name)
                    if cfg is None:
                        raise ValueError(f"Unknown HF_MODEL_CONFIG: {cfg_name}")

                    logger.info(f"Loading HF client ({cfg.display_name}) — this may take 30-60s...")
                    self._llm_client = create_client_from_config(cfg_name)
                    self._backend_kind = "huggingface"
                    self._backend_info = {
                        "kind": "huggingface",
                        "model": cfg.hf_model_path,
                        "turbo_quant": cfg.turbo_quant_enabled,
                        "key_bits": cfg.turbo_quant_key_bits if cfg.turbo_quant_enabled else None,
                        "value_bits": cfg.turbo_quant_value_bits
                        if cfg.turbo_quant_enabled
                        else None,
                        "context_length": cfg.context_length,
                        "display_name": cfg.display_name,
                    }
                    model_name = cfg.hf_model_path
                    logger.info(f"HF backend ready: {cfg.display_name}")
                except Exception as e:
                    logger.warning(f"HF backend init failed, falling back to Ollama: {e}")
                    self._llm_client = None  # reset for ollama path

            # ─── llama-server (OpenAI-compatible, llama-swap :8090) backend ───
            if self._llm_client is None and backend_settings.LLM_BACKEND == "llamacpp":
                from src.models.openai_llm_client import OpenAICompatLLMClient

                self._llm_client = OpenAICompatLLMClient(model=backend_settings.LLM_MODEL)
                self._backend_kind = "llamacpp"
                self._backend_info = {
                    "kind": "llamacpp",
                    "model": backend_settings.LLM_MODEL,
                    "base_url": backend_settings.LLM_BASE_URL,
                    "turbo_quant": True,
                    "context_length": 32768,
                }
                logger.info(f"llama-server backend ready: {backend_settings.LLM_MODEL}")

            # ─── Ollama backend (default) ───
            if self._llm_client is None:
                # Select model: auto-detect, fine-tuned, or base
                if backend_settings.AUTO_SELECT_MODEL:
                    try:
                        from backend.app.services.hardware_detector import (
                            detect_hardware,
                            select_model,
                        )

                        hw = detect_hardware(backend_settings.OLLAMA_HOST)
                        selection = select_model(hw)
                        if selection["available"]:
                            model_name = selection["name"]
                            logger.info(
                                f"Auto-selected model: {model_name} ({selection['reason']})"
                            )
                        else:
                            logger.info(
                                f"Auto-selected model {selection['name']} not available, falling back to config"
                            )
                    except Exception as e:
                        logger.warning(f"Hardware auto-detection failed: {e}")

                if (
                    model_name is None
                    and backend_settings.USE_FINETUNED
                    and backend_settings.MODEL_FINETUNED
                ):
                    model_name = backend_settings.MODEL_FINETUNED
                    logger.info(f"Using fine-tuned model: {model_name}")
                elif model_name is None and backend_settings.MODEL_NAME:
                    model_name = backend_settings.MODEL_NAME
                    logger.info(f"Using base model: {model_name}")

                self._llm_client = LLMClient(model=model_name) if model_name else LLMClient()
                self._backend_info = {
                    "kind": "ollama",
                    "model": model_name,
                    "turbo_quant": False,
                    "context_length": 4096,
                }

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

    async def change_mode(
        self, db: AsyncSession, session_id: str, new_mode: str
    ) -> Optional[Dict[str, Any]]:
        """Change the mode of an existing session."""
        row = await db.get(SessionTable, session_id)
        if not row:
            return None

        previous_mode = row.mode
        row.mode = new_mode
        row.updated_at = datetime.utcnow()
        await db.commit()

        display_name = MODE_DISPLAY_NAMES.get(new_mode, new_mode)
        return {
            "session_id": session_id,
            "previous_mode": previous_mode,
            "current_mode": new_mode,
            "message": f"Режим изменён на «{display_name}»",
        }

    def _check_llm_available(self) -> bool:
        """Check if LLM client is connected.

        Result is cached for 30 seconds — avoids hammering Ollama on every
        /health request (which happens once per 20s from StatusBar).
        Under load, Ollama's /api/tags can block 2+ sec if model is cold.
        """
        import time as _time

        if not self._llm_client:
            return False

        cached_at = getattr(self, "_llm_health_cached_at", 0.0)
        cached_val = getattr(self, "_llm_health_cached", None)
        if cached_val is not None and (_time.time() - cached_at) < 30.0:
            return cached_val

        try:
            val = self._llm_client.check_connection()
        except Exception:
            val = False

        self._llm_health_cached = val
        self._llm_health_cached_at = _time.time()
        return val

    # --- Session Management ---

    async def create_session(
        self,
        db: AsyncSession,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
        custom_problem: Optional[str] = None,
        mode: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> StoredSession:
        """Create a new tutoring session."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        session_mode = mode or "guided_learning"

        # Override mode if user is enrolled in an active experiment
        if user_id:
            try:
                from backend.app.services.experiment_service import get_experiment_service

                exp_service = await get_experiment_service()
                group_info = await exp_service.get_user_group(db, user_id)
                if group_info:
                    session_mode = group_info["forced_mode"]
                    logger.info(
                        f"Experiment override: user={user_id}, "
                        f"group={group_info['group']}, mode={session_mode}"
                    )
            except Exception as e:
                logger.debug(f"Experiment group check skipped: {e}")

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
                    "difficulty": task.difficulty.value
                    if hasattr(task.difficulty, "value")
                    else str(task.difficulty),
                    "problem": task.problem,
                    "hints": task.hints[:3],
                    "skills": task.skills,
                    "solution": task.solution,
                    "answer": task.answer,
                }
            except Exception as e:
                logger.warning(f"Task generation failed: {e}")

        # Create orchestrator session (in-memory, for agent pipeline)
        if self._orchestrator:
            self._orchestrator.create_session(
                session_id=session_id,
                student_id=user_id or "student_default",
                problem=task_data["problem"] if task_data else None,
                topic=topic,
            )

        # Trigger background hint prefetch for the new task
        if task_data and topic:
            try:
                from src.inference.hint_prefetcher import get_hint_prefetcher

                prefetcher = get_hint_prefetcher()
                if not prefetcher._running:
                    prefetcher.start()
                prefetcher.prefetch_for_problem(
                    problem=task_data.get("problem", ""),
                    topic=topic,
                    hints=task_data.get("hints", []),
                )
            except Exception as e:
                logger.debug(f"Hint prefetch skipped: {e}")

        # Persist to DB
        row = SessionTable(
            id=session_id,
            user_id=user_id,
            mode=session_mode,
            topic=topic,
            difficulty=difficulty,
            task_json=json.dumps(task_data, ensure_ascii=False) if task_data else None,
            created_at=now,
            updated_at=now,
        )
        db.add(row)

        # Add welcome message
        welcome = self._generate_welcome(topic, task_data, session_mode)
        welcome_msg = MessageTable(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role="tutor",
            content=welcome,
            move_type="encourage",
            timestamp=now,
        )
        db.add(welcome_msg)
        await db.commit()

        # Kick off background hint prefetch for this session's task.
        # Hints get ready in the cache while student is reading the problem;
        # when /hint endpoint fires, response is instant (no LLM wait).
        if task_data:
            try:
                from src.inference.hint_prefetcher import get_hint_prefetcher

                prefetcher = get_hint_prefetcher()
                if not prefetcher._running:  # lazy start
                    prefetcher.start()
                prefetcher.prefetch_for_problem(
                    problem=task_data.get("problem", ""),
                    topic=topic,
                    hints=task_data.get("hints"),
                )
            except Exception as e:
                logger.debug(f"Hint prefetch skipped: {e}")

        # Return DTO
        session = StoredSession(
            id=session_id,
            created_at=now,
            updated_at=now,
            topic=topic,
            difficulty=difficulty,
            mode=session_mode,
            task=task_data,
            task_id=task_data["id"] if task_data else None,
            user_id=user_id,
            messages=[
                StoredMessage(
                    id=welcome_msg.id,
                    role="tutor",
                    content=welcome,
                    timestamp=now,
                    move_type="encourage",
                )
            ],
        )
        return session

    def _generate_welcome(
        self, topic: Optional[str], task: Optional[Dict], mode: str = "guided_learning"
    ) -> str:
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
        self,
        db: AsyncSession,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List sessions with pagination."""
        query = select(SessionTable)
        count_query = select(sa_func.count(SessionTable.id))

        if user_id:
            query = query.where(SessionTable.user_id == user_id)
            count_query = count_query.where(SessionTable.user_id == user_id)
        if status:
            query = query.where(SessionTable.status == status)
            count_query = count_query.where(SessionTable.status == status)

        total = (await db.execute(count_query)).scalar() or 0
        pages = max(1, (total + limit - 1) // limit)

        query = (
            query.options(selectinload(SessionTable.messages))
            .order_by(SessionTable.updated_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(query)
        rows = result.scalars().all()

        return {
            "sessions": [_row_to_session(r) for r in rows],
            "total": total,
            "page": page,
            "pages": pages,
        }

    async def get_session(self, db: AsyncSession, session_id: str) -> Optional[StoredSession]:
        """Get session by ID with messages."""
        query = (
            select(SessionTable)
            .options(selectinload(SessionTable.messages))
            .where(SessionTable.id == session_id)
        )
        result = await db.execute(query)
        row = result.scalar_one_or_none()
        if not row:
            return None
        return _row_to_session(row)

    async def delete_session(self, db: AsyncSession, session_id: str) -> bool:
        """Delete a session."""
        row = await db.get(SessionTable, session_id)
        if not row:
            return False
        await db.delete(row)
        await db.commit()
        if self._orchestrator:
            try:
                self._orchestrator.close_session(session_id)
            except Exception:
                pass
        return True

    # --- Chat ---

    async def _save_message(self, db: AsyncSession, session_id: str, msg: StoredMessage) -> None:
        """Persist a message to DB."""
        db.add(
            MessageTable(
                id=msg.id,
                session_id=session_id,
                role=msg.role,
                content=msg.content,
                move_type=msg.move_type,
                is_correct=msg.is_correct,
                thinking=msg.thinking,
                timestamp=msg.timestamp,
            )
        )

    async def _update_session_state(
        self,
        db: AsyncSession,
        session_id: str,
        attempts: Optional[int] = None,
        hints_used: Optional[int] = None,
        is_solved: Optional[bool] = None,
    ) -> None:
        """Update session counters in DB."""
        values: Dict[str, Any] = {"updated_at": datetime.utcnow()}
        if attempts is not None:
            values["attempts"] = attempts
        if hints_used is not None:
            values["hints_used"] = hints_used
        if is_solved is not None:
            values["is_solved"] = is_solved
        await db.execute(update(SessionTable).where(SessionTable.id == session_id).values(**values))

    async def process_message(
        self, db: AsyncSession, session_id: str, content: str
    ) -> Optional[Dict[str, Any]]:
        """Process a student message and return tutor response."""
        session = await self.get_session(db, session_id)
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

        await self._save_message(db, session_id, student_msg)
        await self._update_session_state(db, session_id, attempts=session.attempts)

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
                    for m in session.messages[-24:]
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

                if move_type == "encourage" and session.task:
                    is_correct = True
                    session.is_solved = True

                if result.pipeline_trace:
                    thinking = result.pipeline_trace.summary()

            except Exception as e:
                logger.error(f"Orchestrator error: {e}")
                tutor_content = (
                    "Давай попробуем разобраться вместе. Расскажи, что тебе уже понятно?"
                )
                move_type = "scaffolding"
        else:
            tutor_content = (
                "Хороший вопрос! Давай подумаем вместе. Какие формулы ты знаешь по этой теме?"
            )
            move_type = "scaffolding"

        # Parse thinking tags from response (Qwen3 / GLM)
        from backend.app.config import backend_settings

        visible_content, parsed_thinking = parse_thinking_tags(tutor_content)
        if parsed_thinking and not thinking:
            thinking = parsed_thinking
        display_content = visible_content if not backend_settings.SHOW_THINKING else tutor_content

        # Add tutor response
        tutor_msg = StoredMessage(
            id=str(uuid.uuid4()),
            role="tutor",
            content=display_content,
            timestamp=datetime.utcnow(),
            move_type=move_type,
            is_correct=is_correct,
            thinking=thinking,
        )
        await self._save_message(db, session_id, tutor_msg)
        if session.is_solved:
            await self._update_session_state(db, session_id, is_solved=True)
        await db.commit()

        return {
            "message_id": tutor_msg.id,
            "tutor_response": {
                "content": display_content,
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

    async def get_hint(self, db: AsyncSession, session_id: str) -> Optional[Dict[str, Any]]:
        """Get next hint for session.

        First tries the HintPrefetcher cache (pre-generated in background after
        session start). Falls back to task-bank static hints.
        """
        session = await self.get_session(db, session_id)
        if not session or not session.task:
            return None

        hints = session.task.get("hints", [])
        if session.hints_used >= len(hints):
            return None

        # Try prefetcher first — may have richer LLM-enhanced variant
        hint_text = None
        try:
            from src.inference.hint_prefetcher import get_hint_prefetcher

            prefetcher = get_hint_prefetcher()
            levels = ["conceptual", "procedural", "specific"]
            level = levels[min(session.hints_used, 2)]
            cached = prefetcher.get_hint(
                topic=session.topic or "general",
                level=level,
                index=session.hints_used,
            )
            if cached:
                hint_text = cached
                logger.info(
                    f"Hint cache hit (topic={session.topic}, level={level}, "
                    f"idx={session.hints_used})"
                )
        except Exception as e:
            logger.debug(f"Hint prefetch lookup skipped: {e}")

        # Fallback to task-bank
        if hint_text is None:
            hint_text = hints[session.hints_used]

        session.hints_used += 1

        # Save hint message
        hint_msg = StoredMessage(
            id=str(uuid.uuid4()),
            role="tutor",
            content=f"Подсказка {session.hints_used}: {hint_text}",
            timestamp=datetime.utcnow(),
            move_type="hint",
        )
        await self._save_message(db, session_id, hint_msg)
        await self._update_session_state(db, session_id, hints_used=session.hints_used)
        await db.commit()

        return {
            "hint_number": session.hints_used,
            "hint_text": hint_text,
            "hints_remaining": len(hints) - session.hints_used,
        }

    async def reveal_solution(self, db: AsyncSession, session_id: str) -> Optional[Dict[str, Any]]:
        """Reveal solution for session task."""
        session = await self.get_session(db, session_id)
        if not session or not session.task:
            return None

        solution = session.task.get("solution", "Решение недоступно")
        answer = session.task.get("answer", "Ответ недоступен")

        sol_msg = StoredMessage(
            id=str(uuid.uuid4()),
            role="tutor",
            content=f"Решение:\n{solution}\n\nОтвет: {answer}",
            timestamp=datetime.utcnow(),
            move_type="tell",
        )
        await self._save_message(db, session_id, sol_msg)
        await self._update_session_state(db, session_id)
        await db.commit()

        return {
            "solution": solution,
            "answer": answer,
            "penalty_applied": True,
        }

    # --- Streaming ---

    async def process_message_stream(
        self, db: AsyncSession, session_id: str, content: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process message with real token-by-token streaming.

        Yields dicts with type: token, response_complete, or error.
        """
        import asyncio

        from backend.app.services.tracing import get_tracer

        tracer = get_tracer()
        correlation_id = tracer.new_correlation_id()

        session = await self.get_session(db, session_id)
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

        await self._save_message(db, session_id, student_msg)
        await self._update_session_state(db, session_id, attempts=session.attempts)
        await db.commit()

        # Check LLM response cache before calling LLM (traced)
        with tracer.span(
            "cache_check",
            session_id=session_id,
            correlation_id=correlation_id,
            mode=session.mode,
        ) as _cache_span:
            try:
                from backend.app.services.cache_service import get_cache_service

                cache = get_cache_service()
                cached_response = cache.get(content, session.mode)
                _cache_span.set_attr("cache.hit", cached_response is not None)
            except Exception:
                cache = None
                cached_response = None
                _cache_span.set_attr("cache.hit", False)

        if cached_response:
            message_id = str(uuid.uuid4())
            move_type = "scaffolding"

            yield {"type": "token", "content": cached_response, "is_thinking": False}

            # Persist cached response
            tutor_msg = StoredMessage(
                id=message_id,
                role="tutor",
                content=cached_response,
                timestamp=datetime.utcnow(),
                move_type=move_type,
            )
            await self._save_message(db, session_id, tutor_msg)
            await db.commit()

            yield {
                "type": "response_complete",
                "message_id": message_id,
                "response": {
                    "content": cached_response,
                    "move_type": move_type,
                    "is_correct": None,
                },
                "session_state": {
                    "is_solved": session.is_solved,
                    "hints_used": session.hints_used,
                    "attempts": session.attempts,
                },
            }
            tracer.finalize_session(session_id)
            return

        # Determine mode and config
        mode = session.mode
        mode_config = self._get_mode_config(mode)
        move_type = "scaffolding"
        system_prompt = ""
        user_prompt = content

        if mode_config.use_pipeline and self._orchestrator:
            # GUIDED LEARNING: Full agent pipeline (profiler → planner → tutor → verifier)
            try:
                from src.agents.orchestrator import TurnContext
                from src.agents.planner import SessionContext as PlannerSessionContext
                from src.agents.profiler import StudentProfile

                history = [
                    {"role": m.role if m.role != "tutor" else "assistant", "content": m.content}
                    for m in session.messages[-24:]
                ]

                # Compress context if conversation is long
                if len(session.messages) > 10:
                    try:
                        from src.inference.context_compressor import compress_if_needed

                        full_history = [
                            {
                                "role": m.role if m.role != "tutor" else "assistant",
                                "content": m.content,
                            }
                            for m in session.messages
                        ]
                        compressed_msgs, compression_info = compress_if_needed(
                            session_id, full_history
                        )
                        if compression_info:
                            history = compressed_msgs
                            logger.info(
                                f"Context compressed: {compression_info.original_turns} -> "
                                f"{compression_info.compressed_turns} turns"
                            )
                    except Exception as e:
                        logger.debug(f"Context compression skipped: {e}")

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

                # Profiler (traced)
                try:
                    with tracer.span(
                        "profiler",
                        session_id=session_id,
                        correlation_id=correlation_id,
                    ) as _prof_span:
                        profile = self._orchestrator.profiler.diagnose(
                            problem=context.problem,
                            correct_approach=context.correct_answer or "",
                            student_response=context.student_input,
                            history=context.history,
                        )
                        if profile:
                            _prof_span.set_attr("student.level", getattr(profile, "level", None))
                            _prof_span.set_attr("error_type", getattr(profile, "error_type", None))
                except Exception as e:
                    logger.warning(f"Profiler error in stream: {e}")

                # Planner (traced)
                try:
                    with tracer.span(
                        "planner",
                        session_id=session_id,
                        correlation_id=correlation_id,
                    ) as _plan_span:
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
                        _plan_span.set_attr("move_type", move_type)
                except Exception as e:
                    logger.warning(f"Planner error in stream: {e}")

                # RAG (traced)
                if self._orchestrator.rag:
                    try:
                        with tracer.span(
                            "rag",
                            session_id=session_id,
                            correlation_id=correlation_id,
                        ) as _rag_span:
                            rag_context = self._orchestrator.rag.retrieve_context(
                                problem=context.problem,
                                student_response=context.student_input,
                                topic=context.topic,
                            )
                            _rag_span.set_attr(
                                "retrieved",
                                len(rag_context.chunks) if rag_context else 0,
                            )
                    except Exception as e:
                        logger.warning(f"RAG error in stream: {e}")

                system_prompt = self._orchestrator._build_system_prompt(plan)
                user_prompt = self._orchestrator._build_user_prompt(context, profile, rag_context)

            except Exception as e:
                logger.error(f"Stream context building error: {e}")

            # Send thinking content (profiler/planner output)
            thinking_content = []
            if profile and hasattr(profile, "error_type") and profile.error_type:
                thinking_content.append(f"Анализ: обнаружена ошибка типа '{profile.error_type}'")
            if profile and hasattr(profile, "knowledge_gaps") and profile.knowledge_gaps:
                gaps = ", ".join(profile.knowledge_gaps[:3])
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
            for m in session.messages[-24:]:
                role_label = "Пользователь" if m.role == "user" else "Ассистент"
                history_lines.append(f"{role_label}: {m.content}")
            user_prompt = "\n".join(history_lines) if history_lines else content
            move_type = "tell" if mode == "chat" else "scaffolding"

        # Agentic tool-use: assemble OpenAI-format messages and load tools.
        # Both chat AND guided_learning get pedagogical tools (SKI + Navigator);
        # web_search/fetch_url ONLY in chat — anti-pedagogical in Socratic guided.
        chat_messages: list = []
        tool_defs: list = []
        tool_funcs: dict = {}
        if mode in ("chat", "guided_learning"):
            if mode == "chat":
                # Free chat: full conversation history as messages.
                if system_prompt:
                    chat_messages.append({"role": "system", "content": system_prompt})
                for _m in session.messages[-24:]:
                    chat_messages.append(
                        {
                            "role": "user" if _m.role == "user" else "assistant",
                            "content": _m.content,
                        }
                    )
            else:
                # Guided: keep the rich pre-built system+user prompt from the
                # guided pipeline (Profiler+Planner+RAG already baked it in).
                if system_prompt:
                    chat_messages.append({"role": "system", "content": system_prompt})
                if user_prompt:
                    chat_messages.append({"role": "user", "content": user_prompt})

            # SKI tools — pedagogical aids (definitions/examples/methods/prereqs),
            # safe in BOTH modes; they don't give the answer, they help the tutor.
            try:
                from src.tools.ski_tools import SKI_FUNCTIONS, SKI_TOOL_DEFINITIONS

                tool_defs.extend(SKI_TOOL_DEFINITIONS)
                tool_funcs.update(SKI_FUNCTIONS)
            except Exception as e:
                logger.warning(f"ski_tools unavailable: {e}")
            # Navigator tools — Knowledge Forge graph navigation; also safe in both.
            try:
                from src.tools.navigator_tools import (
                    NAVIGATOR_FUNCTIONS,
                    NAVIGATOR_TOOL_DEFINITIONS,
                    set_mastery_source,
                )

                set_mastery_source({})  # empty source — no personalization yet
                tool_defs.extend(NAVIGATOR_TOOL_DEFINITIONS)
                tool_funcs.update(NAVIGATOR_FUNCTIONS)
            except Exception as e:
                logger.warning(f"navigator_tools unavailable: {e}")
            # Web tools — ONLY in chat (web_search in Socratic = student bypass).
            if mode == "chat":
                try:
                    from src.tools.web_tools import WEB_FUNCTIONS, WEB_TOOL_DEFINITIONS

                    tool_defs.extend(WEB_TOOL_DEFINITIONS)
                    tool_funcs.update(WEB_FUNCTIONS)
                except Exception as e:
                    logger.warning(f"web_tools unavailable: {e}")

        def _tool_executor(name: str, args: dict) -> str:
            """Dispatch a tool by name → string. Errors flow into the loop as JSON."""
            fn = tool_funcs.get(name)
            if not fn:
                return f'{{"error":"unknown tool: {name}"}}'
            try:
                result = fn(**args)
            except TypeError as e:
                return f'{{"error":"bad args for {name}: {e}"}}'
            return result if isinstance(result, str) else str(result)

        # Stream from LLM — real token-by-token streaming (no JSON buffering)
        full_response = ""
        message_id = str(uuid.uuid4())
        logger.info(f"Starting LLM streaming for session {session_id}")

        if self._llm_client and hasattr(self._llm_client, "generate_stream"):
            try:
                import concurrent.futures

                queue: asyncio.Queue = asyncio.Queue()
                loop = asyncio.get_event_loop()

                # Decide iterator: chat-mode with tools → agentic loop; else → plain stream.
                use_tools = (
                    mode in ("chat", "guided_learning")
                    and hasattr(self._llm_client, "chat_with_tools")
                    and bool(tool_defs)
                )
                if use_tools:
                    logger.info(
                        f"Agentic {mode}: {len(tool_defs)} tools available "
                        f"({', '.join(t['function']['name'] for t in tool_defs)})"
                    )

                def producer():
                    """Run sync generator and put tokens in queue."""
                    try:
                        token_count = 0
                        thinking_count = 0
                        content_count = 0
                        iterator = (
                            self._llm_client.chat_with_tools(
                                messages=chat_messages,
                                tools=tool_defs,
                                tool_executor=_tool_executor,
                                thinking=True,
                            )
                            if use_tools
                            else self._llm_client.generate_stream(
                                prompt=user_prompt,
                                system=system_prompt,
                                json_mode=False,
                                thinking=True,
                            )
                        )
                        for item in iterator:
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
                                loop.call_soon_threadsafe(queue.put_nowait, ("content", item))
                        logger.info(
                            f"LLM complete: {thinking_count} thinking + {content_count} content tokens"
                        )
                    except Exception as e:
                        logger.error(f"LLM producer error: {e}")
                        loop.call_soon_threadsafe(queue.put_nowait, Exception(f"LLM error: {e}"))
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
                full_response = (
                    "Давай попробуем разобраться вместе. Расскажи, что тебе уже понятно?"
                )
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

        # Parse thinking tags from streamed response (Qwen3 / GLM)
        tutor_content = full_response.strip()
        visible_content, stream_thinking = parse_thinking_tags(tutor_content)
        from backend.app.config import backend_settings

        display_content = visible_content if not backend_settings.SHOW_THINKING else tutor_content
        extracted_move = move_type  # Use planner's move type

        # Check correctness
        is_correct = None
        if extracted_move == "encourage" and session.task:
            is_correct = True
            session.is_solved = True

        # Store response in cache for future reuse
        if cache and tutor_content:
            try:
                cache.put(content, session.mode, tutor_content, move_type=extracted_move)
            except Exception as e:
                logger.debug(f"Cache store skipped: {e}")

        # Persist tutor response (store visible content, thinking separately)
        tutor_msg = StoredMessage(
            id=message_id,
            role="tutor",
            content=display_content,
            timestamp=datetime.utcnow(),
            move_type=extracted_move,
            is_correct=is_correct,
            thinking=stream_thinking,
        )
        await self._save_message(db, session_id, tutor_msg)
        if session.is_solved:
            await self._update_session_state(db, session_id, is_solved=True)
        await db.commit()

        # Send completion
        yield {
            "type": "response_complete",
            "message_id": message_id,
            "response": {
                "content": display_content,
                "move_type": extracted_move,
                "is_correct": is_correct,
            },
            "session_state": {
                "is_solved": session.is_solved,
                "hints_used": session.hints_used,
                "attempts": session.attempts,
            },
        }

        # Finalize trace: move active spans to completed buffer for inspection
        tracer.finalize_session(session_id)

        # Living KG: trigger background session analysis → graph proposals
        try:
            from backend.app.services.kg_evolution_service import analyze_session_async

            # Extract signals from session for SessionTrace
            concepts = [session.topic] if session.topic else []
            errors = []
            if not session.is_solved and session.attempts > 1:
                errors.append(
                    {
                        "concept_id": session.topic or "unknown",
                        "description": f"attempts={session.attempts} without success",
                        "turn": len(session.messages),
                    }
                )

            asyncio.create_task(
                analyze_session_async(
                    session_id=session_id,
                    student_id=session.user_id or "anonymous",
                    topic_id=session.topic or "general",
                    concepts_touched=concepts,
                    errors=errors,
                    hints_given=session.hints_used,
                    resolved=session.is_solved,
                )
            )
        except Exception as e:
            logger.debug(f"KG evolution hook skipped: {e}")

    # --- Tasks ---

    def get_available_topics(self) -> List[Dict[str, Any]]:
        """Get list of available topics."""
        topics = [
            {
                "id": "derivatives",
                "name": "Derivatives",
                "name_ru": "Производные",
                "difficulties": ["easy", "medium", "hard", "olympiad"],
            },
            {
                "id": "integrals",
                "name": "Integrals",
                "name_ru": "Интегралы",
                "difficulties": ["easy", "medium", "hard", "olympiad"],
            },
            {
                "id": "limits",
                "name": "Limits",
                "name_ru": "Пределы",
                "difficulties": ["easy", "medium", "hard", "olympiad"],
            },
            {
                "id": "series",
                "name": "Series",
                "name_ru": "Ряды",
                "difficulties": ["medium", "hard", "olympiad"],
            },
            {
                "id": "equations",
                "name": "Equations",
                "name_ru": "Уравнения",
                "difficulties": ["easy", "medium", "hard"],
            },
            {
                "id": "linear_algebra",
                "name": "Linear Algebra",
                "name_ru": "Линейная алгебра",
                "difficulties": ["easy", "medium", "hard"],
            },
        ]

        # Try to get from task bank
        try:
            from src.data.task_bank import TaskBank

            bank = TaskBank()
            if hasattr(bank, "get_topics"):
                bank_topics = bank.get_topics()
                # Only trust the bank's topics if they match the API shape
                # (id/name/name_ru/difficulties); otherwise fall through to the
                # well-formed static list below — avoids a 500 in /tasks/topics
                # when the bank returns a different shape (e.g. plain strings).
                if bank_topics and all(
                    isinstance(t, dict)
                    and {"id", "name", "name_ru", "difficulties"} <= set(t.keys())
                    for t in bank_topics
                ):
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
        return {
            "tasks": [],
            "reasoning": "Рекомендации основаны на вашем текущем уровне знаний.",
        }

    # --- Student Profile ---

    async def get_student_profile(
        self, db: AsyncSession, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get student profile data from DB."""
        query = select(SessionTable)
        if user_id:
            query = query.where(SessionTable.user_id == user_id)

        result = await db.execute(query)
        sessions = result.scalars().all()

        total_sessions = len(sessions)
        solved_count = sum(1 for s in sessions if s.is_solved)
        total_hints = sum(s.hints_used for s in sessions)

        return {
            "student_id": user_id or "student_default",
            "total_sessions": total_sessions,
            "success_rate": solved_count / total_sessions if total_sessions > 0 else 0.0,
            "total_time_minutes": 0,
            "streak_days": 0,
            "mastery_by_topic": {},
            "weak_skills": [],
            "strong_skills": [],
            "recommended_topic": "derivatives",
        }

    async def get_analytics(
        self, db: AsyncSession, period: str = "week", user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get analytics data from DB."""
        query = select(SessionTable)
        if user_id:
            query = query.where(SessionTable.user_id == user_id)

        result = await db.execute(query)
        sessions = result.scalars().all()

        now = datetime.utcnow()
        return {
            "period_start": now.isoformat(),
            "period_end": now.isoformat(),
            "sessions_count": len(sessions),
            "tasks_attempted": sum(s.attempts for s in sessions),
            "tasks_solved": sum(1 for s in sessions if s.is_solved),
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
        from backend.app.config import backend_settings

        llm_ok = self._check_llm_available()

        backend_info = getattr(self, "_backend_info", {}) or {}
        backend_kind = backend_info.get("kind", "ollama")
        model_name = backend_info.get("model") or (
            backend_settings.MODEL_FINETUNED
            if backend_settings.USE_FINETUNED
            else backend_settings.MODEL_NAME
        )

        components = {
            "llm": {
                "status": "healthy" if llm_ok else "unhealthy",
                "model": model_name,
                "backend": backend_kind,
                "turbo_quant": backend_info.get("turbo_quant", False),
                "context_length": backend_info.get("context_length", 4096),
            },
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
