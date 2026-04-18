"""Тесты для MentalModelAgent и BeliefState (ToM-Tutor, фича 017)."""

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.agents.mental_model_agent import MentalModelAgent
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


# ─────────────────────────────────────────────────────────────────────
# T009-T011: Тесты MentalModelAgent (US1)
# ─────────────────────────────────────────────────────────────────────


SAMPLE_VALID_RESPONSE = json.dumps(
    {
        "active_misconception": "Неверное применение правила произведения",
        "belief_about_topic": "Студент считает производную линейным оператором",
        "predicted_reactions": {
            "scaffolded": "Будет искать контрпример",
            "conceptual_repair": "Увидит противоречие",
            "encourage": "Останется при своей точке зрения",
        },
        "candidate_misconceptions": [],
        "confidence": 0.85,
        "reasoning": "Типичный паттерн ошибки.",
    },
    ensure_ascii=False,
)


@pytest.fixture
def mock_llm_valid():
    """LLM mock, возвращающий валидный JSON-ответ."""
    llm = MagicMock()
    llm.generate.return_value = SAMPLE_VALID_RESPONSE
    return llm


@pytest.fixture
def mock_llm_invalid_json():
    """LLM mock, возвращающий невалидный JSON на обе попытки."""
    llm = MagicMock()
    llm.generate.return_value = "Sorry, I cannot parse this request."
    return llm


@pytest.fixture
def mock_llm_partial_json():
    """LLM mock, возвращающий JSON только после repair-попытки."""
    llm = MagicMock()
    llm.generate.side_effect = [
        "Thinking... not valid json",
        SAMPLE_VALID_RESPONSE,
    ]
    return llm


@pytest.fixture
def mock_llm_exception():
    """LLM mock, падающий с исключением (таймаут / Ollama недоступна)."""
    llm = MagicMock()
    llm.generate.side_effect = TimeoutError("LLM timeout after 2000ms")
    return llm


class TestMentalModelAgent:
    """T009-T011: unit-тесты для агента с моками LLM."""

    def test_returns_valid_belief_on_valid_llm(self, mock_llm_valid) -> None:
        """T009: при валидном LLM-ответе получаем BeliefState с confidence > 0."""
        agent = MentalModelAgent(llm_client=mock_llm_valid)
        belief = agent.infer(
            student_message="производная произведения = произведение производных",
            topic="derivatives",
        )
        assert belief.confidence > 0.5
        assert belief.is_usable()
        assert "произведения" in (belief.active_misconception or "").lower()
        assert len(belief.predicted_reactions) == 3

    def test_empty_message_skips_inference(self, mock_llm_valid) -> None:
        """Пустое сообщение → empty BeliefState, LLM не вызывается."""
        agent = MentalModelAgent(llm_client=mock_llm_valid)
        belief = agent.infer(student_message="")
        assert belief.confidence == 0.0
        assert not belief.is_usable()
        mock_llm_valid.generate.assert_not_called()

    def test_invalid_json_returns_empty(self, mock_llm_invalid_json) -> None:
        """T010: невалидный JSON на обеих попытках → empty BeliefState без исключений."""
        agent = MentalModelAgent(llm_client=mock_llm_invalid_json)
        belief = agent.infer(student_message="тест")
        assert belief.confidence == 0.0
        assert not belief.is_usable()
        # Агент должен попытаться 2 раза (основная + repair)
        assert mock_llm_invalid_json.generate.call_count == 2

    def test_repair_pass_succeeds(self, mock_llm_partial_json) -> None:
        """Repair-попытка восстанавливает BeliefState когда первая дала мусор."""
        agent = MentalModelAgent(llm_client=mock_llm_partial_json)
        belief = agent.infer(student_message="тест")
        assert belief.confidence > 0
        assert mock_llm_partial_json.generate.call_count == 2

    def test_exception_returns_empty(self, mock_llm_exception) -> None:
        """T011: исключение LLM (таймаут) → empty BeliefState, не падаем."""
        agent = MentalModelAgent(llm_client=mock_llm_exception)
        belief = agent.infer(student_message="тест")
        assert belief.confidence == 0.0
        assert not belief.is_usable()

    def test_profile_used_recorded(self, mock_llm_valid) -> None:
        """В BeliefState.profile_used записывается активный профиль."""
        agent = MentalModelAgent(llm_client=mock_llm_valid)
        belief = agent.infer(student_message="тест")
        assert belief.profile_used in ("lite", "standard", "max", "unknown")

    def test_json_parsing_strips_markdown_fence(self) -> None:
        """Парсер JSON умеет снимать ```json ... ``` обёртку."""
        # Напрямую тестируем _parse_json без LLM
        wrapped = f"```json\n{SAMPLE_VALID_RESPONSE}\n```"
        parsed = MentalModelAgent._parse_json(wrapped)
        assert parsed is not None
        assert parsed["confidence"] == 0.85

    def test_json_parsing_handles_preamble(self) -> None:
        """Парсер находит JSON даже если перед ним текст."""
        wrapped = f"Here is my analysis: {SAMPLE_VALID_RESPONSE} End."
        parsed = MentalModelAgent._parse_json(wrapped)
        assert parsed is not None
        assert parsed["confidence"] == 0.85

    def test_confidence_clipped_to_range(self, monkeypatch) -> None:
        """Confidence вне [0,1] из LLM-ответа приводится к границе."""
        llm = MagicMock()
        llm.generate.return_value = json.dumps(
            {
                "active_misconception": "x",
                "belief_about_topic": "y",
                "predicted_reactions": {},
                "confidence": 1.5,  # невалидное значение
                "reasoning": "",
            }
        )
        agent = MentalModelAgent(llm_client=llm)
        belief = agent.infer(student_message="тест")
        assert 0.0 <= belief.confidence <= 1.0


