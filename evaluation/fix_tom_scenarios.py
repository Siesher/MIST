#!/usr/bin/env python3
"""
Диагностика и авто-коррекция scenarios с реальными prereq chains из графа.

Для каждого scenario выводит:
- target concept
- unmastered prereqs в chain (что baseline НА САМОМ ДЕЛЕ найдёт)
- suggested expected_root_gaps

Ничего не меняет сам — только печатает отчёт, по которому можно вручную
скорректировать scenarios/tom_scenarios.json.

Usage:
    python evaluation/fix_tom_scenarios.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.knowledge.knowledge_forge import KnowledgeGraph  # noqa: E402
from src.knowledge.navigator import PersonalizedNavigator  # noqa: E402


def main() -> None:
    graph = KnowledgeGraph(Path("data/knowledge/forge.json"))
    data = json.loads(Path("evaluation/scenarios/tom_scenarios.json").read_text(encoding="utf-8"))

    print(f"{'Scenario':<35} | {'Target':<38} | {'Actual unmastered prereqs'}")
    print("-" * 120)

    for sc in data["scenarios"]:
        name = sc["name"]
        target = sc["target_concept"]
        mastery = sc.get("mastery", {})

        nav = PersonalizedNavigator(graph, mastery)
        gap = nav.diagnose_gap(name, target)

        short_target = target.split(":")[1] if ":" in target else target

        if not gap.missing_prerequisites:
            status = "NO UNMASTERED PREREQ"
        else:
            # Show first 3 unmastered
            short_missing = [m.split(":")[1] for m in gap.missing_prerequisites[:4]]
            status = ", ".join(short_missing)

        expected_short = [e.split(":")[1] for e in sc["expected_root_gaps"]]
        in_chain = any(e in gap.missing_prerequisites for e in sc["expected_root_gaps"])
        marker = "OK " if in_chain else "BAD"

        print(f"{marker} {name:<32} | {short_target:<38} | {status}")
        print(f"    expected: {expected_short}")
        print()


if __name__ == "__main__":
    main()
