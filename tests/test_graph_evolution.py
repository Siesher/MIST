"""Tests for Living Knowledge Graph — session analyzer + graph evolution."""

from pathlib import Path

import pytest

from src.knowledge.graph_evolution import (
    AUTO_ACCEPT_CONFIDENCE,
    GraphEvolver,
    ProposalQueue,
    rule_based_verifier,
)
from src.knowledge.knowledge_forge import (
    EdgeType,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    NodeType,
)
from src.knowledge.navigator import PersonalizedNavigator
from src.knowledge.session_analyzer import (
    GraphProposal,
    ProposalKind,
    SessionAnalyzer,
    SessionTrace,
    analyze_sessions,
)


@pytest.fixture
def base_graph() -> KnowledgeGraph:
    """Small graph: algebra → linear_equations → quadratic_equations."""
    g = KnowledgeGraph()
    for cid, title, diff in [
        ("math:algebra:definition", "Алгебра", 0.2),
        ("math:linear_equations:definition", "Линейные уравнения", 0.3),
        ("math:factoring:definition", "Разложение", 0.4),
        ("math:quadratic_equations:definition", "Квадратные уравнения", 0.5),
        ("math:polynomials:definition", "Многочлены", 0.4),
    ]:
        g.add_node(
            KnowledgeNode(
                id=cid,
                node_type=NodeType.CONCEPT,
                title=title,
                title_en=cid,
                content=f"Content: {title}",
                domain="math",
                difficulty=diff,
            )
        )

    # Canonical prerequisite chain
    for src, tgt in [
        ("math:algebra:definition", "math:linear_equations:definition"),
        ("math:linear_equations:definition", "math:quadratic_equations:definition"),
        ("math:polynomials:definition", "math:factoring:definition"),
    ]:
        g.add_edge(KnowledgeEdge(source_id=src, target_id=tgt, edge_type=EdgeType.PREREQUISITE))
    return g


@pytest.fixture
def navigator(base_graph: KnowledgeGraph) -> PersonalizedNavigator:
    return PersonalizedNavigator(base_graph, {})


# ─────────────────────────────────────────────────────────────────────
# Session Analyzer
# ─────────────────────────────────────────────────────────────────────


class TestSessionAnalyzer:
    def test_detects_missed_prerequisite(self, navigator: PersonalizedNavigator) -> None:
        """Student failed at X, also struggled with C; graph had no edge C→X."""
        trace = SessionTrace(
            session_id="sess_1",
            student_id="s1",
            topic_id="math:quadratic_equations:definition",
            errors=[
                {
                    "concept_id": "math:factoring:definition",
                    "description": "Не смог разложить многочлен",
                    "turn": 2,
                },
            ],
            resolved=False,
        )
        analyzer = SessionAnalyzer(navigator)
        proposals = analyzer.analyze(trace)

        # Should propose PREREQUISITE edge factoring → quadratic_equations
        prereq_proposals = [
            p
            for p in proposals
            if p.kind == ProposalKind.NEW_EDGE
            and p.payload.get("edge_type") == EdgeType.PREREQUISITE.value
        ]
        assert len(prereq_proposals) >= 1
        assert prereq_proposals[0].payload["source_id"] == "math:factoring:definition"

    def test_detects_confusion_pattern(self, navigator: PersonalizedNavigator) -> None:
        """Student errors alternate between two concepts."""
        trace = SessionTrace(
            session_id="sess_2",
            student_id="s1",
            topic_id="math:linear_equations:definition",
            errors=[
                {
                    "concept_id": "math:linear_equations:definition",
                    "description": "Error A description long enough",
                },
                {
                    "concept_id": "math:factoring:definition",
                    "description": "Error B description long enough",
                },
            ],
            resolved=False,
        )
        analyzer = SessionAnalyzer(navigator)
        proposals = analyzer.analyze(trace)

        confusion = [
            p
            for p in proposals
            if p.kind == ProposalKind.NEW_EDGE
            and p.payload.get("edge_type") == EdgeType.CONFUSED_WITH.value
        ]
        assert len(confusion) >= 1

    def test_detects_new_misconception(self, navigator: PersonalizedNavigator) -> None:
        trace = SessionTrace(
            session_id="sess_3",
            student_id="s1",
            topic_id="math:quadratic_equations:definition",
            errors=[
                {
                    "concept_id": "math:quadratic_equations:definition",
                    "description": "Уникальная ошибка которой нет в графе миссконцепций",
                },
            ],
            resolved=False,
        )
        analyzer = SessionAnalyzer(navigator)
        proposals = analyzer.analyze(trace)

        miscs = [p for p in proposals if p.kind == ProposalKind.NEW_NODE]
        assert len(miscs) >= 1
        assert miscs[0].payload["node_type"] == NodeType.MISCONCEPTION.value

    def test_detects_pedagogical_ordering(self, navigator: PersonalizedNavigator) -> None:
        trace = SessionTrace(
            session_id="sess_4",
            student_id="s1",
            topic_id="math:quadratic_equations:definition",
            resolved=True,
            mastery_before={
                "math:algebra:definition": 0.9,
                "math:linear_equations:definition": 0.85,
                "math:quadratic_equations:definition": 0.2,
            },
            mastery_after={"math:quadratic_equations:definition": 0.7},
        )
        analyzer = SessionAnalyzer(navigator)
        proposals = analyzer.analyze(trace)

        # Should NOT propose BEST_TAUGHT_AFTER for linear_equations
        # because PREREQUISITE edge already exists
        taught_after = [
            p for p in proposals if p.payload.get("edge_type") == EdgeType.BEST_TAUGHT_AFTER.value
        ]
        # algebra has no direct prereq edge to quadratic — could be proposed
        # linear_equations has prereq edge — should NOT be proposed
        sources = [p.payload["source_id"] for p in taught_after]
        assert "math:linear_equations:definition" not in sources

    def test_evidence_accumulates_across_sessions(self, navigator: PersonalizedNavigator) -> None:
        traces = [
            SessionTrace(
                session_id=f"sess_{i}",
                student_id=f"s{i}",
                topic_id="math:quadratic_equations:definition",
                errors=[
                    {
                        "concept_id": "math:factoring:definition",
                        "description": "failed factoring",
                    }
                ],
                resolved=False,
            )
            for i in range(5)
        ]
        proposals = analyze_sessions(navigator, traces)
        # Same proposal key across 5 sessions → 5 evidences → high confidence
        prereq = [
            p
            for p in proposals
            if p.kind == ProposalKind.NEW_EDGE
            and p.payload.get("edge_type") == EdgeType.PREREQUISITE.value
        ]
        assert len(prereq) == 1
        assert len(prereq[0].evidence) == 5
        assert prereq[0].confidence > 0.8


