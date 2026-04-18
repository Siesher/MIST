#!/usr/bin/env python3
"""
Полноценная A/B оценка ToM-Tutor на 20 сценариях с ground-truth.

Загружает сценарии из evaluation/scenarios/tom_scenarios.json, прогоняет
в двух режимах (baseline и ToM) и сохраняет Markdown + JSON отчёт для
диплома.

Метрики:
- Gap root-hit rate (main target from spec: 60% -> 80%)
- Gap any-hit rate
- Misconception accuracy (keyword overlap with expected)
- Confidence calibration
- Latency p50/p95
- Per-category breakdown

Usage:
    python evaluation/tom_ab_eval.py
    python evaluation/tom_ab_eval.py --n 5           # subset for debugging
    python evaluation/tom_ab_eval.py --threshold 1.0 # override rerank threshold
"""

import argparse
import json
import logging
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.mental_model_agent import MentalModelAgent  # noqa: E402
from src.knowledge.knowledge_forge import KnowledgeGraph  # noqa: E402
from src.knowledge.navigator import PersonalizedNavigator  # noqa: E402
from src.models.llm_client import LLMClient  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

FORGE_PATH = Path("data/knowledge/forge.json")
SCENARIOS_PATH = Path("evaluation/scenarios/tom_scenarios.json")
REPORTS_DIR = Path("evaluation/reports")


@dataclass
class Scenario:
    name: str
    category: str
    difficulty: str
    mastery: Dict[str, float]
    target_concept: str
    student_message: str
    expected_root_gaps: List[str]
    expected_misconception_keywords: List[str]


def load_scenarios(path: Path) -> List[Scenario]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        Scenario(
            name=s["name"],
            category=s["category"],
            difficulty=s.get("difficulty", ""),
            mastery=s.get("mastery", {}),
            target_concept=s["target_concept"],
            student_message=s["student_message"],
            expected_root_gaps=s["expected_root_gaps"],
            expected_misconception_keywords=s.get("expected_misconception_keywords", []),
        )
        for s in data["scenarios"]
    ]


def check_misconception_hit(belief_text: Optional[str], expected_keywords: List[str]) -> bool:
    """Check if any expected keyword appears in the belief's misconception text."""
    if not belief_text or not expected_keywords:
        return False
    text_lower = belief_text.lower()
    return any(kw.lower() in text_lower for kw in expected_keywords)


def run_scenario(
    scenario: Scenario,
    graph: KnowledgeGraph,
    agent: MentalModelAgent,
) -> Dict:
    """Run one scenario in both baseline and ToM modes."""
    nav = PersonalizedNavigator(graph, scenario.mastery)

    # Baseline
    t0 = time.perf_counter()
    gap_base = nav.diagnose_gap(scenario.name, scenario.target_concept)
    t_base = (time.perf_counter() - t0) * 1000
    base_hit = gap_base.root_gap in scenario.expected_root_gaps
    base_any_hit = any(m in scenario.expected_root_gaps for m in gap_base.missing_prerequisites)

    # ToM inference
    t0 = time.perf_counter()
    belief = agent.infer(
        student_message=scenario.student_message,
        topic=scenario.target_concept.split(":")[1],
    )
    t_infer = (time.perf_counter() - t0) * 1000

    # ToM-aware diagnose (keyword-based rerank)
    t0 = time.perf_counter()
    gap_tom = nav.diagnose_gap(scenario.name, scenario.target_concept, belief_state=belief)

    # LLM-based ranking fallback: когда keyword overlap недостаточен
    # (misconception и prereq в разных словарях), просим LLM сам
    # выбрать самый pedagogically релевантный prereq из top-5 unmastered.
    llm_rank_used = False
    if belief.is_usable(min_confidence=0.7) and gap_tom.missing_prerequisites:
        candidates = []
        for pid in gap_tom.missing_prerequisites[:5]:
            node = graph.get_node(pid)
            if node:
                candidates.append(
                    {
                        "id": pid,
                        "title": node.title,
                        "content": (node.content or "")[:100],
                    }
                )
        if len(candidates) >= 2:
            selected = agent.rank_prereqs_by_relevance(
                scenario.student_message,
                belief,
                candidates,
            )
            if selected and selected != gap_tom.root_gap:
                # Reorder: move LLM selection to front
                gap_tom.root_gap = selected
                rest = [m for m in gap_tom.missing_prerequisites if m != selected]
                gap_tom.missing_prerequisites = [selected] + rest
                llm_rank_used = True

    t_tom_diag = (time.perf_counter() - t0) * 1000
    tom_hit = gap_tom.root_gap in scenario.expected_root_gaps
    tom_any_hit = any(m in scenario.expected_root_gaps for m in gap_tom.missing_prerequisites)

    misc_hit = check_misconception_hit(
        belief.active_misconception, scenario.expected_misconception_keywords
    )

    return {
        "name": scenario.name,
        "category": scenario.category,
        "difficulty": scenario.difficulty,
        "expected_gaps": scenario.expected_root_gaps,
        "expected_misconception_keywords": scenario.expected_misconception_keywords,
        # Baseline
        "baseline_root": gap_base.root_gap,
        "baseline_hit": base_hit,
        "baseline_any_hit": base_any_hit,
        "baseline_latency_ms": round(t_base, 1),
        # ToM
        "tom_root": gap_tom.root_gap,
        "tom_hit": tom_hit,
        "tom_any_hit": tom_any_hit,
        "llm_rank_used": llm_rank_used,
        "tom_latency_ms": round(t_infer + t_tom_diag, 1),
        "tom_infer_ms": round(t_infer, 1),
        # Belief state
        "confidence": round(belief.confidence, 2),
        "misconception": belief.active_misconception,
        "misconception_hit": misc_hit,
        "belief_about_topic": belief.belief_about_topic,
        "reasoning": belief.reasoning,
    }


