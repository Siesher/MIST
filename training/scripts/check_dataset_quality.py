#!/usr/bin/env python3
"""Check quality of generated STEM dataset."""

import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path


def check_quality(path: str):
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                examples.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue

    total = len(examples)
    print(f"Total examples: {total}")
    print("=" * 70)

    # ═══════════════════════════════════════════════════════════
    # 1. Structural checks
    # ═══════════════════════════════════════════════════════════
    print("\n1. STRUCTURAL CHECKS")
    print("-" * 40)

    missing_fields = Counter()
    for ex in examples:
        for field in ["instruction", "output", "domain", "type", "difficulty", "teacher_model"]:
            if field not in ex or not ex[field]:
                missing_fields[field] += 1

    if missing_fields:
        for field, count in missing_fields.most_common():
            print(f"  Missing {field}: {count}")
    else:
        print("  All required fields present: OK")

    # ═══════════════════════════════════════════════════════════
    # 2. Think tag analysis
    # ═══════════════════════════════════════════════════════════
    print("\n2. THINK TAG ANALYSIS")
    print("-" * 40)

    has_think_open = sum(1 for ex in examples if "<think>" in ex.get("output", ""))
    has_think_close = sum(1 for ex in examples if "</think>" in ex.get("output", ""))
    has_both = sum(
        1 for ex in examples
        if "<think>" in ex.get("output", "") and "</think>" in ex.get("output", "")
    )
    has_open_no_close = has_think_open - has_both
    no_think = total - has_think_open

    print(f"  With <think>...</think>: {has_both} ({100*has_both/total:.1f}%)")
    print(f"  Open without close:     {has_open_no_close} ({100*has_open_no_close/total:.1f}%)")
    print(f"  No think tags at all:   {no_think} ({100*no_think/total:.1f}%)")

    think_at_start = sum(
        1 for ex in examples if ex.get("output", "").strip().startswith("<think>")
    )
    print(f"  Think at start:         {think_at_start} ({100*think_at_start/total:.1f}%)")

    # ═══════════════════════════════════════════════════════════
    # 3. Output length distribution
    # ═══════════════════════════════════════════════════════════
    print("\n3. OUTPUT LENGTH DISTRIBUTION")
    print("-" * 40)

    lengths = [len(ex.get("output", "")) for ex in examples]
    sorted_lengths = sorted(lengths)
    print(f"  Min:    {min(lengths)} chars")
    print(f"  P10:    {sorted_lengths[int(0.1*len(lengths))]} chars")
    print(f"  P25:    {sorted_lengths[int(0.25*len(lengths))]} chars")
    print(f"  Median: {statistics.median(lengths):.0f} chars")
    print(f"  P75:    {sorted_lengths[int(0.75*len(lengths))]} chars")
    print(f"  P90:    {sorted_lengths[int(0.9*len(lengths))]} chars")
    print(f"  Max:    {max(lengths)} chars")

    short = sum(1 for l in lengths if l < 100)
    very_short = sum(1 for l in lengths if l < 200)
    print(f"  < 100 chars:  {short} ({100*short/total:.2f}%)")
    print(f"  < 200 chars:  {very_short} ({100*very_short/total:.2f}%)")

    # ═══════════════════════════════════════════════════════════
    # 4. Language check (Russian content)
    # ═══════════════════════════════════════════════════════════
    print("\n4. LANGUAGE CHECK")
    print("-" * 40)

    cyrillic_re = re.compile(r"[а-яА-ЯёЁ]")
    non_russian = []
    for i, ex in enumerate(examples):
        output = ex.get("output", "")
        cyrillic_chars = len(cyrillic_re.findall(output))
        total_alpha = sum(1 for c in output if c.isalpha())
        if total_alpha > 0:
            ratio = cyrillic_chars / total_alpha
            if ratio < 0.3:
                non_russian.append((i, ratio, ex.get("domain"), ex.get("output", "")[:80]))

    print(f"  Non-Russian outputs (<30% Cyrillic): {len(non_russian)}")
    for idx, ratio, domain, snippet in non_russian[:5]:
        print(f"    [{idx}] domain={domain} cyr={ratio:.1%}: {snippet}...")

    # ═══════════════════════════════════════════════════════════
    # 5. Refusal / non-answer detection
    # ═══════════════════════════════════════════════════════════
    print("\n5. REFUSAL / NON-ANSWER DETECTION")
    print("-" * 40)

    refusal_markers = [
        "я не могу", "не в состоянии", "sorry", "i cannot", "i can't",
        "as an ai", "как искусственный интеллект", "к сожалению, я не",
        "i'm not able", "не могу выполнить", "i apologize",
    ]
    refusals = []
    for i, ex in enumerate(examples):
        output_lower = ex.get("output", "").lower()
        for marker in refusal_markers:
            if marker in output_lower:
                refusals.append((i, marker, ex.get("output", "")[:120]))
                break

    print(f"  Refusals detected: {len(refusals)}")
    for idx, marker, snippet in refusals[:5]:
        print(f'    [{idx}] "{marker}": {snippet}...')

    # ═══════════════════════════════════════════════════════════
    # 6. Duplicate detection
    # ═══════════════════════════════════════════════════════════
    print("\n6. DUPLICATE DETECTION")
    print("-" * 40)

    instr_counter = Counter(ex.get("instruction", "") for ex in examples)
    exact_instr_dupes = sum(c - 1 for c in instr_counter.values() if c > 1)
    unique_instructions = sum(1 for c in instr_counter.values() if c == 1)
    print(f"  Unique instructions:     {unique_instructions}")
    print(f"  Duplicate instructions:  {exact_instr_dupes} (templates reused with same difficulty)")

    output_hashes = Counter(hash(ex.get("output", "")) for ex in examples)
    exact_output_dupes = sum(c - 1 for c in output_hashes.values() if c > 1)
    print(f"  Exact output duplicates: {exact_output_dupes}")

    prefix_counter = Counter(ex.get("output", "")[:200] for ex in examples)
    near_dupes = sum(c - 1 for c in prefix_counter.values() if c > 1)
    print(f"  Near-duplicate outputs (200-char prefix): {near_dupes}")

    # ═══════════════════════════════════════════════════════════
    # 7. Calc answer format (\boxed{})
    # ═══════════════════════════════════════════════════════════
    print("\n7. CALC ANSWER FORMAT (\\boxed{})")
    print("-" * 40)

    calc_examples = [ex for ex in examples if ex.get("type") == "calc"]
    has_boxed = sum(1 for ex in calc_examples if "\\boxed" in ex.get("output", ""))
    print(f"  Calc examples:    {len(calc_examples)}")
    print(f"  With \\boxed{{}}:   {has_boxed} ({100*has_boxed/max(1,len(calc_examples)):.1f}%)")

    for domain in ["math", "physics", "chemistry", "cs", "biology"]:
        domain_calc = [ex for ex in calc_examples if ex.get("domain") == domain]
        if domain_calc:
            boxed = sum(1 for ex in domain_calc if "\\boxed" in ex.get("output", ""))
            print(f"    {domain:12s}: {boxed}/{len(domain_calc)} ({100*boxed/len(domain_calc):.1f}%)")

    # ═══════════════════════════════════════════════════════════
    # 8. Quality by teacher model
    # ═══════════════════════════════════════════════════════════
    print("\n8. QUALITY BY TEACHER MODEL")
    print("-" * 40)

    by_model = defaultdict(list)
    for ex in examples:
        by_model[ex.get("teacher_model", "?")].append(ex)

    print(f"  {'Model':20s}  {'Count':>6s}  {'AvgLen':>6s}  {'Think%':>6s}  {'Boxed%':>6s}")
    for model in sorted(by_model.keys()):
        exs = by_model[model]
        avg_len = sum(len(ex.get("output", "")) for ex in exs) / len(exs)
        think_pct = 100 * sum(
            1 for ex in exs
            if "<think>" in ex.get("output", "") and "</think>" in ex.get("output", "")
        ) / len(exs)
        boxed_calc = [ex for ex in exs if ex.get("type") == "calc"]
        boxed_pct = (
            100 * sum(1 for ex in boxed_calc if "\\boxed" in ex.get("output", ""))
            / max(1, len(boxed_calc))
        )
        print(f"  {model:20s}  {len(exs):6d}  {avg_len:6.0f}  {think_pct:5.1f}%  {boxed_pct:5.1f}%")

    # ═══════════════════════════════════════════════════════════
    # 9. Sample outputs (random 3)
    # ═══════════════════════════════════════════════════════════
    print("\n9. RANDOM SAMPLES (first 300 chars of output)")
    print("-" * 40)

    import random
    random.seed(42)
    samples = random.sample(examples, min(3, total))
    for i, ex in enumerate(samples):
        print(f"\n  Sample {i+1}: [{ex.get('domain')}] [{ex.get('type')}] [{ex.get('difficulty')}]")
        print(f"  Model: {ex.get('teacher_model')}")
        print(f"  Instruction: {ex.get('instruction', '')[:100]}...")
        output = ex.get("output", "")[:300]
        print(f"  Output: {output}...")

    # ═══════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("QUALITY SUMMARY")
    print("=" * 70)

    checks = []
    issues = 0

    # Think tags
    pct = 100 * has_both / total
    passed = pct > 95
    checks.append(("Think tags > 95%", f"{pct:.1f}%", "PASS" if passed else "FAIL"))
    if not passed:
        issues += 1

    # Short outputs
    pct = 100 * very_short / total
    passed = pct < 1
    checks.append(("Short outputs < 1%", f"{pct:.2f}%", "PASS" if passed else "FAIL"))
    if not passed:
        issues += 1

    # Refusals
    pct = 100 * len(refusals) / total
    passed = pct < 0.5
    checks.append(("Refusals < 0.5%", f"{len(refusals)} ({pct:.2f}%)", "PASS" if passed else "FAIL"))
    if not passed:
        issues += 1

    # Exact output dupes
    pct = 100 * exact_output_dupes / total
    passed = pct < 1
    checks.append(("Exact dupes < 1%", f"{exact_output_dupes} ({pct:.2f}%)", "PASS" if passed else "FAIL"))
    if not passed:
        issues += 1

    # Russian language
    pct_non_ru = 100 * len(non_russian) / total
    passed = pct_non_ru < 2
    checks.append(("Russian content > 98%", f"{len(non_russian)} non-RU ({pct_non_ru:.2f}%)", "PASS" if passed else "FAIL"))
    if not passed:
        issues += 1

    # Boxed answers for calc
    boxed_pct = 100 * has_boxed / max(1, len(calc_examples))
    status = "PASS" if boxed_pct > 50 else "WARN"
    checks.append(("Calc boxed > 50%", f"{boxed_pct:.1f}%", status))

    # Think at start
    start_pct = 100 * think_at_start / total
    passed = start_pct > 80
    checks.append(("Think at start > 80%", f"{start_pct:.1f}%", "PASS" if passed else "WARN"))

    for name, value, status in checks:
        print(f"  [{status}] {name:25s} = {value}")

    print(f"\nOverall: {len(checks) - issues}/{len(checks)} checks passed, {issues} issues")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "training/data/raw_stem.jsonl"
    if not Path(path).exists():
        print(f"File not found: {path}")
        sys.exit(1)
    check_quality(path)
