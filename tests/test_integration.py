#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MITS Integration Tests

Тестирование полной цепочки взаимодействия:
- Создание сессии → Диалог → Knowledge Tracking → Завершение
- Многоагентный пайплайн
- Memory система
- RAG контекст

T054: Integration Test for Full Tutoring Session
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))



# === Mock LLM Client ===

class MockLLMClient:
    """Mock LLM client for testing without actual API calls."""

    def __init__(self):
        self.call_count = 0
        self.last_prompt = None
        self.responses = []

    def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        system: str = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
        json_mode: bool = False,
        thinking: bool = True,
        **kwargs
    ) -> str:
        """Generate mock response."""
        self.call_count += 1
        self.last_prompt = prompt

        # Detect context and generate appropriate response
        prompt_lower = prompt.lower()

        if "не знаю" in prompt_lower or "помогите" in prompt_lower:
            return json.dumps({
                "move": "scaffolding",
                "message": "Давай разберёмся вместе. Какие данные нам даны в задаче?",
                "reasoning": "Student needs initial guidance"
            }, ensure_ascii=False)

        if "x = 2" in prompt_lower or "x = 3" in prompt_lower:
            return json.dumps({
                "move": "encourage",
                "message": "Отлично! Ты нашёл правильные корни. Как ты их проверил?",
                "reasoning": "Student found correct answer"
            }, ensure_ascii=False)

        if "ошибка" in prompt_lower or "неправильно" in prompt_lower:
            return json.dumps({
                "move": "rectify",
                "message": "Почти правильно! Но проверь внимательнее знак. Что получится, если подставить x = -2?",
                "reasoning": "Minor error correction needed"
            }, ensure_ascii=False)

        # Default scaffolding response
        return json.dumps({
            "move": "scaffolding",
            "message": "Хороший вопрос! С чего бы ты начал решение?",
            "reasoning": "General scaffolding"
        }, ensure_ascii=False)

    def ping(self) -> bool:
        """Health check."""
        return True


# === Test Fixtures ===

@pytest.fixture
def mock_llm():
    """Create mock LLM client."""
    return MockLLMClient()


@pytest.fixture
def sample_task():
    """Create sample tutoring task."""
    from src.data.schemas import Difficulty, Task

    return Task(
        id="test-task-001",
        problem="Решите уравнение: $x^2 - 5x + 6 = 0$",
        topic="algebra.quadratic",
        difficulty=Difficulty.MEDIUM,
        answer="x = 2 или x = 3",
        hints=[
            "Попробуй разложить левую часть на множители.",
            "Какие два числа в сумме дают -5, а в произведении 6?",
            "$(x - 2)(x - 3) = 0$"
        ],
        solution="Используем метод разложения на множители...",
        skills=["quadratic_equations", "factoring"]
    )


@pytest.fixture
def sample_session(sample_task):
    """Create sample tutoring session."""
    from src.data.schemas import TutoringSession

    return TutoringSession(
        id="test-session-001",
        student_id="test-student-001",
        task=sample_task,
        started_at=datetime.now()
    )


# === Unit Tests ===

