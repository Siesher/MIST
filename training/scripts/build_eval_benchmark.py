#!/usr/bin/env python3
"""
Build comprehensive evaluation benchmark from multiple sources.

Combines:
  1. Custom LLM-generated problems (218 problems, 5 STEM domains, Russian)
  2. MGSM Russian (250 grade-school math problems, Russian)
  3. ruMMLU STEM subjects (test split, ~800 MC problems, Russian)

Output: JSONL with unified schema:
  {prompt, ground_truth, answer_type, domain, difficulty, topic, source}

Usage:
    python training/scripts/build_eval_benchmark.py
    python training/scripts/build_eval_benchmark.py --output training/data/eval_benchmark.jsonl
    python training/scripts/build_eval_benchmark.py --skip-download  # use cached HF data
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import json
import logging
import random
from collections import Counter
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ─── ruMMLU subject → MITS domain mapping ──────────────────────

RUMMLU_STEM_SUBJECTS: Dict[str, Dict] = {
    # Math
    "abstract_algebra":          {"domain": "math",      "difficulty": "hard",   "topic": "абстрактная алгебра"},
    "college_mathematics":       {"domain": "math",      "difficulty": "hard",   "topic": "высшая математика"},
    "elementary_mathematics":    {"domain": "math",      "difficulty": "easy",   "topic": "элементарная математика"},
    "high_school_mathematics":   {"domain": "math",      "difficulty": "medium", "topic": "школьная математика"},
    # Physics
    "college_physics":           {"domain": "physics",   "difficulty": "hard",   "topic": "общая физика"},
    "conceptual_physics":        {"domain": "physics",   "difficulty": "easy",   "topic": "концептуальная физика"},
    "high_school_physics":       {"domain": "physics",   "difficulty": "medium", "topic": "школьная физика"},
    "astronomy":                 {"domain": "physics",   "difficulty": "medium", "topic": "астрономия"},
    "electrical_engineering":    {"domain": "physics",   "difficulty": "hard",   "topic": "электротехника"},
    # Chemistry
    "college_chemistry":         {"domain": "chemistry", "difficulty": "hard",   "topic": "общая химия"},
    "high_school_chemistry":     {"domain": "chemistry", "difficulty": "medium", "topic": "школьная химия"},
    # Biology
    "college_biology":           {"domain": "biology",   "difficulty": "hard",   "topic": "общая биология"},
    "high_school_biology":       {"domain": "biology",   "difficulty": "medium", "topic": "школьная биология"},
    "anatomy":                   {"domain": "biology",   "difficulty": "hard",   "topic": "анатомия"},
    "medical_genetics":          {"domain": "biology",   "difficulty": "hard",   "topic": "медицинская генетика"},
    "college_medicine":          {"domain": "biology",   "difficulty": "hard",   "topic": "медицина"},
    # CS
    "college_computer_science":      {"domain": "cs", "difficulty": "hard",   "topic": "информатика"},
    "computer_security":             {"domain": "cs", "difficulty": "medium", "topic": "информационная безопасность"},
    "high_school_computer_science":  {"domain": "cs", "difficulty": "medium", "topic": "школьная информатика"},
    "machine_learning":              {"domain": "cs", "difficulty": "hard",   "topic": "машинное обучение"},
}

ANSWER_LETTERS = ["A", "B", "C", "D"]


# ─── Source 1: Custom LLM-generated problems ───────────────────

def load_custom_eval(path: str) -> List[Dict]:
    """Load our existing LLM-generated eval dataset."""
    problems = []
    p = Path(path)
    if not p.exists():
        logger.warning(f"Custom eval not found at {path}, skipping")
        return problems

    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                record["source"] = record.get("source", "custom_llm")
                problems.append(record)

    logger.info(f"Custom eval: {len(problems)} problems loaded from {path}")
    return problems


# ─── Source 2: MGSM Russian ────────────────────────────────────

def _download_parquet(repo_id: str, filename: str):
    """Download a parquet file from HF Hub's auto-converted branch."""
    from huggingface_hub import hf_hub_download
    import pandas as pd

    path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        repo_type="dataset",
        revision="refs/convert/parquet",
    )
    return pd.read_parquet(path)


