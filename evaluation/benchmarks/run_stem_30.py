"""
STEM-30 Benchmark Runner

Automated scoring script for the STEM-30 benchmark. Sends 30 questions
(6 per domain: math, physics, chemistry, cs, biology) to a model via
Ollama API, verifies answers, and reports per-domain scores.

Metrics:
- Overall score (X/30)
- Per-domain scores (X/6 for each: math, physics, chemistry, cs, biology)
- Calc vs conceptual breakdown
- Socratic score (guiding vs telling analysis)
- Pass/fail against quality gates: overall > 73%, each domain > 50%

Usage:
    python -m evaluation.benchmarks.run_stem_30
    python -m evaluation.benchmarks.run_stem_30 --model qwen3:4b --no-thinking
    python -m evaluation.benchmarks.run_stem_30 --model mits-tutor-qwen3-4b \
        --output evaluation/reports/stem_30_results.json
"""

import json
import logging
import argparse
import time
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

import requests

from training.scripts.verify_answers import verify, extract_answer
from evaluation.benchmarks.socratic_score import analyze_turn

logger = logging.getLogger(__name__)

# Quality gates from spec (Phase 3 targets)
OVERALL_GATE = 0.73  # > 73%
DOMAIN_GATE = 0.50   # each domain > 50%
DOMAINS = ["math", "physics", "chemistry", "cs", "biology"]
QUESTIONS_PER_DOMAIN = 6


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class QuestionResult:
    """Result of a single benchmark question."""
    question_id: int
    domain: str
    question_type: str  # calc, conceptual, code, mc
    difficulty: str
    question: str
    ground_truth: str
    model_response: str
    extracted_answer: str
    correct: bool
    confidence: float
    verification_method: str
    verification_details: str
    socratic_analysis: Dict[str, Any] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    error: Optional[str] = None


@dataclass
class DomainScore:
    """Aggregated score for a single domain."""
    domain: str
    total: int = 0
    correct: int = 0
    calc_total: int = 0
    calc_correct: int = 0
    conceptual_total: int = 0
    conceptual_correct: int = 0
    score: float = 0.0
    passed_gate: bool = False


@dataclass
class BenchmarkResult:
    """Full STEM-30 benchmark result."""
    model: str = ""
    ollama_host: str = ""
    thinking_enabled: bool = True
    timestamp: str = ""
    total_questions: int = 0
    total_correct: int = 0
    overall_score: float = 0.0
    calc_total: int = 0
    calc_correct: int = 0
    calc_score: float = 0.0
    conceptual_total: int = 0
    conceptual_correct: int = 0
    conceptual_score: float = 0.0
    avg_socratic_question_count: float = 0.0
    avg_socratic_telling_count: float = 0.0
    overall_gate_passed: bool = False
    all_domain_gates_passed: bool = False
    all_gates_passed: bool = False
    domain_scores: List[Dict[str, Any]] = field(default_factory=list)
    question_results: List[Dict[str, Any]] = field(default_factory=list)
    total_elapsed_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Ollama API interaction
# ---------------------------------------------------------------------------

