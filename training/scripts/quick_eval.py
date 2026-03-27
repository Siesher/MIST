"""
Quick local evaluation of Ollama MITS model.
Tests 25 prompts (5 per domain), checks format + accuracy.
Usage: python training/scripts/quick_eval.py [--model mits-tutor]
"""

import argparse
import json
import re
from dataclasses import dataclass

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"

# 5 questions per domain with expected answers for verifiable ones
TESTS = {
    "math": [
        ("Реши уравнение x² - 5x + 6 = 0", {"2", "3"}),
        ("Найди производную функции f(x) = 3x³ + 2x²", None),
        ("Вычисли: log₂(8)", {"3"}),
        ("Чему равна сумма углов треугольника?", {"180"}),
        ("Найди площадь круга с радиусом 5 (ответ через π)", None),
    ],
    "physics": [
        ("Тело массой 4 кг движется со скоростью 5 м/с. Найди кинетическую энергию.", {"50"}),
        ("Сила тока в цепи с напряжением 12В и сопротивлением 4 Ом?", {"3"}),
        ("Тело падает с высоты 20 м. Время падения? (g=10 м/с²)", {"2"}),
        ("Формула кинетической энергии?", None),
        ("Первый закон Ньютона — закон чего?", None),
    ],
    "chemistry": [
        ("Молярная масса H₂O (г/моль)?", {"18"}),
        ("Уравняй: 2H₂ + O₂ → H₂O. Коэффициент перед H₂O?", {"2"}),
        ("Число Авогадро приблизительно равно?", None),
        ("Что образуется при реакции кислоты с основанием?", None),
        ("pH нейтрального раствора?", {"7"}),
    ],
    "biology": [
        ("Какая органелла отвечает за синтез белка?", None),
        ("Сколько хромосом у человека?", {"46"}),
        ("Уравнение фотосинтеза: 6CO₂ + 6H₂O → ?", None),
        ("Первый закон Менделя называется законом...?", None),
        ("Где хранится ДНК в клетке?", None),
    ],
    "cs": [
        ("Временная сложность бинарного поиска?", {"O(log n)", "O(log(n))"}),
        ("Временная сложность сортировки пузырьком?", {"O(n²)", "O(n^2)"}),
        ("Что такое рекурсия?", None),
        ("Чем стек отличается от очереди?", None),
        ("Напиши функцию Python для факториала n (2 строки)", None),
        # TODO(human): Add 5 more questions per domain below (25 total)
        # Format: ("question", {"expected_answer"}) or ("question", None)
        # Target: at least 3 verifiable per domain, grade 7-11 level
    ],
}


@dataclass
class Result:
    domain: str
    question: str
    answer: str
    correct: bool | None  # None = not verifiable
    has_steps: bool
    has_latex: bool
    has_thinking: bool
    length: int


def query(prompt: str, model: str) -> str:
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 768},
        },
        timeout=120,
    )
    return resp.json()["response"]


def extract_numbers(text: str) -> set[str]:
    """Extract all numbers from text."""
    nums = re.findall(r"-?\d+(?:\.\d+)?", text)
    return set(nums)


def check_answer(response: str, expected: set[str] | None) -> bool | None:
    if expected is None:
        return None
    resp_lower = response.lower()
    # Direct string match
    for ans in expected:
        if ans.lower() in resp_lower:
            return True
    # Numeric match: check if any expected number appears in response numbers
    for ans in expected:
        try:
            float(ans)
            if ans in extract_numbers(response):
                return True
        except ValueError:
            pass
    return False


