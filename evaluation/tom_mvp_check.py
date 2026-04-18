#!/usr/bin/env python3
"""
MVP-проверка ToM-Tutor: root-hit rate на сценариях с реалистичными
student_message (с встроенными misconception).

Сценарии включают реальные ошибочные утверждения студента — именно то,
для чего ToM спроектирован. Без этого ToM возвращает low confidence
и fallback к baseline. Это НЕ баг, это дизайн.

Сравнение:
  baseline — diagnose_gap без belief (pure DFS depth)
  ToM     — diagnose_gap с belief_state от MentalModelAgent

Usage:
    python evaluation/tom_mvp_check.py
"""

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.mental_model_agent import MentalModelAgent  # noqa: E402
from src.knowledge.knowledge_forge import KnowledgeGraph  # noqa: E402
from src.knowledge.navigator import PersonalizedNavigator  # noqa: E402
from src.models.llm_client import LLMClient  # noqa: E402

FORGE_PATH = Path("data/knowledge/forge.json")


@dataclass
class ToMScenario:
    """Сценарий с реалистичным student_message и ground-truth."""

    name: str
    mastery: Dict[str, float]
    target_concept: str
    student_message: str
    expected_root_gaps: List[str]
    expected_misconception_keyword: Optional[str] = None


def build_tom_scenarios() -> List[ToMScenario]:
    """5 сценариев с встроенными misconception в student_message."""
    return [
        ToMScenario(
            name="product_rule_misconception",
            mastery={
                "math:arithmetic:definition": 0.9,
                "math:variables:definition": 0.85,
                "math:functions_basics:definition": 0.75,
                "math:limits_intuition:definition": 0.7,
                "math:limits_formal:definition": 0.65,
                "math:limits_techniques:definition": 0.6,
            },
            target_concept="math:derivatives_basic:definition",
            student_message=(
                "Я взял производную от (x^2)(sin x) и получил "
                "(2x)(cos x) — правильно же? Производная произведения "
                "равна произведению производных."
            ),
            expected_root_gaps=[
                "math:derivatives_definition:definition",
                "math:derivatives_basic:definition",
            ],
            expected_misconception_keyword="произведен",
        ),
        ToMScenario(
            name="linear_chain_misconception",
            mastery={
                "math:arithmetic:definition": 0.9,
                "math:fractions:definition": 0.85,
                "math:variables:definition": 0.3,
            },
            target_concept="math:quadratic_equations:definition",
            student_message=(
                "Я решаю 2x + 5 = 15. Перенёс 5 вправо, получил 2x = 15 + 5 = 20. Значит x = 10."
            ),
            expected_root_gaps=[
                "math:variables:definition",
                "math:linear_equations:definition",
            ],
            expected_misconception_keyword="знак",
        ),
        ToMScenario(
            name="limits_intuition_gap",
            mastery={
                "math:arithmetic:definition": 0.9,
                "math:variables:definition": 0.85,
                "math:linear_equations:definition": 0.8,
                "math:functions_basics:definition": 0.75,
            },
            target_concept="math:derivatives_definition:definition",
            student_message=(
                "Не понимаю, что значит предел функции. Это какое-то значение, "
                "к которому функция приближается, но не достигает? Звучит "
                "противоречиво."
            ),
            expected_root_gaps=[
                "math:limits_intuition:definition",
                "math:limits_formal:definition",
            ],
            expected_misconception_keyword="предел",
        ),
        ToMScenario(
            name="functions_basics_gap",
            mastery={
                "math:arithmetic:definition": 0.9,
                "math:variables:definition": 0.85,
            },
            target_concept="math:derivatives_basic:definition",
            student_message=(
                "А что такое функция? Это просто формула с x, подставил число "
                "и получил другое число?"
            ),
            expected_root_gaps=[
                "math:functions_basics:definition",
                "math:linear_equations:definition",
            ],
            expected_misconception_keyword="функц",
        ),
        ToMScenario(
            name="cold_start_basic",
            mastery={},
            target_concept="math:quadratic_equations:definition",
            student_message=(
                "Мне говорят, что квадратные уравнения — это ax^2+bx+c=0, "
                "но я даже что такое переменная x не очень понимаю."
            ),
            expected_root_gaps=[
                "math:arithmetic:definition",
                "math:variables:definition",
            ],
            expected_misconception_keyword="переменн",
        ),
    ]


