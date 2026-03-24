#!/usr/bin/env python3
"""
Per-stage model evaluation script for MITS training pipeline.

Evaluates a model checkpoint after each training stage by:
1. Loading the adapter from HuggingFace (or local path)
2. Running evaluation on the eval dataset
3. Optionally converting to GGUF and evaluating via Ollama
4. Producing a JSON report with per-domain accuracy metrics

Supports two modes:
  - colab:  Uses Unsloth to load adapter + evaluate on GPU (fast)
  - local:  Uses Ollama API to evaluate a GGUF/model (no GPU needed)

Usage:
    # Evaluate on Colab (after each training stage)
    python evaluate_stage.py --mode colab \
        --adapter Siesher/mits-qwen3-4b-gspo \
        --stage gspo \
        --eval-data training/data/eval_dataset.jsonl

    # Evaluate locally via Ollama
    python evaluate_stage.py --mode local \
        --model mits-tutor-qwen3-4b-q4_k_m \
        --stage gspo \
        --eval-data training/data/eval_dataset.jsonl

    # Evaluate + export GGUF on Colab
    python evaluate_stage.py --mode colab \
        --adapter Siesher/mits-qwen3-4b-gspo \
        --stage gspo \
        --export-gguf --quantization q4_k_m

    # Compare all stages
    python evaluate_stage.py compare \
        --reports-dir evaluation/reports/
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import json
import logging
import os
import random
import re
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Pipeline stages in order (SFT removed — Instruct base; AdaSTaR removed — 9B baseline too strong)
STAGES = ["base", "gspo", "raft", "dpo"]
STAGE_HF_REPOS = {
    "gspo": "Siesher/mits-qwen3-9b-gspo",
    "raft": "Siesher/mits-qwen3-9b-raft",
    "dpo": "Siesher/mits-qwen3-9b-final",
}

SYSTEM_PROMPT_CALC = (
    "Ты — репетитор по STEM. Реши задачу пошагово и запиши финальный ответ в \\boxed{}."
)
SYSTEM_PROMPT_MC = "Проанализируй задачу и выбери правильный ответ (A, B, C или D)."


def stratified_sample(problems: List[Dict], n: int, seed: int = 42) -> List[Dict]:
    """Sample N problems proportionally by (domain, difficulty).

    Groups problems by (domain, difficulty), then allocates samples
    proportionally to each group's size. Handles remainders via
    largest-remainder method to hit exactly N.

    Falls back to random sampling if a group is too small for its allocation.
    """
    if n >= len(problems):
        return problems

    rng = random.Random(seed)

    groups = defaultdict(list)
    for p in problems:
        key = (p.get("domain", "math"), p.get("difficulty", "medium"))
        groups[key].append(p)

    total = len(problems)
    allocations = {}
    remainders = {}

    for key, group in groups.items():
        exact = n * len(group) / total
        base = int(exact)
        base = min(base, len(group))
        allocations[key] = base
        remainders[key] = exact - base

    # Handle remainders via largest-remainder method
    remainder_count = n - sum(allocations.values())
    if remainder_count > 0:
        sorted_keys = sorted(remainders.keys(), key=lambda k: remainders[k], reverse=True)
        for i in range(remainder_count):
            key = sorted_keys[i % len(sorted_keys)]
            allocations[key] += 1

    # Sample from each group and combine results
    result = []
    for key, group in groups.items():
        result.extend(rng.sample(group, allocations[key]))

    rng.shuffle(result)
    return result


def check_format_compliance(completion: str) -> Dict[str, Any]:
    """Check format compliance of a model completion."""
    # Strip thinking block for analysis of the visible response
    visible = completion.split("</think>")[-1].strip() if "</think>" in completion else completion

    has_boxed = bool(re.search(r"\\boxed\{", visible))
    step_markers = [
        r"[Шш]аг\s*\d",  # Шаг 1, шаг 2
        r"[Сс]ледовательно",  # Следовательно
        r"[Пп]одставим",  # Подставим
        r"[Нн]айд[её]м",  # Найдём
        r"[Рр]ешени[ея]",  # Решение
        r"[Оо]твет\s*:",  # Ответ:
        r"\d\)\s",  # 1) 2) numbered steps
        r"(?:во-первых|во-вторых)",  # во-первых, во-вторых
    ]
    has_steps = any(re.search(p, visible) for p in step_markers)
    has_thinking = "<think>" in completion and "</think>" in completion

    return {
        "has_boxed": has_boxed,
        "has_steps": has_steps,
        "has_thinking": has_thinking,
        "response_length": len(completion),
    }


def load_eval_dataset(path: str) -> List[Dict]:
    """Load evaluation dataset from JSONL."""
    problems = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                problems.append(json.loads(line))
    logger.info(f"Loaded {len(problems)} eval problems from {path}")
    return problems


def _clean_boxed(val: str) -> str:
    """Clean boxed value: strip \\text{}, remove comma separators."""
    # \text{...} or \text {...} -> contents
    val = re.sub(r"\\text\s*\{([^}]*)\}", r"\1", val)
    # Remove LaTeX formatting
    val = val.replace("\\,", "").replace("\\;", "").replace("\\!", "")
    # Remove units (руб, $, см, Дж, etc.) but keep the number
    val = re.sub(r"\s*(?:руб|долл|\$|см|м|кг|Дж|л|г)\.?\s*$", "", val).strip()
    # Remove comma thousand-separators: 276,000 -> 276000
    val = re.sub(r"(\d),(\d{3})\b", r"\1\2", val)
    val = re.sub(r"(\d),(\d{3})\b", r"\1\2", val)  # second pass for millions
    return val.strip()


def extract_answer(text: str) -> str:
    """Extract answer from model output."""
    # Strip thinking block
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    if not text:
        return ""
    # Try \boxed{}
    boxed = re.findall(r"\\boxed\{([^}]+)\}", text)
    if boxed:
        return _clean_boxed(boxed[-1])
    # Try "Ответ: X" / "Ответ — X" / "Answer: X" (colon, equals, em-dash, hyphen)
    # First try to extract just a letter/number after ответ marker
    answer_letter = re.search(
        r"(?:правильный\s+)?(?:ответ|answer)\s*[:=—–\-]\s*\*{0,2}\s*([A-DА-Гa-dа-г])\b",
        text,
        re.IGNORECASE,
    )
    if answer_letter:
        return answer_letter.group(1).strip()
    # Then try broader match for numeric/text answers
    answer_match = re.search(
        r"(?:правильный\s+)?(?:ответ|answer|вариант(?:\s+ответа)?)\s*[:=—–\-]\s*(.+?)(?:\.\s|$)",
        text,
        re.IGNORECASE,
    )
    if answer_match:
        return answer_match.group(1).strip()
    # Try "вариант **X**" / "вариант X " pattern (last occurrence)
    variant_match = re.findall(
        r"вариант\s+\*{0,2}([A-DА-Гa-dа-г])\b",
        text,
        re.IGNORECASE,
    )
    if variant_match:
        return variant_match[-1].strip()
    # Try bold letter at end: **X** or **X. ... ** (common GSPO output pattern)
    bold_match = re.findall(r"\*\*\s*([A-DА-Гa-dа-г])\s*[\.\)]?\s*[^*]*\*\*", text)
    if bold_match:
        return bold_match[-1].strip()
    # Try standalone bold letter near end (last 300 chars)
    tail = text[-300:] if len(text) > 300 else text
    bold_tail = re.findall(r"\*\*([A-DА-Гa-dа-г])\*\*", tail)
    if bold_tail:
        return bold_tail[-1].strip()
    # Try last number (strip comma separators first)
    cleaned = re.sub(r"(\d),(\d{3})\b", r"\1\2", text)
    numbers = re.findall(r"[-+]?\d*\.?\d+", cleaned)
    return numbers[-1] if numbers else ""


def _normalize_number(s: str) -> str:
    """Normalize number string: remove comma separators, %, units."""
    s = re.sub(r"(\d),(\d{3})\b", r"\1\2", s)  # 276,000 -> 276000
    s = re.sub(r"(\d),(\d{3})\b", r"\1\2", s)  # second pass
    s = re.sub(r"\\text\s*\{[^}]*\}", "", s)  # \text{...}
    s = s.replace("\\,", "").replace("\\;", "")
    return s.strip()


def verify_answer(extracted: str, truth: str, domain: str, answer_type: str = "numeric") -> bool:
    """Verify if extracted answer matches ground truth."""
    extracted = str(extracted) if extracted is not None else ""
    truth = str(truth) if truth is not None else ""

    if not extracted or not truth:
        return False

    extracted = extracted.strip().lower()
    truth = truth.strip().lower()

    # Exact match
    if extracted == truth:
        return True

    # MC letter match
    if answer_type == "mc_letter":
        # Normalize Cyrillic АБВГ -> Latin ABCD for comparison
        cyrillic_to_latin = str.maketrans("АБВГабвгАБВГ", "ABCDabcdABCD")

        def find_mc_letter(s: str) -> str | None:
            s_norm = s.translate(cyrillic_to_latin)
            m = re.search(r"[a-d]", s_norm, re.IGNORECASE)
            return m.group(0).upper() if m else None

        ext_l = find_mc_letter(extracted)
        truth_l = find_mc_letter(truth)
        if ext_l and truth_l:
            return ext_l == truth_l
        return False

    # Normalize numbers
    extracted_n = _normalize_number(extracted)
    truth_n = _normalize_number(truth)

    # Handle percentage vs fraction: 50% == 0.5, 25% == 0.25
    def to_float_pct(s: str) -> float | None:
        # Match both real % and escaped \%
        m = re.search(r"([-+]?\d*\.?\d+)\s*\\?%", s)
        if m:
            return float(m.group(1)) / 100.0
        nums = re.findall(r"[-+]?\d*\.?\d+", s)
        return float(nums[-1]) if nums else None

    # Numeric comparison
    try:
        e = to_float_pct(extracted_n)
        t = to_float_pct(truth_n)
        if e is not None and t is not None:
            if abs(t) < 1e-10:
                return abs(e - t) < 1e-6
            return abs(e - t) / max(abs(t), 1e-10) < 0.05
    except (ValueError, IndexError):
        pass

    # Symbolic comparison (if sympy available)
    try:
        import sympy

        pred = sympy.sympify(extracted_n)
        gold = sympy.sympify(truth_n)
        return sympy.simplify(pred - gold) == 0
    except Exception:
        pass

    return False


# ─── In-notebook evaluation (model already loaded) ───────────


def evaluate_with_model(
    model,
    tokenizer,
    eval_problems: List[Dict],
    max_samples: int = 0,
    batch_size: int = 4,
    max_new_tokens: int = 768,
    completions_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate an already-loaded model on eval problems (for use inside notebooks).

    Unlike evaluate_colab(), this does NOT load the model — it uses
    the model/tokenizer that are already in GPU memory from training.
    """
    import torch
    from unsloth import FastLanguageModel

    # Qwen3.5 returns Processor (multimodal) — unwrap to plain tokenizer
    if not hasattr(tokenizer, "vocab_size") and hasattr(tokenizer, "tokenizer"):
        tokenizer = tokenizer.tokenizer

    FastLanguageModel.for_inference(model)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    problems = eval_problems[:max_samples] if max_samples > 0 else eval_problems

    # Prepare completions JSONL file for full response logging
    completions_file = None
    if completions_path:
        os.makedirs(os.path.dirname(completions_path) or ".", exist_ok=True)
        completions_file = open(completions_path, "w", encoding="utf-8")
        logger.info(f"Saving full completions to {completions_path}")

    results = defaultdict(lambda: {"total": 0, "correct": 0})
    diff_results = defaultdict(lambda: {"total": 0, "correct": 0})
    completions_log = []
    total_tokens = 0

    logger.info(f"Evaluating {len(problems)} problems (batch_size={batch_size})...")
    start_time = time.time()

    for batch_start in range(0, len(problems), batch_size):
        batch = problems[batch_start : batch_start + batch_size]

        prompts = []
        for p in batch:
            sys_prompt = (
                SYSTEM_PROMPT_MC if p.get("answer_type") == "mc_letter" else SYSTEM_PROMPT_CALC
            )
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": p["prompt"]},
            ]
            prompts.append(
                tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            )

        inputs = tokenizer(
            text=prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        ).to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                temperature=1.0,
            )

        for i, p in enumerate(batch):
            prompt_len = inputs["input_ids"][i].ne(tokenizer.pad_token_id).sum().item()
            completion = tokenizer.decode(outputs[i][prompt_len:], skip_special_tokens=True)
            total_tokens += len(completion.split())

            domain = p.get("domain", "math")
            difficulty = p.get("difficulty", "medium")
            answer_type = p.get("answer_type", "numeric")
            truth = p.get("ground_truth", p.get("answer", ""))

            extracted = extract_answer(completion)
            correct = verify_answer(extracted, truth, domain, answer_type)

            results[domain]["total"] += 1
            results[domain]["correct"] += 1 if correct else 0
            diff_results[difficulty]["total"] += 1
            diff_results[difficulty]["correct"] += 1 if correct else 0

            entry = {
                "prompt": p["prompt"],
                "completion": completion,
                "domain": domain,
                "difficulty": difficulty,
                "answer_type": answer_type,
                "truth": truth,
                "extracted": extracted,
                "correct": correct,
                "source": p.get("source", ""),
            }
            completions_log.append(entry)

            # Write full completion to JSONL
            if completions_file is not None:
                completions_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
                completions_file.flush()

        done = min(batch_start + batch_size, len(problems))
        if done % 40 == 0 or done == len(problems):
            elapsed = time.time() - start_time
            logger.info(f"  {done}/{len(problems)} ({elapsed:.0f}s)")

    elapsed = time.time() - start_time

    if completions_file is not None:
        completions_file.close()
        logger.info(
            f"Full completions saved to {completions_path} ({len(completions_log)} entries)"
        )

    total_correct = sum(r["correct"] for r in results.values())
    total_count = sum(r["total"] for r in results.values())
    overall_accuracy = total_correct / total_count if total_count > 0 else 0

    return {
        "overall_accuracy": overall_accuracy,
        "total_problems": total_count,
        "total_correct": total_correct,
        "per_domain": {
            d: {
                "accuracy": r["correct"] / r["total"] if r["total"] > 0 else 0,
                "correct": r["correct"],
                "total": r["total"],
            }
            for d, r in results.items()
        },
        "per_difficulty": {
            d: {
                "accuracy": r["correct"] / r["total"] if r["total"] > 0 else 0,
                "correct": r["correct"],
                "total": r["total"],
            }
            for d, r in diff_results.items()
        },
        "avg_completion_tokens": total_tokens / total_count if total_count > 0 else 0,
        "elapsed_seconds": elapsed,
        "completions_path": completions_path,
        "sample_completions": completions_log[:20],
    }


