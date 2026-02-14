#!/usr/bin/env python3
"""
Multi-domain benchmark runner for comparing pruned vs baseline models.

Supports: GSM8K (math), HumanEval (code), SciQ (science), MMLU-STEM (multi-domain)

Usage:
    python evaluation/benchmark_models.py --model glm-stem-pruned --samples 50
    python evaluation/benchmark_models.py --model glm-stem-pruned --compare glm-4.7-flash
"""

import argparse
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

import ollama

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result from a single benchmark evaluation."""
    model_name: str
    benchmark_name: str
    domain: str
    score: float
    baseline_score: float
    retention_rate: float
    samples_tested: int
    avg_latency_ms: float
    timestamp: str


def query_model(model_name: str, prompt: str, max_tokens: int = 512) -> Tuple[str, float]:
    """
    Query an Ollama model and return response with latency.

    Returns:
        Tuple of (response_text, latency_ms)
    """
    start = time.time()
    try:
        response = ollama.generate(
            model=model_name,
            prompt=prompt,
            options={"num_predict": max_tokens, "temperature": 0.0}
        )
        latency = (time.time() - start) * 1000
        return response.get("response", ""), latency
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return "", 0


# =============================================================================
# GSM8K Evaluation (Math Reasoning)
# =============================================================================

def load_gsm8k_samples(samples_dir: str, num_samples: int = 50) -> List[Dict]:
    """Load GSM8K-style math problems."""
    samples_file = Path(samples_dir) / "gsm8k_samples.json"

    if samples_file.exists():
        with open(samples_file, 'r') as f:
            samples = json.load(f)
        return samples[:num_samples]

    # Generate sample problems if file doesn't exist
    logger.warning("GSM8K samples not found, using built-in samples")
    return [
        {"question": "If Sarah has 5 apples and buys 3 more, then gives 2 to her friend, how many apples does she have?", "answer": "6"},
        {"question": "A train travels 60 miles per hour. How far will it travel in 2.5 hours?", "answer": "150"},
        {"question": "If a rectangle has length 8 and width 5, what is its area?", "answer": "40"},
        {"question": "John has $50. He spends $12 on lunch and $18 on a book. How much money does he have left?", "answer": "20"},
        {"question": "If 3x + 7 = 22, what is x?", "answer": "5"},
    ][:num_samples]


def evaluate_gsm8k(model_name: str, samples: List[Dict]) -> Tuple[float, float]:
    """
    Evaluate model on GSM8K-style math problems.

    Returns:
        Tuple of (accuracy, avg_latency_ms)
    """
    correct = 0
    total_latency = 0

    for sample in samples:
        prompt = f"""Solve this math problem step by step. Give your final numerical answer at the end.

Problem: {sample['question']}

Solution:"""

        response, latency = query_model(model_name, prompt)
        total_latency += latency

        # Extract final number from response
        numbers = re.findall(r'\b\d+\.?\d*\b', response)
        if numbers:
            predicted = numbers[-1]  # Take last number as answer
            if str(sample['answer']) in predicted or predicted in str(sample['answer']):
                correct += 1

    accuracy = correct / len(samples) if samples else 0
    avg_latency = total_latency / len(samples) if samples else 0

    return accuracy, avg_latency


# =============================================================================
# HumanEval Evaluation (Code Generation)
# =============================================================================

def load_humaneval_samples(samples_dir: str, num_samples: int = 50) -> List[Dict]:
    """Load HumanEval-style coding problems."""
    samples_file = Path(samples_dir) / "humaneval_samples.json"

    if samples_file.exists():
        with open(samples_file, 'r') as f:
            samples = json.load(f)
        return samples[:num_samples]

    logger.warning("HumanEval samples not found, using built-in samples")
    return [
        {"prompt": "def is_prime(n):", "test": "assert is_prime(7) == True and is_prime(4) == False"},
        {"prompt": "def factorial(n):", "test": "assert factorial(5) == 120"},
        {"prompt": "def reverse_string(s):", "test": "assert reverse_string('hello') == 'olleh'"},
        {"prompt": "def fibonacci(n):", "test": "assert fibonacci(7) == 13"},
        {"prompt": "def is_palindrome(s):", "test": "assert is_palindrome('racecar') == True"},
    ][:num_samples]


def evaluate_humaneval(model_name: str, samples: List[Dict]) -> Tuple[float, float]:
    """
    Evaluate model on HumanEval-style coding problems.

    Returns:
        Tuple of (pass_rate, avg_latency_ms)
    """
    passed = 0
    total_latency = 0

    for sample in samples:
        prompt = f"""Complete this Python function:

{sample['prompt']}

