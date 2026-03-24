"""Generate Socratic tutoring data using Cerebras API for GSPO/KTO/DPO training.

Uses Qwen-3-235B via Cerebras (10 API keys, ~300 req/min) to generate
paired responses for STEM problems:
  - GOOD (Socratic): guiding questions, hints, scaffolding
  - BAD (direct): gives answer immediately

Output formats:
  - KTO: {prompt, completion, label} (label=true for Socratic, false for direct)
  - DPO: {prompt, chosen, rejected}

Usage:
    python training/scripts/generate_socratic_data.py \
        --input training/data/eval_benchmark.jsonl \
        --output training/data/socratic_pairs \
        --max-problems 500 \
        --format both
"""

import argparse
import json
import logging
import random
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from training.cerebras_client import CerebrasClient

# ─── System prompts ─────────────────────────────────────────

SOCRATIC_SYSTEM = (
    "Ты — сократический репетитор по STEM. Твоя задача — помогать студентам "
    "самостоятельно находить решения через наводящие вопросы и подсказки.\n\n"
    "ПРАВИЛА:\n"
    "- НИКОГДА не давай готовый ответ\n"
    "- Задавай 1-2 наводящих вопроса\n"
    "- Давай подсказки, которые направляют мышление\n"
    "- Хвали правильные шаги студента\n"
    "- Используй LaTeX для математических выражений\n"
    "- Отвечай на русском языке"
)

# ─── Student simulation prompts ─────────────────────────────

STUDENT_TEMPLATES = [
    "Помогите мне решить эту задачу: {problem}",
    "Я не понимаю как подступиться к этой задаче: {problem}",
    "Можете объяснить как решать? {problem}",
    "У меня не получается: {problem}\nЯ попробовал(а), но запутался(ась).",
    "Задача: {problem}\nС чего начать?",
]

# ─── Domain-specific hints for generation ────────────────────

DOMAIN_HINTS = {
    "math": "Используй математическую терминологию: уравнения, функции, теоремы. "
    "Направляй через алгебраические преобразования.",
    "physics": "Используй физические законы и формулы. "
    "Направляй через анализ сил, энергий, или процессов.",
    "chemistry": "Используй химическую терминологию: реакции, связи, молекулы. "
    "Направляй через анализ веществ и их свойств.",
    "biology": "Используй биологическую терминологию: клетки, гены, экосистемы. "
    "Направляй через связи между концепциями.",
    "cs": "Используй термины программирования: алгоритмы, структуры данных, сложность. "
    "Направляй через анализ задачи и выбор подхода.",
}


def build_socratic_generation_prompt(
    problem: str,
    ground_truth: str,
    domain: str,
    student_message: str,
) -> tuple[str, str]:
    """Build the prompt that asks Cerebras LLM to produce a Socratic response.

    Args:
        problem: The STEM problem text.
        ground_truth: The correct answer (tutor knows it but must NOT reveal it).
        domain: Subject area (math, physics, chemistry, biology, cs).
        student_message: What the student said (from STUDENT_TEMPLATES).

    Returns:
        Tuple of (system_prompt, user_prompt) for Cerebras API.
    """
    domain_hint = DOMAIN_HINTS.get(domain, "")

    system = (
        "Ты — опытный сократический репетитор по STEM. "
        "Твоя задача — сгенерировать ответ тьютора студенту.\n\n"
        "СТРОГИЕ ПРАВИЛА для ответа:\n"
        "1. НИКОГДА не давай готовый ответ, числовой результат или финальную формулу\n"
        "2. НИКОГДА не используй слова: 'ответ', 'решение', 'итого', 'результат'\n"
        "3. Задай 1-2 наводящих вопроса, которые подведут студента к решению\n"
        "4. Дай подсказку про ПЕРВЫЙ шаг, не раскрывая дальнейших\n"
        "5. Кратко признай затруднение студента (1 предложение)\n"
        "6. Используй LaTeX ($...$) для математических выражений\n"
        "7. Длина ответа: 50-150 слов\n"
        "8. Тон: дружелюбный, поддерживающий, но не снисходительный\n"
        "9. Отвечай на русском языке\n"
    )
    if domain_hint:
        system += f"\nПредметная область: {domain_hint}\n"

    user = (
        f"Студент написал: {student_message}\n\n"
        f"Задача: {problem}\n"
        f"Правильный ответ (ТОЛЬКО для твоего понимания, НЕ раскрывай): {ground_truth}\n\n"
        f"Сгенерируй сократический ответ тьютора. "
        f"Используй знание правильного ответа, чтобы направить вопросы "
        f"в нужную сторону, но НЕ выдавай его ни в какой форме."
    )
    return system, user


