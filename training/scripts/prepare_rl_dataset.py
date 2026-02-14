"""
Hybrid RL Dataset Preparation for GSPO Training

Downloads, normalizes, and balances STEM problems from multiple sources
into a unified JSONL format optimized for RL training with verifiable rewards.

Sources:
- GSM8K (openai/gsm8k) — grade school math, ~7,400 problems
- MATH (hendrycks/competition_math) — competition math, ~5,000 sampled
- OlympiadBench physics (Hothan/OlympiadBench) — olympiad physics, ~236
- ruMMLU STEM (NLPCoreTeam/mmlu_ru) — Russian STEM MC, ~1,500
- Current filtered (Siesher/mits-stem-training-data) — existing verifiable, ~800

Unified schema:
    {
        "prompt": "Solve: ...",
        "answer": "42",
        "domain": "math",
        "difficulty": "medium",
        "source": "gsm8k",
        "answer_type": "numeric"  # numeric | latex_boxed | mc_letter | numeric_with_unit
    }

Usage:
    python -m training.scripts.prepare_rl_dataset --output training/data/rl_combined.jsonl
    python -m training.scripts.prepare_rl_dataset --stats-only
"""

import json
import re
import random
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ruMMLU STEM subject -> domain mapping
# ---------------------------------------------------------------------------

RUMMLU_STEM_SUBJECTS = {
    # math
    "abstract_algebra": "math",
    "college_mathematics": "math",
    "elementary_mathematics": "math",
    "high_school_mathematics": "math",
    "high_school_statistics": "math",
    # physics
    "astronomy": "physics",
    "college_physics": "physics",
    "conceptual_physics": "physics",
    "high_school_physics": "physics",
    # chemistry
    "college_chemistry": "chemistry",
    "high_school_chemistry": "chemistry",
    # biology
    "anatomy": "biology",
    "college_biology": "biology",
    "high_school_biology": "biology",
    # cs
    "college_computer_science": "cs",
    "computer_security": "cs",
    "high_school_computer_science": "cs",
    "machine_learning": "cs",
}

# ruMMLU subject -> difficulty mapping
RUMMLU_DIFFICULTY = {
    "elementary_mathematics": "easy",
    "conceptual_physics": "easy",
    "high_school_mathematics": "medium",
    "high_school_statistics": "medium",
    "high_school_physics": "medium",
    "high_school_chemistry": "medium",
    "high_school_biology": "medium",
    "high_school_computer_science": "medium",
    "abstract_algebra": "hard",
    "college_mathematics": "hard",
    "college_physics": "hard",
    "college_chemistry": "hard",
    "college_biology": "hard",
    "college_computer_science": "hard",
    "computer_security": "hard",
    "machine_learning": "hard",
    "anatomy": "medium",
    "astronomy": "medium",
}

# MC choice letters
MC_LETTERS = ["A", "B", "C", "D"]


# ---------------------------------------------------------------------------
# GSM8K answer extraction
# ---------------------------------------------------------------------------

def extract_gsm8k_answer(solution: str) -> Optional[str]:
    """Extract numeric answer after #### from GSM8K solution text.

    GSM8K format: "... #### 42" or "... ####42"
    Returns the answer string or None if not found.
    """
    match = re.search(r'####\s*(.+?)$', solution.strip(), re.MULTILINE)
    if match:
        answer = match.group(1).strip()
        # Clean: remove commas from numbers like "1,234"
        answer = answer.replace(",", "")
        return answer
    return None


def classify_gsm8k_difficulty(solution: str) -> str:
    """Classify GSM8K problem difficulty by solution step count.

    Counts reasoning steps (lines with calculations or key operations).
    1-3 steps -> easy, 4-6 steps -> medium, 7+ steps -> hard
    """
    lines = [l.strip() for l in solution.strip().split("\n") if l.strip()]
    # Filter to lines that contain actual reasoning (have numbers or operations)
    step_lines = [
        l for l in lines
        if re.search(r'[\d+\-*/=]', l) and not l.startswith("####")
    ]
    step_count = len(step_lines)

    if step_count <= 3:
        return "easy"
    elif step_count <= 6:
        return "medium"
    return "hard"