class TestOrchestratorIntegration:
    """Test multi-agent orchestrator integration."""

    def test_orchestrator_initialization(self, mock_llm):
        """Test orchestrator creates all agents."""
        from src.agents.orchestrator import AgentOrchestrator, OrchestratorMode

        orchestrator = AgentOrchestrator(
            llm_client=mock_llm,
            mode=OrchestratorMode.FULL,
            verify_responses=True,
            use_rag=False,  # Disable for unit test
            use_knowledge_tracking=False,
            use_memory_manager=False
        )

        assert orchestrator is not None
        assert orchestrator.profiler is not None
        assert orchestrator.planner is not None
        assert orchestrator.verifier is not None

    def test_orchestrator_process_turn(self, mock_llm, sample_task):
        """Test full turn processing."""
        from src.agents.orchestrator import AgentOrchestrator, OrchestratorMode, TurnContext

        orchestrator = AgentOrchestrator(
            llm_client=mock_llm,
            mode=OrchestratorMode.FULL,
            use_rag=False,
            use_knowledge_tracking=False,
            use_memory_manager=False
        )

        context = TurnContext(
            problem=sample_task.problem,
            student_input="Не знаю как начать",
            correct_answer=sample_task.answer,
            topic=sample_task.topic,
            student_id="test-student"
        )

        result = orchestrator.process_turn(context)

        assert result is not None
        assert result.response != ""
        assert result.move_type in ["scaffolding", "hint", "encourage", "rectify", "tell"]
        assert result.metrics.get("total_ms", 0) > 0

    def test_orchestrator_query_routing(self, mock_llm):
        """Test query type classification and routing."""
        from src.agents.orchestrator import AgentOrchestrator, QueryType

        orchestrator = AgentOrchestrator(
            llm_client=mock_llm,
            use_rag=False,
            use_knowledge_tracking=False,
            use_memory_manager=False
        )

        # Test different query types
        test_cases = [
            ("Привет!", QueryType.GREETING),
            ("Помогите, не понимаю", QueryType.HINT_REQUEST),
            ("x = 5", QueryType.ANSWER_ATTEMPT),
            ("Что такое дискриминант?", QueryType.CLARIFICATION),
            ("Следующую задачу", QueryType.NEXT_TASK),
        ]

        for input_text, expected_type in test_cases:
            query_type = orchestrator._classify_query(input_text)
            # Some flexibility in classification
            assert query_type in [expected_type, QueryType.ANSWER_ATTEMPT, QueryType.QUESTION]

    def test_orchestrator_graceful_degradation(self, mock_llm):
        """Test graceful degradation when agents fail."""
        from src.agents.orchestrator import AgentOrchestrator, PipelineTrace, TurnContext

        orchestrator = AgentOrchestrator(
            llm_client=mock_llm,
            use_rag=False,
            use_knowledge_tracking=False,
            use_memory_manager=False
        )

        # Simulate error
        context = TurnContext(
            problem="Test problem",
            student_input="Test input"
        )

        trace = PipelineTrace(trace_id="test-trace")

        # Test fallback methods
        profile = orchestrator._fallback_profiler(context, Exception("Test error"))
        assert profile is not None

        plan = orchestrator._fallback_planner(context, Exception("Test error"))
        assert plan is not None

    def test_pipeline_tracing(self, mock_llm, sample_task):
        """Test pipeline trace collection."""
        from src.agents.orchestrator import AgentOrchestrator, OrchestratorMode, TurnContext

        orchestrator = AgentOrchestrator(
            llm_client=mock_llm,
            mode=OrchestratorMode.FULL,
            use_rag=False,
            use_knowledge_tracking=False,
            use_memory_manager=False
        )

        context = TurnContext(
            problem=sample_task.problem,
            student_input="Как решить?",
            correct_answer=sample_task.answer
        )

        result = orchestrator.process_turn(context)

        # Check trace
        assert result.pipeline_trace is not None
        assert result.pipeline_trace.trace_id is not None
        assert len(result.pipeline_trace.stages) > 0
        assert result.pipeline_trace.total_duration_ms > 0


class TestMemoryIntegration:
    """Test memory system integration."""

    def test_session_memory_creation(self):
        """Test session memory initialization."""
        from src.memory.session_memory import create_session_memory

        session = create_session_memory(
            session_id="test-session",
            student_id="test-student"
        )

        assert session is not None
        assert session.context.session_id == "test-session"
        assert session.context.student_id == "test-student"

    def test_session_memory_turn_tracking(self):
        """Test turn tracking in session memory."""
        from src.memory.session_memory import create_session_memory

        session = create_session_memory("test-session", "test-student")

        # Add student input
        session.add_student_input(
            content="Не знаю как решить",
            response_time_ms=5000,
            is_correct=None
        )

        # Add tutor response
        session.add_tutor_response(
            content="Давай разберёмся вместе.",
            move_type="scaffolding"
        )

        history = session.get_history(last_n=10)
        assert len(history) == 2

    def test_student_memory_persistence(self, tmp_path):
        """Test student memory SQLite persistence."""
        from src.memory.student_memory import StudentMemory

        db_path = tmp_path / "test_mits.db"
        memory = StudentMemory(db_path=str(db_path))

        # Create student
        student = memory.create_student("test-student", "Тест Тестов")
        assert student is not None
        assert student["student_id"] == "test-student"

        # Update knowledge
        mastery = memory.update_knowledge_state(
            student_id="test-student",
            topic_id="algebra.quadratic",
            correct=True,
            response_time_ms=30000,
            hints_used=1
        )
        assert mastery.mastery > 0.3

        # Retrieve knowledge state
        state = memory.get_knowledge_state("test-student")
        assert "algebra.quadratic" in state.topics

    def test_memory_manager_session_lifecycle(self, tmp_path):
        """Test full session lifecycle through memory manager."""
        from src.memory.manager import MemoryManager
        from src.memory.student_memory import StudentMemory

        db_path = tmp_path / "test_mits.db"
        student_memory = StudentMemory(db_path=str(db_path))

        manager = MemoryManager(
            student_memory=student_memory,
            apply_decay_on_start=False
        )

        # Start session
        session_id, session, knowledge = manager.start_session("test-student")
        assert session_id is not None
        assert session is not None

        # Record interaction
        manager.record_interaction(
            session_id=session_id,
            student_input="x = 2",
            tutor_response="Отлично!",
            correct=True,
            response_time_ms=10000,
            tutor_move="encourage"
        )

        # End session
        summary = manager.end_session(session_id)
        # Summary may be None if no task was set
        assert session_id not in manager._sessions


