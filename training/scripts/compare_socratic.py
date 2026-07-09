"""
Two-pass model comparison: Accuracy (LLM-judge) + Socratic quality (strict rubric).

Both passes use Cerebras Qwen3-235B as judge — no regex parsing.

Usage:
    PYTHONIOENCODING=utf-8 python training/scripts/compare_socratic.py
    PYTHONIOENCODING=utf-8 python training/scripts/compare_socratic.py --models mits-tutor-9b-think qwen3.5:9b
    PYTHONIOENCODING=utf-8 python training/scripts/compare_socratic.py --problems 20
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from training.cerebras_client import CerebrasClient
from training.scripts.evaluate_stage import (
    SYSTEM_PROMPT_CALC,
    SYSTEM_PROMPT_TUTOR,
    check_format_compliance,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/chat"

# ─── LLM-judge prompts ──────────────────────────────────────

ACCURACY_JUDGE_PROMPT = """Ты — строгий экзаменатор. Определи, правильно ли модель ответила на задачу.

## Задача
{question}

## Правильный ответ
{ground_truth}

## Ответ модели (видимая часть)
{response}

## Правила проверки
- Ответ считается ПРАВИЛЬНЫМ, если модель пришла к верному числовому/символьному результату
- Морфологические варианты допустимы: "митохондрии" = "митохондрия", "Ньютона" = "Ньютон"
- LaTeX-запись эквивалентна текстовой: O(\\log n) = O(log n), \\frac{{1}}{{2}} = 0.5
- Если ответ дан в эквивалентной форме (например, 3x²-12x+9 и 3(x-1)(x-3)) — это ПРАВИЛЬНО
- Единицы измерения не влияют: "50 Дж" = "50"
- Если модель показала правильный ход решения но не дала финальный ответ — это НЕПРАВИЛЬНО
- Если модель задаёт наводящие вопросы вместо решения (сократический режим) — оценивай только если числовой ответ явно присутствует

Верни ТОЛЬКО JSON:
{{"correct": true/false, "extracted_answer": "<что именно модель ответила>", "reason": "<1 предложение>"}}"""


SOCRATIC_JUDGE_PROMPT_STRICT = """Ты — эксперт по сократическому методу обучения. Оцени ответ репетитора СТРОГО.

## Задача студента
{question}

## Правильный ответ (для проверки утечки)
{ground_truth}

## Ответ репетитора
{response}

## Строгая рубрика

**guides_student** (0-3): Качество наводящих вопросов
- 0: Нет вопросов. Просто объясняет или даёт ответ
- 1: Есть вопросы, но риторические или слишком общие ("Подумай, что здесь нужно сделать?")
- 2: Конкретные вопросы по теме, но не выстроены в логическую цепочку
- 3: Цепочка из 2+ вопросов, каждый следующий строится на предыдущем и ведёт к решению

**no_answer_leak** (0-3): Насколько скрыт правильный ответ
- 0: Числовой ответ явно назван ("x = 2 и x = 3", "кинетическая энергия равна 50 Дж")
- 1: Ответ не назван прямо, но показано полное решение с подставленными числами (E_k = 4·25/2 = 50)
- 2: Показана формула или метод, но без подстановки конкретных чисел задачи (E_k = mv²/2, подставь значения)
- 3: Только направление мысли, никаких формул с числами задачи. Студент должен сам выбрать формулу

**scaffolding** (0-3): Пошаговое выстраивание
- 0: Один абзац без структуры
- 1: Есть структура (списки, шаги), но шаги не наращивают сложность — скорее перечисление
- 2: Шаги идут от простого к сложному, но репетитор делает все шаги за студента
- 3: Репетитор делает только первый шаг, а на следующих шагах задаёт вопросы студенту

**encouragement** (0-1): Мотивация и обращение
- 0: Сухо, без обращения к студенту
- 1: Обращается к студенту, поддерживает или мотивирует

**latex_quality** (0-1): Использование математической нотации
- 0: Нет LaTeX или формулы написаны plain text
- 1: Используется LaTeX ($...$) для математических выражений

## Примеры оценки