def load_mgsm_russian() -> List[Dict]:
    """Load MGSM Russian test split (250 grade-school math problems)."""
    logger.info("Downloading MGSM Russian (parquet)...")
    df = _download_parquet("juletxara/mgsm", "ru/test/0000.parquet")

    problems = []
    for _, row in df.iterrows():
        question = str(row["question"])
        answer_number = int(row["answer_number"])

        if question.startswith("Question:"):
            question = question[len("Question:"):].strip()

        problems.append({
            "prompt": question,
            "ground_truth": str(answer_number),
            "answer_type": "numeric",
            "domain": "math",
            "difficulty": classify_mgsm_difficulty(question, answer_number),
            "topic": "арифметика и логика",
            "source": "mgsm_ru",
        })

    logger.info(f"MGSM Russian: {len(problems)} problems loaded")
    return problems


def classify_mgsm_difficulty(question: str, answer: int) -> str:
    """Classify MGSM problem difficulty based on problem characteristics."""
    import re as _re

    sentences = [s.strip() for s in question.split(".") if s.strip()]
    num_sentences = len(sentences)
    num_numbers = len(_re.findall(r'\d+', question))
    hard_keywords = ["процент", "отношение", "дробь", "каждый день", "каждую неделю",
                     "сколько всего", "разниц", "остаток", "в два раза", "в три раза"]
    has_hard_keywords = any(k in question.lower() for k in hard_keywords)
    has_hard_answer = abs(answer) > 1000 or (isinstance(answer, float) and answer != int(answer))

    if num_sentences <= 2 and num_numbers <= 3 and not has_hard_keywords:
        return "easy"
    elif num_sentences <= 4 and num_numbers <= 5 and not has_hard_answer:
        return "medium"
    else:
        return "hard"

# ─── Source 3: ruMMLU STEM ─────────────────────────────────────

def load_rummlu_stem(max_per_subject: int = 0) -> List[Dict]:
    """Load ruMMLU STEM subjects (test split, MC format) via parquet."""
    problems = []
    for subject, meta in RUMMLU_STEM_SUBJECTS.items():
        try:
            logger.info(f"  Loading ruMMLU/{subject}...")
            df = _download_parquet(
                "NLPCoreTeam/mmlu_ru",
                f"{subject}/test/0000.parquet",
            )
        except Exception as e:
            logger.warning(f"  Failed to load {subject}: {e}")
            continue

        subject_problems = []
        for _, row in df.iterrows():
            question_ru = str(row.get("question_ru", row.get("question", "")))
            choices_ru = row.get("choices_ru", row.get("choices", []))
            answer_idx = int(row["answer"])

            if not question_ru or choices_ru is None or len(choices_ru) == 0:
                continue

            options_text = "\n".join(
                f"{ANSWER_LETTERS[i]}. {choice}"
                for i, choice in enumerate(choices_ru)
                if i < len(ANSWER_LETTERS)
            )
            prompt = f"{question_ru}\n\n{options_text}"

            subject_problems.append({
                "prompt": prompt,
                "ground_truth": ANSWER_LETTERS[answer_idx],
                "answer_type": "mc_letter",
                "domain": meta["domain"],
                "difficulty": meta["difficulty"],
                "topic": meta["topic"],
                "source": f"rummlu_{subject}",
            })

        if max_per_subject > 0:
            random.seed(42)
            subject_problems = random.sample(
                subject_problems,
                min(max_per_subject, len(subject_problems)),
            )

        problems.extend(subject_problems)
        logger.info(f"    -> {len(subject_problems)} problems from {subject}")

    logger.info(f"ruMMLU STEM: {len(problems)} problems total")
    return problems


# ─── Merge & balance ───────────────────────────────────────────

