"""Tests for SourceExtractor — LLM-based knowledge extraction."""

import json
from unittest.mock import MagicMock

import pytest

from src.knowledge.knowledge_forge import KnowledgeGraph, NodeType
from src.knowledge.source_extractor import SourceExtractor


@pytest.fixture
def mock_llm():
    """Create a mock LLM client that returns predefined JSON."""
    llm = MagicMock()
    return llm


@pytest.fixture
def extractor(mock_llm) -> SourceExtractor:
    """Create extractor with mocked LLM."""
    return SourceExtractor(llm_client=mock_llm, extraction_confidence=0.7)


SAMPLE_ENTITIES_RESPONSE = json.dumps(
    {
        "entities": [
            {
                "type": "concept",
                "title": "Квадратное уравнение",
                "title_en": "Quadratic Equation",
                "content": "Уравнение вида ax^2 + bx + c = 0, где a != 0.",
                "difficulty": 0.4,
                "tags": ["algebra", "equations"],
            },
            {
                "type": "formula",
                "title": "Дискриминант",
                "title_en": "Discriminant",
                "content": "D = b^2 - 4ac",
                "difficulty": 0.3,
                "tags": ["algebra", "formula"],
            },
            {
                "type": "example",
                "title": "Пример: x^2 - 5x + 6 = 0",
                "title_en": "Example: x^2 - 5x + 6 = 0",
                "content": "Решение: D = 25 - 24 = 1, x1 = 3, x2 = 2.",
                "difficulty": 0.3,
                "tags": ["algebra", "example"],
            },
        ]
    }
)

SAMPLE_RELATIONS_RESPONSE = json.dumps(
    {
        "relations": [
            {
                "source": "Квадратное уравнение",
                "target": "Дискриминант",
                "type": "derived_from",
            },
            {
                "source": "Пример: x^2 - 5x + 6 = 0",
                "target": "Квадратное уравнение",
                "type": "illustrates",
            },
        ]
    }
)


class TestSourceExtractor:
    """Test extraction with mocked LLM responses."""

    def test_extract_entities(self, extractor: SourceExtractor, mock_llm) -> None:
        """T038: Extract entities from sample text."""
        mock_llm.generate.side_effect = [
            SAMPLE_ENTITIES_RESPONSE,
            SAMPLE_RELATIONS_RESPONSE,
        ]

        nodes, edges = extractor.extract(
            text="Квадратное уравнение ax^2 + bx + c = 0...",
            domain="math",
            source_name="test_doc",
        )

        assert len(nodes) == 3
        types = {n.node_type for n in nodes}
        assert NodeType.CONCEPT in types
        assert NodeType.FORMULA in types
        assert NodeType.EXAMPLE in types

        # All should have confidence < 1.0
        for node in nodes:
            assert node.confidence == 0.7
            assert node.source == "test_doc"

    def test_extract_relations(self, extractor: SourceExtractor, mock_llm) -> None:
        """T038: Extract relations between entities."""
        mock_llm.generate.side_effect = [
            SAMPLE_ENTITIES_RESPONSE,
            SAMPLE_RELATIONS_RESPONSE,
        ]

        nodes, edges = extractor.extract(
            text="Квадратное уравнение...",
            domain="math",
        )

        assert len(edges) == 2

    def test_deduplication_on_ingest(self, extractor: SourceExtractor, mock_llm) -> None:
        """T039: Extract same text twice, verify no duplicate nodes."""
        mock_llm.generate.side_effect = [
            SAMPLE_ENTITIES_RESPONSE,
            SAMPLE_RELATIONS_RESPONSE,
            SAMPLE_ENTITIES_RESPONSE,
            SAMPLE_RELATIONS_RESPONSE,
        ]

        graph = KnowledgeGraph()

        # First ingestion
        result1 = extractor.ingest(graph, "text...", domain="math", source_name="doc1")
        assert result1["nodes_added"] == 3

        # Second ingestion — should skip all
        result2 = extractor.ingest(graph, "text...", domain="math", source_name="doc2")
        assert result2["nodes_skipped"] == 3
        assert result2["nodes_added"] == 0

    def test_empty_extraction(self, extractor: SourceExtractor, mock_llm) -> None:
        """Handle LLM returning no entities."""
        mock_llm.generate.return_value = json.dumps({"entities": []})

        nodes, edges = extractor.extract(text="Empty text", domain="math")
        assert len(nodes) == 0
        assert len(edges) == 0

    def test_llm_error_handling(self, extractor: SourceExtractor, mock_llm) -> None:
        """Handle LLM failure gracefully."""
        mock_llm.generate.side_effect = Exception("LLM unavailable")

        nodes, edges = extractor.extract(text="Some text", domain="math")
        assert len(nodes) == 0
        assert len(edges) == 0


class TestNodeTypeMapping:
    """Test string-to-enum mapping."""

    def test_valid_types(self) -> None:
        assert SourceExtractor._map_node_type("concept") == NodeType.CONCEPT
        assert SourceExtractor._map_node_type("formula") == NodeType.FORMULA
        assert SourceExtractor._map_node_type("theorem") == NodeType.THEOREM

    def test_unknown_type_defaults_to_concept(self) -> None:
        assert SourceExtractor._map_node_type("unknown") == NodeType.CONCEPT

    def test_slugify(self) -> None:
        assert SourceExtractor._slugify("Quadratic Equation") == "quadratic_equation"
        assert SourceExtractor._slugify("L'Hôpital's Rule") == "l_h_pital_s_rule"
