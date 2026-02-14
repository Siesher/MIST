"""
Socratic Score Benchmark

Analyzes tutor responses for guiding questions vs direct answers.
Computes:
- Socratic Score: ratio of guiding responses to total responses
- Telling Rate: ratio of direct answer responses to total responses

A good Socratic tutor should have:
- Socratic Score > 0.6
- Telling Rate < 0.2

Usage:
    python -m evaluation.benchmarks.socratic_score \
        --dialogs data/training/synthetic_dialogs.jsonl \
        --output evaluation/reports/socratic_score.json
"""

import json
import re
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# Indicators of Socratic questioning (Russian)
QUESTION_PATTERNS = [
    r"\?",
    r"как ты думаешь",
    r"что ты.*думаешь",
    r"попробуй",
    r"подумай",
    r"вспомни",
    r"какой",
    r"какая",
    r"почему",
    r"зачем",
    r"что будет если",
    r"а если",
    r"как можно",
    r"что ты знаешь",
    r"давай разберём",
    r"давай подумаем",
]

# Indicators of direct telling
TELLING_PATTERNS = [
    r"ответ[:\s]",
    r"правильный ответ",
    r"решение[:\s]",
    r"результат[:\s]",
    r"равно\s+\d",
    r"получается\s+\d",
    r"формула[:\s]",
    r"запомни[:\s]",
]


@dataclass
class SocraticResult:
    """Result of Socratic Score analysis."""
    total_tutor_turns: int = 0
    guiding_turns: int = 0
    telling_turns: int = 0
    neutral_turns: int = 0
    socratic_score: float = 0.0
    telling_rate: float = 0.0
    per_dialog: List[Dict[str, Any]] = field(default_factory=list)


def analyze_turn(text: str) -> Dict[str, Any]:
    """Analyze a single tutor turn for Socratic indicators."""
    text_lower = text.lower()

    question_count = sum(1 for p in QUESTION_PATTERNS if re.search(p, text_lower))
    telling_count = sum(1 for p in TELLING_PATTERNS if re.search(p, text_lower))

    is_guiding = question_count >= 1 and telling_count == 0
    is_telling = telling_count >= 1 and question_count == 0

    return {
        "question_count": question_count,
        "telling_count": telling_count,
        "is_guiding": is_guiding,
        "is_telling": is_telling,
    }


def evaluate_dialogs(dialogs_path: Path) -> SocraticResult:
    """Run Socratic Score benchmark on dialog dataset."""
    result = SocraticResult()

    with open(dialogs_path, "r", encoding="utf-8") as f:
        for line in f:
            dialog = json.loads(line)
            turns = dialog.get("turns", [])

            dialog_guiding = 0
            dialog_telling = 0
            dialog_total = 0

            for turn in turns:
                if turn.get("role") not in ("tutor", "assistant"):
                    continue

                content = turn.get("content", "")
                analysis = analyze_turn(content)

                dialog_total += 1

                if analysis["is_guiding"]:
                    dialog_guiding += 1
                elif analysis["is_telling"]:
                    dialog_telling += 1

            if dialog_total > 0:
                result.per_dialog.append({
                    "dialog_id": dialog.get("id", ""),
                    "total_turns": dialog_total,
                    "guiding": dialog_guiding,
                    "telling": dialog_telling,
                    "socratic_score": dialog_guiding / dialog_total,
                    "telling_rate": dialog_telling / dialog_total,
                })

            result.total_tutor_turns += dialog_total
            result.guiding_turns += dialog_guiding
            result.telling_turns += dialog_telling

    result.neutral_turns = result.total_tutor_turns - result.guiding_turns - result.telling_turns

    if result.total_tutor_turns > 0:
        result.socratic_score = result.guiding_turns / result.total_tutor_turns
        result.telling_rate = result.telling_turns / result.total_tutor_turns

    return result


def main():
    parser = argparse.ArgumentParser(description="Socratic Score benchmark")
    parser.add_argument("--dialogs", type=str, required=True)
    parser.add_argument("--output", type=str,
                        default="evaluation/reports/socratic_score.json")
    args = parser.parse_args()

    result = evaluate_dialogs(Path(args.dialogs))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(result), f, indent=2, ensure_ascii=False)

    print(f"Socratic Score: {result.socratic_score:.3f}")
    print(f"Telling Rate: {result.telling_rate:.3f}")
    print(f"Total tutor turns: {result.total_tutor_turns}")
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
