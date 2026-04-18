"""Тесты для MentalModelAgent и BeliefState (ToM-Tutor, фича 017)."""

from datetime import datetime

import pytest

from src.data.schemas import BeliefState

# ─────────────────────────────────────────────────────────────────────
# T007: Тесты BeliefState dataclass
# ─────────────────────────────────────────────────────────────────────


class TestBeliefState:
    """Проверка валидации, empty(), сериализации."""

    def test_default_values(self) -> None:
        """По умолчанию — все поля пустые, confidence=0."""
        bs = BeliefState()
        assert bs.active_misconception is None
        assert bs.active_misconception_node_id is None
        assert bs.belief_about_topic == ""
        assert bs.predicted_reactions == {}
        assert bs.candidate_misconceptions == []
        assert bs.confidence == 0.0
        assert bs.reasoning == ""
        assert bs.profile_used == ""
        # generated_at должен быть автоматически установлен
        assert bs.generated_at != ""
        # Валидный ISO 8601
        datetime.fromisoformat(bs.generated_at)

    def test_confidence_upper_bound(self) -> None:
        """confidence > 1.0 должно падать с ValidationError."""
        with pytest.raises(Exception):
            BeliefState(confidence=1.5)

    def test_confidence_lower_bound(self) -> None:
        """confidence < 0.0 должно падать с ValidationError."""
        with pytest.raises(Exception):
            BeliefState(confidence=-0.1)

    def test_confidence_boundary_values(self) -> None:
        """0.0 и 1.0 — валидные значения."""
        bs1 = BeliefState(confidence=0.0)
        bs2 = BeliefState(confidence=1.0)
        assert bs1.confidence == 0.0
        assert bs2.confidence == 1.0

    def test_empty_classmethod(self) -> None:
        """BeliefState.empty() даёт гарантированно пустой state с confidence=0."""
        bs = BeliefState.empty(profile_name="lite")
        assert bs.confidence == 0.0
        assert bs.active_misconception is None
        assert bs.predicted_reactions == {}
        assert bs.profile_used == "lite"
        assert bs.is_usable() is False

    def test_is_usable_threshold(self) -> None:
        """is_usable() возвращает True только когда confidence >= min_confidence."""
        assert BeliefState(confidence=0.5).is_usable() is True
        assert BeliefState(confidence=0.2).is_usable() is False
        assert BeliefState(confidence=0.3).is_usable() is True
        # Custom threshold
        assert BeliefState(confidence=0.4).is_usable(min_confidence=0.5) is False
        assert BeliefState(confidence=0.6).is_usable(min_confidence=0.5) is True

    def test_json_serialization(self) -> None:
        """BeliefState сериализуется в валидный JSON через model_dump()."""
        bs = BeliefState(
            active_misconception="Неверное правило произведения",
            belief_about_topic="Студент считает производную линейным оператором",
            predicted_reactions={
                "scaffolded": "Будет искать контрпример",
                "conceptual_repair": "Увидит противоречие",
            },
            confidence=0.85,
            profile_used="standard",
        )
        dumped = bs.model_dump()
        assert dumped["active_misconception"] == "Неверное правило произведения"
        assert dumped["confidence"] == 0.85
        assert len(dumped["predicted_reactions"]) == 2

    def test_round_trip_serialization(self) -> None:
        """Сериализация и обратная десериализация сохраняют все поля."""
        original = BeliefState(
            active_misconception="test",
            belief_about_topic="тестовая модель",
            predicted_reactions={"encourage": "reaction"},
            confidence=0.7,
            reasoning="rationale",
            profile_used="lite",
        )
        dumped = original.model_dump()
        restored = BeliefState(**dumped)
        assert restored.active_misconception == original.active_misconception
        assert restored.confidence == original.confidence
        assert restored.predicted_reactions == original.predicted_reactions