# ─────────────────────────────────────────────────────────────────────
# Rule-based verifier
# ─────────────────────────────────────────────────────────────────────


class TestRuleBasedVerifier:
    def test_rejects_cycle_creating_prerequisite(self, base_graph: KnowledgeGraph) -> None:
        """quadratic → linear would create cycle (linear → quadratic exists)."""
        proposal = GraphProposal(
            kind=ProposalKind.NEW_EDGE,
            payload={
                "source_id": "math:quadratic_equations:definition",
                "target_id": "math:linear_equations:definition",
                "edge_type": EdgeType.PREREQUISITE.value,
            },
            confidence=0.9,
        )
        ok, reason = rule_based_verifier(proposal, base_graph)
        assert not ok
        assert "cycle" in reason

    def test_rejects_self_loop(self, base_graph: KnowledgeGraph) -> None:
        proposal = GraphProposal(
            kind=ProposalKind.NEW_EDGE,
            payload={
                "source_id": "math:algebra:definition",
                "target_id": "math:algebra:definition",
                "edge_type": EdgeType.PREREQUISITE.value,
            },
            confidence=0.9,
        )
        ok, reason = rule_based_verifier(proposal, base_graph)
        assert not ok
        assert "self-loop" in reason

    def test_rejects_existing_edge(self, base_graph: KnowledgeGraph) -> None:
        proposal = GraphProposal(
            kind=ProposalKind.NEW_EDGE,
            payload={
                "source_id": "math:algebra:definition",
                "target_id": "math:linear_equations:definition",
                "edge_type": EdgeType.PREREQUISITE.value,
            },
            confidence=0.9,
        )
        ok, reason = rule_based_verifier(proposal, base_graph)
        assert not ok
        assert "already exists" in reason

    def test_accepts_valid_new_edge(self, base_graph: KnowledgeGraph) -> None:
        proposal = GraphProposal(
            kind=ProposalKind.NEW_EDGE,
            payload={
                "source_id": "math:algebra:definition",
                "target_id": "math:factoring:definition",
                "edge_type": EdgeType.PREREQUISITE.value,
            },
            confidence=0.9,
        )
        ok, _ = rule_based_verifier(proposal, base_graph)
        assert ok

    def test_rejects_short_content_node(self, base_graph: KnowledgeGraph) -> None:
        proposal = GraphProposal(
            kind=ProposalKind.NEW_NODE,
            payload={
                "id": "math:new:misc",
                "node_type": "misconception",
                "title": "x",
                "content": "bad",
            },
            confidence=0.9,
        )
        ok, reason = rule_based_verifier(proposal, base_graph)
        assert not ok
        assert "too short" in reason