def check_format(response: str) -> tuple[bool, bool, bool]:
    has_steps = any(
        marker in response.lower()
        for marker in [
            "шаг",
            "step",
            "следовательно",
            "значит",
            "поэтому",
            "1.",
            "2.",
            "3.",
            "подставим",
            "найдём",
            "вычислим",
        ]
    )
    has_latex = bool(re.search(r"\$[^$]+\$|\\\[|\\\(|\\frac|\\times|\\cdot", response))
    has_thinking = "<think>" in response or "</think>" in response
    return has_steps, has_latex, has_thinking


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="mits-tutor")
    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print(f"Quick Eval: {args.model}")
    print(f"{'=' * 60}")

    results: list[Result] = []
    total = sum(len(q) for q in TESTS.values())
    done = 0

    for domain, questions in TESTS.items():
        print(f"\n[{domain.upper()}]")
        for question, expected in questions:
            done += 1
            print(f"  {done}/{total} {question[:60]}...", end=" ", flush=True)
            try:
                response = query(question, args.model)
                correct = check_answer(response, expected)
                has_steps, has_latex, has_thinking = check_format(response)
                results.append(
                    Result(
                        domain=domain,
                        question=question,
                        answer=response[:200],
                        correct=correct,
                        has_steps=has_steps,
                        has_latex=has_latex,
                        has_thinking=has_thinking,
                        length=len(response),
                    )
                )
                status = ("✓" if correct else "✗") if correct is not None else "~"
                flags = (
                    ("S" if has_steps else ".")
                    + ("L" if has_latex else ".")
                    + ("T" if has_thinking else ".")
                )
                print(f"{status} [{flags}] {len(response)}ch")
            except Exception as e:
                print(f"ERROR: {e}")
                results.append(Result(domain, question, "", None, False, False, False, 0))

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")

    verifiable = [r for r in results if r.correct is not None]
    correct = [r for r in verifiable if r.correct]
    accuracy = len(correct) / len(verifiable) * 100 if verifiable else 0

    print(f"\nAccuracy (verifiable):  {len(correct)}/{len(verifiable)} = {accuracy:.0f}%")
    print(
        f"Step-by-step reasoning: {sum(r.has_steps for r in results)}/{len(results)} = {sum(r.has_steps for r in results) / len(results) * 100:.0f}%"
    )
    print(
        f"LaTeX formatting:       {sum(r.has_latex for r in results)}/{len(results)} = {sum(r.has_latex for r in results) / len(results) * 100:.0f}%"
    )
    print(
        f"Chain-of-thought tags:  {sum(r.has_thinking for r in results)}/{len(results)} = {sum(r.has_thinking for r in results) / len(results) * 100:.0f}%"
    )
    print(f"Avg response length:    {sum(r.length for r in results) // len(results)} chars")

    print("\nBy domain:")
    for domain in TESTS:
        domain_results = [r for r in results if r.domain == domain]
        verif = [r for r in domain_results if r.correct is not None]
        corr = [r for r in verif if r.correct]
        acc_str = f"{len(corr)}/{len(verif)}" if verif else "n/a"
        steps = sum(r.has_steps for r in domain_results)
        print(f"  {domain:<12} acc={acc_str:<5}  steps={steps}/{len(domain_results)}")

    # Save
    out = {
        "model": args.model,
        "accuracy_pct": round(accuracy, 1),
        "verifiable_correct": len(correct),
        "verifiable_total": len(verifiable),
        "steps_pct": round(sum(r.has_steps for r in results) / len(results) * 100, 1),
        "latex_pct": round(sum(r.has_latex for r in results) / len(results) * 100, 1),
        "thinking_pct": round(sum(r.has_thinking for r in results) / len(results) * 100, 1),
        "avg_length": sum(r.length for r in results) // len(results),
        "by_domain": {
            d: {
                "correct": sum(1 for r in results if r.domain == d and r.correct),
                "verifiable": sum(1 for r in results if r.domain == d and r.correct is not None),
                "steps": sum(1 for r in results if r.domain == d and r.has_steps),
            }
            for d in TESTS
        },
    }
    safe_name = args.model.replace(":", "_").replace("/", "_")
    report_path = f"evaluation/reports/quick_eval_{safe_name}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {report_path}")


if __name__ == "__main__":
    main()
