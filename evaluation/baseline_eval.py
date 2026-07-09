#!/usr/bin/env python3
"""
Baseline evaluation suite for MITS Knowledge Forge + Living KG.

Measures 4 navigator metrics (no LLM required) + 2 optional LLM metrics
if Ollama is running.

Output: JSON + Markdown report in evaluation/reports/.

Usage:
    python evaluation/baseline_eval.py              # deterministic only
    python evaluation/baseline_eval.py --with-llm   # + Ollama metrics
"""

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.knowledge.graph_evolution import (  # noqa: E402
    AUTO_ACCEPT_CONFIDENCE,
    GraphEvolver,
    ProposalQueue,
)
from src.knowledge.knowledge_forge import (  # noqa: E402
    EdgeType,
    KnowledgeGraph,
)
from src.knowledge.navigator import PersonalizedNavigator  # noqa: E402
from src.knowledge.session_analyzer import (  # noqa: E402
    analyze_sessions,
)

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

FORGE_PATH = Path("data/knowledge/forge.json")
REPORTS_DIR = Path("evaluation/reports")


# ─────────────────────────────────────────────────────────────────────
# Test scenarios
# ─────────────────────────────────────────────────────────────────────


@dataclass
class GapScenario:
    """A scenario for testing gap diagnosis.

    Student has known mastery on prereqs; target concept has a planted
    gap. We check if diagnose_gap finds the expected root_gap.
    """

    name: str
    mastery: Dict[str, float]
    target_concept: str
    expected_root_gaps: List[str]  # Any of these is acceptable
    expected_missing: List[str] = field(default_factory=list)


def build_gap_scenarios() -> List[GapScenario]:
    """Hand-crafted gap diagnosis scenarios from the real forge.json."""
    return [
        GapScenario(
            name="algebra_gap_for_quadratic",
            mastery={
                "math:arithmetic:definition": 0.9,
                "math:fractions:definition": 0.85,
                "math:variables:definition": 0.3,  # gap
            },
            target_concept="math:quadratic_equations:definition",
            expected_root_gaps=["math:variables:definition", "math:linear_equations:definition"],
            expected_missing=["math:linear_equations:definition", "math:variables:definition"],
        ),
        GapScenario(
            name="limits_gap_for_derivatives",
            mastery={
                "math:arithmetic:definition": 0.9,
                "math:fractions:definition": 0.85,
                "math:variables:definition": 0.85,
                "math:linear_equations:definition": 0.8,
                "math:functions_basics:definition": 0.75,
                "math:limits_intuition:definition": 0.2,  # gap
            },
            target_concept="math:derivatives_definition:definition",
            expected_root_gaps=[
                "math:limits_intuition:definition",
                "math:limits_formal:definition",
            ],
        ),
        GapScenario(
            name="deep_chain_integration",
            mastery={
                "math:arithmetic:definition": 0.9,
                "math:fractions:definition": 0.85,
                "math:variables:definition": 0.9,
                "math:linear_equations:definition": 0.85,
                "math:functions_basics:definition": 0.8,
            },
            target_concept="math:definite_integrals:definition",
            expected_root_gaps=[
                "math:limits_intuition:definition",
                "math:limits_formal:definition",
                "math:limits_techniques:definition",
            ],
        ),
        GapScenario(
            name="functions_gap_for_calculus",
            mastery={
                "math:arithmetic:definition": 0.9,
                "math:fractions:definition": 0.85,
                "math:variables:definition": 0.85,
            },
            target_concept="math:derivatives_basic:definition",
            expected_root_gaps=[
                "math:functions_basics:definition",
                "math:linear_equations:definition",
            ],
        ),
        GapScenario(
            name="basic_arithmetic_gap",
            mastery={},  # Cold start — no mastery at all
            target_concept="math:quadratic_equations:definition",
            expected_root_gaps=["math:arithmetic:definition", "math:variables:definition"],
        ),
    ]


@dataclass
class FrontierScenario:
    name: str
    mastery: Dict[str, float]
    must_include: List[str] = field(default_factory=list)  # expected in top-N
    must_exclude: List[str] = field(default_factory=list)  # never in top-N