# ─────────────────────────────────────────────────────────────────────
# Proposal Queue + Evolver
# ─────────────────────────────────────────────────────────────────────


class TestProposalQueue:
    def test_save_and_load(self, tmp_path: Path) -> None:
        queue = ProposalQueue(storage_path=tmp_path / "proposals.json")
        prop = GraphProposal(
            kind=ProposalKind.NEW_NODE,
            payload={"id": "x:y:z", "title": "Test"},
            origin="test",
        )
        prop.add_evidence("sess1", reason="test reason")
        queue.add_or_merge(prop)
        queue.save()

        # Reload
        queue2 = ProposalQueue(storage_path=tmp_path / "proposals.json")
        assert len(queue2.pending()) == 1

    def test_evidence_merging(self, tmp_path: Path) -> None:
        queue = ProposalQueue(storage_path=tmp_path / "q.json")
        for i in range(3):
            p = GraphProposal(
                kind=ProposalKind.NEW_NODE,
                payload={"id": "x:y:z"},
                origin="test",
            )
            p.add_evidence(f"sess{i}", reason="")
            queue.add_or_merge(p)
        # Should be 1 unique proposal with 3 evidences
        pending = queue.pending()
        assert len(pending) == 1
        assert len(pending[0].evidence) == 3
        assert pending[0].confidence > 0.5


class TestGraphEvolver:
    def test_promotes_high_confidence(self, base_graph: KnowledgeGraph, tmp_path: Path) -> None:
        queue = ProposalQueue(storage_path=tmp_path / "q.json")
        evolver = GraphEvolver(
            graph=base_graph,
            queue=queue,
            growth_log_path=tmp_path / "growth.jsonl",
        )

        # Build a valid high-confidence proposal
        prop = GraphProposal(
            kind=ProposalKind.NEW_EDGE,
            payload={
                "source_id": "math:algebra:definition",
                "target_id": "math:factoring:definition",
                "edge_type": EdgeType.PREREQUISITE.value,
            },
            origin="test",
        )
        # Accumulate enough evidence to exceed threshold
        for i in range(6):
            prop.add_evidence(f"sess{i}", reason="")

        assert prop.confidence >= AUTO_ACCEPT_CONFIDENCE

        evolver.ingest_proposals([prop])
        stats = evolver.promote_ready()

        assert stats["accepted"] == 1
        # Edge should now exist in graph
        assert base_graph.has_edge(
            "math:algebra:definition",
            "math:factoring:definition",
            EdgeType.PREREQUISITE,
        )

    def test_keeps_low_confidence_in_queue(
        self, base_graph: KnowledgeGraph, tmp_path: Path
    ) -> None:
        queue = ProposalQueue(storage_path=tmp_path / "q.json")
        evolver = GraphEvolver(
            graph=base_graph,
            queue=queue,
            growth_log_path=tmp_path / "growth.jsonl",
        )
        prop = GraphProposal(
            kind=ProposalKind.NEW_EDGE,
            payload={
                "source_id": "math:algebra:definition",
                "target_id": "math:factoring:definition",
                "edge_type": EdgeType.PREREQUISITE.value,
            },
            origin="test",
            confidence=0.4,
        )
        prop.add_evidence("sess1", reason="")
        evolver.ingest_proposals([prop])
        stats = evolver.promote_ready()

        assert stats["accepted"] == 0
        assert len(queue.pending()) == 1

    def test_rejected_proposal_leaves_queue(
        self, base_graph: KnowledgeGraph, tmp_path: Path
    ) -> None:
        queue = ProposalQueue(storage_path=tmp_path / "q.json")
        evolver = GraphEvolver(
            graph=base_graph,
            queue=queue,
            growth_log_path=tmp_path / "growth.jsonl",
        )
        # Propose cycle-creating edge
        prop = GraphProposal(
            kind=ProposalKind.NEW_EDGE,
            payload={
                "source_id": "math:quadratic_equations:definition",
                "target_id": "math:linear_equations:definition",
                "edge_type": EdgeType.PREREQUISITE.value,
            },
            origin="test",
        )
        for i in range(6):
            prop.add_evidence(f"s{i}", reason="")

        evolver.ingest_proposals([prop])
        stats = evolver.promote_ready()
        assert stats["rejected"] == 1
        assert len(queue.pending()) == 0  # Rejected removed from queue