def main() -> None:
    print("=" * 70)
    print("ToM-Tutor MVP: проверка root-hit rate на ToM-specific сценариях")
    print("=" * 70)

    graph = KnowledgeGraph(FORGE_PATH)
    scenarios = build_tom_scenarios()
    # Base Qwen3.5-9B — без thinking для структурированного output
    llm = LLMClient(model="qwen3.5:9b")

    baseline_hits = 0
    tom_hits = 0
    misconception_hits = 0
    rows = []

    for sc in scenarios:
        nav = PersonalizedNavigator(graph, sc.mastery)
        agent = MentalModelAgent(llm_client=llm, knowledge_graph=graph)

        # Baseline — без belief_state
        t0 = time.perf_counter()
        gap_base = nav.diagnose_gap(sc.name, sc.target_concept)
        t_base = (time.perf_counter() - t0) * 1000
        base_hit = gap_base.root_gap in sc.expected_root_gaps

        # ToM — infer belief, потом diagnose с belief
        t0 = time.perf_counter()
        belief = agent.infer(
            student_message=sc.student_message,
            topic=sc.target_concept.split(":")[1],
        )
        t_infer = (time.perf_counter() - t0) * 1000

        gap_tom = nav.diagnose_gap(sc.name, sc.target_concept, belief_state=belief)
        tom_hit = gap_tom.root_gap in sc.expected_root_gaps

        # Misconception detection check
        misc_hit = False
        if sc.expected_misconception_keyword and belief.active_misconception:
            misc_hit = (
                sc.expected_misconception_keyword.lower() in belief.active_misconception.lower()
            )

        baseline_hits += int(base_hit)
        tom_hits += int(tom_hit)
        misconception_hits += int(misc_hit)

        rows.append(
            {
                "scenario": sc.name,
                "expected": sc.expected_root_gaps,
                "baseline_root": gap_base.root_gap,
                "baseline_hit": base_hit,
                "tom_root": gap_tom.root_gap,
                "tom_hit": tom_hit,
                "tom_confidence": round(belief.confidence, 2),
                "tom_misconception": belief.active_misconception,
                "misconception_hit": misc_hit,
                "latency_infer_ms": round(t_infer, 1),
                "latency_base_ms": round(t_base, 1),
            }
        )

        print(f"\n[{sc.name}]")
        print(f"  student: {sc.student_message[:80]}...")
        print(f"  baseline: {gap_base.root_gap} — {'HIT' if base_hit else 'miss'}")
        print(
            f"  ToM:      {gap_tom.root_gap} — {'HIT' if tom_hit else 'miss'} "
            f"(conf={belief.confidence:.2f}, {t_infer:.0f} ms)"
        )
        if belief.active_misconception:
            misc_mark = "OK" if misc_hit else "NO"
            print(f"  misc [{misc_mark}]: {belief.active_misconception[:90]}")

    n = len(scenarios)
    print("\n" + "=" * 70)
    print(f"Baseline root-hit rate:  {baseline_hits}/{n} = {baseline_hits / n * 100:.0f}%")
    print(f"ToM root-hit rate:       {tom_hits}/{n} = {tom_hits / n * 100:.0f}%")
    print(
        f"Misconception accuracy:  {misconception_hits}/{n} = {misconception_hits / n * 100:.0f}%"
    )
    delta = (tom_hits - baseline_hits) / n * 100
    print(f"Delta:                   {delta:+.0f}%")
    target = 80
    achieved = tom_hits / n * 100 >= target
    print(f"\nTarget >= {target}%: {'ДОСТИГНУТО' if achieved else 'ещё не достигнуто'}")
    print("=" * 70)

    out = {
        "summary": {
            "baseline_root_hit_rate": baseline_hits / n,
            "tom_root_hit_rate": tom_hits / n,
            "misconception_accuracy": misconception_hits / n,
            "delta": delta / 100,
            "n_scenarios": n,
        },
        "scenarios": rows,
    }
    out_path = Path("evaluation/reports/tom_mvp_check.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nСохранено: {out_path}")


if __name__ == "__main__":
    main()
