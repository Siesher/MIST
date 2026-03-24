"""
Tests for Textbook Grounding Mechanisms.

Covers:
1. KnowledgeCard schema extension (solution_methods, problem_templates)
2. Method Cards retrieval
3. Problem Templates (sampling, constraints, derived params)
4. Notation Grounding (context merge, Russian→SymPy normalization)
5. Solution Method Verification (schema fields)
6. Task Generator template integration
"""

import json
import os
import tempfile

import pytest

from src.data.schemas import VerificationResult
from src.knowledge.ski import KnowledgeCard, StructuredKnowledgeIndex

# ── Fixtures ─────────────────────────────────────────────────────

SAMPLE_CARD_DATA = {
    "id": "test_quad_01",
    "topic": "quadratic_equations",
    "domain": "math",
    "skill": "algebra.quadratic",
    "difficulty": "medium",
    "prerequisites": ["linear_equations"],
    "definition": "Квадратное уравнение",
    "key_formulas": [{"name": "D", "latex": "D=b^2-4ac"}],
    "notation": {"D": "дискриминант", "a": "старший коэф."},
    "worked_examples": [],
    "common_errors": [],
    "tags": ["algebra"],
    "solution_methods": [
        {
            "method_id": "quadratic_discriminant",
            "name": "Через дискриминант",
            "applicability": "Любое квадратное уравнение",
            "steps": [
                {"step": "1", "action": "Определить a,b,c", "formula": ""},
                {"step": "2", "action": "Вычислить D", "formula": "D=b^2-4ac"},
            ],
            "when_to_use": "Универсальный метод",
            "common_pitfalls": ["Забыть минус перед b"],
        },
        {
            "method_id": "quadratic_vieta",
            "name": "Теорема Виета",
            "applicability": "a=1, целые корни",
            "steps": [
                {"step": "1", "action": "Подобрать числа", "formula": "x1+x2=-p"},
            ],
            "when_to_use": "Приведённые уравнения",
            "common_pitfalls": [],
        },
    ],
    "problem_templates": [
        {
            "template_id": "quad_int_01",
            "pattern": "Решите $x^2 + {b}x + {c} = 0$",
            "parameters": {
                "x1": {"type": "int", "range": [-9, 9], "exclude": [0]},
                "x2": {"type": "int", "range": [-9, 9], "exclude": [0]},
            },
            "derived_params": {"b": "-(x1 + x2)", "c": "x1 * x2"},
            "constraints": ["x1 != x2", "abs(b) <= 20"],
            "answer_template": "$x_1={x1}, x_2={x2}$",
            "solution_method_id": "quadratic_discriminant",
            "difficulty": "easy",
        }
    ],
}

SAMPLE_CARD_LEGACY = {
    "id": "test_legacy_01",
    "topic": "linear_equations",
    "domain": "math",
    "skill": "algebra.linear",
    "difficulty": "easy",
    "definition": "ax+b=0",
    "key_formulas": [],
    "notation": {"x": "неизвестная"},
    "tags": ["algebra"],
}