# ---------------------------------------------------------------------------
# MATH (Hendrycks) answer extraction
# ---------------------------------------------------------------------------

def extract_math_boxed_answer(solution: str) -> Optional[str]:
    """Extract answer from \\boxed{...} in MATH dataset solutions.

    Handles nested braces like \\boxed{\\frac{1}{2}}.
    """
    # Find last \boxed{...} with nested brace support
    idx = solution.rfind("\\boxed{")
    if idx == -1:
        return None

    start = idx + len("\\boxed{")
    depth = 1
    pos = start
    while pos < len(solution) and depth > 0:
        if solution[pos] == "{":
            depth += 1
        elif solution[pos] == "}":
            depth -= 1
        pos += 1

    if depth == 0:
        return solution[start:pos - 1].strip()
    return None


def map_math_difficulty(level: str) -> str:
    """Map MATH dataset Level 1-5 to easy/medium/hard."""
    level_str = str(level).strip()
    # Extract number from "Level 1", "Level 2", etc.
    match = re.search(r'(\d)', level_str)
    if match:
        num = int(match.group(1))
        if num <= 2:
            return "easy"
        elif num <= 3:
            return "medium"
        return "hard"
    return "medium"


# ---------------------------------------------------------------------------
# Source loaders
# ---------------------------------------------------------------------------

def load_gsm8k() -> List[Dict[str, Any]]:
    """Load and normalize GSM8K dataset."""
    from datasets import load_dataset

    logger.info("Loading GSM8K from openai/gsm8k...")
    ds = load_dataset("openai/gsm8k", "main", split="train")

    problems = []
    skipped = 0
    for row in ds:
        question = row["question"].strip()
        solution = row["answer"]
        answer = extract_gsm8k_answer(solution)

        if not answer:
            skipped += 1
            continue

        problems.append({
            "prompt": question,
            "answer": answer,
            "domain": "math",
            "difficulty": classify_gsm8k_difficulty(solution),
            "source": "gsm8k",
            "answer_type": "numeric",
        })

    logger.info(f"GSM8K: {len(problems)} loaded, {skipped} skipped (no #### answer)")
    return problems


def load_math_hendrycks(max_samples: int = 5000) -> List[Dict[str, Any]]:
    """Load and normalize MATH (Hendrycks) competition math dataset.

    Samples up to max_samples to balance with GSM8K.
    """
    from datasets import load_dataset

    # Fallback chain: original is gated, try accessible mirrors
    MATH_DATASET_IDS = [
        "hendrycks/competition_math",
        "lighteval/MATH",
        "DigitalLearningGmbH/MATH-lighteval",
    ]
    ds = None
    for ds_id in MATH_DATASET_IDS:
        try:
            logger.info(f"Loading MATH from {ds_id}...")
            ds = load_dataset(ds_id, split="train")
            logger.info(f"Successfully loaded from {ds_id}")
            break
        except Exception as e:
            logger.warning(f"Failed to load {ds_id}: {e}")
            continue

    if ds is None:
        logger.error("All MATH dataset sources failed. Returning empty list.")
        return []

    all_problems = []
    skipped = 0
    for row in ds:
        problem_text = row["problem"].strip()
        solution = row["solution"]
        level = row.get("level", "Level 3")

        answer = extract_math_boxed_answer(solution)
        if not answer:
            skipped += 1
            continue

        all_problems.append({
            "prompt": problem_text,
            "answer": answer,
            "domain": "math",
            "difficulty": map_math_difficulty(level),
            "source": "math_hendrycks",
            "answer_type": "latex_boxed",
        })

    logger.info(f"MATH: {len(all_problems)} extracted, {skipped} skipped (no \\boxed answer)")

    # Sample if we have more than max_samples
    if len(all_problems) > max_samples:
        # Stratified sampling by difficulty
        by_diff = {"easy": [], "medium": [], "hard": []}
        for p in all_problems:
            by_diff[p["difficulty"]].append(p)

        sampled = []
        for diff, items in by_diff.items():
            ratio = len(items) / len(all_problems)
            n = max(1, int(max_samples * ratio))
            sampled.extend(random.sample(items, min(n, len(items))))

        # Fill remainder if needed
        if len(sampled) < max_samples:
            remaining = [p for p in all_problems if p not in sampled]
            sampled.extend(random.sample(remaining, min(max_samples - len(sampled), len(remaining))))

        all_problems = sampled[:max_samples]
        logger.info(f"MATH: sampled to {len(all_problems)}")

    return all_problems


