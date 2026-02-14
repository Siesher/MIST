#!/usr/bin/env python3
"""
MITS Dataset Generation Script

Generates synthetic tutoring dialogs using Nemotron-3-Nano-30B-A3B
as the Teacher model for distillation.

Usage:
    python training/scripts/generate_dataset.py --num-dialogs 1000
    python training/scripts/generate_dataset.py --num-dialogs 100 --topic derivatives
"""

import argparse
import json
import random
from pathlib import Path
from datetime import datetime
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from training.dataset.dialog_generator import (
    SyntheticDialogGenerator,
    StudentPersona,
    save_dialogs,
    save_training_data
)
from training.dataset.quality_filter import (
    DialogQualityFilter,
    analyze_dataset
)
from src.data.task_bank import TaskBank
from src.data.schemas import Difficulty
from src.config import settings

import structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ]
)
logger = structlog.get_logger()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate synthetic tutoring dialogs for distillation"
    )
    parser.add_argument(
        "--num-dialogs",
        type=int,
        default=100,
        help="Number of dialogs to generate (default: 100)"
    )
    parser.add_argument(
        "--dialogs-per-task",
        type=int,
        default=3,
        help="Dialogs to generate per task (default: 3)"
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Filter tasks by topic (e.g., 'derivatives')"
    )
    parser.add_argument(
        "--difficulty",
        type=str,
        choices=["easy", "medium", "hard", "olympiad"],
        default=None,
        help="Filter tasks by difficulty"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/distillation",
        help="Output directory (default: data/distillation)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"Model to use (default: {settings.MODEL_NAME})"
    )
    parser.add_argument(
        "--min-quality",
        type=float,
        default=0.6,
        help="Minimum quality score for dialogs (default: 0.6)"
    )
    parser.add_argument(
        "--test-split",
        type=float,
        default=0.1,
        help="Fraction for test set (default: 0.1)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Set seed
    random.seed(args.seed)

    logger.info(
        "starting_generation",
        num_dialogs=args.num_dialogs,
        model=args.model or settings.MODEL_NAME
    )

    # Initialize components
    generator = SyntheticDialogGenerator(model=args.model)
    task_bank = TaskBank()
    quality_filter = DialogQualityFilter(
        min_turns=4,
        max_turns=15,
        require_latex=True
    )

    # Get tasks
    difficulty = Difficulty(args.difficulty) if args.difficulty else None
    tasks = task_bank.get_tasks(
        topic=args.topic,
        difficulty=difficulty,
        limit=None  # Get all matching tasks
    )

    if not tasks:
        logger.error("no_tasks_found", topic=args.topic, difficulty=args.difficulty)
        print("\nNo tasks found! Make sure task_bank has tasks.")
        print("Available topics:", task_bank.get_topics() if hasattr(task_bank, 'get_topics') else "unknown")
        return

    logger.info("tasks_loaded", count=len(tasks))

    # Calculate how many tasks we need
    dialogs_per_task = args.dialogs_per_task
    tasks_needed = (args.num_dialogs + dialogs_per_task - 1) // dialogs_per_task

    # Sample tasks if we have more than needed
    if len(tasks) > tasks_needed:
        tasks = random.sample(tasks, tasks_needed)
    else:
        # Repeat tasks if we don't have enough
        while len(tasks) < tasks_needed:
            tasks.extend(random.sample(tasks, min(len(tasks), tasks_needed - len(tasks))))

    # Generate dialogs
    all_dialogs = []
    personas = list(StudentPersona)

    print(f"\nGenerating {args.num_dialogs} dialogs from {len(tasks)} tasks...")
    print(f"Using model: {args.model or settings.MODEL_NAME}")
    print("-" * 60)

    for i, dialog in enumerate(generator.generate_batch(
        tasks=tasks[:tasks_needed],
        dialogs_per_task=dialogs_per_task,
        personas=personas
    )):
        all_dialogs.append(dialog)

        if (i + 1) % 10 == 0:
            print(f"  Generated {i + 1} dialogs...")

        if len(all_dialogs) >= args.num_dialogs:
            break

    print(f"\nGenerated {len(all_dialogs)} raw dialogs")

    # Quality filter
    print("\nFiltering by quality...")
    passed, failed, filter_stats = quality_filter.filter_dialogs(
        all_dialogs,
        min_score=args.min_quality
    )

    print(f"  Passed: {len(passed)} ({filter_stats['pass_rate']:.1%})")
    print(f"  Failed: {len(failed)}")
    print(f"  Avg score: {filter_stats['avg_score']:.2f}")

    if not passed:
        logger.error("no_dialogs_passed_filter")
        print("\nNo dialogs passed quality filter! Try lowering --min-quality")
        return

    # Analyze dataset
    print("\nDataset statistics:")
    stats = analyze_dataset(passed)
    print(f"  Total dialogs: {stats['num_dialogs']}")
    print(f"  Total turns: {stats['total_turns']}")
    print(f"  Avg turns/dialog: {stats['avg_turns_per_dialog']}")
    print(f"  Solved rate: {stats['solved_rate']:.1%}")
    print(f"  Told answer rate: {stats['told_answer_rate']:.1%}")

    print("\n  Move distribution:")
    for move, ratio in sorted(stats['move_distribution'].items(), key=lambda x: -x[1]):
        print(f"    {move}: {ratio:.1%}")

    # Split into train/test
    random.shuffle(passed)
    split_idx = int(len(passed) * (1 - args.test_split))
    train_dialogs = passed[:split_idx]
    test_dialogs = passed[split_idx:]

    print(f"\n  Train set: {len(train_dialogs)}")
    print(f"  Test set: {len(test_dialogs)}")

    # Save outputs
    output_dir = Path(args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Raw dialogs
    raw_dir = output_dir / "raw_dialogs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    save_dialogs(all_dialogs, raw_dir / f"dialogs_{timestamp}.jsonl")
    save_dialogs(failed, raw_dir / f"failed_{timestamp}.jsonl")

    # Processed (training format)
    processed_dir = output_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    save_training_data(train_dialogs, processed_dir / "train.jsonl")
    save_training_data(test_dialogs, processed_dir / "eval.jsonl")

    # Also save as single files for easier access
    save_training_data(passed, processed_dir / f"all_{timestamp}.jsonl")

    # Save statistics
    stats_path = output_dir / f"stats_{timestamp}.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump({
            "generation_args": vars(args),
            "filter_stats": filter_stats,
            "dataset_stats": stats,
            "train_size": len(train_dialogs),
            "test_size": len(test_dialogs),
            "timestamp": timestamp
        }, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print("Generation complete!")
    print(f"  Raw dialogs: {raw_dir}/dialogs_{timestamp}.jsonl")
    print(f"  Train data: {processed_dir}/train.jsonl")
    print(f"  Eval data: {processed_dir}/eval.jsonl")
    print(f"  Statistics: {stats_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
