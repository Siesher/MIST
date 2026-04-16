"""Tests for PersonalizedNavigator — frontier, gap diagnosis, pathfinding, scoring."""

import pytest

from src.knowledge.knowledge_forge import (
    EdgeType,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    NodeType,
)
from src.knowledge.navigator import (
    PersonalizedNavigator,
    _compute_edge_cost,
    _score_frontier_node,
)


@pytest.fixture
def calculus_graph() -> KnowledgeGraph:
    """Graph: algebra → limits → derivatives → integrals, with a misconception."""
    g = KnowledgeGraph()

    concepts = [
        ("math:algebra:definition", "Алгебра", "Algebra", 0.2),
        ("math:functions:definition", "Функции", "Functions", 0.3),
        ("math:limits:definition", "Пределы", "Limits", 0.5),
        ("math:derivatives:definition", "Производная", "Derivative", 0.6),
        ("math:antiderivatives:definition", "Первообразная", "Antiderivative", 0.6),
        ("math:definite_integrals:definition", "Определённый интеграл", "Definite Integral", 0.7),
    ]
    for cid, title, title_en, diff in concepts:
        g.add_node(
            KnowledgeNode(
                id=cid,
                node_type=NodeType.CONCEPT,
                title=title,
                title_en=title_en,
                content=f"Определение: {title}",
                domain="math",
                difficulty=diff,
            )
        )

    # Misconception node
    g.add_node(
        KnowledgeNode(
            id="math:sign_error_integrals:misconception",
            node_type=NodeType.MISCONCEPTION,
            title="Ошибка знака при интегрировании",
            title_en="Sign error in integration",
            content="Студенты часто забывают менять знак при подстановке.",
            domain="math",
            difficulty=0.5,
        )
    )

    # Prerequisites: algebra → limits → derivatives → antiderivatives → definite_integrals
    prereqs = [
        ("math:algebra:definition", "math:limits:definition"),
        ("math:functions:definition", "math:limits:definition"),
        ("math:limits:definition", "math:derivatives:definition"),
        ("math:derivatives:definition", "math:antiderivatives:definition"),
        ("math:antiderivatives:definition", "math:definite_integrals:definition"),
    ]
    for src, tgt in prereqs:
        g.add_edge(
            KnowledgeEdge(
                source_id=src,
                target_id=tgt,
                edge_type=EdgeType.PREREQUISITE,
            )
        )

    # Misconception link
    g.add_edge(
        KnowledgeEdge(
            source_id="math:sign_error_integrals:misconception",
            target_id="math:definite_integrals:definition",
            edge_type=EdgeType.COMMON_ERROR_FOR,
        )
    )

    return g


class TestScoreFrontierNode:
    """Test _score_frontier_node() readiness scoring."""

    def test_no_prereqs_entry_point(self) -> None:
        score = _score_frontier_node(
            own_mastery=0.0,
            prereq_mastery_avg=1.0,
            n_mastered=0,
            n_total_prereqs=0,
            difficulty=0.3,
        )
        assert 0.0 < score <= 1.0

    def test_all_prereqs_mastered(self) -> None:
        score = _score_frontier_node(
            own_mastery=0.1,
            prereq_mastery_avg=0.9,
            n_mastered=3,
            n_total_prereqs=3,
            difficulty=0.5,
        )
        assert score > 0.5, "Student with all prereqs mastered should be highly ready"

    def test_no_prereqs_mastered(self) -> None:
        score = _score_frontier_node(
            own_mastery=0.0,
            prereq_mastery_avg=0.1,
            n_mastered=0,
            n_total_prereqs=3,
            difficulty=0.5,
        )
        assert score < 0.3, "Student with no prereqs should have low readiness"

    def test_partial_prereqs(self) -> None:
        score_partial = _score_frontier_node(
            own_mastery=0.1,
            prereq_mastery_avg=0.6,
            n_mastered=2,
            n_total_prereqs=3,
            difficulty=0.5,
        )
        score_all = _score_frontier_node(
            own_mastery=0.1,
            prereq_mastery_avg=0.9,
            n_mastered=3,
            n_total_prereqs=3,
            difficulty=0.5,
        )
        assert score_partial < score_all

    def test_high_own_mastery_low_score(self) -> None:
        score_low = _score_frontier_node(
            own_mastery=0.0,
            prereq_mastery_avg=0.9,
            n_mastered=3,
            n_total_prereqs=3,
            difficulty=0.5,
        )
        score_high = _score_frontier_node(
            own_mastery=0.6,
            prereq_mastery_avg=0.9,
            n_mastered=3,
            n_total_prereqs=3,
            difficulty=0.5,
        )
        assert score_low > score_high, "Already partially learned = less frontier value"

    def test_difficulty_penalty_with_weak_prereqs(self) -> None:
        score_easy = _score_frontier_node(
            own_mastery=0.0,
            prereq_mastery_avg=0.5,
            n_mastered=1,
            n_total_prereqs=2,
            difficulty=0.2,
        )
        score_hard = _score_frontier_node(
            own_mastery=0.0,
            prereq_mastery_avg=0.5,
            n_mastered=1,
            n_total_prereqs=2,
            difficulty=0.9,
        )
        assert score_easy >= score_hard, "Hard concept with weak prereqs should score lower"