def load_olympiad_physics() -> List[Dict[str, Any]]:
    """Load OlympiadBench physics (open-ended, English, competition)."""
    from datasets import load_dataset

    logger.info("Loading OlympiadBench physics...")
    try:
        ds = load_dataset("Hothan/OlympiadBench", split="train")
    except Exception:
        # Try specific config
        try:
            ds = load_dataset("Hothan/OlympiadBench", "OE_TO_physics_en_COMP", split="train")
        except Exception as e:
            logger.warning(f"Could not load OlympiadBench: {e}")
            return []

    problems = []
    skipped = 0
    for row in ds:
        # Filter to physics open-ended problems
        if row.get("subject", "") != "Physics":
            continue
        if row.get("answer_type", "") not in ("Numerical", "Expression", "Equation"):
            skipped += 1
            continue

        question = row.get("question", "").strip()
        if not question:
            skipped += 1
            continue

        # Extract answer — OlympiadBench uses final_answer list
        final_answer = row.get("final_answer", [])
        if isinstance(final_answer, list) and final_answer:
            answer = str(final_answer[0]).strip()
        elif isinstance(final_answer, str):
            answer = final_answer.strip()
        else:
            skipped += 1
            continue

        if not answer:
            skipped += 1
            continue

        # Build problem with optional unit and error
        problem = {
            "prompt": question,
            "answer": answer,
            "domain": "physics",
            "difficulty": "hard",  # All olympiad-level
            "source": "olympiad_bench",
            "answer_type": "numeric_with_unit",
        }

        # Add unit if available
        unit = row.get("unit", "")
        if unit:
            problem["unit"] = unit.strip()

        # Add error tolerance if available
        error = row.get("error", "")
        if error:
            problem["error"] = str(error).strip()

        problems.append(problem)

    logger.info(f"OlympiadBench physics: {len(problems)} loaded, {skipped} skipped")
    return problems


def load_rummlu_stem() -> List[Dict[str, Any]]:
    """Load Russian MMLU STEM subjects as multiple-choice problems.

    Uses CohereLabs/Global-MMLU (Russian config) — standard parquet format,
    no deprecated dataset scripts. Shuffles choices with per-problem
    deterministic seed to prevent positional bias.
    """
    from datasets import load_dataset

    # Fallback chain: Global-MMLU (parquet) → NLPCoreTeam (deprecated script)
    RUMMLU_SOURCES = [
        ("CohereLabs/Global-MMLU", {"name": "ru", "split": "test"}),
        ("NLPCoreTeam/mmlu_ru", {"split": "test"}),
    ]
    ds = None
    source_id = None
    for ds_id, kwargs in RUMMLU_SOURCES:
        try:
            logger.info(f"Loading ruMMLU from {ds_id}...")
            ds = load_dataset(ds_id, **kwargs)
            source_id = ds_id
            logger.info(f"Successfully loaded from {ds_id}")
            break
        except Exception as e:
            logger.warning(f"Failed to load {ds_id}: {e}")
            continue

    if ds is None:
        logger.error("All ruMMLU sources failed. Returning empty list.")
        return []

    is_global_mmlu = "Global-MMLU" in source_id

    problems = []
    skipped = 0
    for row in ds:
        subject = row.get("subject", "")
        if subject not in RUMMLU_STEM_SUBJECTS:
            continue

        question = row.get("question", "").strip()
        if not question:
            skipped += 1
            continue

        # Extract choices and correct answer index depending on source format
        if is_global_mmlu:
            # Global-MMLU: option_a..option_d, answer is letter "A"-"D"
            choices = [
                row.get("option_a", ""),
                row.get("option_b", ""),
                row.get("option_c", ""),
                row.get("option_d", ""),
            ]
            answer_raw = row.get("answer", "")
            letter_to_idx = {"A": 0, "B": 1, "C": 2, "D": 3}
            answer_idx = letter_to_idx.get(answer_raw)
        else:
            # NLPCoreTeam: choices list, answer is int index
            choices = row.get("choices", [])
            answer_idx = row.get("answer", None)
            if not isinstance(answer_idx, int):
                skipped += 1
                continue

        if len(choices) != 4 or answer_idx is None or not (0 <= answer_idx < 4):
            skipped += 1
            continue

        if any(not c.strip() for c in choices):
            skipped += 1
            continue

        # Shuffle choices with deterministic seed
        seed = hash(question) & 0xFFFFFFFF
        rng = random.Random(seed)
        indexed_choices = list(enumerate(choices))
        rng.shuffle(indexed_choices)

        # Find new position of correct answer
        new_answer_idx = None
        shuffled_choices = []
        for new_idx, (orig_idx, text) in enumerate(indexed_choices):
            shuffled_choices.append(text)
            if orig_idx == answer_idx:
                new_answer_idx = new_idx

        if new_answer_idx is None:
            skipped += 1
            continue

        answer_letter = MC_LETTERS[new_answer_idx]

        # Format MC prompt (Russian)
        prompt_lines = [question]
        for i, choice_text in enumerate(shuffled_choices):
            prompt_lines.append(f"{MC_LETTERS[i]}) {choice_text}")
        prompt = "\n".join(prompt_lines)

        domain = RUMMLU_STEM_SUBJECTS[subject]
        difficulty = RUMMLU_DIFFICULTY.get(subject, "medium")

        problems.append({
            "prompt": prompt,
            "answer": answer_letter,
            "domain": domain,
            "difficulty": difficulty,
            "source": "rummlu",
            "answer_type": "mc_letter",
        })

    logger.info(f"ruMMLU STEM: {len(problems)} loaded, {skipped} skipped")
    return problems


