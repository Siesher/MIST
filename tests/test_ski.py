"""
Tests for Structured Knowledge Index (SKI).

Tests loading, lookups, search, and edge cases.
"""

import json
import tempfile
import pytest
from pathlib import Path

from src.knowledge.ski import KnowledgeCard, StructuredKnowledgeIndex


# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def sample_cards_dir(tmp_path):
    """Create a temp directory with sample knowledge cards."""
    card_data = {
        "cards": [
            {
                "id": "test_derivatives_01",
                "topic": "derivatives",
                "domain": "math",
                "skill": "calculus.derivatives",
                "difficulty": "medium",
                "prerequisites": ["limits", "functions"],
                "definition": "Производная функции f в точке x₀",
                "key_formulas": [
                    {"name": "Степень", "latex": "(x^n)' = nx^{n-1}"},
                    {"name": "Произведение", "latex": "(fg)' = f'g + fg'"},
                ],
                "notation": {"f'(x)": "производная"},
                "worked_examples": [
                    {
                        "difficulty": "easy",
                        "problem": "f(x) = 3x²",
                        "steps": ["(3x²)' = 6x"],
                        "answer": "6x",
                    },
                    {
                        "difficulty": "hard",
                        "problem": "f(x) = ln(sin(x²))",
                        "steps": ["chain rule..."],
                        "answer": "2x·ctg(x²)",
                    },
                ],
                "common_errors": [
                    {"error": "Забыта внутренняя производная", "description": "...", "correction": "..."},
                ],
                "tags": ["calculus", "chain_rule", "product_rule"],
            },
            {
                "id": "test_quadratic_01",
                "topic": "quadratic_equations",
                "domain": "math",
                "skill": "algebra.quadratic",
                "difficulty": "easy",
                "prerequisites": ["linear_equations", "square_roots"],
                "definition": "Уравнение вида ax² + bx + c = 0",
                "key_formulas": [
                    {"name": "Дискриминант", "latex": "D = b² - 4ac"},
                ],
                "notation": {},
                "worked_examples": [],
                "common_errors": [
                    {"error": "Неправильный знак", "description": "...", "correction": "..."},
                ],
                "tags": ["algebra", "quadratic", "discriminant"],
            },
        ]
    }

    json_file = tmp_path / "test_cards.json"
    json_file.write_text(json.dumps(card_data, ensure_ascii=False), encoding="utf-8")
    return tmp_path


@pytest.fixture
def ski(sample_cards_dir):
    """Create an SKI instance from sample data."""
    return StructuredKnowledgeIndex(data_path=str(sample_cards_dir))


# ── Loading Tests ────────────────────────────────────────────────

class TestSKILoading:

    def test_loads_cards(self, ski):
        assert ski.stats["total_cards"] == 2

    def test_indexes_topics(self, ski):
        assert "derivatives" in ski.stats["topics"]
        assert "quadratic_equations" in ski.stats["topics"]

    def test_indexes_domains(self, ski):
        assert "math" in ski.stats["domains"]

    def test_indexes_skills(self, ski):
        assert "calculus.derivatives" in ski.stats["skills"]
        assert "algebra.quadratic" in ski.stats["skills"]

    def test_empty_directory(self, tmp_path):
        ski = StructuredKnowledgeIndex(data_path=str(tmp_path))
        assert ski.stats["total_cards"] == 0

    def test_nonexistent_directory(self, tmp_path):
        ski = StructuredKnowledgeIndex(data_path=str(tmp_path / "nonexistent"))
        assert ski.stats["total_cards"] == 0


# ── Lookup Tests ─────────────────────────────────────────────────

