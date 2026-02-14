"""
Error Recovery Benchmark

Measures the percentage of student errors that are successfully corrected
within N turns of tutor interaction.

Metrics:
- Recovery Rate: % of errors followed by correct answer within 3 turns
- Avg Turns to Recovery: average number of turns to correct an error
- Persistent Error Rate: % of errors never corrected in the session

Usage:
    python -m evaluation.benchmarks.error_recovery \
        --dialogs data/training/synthetic_dialogs.jsonl \
        --output evaluation/reports/error_recovery.json
"""

import json
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

RECOVERY_WINDOW = 3


@dataclass
class ErrorRecoveryResult:
    """Result of error recovery analysis."""
    total_errors: int = 0
    recovered_errors: int = 0
    persistent_errors: int = 0
    recovery_rate: float = 0.0
    avg_turns_to_recovery: float = 0.0
    persistent_error_rate: float = 0.0
    per_dialog: List[Dict[str, Any]] = field(default_factory=list)


def evaluate_dialogs(dialogs_path: Path, window: int = RECOVERY_WINDOW) -> ErrorRecoveryResult:
    """Run error recovery benchmark on dialog dataset."""
    result = ErrorRecoveryResult()
    recovery_turns_list = []

    with open(dialogs_path, "r", encoding="utf-8") as f:
        for line in f:
            dialog = json.loads(line)
            turns = dialog.get("turns", [])

            dialog_errors = 0
            dialog_recovered = 0

            for i, turn in enumerate(turns):
                if turn.get("role") not in ("student", "user"):
                    continue

                is_correct = turn.get("is_correct")
                if is_correct is not None and not is_correct:
                    dialog_errors += 1

                    recovered = False
                    for j in range(i + 1, min(i + 1 + window * 2, len(turns))):
                        future = turns[j]
                        if future.get("role") in ("student", "user"):
                            if future.get("is_correct"):
                                recovered = True
                                turns_needed = (j - i + 1) // 2
                                recovery_turns_list.append(turns_needed)
                                break

                    if recovered:
                        dialog_recovered += 1

            result.total_errors += dialog_errors
            result.recovered_errors += dialog_recovered

            if dialog_errors > 0:
                result.per_dialog.append({
                    "dialog_id": dialog.get("id", ""),
                    "errors": dialog_errors,
                    "recovered": dialog_recovered,
                    "recovery_rate": dialog_recovered / dialog_errors,
                })

    result.persistent_errors = result.total_errors - result.recovered_errors

    if result.total_errors > 0:
        result.recovery_rate = result.recovered_errors / result.total_errors
        result.persistent_error_rate = result.persistent_errors / result.total_errors

    if recovery_turns_list:
        result.avg_turns_to_recovery = sum(recovery_turns_list) / len(recovery_turns_list)

    return result


def main():
    parser = argparse.ArgumentParser(description="Error Recovery benchmark")
    parser.add_argument("--dialogs", type=str, required=True)
    parser.add_argument("--output", type=str,
                        default="evaluation/reports/error_recovery.json")
    parser.add_argument("--window", type=int, default=RECOVERY_WINDOW)
    args = parser.parse_args()

    result = evaluate_dialogs(Path(args.dialogs), args.window)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(result), f, indent=2, ensure_ascii=False)

    print(f"Error Recovery Rate: {result.recovery_rate:.3f}")
    print(f"Avg Turns to Recovery: {result.avg_turns_to_recovery:.1f}")
    print(f"Persistent Error Rate: {result.persistent_error_rate:.3f}")
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