def load_current_filtered() -> List[Dict[str, Any]]:
    """Load and filter current dataset for RL-compatible problems.

    Filters:
    - type == "verifiable"
    - Has numeric or \\boxed{} answer
    - NOT conceptual (no "explain"/"prove"/"derive" keywords)
    """
    from datasets import load_dataset

    logger.info("Loading current dataset from Siesher/mits-stem-training-data...")
    try:
        hf_ds = load_dataset("Siesher/mits-stem-training-data", "gspo")
        all_rows = [dict(r) for r in hf_ds["train"]] + [dict(r) for r in hf_ds["test"]]
    except Exception as e:
        logger.warning(f"Could not load current dataset: {e}")
        return []

    # Conceptual keywords to exclude
    conceptual_patterns = re.compile(
        r'\b(explain|объясни|докажи|prove|derive|выведи|опиши|describe|'
        r'расскажи|tell|обоснуй|justify|compare|сравни)\b',
        re.IGNORECASE,
    )

    problems = []
    skipped = 0
    for row in all_rows:
        # Must be verifiable
        if row.get("type", "verifiable") != "verifiable":
            skipped += 1
            continue

        prompt = row.get("prompt", row.get("instruction", "")).strip()
        answer = row.get("answer", row.get("ground_truth", "")).strip()

        if not prompt or not answer:
            skipped += 1
            continue

        # Skip conceptual questions
        if conceptual_patterns.search(prompt):
            skipped += 1
            continue

        # Must have numeric or boxed answer
        has_boxed = "\\boxed{" in answer or "\\boxed{" in prompt
        has_numeric = bool(re.search(r'\d', answer))
        has_mc = bool(re.match(r'^[A-DА-Г]$', answer.strip()))

        if not (has_boxed or has_numeric or has_mc):
            skipped += 1
            continue

        # Determine answer type
        if has_mc:
            answer_type = "mc_letter"
        elif has_boxed:
            answer_type = "latex_boxed"
        else:
            answer_type = "numeric"

        domain = row.get("domain", "math")
        difficulty = row.get("difficulty", "medium")
        # Normalize difficulty string
        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "medium"

        problems.append({
            "prompt": prompt,
            "answer": answer,
            "domain": domain,
            "difficulty": difficulty,
            "source": "current_filtered",
            "answer_type": answer_type,
        })

    logger.info(f"Current filtered: {len(problems)} loaded, {skipped} skipped")
    return problems