def build_direct_generation_prompt(
    problem: str,
    ground_truth: str,
    domain: str,
    student_message: str,
) -> tuple[str, str]:
    """Build prompt for generating a DIRECT (non-Socratic) response — the negative example."""
    system = (
        "Ты — репетитор. Дай студенту полное решение задачи с ответом. "
        "Реши пошагово и дай финальный ответ. Не задавай вопросов студенту."
    )
    user = (
        f"Студент спрашивает: {student_message}\n\n"
        f"Задача: {problem}\n"
        f"Правильный ответ: {ground_truth}\n\n"
        f"Дай полное решение с ответом."
    )
    return system, user


# ─── Quality filters ────────────────────────────────────────


def is_good_socratic(response: str) -> bool:
    """Check if response follows Socratic principles."""
    has_question = "?" in response
    no_direct_answer = not any(
        marker in response.lower()
        for marker in ["правильный ответ", "ответ:", "= \\boxed", "решение:"]
    )
    min_length = len(response.split()) >= 20
    max_length = len(response.split()) <= 300
    return has_question and no_direct_answer and min_length and max_length


def is_good_direct(response: str) -> bool:
    """Check if response gives a direct answer (for negative example)."""
    has_answer = any(
        marker in response.lower() for marker in ["ответ", "решение", "итого", "результат", "="]
    )
    min_length = len(response.split()) >= 15
    return has_answer and min_length


# ─── Main pipeline ──────────────────────────────────────────


def generate_pair(
    problem: dict[str, Any],
    client: CerebrasClient,
) -> dict[str, Any] | None:
    """Generate one Socratic + Direct pair for a problem."""
    prompt_text = problem["prompt"]
    truth = problem.get("ground_truth", problem.get("answer", ""))
    domain = problem.get("domain", "math")

    student_msg = random.choice(STUDENT_TEMPLATES).format(problem=prompt_text)

    # Generate Socratic response
    try:
        sys_prompt, user_prompt = build_socratic_generation_prompt(
            problem=prompt_text,
            ground_truth=truth,
            domain=domain,
            student_message=student_msg,
        )
        socratic_response = client.generate(
            prompt=user_prompt,
            system_prompt=sys_prompt,
            temperature=0.7,
            max_tokens=1024,
        )
    except NotImplementedError:
        logger.error("build_socratic_generation_prompt not implemented. See TODO(human).")
        sys.exit(1)
    except Exception as e:
        logger.warning(f"Socratic generation failed: {e}")
        return None

    # Generate Direct response
    try:
        sys_prompt, user_prompt = build_direct_generation_prompt(
            problem=prompt_text,
            ground_truth=truth,
            domain=domain,
            student_message=student_msg,
        )
        direct_response = client.generate(
            prompt=user_prompt,
            system_prompt=sys_prompt,
            temperature=0.3,
            max_tokens=1024,
        )
    except Exception as e:
        logger.warning(f"Direct generation failed: {e}")
        return None

    # Quality filter
    if not is_good_socratic(socratic_response):
        logger.debug("Filtered: Socratic response not good enough")
        return None
    if not is_good_direct(direct_response):
        logger.debug("Filtered: Direct response not good enough")
        return None

    return {
        "student_message": student_msg,
        "socratic_response": socratic_response,
        "direct_response": direct_response,
        "problem": prompt_text,
        "ground_truth": truth,
        "domain": domain,
        "difficulty": problem.get("difficulty", "medium"),
        "answer_type": problem.get("answer_type", "numeric"),
    }