def merge_and_report(
    sources: Dict[str, List[Dict]],
    max_per_domain: int = 0,
) -> List[Dict]:
    """Merge all sources, report statistics, optionally cap per domain."""
    all_problems = []
    for source_name, problems in sources.items():
        all_problems.extend(problems)
        logger.info(f"Source '{source_name}': {len(problems)} problems")

    # Statistics
    domain_counts = Counter(p["domain"] for p in all_problems)
    source_counts = Counter(p["source"].split("_")[0] for p in all_problems)
    difficulty_counts = Counter(p["difficulty"] for p in all_problems)
    answer_type_counts = Counter(p["answer_type"] for p in all_problems)

    logger.info(f"\n{'='*50}")
    logger.info(f"Total: {len(all_problems)} problems")
    logger.info(f"{'='*50}")
    logger.info("By domain:")
    for d, c in sorted(domain_counts.items()):
        logger.info(f"  {d:<12}: {c:>4}")
    logger.info("By source:")
    for s, c in sorted(source_counts.items()):
        logger.info(f"  {s:<12}: {c:>4}")
    logger.info("By difficulty:")
    for d, c in sorted(difficulty_counts.items()):
        logger.info(f"  {d:<12}: {c:>4}")
    logger.info("By answer type:")
    for t, c in sorted(answer_type_counts.items()):
        logger.info(f"  {t:<12}: {c:>4}")

    # Optional capping
    if max_per_domain > 0:
        capped = []
        for domain in ["math", "physics", "chemistry", "biology", "cs"]:
            domain_problems = [p for p in all_problems if p["domain"] == domain]
            if len(domain_problems) > max_per_domain:
                random.seed(42)
                domain_problems = random.sample(domain_problems, max_per_domain)
            capped.extend(domain_problems)
        logger.info(f"\nCapped to {max_per_domain}/domain: {len(capped)} problems")
        all_problems = capped

    random.seed(42)
    random.shuffle(all_problems)
    return all_problems


def save_benchmark(problems: List[Dict], output_path: str):
    """Save benchmark as JSONL."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for p in problems:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    logger.info(f"\nBenchmark saved to {output_path} ({len(problems)} problems)")


# ─── CLI ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build MITS evaluation benchmark")
    parser.add_argument(
        "--output", default="training/data/eval_benchmark.jsonl",
        help="Output JSONL path",
    )
    parser.add_argument(
        "--custom-eval", default="training/data/eval_dataset.jsonl",
        help="Path to existing custom eval dataset",
    )
    parser.add_argument(
        "--max-per-subject", type=int, default=0,
        help="Max problems per ruMMLU subject (0=all)",
    )
    parser.add_argument(
        "--max-per-domain", type=int, default=0,
        help="Max problems per domain in final dataset (0=unlimited)",
    )
    parser.add_argument(
        "--skip-mgsm", action="store_true",
        help="Skip MGSM download",
    )
    parser.add_argument(
        "--skip-rummlu", action="store_true",
        help="Skip ruMMLU download",
    )
    args = parser.parse_args()

    sources = {}

    # 1. Custom eval
    custom = load_custom_eval(args.custom_eval)
    if custom:
        sources["custom"] = custom

    # 2. MGSM Russian
    if not args.skip_mgsm:
        try:
            mgsm = load_mgsm_russian()
            sources["mgsm"] = mgsm
        except Exception as e:
            logger.error(f"MGSM loading failed: {e}")

    # 3. ruMMLU STEM
    if not args.skip_rummlu:
        try:
            rummlu = load_rummlu_stem(max_per_subject=args.max_per_subject)
            sources["rummlu"] = rummlu
        except Exception as e:
            logger.error(f"ruMMLU loading failed: {e}")

    if not sources:
        logger.error("No sources loaded!")
        return

    # Merge
    benchmark = merge_and_report(sources, max_per_domain=args.max_per_domain)

    # Save
    save_benchmark(benchmark, args.output)

    # Also update baseline dict in eval cells if needed
    logger.info("\nDone! Update EVAL_DATASET_PATH in notebooks to use this file.")
    logger.info("Update BASELINE dict after evaluating base model on this benchmark.")


if __name__ == "__main__":
    main()