def aggregate(results: List[Dict]) -> Dict:
    """Compute summary metrics."""
    n = len(results)
    if n == 0:
        return {}

    base_hits = sum(1 for r in results if r["baseline_hit"])
    tom_hits = sum(1 for r in results if r["tom_hit"])
    base_any = sum(1 for r in results if r["baseline_any_hit"])
    tom_any = sum(1 for r in results if r["tom_any_hit"])
    misc_hits = sum(1 for r in results if r["misconception_hit"])
    improved = sum(1 for r in results if r["tom_hit"] and not r["baseline_hit"])
    regressed = sum(1 for r in results if r["baseline_hit"] and not r["tom_hit"])

    tom_latencies = [r["tom_latency_ms"] for r in results]
    confidences = [r["confidence"] for r in results]

    # Per-category breakdown
    by_cat: Dict[str, Dict] = {}
    for r in results:
        cat = r["category"]
        by_cat.setdefault(cat, {"n": 0, "base_hit": 0, "tom_hit": 0, "misc_hit": 0})
        by_cat[cat]["n"] += 1
        by_cat[cat]["base_hit"] += int(r["baseline_hit"])
        by_cat[cat]["tom_hit"] += int(r["tom_hit"])
        by_cat[cat]["misc_hit"] += int(r["misconception_hit"])

    return {
        "n": n,
        "baseline_root_hit_rate": round(base_hits / n, 3),
        "tom_root_hit_rate": round(tom_hits / n, 3),
        "baseline_any_hit_rate": round(base_any / n, 3),
        "tom_any_hit_rate": round(tom_any / n, 3),
        "misconception_accuracy": round(misc_hits / n, 3),
        "scenarios_improved_by_tom": improved,
        "scenarios_regressed_by_tom": regressed,
        "delta_root_hit": round((tom_hits - base_hits) / n, 3),
        "tom_latency_p50_ms": round(statistics.median(tom_latencies), 1),
        "tom_latency_p95_ms": round(
            statistics.quantiles(tom_latencies, n=20)[18]
            if len(tom_latencies) >= 2
            else tom_latencies[0],
            1,
        ),
        "avg_confidence": round(sum(confidences) / n, 2),
        "by_category": {
            cat: {
                "n": v["n"],
                "baseline": f"{v['base_hit']}/{v['n']}",
                "tom": f"{v['tom_hit']}/{v['n']}",
                "misc": f"{v['misc_hit']}/{v['n']}",
            }
            for cat, v in by_cat.items()
        },
    }