def format_for_kto(pair: dict[str, Any]) -> list[dict[str, Any]]:
    """Format pair as two KTO records (desirable + undesirable)."""
    prompt = [
        {"role": "system", "content": SOCRATIC_SYSTEM},
        {"role": "user", "content": pair["student_message"]},
    ]
    return [
        {
            "prompt": prompt,
            "completion": pair["socratic_response"],
            "label": True,
            "domain": pair["domain"],
            "difficulty": pair["difficulty"],
        },
        {
            "prompt": prompt,
            "completion": pair["direct_response"],
            "label": False,
            "domain": pair["domain"],
            "difficulty": pair["difficulty"],
        },
    ]


def format_for_dpo(pair: dict[str, Any]) -> dict[str, Any]:
    """Format pair as one DPO record (chosen + rejected)."""
    prompt = [
        {"role": "system", "content": SOCRATIC_SYSTEM},
        {"role": "user", "content": pair["student_message"]},
    ]
    return {
        "prompt": prompt,
        "chosen": pair["socratic_response"],
        "rejected": pair["direct_response"],
        "domain": pair["domain"],
        "difficulty": pair["difficulty"],
    }


def main():
    parser = argparse.ArgumentParser(description="Generate Socratic training data via Cerebras")
    parser.add_argument("--input", required=True, help="Input problems JSONL")
    parser.add_argument("--output", required=True, help="Output path prefix (without extension)")
    parser.add_argument("--max-problems", type=int, default=500)
    parser.add_argument("--format", choices=["kto", "dpo", "both"], default="both")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--env-file", default=".env", help="Path to .env with Cerebras keys")
    args = parser.parse_args()

    random.seed(args.seed)
    sys.stdout.reconfigure(encoding="utf-8")

    # Init Cerebras client
    client = CerebrasClient(env_file=args.env_file)
    logger.info(f"Cerebras client ready: {client.get_stats()['keys_available']} API keys")

    # Load problems
    problems = []
    with open(args.input, "r", encoding="utf-8") as f:
        for line in f:
            problems.append(json.loads(line))
    logger.info(f"Loaded {len(problems)} problems from {args.input}")

    # Sample
    if args.max_problems < len(problems):
        problems = random.sample(problems, args.max_problems)
    logger.info(f"Processing {len(problems)} problems with Cerebras Qwen-3-235B")

    # Generate
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    kto_path = Path(f"{args.output}.kto.jsonl") if args.format in ("kto", "both") else None
    dpo_path = Path(f"{args.output}.dpo.jsonl") if args.format in ("dpo", "both") else None

    generated = 0
    filtered = 0

    kto_file = open(kto_path, "w", encoding="utf-8") if kto_path else None
    dpo_file = open(dpo_path, "w", encoding="utf-8") if dpo_path else None

    try:
        for i, problem in enumerate(problems):
            pair = generate_pair(problem, client)

            if pair is None:
                filtered += 1
                continue

            generated += 1

            if kto_file:
                for record in format_for_kto(pair):
                    kto_file.write(json.dumps(record, ensure_ascii=False) + "\n")

            if dpo_file:
                record = format_for_dpo(pair)
                dpo_file.write(json.dumps(record, ensure_ascii=False) + "\n")

            if (i + 1) % 10 == 0:
                stats = client.get_stats()
                logger.info(
                    f"  Progress: {i + 1}/{len(problems)} "
                    f"(generated={generated}, filtered={filtered}, "
                    f"api_calls={stats['total_requests']})"
                )
    finally:
        if kto_file:
            kto_file.close()
        if dpo_file:
            dpo_file.close()

    stats = client.get_stats()
    logger.info(f"Done: {generated} pairs generated, {filtered} filtered out")
    logger.info(f"  API stats: {stats['total_requests']} requests, {stats['total_tokens']} tokens")
    if kto_path:
        logger.info(f"  KTO data: {kto_path} ({generated * 2} records)")
    if dpo_path:
        logger.info(f"  DPO data: {dpo_path} ({generated} records)")


if __name__ == "__main__":
    main()