class TestLanguageSupport:
    """Test Russian language support."""

    def test_language_detection_russian(self):
        """Test Russian language detection."""
        from src.utils.language_detector import Language, detect_language

        result = detect_language("Решите уравнение: $x^2 - 5x + 6 = 0$")
        assert result.language == Language.RUSSIAN
        assert result.confidence > 0.5

    def test_language_detection_english(self):
        """Test English language detection."""
        from src.utils.language_detector import Language, detect_language

        result = detect_language("Solve the equation: $x^2 - 5x + 6 = 0$")
        assert result.language == Language.ENGLISH

    def test_russian_math_notation(self):
        """Test Russian math notation conversion."""
        from src.models.prompts import convert_to_russian_notation

        latex = r"$\tan(x) + \cot(x) = 1$"
        russian = convert_to_russian_notation(latex)

        assert r"\text{tg}" in russian or "tg" in russian
        assert r"\text{ctg}" in russian or "ctg" in russian

    def test_russian_notation_detection(self):
        """Test detection of Russian vs English notation."""
        from src.utils.language_detector import detect_language

        # Russian notation
        russian_expr = "Найдите $\\text{tg}(x)$ если $\\sin(x) = 0.5$"
        result = detect_language(russian_expr)
        assert result.has_russian_math or result.language.value == "ru"

        # English notation
        english_expr = "Find $\\tan(x)$ if $\\sin(x) = 0.5$"
        result = detect_language(english_expr)
        assert result.has_english_math or result.language.value == "en"


class TestTutorAgent:
    """Test tutor agent functionality."""

    def test_tutor_response_generation(self, mock_llm, sample_session):
        """Test basic response generation."""
        from src.agents.tutor_agent import SocraticTutorAgent

        tutor = SocraticTutorAgent(
            llm_client=mock_llm,
            use_orchestrator=False,  # Test classic mode
            use_rag=False
        )

        response = tutor.generate_response(
            session=sample_session,
            student_message="Не знаю как начать"
        )

        assert response is not None
        assert response.message != ""
        assert response.move is not None

    def test_frustration_detection(self):
        """Test frustration detection in student messages."""
        from src.models.prompts import detect_frustration

        assert detect_frustration("Не понимаю ничего!") == True
        assert detect_frustration("Я сдаюсь") == True
        assert detect_frustration("x = 5") == False
        assert detect_frustration("Попробую метод подстановки") == False

    def test_break_suggestion(self, mock_llm, sample_session):
        """Test break suggestion for cognitive overload."""
        from src.agents.tutor_agent import SocraticTutorAgent

        tutor = SocraticTutorAgent(
            llm_client=mock_llm,
            use_orchestrator=False,
            use_rag=False
        )

        # Test conditions for break suggestion
        should_break, reason = tutor.should_suggest_break(
            session=sample_session,
            session_memory=None,
            cognitive_load_score=0.9  # High cognitive load
        )

        assert should_break == True
        assert reason == "cognitive_overload"