def query_ollama(
    prompt: str,
    model: str,
    host: str,
    thinking: bool = True,
    timeout: int = 120,
) -> Dict[str, Any]:
    """Send a prompt to Ollama and return the response.

    Args:
        prompt: The question to send.
        model: Ollama model name.
        host: Ollama API base URL.
        thinking: Whether to enable thinking/reasoning mode.
        timeout: Request timeout in seconds.

    Returns:
        Dict with 'response' text and 'elapsed_seconds'.
    """
    url = f"{host}/api/generate"

    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 2048,
        },
    }

    if thinking:
        payload["options"]["num_predict"] = 4096

    start = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        elapsed = time.perf_counter() - start
        data = resp.json()
        return {
            "response": data.get("response", ""),
            "elapsed_seconds": elapsed,
        }
    except requests.exceptions.Timeout:
        elapsed = time.perf_counter() - start
        return {
            "response": "",
            "elapsed_seconds": elapsed,
            "error": f"Timeout after {timeout}s",
        }
    except requests.exceptions.ConnectionError as e:
        elapsed = time.perf_counter() - start
        return {
            "response": "",
            "elapsed_seconds": elapsed,
            "error": f"Connection error: {e}",
        }
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {
            "response": "",
            "elapsed_seconds": elapsed,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Load benchmark questions
# ---------------------------------------------------------------------------

def load_questions(path: Path) -> List[Dict[str, Any]]:
    """Load STEM-30 questions from JSON file.

    Expected format: list of objects with fields:
        - id, domain, type, difficulty, question, ground_truth
        - Optional: test_cases, rubric, reference, verification_method
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        # Support {"questions": [...]} wrapper
        questions = data.get("questions", data.get("items", []))
    elif isinstance(data, list):
        questions = data
    else:
        raise ValueError(f"Unexpected format in {path}: expected list or dict")

    if not questions:
        raise ValueError(f"No questions found in {path}")

    logger.info(f"Loaded {len(questions)} questions from {path}")
    return questions


# ---------------------------------------------------------------------------
# Evaluate a single question
# ---------------------------------------------------------------------------

def evaluate_question(
    question: Dict[str, Any],
    model: str,
    host: str,
    thinking: bool,
) -> QuestionResult:
    """Evaluate a single benchmark question.

    Sends the question to the model, extracts the answer, verifies it,
    and analyzes the response for Socratic indicators.
    """
    q_id = question.get("id", 0)
    domain = question.get("domain", "math")
    q_type = question.get("type", "calc")
    difficulty = question.get("difficulty", "medium")
    prompt = question["question"]
    ground_truth = question.get("ground_truth", question.get("answer", ""))

    logger.info(f"  Q{q_id} [{domain}/{q_type}]: {prompt[:80]}...")

    # Query the model
    ollama_result = query_ollama(prompt, model, host, thinking=thinking)

    model_response = ollama_result["response"]
    elapsed = ollama_result["elapsed_seconds"]
    error = ollama_result.get("error")

    if error:
        logger.warning(f"  Q{q_id}: Error — {error}")
        return QuestionResult(
            question_id=q_id,
            domain=domain,
            question_type=q_type,
            difficulty=difficulty,
            question=prompt,
            ground_truth=ground_truth,
            model_response=model_response,
            extracted_answer="",
            correct=False,
            confidence=0.0,
            verification_method="error",
            verification_details="",
            elapsed_seconds=elapsed,
            error=error,
        )

    # Extract the answer from model response
    extracted = extract_answer(model_response)

    # Verify using domain-aware verification
    verification = verify(
        answer=extracted,
        truth=ground_truth,
        domain=domain,
        question_type=q_type,
        test_cases=question.get("test_cases"),
        rubric=question.get("rubric"),
        reference=question.get("reference", ground_truth),
    )

    # Socratic analysis on the model response
    socratic = analyze_turn(model_response)

    status = "CORRECT" if verification.correct else "WRONG"
    logger.info(
        f"  Q{q_id}: {status} (extracted={extracted!r}, "
        f"truth={ground_truth!r}, method={verification.method})"
    )

    return QuestionResult(
        question_id=q_id,
        domain=domain,
        question_type=q_type,
        difficulty=difficulty,
        question=prompt,
        ground_truth=ground_truth,
        model_response=model_response,
        extracted_answer=extracted,
        correct=verification.correct,
        confidence=verification.confidence,
        verification_method=verification.method,
        verification_details=verification.details,
        socratic_analysis=socratic,
        elapsed_seconds=elapsed,
    )


# ---------------------------------------------------------------------------
# Aggregate results
# ---------------------------------------------------------------------------

def aggregate_results(
    question_results: List[QuestionResult],
    model: str,
    host: str,
    thinking: bool,
) -> BenchmarkResult:
    """Aggregate individual question results into the benchmark result."""
    result = BenchmarkResult(
        model=model,
        ollama_host=host,
        thinking_enabled=thinking,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_questions=len(question_results),
    )

    # Per-domain accumulators
    domain_data: Dict[str, DomainScore] = {
        d: DomainScore(domain=d) for d in DOMAINS
    }

    socratic_question_counts: List[int] = []
    socratic_telling_counts: List[int] = []

    for qr in question_results:
        # Overall
        if qr.correct:
            result.total_correct += 1

        # Per-domain
        ds = domain_data.get(qr.domain)
        if ds is None:
            # Unknown domain; create an entry for it
            ds = DomainScore(domain=qr.domain)
            domain_data[qr.domain] = ds

        ds.total += 1
        if qr.correct:
            ds.correct += 1

        # Calc vs conceptual
        if qr.question_type in ("calc", "code", "mc"):
            ds.calc_total += 1
            result.calc_total += 1
            if qr.correct:
                ds.calc_correct += 1
                result.calc_correct += 1
        elif qr.question_type == "conceptual":
            ds.conceptual_total += 1
            result.conceptual_total += 1
            if qr.correct:
                ds.conceptual_correct += 1
                result.conceptual_correct += 1

        # Socratic indicators
        if qr.socratic_analysis:
            socratic_question_counts.append(
                qr.socratic_analysis.get("question_count", 0)
            )
            socratic_telling_counts.append(
                qr.socratic_analysis.get("telling_count", 0)
            )

        result.total_elapsed_seconds += qr.elapsed_seconds
        result.question_results.append(asdict(qr))

    # Overall score
    if result.total_questions > 0:
        result.overall_score = result.total_correct / result.total_questions

    # Calc / conceptual scores
    if result.calc_total > 0:
        result.calc_score = result.calc_correct / result.calc_total
    if result.conceptual_total > 0:
        result.conceptual_score = result.conceptual_correct / result.conceptual_total

    # Per-domain scores and gate checks
    all_domains_passed = True
    for domain in DOMAINS:
        ds = domain_data.get(domain)
        if ds is None or ds.total == 0:
            continue
        ds.score = ds.correct / ds.total
        ds.passed_gate = ds.score > DOMAIN_GATE
        if not ds.passed_gate:
            all_domains_passed = False
        result.domain_scores.append(asdict(ds))

    # Also include any extra domains not in DOMAINS
    for domain, ds in domain_data.items():
        if domain not in DOMAINS and ds.total > 0:
            ds.score = ds.correct / ds.total
            ds.passed_gate = ds.score > DOMAIN_GATE
            result.domain_scores.append(asdict(ds))

    # Socratic averages
    if socratic_question_counts:
        result.avg_socratic_question_count = (
            sum(socratic_question_counts) / len(socratic_question_counts)
        )
    if socratic_telling_counts:
        result.avg_socratic_telling_count = (
            sum(socratic_telling_counts) / len(socratic_telling_counts)
        )

    # Gate checks
    result.overall_gate_passed = result.overall_score > OVERALL_GATE
    result.all_domain_gates_passed = all_domains_passed
    result.all_gates_passed = (
        result.overall_gate_passed and result.all_domain_gates_passed
    )

    return result


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def print_report(result: BenchmarkResult) -> None:
    """Print a human-readable report to stdout."""
    print()
    print("=" * 60)
    print("  STEM-30 Benchmark Results")
    print("=" * 60)
    print(f"  Model:     {result.model}")
    print(f"  Host:      {result.ollama_host}")
    print(f"  Thinking:  {'enabled' if result.thinking_enabled else 'disabled'}")
    print(f"  Timestamp: {result.timestamp}")
    print(f"  Duration:  {result.total_elapsed_seconds:.1f}s")
    print()

    # Overall score
    print(f"  Overall Score: {result.total_correct}/{result.total_questions} "
          f"({result.overall_score:.1%})")
    print()

    # Per-domain scores
    print("  Per-Domain Scores:")
    print("  " + "-" * 56)
    print(f"  {'Domain':<12} {'Score':>8} {'Calc':>10} {'Concept':>10} {'Gate':>8}")
    print("  " + "-" * 56)
    for ds in result.domain_scores:
        calc_str = (
            f"{ds['calc_correct']}/{ds['calc_total']}"
            if ds["calc_total"] > 0
            else "n/a"
        )
        conc_str = (
            f"{ds['conceptual_correct']}/{ds['conceptual_total']}"
            if ds["conceptual_total"] > 0
            else "n/a"
        )
        gate_str = "PASS" if ds["passed_gate"] else "FAIL"
        print(
            f"  {ds['domain']:<12} "
            f"{ds['correct']}/{ds['total']:>2} ({ds['score']:.0%})"
            f"  {calc_str:>6}"
            f"  {conc_str:>6}"
            f"     {gate_str}"
        )
    print("  " + "-" * 56)
    print()

    # Calc vs conceptual breakdown
    print("  Type Breakdown:")
    if result.calc_total > 0:
        print(f"    Calc/Code/MC:  {result.calc_correct}/{result.calc_total} "
              f"({result.calc_score:.1%})")
    if result.conceptual_total > 0:
        print(f"    Conceptual:    {result.conceptual_correct}/{result.conceptual_total} "
              f"({result.conceptual_score:.1%})")
    print()

    # Socratic score
    print("  Socratic Indicators (avg per response):")
    print(f"    Question patterns: {result.avg_socratic_question_count:.2f}")
    print(f"    Telling patterns:  {result.avg_socratic_telling_count:.2f}")
    print()

    # Quality gates
    print("  Quality Gates:")
    overall_str = "PASS" if result.overall_gate_passed else "FAIL"
    domain_str = "PASS" if result.all_domain_gates_passed else "FAIL"
    final_str = "PASS" if result.all_gates_passed else "FAIL"
    print(f"    Overall > {OVERALL_GATE:.0%}:      {overall_str} ({result.overall_score:.1%})")
    print(f"    Each domain > {DOMAIN_GATE:.0%}: {domain_str}")
    print(f"    All gates:           {final_str}")
    print()
    print("=" * 60)


def save_results(result: BenchmarkResult, output_path: Path) -> None:
    """Save benchmark results to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(result), f, indent=2, ensure_ascii=False)
    logger.info(f"Results saved to {output_path}")