class TestSKILookups:

    def test_lookup_by_topic(self, ski):
        cards = ski.lookup_by_topic("derivatives")
        assert len(cards) == 1
        assert cards[0].topic == "derivatives"

    def test_lookup_by_topic_case_insensitive(self, ski):
        cards = ski.lookup_by_topic("DERIVATIVES")
        assert len(cards) == 1

    def test_lookup_by_topic_not_found(self, ski):
        cards = ski.lookup_by_topic("quantum_physics")
        assert len(cards) == 0

    def test_lookup_by_topic_with_domain(self, ski):
        cards = ski.lookup_by_topic("derivatives", domain="math")
        assert len(cards) == 1
        cards = ski.lookup_by_topic("derivatives", domain="physics")
        assert len(cards) == 0

    def test_lookup_by_skill(self, ski):
        cards = ski.lookup_by_skill("calculus.derivatives")
        assert len(cards) == 1
        assert cards[0].skill == "calculus.derivatives"

    def test_get_formulas(self, ski):
        formulas = ski.get_formulas("derivatives")
        assert len(formulas) == 2
        names = [f["name"] for f in formulas]
        assert "Степень" in names

    def test_get_formulas_not_found(self, ski):
        formulas = ski.get_formulas("topology")
        assert formulas == []

    def test_get_worked_examples(self, ski):
        examples = ski.get_worked_examples("derivatives")
        assert len(examples) == 2

    def test_get_worked_examples_by_difficulty(self, ski):
        easy = ski.get_worked_examples("derivatives", difficulty="easy")
        assert len(easy) == 1
        assert easy[0]["answer"] == "6x"

        hard = ski.get_worked_examples("derivatives", difficulty="hard")
        assert len(hard) == 1

    def test_get_prerequisites(self, ski):
        prereqs = ski.get_prerequisites("derivatives")
        assert "limits" in prereqs
        assert "functions" in prereqs

    def test_get_common_errors(self, ski):
        errors = ski.get_common_errors("derivatives")
        assert len(errors) == 1
        assert "внутренняя" in errors[0]["error"].lower()


# ── Search Tests ─────────────────────────────────────────────────

class TestSKISearch:

    def test_search_by_topic_name(self, ski):
        results = ski.search("derivatives")
        assert len(results) >= 1
        assert results[0].topic == "derivatives"

    def test_search_by_tag(self, ski):
        results = ski.search("discriminant")
        assert len(results) >= 1
        assert results[0].topic == "quadratic_equations"

    def test_search_by_partial_term(self, ski):
        results = ski.search("quadratic")
        assert len(results) >= 1

    def test_search_with_domain_filter(self, ski):
        results = ski.search("derivatives", domain="math")
        assert len(results) >= 1
        results = ski.search("derivatives", domain="physics")
        assert len(results) == 0

    def test_search_not_found(self, ski):
        results = ski.search("blockchain")
        assert len(results) == 0

    def test_search_limit(self, ski):
        results = ski.search("math", limit=1)
        assert len(results) <= 1


# ── KnowledgeCard Serialization ──────────────────────────────────

class TestKnowledgeCard:

    def test_to_dict_roundtrip(self):
        card = KnowledgeCard(
            id="test",
            topic="test_topic",
            domain="math",
            skill="test.skill",
            difficulty="easy",
            definition="Test def",
            tags=["tag1"],
        )
        d = card.to_dict()
        card2 = KnowledgeCard.from_dict(d)
        assert card2.id == card.id
        assert card2.topic == card.topic
        assert card2.tags == card.tags

    def test_from_dict_defaults(self):
        card = KnowledgeCard.from_dict({"id": "x", "topic": "t"})
        assert card.domain == "math"
        assert card.difficulty == "medium"
        assert card.prerequisites == []


# ── Add Card at Runtime ──────────────────────────────────────────

class TestSKIAddCard:

    def test_add_card(self, ski):
        new_card = KnowledgeCard(
            id="new_01",
            topic="integrals",
            domain="math",
            skill="calculus.integrals",
            difficulty="hard",
            tags=["calculus"],
        )
        ski.add_card(new_card)
        assert ski.stats["total_cards"] == 3
        assert ski.lookup_by_topic("integrals")[0].id == "new_01"