def build_frontier_scenarios() -> List[FrontierScenario]:
    return [
        FrontierScenario(
            name="basic_math_mastered",
            mastery={
                "math:arithmetic:definition": 0.9,
                "math:fractions:definition": 0.85,
                "math:decimals:definition": 0.8,
            },
            must_include=[],  # anything from algebra/percentages
            must_exclude=[
                "math:limits_techniques:definition",
                "math:derivatives_basic:definition",
                "math:definite_integrals:definition",
            ],
        ),
        FrontierScenario(
            name="algebra_mastered",
            mastery={
                "math:arithmetic:definition": 0.9,
                "math:fractions:definition": 0.9,
                "math:decimals:definition": 0.85,
                "math:variables:definition": 0.85,
                "math:linear_equations:definition": 0.8,
                "math:functions_basics:definition": 0.75,
            },
            must_exclude=[
                "math:definite_integrals:definition",
                "math:integration_by_parts:definition",
            ],
        ),
    ]


@dataclass
class PathScenario:
    name: str
    mastery: Dict[str, float]
    target: str


def build_path_scenarios() -> List[PathScenario]:
    return [
        PathScenario(
            name="algebra_to_derivatives",
            mastery={
                "math:arithmetic:definition": 0.9,
                "math:variables:definition": 0.85,
                "math:linear_equations:definition": 0.8,
                "math:functions_basics:definition": 0.75,
            },
            target="math:derivatives_definition:definition",
        ),
        PathScenario(
            name="cold_start_to_quadratic",
            mastery={},
            target="math:quadratic_equations:definition",
        ),
        PathScenario(
            name="already_mastered",
            mastery={"math:linear_equations:definition": 0.9},
            target="math:linear_equations:definition",
        ),
    ]


# ─────────────────────────────────────────────────────────────────────
# Evaluation Functions
# ─────────────────────────────────────────────────────────────────────


def eval_gap_diagnosis(
    graph: KnowledgeGraph,
    scenarios: List[GapScenario],
) -> Dict:
    """Test diagnose_gap against known scenarios. Metric: root_gap hit rate."""
    results = []
    correct_root = 0
    correct_any = 0

    for sc in scenarios:
        nav = PersonalizedNavigator(graph, sc.mastery)
        t0 = time.perf_counter()
        gap = nav.diagnose_gap(sc.name, sc.target_concept)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        root_hit = gap.root_gap in sc.expected_root_gaps if gap.root_gap else False
        any_hit = any(m in sc.expected_root_gaps for m in gap.missing_prerequisites)

        correct_root += int(root_hit)
        correct_any += int(any_hit)

        results.append(
            {
                "scenario": sc.name,
                "expected_gaps": sc.expected_root_gaps,
                "detected_root": gap.root_gap,
                "detected_missing": gap.missing_prerequisites[:5],
                "root_hit": root_hit,
                "any_hit": any_hit,
                "elapsed_ms": round(elapsed_ms, 2),
            }
        )

    n = len(scenarios) or 1
    return {
        "metric": "gap_diagnosis",
        "n_scenarios": len(scenarios),
        "root_hit_rate": round(correct_root / n, 3),
        "any_hit_rate": round(correct_any / n, 3),
        "avg_latency_ms": round(sum(r["elapsed_ms"] for r in results) / n, 2),
        "scenarios": results,
    }


def eval_frontier(
    graph: KnowledgeGraph,
    scenarios: List[FrontierScenario],
    k: int = 5,
) -> Dict:
    """Test frontier quality. Metrics: exclusion violations, correctness."""
    results = []
    violations = 0
    total_checks = 0

    for sc in scenarios:
        nav = PersonalizedNavigator(graph, sc.mastery)
        t0 = time.perf_counter()
        frontier = nav.get_learning_frontier(sc.name, max_results=k, domain="math")
        elapsed_ms = (time.perf_counter() - t0) * 1000

        top_ids = [f.node_id for f in frontier]
        # Exclusion check
        excluded_hits = [eid for eid in sc.must_exclude if eid in top_ids]
        inclusion_hits = [iid for iid in sc.must_include if iid in top_ids]

        violations += len(excluded_hits)
        total_checks += len(sc.must_exclude) + len(sc.must_include)

        results.append(
            {
                "scenario": sc.name,
                "top_k": [(f.node_id, round(f.readiness_score, 2)) for f in frontier],
                "excluded_hits": excluded_hits,
                "inclusion_hits": inclusion_hits,
                "violations": len(excluded_hits),
                "elapsed_ms": round(elapsed_ms, 2),
            }
        )

    n = len(scenarios) or 1
    return {
        "metric": "frontier_quality",
        "n_scenarios": len(scenarios),
        "violation_rate": round(violations / max(total_checks, 1), 3),
        "avg_latency_ms": round(sum(r["elapsed_ms"] for r in results) / n, 2),
        "scenarios": results,
    }