# ---------------------------------------------------------------------------
# Dataset balancing
# ---------------------------------------------------------------------------

def balance_dataset(
    all_problems: List[Dict[str, Any]],
    target_counts: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """Balance dataset by source with stratified difficulty sampling.

    Default targets:
        gsm8k: 7400, math_hendrycks: 5000, olympiad_bench: 236,
        rummlu: 1500, current_filtered: 800

    If a source has fewer than target, keep all.
    If more, stratified sample preserving difficulty ratios.

    Args:
        all_problems: Combined list from all sources.
        target_counts: Optional dict of source -> max count.

    Returns:
        Balanced list of problems.
    """
    defaults = {
        "gsm8k": 7400,
        "math_hendrycks": 5000,
        "olympiad_bench": 236,
        "rummlu": 1500,
        "current_filtered": 800,
    }
    targets = target_counts or defaults

    # Group by source
    by_source: Dict[str, List[Dict[str, Any]]] = {}
    for p in all_problems:
        by_source.setdefault(p["source"], []).append(p)

    balanced = []
    for source, items in by_source.items():
        cap = targets.get(source, len(items))

        if len(items) <= cap:
            balanced.extend(items)
            continue

        # Stratified sampling: preserve difficulty distribution
        by_diff: Dict[str, List[Dict[str, Any]]] = {}
        for p in items:
            by_diff.setdefault(p["difficulty"], []).append(p)

        sampled = []
        for diff, diff_items in by_diff.items():
            ratio = len(diff_items) / len(items)
            n = max(1, round(cap * ratio))
            sampled.extend(random.sample(diff_items, min(n, len(diff_items))))

        # Trim or fill to exact cap
        if len(sampled) > cap:
            sampled = random.sample(sampled, cap)
        elif len(sampled) < cap:
            remaining = [p for p in items if p not in sampled]
            fill = min(cap - len(sampled), len(remaining))
            sampled.extend(random.sample(remaining, fill))

        balanced.extend(sampled)

    random.shuffle(balanced)
    return balanced


# ---------------------------------------------------------------------------
# Dataset statistics
# ---------------------------------------------------------------------------

def compute_stats(problems: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute detailed dataset statistics."""
    total = len(problems)

    source_counts = Counter(p["source"] for p in problems)
    domain_counts = Counter(p["domain"] for p in problems)
    difficulty_counts = Counter(p["difficulty"] for p in problems)
    answer_type_counts = Counter(p["answer_type"] for p in problems)

    # Cross-tabulation: domain x difficulty
    domain_difficulty = {}
    for p in problems:
        key = p["domain"]
        if key not in domain_difficulty:
            domain_difficulty[key] = Counter()
        domain_difficulty[key][p["difficulty"]] += 1

    # Verify all answers are non-empty
    empty_answers = sum(1 for p in problems if not p.get("answer", "").strip())

    stats = {
        "total": total,
        "sources": dict(source_counts),
        "domains": dict(domain_counts),
        "domain_pcts": {
            d: round(c / total * 100, 1)
            for d, c in domain_counts.items()
        },
        "difficulty": dict(difficulty_counts),
        "difficulty_pcts": {
            d: round(c / total * 100, 1)
            for d, c in difficulty_counts.items()
        },
        "answer_types": dict(answer_type_counts),
        "domain_x_difficulty": {
            d: dict(dd) for d, dd in domain_difficulty.items()
        },
        "empty_answers": empty_answers,
    }
    return stats


def print_stats(stats: Dict[str, Any]) -> None:
    """Print dataset statistics in a readable format."""
    print(f"\n{'='*60}")
    print(f"RL Dataset Statistics")
    print(f"{'='*60}")
    print(f"Total problems: {stats['total']}")
    print(f"Empty answers: {stats['empty_answers']}")

    print(f"\nBy source:")
    for source, count in sorted(stats["sources"].items()):
        print(f"  {source}: {count}")

    print(f"\nBy domain:")
    for domain, count in sorted(stats["domains"].items()):
        pct = stats["domain_pcts"][domain]
        print(f"  {domain}: {count} ({pct}%)")

    print(f"\nBy difficulty:")
    for diff in ("easy", "medium", "hard"):
        count = stats["difficulty"].get(diff, 0)
        pct = stats["difficulty_pcts"].get(diff, 0)
        print(f"  {diff}: {count} ({pct}%)")

    print(f"\nBy answer type:")
    for atype, count in sorted(stats["answer_types"].items()):
        print(f"  {atype}: {count}")

    print(f"\nDomain x Difficulty:")
    for domain in sorted(stats["domain_x_difficulty"].keys()):
        dd = stats["domain_x_difficulty"][domain]
        parts = [f"{d}={dd.get(d, 0)}" for d in ("easy", "medium", "hard")]
        print(f"  {domain}: {', '.join(parts)}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def prepare_rl_dataset(
    output_path: str,
    math_samples: int = 5000,
    stats_only: bool = False,
    seed: int = 42,
) -> Dict[str, Any]:
    """Main pipeline: load all sources, normalize, balance, save.

    Args:
        output_path: Path for output JSONL file.
        math_samples: Max samples from MATH dataset.
        stats_only: If True, compute stats without saving.
        seed: Random seed for reproducibility.

    Returns:
        Dataset statistics dict.
    """
    random.seed(seed)

    # Load all sources — each loader is wrapped so partial datasets work
    print("Loading datasets from HuggingFace...")
    loaders = [
        ("GSM8K", lambda: load_gsm8k()),
        ("MATH (Hendrycks)", lambda: load_math_hendrycks(max_samples=math_samples)),
        ("OlympiadBench physics", lambda: load_olympiad_physics()),
        ("ruMMLU STEM", lambda: load_rummlu_stem()),
        ("Current filtered", lambda: load_current_filtered()),
    ]
    loaded = {}
    for name, loader_fn in loaders:
        try:
            loaded[name] = loader_fn()
        except Exception as e:
            logger.warning(f"Failed to load {name}: {e}")
            print(f"  WARNING: {name} failed to load — skipping ({e})")
            loaded[name] = []

    gsm8k = loaded["GSM8K"]
    math_hend = loaded["MATH (Hendrycks)"]
    olympiad = loaded["OlympiadBench physics"]
    rummlu = loaded["ruMMLU STEM"]
    current = loaded["Current filtered"]

    print(f"\nRaw counts:")
    print(f"  GSM8K: {len(gsm8k)}")
    print(f"  MATH (Hendrycks): {len(math_hend)}")
    print(f"  OlympiadBench physics: {len(olympiad)}")
    print(f"  ruMMLU STEM: {len(rummlu)}")
    print(f"  Current filtered: {len(current)}")

    # Combine all
    all_problems = gsm8k + math_hend + olympiad + rummlu + current
    print(f"  Total (raw): {len(all_problems)}")

    # Balance
    balanced = balance_dataset(all_problems)
    print(f"  Total (balanced): {len(balanced)}")

    # Deduplicate by prompt
    seen_prompts = set()
    deduped = []
    for p in balanced:
        prompt_key = p["prompt"].strip().lower()[:200]
        if prompt_key not in seen_prompts:
            seen_prompts.add(prompt_key)
            deduped.append(p)
    if len(deduped) < len(balanced):
        print(f"  Removed {len(balanced) - len(deduped)} duplicates")
    balanced = deduped

    # Compute stats
    stats = compute_stats(balanced)
    print_stats(stats)

    # Save
    if not stats_only:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for p in balanced:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        print(f"\nSaved {len(balanced)} problems to {output_path}")
        stats["output_path"] = str(out)

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prepare hybrid RL dataset for GSPO training"
    )
    parser.add_argument(
        "--output",
        default="training/data/rl_combined.jsonl",
        help="Output JSONL path",
    )
    parser.add_argument(
        "--math-samples",
        type=int,
        default=5000,
        help="Max samples from MATH dataset",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Only compute and print stats, don't save",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    stats = prepare_rl_dataset(
        output_path=args.output,
        math_samples=args.math_samples,
        stats_only=args.stats_only,
        seed=args.seed,
    )

    # Save stats JSON alongside output
    if not args.stats_only:
        stats_path = Path(args.output).with_suffix(".stats.json")
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        print(f"Stats saved to {stats_path}")