def write_markdown(summary: Dict, results: List[Dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ToM-Tutor A/B Evaluation Report",
        "",
        f"**Generated**: {datetime.now().isoformat(timespec='seconds')}",
        f"**Scenarios**: {summary['n']} (from evaluation/scenarios/tom_scenarios.json)",
        "",
        "## Summary",
        "",
        "| Метрика | Baseline | ToM | Delta |",
        "|---------|:--------:|:---:|:-----:|",
        f"| Root-hit rate | {summary['baseline_root_hit_rate']:.1%} | "
        f"**{summary['tom_root_hit_rate']:.1%}** | "
        f"{summary['delta_root_hit']:+.1%} |",
        f"| Any-hit rate | {summary['baseline_any_hit_rate']:.1%} | "
        f"{summary['tom_any_hit_rate']:.1%} | "
        f"{(summary['tom_any_hit_rate'] - summary['baseline_any_hit_rate']):+.1%} |",
        "",
        f"**Misconception accuracy**: {summary['misconception_accuracy']:.1%}",
        f"**Improved by ToM**: {summary['scenarios_improved_by_tom']}",
        f"**Regressed by ToM**: {summary['scenarios_regressed_by_tom']}",
        f"**Avg confidence**: {summary['avg_confidence']:.2f}",
        f"**ToM latency**: p50 {summary['tom_latency_p50_ms']:.0f} ms, "
        f"p95 {summary['tom_latency_p95_ms']:.0f} ms",
        "",
        "## Per-Category Breakdown",
        "",
        "| Category | n | Baseline | ToM | Misconception |",
        "|----------|:-:|:--------:|:---:|:-------------:|",
    ]
    for cat, v in summary["by_category"].items():
        lines.append(f"| {cat} | {v['n']} | {v['baseline']} | {v['tom']} | {v['misc']} |")

    lines.extend(
        [
            "",
            "## Per-Scenario Detail",
            "",
            "| # | Scenario | Baseline | ToM | Conf | Misc | Latency |",
            "|---|----------|:--------:|:---:|:----:|:----:|:-------:|",
        ]
    )
    for i, r in enumerate(results, 1):
        base_mark = "HIT" if r["baseline_hit"] else "miss"
        tom_mark = "HIT" if r["tom_hit"] else "miss"
        misc_mark = "yes" if r["misconception_hit"] else "-"
        lines.append(
            f"| {i} | {r['name']} | {base_mark} | {tom_mark} | "
            f"{r['confidence']:.2f} | {misc_mark} | "
            f"{r['tom_latency_ms']:.0f} ms |"
        )

    lines.extend(
        [
            "",
            "## Failure Analysis",
            "",
            "### Regressed (baseline HIT, ToM miss)",
        ]
    )
    regressions = [r for r in results if r["baseline_hit"] and not r["tom_hit"]]
    if not regressions:
        lines.append("\n*Нет regressions.*")
    else:
        for r in regressions:
            lines.extend(
                [
                    "",
                    f"**{r['name']}** (confidence={r['confidence']:.2f})",
                    f"- Expected: `{r['expected_gaps']}`",
                    f"- Baseline: `{r['baseline_root']}` (HIT)",
                    f"- ToM: `{r['tom_root']}` (miss)",
                    f"- Misconception: {r['misconception']}",
                ]
            )

    lines.extend(["", "### Improved (baseline miss, ToM HIT)"])
    improvements = [r for r in results if r["tom_hit"] and not r["baseline_hit"]]
    if not improvements:
        lines.append("\n*Нет improvements.*")
    else:
        for r in improvements:
            lines.extend(
                [
                    "",
                    f"**{r['name']}** (confidence={r['confidence']:.2f})",
                    f"- Expected: `{r['expected_gaps']}`",
                    f"- Baseline: `{r['baseline_root']}` (miss)",
                    f"- ToM: `{r['tom_root']}` (HIT)",
                    f"- Misconception: {r['misconception']}",
                ]
            )

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="ToM-Tutor A/B evaluation")
    parser.add_argument("--n", type=int, default=None, help="Run first N scenarios only")
    parser.add_argument("--model", type=str, default="qwen3.5:9b")
    args = parser.parse_args()

    print("=" * 72)
    print("ToM-Tutor A/B Evaluation")
    print("=" * 72)

    graph = KnowledgeGraph(FORGE_PATH)
    scenarios = load_scenarios(SCENARIOS_PATH)
    if args.n is not None:
        scenarios = scenarios[: args.n]
    print(f"Loaded {len(scenarios)} scenarios from {SCENARIOS_PATH}")
    print(f"Graph: {graph.stats['total_nodes']} nodes, {graph.stats['total_edges']} edges")

    llm = LLMClient(model=args.model)
    agent = MentalModelAgent(llm_client=llm, knowledge_graph=graph)

    results = []
    for i, sc in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] {sc.name} ({sc.category})...")
        try:
            r = run_scenario(sc, graph, agent)
            results.append(r)
            base_mark = "HIT" if r["baseline_hit"] else "miss"
            tom_mark = "HIT" if r["tom_hit"] else "miss"
            print(
                f"   baseline: {base_mark} | ToM: {tom_mark} | "
                f"conf={r['confidence']:.2f} | {r['tom_latency_ms']:.0f} ms"
            )
        except Exception as e:
            print(f"   ERROR: {e}")
            continue

    summary = aggregate(results)

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"Baseline root-hit:  {summary['baseline_root_hit_rate']:.1%}")
    print(f"ToM root-hit:       {summary['tom_root_hit_rate']:.1%}")
    print(f"Delta:              {summary['delta_root_hit']:+.1%}")
    print(f"Improved scenarios: {summary['scenarios_improved_by_tom']}")
    print(f"Regressed:          {summary['scenarios_regressed_by_tom']}")
    print(f"Misconception acc:  {summary['misconception_accuracy']:.1%}")
    print(f"Avg confidence:     {summary['avg_confidence']:.2f}")
    print(
        f"ToM p50/p95 latency: {summary['tom_latency_p50_ms']:.0f} / "
        f"{summary['tom_latency_p95_ms']:.0f} ms"
    )

    # Save
    ts = datetime.now().strftime("%Y-%m-%d")
    md_path = REPORTS_DIR / f"tom_ab_{ts}.md"
    json_path = REPORTS_DIR / f"tom_ab_{ts}.json"
    write_markdown(summary, results, md_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(
            {"summary": summary, "results": results, "generated_at": datetime.now().isoformat()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nReports saved:\n  {md_path}\n  {json_path}")
    print("=" * 72)


if __name__ == "__main__":
    main()
