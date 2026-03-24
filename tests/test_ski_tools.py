"""
Tests for SKI tool functions and Ollama tool definitions.

Tests each tool with real SKI data and verifies Ollama tool format.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.tools.ski_tools import (
    lookup_concept, get_worked_example, get_formula, get_prerequisites,
    SKI_TOOL_DEFINITIONS, SKI_FUNCTIONS,
)


# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_ski():
    """Reset the lazy-loaded SKI singleton before each test."""
    import src.tools.ski_tools as mod
    mod._ski = None
    yield
    mod._ski = None


@pytest.fixture
def mock_ski():
    """Patch SKI with a mock that has test data."""
    from src.knowledge.ski import KnowledgeCard

    card = KnowledgeCard(
        id="test_01",
        topic="derivatives",
        domain="math",
        skill="calculus.derivatives",
        difficulty="medium",
        prerequisites=["limits", "functions"],
        definition="Производная — предел отношения приращения",
        key_formulas=[
            {"name": "Степень", "latex": "(x^n)' = nx^{n-1}"},
            {"name": "Цепное", "latex": "(f(g))' = f'(g)·g'"},
        ],
        worked_examples=[
            {
                "difficulty": "easy",
                "problem": "f(x) = 3x²",
                "steps": ["(3x²)' = 6x"],
                "answer": "6x",
            },
        ],
        common_errors=[
            {"error": "Забыта внутренняя", "description": "...", "correction": "..."},
        ],
        tags=["calculus"],
    )

    mock_index = MagicMock()
    mock_index.lookup_by_topic.return_value = [card]
    mock_index.search.return_value = [card]
    mock_index.get_formulas.return_value = card.key_formulas
    mock_index.get_worked_examples.return_value = card.worked_examples
    mock_index.get_prerequisites.return_value = card.prerequisites
    mock_index.get_common_errors.return_value = card.common_errors

    with patch("src.tools.ski_tools._get_ski", return_value=mock_index):
        yield mock_index


# ── Tool Function Tests ──────────────────────────────────────────

class TestLookupConcept:

    def test_returns_json(self, mock_ski):
        result = lookup_concept("derivatives")
        data = json.loads(result)
        assert data["topic"] == "derivatives"
        assert "definition" in data
        assert len(data["key_formulas"]) == 2

    def test_includes_common_errors(self, mock_ski):
        data = json.loads(lookup_concept("derivatives"))
        assert len(data["common_errors"]) == 1

    def test_with_domain(self, mock_ski):
        lookup_concept("derivatives", domain="math")
        mock_ski.lookup_by_topic.assert_called_with("derivatives", domain="math")

    def test_not_found_uses_search(self, mock_ski):
        mock_ski.lookup_by_topic.return_value = []
        result = lookup_concept("topology")
        # Should fallback to search
        mock_ski.search.assert_called_once()

    def test_not_found_returns_error(self, mock_ski):
        mock_ski.lookup_by_topic.return_value = []
        mock_ski.search.return_value = []
        data = json.loads(lookup_concept("nonexistent"))
        assert "error" in data

    def test_ski_unavailable(self):
        with patch("src.tools.ski_tools._get_ski", return_value=None):
            data = json.loads(lookup_concept("derivatives"))
            assert "error" in data


class TestGetWorkedExample:

    def test_returns_example(self, mock_ski):
        data = json.loads(get_worked_example("derivatives"))
        assert data["problem"] == "f(x) = 3x²"
        assert "steps" in data
        assert data["answer"] == "6x"

    def test_with_difficulty(self, mock_ski):
        get_worked_example("derivatives", difficulty="easy")
        mock_ski.get_worked_examples.assert_called_with("derivatives", difficulty="easy")

    def test_not_found(self, mock_ski):
        mock_ski.get_worked_examples.return_value = []
        data = json.loads(get_worked_example("topology"))
        assert "error" in data


class TestGetFormula:

    def test_returns_formulas(self, mock_ski):
        data = json.loads(get_formula("derivatives"))
        assert len(data["formulas"]) == 2
        assert data["formulas"][0]["name"] == "Степень"

    def test_not_found(self, mock_ski):
        mock_ski.get_formulas.return_value = []
        data = json.loads(get_formula("topology"))
        assert "error" in data


class TestGetPrerequisites:

    def test_returns_prereqs(self, mock_ski):
        data = json.loads(get_prerequisites("derivatives"))
        assert "limits" in data["prerequisites"]
        assert "functions" in data["prerequisites"]

    def test_empty_prereqs(self, mock_ski):
        mock_ski.get_prerequisites.return_value = []
        mock_ski.lookup_by_topic.return_value = [MagicMock()]
        data = json.loads(get_prerequisites("basic_math"))
        assert data["prerequisites"] == []

    def test_topic_not_found(self, mock_ski):
        mock_ski.get_prerequisites.return_value = []
        mock_ski.lookup_by_topic.return_value = []
        data = json.loads(get_prerequisites("nonexistent"))
        assert "error" in data


# ── Tool Definitions Format ──────────────────────────────────────

class TestToolDefinitions:

    def test_five_tools_defined(self):
        assert len(SKI_TOOL_DEFINITIONS) == 5

    def test_all_have_required_fields(self):
        for tool_def in SKI_TOOL_DEFINITIONS:
            assert tool_def["type"] == "function"
            fn = tool_def["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn
            assert fn["parameters"]["type"] == "object"
            assert "required" in fn["parameters"]

    def test_function_names_match(self):
        defined_names = {t["function"]["name"] for t in SKI_TOOL_DEFINITIONS}
        callable_names = set(SKI_FUNCTIONS.keys())
        assert defined_names == callable_names

    def test_all_functions_callable(self):
        for name, fn in SKI_FUNCTIONS.items():
            assert callable(fn), f"{name} is not callable"

    def test_topic_required_in_all(self):
        for tool_def in SKI_TOOL_DEFINITIONS:
            required = tool_def["function"]["parameters"]["required"]
            assert "topic" in required