def append_summary_csv(
    eval_results: Dict,
    stage: str,
    csv_path: str = "evaluation/reports/summary.csv",
):
    """Append a row to the summary CSV for graph building."""
    import csv

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    domains = eval_results.get("per_domain", {})
    difficulties = eval_results.get("per_difficulty", {})

    row = {
        "stage": stage,
        "overall": f"{eval_results['overall_accuracy']:.4f}",
        "math": f"{domains.get('math', {}).get('accuracy', 0):.4f}",
        "physics": f"{domains.get('physics', {}).get('accuracy', 0):.4f}",
        "chemistry": f"{domains.get('chemistry', {}).get('accuracy', 0):.4f}",
        "biology": f"{domains.get('biology', {}).get('accuracy', 0):.4f}",
        "cs": f"{domains.get('cs', {}).get('accuracy', 0):.4f}",
        "easy": f"{difficulties.get('easy', {}).get('accuracy', 0):.4f}",
        "medium": f"{difficulties.get('medium', {}).get('accuracy', 0):.4f}",
        "hard": f"{difficulties.get('hard', {}).get('accuracy', 0):.4f}",
        "total_problems": eval_results["total_problems"],
        "elapsed_s": f"{eval_results.get('elapsed_seconds', 0):.0f}",
        "timestamp": datetime.now().isoformat(),
    }

    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    logger.info(f"Summary row appended to {csv_path}")


