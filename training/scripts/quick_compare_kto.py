#!/usr/bin/env python3
"""
Quick comparison: GSPO vs KTO vs Base on 10 STEM problems.

Usage:
    python training/scripts/quick_compare_kto.py

Prerequisites:
    - Ollama running with models: mits-tutor-9b-think, mits-tutor-9b-kto, qwen3.5:9b
"""

import json
import logging
import os
import time
from typing import Any, Dict, List

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODELS = {
    "gspo": "mits-tutor-9b-think",
    "kto": "mits-tutor-9b-kto",
    "base": "qwen3.5:9b",
}

# 10 problems across 5 STEM domains, varying difficulty
TEST_PROBLEMS = [
    # Math (3)
    {
        "id": "math_1",
        "domain": "math",
        "difficulty": "easy",
        "problem": "Реши уравнение: $2x + 5 = 15$",
        "answer": "5",
    },
    {
        "id": "math_2",
        "domain": "math",
        "difficulty": "medium",
        "problem": "Найди производную функции $f(x) = x^3 \\sin(x)$",
        "answer": "3x^2 sin(x) + x^3 cos(x)",
    },
    {
        "id": "math_3",
        "domain": "math",
        "difficulty": "hard",
        "problem": "Вычисли определённый интеграл $\\int_0^1 \\frac{\\ln(1+x)}{x} dx$",
        "answer": "pi^2/12",
    },
    # Physics (2)
    {
        "id": "phys_1",
        "domain": "physics",
        "difficulty": "easy",
        "problem": "Мяч бросили вертикально вверх со скоростью 20 м/с. Через сколько секунд он достигнет максимальной высоты? (g = 10 м/с²)",
        "answer": "2",
    },
    {
        "id": "phys_2",
        "domain": "physics",
        "difficulty": "medium",
        "problem": "Два резистора R₁ = 6 Ом и R₂ = 3 Ом соединены параллельно. Найди общее сопротивление.",
        "answer": "2",
    },
    # Chemistry (2)
    {
        "id": "chem_1",
        "domain": "chemistry",
        "difficulty": "easy",
        "problem": "Уравняй реакцию: Fe + O₂ → Fe₂O₃",
        "answer": "4Fe + 3O2 = 2Fe2O3",
    },
    {
        "id": "chem_2",
        "domain": "chemistry",
        "difficulty": "medium",
        "problem": "Какой объём CO₂ (н.у.) выделится при разложении 100 г CaCO₃?",
        "answer": "22.4",
    },
    # Biology (1)
    {
        "id": "bio_1",
        "domain": "biology",
        "difficulty": "medium",
        "problem": "Объясни, чем отличается митоз от мейоза. В каких клетках происходит каждый процесс?",
        "answer": None,  # Open-ended
    },
    # CS (2)
    {
        "id": "cs_1",
        "domain": "cs",
        "difficulty": "easy",
        "problem": "Напиши функцию на Python, которая проверяет, является ли строка палиндромом.",
        "answer": None,  # Open-ended
    },
    {
        "id": "cs_2",
        "domain": "cs",
        "difficulty": "medium",
        "problem": "Какова сложность бинарного поиска и почему? Когда его нельзя применить?",
        "answer": "O(log n)",
    },
]

SYSTEM_PROMPT = (
    "Ты — репетитор по STEM. Помоги ученику разобраться с задачей. "
    "Задавай наводящие вопросы, объясняй метод, но не давай готовый ответ сразу."
)


def query_model(
    model: str,
    problem: str,
    timeout: int = 300,
) -> Dict[str, Any]:
    """Query Ollama model and return response + timing."""
    start = time.time()
    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": problem},
                ],
                "stream": False,
                "options": {"num_predict": 2048},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        elapsed = time.time() - start

        content = data.get("message", {}).get("content", "")
        thinking = data.get("message", {}).get("thinking", "")

        # Token counts from Ollama response
        eval_count = data.get("eval_count", 0)
        eval_duration_ns = data.get("eval_duration", 1)
        tok_per_sec = eval_count / (eval_duration_ns / 1e9) if eval_duration_ns > 0 else 0

        return {
            "content": content,
            "thinking": thinking,
            "elapsed": round(elapsed, 1),
            "tokens": eval_count,
            "tok_per_sec": round(tok_per_sec, 1),
            "error": None,
        }
    except Exception as e:
        return {
            "content": "",
            "thinking": "",
            "elapsed": round(time.time() - start, 1),
            "tokens": 0,
            "tok_per_sec": 0,
            "error": str(e),
        }


