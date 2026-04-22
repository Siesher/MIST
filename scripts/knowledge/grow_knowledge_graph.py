#!/usr/bin/env python3
"""
Grow Knowledge Graph from tutoring session traces.

Demo mode (default): generates synthetic sessions to show graph growth.
Production mode (--from-logs): processes real session logs from data/logs/.

Usage:
    python scripts/grow_knowledge_graph.py            # synthetic demo
    python scripts/grow_knowledge_graph.py --from-logs  # real logs
    python scripts/grow_knowledge_graph.py --reset      # reset proposals
"""

import argparse
import logging
import random
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.knowledge.graph_evolution import (  # noqa: E402
    DEFAULT_PROPOSALS_PATH,
    GraphEvolver,
    ProposalQueue,
)
from src.knowledge.knowledge_forge import KnowledgeGraph  # noqa: E402
from src.knowledge.navigator import PersonalizedNavigator  # noqa: E402
from src.knowledge.session_analyzer import (  # noqa: E402
    SessionTrace,
    analyze_sessions,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

FORGE_PATH = Path("data/knowledge/forge.json")


# ─────────────────────────────────────────────────────────────────────
# Synthetic session generators (for demo)
# ─────────────────────────────────────────────────────────────────────


def make_synthetic_sessions(graph: KnowledgeGraph, n: int = 30) -> list:
    """Generate synthetic SessionTrace objects for demo/testing.

    Simulates common real-world patterns:
    - Students failing at a target concept due to gaps in prerequisites
    - Students confusing related concepts
    - Students learning a topic faster after mastering a related one
    """
    rng = random.Random(42)
    traces = []

    # Pick some concept nodes from the graph
    concept_ids = [nid for nid, node in graph._nodes.items() if node.node_type.value == "concept"]
    if len(concept_ids) < 5:
        return []

    # Scenario A: Students failing at "quadratic_equations" due to gaps
    # in "linear_equations" (observed repeatedly — should propose edge if missing)
    target_a = "math:quadratic_equations:definition"
    gap_source_a = "math:factoring:definition"
    if graph.get_node(target_a) and graph.get_node(gap_source_a):
        for i in range(6):
            traces.append(
                SessionTrace(
                    session_id=f"sess_a_{i}_{uuid4().hex[:6]}",
                    student_id=f"student_{i}",
                    topic_id=target_a,
                    concepts_touched=[target_a, gap_source_a],
                    errors=[
                        {
                            "concept_id": gap_source_a,
                            "description": "Ученик не смог разложить многочлен на множители "
                            "для решения квадратного уравнения",
                            "turn": 2,
                        },
                        {
                            "concept_id": target_a,
                            "description": "Неверно применена формула корней",
                            "turn": 4,
                        },
                    ],
                    hints_given=3,
                    resolved=False,
                    mastery_before={
                        "math:arithmetic:definition": 0.9,
                        "math:linear_equations:definition": 0.75,
                        gap_source_a: rng.uniform(0.2, 0.4),
                        target_a: rng.uniform(0.2, 0.5),
                    },
                    mastery_after={target_a: rng.uniform(0.3, 0.6)},
                    duration_sec=rng.uniform(600, 1200),
                )
            )

    # Scenario B: Students confusing limits with continuity
    conc_b1 = "math:limits_formal:definition"
    conc_b2 = "math:limits_techniques:definition"
    if graph.get_node(conc_b1) and graph.get_node(conc_b2):
        for i in range(4):
            traces.append(
                SessionTrace(
                    session_id=f"sess_b_{i}_{uuid4().hex[:6]}",
                    student_id=f"student_{i + 10}",
                    topic_id=conc_b1,
                    concepts_touched=[conc_b1, conc_b2],
                    errors=[
                        {
                            "concept_id": conc_b1,
                            "description": "Смешал определение предела с методом вычисления",
                            "turn": 2,
                        },
                        {
                            "concept_id": conc_b2,
                            "description": "Применил формальное определение там, где нужен "
                            "готовый метод",
                            "turn": 3,
                        },
                    ],
                    hints_given=2,
                    resolved=True,
                    mastery_before={conc_b1: 0.4, conc_b2: 0.5},
                    mastery_after={conc_b1: 0.6, conc_b2: 0.65},
                    duration_sec=rng.uniform(500, 900),
                )
            )

    # Scenario C: Faster learning of "derivatives_basic" after "power_rule"
    target_c = "math:derivatives_basic:definition"
    prereq_c = "math:derivatives_definition:definition"
    if graph.get_node(target_c) and graph.get_node(prereq_c):
        for i in range(3):
            traces.append(
                SessionTrace(
                    session_id=f"sess_c_{i}_{uuid4().hex[:6]}",
                    student_id=f"student_{i + 20}",
                    topic_id=target_c,
                    concepts_touched=[target_c, prereq_c],
                    errors=[],
                    hints_given=1,
                    resolved=True,
                    mastery_before={prereq_c: 0.8, target_c: 0.3},
                    mastery_after={prereq_c: 0.85, target_c: 0.75},
                    duration_sec=rng.uniform(300, 600),
                )
            )

    rng.shuffle(traces)
    return traces[:n]


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Grow the Knowledge Graph")
    parser.add_argument(
        "--from-logs",
        action="store_true",
        help="Process real session logs (not yet implemented — uses synthetic)",
    )
    parser.add_argument(
        "--n-sessions",
        type=int,
        default=30,
        help="Number of synthetic sessions (demo mode only)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Auto-accept confidence threshold",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear the proposal queue before running",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze but do not merge into graph",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Knowledge Graph Evolution — grow from sessions")
    logger.info("=" * 60)

    if not FORGE_PATH.exists():
        logger.error(f"forge.json not found at {FORGE_PATH}. Run migration first.")
        return

    graph = KnowledgeGraph(FORGE_PATH)
    nav = PersonalizedNavigator(graph, {})
    logger.info(
        f"Initial graph: {graph.stats['total_nodes']} nodes, {graph.stats['total_edges']} edges"
    )

    # Reset queue if requested
    if args.reset:
        if DEFAULT_PROPOSALS_PATH.exists():
            DEFAULT_PROPOSALS_PATH.unlink()
            logger.info("Proposal queue cleared")

    # Generate or load sessions
    if args.from_logs:
        logger.warning("Real-log ingestion not yet implemented — using synthetic")
    traces = make_synthetic_sessions(graph, n=args.n_sessions)
    logger.info(f"Generated {len(traces)} synthetic session traces")

    # Analyze sessions
    proposals = analyze_sessions(nav, traces)
    logger.info(f"Produced {len(proposals)} unique proposals from sessions")

    if not proposals:
        logger.info("Nothing to propose. Exiting.")
        return

    # Show top proposals by confidence
    proposals_sorted = sorted(proposals, key=lambda p: -p.confidence)
    logger.info("")
    logger.info("Top proposals:")
    for p in proposals_sorted[:10]:
        payload_summary = (
            p.payload.get("title", "")[:50]
            if p.kind.value == "new_node"
            else f"{p.payload.get('source_id', '')} --[{p.payload.get('edge_type', '')}]--> "
            f"{p.payload.get('target_id', '')}"
        )
        logger.info(
            f"  [{p.confidence:.2f}] {p.kind.value}: {payload_summary} "
            f"(evidence: {len(p.evidence)}, origin: {p.origin})"
        )

    if args.dry_run:
        logger.info("Dry-run mode: proposals NOT applied. Exiting.")
        return

    # Load queue and ingest
    queue = ProposalQueue()
    evolver = GraphEvolver(graph, queue=queue)
    evolver.ingest_proposals(proposals)

    # Promote ready proposals
    stats = evolver.promote_ready(threshold=args.threshold)
    logger.info("")
    logger.info("=" * 60)
    logger.info(
        f"RESULTS: accepted={stats['accepted']}, rejected={stats['rejected']}, "
        f"skipped={stats['skipped']}"
    )
    logger.info("=" * 60)

    # Save
    queue.save()
    if stats["accepted"] > 0:
        graph.save(FORGE_PATH)
        logger.info(
            f"Graph saved: {graph.stats['total_nodes']} nodes, {graph.stats['total_edges']} edges"
        )
    logger.info(f"Pending proposals: {len(queue.pending())}")


if __name__ == "__main__":
    main()