def print_comparison(eval_results: Dict, stage: str, baseline: Optional[Dict] = None):
    """Print a comparison table with optional baseline."""
    overall = eval_results["overall_accuracy"]
    domains = eval_results.get("per_domain", {})

    base_overall = baseline["overall_accuracy"] if baseline else None

    header = f"  {stage.upper()} | Accuracy: {overall:.1%}"
    if base_overall is not None:
        header += f" (base: {base_overall:.1%}) | Δ={overall - base_overall:+.1%}"

    print(f"\n{'=' * 60}")
    print(header)
    print(f"{'=' * 60}")
    print(f"  {'Domain':<12} {'Score':>7} {'Base':>7} {'Delta':>7}")
    print(f"  {'-' * 36}")

    for d in ["math", "physics", "chemistry", "biology", "cs"]:
        acc = domains.get(d, {}).get("accuracy", 0)
        if baseline:
            base_d = baseline.get("per_domain", {}).get(d, {}).get("accuracy", 0)
            delta = acc - base_d
            arrow = "▲" if delta > 0.005 else "▼" if delta < -0.005 else "="
            print(f"  {d:<12} {acc:>6.1%} {base_d:>6.1%} {arrow}{abs(delta):>5.1%}")
        else:
            print(f"  {d:<12} {acc:>6.1%}")

    print(f"{'=' * 60}")
    print(
        f"  Time: {eval_results.get('elapsed_seconds', 0):.0f}s | Problems: {eval_results['total_problems']}"
    )