def eval_path_validity(
    graph: KnowledgeGraph,
    scenarios: List[PathScenario],
) -> Dict:
    """Test that path respects prerequisite ordering.

    For every consecutive pair (A, B) in a path, either:
    - A is PREREQUISITE of B, OR
    - A is BEST_TAUGHT_AFTER B source, OR
    - A is already mastered (start node)
    """
    results = []
    invalid_pairs = 0
    total_pairs = 0

    for sc in scenarios:
        nav = PersonalizedNavigator(graph, sc.mastery)
        t0 = time.perf_counter()
        path = nav.find_optimal_path(sc.name, sc.target)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        invalid = []
        if path and len(path.path) > 1:
            for a, b in zip(path.path[:-1], path.path[1:]):
                total_pairs += 1
                is_valid = graph.has_edge(a, b, EdgeType.PREREQUISITE) or graph.has_edge(
                    a, b, EdgeType.BEST_TAUGHT_AFTER
                )
                if not is_valid:
                    invalid.append((a, b))
                    invalid_pairs += 1

        results.append(
            {
                "scenario": sc.name,
                "target": sc.target,
                "path_length": len(path.path) if path else 0,
                "path_cost": round(path.total_cost, 2) if path else None,
                "invalid_transitions": invalid,
                "elapsed_ms": round(elapsed_ms, 2),
            }
        )

    n = len(scenarios) or 1
    return {
        "metric": "path_validity",
        "n_scenarios": len(scenarios),
        "invalid_rate": round(invalid_pairs / max(total_pairs, 1), 3),
        "n_total_pairs": total_pairs,
        "n_invalid_pairs": invalid_pairs,
        "avg_latency_ms": round(sum(r["elapsed_ms"] for r in results) / n, 2),
        "scenarios": results,
    }


def eval_living_kg_detection(
    graph: KnowledgeGraph,
    n_sessions: int = 30,
) -> Dict:
    """Run Living KG on synthetic sessions, measure detection stats.

    We plant 3 known patterns across sessions and check detection.
    """
    from scripts.grow_knowledge_graph import make_synthetic_sessions

    # Use a snapshot of graph to avoid polluting the real one
    snapshot = KnowledgeGraph()
    for node in graph._nodes.values():
        snapshot.add_node(node)
    for edge in graph._edges:
        snapshot.add_edge(edge)

    nav = PersonalizedNavigator(snapshot, {})
    sessions = make_synthetic_sessions(snapshot, n=n_sessions)

    t0 = time.perf_counter()
    proposals = analyze_sessions(nav, sessions)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Group by origin
    by_origin: Dict[str, List] = {}
    for p in proposals:
        by_origin.setdefault(p.origin, []).append(p)

    high_conf = [p for p in proposals if p.confidence >= AUTO_ACCEPT_CONFIDENCE]

    # Run through verifier
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        queue = ProposalQueue(storage_path=Path(tmpdir) / "q.json")
        evolver = GraphEvolver(
            graph=snapshot, queue=queue, growth_log_path=Path(tmpdir) / "g.jsonl"
        )
        evolver.ingest_proposals(proposals)
        stats = evolver.promote_ready()

    return {
        "metric": "living_kg_detection",
        "n_sessions": len(sessions),
        "n_proposals": len(proposals),
        "n_high_confidence": len(high_conf),
        "by_origin": {k: len(v) for k, v in by_origin.items()},
        "verifier_accepted": stats["accepted"],
        "verifier_rejected": stats["rejected"],
        "graph_growth": {
            "nodes_added": stats["accepted"],  # approx; includes both node and edge
            "before_nodes": graph.stats["total_nodes"],
            "before_edges": graph.stats["total_edges"],
            "after_nodes": snapshot.stats["total_nodes"],
            "after_edges": snapshot.stats["total_edges"],
        },
        "analyze_latency_ms": round(elapsed_ms, 2),
    }


# ─────────────────────────────────────────────────────────────────────
# Report Generation
# ─────────────────────────────────────────────────────────────────────