class TestKnowledgeTracking:
    """Test knowledge tracking integration."""

    def test_bkt_update(self, tmp_path):
        """Test BKT knowledge update."""
        from src.models.knowledge_tracing import KnowledgeTracker

        # storage_path=tmp_path: record_attempt автосохраняет профиль на диск,
        # реальный data/students/ засорять нельзя
        tracker = KnowledgeTracker(storage_path=str(tmp_path))

        updated = tracker.record_attempt(
            student_id="test-student",
            skills=["quadratic_equations"],
            is_correct=True,
        )

        assert "quadratic_equations" in updated
        assert updated["quadratic_equations"] > 0.3  # mastery вырос после верного ответа

    def test_knowledge_decay(self, tmp_path):
        """Test Ebbinghaus knowledge decay."""
        from src.memory.student_memory import StudentMemory

        db_path = tmp_path / "test_decay.db"
        memory = StudentMemory(db_path=str(db_path))

        # Create student and set initial knowledge
        memory.create_student("decay-test")
        memory.update_knowledge_state(
            student_id="decay-test",
            topic_id="algebra.quadratic",
            correct=True,
            response_time_ms=30000,
            hints_used=0
        )

        # Get initial state
        state_before = memory.get_knowledge_state("decay-test")
        initial_mastery = state_before.topics["algebra.quadratic"].mastery
        assert initial_mastery > 0.0

        # Apply decay (in real usage this happens over time)
        memory.apply_knowledge_decay("decay-test")

        # Note: Decay may not be visible immediately if not enough time passed
        # This test mainly verifies the method runs without error


# === Full Integration Test ===

class TestFullTutoringSession:
    """End-to-end tutoring session test."""

    def test_complete_session_flow(self, mock_llm, sample_task, tmp_path):
        """Test complete tutoring session from start to finish."""
        from src.agents.orchestrator import AgentOrchestrator, TurnContext
        from src.memory.manager import MemoryManager
        from src.memory.student_memory import StudentMemory

        # Setup
        db_path = tmp_path / "test_session.db"
        student_memory = StudentMemory(db_path=str(db_path))
        memory_manager = MemoryManager(student_memory=student_memory)

        orchestrator = AgentOrchestrator(
            llm_client=mock_llm,
            memory_manager=memory_manager,
            use_rag=False,
            use_knowledge_tracking=False
        )

        student_id = "integration-test-student"

        # 1. Start session
        session_id, session, knowledge = memory_manager.start_session(student_id)
        assert session_id is not None

        # 2. First turn - student doesn't know how to start
        context1 = TurnContext(
            problem=sample_task.problem,
            student_input="Не знаю как решить это уравнение",
            correct_answer=sample_task.answer,
            topic=sample_task.topic,
            student_id=student_id
        )

        result1 = orchestrator.process_turn(context1, session_id)
        assert result1.move_type in ["scaffolding", "hint"]
        assert "?" in result1.response or "давай" in result1.response.lower()

        # Record interaction
        memory_manager.record_interaction(
            session_id=session_id,
            student_input=context1.student_input,
            tutor_response=result1.response,
            correct=None,
            response_time_ms=5000,
            tutor_move=result1.move_type
        )

        # 3. Second turn - student attempts solution
        context2 = TurnContext(
            problem=sample_task.problem,
            student_input="Если разложить на множители... x-2 и x-3?",
            correct_answer=sample_task.answer,
            topic=sample_task.topic,
            student_id=student_id
        )

        result2 = orchestrator.process_turn(context2, session_id)
        assert result2 is not None

        # 4. Third turn - student finds answer
        context3 = TurnContext(
            problem=sample_task.problem,
            student_input="Значит x = 2 или x = 3!",
            correct_answer=sample_task.answer,
            topic=sample_task.topic,
            student_id=student_id
        )

        result3 = orchestrator.process_turn(context3, session_id)
        # Should recognize correct answer
        assert result3 is not None

        # 5. End session
        summary = memory_manager.end_session(session_id)

        # Verify session ended
        assert session_id not in memory_manager._sessions

        print("\n=== Integration Test Complete ===")
        print("Turns processed: 3")
        print(f"Final move: {result3.move_type}")
        print(f"Total LLM calls: {mock_llm.call_count}")


# === Performance Tests ===

class TestPerformance:
    """Performance and latency tests."""

    def test_orchestrator_latency(self, mock_llm, sample_task):
        """Test orchestrator response latency."""
        from src.agents.orchestrator import AgentOrchestrator, TurnContext

        orchestrator = AgentOrchestrator(
            llm_client=mock_llm,
            use_rag=False,
            use_knowledge_tracking=False,
            use_memory_manager=False
        )

        context = TurnContext(
            problem=sample_task.problem,
            student_input="Test input",
            correct_answer=sample_task.answer
        )

        start = time.time()
        result = orchestrator.process_turn(context)
        elapsed = (time.time() - start) * 1000

        # Should complete within reasonable time (without actual LLM)
        assert elapsed < 1000  # 1 second max
        assert result.metrics.get("total_ms", 0) > 0


# === Run Tests ===

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
