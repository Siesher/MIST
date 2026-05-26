"""V-STaR training subset builder.

Constructs 1000-task stratified subset для V-STaR generation phase:
  - Source: rl_combined.jsonl (disjoint от Phase 0a eval — verified 0% overlap)
  - Skip-easy strategy (Phase 0a easy already near-ceiling)
  - Distribution-matched stratification (60% medium / 40% hard per domain, where available)
  - Equal-per-domain target 200 (chemistry capped at 162 due to source availability)

Output: training/data/vstar_subset.jsonl с metadata (source_idx для traceability).

Usage:
  uv run python scripts/vstar_build_subset.py
  uv run python scripts/vstar_build_subset.py --target-per-domain 200 --seed 42
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
RL_DATA = ROOT / "training/data/rl_combined.jsonl"
EVAL_DATA = ROOT / "training/data/eval_dataset.jsonl"
OUT_PATH = ROOT / "training/data/vstar_subset.jsonl"

DOMAINS = ["math", "physics", "chemistry", "biology", "cs"]
DIFFICULTIES = ["medium", "hard"]  # skip-easy
TARGET_PER_DOMAIN_DEFAULT = 200
DIFFICULTY_RATIO = {"medium": 0.6, "hard": 0.4}  # match Phase 0a eval distribution

# Hard-only mode (Phase 1.5 pivot — target Phase 0a regression failure mode)
DIFFICULTIES_HARD = ["hard"]
DIFFICULTY_RATIO_HARD = {"hard": 1.0}
TARGET_PER_DOMAIN_HARD = 100


def load_jsonl(path: Path) -> list[dict]:
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return items


def build_subset(
    target_per_domain: int, seed: int, hard_only: bool = False
) -> tuple[list[dict], dict]:
    """Stratified subset с per-domain caps + distribution-matched difficulty.

    Args:
        target_per_domain: Target item count per domain.
        seed: Random seed для воспроизводимости.
        hard_only: Если True, sample только hard difficulty (Phase 1.5 pivot).

    Returns (subset_items, stats_dict).
    """
    random.seed(seed)

    difficulties = DIFFICULTIES_HARD if hard_only else DIFFICULTIES
    difficulty_ratio = DIFFICULTY_RATIO_HARD if hard_only else DIFFICULTY_RATIO

    # Load source
    rl_items = load_jsonl(RL_DATA)
    print(f"[source] rl_combined.jsonl: {len(rl_items)} items")
    if hard_only:
        print("[mode] hard-only — Phase 1.5 pivot targeting Phase 0a regression failure mode")

    # Verify disjoint от eval (safety check)
    eval_prompts = {item.get("prompt", "").strip() for item in load_jsonl(EVAL_DATA)}
    rl_disjoint = [it for it in rl_items if it.get("prompt", "").strip() not in eval_prompts]
    if len(rl_disjoint) < len(rl_items):
        print(f"  ⚠️  filtered {len(rl_items) - len(rl_disjoint)} eval-overlapping items")
    else:
        print("  ✓ 0 eval overlap confirmed")

    # Pool by (domain, difficulty)
    by_cell = defaultdict(list)
    for item in rl_disjoint:
        d = item.get("domain")
        diff = item.get("difficulty")
        if d in DOMAINS and diff in difficulties:
            by_cell[(d, diff)].append(item)

    # Stratified sampling
    subset = []
    stats = defaultdict(lambda: defaultdict(int))

    for domain in DOMAINS:
        domain_available = sum(len(by_cell.get((domain, diff), [])) for diff in difficulties)
        domain_target = min(target_per_domain, domain_available)

        # Allocate per difficulty: target × ratio, capped at available
        allocations = {}
        for diff in difficulties:
            available = len(by_cell.get((domain, diff), []))
            wanted = int(round(domain_target * difficulty_ratio[diff]))
            allocations[diff] = min(wanted, available)

        # If short due to caps, rebalance to other difficulty
        actual_total = sum(allocations.values())
        deficit = domain_target - actual_total
        if deficit > 0:
            for diff in difficulties:
                available = len(by_cell.get((domain, diff), []))
                remaining = available - allocations[diff]
                if remaining > 0:
                    take = min(remaining, deficit)
                    allocations[diff] += take
                    deficit -= take
                    if deficit <= 0:
                        break

        # Sample
        for diff in difficulties:
            n = allocations[diff]
            pool = by_cell.get((domain, diff), [])
            if n == 0 or not pool:
                continue
            sampled = random.sample(pool, n)
            for item in sampled:
                # Enrich with subset metadata
                enriched = dict(item)
                enriched["vstar_source"] = "rl_combined"
                subset.append(enriched)
                stats[domain][diff] += 1

    return subset, dict(stats)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-per-domain", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--hard-only",
        action="store_true",
        help="Phase 1.5 pivot — sample только hard difficulty",
    )
    args = parser.parse_args()

    # Apply hard-only defaults if not explicitly set
    target_per_domain = args.target_per_domain
    if target_per_domain is None:
        target_per_domain = TARGET_PER_DOMAIN_HARD if args.hard_only else TARGET_PER_DOMAIN_DEFAULT
    out_path = args.out
    if out_path is None:
        out_path = ROOT / "training/data/vstar_subset_hard.jsonl" if args.hard_only else OUT_PATH

    subset, stats = build_subset(target_per_domain, args.seed, hard_only=args.hard_only)

    # Save
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for item in subset:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    # Report
    print(f"\n[saved] {out_path} — {len(subset)} items")
    print("\n=== STRATIFICATION REPORT ===")
    if args.hard_only:
        print(f"{'Domain':<12} {'hard':<10} {'total':<8} {'target':<8}")
        print("-" * 45)
        grand_total = 0
        for d in DOMAINS:
            h = stats.get(d, {}).get("hard", 0)
            grand_total += h
            print(f"{d:<12} {h:<10} {h:<8} {target_per_domain:<8}")
        print(f"{'TOTAL':<12} {'':<10} {grand_total:<8}")
    else:
        print(f"{'Domain':<12} {'medium':<10} {'hard':<10} {'total':<8} {'target':<8}")
        print("-" * 55)
        grand_total = 0
        for d in DOMAINS:
            m = stats.get(d, {}).get("medium", 0)
            h = stats.get(d, {}).get("hard", 0)
            t = m + h
            grand_total += t
            print(f"{d:<12} {m:<10} {h:<10} {t:<8} {target_per_domain:<8}")
        print(f"{'TOTAL':<12} {'':<10} {'':<10} {grand_total:<8}")

    # Source breakdown
    src_counter = Counter(item.get("source", "?") for item in subset)
    print(f"\nSource composition: {dict(src_counter.most_common(10))}")

    print("\n[next] V-STaR generation: uv run python scripts/vstar_generate.py")


if __name__ == "__main__":
    main()
