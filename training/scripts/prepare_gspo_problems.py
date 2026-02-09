#!/usr/bin/env python3
"""
Prepare GSPO training problems from combined_stem dataset.

Extracts verifiable and conceptual problems with ground truth answers,
balanced across STEM domains, with curriculum ordering (easy → hard).

Output format:
  {"prompt": "...", "answer": "...", "domain": "...", "type": "verifiable"|"conceptual"}

Usage:
    python training/scripts/prepare_gspo_problems.py
    python training/scripts/prepare_gspo_problems.py --input training/data/combined_stem_balanced.jsonl
"""

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


# ─── Answer extraction ───

def extract_boxed(text: str) -> str:
    """Extract answer from \\boxed{...}."""
    matches = re.findall(r"\\boxed\{([^}]+)\}", text)
    return matches[-1].strip() if matches else ""


def extract_final_answer(text: str) -> str:
    """Extract final answer from output (after </think> if present)."""
    # Try boxed first
    boxed = extract_boxed(text)
    if boxed:
        return boxed

    # Look for "Ответ:" pattern
    answer_match = re.search(r"(?:Ответ|ответ|Answer|answer)\s*[:=]\s*(.+?)(?:\n|$)", text)
    if answer_match:
        return answer_match.group(1).strip()

    # Try last number
    numbers = re.findall(r"[-+]?\d*[.,]?\d+", text)
    if numbers:
        return numbers[-1].replace(",", ".")

    return ""


def classify_verifiable(example: dict) -> str:
    """Classify problem as verifiable or conceptual based on content."""
    ex_type = example.get("type", "")
    output = example.get("output", "")
    domain = example.get("domain", "")

    # Explicit calc type with boxed answer = verifiable
    if ex_type == "calc" and extract_boxed(output):
        return "verifiable"

    # CS code problems
    if domain == "cs" and ("```python" in output or "def " in output):
        return "verifiable"

    # Has boxed answer in any domain
    if extract_boxed(output):
        return "verifiable"

    return "conceptual"


# ─── Difficulty ordering ───

DIFFICULTY_ORDER = {
    "школьный": 0,
    "базовый университетский": 1,
    "продвинутый": 2,
    "олимпиадный": 3,
}


# ─── Domain targets ───

DOMAIN_TARGETS = {
    "math": 4000,
    "physics": 3500,
    "chemistry": 2500,
    "cs": 2500,
    "biology": 2500,
}

TOTAL_TARGET = sum(DOMAIN_TARGETS.values())  # 15000


def prepare_problems(input_path: str, output_path: str):
    # Load dataset
    examples = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))

    print(f"Loaded: {len(examples)} examples")

    # Group by domain
    by_domain = defaultdict(list)
    for ex in examples:
        domain = ex.get("domain", "unknown")
        if domain in DOMAIN_TARGETS:
            by_domain[domain].append(ex)

    # Process each domain
    all_problems = []
    stats = defaultdict(lambda: {"verifiable": 0, "conceptual": 0, "no_answer": 0})

    for domain, target_count in DOMAIN_TARGETS.items():
        domain_examples = by_domain.get(domain, [])
        if not domain_examples:
            print(f"  WARNING: No examples for {domain}")
            continue

        # Sort by difficulty (curriculum: easy → hard)
        domain_examples.sort(
            key=lambda x: DIFFICULTY_ORDER.get(x.get("difficulty", ""), 1)
        )

        selected = []
        for ex in domain_examples:
            if len(selected) >= target_count:
                break

            vtype = classify_verifiable(ex)
            answer = extract_final_answer(ex.get("output", ""))

            # For verifiable problems, require an answer
            if vtype == "verifiable" and not answer:
                stats[domain]["no_answer"] += 1
                continue

            problem = {
                "prompt": ex.get("instruction", ""),
                "answer": answer,
                "domain": domain,
                "type": vtype,
                "difficulty": ex.get("difficulty", ""),
            }
            selected.append(problem)
            stats[domain][vtype] += 1

        all_problems.extend(selected)

    # Print stats
    total = len(all_problems)
    print(f"\nTotal problems: {total}")
    print(f"\nPer-domain breakdown:")
    for domain in DOMAIN_TARGETS:
        s = stats[domain]
        domain_total = s["verifiable"] + s["conceptual"]
        pct = 100 * domain_total / max(1, total)
        print(f"  {domain:12s}: {domain_total:5d} ({pct:.1f}%)  "
              f"verifiable={s['verifiable']}, conceptual={s['conceptual']}, "
              f"no_answer_skipped={s['no_answer']}")

    verifiable_total = sum(s["verifiable"] for s in stats.values())
    conceptual_total = sum(s["conceptual"] for s in stats.values())
    print(f"\n  Verifiable: {verifiable_total} ({100*verifiable_total/max(1,total):.1f}%)")
    print(f"  Conceptual: {conceptual_total} ({100*conceptual_total/max(1,total):.1f}%)")

    # Save
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for p in all_problems:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"\nSaved to {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", default="training/data/combined_stem_balanced.jsonl")
    parser.add_argument("-o", "--output", default="training/data/gspo_problems.jsonl")
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"Not found: {args.input}")
        return 1

    prepare_problems(args.input, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
