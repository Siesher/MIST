"""Apply Cerebras LLM-judge to KTO completions for fair Socratic comparison.

This is a *second pass* over the jsonl produced by eval_kto_on_existing_benchmark.py.
It uses the EXACT same judge prompt + composite scoring formula as evaluate_stage.py
used to score Base and GSPO in compare_base_vs_gspo_*.json — this puts KTO on the
same Socratic measurement scale.

Inputs:
  evaluation/reports/kto_fair_eval_25.jsonl   (incremental from main eval)
Outputs:
  evaluation/reports/kto_fair_eval_25_judged.jsonl   (incremental, resume-safe)

Adds per-entry fields:
  is_correct (Cerebras semantic check), guides_student (0-2), no_answer_leak (0-2),
  scaffolding (0-2), engagement (0-1), socratic_score (0-1 composite), explanation.

Usage:
  .venv\\Scripts\\python.exe scripts/diploma/_judge_kto_with_cerebras.py
  # Reads kto_fair_eval_25.jsonl by default; pass --input/--output to override.
"""

import argparse
import io
import json
import logging
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from training.cerebras_client import CerebrasClient  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Verbatim from training/scripts/evaluate_stage.py — same prompt as Base/GSPO scoring
COMBINED_JUDGE_PROMPT = """\
Оцени ответ сократического репетитора по STEM. Правильный ответ дан только тебе — \
репетитор не должен его раскрывать студенту.

## Условие задачи
{question}

## Правильный ответ (только для твоего анализа)
{ground_truth}

## Ответ репетитора
{response}

## Критерии

**is_correct** (true/false): Ведёт ли педагогическое направление к правильному решению?
- true: подсказки и вопросы методологически верны и ведут к правильному ответу
- false: содержит ошибку в методе, неверное направление или противоречит условию

**guides_student** (0-2): Направляет ли мышление студента?
- 0: даёт готовый ответ или решение без вопросов
- 1: вопросы слишком общие ("Подумай ещё") или не по теме
- 2: конкретные наводящие вопросы, ведущие к решению ("Какая формула связывает F и m?")

**no_answer_leak** (0-2): Скрыт ли правильный ответ?
- 0: числовой/буквенный ответ прямо виден ("x = 2", "ответ: 50 Дж")
- 1: ответ частично раскрыт — метод с подставленными числами или финальная формула
- 2: ответ полностью скрыт — только направление, подсказки, вопросы

**scaffolding** (0-2): Пошаговое выстраивание от простого к сложному?
- 0: нет структуры
- 1: есть элементы структуры, но не последовательное наращивание
- 2: чёткие шаги, каждый строится на предыдущем

**engagement** (0-1): Вовлекает и мотивирует?
- 0: сухо, формально, без обращения к студенту
- 1: обращается к студенту, поддерживает ("Отлично!", "Давай разберёмся вместе")

Верни ТОЛЬКО JSON (без markdown, без текста вне JSON):
{{"is_correct": <true|false>, "guides_student": <0-2>, "no_answer_leak": <0-2>, \
"scaffolding": <0-2>, "engagement": <0-1>, "explanation": "<1-2 предложения на русском>"}}"""


def judge_one(question: str, response: str, ground_truth: str, client: CerebrasClient) -> dict:
    """Single Cerebras judge call with same retry logic as evaluate_stage.py."""
    prompt = COMBINED_JUDGE_PROMPT.format(
        question=question[:400],
        response=response[:800],
        ground_truth=ground_truth,
    )
    max_retries = 5
    for attempt in range(max_retries):
        try:
            raw = client.generate(
                prompt=prompt,
                system_prompt=(
                    "You are an expert evaluator of Socratic STEM tutoring. "
                    "Return ONLY valid JSON, no markdown."
                ),
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
                + scores.get("engagement", 0)
            )
            scores["socratic_score"] = round(total / 7, 3)
            scores["is_correct"] = bool(scores.get("is_correct", False))
            return scores
        except json.JSONDecodeError as e:
            logger.warning("Judge invalid JSON (attempt %d): %s", attempt + 1, str(e)[:120])
            return {"socratic_score": None, "is_correct": None, "judge_error": f"invalid JSON: {e}"}
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait = 2**attempt * 5
                logger.info("Rate limit, waiting %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                time.sleep(wait)
                continue
            logger.warning("Judge failed: %s", str(e)[:200])
            return {"socratic_score": None, "is_correct": None, "judge_error": str(e)}
    return {"socratic_score": None, "is_correct": None, "judge_error": "exhausted retries"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        type=str,
        default=str(ROOT / "evaluation/reports/kto_fair_eval_25.jsonl"),
        help="Input jsonl produced by eval_kto_on_existing_benchmark.py",
    )
    ap.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output jsonl (default: <input>_judged.jsonl)",
    )
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output) if args.output else in_path.with_name(
        in_path.stem + "_judged.jsonl"
    )
    if not in_path.exists():
        logger.error("Input not found: %s", in_path)
        return

    # Resume support: skip already-judged idx
    judged_idxs: set[int] = set()
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    if "idx" in e and "socratic_score" in e and e.get("socratic_score") is not None:
                        judged_idxs.add(e["idx"])
                except json.JSONDecodeError:
                    continue
        logger.info("Resume: %d entries already judged", len(judged_idxs))

    client = CerebrasClient()
    logger.info("Cerebras client initialized: model=%s", client.model)

    n_judged = 0
    n_skipped = 0
    n_errored = 0
    with open(in_path, "r", encoding="utf-8") as fin, open(out_path, "a", encoding="utf-8") as fout:
        for line in fin:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "idx" not in entry or entry.get("error"):
                continue
            if entry["idx"] in judged_idxs:
                n_skipped += 1
                continue

            visible = entry.get("visible", "")
            if not visible.strip():
                # No visible response → judge can't grade Socratic quality
                judgment = {
                    "is_correct": False,
                    "guides_student": 0,
                    "no_answer_leak": 2,  # nothing to leak
                    "scaffolding": 0,
                    "engagement": 0,
                    "socratic_score": 0.0,
                    "explanation": "Visible response is empty (model exhausted thinking budget).",
                }
            else:
                judgment = judge_one(
                    question=entry.get("user_prompt", ""),
                    response=visible,
                    ground_truth=str(entry.get("truth", "")),
                    client=client,
                )

            entry.update(judgment)
            fout.write(json.dumps(entry, ensure_ascii=False) + "\n")
            fout.flush()

            if judgment.get("socratic_score") is None:
                n_errored += 1
                marker = "ERR"
            else:
                n_judged += 1
                marker = f"socratic={judgment['socratic_score']:.2f} correct={judgment['is_correct']}"
            logger.info(
                "  idx=%d [%s/%s] %s",
                entry["idx"],
                entry.get("domain"),
                entry.get("difficulty"),
                marker,
            )

    logger.info("Done. judged=%d, skipped=%d (already done), errored=%d", n_judged, n_skipped, n_errored)
    logger.info("Output: %s", out_path)


if __name__ == "__main__":
    main()
