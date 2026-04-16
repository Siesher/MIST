"""Tests for Knowledge Forge — KnowledgeGraph, persistence, migration."""

import tempfile
from pathlib import Path

import pytest

from src.knowledge.knowledge_forge import (
    EdgeType,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    NodeType,
)


@pytest.fixture
def empty_graph() -> KnowledgeGraph:
    """Create an empty in-memory graph."""
    return KnowledgeGraph()


@pytest.fixture
def sample_graph() -> KnowledgeGraph:
    """Create a small graph with algebra → calculus prerequisite chain."""
    g = KnowledgeGraph()

    g.add_node(
        KnowledgeNode(
            id="math:algebra:definition",
            node_type=NodeType.CONCEPT,
            title="Алгебра",
            title_en="Algebra",
            content="Раздел математики, изучающий операции над переменными.",
            domain="math",
            difficulty=0.2,
        )
    )
    g.add_node(
        KnowledgeNode(
            id="math:limits:definition",
            node_type=NodeType.CONCEPT,
            title="Пределы",
            title_en="Limits",
            content="Предел функции при x стремящемся к a.",
            domain="math",
            difficulty=0.5,
        )
    )
    g.add_node(
        KnowledgeNode(
            id="math:derivatives:definition",
            node_type=NodeType.CONCEPT,
            title="Производная",
            title_en="Derivative",
            content="Производная как предел отношения приращений.",
            domain="math",
            difficulty=0.6,
        )
    )

    g.add_edge(
        KnowledgeEdge(
            source_id="math:algebra:definition",
            target_id="math:limits:definition",
            edge_type=EdgeType.PREREQUISITE,
        )
    )
    g.add_edge(
        KnowledgeEdge(
            source_id="math:limits:definition",
            target_id="math:derivatives:definition",
            edge_type=EdgeType.PREREQUISITE,
        )
    )

    return g


class TestKnowledgeGraphCRUD:
    """Test basic graph operations."""

    def test_add_and_get_node(self, empty_graph: KnowledgeGraph) -> None:
        node = KnowledgeNode(
            id="test:node",
            node_type=NodeType.CONCEPT,
            title="Test",
            title_en="Test",
            content="Test content",
        )
        empty_graph.add_node(node)
        assert empty_graph.get_node("test:node") is not None
        assert empty_graph.get_node("test:node").title == "Test"

    def test_get_nonexistent_node(self, empty_graph: KnowledgeGraph) -> None:
        assert empty_graph.get_node("nonexistent") is None

    def test_add_edge(self, sample_graph: KnowledgeGraph) -> None:
        assert sample_graph.stats["total_edges"] == 2

    def test_add_edge_missing_node_raises(self, empty_graph: KnowledgeGraph) -> None:
        empty_graph.add_node(
            KnowledgeNode(
                id="a",
                node_type=NodeType.CONCEPT,
                title="A",
                title_en="A",
                content="A",
            )
        )
        with pytest.raises(KeyError):
            empty_graph.add_edge(
                KnowledgeEdge(
                    source_id="a",
                    target_id="nonexistent",
                    edge_type=EdgeType.PREREQUISITE,
                )
            )

    def test_remove_node(self, sample_graph: KnowledgeGraph) -> None:
        assert sample_graph.remove_node("math:algebra:definition")
        assert sample_graph.get_node("math:algebra:definition") is None
        # Edges involving this node should also be removed
        assert sample_graph.stats["total_edges"] == 1

    def test_stats(self, sample_graph: KnowledgeGraph) -> None:
        stats = sample_graph.stats
        assert stats["total_nodes"] == 3
        assert stats["total_edges"] == 2
        assert stats["by_type"]["concept"] == 3


class TestKnowledgeGraphNavigation:
    """Test graph traversal methods."""

    def test_explore(self, sample_graph: KnowledgeGraph) -> None:
        result = sample_graph.explore("math:limits:definition")
        assert result is not None
        assert result["node"]["title"] == "Пределы"
        assert result["degree"] == 2  # 1 incoming + 1 outgoing

    def test_find_path(self, sample_graph: KnowledgeGraph) -> None:
        path = sample_graph.find_path("math:algebra:definition", "math:derivatives:definition")
        assert path is not None
        assert len(path) == 3
        assert path[0] == "math:algebra:definition"
        assert path[-1] == "math:derivatives:definition"

    def test_find_path_no_connection(self, sample_graph: KnowledgeGraph) -> None:
        # Reverse direction — no path from derivatives to algebra
        path = sample_graph.find_path("math:derivatives:definition", "math:algebra:definition")
        assert path is None

    def test_search_by_domain(self, sample_graph: KnowledgeGraph) -> None:
        results = sample_graph.search(domain="math")
        assert len(results) == 3

    def test_search_by_query(self, sample_graph: KnowledgeGraph) -> None:
        results = sample_graph.search(query="Производная")
        assert len(results) == 1
        assert results[0].id == "math:derivatives:definition"


class TestKnowledgeGraphPersistence:
    """Test save/load round-trip."""

    def test_save_and_load(self, sample_graph: KnowledgeGraph) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = Path(f.name)

        sample_graph.save(path)
        loaded = KnowledgeGraph(path)

        assert loaded.stats["total_nodes"] == sample_graph.stats["total_nodes"]
        assert loaded.stats["total_edges"] == sample_graph.stats["total_edges"]

        node = loaded.get_node("math:limits:definition")
        assert node is not None
        assert node.title == "Пределы"

        path.unlink()