class TestNavigatorBeliefReranking:
    """T012-T013: Navigator.diagnose_gap использует belief_state для re-ranking."""

    def test_diagnose_gap_without_belief_unchanged(self) -> None:
        """T013: без belief_state поведение идентично baseline (depth-based)."""
        from src.knowledge.knowledge_forge import (
            EdgeType,
            KnowledgeEdge,
            KnowledgeGraph,
            KnowledgeNode,
            NodeType,
        )
        from src.knowledge.navigator import PersonalizedNavigator

        g = KnowledgeGraph()
        for cid in ["a", "b", "c"]:
            g.add_node(
                KnowledgeNode(
                    id=f"m:{cid}:definition",
                    node_type=NodeType.CONCEPT,
                    title=cid.upper(),
                    title_en=cid,
                    content=cid,
                    domain="math",
                    difficulty=0.5,
                )
            )
        g.add_edge(
            KnowledgeEdge(
                source_id="m:a:definition",
                target_id="m:b:definition",
                edge_type=EdgeType.PREREQUISITE,
            )
        )
        g.add_edge(
            KnowledgeEdge(
                source_id="m:b:definition",
                target_id="m:c:definition",
                edge_type=EdgeType.PREREQUISITE,
            )
        )

        nav = PersonalizedNavigator(g, {})
        # Без belief_state → depth-based (самый глубокий = a)
        gap = nav.diagnose_gap("s1", "m:c:definition")
        assert gap.root_gap == "m:a:definition"

    def test_diagnose_gap_reranks_with_belief(self) -> None:
        """T012: belief_state с совпадением по тегам меняет root_gap."""
        from src.knowledge.knowledge_forge import (
            EdgeType,
            KnowledgeEdge,
            KnowledgeGraph,
            KnowledgeNode,
            NodeType,
        )
        from src.knowledge.navigator import PersonalizedNavigator

        g = KnowledgeGraph()
        # Два unmastered prereq разной глубины,
        # но shallow имеет совпадение с misconception
        g.add_node(
            KnowledgeNode(
                id="m:shallow:definition",
                node_type=NodeType.CONCEPT,
                title="Правило произведения",
                title_en="product_rule",
                content="Правило произведения производных",
                domain="math",
                tags=["произведение", "производная"],
                difficulty=0.5,
            )
        )
        g.add_node(
            KnowledgeNode(
                id="m:deep:definition",
                node_type=NodeType.CONCEPT,
                title="Пределы",
                title_en="limits",
                content="Пределы",
                domain="math",
                tags=["предел"],
                difficulty=0.5,
            )
        )
        g.add_node(
            KnowledgeNode(
                id="m:target:definition",
                node_type=NodeType.CONCEPT,
                title="Производные",
                title_en="derivatives",
                content="Производные",
                domain="math",
                difficulty=0.6,
            )
        )
        # deep → shallow → target (цепочка prereq)
        g.add_edge(
            KnowledgeEdge(
                source_id="m:deep:definition",
                target_id="m:shallow:definition",
                edge_type=EdgeType.PREREQUISITE,
            )
        )
        g.add_edge(
            KnowledgeEdge(
                source_id="m:shallow:definition",
                target_id="m:target:definition",
                edge_type=EdgeType.PREREQUISITE,
            )
        )

        nav = PersonalizedNavigator(g, {})

        # Без belief: root = deep (самый глубокий)
        gap_baseline = nav.diagnose_gap("s1", "m:target:definition")
        assert gap_baseline.root_gap == "m:deep:definition"

        # С belief про правило произведения: root должен стать shallow
        belief = BeliefState(
            active_misconception="Неверное применение правила произведения",
            belief_about_topic="Студент путает правило произведения",
            predicted_reactions={"scaffolded": "test"},
            confidence=0.8,
        )
        gap_tom = nav.diagnose_gap("s1", "m:target:definition", belief_state=belief)
        assert gap_tom.root_gap == "m:shallow:definition"

    def test_diagnose_gap_low_confidence_ignores_belief(self) -> None:
        """При confidence < 0.5 belief_state игнорируется (fallback к depth)."""
        from src.knowledge.knowledge_forge import (
            EdgeType,
            KnowledgeEdge,
            KnowledgeGraph,
            KnowledgeNode,
            NodeType,
        )
        from src.knowledge.navigator import PersonalizedNavigator

        g = KnowledgeGraph()
        for cid, title in [("a", "Правило произведения"), ("b", "B"), ("c", "C")]:
            g.add_node(
                KnowledgeNode(
                    id=f"m:{cid}:definition",
                    node_type=NodeType.CONCEPT,
                    title=title,
                    title_en=cid,
                    content=title,
                    domain="math",
                    difficulty=0.5,
                )
            )
        g.add_edge(
            KnowledgeEdge(
                source_id="m:a:definition",
                target_id="m:b:definition",
                edge_type=EdgeType.PREREQUISITE,
            )
        )
        g.add_edge(
            KnowledgeEdge(
                source_id="m:b:definition",
                target_id="m:c:definition",
                edge_type=EdgeType.PREREQUISITE,
            )
        )

        nav = PersonalizedNavigator(g, {})
        # Низкая уверенность — belief игнорируется, root = a (deepest)
        belief_weak = BeliefState(
            active_misconception="правило произведения",
            belief_about_topic="test",
            confidence=0.2,
        )
        gap = nav.diagnose_gap("s1", "m:c:definition", belief_state=belief_weak)
        assert gap.root_gap == "m:a:definition"
