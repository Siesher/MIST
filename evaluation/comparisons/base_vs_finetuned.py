"""
Base vs Fine-tuned Model Comparison

Runs both base and fine-tuned models on the same test prompts,
comparing Socratic Score, response quality, and latency.

Usage:
    python -m evaluation.comparisons.base_vs_finetuned \
        --test-prompts data/training/test_prompts.jsonl \
        --base-model glm-4.7-flash \
        --ft-model mits-tutor-ft \
        --output evaluation/reports/base_vs_finetuned.json
"""

import json
import time
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class ModelResult:
    """Results for a single model."""
    model_name: str = ""
    avg_latency_ms: float = 0.0
    socratic_score: float = 0.0
    telling_rate: float = 0.0
    avg_response_length: float = 0.0
    num_prompts: int = 0


@dataclass
class ComparisonResult:
    """Full comparison result."""
    base_model: Dict[str, Any] = field(default_factory=dict)
    finetuned_model: Dict[str, Any] = field(default_factory=dict)
    improvement: Dict[str, float] = field(default_factory=dict)
    test_prompts_count: int = 0


def generate_response(model_name: str, prompt: str, ollama_host: str = "http://localhost:11434") -> tuple:
    """Generate a response from Ollama and measure time."""
    import requests

    start = time.perf_counter()
    try:
        resp = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "top_p": 0.95},
            },
            timeout=120,
        )
        resp.raise_for_status()
        response_text = resp.json().get("response", "")
    except Exception as e:
        logger.warning(f"Generation failed for {model_name}: {e}")
        return "", 0.0

    elapsed_ms = (time.perf_counter() - start) * 1000
    return response_text, elapsed_ms


def analyze_response(text: str) -> Dict[str, Any]:
    """Analyze response for Socratic indicators."""
    from evaluation.benchmarks.socratic_score import analyze_turn
    analysis = analyze_turn(text)
    return {
        "length": len(text),
        "is_guiding": analysis["is_guiding"],
        "is_telling": analysis["is_telling"],
    }


def evaluate_model(model_name: str, prompts: List[str], ollama_host: str) -> ModelResult:
    """Evaluate a model on all test prompts."""
    latencies = []
    guiding_count = 0
    telling_count = 0
    total_length = 0

    for i, prompt in enumerate(prompts):
        response, latency = generate_response(model_name, prompt, ollama_host)
        if not response:
            continue

        latencies.append(latency)
        analysis = analyze_response(response)
        total_length += analysis["length"]

        if analysis["is_guiding"]:
            guiding_count += 1
        if analysis["is_telling"]:
            telling_count += 1

        if (i + 1) % 10 == 0:
            logger.info(f"  {model_name}: {i+1}/{len(prompts)} prompts")

    n = len(latencies)
    return ModelResult(
        model_name=model_name,
        avg_latency_ms=sum(latencies) / n if n else 0,
        socratic_score=guiding_count / n if n else 0,
        telling_rate=telling_count / n if n else 0,
        avg_response_length=total_length / n if n else 0,
        num_prompts=n,
    )


def load_test_prompts(path: Path) -> List[str]:
    """Load test prompts from JSONL."""
    prompts = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            prompt = data.get("prompt", data.get("text", ""))
            if prompt:
                prompts.append(prompt)
    return prompts


def main():
    parser = argparse.ArgumentParser(description="Base vs fine-tuned comparison")
    parser.add_argument("--test-prompts", type=str, required=True)
    parser.add_argument("--base-model", type=str, default="glm-4.7-flash")
    parser.add_argument("--ft-model", type=str, default="mits-tutor-ft")
    parser.add_argument("--ollama-host", type=str, default="http://localhost:11434")
    parser.add_argument("--output", type=str, default="evaluation/reports/base_vs_finetuned.json")
    args = parser.parse_args()

    prompts = load_test_prompts(Path(args.test_prompts))
    logger.info(f"Loaded {len(prompts)} test prompts")

    logger.info(f"Evaluating base model: {args.base_model}")
    base = evaluate_model(args.base_model, prompts, args.ollama_host)

    logger.info(f"Evaluating fine-tuned model: {args.ft_model}")
    ft = evaluate_model(args.ft_model, prompts, args.ollama_host)

    result = ComparisonResult(
        base_model=asdict(base),
        finetuned_model=asdict(ft),
        improvement={
            "socratic_score": ft.socratic_score - base.socratic_score,
            "telling_rate": base.telling_rate - ft.telling_rate,
            "latency_ms": base.avg_latency_ms - ft.avg_latency_ms,
        },
        test_prompts_count=len(prompts),
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(result), f, indent=2, ensure_ascii=False)

    print(f"\n{'Metric':<25} {'Base':>10} {'Fine-tuned':>12} {'Delta':>10}")
    print("-" * 60)
    print(f"{'Socratic Score':<25} {base.socratic_score:>10.3f} {ft.socratic_score:>12.3f} {ft.socratic_score - base.socratic_score:>+10.3f}")
    print(f"{'Telling Rate':<25} {base.telling_rate:>10.3f} {ft.telling_rate:>12.3f} {ft.telling_rate - base.telling_rate:>+10.3f}")
    print(f"{'Avg Latency (ms)':<25} {base.avg_latency_ms:>10.0f} {ft.avg_latency_ms:>12.0f} {ft.avg_latency_ms - base.avg_latency_ms:>+10.0f}")
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