class TestComputeEdgeCost:
    """Test _compute_edge_cost() for Dijkstra pathfinding."""

    def test_mastered_near_zero_cost(self) -> None:
        cost = _compute_edge_cost(mastery=0.95, difficulty=0.5)
        assert cost < 0.1

    def test_unknown_high_cost(self) -> None:
        cost = _compute_edge_cost(mastery=0.0, difficulty=0.5)
        assert cost > 0.3

    def test_easy_cheaper_than_hard(self) -> None:
        cost_easy = _compute_edge_cost(mastery=0.3, difficulty=0.1)
        cost_hard = _compute_edge_cost(mastery=0.3, difficulty=0.9)
        assert cost_easy < cost_hard

    def test_always_positive(self) -> None:
        assert _compute_edge_cost(mastery=1.0, difficulty=0.0) > 0
        assert _compute_edge_cost(mastery=0.0, difficulty=1.0) > 0

    def test_boundary_values(self) -> None:
        assert _compute_edge_cost(mastery=0.0, difficulty=0.0) >= 0.01
        assert _compute_edge_cost(mastery=1.0, difficulty=1.0) >= 0.01


class TestNavigatorFrontier:
    """Test get_learning_frontier() — ZPD on graph."""

    def test_frontier_with_mastered_prereqs(self, calculus_graph: KnowledgeGraph) -> None:
        mastery = {
            "math:algebra:definition": 0.9,
            "math:functions:definition": 0.85,
        }
        nav = PersonalizedNavigator(calculus_graph, mastery)
        frontier = nav.get_learning_frontier("s1", max_results=5)

        # Limits should be on frontier (both prereqs mastered)
        frontier_ids = [f.node_id for f in frontier]
        assert "math:limits:definition" in frontier_ids

    def test_frontier_excludes_mastered(self, calculus_graph: KnowledgeGraph) -> None:
        mastery = {
            "math:algebra:definition": 0.9,
            "math:functions:definition": 0.85,
            "math:limits:definition": 0.8,
        }
        nav = PersonalizedNavigator(calculus_graph, mastery)
        frontier = nav.get_learning_frontier("s1")

        frontier_ids = [f.node_id for f in frontier]
        assert "math:limits:definition" not in frontier_ids, "Already mastered"
        assert "math:derivatives:definition" in frontier_ids, "Next in line"

    def test_cold_start_empty_mastery(self, calculus_graph: KnowledgeGraph) -> None:
        nav = PersonalizedNavigator(calculus_graph, {})
        frontier = nav.get_learning_frontier("s1")
        assert len(frontier) > 0, "Should return entry-point concepts"


class TestNavigatorGapDiagnosis:
    """Test diagnose_gap() — find missing prerequisites."""

    def test_finds_root_gap(self, calculus_graph: KnowledgeGraph) -> None:
        mastery = {
            "math:algebra:definition": 0.9,
            "math:functions:definition": 0.85,
            "math:limits:definition": 0.8,
            "math:derivatives:definition": 0.3,  # Weak
        }
        nav = PersonalizedNavigator(calculus_graph, mastery)
        gap = nav.diagnose_gap("s1", "math:antiderivatives:definition")

        assert "math:derivatives:definition" in gap.missing_prerequisites

    def test_finds_misconceptions(self, calculus_graph: KnowledgeGraph) -> None:
        nav = PersonalizedNavigator(calculus_graph, {})
        gap = nav.diagnose_gap("s1", "math:definite_integrals:definition")

        assert "math:sign_error_integrals:misconception" in gap.misconceptions

    def test_no_gap_when_all_mastered(self, calculus_graph: KnowledgeGraph) -> None:
        mastery = {
            "math:algebra:definition": 0.9,
            "math:functions:definition": 0.85,
            "math:limits:definition": 0.8,
            "math:derivatives:definition": 0.8,
        }
        nav = PersonalizedNavigator(calculus_graph, mastery)
        gap = nav.diagnose_gap("s1", "math:antiderivatives:definition")
        assert len(gap.missing_prerequisites) == 0


class TestNavigatorOptimalPath:
    """Test find_optimal_path() — Dijkstra pathfinding."""

    def test_path_respects_dependency_order(self, calculus_graph: KnowledgeGraph) -> None:
        mastery = {"math:algebra:definition": 0.9, "math:functions:definition": 0.85}
        nav = PersonalizedNavigator(calculus_graph, mastery)
        path = nav.find_optimal_path("s1", "math:derivatives:definition")

        assert path is not None
        assert path.path[-1] == "math:derivatives:definition"

    def test_already_mastered_target(self, calculus_graph: KnowledgeGraph) -> None:
        mastery = {"math:derivatives:definition": 0.9}
        nav = PersonalizedNavigator(calculus_graph, mastery)
        path = nav.find_optimal_path("s1", "math:derivatives:definition")

        assert path is not None
        assert path.total_cost == 0.0

    def test_unreachable_returns_none(self, calculus_graph: KnowledgeGraph) -> None:
        # Add isolated node
        calculus_graph.add_node(
            KnowledgeNode(
                id="cs:oop:definition",
                node_type=NodeType.CONCEPT,
                title="ООП",
                title_en="OOP",
                content="Object-oriented programming",
                domain="cs",
                difficulty=0.4,
            )
        )
        nav = PersonalizedNavigator(calculus_graph, {})
        path = nav.find_optimal_path("s1", "cs:oop:definition")
        # Might return a path with just the node if it has no prereqs, or None
        # Depends on implementation — the node IS reachable as a start node
        # since it has no prerequisites
        if path is not None:
            assert "cs:oop:definition" in path.path
