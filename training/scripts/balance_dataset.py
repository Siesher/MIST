#!/usr/bin/env python3
"""
Balance combined_stem.jsonl so no domain exceeds max_pct (default 25%).

Trims over-represented domains by removing random excess examples.
"""

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path


def balance(input_path, output_path, max_pct=25.0, seed=42):
    # Load
    examples = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))

    total = len(examples)
    print(f"Input: {total} examples")

    # Group by domain
    by_domain = defaultdict(list)
    for ex in examples:
        by_domain[ex.get("domain", "unknown")].append(ex)

    for d, items in sorted(by_domain.items()):
        pct = 100 * len(items) / total
        print(f"  {d}: {len(items)} ({pct:.1f}%)")

    # Iteratively trim over-represented domains
    # When trimming, recalculate total to maintain correct ratios
    rng = random.Random(seed)
    trimmed_counts = {}

    for _ in range(5):  # iterate to handle cascading ratio changes
        current_total = sum(len(v) for v in by_domain.values())
        changed = False
        for domain, items in list(by_domain.items()):
            pct = 100 * len(items) / current_total
            if pct > max_pct:
                target_count = int(current_total * max_pct / 100)
                rng.shuffle(items)
                removed = len(items) - target_count
                by_domain[domain] = items[:target_count]
                trimmed_counts[domain] = trimmed_counts.get(domain, 0) + removed
                changed = True
        if not changed:
            break

    # Combine and shuffle
    balanced = []
    for items in by_domain.values():
        balanced.extend(items)
    rng.shuffle(balanced)

    final_total = len(balanced)
    total_removed = total - final_total

    print(f"\nRemoved: {total_removed}")
    for d, c in sorted(trimmed_counts.items()):
        print(f"  {d}: -{c}")

    print(f"\nOutput: {final_total} examples")
    domain_counts = Counter(ex.get("domain", "?") for ex in balanced)
    for d in ["math", "physics", "chemistry", "cs", "biology"]:
        c = domain_counts.get(d, 0)
        pct = 100 * c / final_total
        status = "OK" if pct <= max_pct else "FAIL"
        print(f"  {d}: {c} ({pct:.1f}%) [{status}]")

    # Save
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in balanced:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"\nSaved to {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", default="training/data/combined_stem.jsonl")
    parser.add_argument("-o", "--output", default="training/data/combined_stem_balanced.jsonl")
    parser.add_argument("--max-pct", type=float, default=25.0)
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"Not found: {args.input}")
        return 1

    balance(args.input, args.output, args.max_pct)
    return 0


if __name__ == "__main__":
    sys.exit(main())
