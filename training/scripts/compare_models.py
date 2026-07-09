"""Quick comparison of GSPO-tuned model vs base model on 10 prompts."""

import json
import sys
import time

import requests

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

PROMPTS = [
    "Реши уравнение x² - 5x + 6 = 0",
    "Найди производную f(x) = 3x³ + 2x²",
    "Вычисли log₂(8)",
    "Тело массой 4 кг движется со скоростью 5 м/с. Найди кинетическую энергию.",
    "Молярная масса H₂O?",
    "Сколько хромосом у человека?",
    "Временная сложность бинарного поиска?",
    "Чему равна сумма углов треугольника?",
    "Сила тока при напряжении 12В и сопротивлении 4 Ом?",
    "Что образуется при реакции кислоты с основанием?",
]

MODELS = sys.argv[1:] if len(sys.argv) > 1 else ["mits-tutor-9b", "qwen3.5:9b"]


def chat(model: str, prompt: str, max_tokens: int = 768) -> tuple[str, float]:
    """Send chat request, return (response, elapsed_seconds)."""
    t0 = time.time()
    resp = requests.post(
        OLLAMA_CHAT_URL,
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": max_tokens},
        },
        timeout=300,
    )
    elapsed = time.time() - t0
    data = resp.json()
    content = data.get("message", {}).get("content", f"ERROR: {data}")
    return content, elapsed


def analyze(response: str) -> dict:
    """Analyze response for Socratic qualities."""
    lower = response.lower()
    return {
        "has_question": "?" in response,
        "has_thinking": "<think>" in response,
        "has_latex": "$" in response or "\\frac" in response or "\\(" in response,
        "has_steps": any(
            m in lower for m in ["шаг", "подставим", "найдём", "вычислим", "1.", "2."]
        ),
        "is_socratic": any(
            m in lower
            for m in [
                "подумай",
                "попробуй",
                "как ты думаешь",
                "что если",
                "какой",
                "давай",
                "вспомни",
                "обрати внимание",
                "подсказка",
                "наводящ",
            ]
        ),
        "gives_direct_answer": any(
            m in lower
            for m in [
                "ответ:",
                "= 2",
                "= 3",
                "= 50",
                "= 18",
                "= 46",
                "= 180",
            ]
        ),
        "length": len(response),
    }


def main():
    print(f"\n{'=' * 70}")
    print(f"Model Comparison: {' vs '.join(MODELS)}")
    print(f"{'=' * 70}")

    results = {m: [] for m in MODELS}

    for i, prompt in enumerate(PROMPTS, 1):
        print(f"\n[{i}/{len(PROMPTS)}] {prompt}")
        print("-" * 60)

        for model in MODELS:
            print(f"\n  >>> {model}:")
            try:
                response, elapsed = chat(model, prompt)
                stats = analyze(response)
                results[model].append(stats)

                # Print truncated response
                display = response.replace("\n", " ")[:300]
                print(f"  {display}")
                print(
                    f"  [{elapsed:.1f}s | {stats['length']}ch | "
                    f"Q:{'✓' if stats['has_question'] else '✗'} "
                    f"T:{'✓' if stats['has_thinking'] else '✗'} "
                    f"S:{'✓' if stats['is_socratic'] else '✗'} "
                    f"D:{'✓' if stats['gives_direct_answer'] else '✗'}]"
                )
            except Exception as e:
                print(f"  ERROR: {e}")
                results[model].append({"error": True})

    # Summary table
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"{'Metric':<30}", end="")
    for m in MODELS:
        print(f"{m:<25}", end="")
    print()
    print("-" * (30 + 25 * len(MODELS)))

    for metric, label in [
        ("has_question", "Contains question (?)"),
        ("has_thinking", "Has <think> block"),
        ("has_latex", "Uses LaTeX"),
        ("has_steps", "Step-by-step"),
        ("is_socratic", "Socratic style"),
        ("gives_direct_answer", "Gives direct answer"),
    ]:
        print(f"{label:<30}", end="")
        for m in MODELS:
            valid = [r for r in results[m] if "error" not in r]
            count = sum(1 for r in valid if r.get(metric, False))
            pct = count / len(valid) * 100 if valid else 0
            print(f"{count}/{len(valid)} ({pct:.0f}%){'':<12}", end="")
        print()

    # Avg length
    print(f"{'Avg response length':<30}", end="")
    for m in MODELS:
        valid = [r for r in results[m] if "error" not in r]
        avg_len = sum(r["length"] for r in valid) // max(len(valid), 1)
        print(f"{avg_len} chars{'':<14}", end="")
    print()

    # Save
    report = {
        m: {
            "questions": sum(1 for r in results[m] if r.get("has_question")),
            "thinking": sum(1 for r in results[m] if r.get("has_thinking")),
            "socratic": sum(1 for r in results[m] if r.get("is_socratic")),
            "direct_answer": sum(1 for r in results[m] if r.get("gives_direct_answer")),
            "avg_length": sum(r.get("length", 0) for r in results[m]) // max(len(results[m]), 1),
            "total": len(results[m]),
        }
        for m in MODELS
    }

    with open("evaluation/reports/model_comparison.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("\nSaved to evaluation/reports/model_comparison.json")


if __name__ == "__main__":
    main()