# ─── Colab mode: Unsloth evaluation ──────────────────────────


def evaluate_colab(
    adapter_source: str,
    eval_problems: List[Dict],
    max_samples: int = 0,
    batch_size: int = 4,
    max_new_tokens: int = 768,
    completions_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate using Unsloth on GPU (Colab mode)."""
    import torch
    from unsloth import FastLanguageModel

    logger.info(f"Loading adapter from {adapter_source}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=adapter_source,
        max_seq_length=512 + max_new_tokens,
        load_in_4bit=True,
        dtype=torch.bfloat16,
    )

    # Qwen3.5 returns Processor (multimodal) — unwrap to plain tokenizer
    if not hasattr(tokenizer, "vocab_size") and hasattr(tokenizer, "tokenizer"):
        tokenizer = tokenizer.tokenizer

    FastLanguageModel.for_inference(model)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    problems = eval_problems[:max_samples] if max_samples > 0 else eval_problems

    # Prepare completions JSONL file for full response logging
    completions_file = None
    if completions_path:
        os.makedirs(os.path.dirname(completions_path) or ".", exist_ok=True)
        completions_file = open(completions_path, "w", encoding="utf-8")
        logger.info(f"Saving full completions to {completions_path}")

    results = defaultdict(lambda: {"total": 0, "correct": 0})
    diff_results = defaultdict(lambda: {"total": 0, "correct": 0})
    completions_log = []
    total_tokens = 0

    logger.info(f"Evaluating {len(problems)} problems (batch_size={batch_size})...")
    start_time = time.time()

    for batch_start in range(0, len(problems), batch_size):
        batch = problems[batch_start : batch_start + batch_size]

        # Format prompts
        prompts = []
        for p in batch:
            sys_prompt = (
                SYSTEM_PROMPT_MC if p.get("answer_type") == "mc_letter" else SYSTEM_PROMPT_CALC
            )
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": p["prompt"]},
            ]
            prompts.append(
                tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            )

        # Batch tokenize
        inputs = tokenizer(
            text=prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        ).to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,  # Greedy for reproducibility
                temperature=1.0,
            )

        # Decode and verify
        for i, p in enumerate(batch):
            prompt_len = inputs["input_ids"][i].ne(tokenizer.pad_token_id).sum().item()
            completion = tokenizer.decode(outputs[i][prompt_len:], skip_special_tokens=True)
            total_tokens += len(completion.split())

            domain = p.get("domain", "math")
            difficulty = p.get("difficulty", "medium")
            answer_type = p.get("answer_type", "numeric")
            truth = p.get("ground_truth", p.get("answer", ""))

            extracted = extract_answer(completion)
            correct = verify_answer(extracted, truth, domain, answer_type)

            results[domain]["total"] += 1
            results[domain]["correct"] += 1 if correct else 0
            diff_results[difficulty]["total"] += 1
            diff_results[difficulty]["correct"] += 1 if correct else 0

            entry = {
                "prompt": p["prompt"],
                "completion": completion,
                "domain": domain,
                "difficulty": difficulty,
                "answer_type": answer_type,
                "truth": truth,
                "extracted": extracted,
                "correct": correct,
                "source": p.get("source", ""),
            }
            completions_log.append(entry)

            if completions_file is not None:
                completions_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
                completions_file.flush()

        done = min(batch_start + batch_size, len(problems))
        if done % 20 == 0 or done == len(problems):
            elapsed = time.time() - start_time
            logger.info(f"  {done}/{len(problems)} ({elapsed:.0f}s)")

    elapsed = time.time() - start_time

    if completions_file is not None:
        completions_file.close()
        logger.info(
            f"Full completions saved to {completions_path} ({len(completions_log)} entries)"
        )

    # Compile results
    total_correct = sum(r["correct"] for r in results.values())
    total_count = sum(r["total"] for r in results.values())
    overall_accuracy = total_correct / total_count if total_count > 0 else 0

    return {
        "overall_accuracy": overall_accuracy,
        "total_problems": total_count,
        "total_correct": total_correct,
        "per_domain": {
            d: {
                "accuracy": r["correct"] / r["total"] if r["total"] > 0 else 0,
                "correct": r["correct"],
                "total": r["total"],
            }
            for d, r in results.items()
        },
        "per_difficulty": {
            d: {
                "accuracy": r["correct"] / r["total"] if r["total"] > 0 else 0,
                "correct": r["correct"],
                "total": r["total"],
            }
            for d, r in diff_results.items()
        },
        "avg_completion_tokens": total_tokens / total_count if total_count > 0 else 0,
        "elapsed_seconds": elapsed,
        "completions_path": completions_path,
        "sample_completions": completions_log[:20],
    }


def export_gguf_from_adapter(
    adapter_source: str,
    output_dir: str,
    quantization: str = "q4_k_m",
) -> str:
    """Export adapter to GGUF format. Returns path to GGUF file."""
    import torch
    from unsloth import FastLanguageModel

    logger.info(f"Loading adapter for GGUF export: {adapter_source}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=adapter_source,
        max_seq_length=2048,
        load_in_4bit=True,
        dtype=torch.bfloat16,
    )

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"model-{quantization}")

    logger.info(f"Exporting GGUF ({quantization}) to {output_path}...")
    model.save_pretrained_gguf(output_path, tokenizer, quantization_method=quantization)

    # Find the .gguf file
    for f in os.listdir(output_path):
        if f.endswith(".gguf"):
            gguf_path = os.path.join(output_path, f)
            size_mb = os.path.getsize(gguf_path) / (1024 * 1024)
            logger.info(f"GGUF exported: {gguf_path} ({size_mb:.0f} MB)")
            return gguf_path

    raise FileNotFoundError(f"No .gguf file found in {output_path}")


# ─── Local mode: Ollama evaluation ───────────────────────────


def _eval_single_problem(args):
    """Evaluate a single problem via Ollama (used by ThreadPoolExecutor)."""
    import requests

    idx, p, model_name, ollama_host, session = args
    domain = p.get("domain", "math")
    difficulty = p.get("difficulty", "medium")
    answer_type = p.get("answer_type", "numeric")
    truth = p.get("ground_truth", p.get("answer", ""))
    sys_prompt = SYSTEM_PROMPT_MC if answer_type == "mc_letter" else SYSTEM_PROMPT_CALC

    try:
        http = session if session is not None else requests
        resp = http.post(
            f"{ollama_host}/api/chat",
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": p["prompt"]},
                ],
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 8192,
                    "num_ctx": 16384,
                },
                "think": True,
            },
            timeout=360,
        )

        if resp.status_code != 200:
            return {"idx": idx, "error": True}

        msg = resp.json().get("message", {})
        # Ollama 0.7+: thinking models return reasoning in 'thinking' field
        thinking = msg.get("thinking", "")
        content = msg.get("content", "")
        if thinking:
            completion = f"<think>\n{thinking}\n</think>\n{content}"
        else:
            completion = content
        extracted = extract_answer(completion)
        correct = verify_answer(extracted, truth, domain, answer_type)
        fmt = check_format_compliance(completion)

        return {
            "idx": idx,
            "error": False,
            "domain": domain,
            "difficulty": difficulty,
            "correct": correct,
            "tokens": len(completion.split()),
            "format": fmt,
            "log": {
                "prompt": p["prompt"],
                "completion": completion,
                "domain": domain,
                "difficulty": difficulty,
                "answer_type": p.get("answer_type", "numeric"),
                "truth": truth,
                "extracted": extracted,
                "correct": correct,
                "has_boxed": fmt["has_boxed"],
                "has_thinking": fmt["has_thinking"],
                "source": p.get("source", ""),
            },
        }
    except Exception as e:
        return {"idx": idx, "error": True, "error_msg": str(e)}


def _preflight_check(model_name: str, ollama_host: str) -> bool:
    """Verify Ollama is running and the model is available."""
    import requests

    try:
        resp = requests.get(f"{ollama_host}/api/tags", timeout=10)
        if resp.status_code != 200:
            logger.error(f"Ollama not reachable at {ollama_host} (status {resp.status_code})")
            return False
        models = [m["name"] for m in resp.json().get("models", [])]
        # Match with or without ":latest" tag
        matched = any(model_name in m or m.startswith(model_name) for m in models)
        if not matched:
            logger.error(
                f"Model '{model_name}' not found in Ollama. Available: {', '.join(models[:10])}"
            )
            logger.error(f"Run: ollama pull {model_name}")
            return False
        logger.info(f"Preflight OK: Ollama running, model '{model_name}' available")
        return True
    except requests.ConnectionError:
        logger.error(f"Cannot connect to Ollama at {ollama_host}. Is it running? (ollama serve)")
        return False
    except Exception as e:
        logger.error(f"Preflight check failed: {e}")
        return False


def evaluate_local(
    model_name: str,
    eval_problems: List[Dict],
    ollama_host: str = "http://localhost:11434",
    max_samples: int = 0,
    num_workers: int = 2,
    completions_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate using Ollama API with parallel requests."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not _preflight_check(model_name, ollama_host):
        return {
            "overall_accuracy": 0,
            "total_problems": 0,
            "total_correct": 0,
            "errors": len(eval_problems),
            "per_domain": {},
            "per_difficulty": {},
            "avg_completion_tokens": 0,
            "elapsed_seconds": 0,
            "sample_completions": [],
            "error_message": f"Preflight failed: Ollama not running or model '{model_name}' not found",
        }

    problems = eval_problems[:max_samples] if max_samples > 0 else eval_problems

    # Prepare completions JSONL file for full response logging
    completions_file = None
    if completions_path:
        os.makedirs(os.path.dirname(completions_path) or ".", exist_ok=True)
        completions_file = open(completions_path, "w", encoding="utf-8")
        logger.info(f"Saving full completions to {completions_path}")

    results = defaultdict(lambda: {"total": 0, "correct": 0})
    diff_results = defaultdict(lambda: {"total": 0, "correct": 0})
    completions_log = []
    total_tokens = 0
    errors = 0
    done_count = 0
    fmt_counts = {"has_boxed": 0, "has_steps": 0, "has_thinking": 0, "total_length": 0, "count": 0}

    logger.info(
        f"Evaluating {len(problems)} problems via Ollama ({model_name}), {num_workers} workers..."
    )
    logger.info("  Options: num_predict=8192, num_ctx=16384, timeout=360s")
    start_time = time.time()

    import requests as _requests

    session = _requests.Session()
    # Connection pooling: reuse TCP connections to Ollama
    adapter = _requests.adapters.HTTPAdapter(
        pool_connections=num_workers,
        pool_maxsize=num_workers + 2,
    )
    session.mount("http://", adapter)

    tasks = [(i, p, model_name, ollama_host, session) for i, p in enumerate(problems)]

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(_eval_single_problem, t): t for t in tasks}

        for future in as_completed(futures):
            result = future.result()
            done_count += 1

            if result["error"]:
                errors += 1
                if errors <= 3:
                    logger.warning(
                        f"  Error on problem {result['idx']}: {result.get('error_msg', 'unknown')}"
                    )
                elif errors == 4:
                    logger.warning("  Suppressing further error messages...")
            else:
                domain = result["domain"]
                difficulty = result["difficulty"]
                results[domain]["total"] += 1
                results[domain]["correct"] += 1 if result["correct"] else 0
                diff_results[difficulty]["total"] += 1
                diff_results[difficulty]["correct"] += 1 if result["correct"] else 0
                total_tokens += result["tokens"]
                # Track format compliance
                fmt = result.get("format", {})
                fmt_counts["count"] += 1
                fmt_counts["has_boxed"] += 1 if fmt.get("has_boxed") else 0
                fmt_counts["has_steps"] += 1 if fmt.get("has_steps") else 0
                fmt_counts["has_thinking"] += 1 if fmt.get("has_thinking") else 0
                fmt_counts["total_length"] += fmt.get("response_length", 0)
                if len(completions_log) < 20:
                    completions_log.append(result["log"])

                # Write full completion to JSONL
                if completions_file is not None:
                    completions_file.write(json.dumps(result["log"], ensure_ascii=False) + "\n")
                    completions_file.flush()

                # Per-problem logging
                log = result["log"]
                mark = "+" if log["correct"] else "x"
                boxed = "[B]" if fmt.get("has_boxed") else "[ ]"
                think = "[T]" if fmt.get("has_thinking") else "   "
                logger.info(
                    f"  [{mark}] #{result['idx']:>4d} {domain:<10s} {difficulty:<6s} | "
                    f"truth={log['truth']:<12s} pred={log['extracted']:<12s} "
                    f"| {boxed} boxed {think} | {result['tokens']} tok"
                )
                if done_count <= 10:
                    preview = log.get("completion", "")[:150].replace("\n", " ")
                    logger.info(f"    >> {preview}")

            if done_count % 50 == 0 or done_count == len(problems):
                elapsed = time.time() - start_time
                rate = done_count / elapsed if elapsed > 0 else 0
                eta = (len(problems) - done_count) / rate if rate > 0 else 0
                logger.info(
                    f"  {done_count}/{len(problems)} ({elapsed:.0f}s, "
                    f"{rate:.1f} prob/s, ETA {eta:.0f}s, {errors} errors)"
                )

    elapsed = time.time() - start_time

    if completions_file is not None:
        completions_file.close()
        logger.info(f"Full completions saved to {completions_path} ({done_count - errors} entries)")

    total_correct = sum(r["correct"] for r in results.values())
    total_count = sum(r["total"] for r in results.values())
    overall_accuracy = total_correct / total_count if total_count > 0 else 0

    fc = fmt_counts["count"]
    format_compliance = {
        "boxed_pct": fmt_counts["has_boxed"] / fc if fc > 0 else 0,
        "steps_pct": fmt_counts["has_steps"] / fc if fc > 0 else 0,
        "thinking_pct": fmt_counts["has_thinking"] / fc if fc > 0 else 0,
        "avg_response_length": fmt_counts["total_length"] / fc if fc > 0 else 0,
        "total_evaluated": fc,
    }

    return {
        "overall_accuracy": overall_accuracy,
        "total_problems": total_count,
        "total_correct": total_correct,
        "errors": errors,
        "per_domain": {
            d: {
                "accuracy": r["correct"] / r["total"] if r["total"] > 0 else 0,
                "correct": r["correct"],
                "total": r["total"],
            }
            for d, r in results.items()
        },
        "per_difficulty": {
            d: {
                "accuracy": r["correct"] / r["total"] if r["total"] > 0 else 0,
                "correct": r["correct"],
                "total": r["total"],
            }
            for d, r in diff_results.items()
        },
        "format_compliance": format_compliance,
        "avg_completion_tokens": total_tokens / total_count if total_count > 0 else 0,
        "elapsed_seconds": elapsed,
        "completions_path": completions_path,
        "sample_completions": completions_log[:20],
    }


# ─── Report generation ───────────────────────────────────────


def save_report(
    eval_results: Dict,
    stage: str,
    mode: str,
    adapter_source: str,
    output_dir: str = "evaluation/reports",
):
    """Save evaluation report as JSON."""
    os.makedirs(output_dir, exist_ok=True)

    report = {
        "stage": stage,
        "mode": mode,
        "adapter_source": adapter_source,
        "evaluated_at": datetime.now().isoformat(),
        "results": eval_results,
    }

    filename = f"stage_{stage}_{mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Print summary
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Stage: {stage.upper()} | Mode: {mode}")
    logger.info(f"Overall accuracy: {eval_results['overall_accuracy']:.1%}")
    logger.info(f"{'=' * 60}")
    for domain, metrics in eval_results["per_domain"].items():
        logger.info(
            f"  {domain:12s}: {metrics['accuracy']:.1%} ({metrics['correct']}/{metrics['total']})"
        )

    # Print format compliance if available
    fc = eval_results.get("format_compliance")
    if fc:
        logger.info("\n  Format compliance:")
        logger.info(f"    \\boxed{{}} usage: {fc['boxed_pct']:.1%}")
        logger.info(f"    Step markers:   {fc['steps_pct']:.1%}")
        logger.info(f"    <think> tags:   {fc['thinking_pct']:.1%}")
        logger.info(f"    Avg response:   {fc['avg_response_length']:.0f} chars")

    logger.info(f"\nReport saved to {path}")

    return path


def compare_stages(reports_dir: str = "evaluation/reports"):
    """Compare results across all pipeline stages."""
    reports_path = Path(reports_dir)
    if not reports_path.exists():
        logger.error(f"Reports directory not found: {reports_dir}")
        return

    # Load latest report per stage
    stage_reports = {}
    for f in sorted(reports_path.glob("stage_*.json")):
        with open(f) as fh:
            report = json.load(fh)
        stage = report["stage"]
        stage_reports[stage] = report

    if not stage_reports:
        logger.info("No reports found.")
        return

    # Print comparison table
    logger.info(f"\n{'=' * 70}")
    logger.info("Pipeline Stage Comparison")
    logger.info(f"{'=' * 70}")
    header = f"{'Stage':>8s} | {'Overall':>8s} | {'Math':>6s} | {'Physics':>7s} | {'Chem':>6s} | {'Bio':>6s} | {'CS':>6s}"
    logger.info(header)
    logger.info("-" * 70)

    for stage in STAGES:
        if stage not in stage_reports:
            continue
        r = stage_reports[stage]["results"]
        domains = r.get("per_domain", {})
        row = (
            f"{stage:>8s} | "
            f"{r['overall_accuracy']:>7.1%} | "
            f"{domains.get('math', {}).get('accuracy', 0):>5.1%} | "
            f"{domains.get('physics', {}).get('accuracy', 0):>6.1%} | "
            f"{domains.get('chemistry', {}).get('accuracy', 0):>5.1%} | "
            f"{domains.get('biology', {}).get('accuracy', 0):>5.1%} | "
            f"{domains.get('cs', {}).get('accuracy', 0):>5.1%}"
        )
        logger.info(row)

    logger.info(f"{'=' * 70}")

    # Save comparison
    comparison_path = os.path.join(reports_dir, "stage_comparison.json")
    with open(comparison_path, "w", encoding="utf-8") as f:
        json.dump(stage_reports, f, indent=2, ensure_ascii=False)
    logger.info(f"Comparison saved to {comparison_path}")


# ─── CLI ──────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="MITS per-stage model evaluation")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Evaluate command
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate a model stage")
    eval_parser.add_argument("--mode", choices=["colab", "local"], required=True)
    eval_parser.add_argument("--adapter", help="HF repo or local path (colab mode)")
    eval_parser.add_argument("--model", help="Ollama model name (local mode)")
    eval_parser.add_argument("--stage", required=True, choices=STAGES)
    eval_parser.add_argument("--eval-data", default="training/data/eval_dataset.jsonl")
    eval_parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Use eval_benchmark.jsonl (alias for --eval-data training/data/eval_benchmark.jsonl)",
    )
    eval_parser.add_argument("--max-samples", type=int, default=0, help="Limit eval size (0=all)")
    eval_parser.add_argument(
        "--stratified",
        action="store_true",
        help="Use stratified sampling by (domain, difficulty) instead of first N",
    )
    eval_parser.add_argument("--ollama-host", default="http://localhost:11434")
    eval_parser.add_argument(
        "--workers", type=int, default=2, help="Parallel workers for local mode (2 for CPU)"
    )
    eval_parser.add_argument("--export-gguf", action="store_true", help="Also export GGUF (colab)")
    eval_parser.add_argument("--quantization", default="q4_k_m")
    eval_parser.add_argument("--reports-dir", default="evaluation/reports")
    eval_parser.add_argument(
        "--save-completions",
        action="store_true",
        help="Save ALL model completions to JSONL for later comparison",
    )
    eval_parser.add_argument(
        "--completions-dir",
        default="evaluation/completions",
        help="Directory for completion JSONL files",
    )
    eval_parser.add_argument(
        "--problem-file",
        default="",
        help="JSONL file with exact problems to evaluate (for paired comparison)",
    )

    # Compare command
    cmp_parser = subparsers.add_parser("compare", help="Compare all stages")
    cmp_parser.add_argument("--reports-dir", default="evaluation/reports")

    args = parser.parse_args()

    if args.command == "compare":
        compare_stages(args.reports_dir)
        return

    if args.command is None:
        parser.print_help()
        return

    # Resolve eval data path
    eval_data_path = args.eval_data
    if args.benchmark:
        eval_data_path = str(_PROJECT_ROOT / "training" / "data" / "eval_benchmark.jsonl")

    # Load eval dataset
    if args.problem_file:
        eval_problems = load_eval_dataset(args.problem_file)
        logger.info(f"Loaded {len(eval_problems)} problems from --problem-file {args.problem_file}")
    else:
        eval_problems = load_eval_dataset(eval_data_path)

        # Apply stratified sampling if requested
        if args.stratified and args.max_samples > 0:
            eval_problems = stratified_sample(eval_problems, args.max_samples)
            logger.info(f"Stratified sample: {len(eval_problems)} problems selected")

    # Auto-resolve adapter from stage name
    adapter_source = args.adapter or STAGE_HF_REPOS.get(args.stage, "")
    if args.mode == "colab" and not adapter_source:
        logger.error("--adapter is required for colab mode (or use a known stage name)")
        return

    # Build completions path: evaluation/completions/{stage}_{model}_{timestamp}.jsonl
    completions_path = None
    if args.save_completions:
        os.makedirs(args.completions_dir, exist_ok=True)
        model_tag = (args.model or adapter_source or args.stage).replace("/", "_").replace(":", "_")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        completions_path = os.path.join(
            args.completions_dir, f"{args.stage}_{model_tag}_{ts}.jsonl"
        )

    if args.mode == "colab":
        results = evaluate_colab(
            adapter_source=adapter_source,
            eval_problems=eval_problems,
            max_samples=args.max_samples,
            completions_path=completions_path,
        )

        report_path = save_report(results, args.stage, "colab", adapter_source, args.reports_dir)

        if args.export_gguf:
            gguf_dir = os.path.join("evaluation", "gguf", args.stage)
            gguf_path = export_gguf_from_adapter(adapter_source, gguf_dir, args.quantization)
            logger.info(f"GGUF exported: {gguf_path}")

    elif args.mode == "local":
        model_name = args.model
        if not model_name:
            logger.error("--model is required for local mode")
            return

        results = evaluate_local(
            model_name=model_name,
            eval_problems=eval_problems,
            ollama_host=args.ollama_host,
            max_samples=args.max_samples,
            num_workers=args.workers,
            completions_path=completions_path,
        )

        report_path = save_report(results, args.stage, "local", model_name, args.reports_dir)


if __name__ == "__main__":
    main()
