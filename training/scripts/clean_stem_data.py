#!/usr/bin/env python3
"""
Clean and fix STEM dataset quality issues.

Steps:
  1. Remove low-quality teacher models (zai-glm-4.7)
  2. Fix unclosed <think> tags
  3. Remove non-Russian outputs (<30% Cyrillic)
  4. Remove refusals
  5. Deduplicate by 200-char output prefix
  6. Remove very short outputs (<200 chars)
  7. Save cleaned dataset + report

Usage:
    python training/scripts/clean_stem_data.py
    python training/scripts/clean_stem_data.py --input training/data/raw_stem.jsonl --output training/data/raw_stem_clean.jsonl
    python training/scripts/clean_stem_data.py --dry-run
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


# ═══════════════════════════════════════════════════════════
#  Filters
# ═══════════════════════════════════════════════════════════

BLOCKED_MODELS = {"zai-glm-4.7"}

REFUSAL_MARKERS = [
    "я не могу", "не в состоянии", "sorry", "i cannot", "i can't",
    "as an ai", "как искусственный интеллект", "к сожалению, я не",
    "i'm not able", "не могу выполнить", "i apologize",
]

CYRILLIC_RE = re.compile(r"[а-яА-ЯёЁ]")

MIN_OUTPUT_LENGTH = 200


def is_non_russian(output: str) -> bool:
    """Check if output has <30% Cyrillic among alphabetic chars."""
    total_alpha = sum(1 for c in output if c.isalpha())
    if total_alpha == 0:
        return False
    cyrillic_chars = len(CYRILLIC_RE.findall(output))
    return (cyrillic_chars / total_alpha) < 0.3


def is_refusal(output: str) -> bool:
    """Check if output contains refusal markers."""
    output_lower = output.lower()
    return any(marker in output_lower for marker in REFUSAL_MARKERS)


# ═══════════════════════════════════════════════════════════
#  Think tag fixer
# ═══════════════════════════════════════════════════════════

def fix_think_tags(output: str) -> str:
    """Fix unclosed <think> tags by inserting </think> before the visible answer."""
    has_open = "<think>" in output
    has_close = "</think>" in output

    if not has_open:
        return output
    if has_open and has_close:
        return output

    # Has <think> but no </think> — find where reasoning ends and answer begins.
    # Strategy: look for double newline after reasoning, or common answer markers.
    think_start = output.index("<think>")
    after_think = output[think_start + len("<think>"):]

    # Patterns that signal the start of the visible answer
    answer_markers = [
        "\n\n**",           # bold heading after reasoning
        "\n\n#",            # markdown heading
        "\n\n---",          # horizontal rule
        "\n\nИтак,",
        "\n\nОтвет",
        "\n\nРешение",
        "\n\nДано",
        "\n\nЗадача",
        "\n\nРассмотрим",
        "\n\nДавай",
        "\n\n\\boxed",
        "\n\n$$",
    ]

    best_pos = -1
    for marker in answer_markers:
        pos = after_think.find(marker)
        if pos != -1:
            if best_pos == -1 or pos < best_pos:
                best_pos = pos

    if best_pos != -1:
        # Insert </think> right before the answer marker
        insert_at = think_start + len("<think>") + best_pos
        return output[:insert_at] + "\n</think>\n" + output[insert_at:]

    # Fallback: look for the last \n\n that has substantial text after it (>100 chars)
    parts = after_think.split("\n\n")
    if len(parts) >= 2:
        # Accumulate from the end — find where "answer" part begins
        cumulative = 0
        split_idx = len(parts)
        for i in range(len(parts) - 1, 0, -1):
            cumulative += len(parts[i])
            if cumulative > 100:
                split_idx = i
                break

        if split_idx < len(parts):
            thinking = "\n\n".join(parts[:split_idx])
            answer = "\n\n".join(parts[split_idx:])
            return (
                output[:think_start]
                + "<think>"
                + thinking
                + "\n</think>\n\n"
                + answer
            )

    # Last resort: append </think> at the very end
    return output + "\n</think>"


# ═══════════════════════════════════════════════════════════
#  Main cleaning pipeline
# ═══════════════════════════════════════════════════════════

def clean_dataset(input_path: str, output_path: str, dry_run: bool = False):
    # Load
    examples = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    examples.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    total = len(examples)
    print(f"Loaded: {total} examples")
    print("=" * 60)

    # Track removal reasons
    removed = defaultdict(list)
    cleaned = []

    # ─── Step 1: Remove blocked models ───
    for ex in examples:
        model = ex.get("teacher_model", "")
        if model in BLOCKED_MODELS:
            removed["blocked_model"].append(
                f"[{model}] {ex.get('instruction', '')[:60]}"
            )
        else:
            cleaned.append(ex)

    step1_count = total - len(cleaned)
    print(f"Step 1 — Blocked models:  -{step1_count} (remaining: {len(cleaned)})")

    # ─── Step 2: Fix think tags ───
    think_fixed = 0
    for ex in cleaned:
        output = ex.get("output", "")
        has_open = "<think>" in output
        has_close = "</think>" in output
        if has_open and not has_close:
            ex["output"] = fix_think_tags(output)
            think_fixed += 1

    print(f"Step 2 — Think tags fixed: {think_fixed}")

    # ─── Step 3: Remove non-Russian ───
    before = len(cleaned)
    filtered = []
    for ex in cleaned:
        if is_non_russian(ex.get("output", "")):
            removed["non_russian"].append(
                f"[{ex.get('domain')}] {ex.get('output', '')[:60]}"
            )
        else:
            filtered.append(ex)
    cleaned = filtered
    print(f"Step 3 — Non-Russian:     -{before - len(cleaned)} (remaining: {len(cleaned)})")

    # ─── Step 4: Remove refusals ───
    before = len(cleaned)
    filtered = []
    for ex in cleaned:
        if is_refusal(ex.get("output", "")):
            removed["refusal"].append(
                f"[{ex.get('domain')}] {ex.get('output', '')[:60]}"
            )
        else:
            filtered.append(ex)
    cleaned = filtered
    print(f"Step 4 — Refusals:        -{before - len(cleaned)} (remaining: {len(cleaned)})")

    # ─── Step 5: Remove very short outputs ───
    before = len(cleaned)
    filtered = []
    for ex in cleaned:
        if len(ex.get("output", "")) < MIN_OUTPUT_LENGTH:
            removed["too_short"].append(
                f"[{ex.get('domain')}] len={len(ex.get('output', ''))} {ex.get('output', '')[:60]}"
            )
        else:
            filtered.append(ex)
    cleaned = filtered
    print(f"Step 5 — Too short (<{MIN_OUTPUT_LENGTH}): -{before - len(cleaned)} (remaining: {len(cleaned)})")

    # ─── Step 6: Deduplicate by 200-char output prefix ───
    before = len(cleaned)
    seen_prefixes = {}
    filtered = []
    for ex in cleaned:
        prefix = ex.get("output", "")[:200]
        if prefix in seen_prefixes:
            removed["near_dupe"].append(
                f"[{ex.get('domain')}] dup of idx {seen_prefixes[prefix]}"
            )
        else:
            seen_prefixes[prefix] = len(filtered)
            filtered.append(ex)
    cleaned = filtered
    print(f"Step 6 — Near-duplicates: -{before - len(cleaned)} (remaining: {len(cleaned)})")

    # ═══════════════════════════════════════════════════════
    #  Summary
    # ═══════════════════════════════════════════════════════
    final = len(cleaned)
    total_removed = total - final

    print("\n" + "=" * 60)
    print("CLEANING SUMMARY")
    print("=" * 60)
    print(f"  Input:          {total}")
    print(f"  Removed:        {total_removed} ({100*total_removed/total:.1f}%)")
    for reason in ["blocked_model", "non_russian", "refusal", "too_short", "near_dupe"]:
        count = len(removed[reason])
        if count:
            print(f"    {reason:18s}: {count}")
    print(f"  Think tags fixed: {think_fixed}")
    print(f"  Output:         {final}")

    # Post-clean quality check
    print("\n" + "-" * 60)
    print("POST-CLEAN QUALITY")
    print("-" * 60)

    has_both = sum(
        1 for ex in cleaned
        if "<think>" in ex.get("output", "") and "</think>" in ex.get("output", "")
    )
    think_pct = 100 * has_both / max(1, final)

    domain_counts = Counter(ex.get("domain", "?") for ex in cleaned)
    model_counts = Counter(ex.get("teacher_model", "?") for ex in cleaned)

    print(f"  Think tags:  {has_both}/{final} ({think_pct:.1f}%)")
    print(f"\n  Domain distribution:")
    for d in ["math", "physics", "chemistry", "cs", "biology"]:
        c = domain_counts.get(d, 0)
        pct = 100 * c / max(1, final)
        print(f"    {d:12s}: {c:6d} ({pct:.1f}%)")

    print(f"\n  Model distribution:")
    for model, count in model_counts.most_common():
        print(f"    {model:20s}: {count:6d} ({100*count/final:.1f}%)")

    # Save
    if not dry_run:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for ex in cleaned:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print(f"\nSaved to: {output_path}")
    else:
        print(f"\n[DRY RUN] Would save to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Clean STEM dataset")
    parser.add_argument(
        "-i", "--input",
        default="training/data/raw_stem.jsonl",
        help="Input JSONL file",
    )
    parser.add_argument(
        "-o", "--output",
        default="training/data/raw_stem_clean.jsonl",
        help="Output JSONL file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print stats without saving",
    )
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"File not found: {args.input}")
        return 1

    clean_dataset(args.input, args.output, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
