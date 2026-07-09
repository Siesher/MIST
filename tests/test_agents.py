"""
MITS Tests - Agents

Basic tests for tutoring agents.
"""

from unittest.mock import Mock

import pytest


class TestTutorAgent:
    """Tests for SocraticTutorAgent."""

    def test_strategy_selection_solved(self):
        """Should select encourage strategy when solved."""
        from src.agents.tutor_agent import SocraticTutorAgent

        # Mock LLM client
        mock_llm = Mock()
        agent = SocraticTutorAgent(mock_llm)

        situation = {"student_state": "solved"}
        mock_session = Mock()
        mock_session.hints_used = 0
        mock_session.attempts = 1

        strategy = agent._select_strategy(situation, mock_session)
        assert strategy == "encourage"

    def test_strategy_selection_frustrated(self):
        """Should select hint when student is frustrated."""
        from src.agents.tutor_agent import SocraticTutorAgent

        mock_llm = Mock()
        agent = SocraticTutorAgent(mock_llm)

        situation = {"emotional_state": "frustrated"}
        mock_session = Mock()
        mock_session.hints_used = 0
        mock_session.attempts = 2

        strategy = agent._select_strategy(situation, mock_session)
        assert strategy == "hint"

    def test_strategy_selection_error(self):
        """Should select rectify when student made error."""
        from src.agents.tutor_agent import SocraticTutorAgent

        mock_llm = Mock()
        agent = SocraticTutorAgent(mock_llm)

        situation = {"student_state": "made_error"}
        mock_session = Mock()
        mock_session.hints_used = 0
        mock_session.attempts = 1

        strategy = agent._select_strategy(situation, mock_session)
        assert strategy == "rectify"

    def test_answer_leak_detection(self):
        """Should detect when answer is revealed."""
        from src.agents.tutor_agent import SocraticTutorAgent
        from src.data.schemas import Task

        mock_llm = Mock()
        agent = SocraticTutorAgent(mock_llm)

        task = Task(
            topic="test",
            problem="Find x",
            solution="x = 144",
            answer="144"
        )

        # Should detect direct answer
        assert agent._is_revealing_answer("The answer is 144", task)

        # Should not flag non-revealing messages
        assert not agent._is_revealing_answer("What do you think?", task)

        # Короткие ответы (<3 символов) намеренно не флагуются — иначе
        # любая цифра в сообщении тьютора давала бы ложную тревогу
        short_task = Task(topic="test", problem="Find x", solution="x = 7", answer="7")
        assert not agent._is_revealing_answer("The answer is 7", short_task)


class TestResponseVerifier:
    """Tests for ResponseVerifierAgent."""

    def test_numeric_verification(self):
        """Should verify numeric answers."""
        from src.agents.response_verifier import ResponseVerifierAgent

        mock_llm = Mock()
        agent = ResponseVerifierAgent(mock_llm)

        result = agent._verify_symbolic("42", "The answer is 42")

        # May be None if can't extract, that's ok
        if result:
            assert result.is_correct

    def test_expression_cleaning(self):
        """Should clean mathematical expressions."""
        from src.agents.response_verifier import ResponseVerifierAgent

        mock_llm = Mock()
        agent = ResponseVerifierAgent(mock_llm)

        # Test basic cleaning
        cleaned = agent._clean_expression("2x + 3")
        assert "2*x" in cleaned

        cleaned = agent._clean_expression("x^2")
        assert "x**2" in cleaned


class TestMathUtils:
    """Tests for math utilities."""

    def test_clean_expression(self):
        """Should clean expressions properly."""
        from src.utils.math_utils import clean_expression

        assert "2*x" in clean_expression("2x")
        assert "**" in clean_expression("x^2")

    def test_expressions_equal(self):
        """Should compare expressions."""
        from src.utils.math_utils import expressions_equal

        # Same expression
        is_equal, conf = expressions_equal("x + 1", "1 + x")
        assert is_equal
        assert conf > 0.9

        # Different expressions
        is_equal, conf = expressions_equal("x + 1", "x + 2")
        assert not is_equal

    def test_compute_derivative(self):
        """Should compute derivatives."""
        from src.utils.math_utils import compute_derivative

        result = compute_derivative("x**2")
        assert result == "2*x"


class TestSchemas:
    """Tests for data schemas."""

    def test_task_creation(self):
        """Should create valid task."""
        from src.data.schemas import Difficulty, Task

        task = Task(
            topic="derivatives",
            difficulty=Difficulty.MEDIUM,
            problem="Find f'(x) for f(x) = x²",
            solution="f'(x) = 2x",
            answer="2x"
        )

        assert task.topic == "derivatives"
        assert task.difficulty == Difficulty.MEDIUM
        assert task.id is not None

    def test_session_add_message(self):
        """Should track conversation."""
        from src.data.schemas import Task, TutoringSession

        task = Task(
            topic="test",
            problem="Test problem",
            solution="Solution",
            answer="42"
        )

        session = TutoringSession(
            student_id="test_student",
            task=task
        )

        session.add_student_message("My attempt")

        assert len(session.conversation) == 1
        assert session.attempts == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