Write only the function body, no explanation."""

        response, latency = query_model(model_name, prompt, max_tokens=256)
        total_latency += latency

        # Try to execute the code
        try:
            # Extract code from response
            code = sample['prompt'] + "\n" + response.split("```")[0].strip()
            if "def " in response:
                # If response includes full function, use it
                match = re.search(r'def \w+\([^)]*\):.*?(?=\ndef |\Z)', response, re.DOTALL)
                if match:
                    code = match.group(0)

            # Execute test
            exec(code + "\n" + sample['test'], {})
            passed += 1
        except Exception:
            pass  # Test failed

    pass_rate = passed / len(samples) if samples else 0
    avg_latency = total_latency / len(samples) if samples else 0

    return pass_rate, avg_latency


# =============================================================================
# SciQ Evaluation (Science Knowledge)
# =============================================================================

def load_sciq_samples(samples_dir: str, num_samples: int = 50) -> List[Dict]:
    """Load SciQ-style science questions."""
    samples_file = Path(samples_dir) / "sciq_samples.json"

    if samples_file.exists():
        with open(samples_file, 'r') as f:
            samples = json.load(f)
        return samples[:num_samples]

    logger.warning("SciQ samples not found, using built-in samples")
    return [
        {"question": "What is the chemical formula for water?", "answer": "H2O"},
        {"question": "What organelle is responsible for cellular respiration?", "answer": "mitochondria"},
        {"question": "What is Newton's second law of motion?", "answer": "F=ma"},
        {"question": "What type of bond forms between sodium and chlorine?", "answer": "ionic"},
        {"question": "What is the powerhouse of the cell?", "answer": "mitochondria"},
    ][:num_samples]


def evaluate_sciq(model_name: str, samples: List[Dict]) -> Tuple[float, float]:
    """
    Evaluate model on SciQ-style science questions.

    Returns:
        Tuple of (accuracy, avg_latency_ms)
    """
    correct = 0
    total_latency = 0

    for sample in samples:
        prompt = f"""Answer this science question concisely.

Question: {sample['question']}

Answer:"""

        response, latency = query_model(model_name, prompt, max_tokens=100)
        total_latency += latency

        # Check if answer is in response (case insensitive)
        if sample['answer'].lower() in response.lower():
            correct += 1

    accuracy = correct / len(samples) if samples else 0
    avg_latency = total_latency / len(samples) if samples else 0

    return accuracy, avg_latency


# =============================================================================
# MMLU-STEM Evaluation (Multi-domain)
# =============================================================================

def load_mmlu_samples(samples_dir: str, num_samples: int = 50) -> List[Dict]:
    """Load MMLU-STEM style multiple choice questions."""
    samples_file = Path(samples_dir) / "mmlu_stem_samples.json"

    if samples_file.exists():
        with open(samples_file, 'r') as f:
            samples = json.load(f)
        return samples[:num_samples]

    logger.warning("MMLU-STEM samples not found, using built-in samples")
    return [
        {"question": "What is the derivative of x^2?", "choices": ["x", "2x", "x^2", "2"], "answer": "B"},
        {"question": "Which planet is known as the Red Planet?", "choices": ["Venus", "Mars", "Jupiter", "Saturn"], "answer": "B"},
        {"question": "What is the pH of a neutral solution?", "choices": ["0", "7", "14", "1"], "answer": "B"},
        {"question": "What is the time complexity of binary search?", "choices": ["O(n)", "O(log n)", "O(n^2)", "O(1)"], "answer": "B"},
        {"question": "What is the unit of electrical resistance?", "choices": ["Volt", "Ampere", "Ohm", "Watt"], "answer": "C"},
    ][:num_samples]


def evaluate_mmlu(model_name: str, samples: List[Dict]) -> Tuple[float, float]:
    """
    Evaluate model on MMLU-STEM multiple choice questions.

    Returns:
        Tuple of (accuracy, avg_latency_ms)
    """
    correct = 0
    total_latency = 0

    for sample in samples:
        choices_str = "\n".join(f"{chr(65+i)}. {c}" for i, c in enumerate(sample['choices']))
        prompt = f"""Answer this multiple choice question. Reply with only the letter (A, B, C, or D).

Question: {sample['question']}

{choices_str}

