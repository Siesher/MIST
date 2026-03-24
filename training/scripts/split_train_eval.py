"""Split eval_benchmark.jsonl into clean train/eval sets for Socratic data generation.

Ensures:
  - paired_problems_150.jsonl stays entirely in eval (sacred test set)
  - Stratified split by domain + difficulty
  - No overlap between train and eval

Usage:
    python training/scripts/split_train_eval.py \
        --benchmark training/data/eval_benchmark.jsonl \
        --paired evaluation/paired_problems_150.jsonl \
        --train-output training/data/socratic_source.jsonl \
        --eval-output training/data/eval_clean.jsonl \
        --train-size 2500
"""

import argparse
import json
import logging
import random
import sys
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def normalize_prompt(text: str) -> str:
    """Normalize prompt for dedup matching."""
    return " ".join(text.split()).strip().lower()


def main() -> None:
    parser = argparse.ArgumentParser(description="Split benchmark into train/eval")
    parser.add_argument("--benchmark", default="training/data/eval_benchmark.jsonl")
    parser.add_argument("--paired", default="evaluation/paired_problems_150.jsonl")
    parser.add_argument("--train-output", default="training/data/socratic_source.jsonl")
    parser.add_argument("--eval-output", default="training/data/eval_clean.jsonl")
    parser.add_argument("--train-size", type=int, default=2500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    sys.stdout.reconfigure(encoding="utf-8")

    # Load paired problems (sacred eval set)
    paired_prompts: set[str] = set()
    paired_path = Path(args.paired)
    if paired_path.exists():
        with open(paired_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                paired_prompts.add(normalize_prompt(rec["prompt"]))
        logger.info(f"Loaded {len(paired_prompts)} sacred eval prompts from {args.paired}")
    else:
        logger.warning(f"Paired file not found: {args.paired}, proceeding without it")

    # Load full benchmark
    all_problems: list[dict] = []
    with open(args.benchmark, "r", encoding="utf-8") as f:
        for line in f:
            all_problems.append(json.loads(line))
    logger.info(f"Loaded {len(all_problems)} problems from {args.benchmark}")

    # Separate sacred eval problems
    sacred_eval: list[dict] = []
    available: list[dict] = []
    for p in all_problems:
        if normalize_prompt(p["prompt"]) in paired_prompts:
            sacred_eval.append(p)
        else:
            available.append(p)

    logger.info(f"Sacred eval (paired): {len(sacred_eval)}")
    logger.info(f"Available for split: {len(available)}")

    # Stratified split by domain + difficulty
    strata: dict[str, list[dict]] = defaultdict(list)
    for p in available:
        key = f"{p.get('domain', 'unknown')}_{p.get('difficulty', 'unknown')}"
        strata[key].append(p)

    train_problems: list[dict] = []
    eval_problems: list[dict] = list(sacred_eval)  # start with sacred

    train_target = min(args.train_size, len(available))
    train_ratio = train_target / len(available)

    for key, problems in strata.items():
        random.shuffle(problems)
        n_train = round(len(problems) * train_ratio)
        train_problems.extend(problems[:n_train])
        eval_problems.extend(problems[n_train:])

    random.shuffle(train_problems)
    random.shuffle(eval_problems)

    # Stats
    train_domains: dict[str, int] = defaultdict(int)
    eval_domains: dict[str, int] = defaultdict(int)
    for p in train_problems:
        train_domains[p.get("domain", "unknown")] += 1
    for p in eval_problems:
        eval_domains[p.get("domain", "unknown")] += 1

    # Save
    train_path = Path(args.train_output)
    train_path.parent.mkdir(parents=True, exist_ok=True)
    with open(train_path, "w", encoding="utf-8") as f:
        for p in train_problems:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    eval_path = Path(args.eval_output)
    eval_path.parent.mkdir(parents=True, exist_ok=True)
    with open(eval_path, "w", encoding="utf-8") as f:
        for p in eval_problems:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    logger.info(f"\n{'=' * 50}")
    logger.info(f"TRAIN: {len(train_problems)} problems -> {train_path}")
    logger.info(f"  Domains: {dict(train_domains)}")
    logger.info(f"EVAL:  {len(eval_problems)} problems -> {eval_path}")
    logger.info(f"  Domains: {dict(eval_domains)}")
    logger.info(f"  (includes {len(sacred_eval)} sacred paired problems)")
    logger.info(f"{'=' * 50}")


if __name__ == "__main__":
    main()