# ---------------------------------------------------------------------------
# Main benchmark runner
# ---------------------------------------------------------------------------

def run_benchmark(
    questions_path: Path,
    model: str,
    host: str,
    thinking: bool,
) -> BenchmarkResult:
    """Run the full STEM-30 benchmark.

    Args:
        questions_path: Path to stem_30.json.
        model: Ollama model name.
        host: Ollama API base URL.
        thinking: Whether to enable thinking mode.

    Returns:
        Populated BenchmarkResult with all scores.
    """
    questions = load_questions(questions_path)

    logger.info(
        f"Running STEM-30 benchmark: model={model}, "
        f"questions={len(questions)}, thinking={thinking}"
    )

    question_results: List[QuestionResult] = []
    for i, q in enumerate(questions):
        logger.info(f"Question {i + 1}/{len(questions)}")
        qr = evaluate_question(q, model, host, thinking)
        question_results.append(qr)

    result = aggregate_results(question_results, model, host, thinking)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="STEM-30 Benchmark — automated scoring for 5-domain STEM evaluation",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="mits-tutor-qwen3-4b",
        help="Ollama model name (default: mits-tutor-qwen3-4b)",
    )
    parser.add_argument(
        "--ollama-host",
        type=str,
        default="http://localhost:11434",
        help="Ollama API base URL (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="evaluation/reports/stem_30_results.json",
        help="Output path for JSON results (default: evaluation/reports/stem_30_results.json)",
    )
    parser.add_argument(
        "--questions",
        type=str,
        default="evaluation/benchmarks/stem_30.json",
        help="Path to benchmark questions JSON (default: evaluation/benchmarks/stem_30.json)",
    )
    parser.add_argument(
        "--thinking",
        action="store_true",
        default=True,
        dest="thinking",
        help="Enable thinking/reasoning mode (default: True)",
    )
    parser.add_argument(
        "--no-thinking",
        action="store_false",
        dest="thinking",
        help="Disable thinking/reasoning mode",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable debug logging",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    questions_path = Path(args.questions)
    if not questions_path.exists():
        logger.error(f"Questions file not found: {questions_path}")
        sys.exit(1)

    output_path = Path(args.output)

    # Run the benchmark
    result = run_benchmark(
        questions_path=questions_path,
        model=args.model,
        host=args.ollama_host,
        thinking=args.thinking,
    )

    # Print report
    print_report(result)

    # Save results
    save_results(result, output_path)

    print(f"Results saved to {output_path}")

    # Exit with non-zero code if gates failed
    if not result.all_gates_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