Answer:"""

        response, latency = query_model(model_name, prompt, max_tokens=10)
        total_latency += latency

        # Extract letter from response
        match = re.search(r'\b([ABCD])\b', response.upper())
        if match and match.group(1) == sample['answer']:
            correct += 1

    accuracy = correct / len(samples) if samples else 0
    avg_latency = total_latency / len(samples) if samples else 0

    return accuracy, avg_latency


# =============================================================================
# Main Benchmark Runner
# =============================================================================

BENCHMARKS = {
    "gsm8k": {"loader": load_gsm8k_samples, "evaluator": evaluate_gsm8k, "domain": "math"},
    "humaneval": {"loader": load_humaneval_samples, "evaluator": evaluate_humaneval, "domain": "code"},
    "sciq": {"loader": load_sciq_samples, "evaluator": evaluate_sciq, "domain": "science"},
    "mmlu-stem": {"loader": load_mmlu_samples, "evaluator": evaluate_mmlu, "domain": "multi"},
}


def run_benchmarks(
    model_name: str,
    benchmarks: List[str],
    samples_dir: str,
    num_samples: int = 50,
    baseline_model: Optional[str] = None
) -> List[BenchmarkResult]:
    """
    Run benchmarks on a model, optionally comparing to baseline.

    Returns:
        List of BenchmarkResult objects
    """
    results = []
    baseline_scores = {}

    # Run baseline first if specified
    if baseline_model:
        logger.info(f"Running baseline model: {baseline_model}")
        for bench_name in benchmarks:
            if bench_name not in BENCHMARKS:
                logger.warning(f"Unknown benchmark: {bench_name}")
                continue

            bench = BENCHMARKS[bench_name]
            samples = bench["loader"](samples_dir, num_samples)
            score, latency = bench["evaluator"](baseline_model, samples)
            baseline_scores[bench_name] = score
            logger.info(f"  {bench_name}: {score:.2%}")

    # Run target model
    logger.info(f"Running target model: {model_name}")
    for bench_name in benchmarks:
        if bench_name not in BENCHMARKS:
            continue

        bench = BENCHMARKS[bench_name]
        samples = bench["loader"](samples_dir, num_samples)

        logger.info(f"  Evaluating {bench_name}...")
        score, latency = bench["evaluator"](model_name, samples)

        baseline = baseline_scores.get(bench_name, score)
        retention = score / baseline if baseline > 0 else 1.0

        result = BenchmarkResult(
            model_name=model_name,
            benchmark_name=bench_name,
            domain=bench["domain"],
            score=score,
            baseline_score=baseline,
            retention_rate=retention,
            samples_tested=len(samples),
            avg_latency_ms=latency,
            timestamp=datetime.now().isoformat()
        )
        results.append(result)

        status = "[OK]" if retention >= 0.95 else "[!]"
        logger.info(f"    Score: {score:.2%}, Retention: {retention:.2%} {status}")

    return results


def print_results_table(results: List[BenchmarkResult]):
    """Print results as formatted table."""
    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS")
    print("=" * 80)
    print(f"{'Benchmark':<15} {'Domain':<10} {'Score':<10} {'Baseline':<10} {'Retention':<12} {'Status':<8}")
    print("-" * 80)

    all_pass = True
    for r in results:
        status = "[OK]" if r.retention_rate >= 0.95 else "[FAIL]"
        if r.retention_rate < 0.95:
            all_pass = False

        print(f"{r.benchmark_name:<15} {r.domain:<10} {r.score:>8.1%} {r.baseline_score:>9.1%} {r.retention_rate:>10.1%} {status:<8}")

    print("-" * 80)
    print(f"Overall: {'PASS - All domains >= 95% retention' if all_pass else 'FAIL - Some domains below 95%'}")
    print("=" * 80 + "\n")


def save_results(results: List[BenchmarkResult], output_path: str):
    """Save results to JSON file."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "results": [asdict(r) for r in results]
    }

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    logger.info(f"Results saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Benchmark models on STEM tasks")
    parser.add_argument("--model", "-m", required=True, help="Model to evaluate")
    parser.add_argument("--compare", "-c", help="Baseline model for comparison")
    parser.add_argument("--benchmarks", "-b", default="gsm8k,humaneval,sciq,mmlu-stem",
                        help="Comma-separated list of benchmarks")
    parser.add_argument("--samples", "-s", type=int, default=50, help="Samples per benchmark")
    parser.add_argument("--samples-dir", default="evaluation/data/validation_samples",
                        help="Directory containing sample files")
    parser.add_argument("--output", "-o", help="Output JSON file for results")

    args = parser.parse_args()

    benchmarks = [b.strip() for b in args.benchmarks.split(",")]

    logger.info(f"Starting benchmark evaluation")
    logger.info(f"  Model: {args.model}")
    logger.info(f"  Baseline: {args.compare or 'None'}")
    logger.info(f"  Benchmarks: {benchmarks}")
    logger.info(f"  Samples: {args.samples}")

    results = run_benchmarks(
        model_name=args.model,
        benchmarks=benchmarks,
        samples_dir=args.samples_dir,
        num_samples=args.samples,
        baseline_model=args.compare
    )

    print_results_table(results)

    if args.output:
        save_results(results, args.output)

    # Exit with error if any benchmark failed
    all_pass = all(r.retention_rate >= 0.95 for r in results)
    return 0 if all_pass else 1


if __name__ == "__main__":
    exit(main())