@pytest.fixture
def tmp_data_dir():
    """Create a temporary directory with test JSON files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Card with new fields
        with open(os.path.join(tmpdir, "quadratic.json"), "w", encoding="utf-8") as f:
            json.dump({"cards": [SAMPLE_CARD_DATA]}, f, ensure_ascii=False)
        # Legacy card without new fields
        with open(os.path.join(tmpdir, "linear.json"), "w", encoding="utf-8") as f:
            json.dump({"cards": [SAMPLE_CARD_LEGACY]}, f, ensure_ascii=False)
        yield tmpdir


@pytest.fixture
def ski(tmp_data_dir):
    """Create SKI from temporary data."""
    return StructuredKnowledgeIndex(data_path=tmp_data_dir)


# ── 1. Schema Tests ──────────────────────────────────────────────

class TestKnowledgeCardSchema:
    """Test new fields on KnowledgeCard."""

    def test_new_fields_load(self, ski):
        cards = ski.lookup_by_topic("quadratic_equations")
        assert len(cards) == 1
        card = cards[0]
        assert len(card.solution_methods) == 2
        assert len(card.problem_templates) == 1
        assert card.solution_methods[0]["method_id"] == "quadratic_discriminant"

    def test_backward_compat(self, ski):
        """Legacy JSON without solution_methods/problem_templates loads fine."""
        cards = ski.lookup_by_topic("linear_equations")
        assert len(cards) == 1
        card = cards[0]
        assert card.solution_methods == []
        assert card.problem_templates == []

    def test_to_dict_includes_new_fields(self):
        card = KnowledgeCard.from_dict(SAMPLE_CARD_DATA)
        d = card.to_dict()
        assert "solution_methods" in d
        assert "problem_templates" in d
        assert len(d["solution_methods"]) == 2

    def test_from_dict_defaults(self):
        card = KnowledgeCard.from_dict(SAMPLE_CARD_LEGACY)
        assert card.solution_methods == []
        assert card.problem_templates == []


# ── 2. Method Cards ──────────────────────────────────────────────

class TestMethodCards:

    def test_get_all_methods(self, ski):
        methods = ski.get_solution_methods("quadratic_equations")
        assert len(methods) == 2
        names = {m["name"] for m in methods}
        assert "Через дискриминант" in names
        assert "Теорема Виета" in names

    def test_get_by_method_id(self, ski):
        methods = ski.get_solution_methods("quadratic_equations", method_id="quadratic_vieta")
        assert len(methods) == 1
        assert methods[0]["method_id"] == "quadratic_vieta"

    def test_get_missing_topic(self, ski):
        methods = ski.get_solution_methods("nonexistent_topic")
        assert methods == []

    def test_get_missing_method_id(self, ski):
        methods = ski.get_solution_methods("quadratic_equations", method_id="nonexistent")
        assert methods == []


# ── 3. Problem Templates ─────────────────────────────────────────

class TestProblemTemplates:

    def test_get_templates(self, ski):
        templates = ski.get_problem_templates("quadratic_equations")
        assert len(templates) == 1
        assert templates[0]["template_id"] == "quad_int_01"

    def test_get_by_difficulty(self, ski):
        easy = ski.get_problem_templates("quadratic_equations", difficulty="easy")
        assert len(easy) == 1
        hard = ski.get_problem_templates("quadratic_equations", difficulty="hard")
        assert hard == []

    def test_param_sampling(self):
        """Test _check_constraints validates params correctly."""
        from src.agents.task_generator import TaskGeneratorAgent
        assert TaskGeneratorAgent._check_constraints(
            ["1 != 2", "abs(-3) <= 20"], {"x1": 1, "x2": 2, "b": -3}
        )

    def test_constraint_rejection(self):
        """Constraints that fail should reject the sample."""
        from src.agents.task_generator import TaskGeneratorAgent
        # x1 == x2 should fail "x1 != x2"
        assert not TaskGeneratorAgent._check_constraints(
            ["x1 != x2"], {"x1": 3, "x2": 3}
        )

    def test_derived_params(self):
        """Derived params should be computed correctly."""
        from src.agents.task_generator import TaskGeneratorAgent

        class FakeAgent(TaskGeneratorAgent):
            def __init__(self):
                pass  # Skip real init

        agent = FakeAgent()
        template = {
            "derived_params": {"b": "-(x1 + x2)", "c": "x1 * x2"}
        }
        params = {"x1": 3, "x2": -2}
        result = agent._compute_derived_params(template, params)
        assert result["b"] == -1  # -(3 + (-2)) = -1
        assert result["c"] == -6  # 3 * (-2) = -6


# ── 4. Notation Grounding ────────────────────────────────────────

class TestNotationGrounding:

    def test_get_notation_context(self, ski):
        notation = ski.get_notation_context("quadratic_equations")
        assert "D" in notation
        assert notation["D"] == "дискриминант"

    def test_empty_notation(self, ski):
        notation = ski.get_notation_context("nonexistent_topic")
        assert notation == {}

    def test_russian_to_sympy_normalization(self):
        """Russian trig/log functions should be normalized."""
        from src.agents.response_verifier import ResponseVerifierAgent
        verifier = ResponseVerifierAgent.__new__(ResponseVerifierAgent)
        # Test the class-level mapping exists
        assert verifier.RUSSIAN_TO_SYMPY["tg"] == "tan"
        assert verifier.RUSSIAN_TO_SYMPY["ctg"] == "cot"
        assert verifier.RUSSIAN_TO_SYMPY["lg"] == "log10"
        assert verifier.RUSSIAN_TO_SYMPY["arctg"] == "atan"

    def test_clean_expression_russian(self):
        """_clean_expression should convert Russian function names."""
        from src.agents.response_verifier import ResponseVerifierAgent
        verifier = ResponseVerifierAgent.__new__(ResponseVerifierAgent)
        # Manually call _clean_expression
        result = verifier._clean_expression("tg(x) + ctg(x)")
        assert "tan" in result
        assert "cot" in result


# ── 5. Method Verification Schema ────────────────────────────────

class TestMethodVerification:

    def test_verification_result_new_fields(self):
        """VerificationResult should support method fields."""
        result = VerificationResult(
            is_correct=True,
            method_used="quadratic_vieta",
            expected_method="quadratic_discriminant",
            method_correct=False,
            method_feedback="Используй дискриминант",
        )
        assert result.method_used == "quadratic_vieta"
        assert result.method_correct is False
        assert result.error_type is None  # Not set unless explicitly

    def test_wrong_method_error_type(self):
        result = VerificationResult(
            is_correct=True,
            has_error=True,
            error_type="wrong_method",
            method_correct=False,
        )
        assert result.error_type == "wrong_method"

    def test_default_method_fields(self):
        """Default VerificationResult should have None method fields."""
        result = VerificationResult(is_correct=True)
        assert result.method_used is None
        assert result.expected_method is None
        assert result.method_correct is None
        assert result.method_feedback is None


# ── 6. Task Generator Template Integration ───────────────────────

class TestTaskGeneratorTemplates:

    def test_generate_from_template_with_real_data(self, tmp_data_dir):
        """Template generation should produce a valid Task with real seed data."""
        from unittest.mock import MagicMock

        import src.agents.task_generator as tg_module
        from src.agents.task_generator import TaskGeneratorAgent
        from src.data.schemas import Difficulty

        # Patch SKI
        old_has = tg_module.HAS_SKI
        old_get = tg_module.get_ski
        tg_module.HAS_SKI = True
        ski_instance = StructuredKnowledgeIndex(data_path=tmp_data_dir)
        tg_module.get_ski = lambda: ski_instance

        try:
            agent = TaskGeneratorAgent.__new__(TaskGeneratorAgent)
            agent.logger = MagicMock()
            task = agent._generate_from_template("quadratic_equations", Difficulty.EASY)
            assert task is not None
            assert "x^2" in task.problem
            assert task.answer  # non-empty
            assert task.topic == "quadratic_equations"
            assert task.difficulty == Difficulty.EASY
        finally:
            tg_module.HAS_SKI = old_has
            tg_module.get_ski = old_get

    def test_template_fallback_on_missing_topic(self, tmp_data_dir):
        """Template generation returns None for unknown topic."""
        from unittest.mock import MagicMock

        import src.agents.task_generator as tg_module
        from src.agents.task_generator import TaskGeneratorAgent
        from src.data.schemas import Difficulty

        old_has = tg_module.HAS_SKI
        old_get = tg_module.get_ski
        tg_module.HAS_SKI = True
        ski_instance = StructuredKnowledgeIndex(data_path=tmp_data_dir)
        tg_module.get_ski = lambda: ski_instance

        try:
            agent = TaskGeneratorAgent.__new__(TaskGeneratorAgent)
            agent.logger = MagicMock()
            task = agent._generate_from_template("nonexistent", Difficulty.EASY)
            assert task is None
        finally:
            tg_module.HAS_SKI = old_has
            tg_module.get_ski = old_get


# ── 7. SKI Tool Function ─────────────────────────────────────────

class TestSKIToolFunction:

    def test_get_solution_method_tool(self, tmp_data_dir):
        """The get_solution_method tool function should return JSON."""
        import src.tools.ski_tools as ski_tools_module
        from src.tools.ski_tools import get_solution_method

        # Patch the global SKI
        old_ski = ski_tools_module._ski
        ski_tools_module._ski = StructuredKnowledgeIndex(data_path=tmp_data_dir)

        try:
            result_json = get_solution_method("quadratic_equations")
            result = json.loads(result_json)
            assert "methods" in result
            assert len(result["methods"]) == 2

            # With specific method_id
            result_json = get_solution_method("quadratic_equations", method_id="quadratic_vieta")
            result = json.loads(result_json)
            assert result["method_id"] == "quadratic_vieta"
            assert result["name"] == "Теорема Виета"
        finally:
            ski_tools_module._ski = old_ski

    def test_get_solution_method_missing(self, tmp_data_dir):
        import src.tools.ski_tools as ski_tools_module
        from src.tools.ski_tools import get_solution_method

        old_ski = ski_tools_module._ski
        ski_tools_module._ski = StructuredKnowledgeIndex(data_path=tmp_data_dir)

        try:
            result = json.loads(get_solution_method("nonexistent"))
            assert "error" in result
        finally:
            ski_tools_module._ski = old_ski