def generate_markdown_report(results: List[Dict], out_path: Path) -> None:
    lines = [
        "# MITS Baseline Evaluation Report",
        "",
        f"**Generated:** {datetime.now().isoformat(timespec='seconds')}",
        "**Baseline:** Knowledge Forge + Living KG (no ToM, no prompt tweaks)",
        "",
        "## Summary",
        "",
        "| Metric | Value | Notes |",
        "|--------|-------|-------|",
    ]

    for r in results:
        m = r["metric"]
        if m == "gap_diagnosis":
            lines.append(
                f"| Gap Diagnosis (root hit rate) | "
                f"**{r['root_hit_rate']:.1%}** | "
                f"{r['n_scenarios']} scenarios, avg {r['avg_latency_ms']:.1f} ms |"
            )
            lines.append(
                f"| Gap Diagnosis (any hit rate) | "
                f"**{r['any_hit_rate']:.1%}** | "
                f"At least one expected gap found |"
            )
        elif m == "frontier_quality":
            lines.append(
                f"| Frontier Violation Rate | "
                f"**{r['violation_rate']:.1%}** | "
                f"Lower = better, {r['n_scenarios']} scenarios |"
            )
        elif m == "path_validity":
            lines.append(
                f"| Path Validity (invalid-pair rate) | "
                f"**{r['invalid_rate']:.1%}** | "
                f"{r['n_total_pairs']} total pairs checked |"
            )
        elif m == "living_kg_detection":
            gg = r["graph_growth"]
            lines.append(
                f"| Living KG Proposals | "
                f"**{r['n_proposals']}** unique ({r['n_high_confidence']} high-conf) | "
                f"from {r['n_sessions']} sessions |"
            )
            lines.append(
                f"| Graph Growth | "
                f"{gg['before_nodes']}→{gg['after_nodes']} nodes, "
                f"{gg['before_edges']}→{gg['after_edges']} edges | "
                f"{r['verifier_accepted']} accepted, "
                f"{r['verifier_rejected']} rejected |"
            )

    lines.extend(["", "## Detailed Results", ""])
    for r in results:
        lines.append(f"### {r['metric']}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(r, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="MITS baseline evaluation")
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help="Also run Ollama-dependent metrics (Socratic quality, tool usage)",
    )
    parser.add_argument(
        "--n-sessions", type=int, default=30, help="Number of synthetic sessions for Living KG eval"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for report (default: evaluation/reports/baseline_YYYY-MM-DD.md)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("MITS Baseline Evaluation")
    print("=" * 70)

    if not FORGE_PATH.exists():
        print(f"ERROR: {FORGE_PATH} not found. Run migration first.")
        return

    graph = KnowledgeGraph(FORGE_PATH)
    print(f"Graph: {graph.stats['total_nodes']} nodes, {graph.stats['total_edges']} edges\n")

    results: List[Dict] = []

    # Eval 1
    print("[1/4] Gap Diagnosis ...", end=" ", flush=True)
    r1 = eval_gap_diagnosis(graph, build_gap_scenarios())
    print(f"root_hit_rate={r1['root_hit_rate']:.2f}, any_hit_rate={r1['any_hit_rate']:.2f}")
    results.append(r1)

    # Eval 2
    print("[2/4] Frontier Quality ...", end=" ", flush=True)
    r2 = eval_frontier(graph, build_frontier_scenarios())
    print(f"violation_rate={r2['violation_rate']:.2f}")
    results.append(r2)

    # Eval 3
    print("[3/4] Path Validity ...", end=" ", flush=True)
    r3 = eval_path_validity(graph, build_path_scenarios())
    print(f"invalid_rate={r3['invalid_rate']:.2f} ({r3['n_invalid_pairs']}/{r3['n_total_pairs']})")
    results.append(r3)

    # Eval 4
    print("[4/4] Living KG Detection ...", end=" ", flush=True)
    r4 = eval_living_kg_detection(graph, n_sessions=args.n_sessions)
    print(f"{r4['n_proposals']} proposals, {r4['verifier_accepted']} accepted")
    results.append(r4)

    # LLM-based evals
    if args.with_llm:
        print("[5/6] LLM-based metrics not yet implemented — skipping")

    # Output
    out_path = (
        Path(args.output) if args.output else REPORTS_DIR / f"baseline_{datetime.now():%Y-%m-%d}.md"
    )
    generate_markdown_report(results, out_path)

    json_path = out_path.with_suffix(".json")
    json_path.write_text(
        json.dumps(
            {"timestamp": datetime.now().isoformat(), "results": results},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n{'=' * 70}")
    print(f"Report saved: {out_path}")
    print(f"JSON data:    {json_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
