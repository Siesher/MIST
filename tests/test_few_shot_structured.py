"""
Tests for dynamic structured few-shot retrieval.
"""

import json
import pytest
from pathlib import Path

from src.knowledge.few_shot_bank import FewShotBank, FewShotExample


@pytest.fixture
def bank_with_data(tmp_path):
    """Create a bank with test data including skill and student_level."""
    data = {
        "topic": "derivatives",
        "examples": [
            {
                "topic": "derivatives",
                "difficulty": "easy",
                "problem": "f(x) = x²",
                "student_input": "2x?",
                "tutor_response": "Верно!",
                "tags": ["power_rule"],
                "skill": "calculus.derivatives",
                "student_level": "beginner",
            },
            {
                "topic": "derivatives",
                "difficulty": "hard",
                "problem": "f(x) = ln(sin(x))",
                "student_input": "Как?",
                "tutor_response": "Цепное правило...",
                "tags": ["chain_rule", "logarithm"],
                "skill": "calculus.derivatives",
                "student_level": "advanced",
            },
        ],
    }
    data2 = {
        "topic": "integrals",
        "examples": [
            {
                "topic": "integrals",
                "difficulty": "medium",
                "problem": "int x dx",
                "student_input": "x²/2?",
                "tutor_response": "+ C!",
                "tags": ["basic_integral"],
                "skill": "calculus.integrals",
                "student_level": "intermediate",
            },
        ],
    }

    (tmp_path / "derivatives.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "integrals.json").write_text(
        json.dumps(data2, ensure_ascii=False), encoding="utf-8"
    )

    return FewShotBank(data_path=tmp_path)


class TestRetrieveStructured:

    def test_topic_match(self, bank_with_data):
        results = bank_with_data.retrieve_structured(topic="derivatives", limit=5)
        assert len(results) == 2
        assert all(r.topic == "derivatives" for r in results)

    def test_topic_plus_difficulty(self, bank_with_data):
        results = bank_with_data.retrieve_structured(
            topic="derivatives", difficulty="easy", limit=5
        )
        # easy one should score higher (topic+3, difficulty+1 = 4)
        assert results[0].difficulty == "easy"

    def test_skill_match(self, bank_with_data):
        results = bank_with_data.retrieve_structured(
            skill="calculus.derivatives", limit=5
        )
        assert len(results) >= 2
        assert all(r.skill == "calculus.derivatives" for r in results)

    def test_tag_match(self, bank_with_data):
        results = bank_with_data.retrieve_structured(tags=["chain_rule"], limit=5)
        assert len(results) >= 1
        assert "chain_rule" in results[0].tags

    def test_combined_scoring(self, bank_with_data):
        # Topic derivatives + tag chain_rule + difficulty hard → should rank the hard one first
        results = bank_with_data.retrieve_structured(
            topic="derivatives",
            difficulty="hard",
            tags=["chain_rule"],
            limit=2,
        )
        assert results[0].difficulty == "hard"

    def test_limit(self, bank_with_data):
        results = bank_with_data.retrieve_structured(topic="derivatives", limit=1)
        assert len(results) == 1

    def test_no_match(self, bank_with_data):
        results = bank_with_data.retrieve_structured(topic="topology")
        assert len(results) == 0

    def test_cross_topic_with_tags(self, bank_with_data):
        # Tags alone should find across topics
        results = bank_with_data.retrieve_structured(tags=["basic_integral"])
        assert len(results) == 1
        assert results[0].topic == "integrals"


class TestNewFields:

    def test_skill_loaded(self, bank_with_data):
        examples = bank_with_data.get_examples_by_topic("derivatives", limit=5)
        assert all(ex.skill == "calculus.derivatives" for ex in examples)

    def test_student_level_loaded(self, bank_with_data):
        examples = bank_with_data.get_examples_by_topic("derivatives", limit=5)
        levels = {ex.student_level for ex in examples}
        assert "beginner" in levels
        assert "advanced" in levels

    def test_backward_compatible_without_new_fields(self, tmp_path):
        """Old JSON without skill/student_level should still load."""
        data = {
            "topic": "limits",
            "examples": [
                {
                    "topic": "limits",
                    "difficulty": "easy",
                    "problem": "lim x->0 sin(x)/x",
                    "student_input": "1?",
                    "tutor_response": "Да!",
                    "tags": ["remarkable_limit"],
                },
            ],
        }
        (tmp_path / "limits.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

        bank = FewShotBank(data_path=tmp_path)
        examples = bank.get_examples_by_topic("limits")
        assert len(examples) == 1
        assert examples[0].skill == ""
        assert examples[0].student_level == ""