Пример ответа с оценкой 12/11 (идеальный):
"Отличный вопрос! Давай разберёмся вместе. Для начала: какая физическая величина описывает энергию движущегося тела? Когда вспомнишь формулу — какие значения из условия тебе понадобятся для подстановки?"
→ guides=3, leak=3, scaff=3, encourage=1, latex=1 (формулы не нужны в этом ответе), but only if question asks for formula

Пример ответа с оценкой 4/11 (плохой):
"Кинетическая энергия вычисляется по формуле $E_k = \\frac{{mv^2}}{{2}}$. Подставим: $E_k = \\frac{{4 \\cdot 5^2}}{{2}} = \\frac{{100}}{{2}} = 50$ Дж. Попробуй проверить!"
→ guides=0, leak=0, scaff=1, encourage=1, latex=1

Верни ТОЛЬКО JSON (без markdown):
{{"guides_student": <0-3>, "no_answer_leak": <0-3>, "scaffolding": <0-3>, "encouragement": <0-1>, "latex_quality": <0-1>, "explanation": "<2-3 предложения на русском с конкретными примерами из ответа>"}}"""


# ─── Problems: mixed difficulty ──────────────────────────────

PROBLEMS = [
    # Math — easy
    {
        "prompt": "Реши уравнение x² - 5x + 6 = 0",
        "ground_truth": "x=2, x=3",
        "domain": "math",
        "difficulty": "easy",
    },
    {
        "prompt": "Чему равна сумма углов треугольника?",
        "ground_truth": "180",
        "domain": "math",
        "difficulty": "easy",
    },
    # Math — medium
    {
        "prompt": "Найди производную f(x) = x³ - 6x² + 9x + 1",
        "ground_truth": "3x²-12x+9",
        "domain": "math",
        "difficulty": "medium",
    },
    {
        "prompt": "Вычисли определённый интеграл ∫₀¹ (3x² + 2x) dx",
        "ground_truth": "2",
        "domain": "math",
        "difficulty": "medium",
    },
    # Physics — easy
    {
        "prompt": "Тело массой 4 кг движется со скоростью 5 м/с. Найди кинетическую энергию.",
        "ground_truth": "50 Дж",
        "domain": "physics",
        "difficulty": "easy",
    },
    {
        "prompt": "Сила тока в цепи с напряжением 12В и сопротивлением 4 Ом?",
        "ground_truth": "3 А",
        "domain": "physics",
        "difficulty": "easy",
    },
    # Physics — medium
    {
        "prompt": "Тело брошено вертикально вверх со скоростью 20 м/с. На какую максимальную высоту оно поднимется? (g=10 м/с²)",
        "ground_truth": "20 м",
        "domain": "physics",
        "difficulty": "medium",
    },
    {
        "prompt": "Два резистора 6 Ом и 3 Ом соединены параллельно. Чему равно общее сопротивление?",
        "ground_truth": "2 Ом",
        "domain": "physics",
        "difficulty": "medium",
    },
    # Chemistry
    {
        "prompt": "Молярная масса H₂O (г/моль)?",
        "ground_truth": "18 г/моль",
        "domain": "chemistry",
        "difficulty": "easy",
    },
    {
        "prompt": "pH нейтрального раствора?",
        "ground_truth": "7",
        "domain": "chemistry",
        "difficulty": "easy",
    },
    {
        "prompt": "Сколько молей содержится в 44 г CO₂? (M(CO₂)=44 г/моль)",
        "ground_truth": "1 моль",
        "domain": "chemistry",
        "difficulty": "medium",
    },
    # Biology
    {
        "prompt": "Сколько хромосом у человека?",
        "ground_truth": "46",
        "domain": "biology",
        "difficulty": "easy",
    },
    {
        "prompt": "Какая органелла отвечает за клеточное дыхание?",
        "ground_truth": "митохондрия",
        "domain": "biology",
        "difficulty": "easy",
    },
    {
        "prompt": "Какой процесс обеспечивает перенос генетической информации с ДНК на мРНК?",
        "ground_truth": "транскрипция",
        "domain": "biology",
        "difficulty": "medium",
    },
    # CS
    {
        "prompt": "Временная сложность бинарного поиска?",
        "ground_truth": "O(log n)",
        "domain": "cs",
        "difficulty": "easy",
    },
    {
        "prompt": "Временная сложность сортировки пузырьком в худшем случае?",
        "ground_truth": "O(n²)",
        "domain": "cs",
        "difficulty": "easy",
    },
    {
        "prompt": "Какая структура данных использует принцип LIFO?",
        "ground_truth": "стек",
        "domain": "cs",
        "difficulty": "easy",
    },
    {
        "prompt": "Какова временная сложность поиска элемента в хеш-таблице в среднем случае?",
        "ground_truth": "O(1)",
        "domain": "cs",
        "difficulty": "medium",
    },
]


# ─── LLM-judge functions ────────────────────────────────────


def verify_answer_llm(
    question: str,
    response: str,
    ground_truth: str,
    cerebras: CerebrasClient,
) -> Dict[str, Any]:
    """Verify answer correctness using LLM-judge (Cerebras Qwen3-235B)."""
    prompt = ACCURACY_JUDGE_PROMPT.format(
        question=question,
        response=response,
        ground_truth=ground_truth,
    )
    try:
        raw = cerebras.generate(
            prompt=prompt,
            system_prompt="You are an expert STEM examiner. Return ONLY valid JSON.",
            max_tokens=200,
            temperature=0.0,
        )
        json_str = raw.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        result = json.loads(json_str)
        return result
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Accuracy judge failed: {e}")
        return {"correct": None, "extracted_answer": "", "reason": f"judge error: {e}"}


def evaluate_socratic_strict(
    question: str,
    response: str,
    ground_truth: str,
    cerebras: CerebrasClient,
) -> Dict[str, Any]:
    """Evaluate Socratic quality with strict rubric (max score = 11)."""
    prompt = SOCRATIC_JUDGE_PROMPT_STRICT.format(
        question=question,
        response=response,
        ground_truth=ground_truth,
    )
    try:
        raw = cerebras.generate(
            prompt=prompt,
            system_prompt="You are an expert evaluator of Socratic teaching. Be STRICT. Return ONLY valid JSON.",
            max_tokens=300,
            temperature=0.0,
        )
        json_str = raw.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        scores = json.loads(json_str)

        total = (
            scores.get("guides_student", 0)
            + scores.get("no_answer_leak", 0)
            + scores.get("scaffolding", 0)
            + scores.get("encouragement", 0)
            + scores.get("latex_quality", 0)
        )
        scores["socratic_score"] = round(total / 11, 3)
        scores["total_points"] = total
        return scores

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Socratic judge failed: {e}")
        return {"socratic_score": None, "error": str(e)}


# ─── Ollama ──────────────────────────────────────────────────


def ollama_chat(model: str, prompt: str, system_prompt: str) -> Dict[str, str]:
    """Send chat request to Ollama, return {content, thinking, full}."""
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 4096, "num_ctx": 8192},
            "think": True,
        },
        timeout=300,
    )
    msg = resp.json().get("message", {})
    thinking = msg.get("thinking", "")
    content = msg.get("content", "")
    full = f"<think>\n{thinking}\n</think>\n{content}" if thinking else content
    return {"content": content, "thinking": thinking, "full": full}


# ─── Evaluation passes ───────────────────────────────────────


def run_accuracy_pass(
    model: str,
    problems: List[Dict],
    cerebras: CerebrasClient,
) -> List[Dict]:
    """Pass 1: Accuracy — solve with \\boxed{} prompt, verify with LLM-judge."""
    results = []
    for i, p in enumerate(problems):
        logger.info(f"  [Accuracy {i + 1}/{len(problems)}] {p['prompt'][:55]}...")
        t0 = time.time()
        out = ollama_chat(model, p["prompt"], SYSTEM_PROMPT_CALC)
        ollama_elapsed = time.time() - t0

        fmt = check_format_compliance(out["full"])

        # LLM-judge for accuracy (visible part only)
        t1 = time.time()
        verdict = verify_answer_llm(
            question=p["prompt"],
            response=out["content"],
            ground_truth=p["ground_truth"],
            cerebras=cerebras,
        )
        judge_elapsed = time.time() - t1

        correct = verdict.get("correct")
        extracted = verdict.get("extracted_answer", "")
        mark = "+" if correct else ("?" if correct is None else "x")
        logger.info(
            f"    [{mark}] truth={p['ground_truth']:<14s} pred={str(extracted):<14s} "
            f"({ollama_elapsed:.1f}s + judge {judge_elapsed:.1f}s) {verdict.get('reason', '')}"
        )

        results.append(
            {
                "problem": p,
                "completion": out["full"],
                "content": out["content"],
                "extracted": extracted,
                "correct": correct,
                "judge_verdict": verdict,
                "format": fmt,
                "elapsed": ollama_elapsed,
            }
        )
    return results


def run_socratic_pass(
    model: str,
    problems: List[Dict],
    cerebras: CerebrasClient,
) -> List[Dict]:
    """Pass 2: Socratic quality — tutor prompt + strict LLM-judge."""
    results = []
    for i, p in enumerate(problems):
        logger.info(f"  [Socratic {i + 1}/{len(problems)}] {p['prompt'][:55]}...")
        t0 = time.time()
        out = ollama_chat(model, p["prompt"], SYSTEM_PROMPT_TUTOR)
        ollama_elapsed = time.time() - t0

        t1 = time.time()
        scores = evaluate_socratic_strict(
            question=p["prompt"],
            response=out["content"],
            ground_truth=p["ground_truth"],
            cerebras=cerebras,
        )
        judge_elapsed = time.time() - t1

        sc = scores.get("socratic_score")
        tp = scores.get("total_points", "?")
        sc_str = f"{sc:.2f}" if sc is not None else "ERR"
        logger.info(
            f"    {tp}/11 ({sc_str}) | guide={scores.get('guides_student', '?')} "
            f"leak={scores.get('no_answer_leak', '?')} scaff={scores.get('scaffolding', '?')} "
            f"enc={scores.get('encouragement', '?')} tex={scores.get('latex_quality', '?')} "
            f"({ollama_elapsed:.1f}s + judge {judge_elapsed:.1f}s)"
        )

        results.append(
            {
                "problem": p,
                "tutor_response": out["content"],
                "thinking": out["thinking"],
                "scores": scores,
                "ollama_elapsed": ollama_elapsed,
                "judge_elapsed": judge_elapsed,
            }
        )
    return results


# ─── Summary ─────────────────────────────────────────────────


def print_summary(
    models: List[str],
    accuracy_results: Dict[str, List[Dict]],
    socratic_results: Dict[str, List[Dict]],
) -> Dict[str, Any]:
    """Print comparison table and return report dict."""
    report: Dict[str, Any] = {}

    print(f"\n{'=' * 80}")
    print("COMPARISON RESULTS (LLM-judge accuracy + strict Socratic rubric)")
    print(f"{'=' * 80}")

    print(f"\n{'Metric':<40}", end="")
    for m in models:
        print(f"{m:<20}", end="")
    print()
    print("-" * (40 + 20 * len(models)))

    for m in models:
        acc = accuracy_results[m]
        soc = socratic_results[m]

        # Accuracy (only count non-None verdicts)
        valid_acc = [r for r in acc if r["correct"] is not None]
        correct = sum(1 for r in valid_acc if r["correct"])
        total = len(valid_acc)
        accuracy = correct / total if total else 0

        has_thinking = sum(1 for r in acc if r["format"].get("has_thinking"))
        has_boxed = sum(1 for r in acc if r["format"].get("has_boxed"))

        # Socratic
        valid_soc = [r["scores"] for r in soc if r["scores"].get("socratic_score") is not None]
        n_soc = len(valid_soc)

        def avg(key: str) -> float:
            return sum(s.get(key, 0) for s in valid_soc) / n_soc if n_soc else 0

        report[m] = {
            "accuracy": round(accuracy, 3),
            "correct": correct,
            "total": total,
            "judge_errors": len(acc) - len(valid_acc),
            "thinking_pct": round(has_thinking / len(acc), 3) if acc else 0,
            "boxed_pct": round(has_boxed / len(acc), 3) if acc else 0,
            "socratic_score": round(avg("socratic_score"), 3),
            "total_points": round(avg("total_points"), 1),
            "guides_student": round(avg("guides_student"), 2),
            "no_answer_leak": round(avg("no_answer_leak"), 2),
            "scaffolding": round(avg("scaffolding"), 2),
            "encouragement": round(avg("encouragement"), 2),
            "latex_quality": round(avg("latex_quality"), 2),
            "socratic_valid": n_soc,
        }

    metrics = [
        ("Accuracy (LLM-judge)", lambda r: f"{r['correct']}/{r['total']} ({r['accuracy']:.0%})"),
        ("<think> usage", lambda r: f"{r['thinking_pct']:.0%}"),
        ("\\boxed{} usage", lambda r: f"{r['boxed_pct']:.0%}"),
        ("", lambda r: ""),
        ("Socratic Score (0-1)", lambda r: f"{r['socratic_score']:.3f}"),
        ("  Total points (0-11)", lambda r: f"{r['total_points']:.1f}"),
        ("  guides_student (0-3)", lambda r: f"{r['guides_student']:.2f}"),
        ("  no_answer_leak (0-3)", lambda r: f"{r['no_answer_leak']:.2f}"),
        ("  scaffolding (0-3)", lambda r: f"{r['scaffolding']:.2f}"),
        ("  encouragement (0-1)", lambda r: f"{r['encouragement']:.2f}"),
        ("  latex_quality (0-1)", lambda r: f"{r['latex_quality']:.2f}"),
    ]

    for label, fmt_fn in metrics:
        if not label:
            print()
            continue
        print(f"{label:<40}", end="")
        for m in models:
            print(f"{fmt_fn(report[m]):<20}", end="")
        print()

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Compare models: LLM-judge Accuracy + strict Socratic"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["mits-tutor-9b-think", "qwen3.5:9b"],
        help="Ollama model names to compare",
    )
    parser.add_argument(
        "--problems",
        type=int,
        default=0,
        help="Limit number of problems (0 = all)",
    )
    args = parser.parse_args()

    problems = PROBLEMS[: args.problems] if args.problems > 0 else PROBLEMS

    logger.info(f"Models: {args.models}")
    logger.info(f"Problems: {len(problems)} (5 domains, easy+medium)")

    logger.info("Initializing Cerebras client (Qwen3-235B judge)...")
    cerebras = CerebrasClient()
    logger.info(f"  {cerebras.get_stats()['keys_available']} API keys loaded")

    accuracy_results: Dict[str, List[Dict]] = {}
    socratic_results: Dict[str, List[Dict]] = {}

    for model in args.models:
        print(f"\n{'=' * 60}")
        print(f"Model: {model}")
        print(f"{'=' * 60}")

        logger.info(f"\n--- Pass 1: Accuracy + LLM-judge ({model}) ---")
        accuracy_results[model] = run_accuracy_pass(model, problems, cerebras)

        logger.info(f"\n--- Pass 2: Socratic strict ({model}) ---")
        socratic_results[model] = run_socratic_pass(model, problems, cerebras)

    report = print_summary(args.models, accuracy_results, socratic_results)

    # Save
    output_path = "evaluation/reports/socratic_comparison.json"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    detailed = {
        "models": args.models,
        "num_problems": len(problems),
        "judge": "cerebras/qwen-3-235b-a22b-instruct-2507",
        "rubric_version": "strict_v2",
        "summary": report,
        "cerebras_stats": cerebras.get_stats(),
        "details": {
            model: {
                "accuracy": [
                    {
                        "prompt": r["problem"]["prompt"],
                        "domain": r["problem"]["domain"],
                        "difficulty": r["problem"]["difficulty"],
                        "truth": r["problem"]["ground_truth"],
                        "extracted": r["extracted"],
                        "correct": r["correct"],
                        "judge_reason": r["judge_verdict"].get("reason", ""),
                    }
                    for r in accuracy_results[model]
                ],
                "socratic": [
                    {
                        "prompt": r["problem"]["prompt"],
                        "domain": r["problem"]["domain"],
                        "difficulty": r["problem"]["difficulty"],
                        "tutor_response": r["tutor_response"][:500],
                        "scores": r["scores"],
                    }
                    for r in socratic_results[model]
                ],
            }
            for model in args.models
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(detailed, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed report: {output_path}")
    print(f"Cerebras usage: {cerebras.get_stats()}")


if __name__ == "__main__":
    main()
