"""
Unified Benchmark Runner (013-comprehensive-improvements)

Runs ML-focused benchmarks and outputs structured JSON + markdown report.
Complements the existing run_evaluation.py (which handles tutoring quality).

Usage:
    python -m evaluation.run_benchmarks --benchmark all
    python -m evaluation.run_benchmarks --benchmark knowledge_prediction affect_accuracy
"""

import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from dataclasses import asdict

logger = logging.getLogger(__name__)

AVAILABLE_BENCHMARKS = [
    "socratic_score",
    "error_recovery",
    "latency",
    "knowledge_prediction",
    "affect_accuracy",
    "base_vs_finetuned",
]


def run_socratic_score(args) -> Dict[str, Any]:
    dialogs_path = Path(args.dialogs or "data/training/synthetic_dialogs.jsonl")
    if not dialogs_path.exists():
        return {"error": f"Dialogs not found: {dialogs_path}"}
    from evaluation.benchmarks.socratic_score import evaluate_dialogs
    return asdict(evaluate_dialogs(dialogs_path))


def run_error_recovery(args) -> Dict[str, Any]:
    dialogs_path = Path(args.dialogs or "data/training/synthetic_dialogs.jsonl")
    if not dialogs_path.exists():
        return {"error": f"Dialogs not found: {dialogs_path}"}
    from evaluation.benchmarks.error_recovery import evaluate_dialogs
    return asdict(evaluate_dialogs(dialogs_path))


def run_latency(args) -> Dict[str, Any]:
    from evaluation.benchmarks.latency_benchmark import run_benchmark
    return asdict(run_benchmark(
        args.backend_url or "http://localhost:8000",
        args.requests_per_mode or 10,
    ))


def run_knowledge_prediction(args) -> Dict[str, Any]:
    test_path = Path(args.test_data or "data/training/assistments_test.pt")
    if not test_path.exists():
        return {"error": f"Test data not found: {test_path}"}
    from evaluation.benchmarks.knowledge_prediction import (
        load_test_sequences, evaluate_bkt, evaluate_dkt,
    )
    sequences = load_test_sequences(test_path)
    if not sequences:
        return {"error": "No test sequences loaded"}
    bkt = evaluate_bkt(sequences)
    dkt = evaluate_dkt(sequences, args.dkt_weights or "data/models/dkt_pretrained.pt")
    return {"bkt": asdict(bkt), "dkt": asdict(dkt), "improvement_auc": dkt.auc - bkt.auc}


def run_affect_accuracy(args) -> Dict[str, Any]:
    test_path = Path(args.affect_data or "data/training/affect_labels.jsonl")
    if not test_path.exists():
        return {"error": f"Affect data not found: {test_path}"}
    from evaluation.benchmarks.affect_accuracy import evaluate_rules, evaluate_ml
    texts, labels = [], []
    with open(test_path, "r", encoding="utf-8") as f:
        for line in f:
            sample = json.loads(line)
            if sample.get("label"):
                texts.append(sample["text"])
                labels.append(sample["label"])
    rules = evaluate_rules(texts, labels)
    ml = evaluate_ml(texts, labels, args.ml_model or "data/models/rubert_affect")
    return {"rules": asdict(rules), "ml": asdict(ml), "improvement_f1": ml.macro_f1 - rules.macro_f1}


def run_base_vs_finetuned(args) -> Dict[str, Any]:
    prompts_path = Path(args.test_prompts or "data/training/test_prompts.jsonl")
    if not prompts_path.exists():
        return {"error": f"Test prompts not found: {prompts_path}"}
    from evaluation.comparisons.base_vs_finetuned import load_test_prompts, evaluate_model
    prompts = load_test_prompts(prompts_path)
    host = args.ollama_host or "http://localhost:11434"
    base = evaluate_model(args.base_model or "glm-4.7-flash", prompts, host)
    ft = evaluate_model(args.ft_model or "mits-tutor-ft", prompts, host)
    return {"base": asdict(base), "finetuned": asdict(ft), "improvement_socratic": ft.socratic_score - base.socratic_score}


BENCHMARK_RUNNERS = {
    "socratic_score": run_socratic_score,
    "error_recovery": run_error_recovery,
    "latency": run_latency,
    "knowledge_prediction": run_knowledge_prediction,
    "affect_accuracy": run_affect_accuracy,
    "base_vs_finetuned": run_base_vs_finetuned,
}


def generate_markdown_report(results: Dict[str, Any], output_path: Path):
    """Generate a markdown report from results."""
    lines = ["# MITS Benchmark Report", "", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]

    for name, data in results.items():
        lines.append(f"## {name.replace('_', ' ').title()}")
        lines.append("")
        if "error" in data:
            lines.append(f"**Error**: {data['error']}")
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    lines.extend([f"### {key}", "", "| Metric | Value |", "|--------|-------|"])
                    for k, v in value.items():
                        if isinstance(v, float):
                            lines.append(f"| {k} | {v:.4f} |")
                        elif not isinstance(v, (list, dict)):
                            lines.append(f"| {k} | {v} |")
                    lines.append("")
                elif isinstance(value, float):
                    lines.append(f"- **{key}**: {value:.4f}")
                elif isinstance(value, int):
                    lines.append(f"- **{key}**: {value}")
        lines.extend(["", "---", ""])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="MITS Benchmark Runner")
    parser.add_argument("--benchmark", nargs="+", default=["all"],
                        choices=AVAILABLE_BENCHMARKS + ["all"])
    parser.add_argument("--output-dir", type=str, default="evaluation/reports")
    parser.add_argument("--dialogs", type=str, default=None)
    parser.add_argument("--test-data", type=str, default=None)
    parser.add_argument("--affect-data", type=str, default=None)
    parser.add_argument("--test-prompts", type=str, default=None)
    parser.add_argument("--dkt-weights", type=str, default=None)
    parser.add_argument("--ml-model", type=str, default=None)
    parser.add_argument("--base-model", type=str, default=None)
    parser.add_argument("--ft-model", type=str, default=None)
    parser.add_argument("--backend-url", type=str, default=None)
    parser.add_argument("--ollama-host", type=str, default=None)
    parser.add_argument("--requests-per-mode", type=int, default=None)
    args = parser.parse_args()

    benchmarks = AVAILABLE_BENCHMARKS if "all" in args.benchmark else args.benchmark
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results = {}
    for name in benchmarks:
        logger.info(f"Running benchmark: {name}")
        runner = BENCHMARK_RUNNERS.get(name)
        if not runner:
            continue
        try:
            all_results[name] = runner(args)
            logger.info(f"  {name}: OK")
        except Exception as e:
            logger.error(f"  {name}: FAILED — {e}")
            all_results[name] = {"error": str(e)}

    json_path = output_dir / "benchmark_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    md_path = output_dir / "benchmark_report.md"
    generate_markdown_report(all_results, md_path)

    print(f"\nBenchmarks complete. {len(all_results)} run.")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    main()