def score_response(response: str, problem: Dict) -> Dict[str, float]:
    """Simple heuristic scoring (no LLM judge needed)."""
    text = response.lower()
    scores: Dict[str, float] = {}

    # 1. Has question mark? (Socratic indicator)
    question_count = response.count("?")
    scores["has_questions"] = min(question_count, 3) / 3.0

    # 2. Answer leak check (if answer is known)
    answer = problem.get("answer")
    if answer:
        answer_lower = str(answer).lower().strip()
        # Check if the answer appears verbatim
        if answer_lower in text:
            scores["answer_leaked"] = 1.0
        else:
            scores["answer_leaked"] = 0.0
    else:
        scores["answer_leaked"] = 0.0

    # 3. Uses LaTeX / code formatting?
    has_latex = "$" in response
    has_code = "```" in response
    scores["uses_notation"] = 1.0 if (has_latex or has_code) else 0.0

    # 4. Response length (too short = bad, too long = verbose)
    word_count = len(response.split())
    if word_count < 20:
        scores["length_quality"] = 0.3
    elif word_count < 50:
        scores["length_quality"] = 0.7
    elif word_count < 300:
        scores["length_quality"] = 1.0
    else:
        scores["length_quality"] = 0.7

    # 5. Russian language?
    russian_chars = sum(1 for c in response if "\u0400" <= c <= "\u04ff")
    scores["is_russian"] = 1.0 if russian_chars > len(response) * 0.1 else 0.0

    # Composite
    scores["composite"] = (
        scores["has_questions"] * 0.3
        + (1 - scores["answer_leaked"]) * 0.3
        + scores["uses_notation"] * 0.15
        + scores["length_quality"] * 0.15
        + scores["is_russian"] * 0.1
    )

    return scores


def check_models_available() -> List[str]:
    """Check which models are available in Ollama."""
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        available = [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        logger.error("Ollama not reachable!")
        return []

    present = []
    for stage, model in MODELS.items():
        if any(model in m for m in available):
            present.append(stage)
            logger.info(f"  {stage}: {model} ✓")
        else:
            logger.warning(f"  {stage}: {model} ✗ (not found)")
    return present


def main() -> None:
    logger.info("=" * 60)
    logger.info("MITS Quick Compare: GSPO vs KTO vs Base")
    logger.info("=" * 60)

    available = check_models_available()
    if not available:
        logger.error("No models available. Check Ollama.")
        return

    results: Dict[str, List[Dict]] = {stage: [] for stage in available}

    for i, problem in enumerate(TEST_PROBLEMS):
        logger.info(
            f"\n[{i + 1}/{len(TEST_PROBLEMS)}] {problem['domain']} "
            f"({problem['difficulty']}): {problem['problem'][:60]}..."
        )

        for stage in available:
            model = MODELS[stage]
            logger.info(f"  Querying {stage} ({model})...")
            resp = query_model(model, problem["problem"])

            if resp["error"]:
                logger.error(f"  {stage} ERROR: {resp['error']}")
                continue

            scores = score_response(resp["content"], problem)

            result = {
                "problem_id": problem["id"],
                "domain": problem["domain"],
                "difficulty": problem["difficulty"],
                "content": resp["content"][:500],  # Truncate for readability
                "thinking_len": len(resp["thinking"]),
                "elapsed": resp["elapsed"],
                "tokens": resp["tokens"],
                "tok_per_sec": resp["tok_per_sec"],
                **scores,
            }
            results[stage].append(result)

            logger.info(
                f"  {stage}: {resp['tokens']} tok, {resp['tok_per_sec']} tok/s, "
                f"socratic={scores['has_questions']:.1f}, "
                f"leak={scores['answer_leaked']:.0f}, "
                f"composite={scores['composite']:.2f}"
            )

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)

    for stage in available:
        if not results[stage]:
            continue
        n = len(results[stage])
        avg_composite = sum(r["composite"] for r in results[stage]) / n
        avg_questions = sum(r["has_questions"] for r in results[stage]) / n
        avg_leak = sum(r["answer_leaked"] for r in results[stage]) / n
        avg_tok_s = sum(r["tok_per_sec"] for r in results[stage]) / n
        avg_notation = sum(r["uses_notation"] for r in results[stage]) / n

        logger.info(
            f"  {stage:6s}: composite={avg_composite:.3f}  "
            f"socratic={avg_questions:.2f}  leak={avg_leak:.2f}  "
            f"notation={avg_notation:.2f}  speed={avg_tok_s:.1f} tok/s"
        )

    # Per-difficulty breakdown
    logger.info("\nPER-DIFFICULTY BREAKDOWN:")
    for diff in ["easy", "medium", "hard"]:
        logger.info(f"  {diff}:")
        for stage in available:
            diff_results = [r for r in results[stage] if r["difficulty"] == diff]
            if not diff_results:
                continue
            n = len(diff_results)
            avg_c = sum(r["composite"] for r in diff_results) / n
            avg_q = sum(r["has_questions"] for r in diff_results) / n
            avg_l = sum(r["answer_leaked"] for r in diff_results) / n
            logger.info(
                f"    {stage:6s}: composite={avg_c:.3f}  "
                f"socratic={avg_q:.2f}  leak={avg_l:.2f}  (n={n})"
            )

    # Side-by-side example (first problem)
    logger.info("\n" + "=" * 60)
    logger.info("SIDE-BY-SIDE EXAMPLE (math_1: solve 2x + 5 = 15)")
    logger.info("=" * 60)
    for stage in available:
        match = [r for r in results[stage] if r["problem_id"] == "math_1"]
        if match:
            logger.info(f"\n--- {stage.upper()} ---")
            logger.info(match[0]["content"][:800])

    # Save detailed results
    output_path = "evaluation/reports/quick_compare_kto.json"

    os.makedirs("evaluation/reports", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"\nDetailed results saved to {output_path}")


if __name__ == "__main__":
    main()
