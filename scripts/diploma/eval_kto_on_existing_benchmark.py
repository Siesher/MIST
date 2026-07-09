#!/usr/bin/env python3
"""Evaluate KTO model on the same 143-problem benchmark used for Base vs GSPO.

Reuses prompts + ground truth from the existing comparison report:
    evaluation/reports/compare_base_vs_gspo_20260331_115146.json

For each problem:
  1. Query Ollama (mits-tutor-9b-kto) with the same system prompt.
  2. Score response using a dual-metric approach (thinking vs visible).
  3. Aggregate per-domain / per-difficulty.

Output:
    evaluation/reports/kto_eval_<timestamp>.json

Usage:
    python scripts/diploma/eval_kto_on_existing_benchmark.py [--max-problems N]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from training.scripts.evaluate_stage import extract_answer, verify_answer  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_KTO_MODEL = "mits-tutor-9b-kto"
SOURCE_REPORT = (
    _PROJECT_ROOT / "evaluation/reports/compare_base_vs_gspo_20260331_115146.json"
)

SYSTEM_PROMPT_CALC = (
    "Ты — репетитор по STEM. Реши задачу пошагово и запиши финальный ответ в \\boxed{}."
)
SYSTEM_PROMPT_MC = "Проанализируй задачу и выбери правильный ответ (A, B, C или D)."

# Socratic prompt — taken from evaluate_stage.py (SYSTEM_PROMPT_TUTOR).
# Used to test KTO in its native mode of operation (Socratic tutoring).
SYSTEM_PROMPT_TUTOR = (
    "Ты - сократический учитель по STEM (математика, физика, химия, биология, информатика).\n\n"
    "ПРАВИЛА:\n"
    "- НИКОГДА не давай готовый ответ\n"
    "- Задавай 1-2 наводящих вопроса\n"
    "- Давай подсказки, которые направляют мышление\n"
    "- Хвали правильные шаги студента\n"
    "- Используй LaTeX ($...$) для математических выражений\n"
    "- Отвечай на русском языке"
)


def pick_system_prompt(answer_type: str, mode: str = "calc") -> str:
    """Choose system prompt based on evaluation mode.

    mode='calc'  → matches evaluate_stage.py policy for fair Base/GSPO comparison
    mode='tutor' → uses Socratic prompt — KTO's native operating mode
    """
    if mode == "tutor":
        return SYSTEM_PROMPT_TUTOR
    return SYSTEM_PROMPT_MC if answer_type == "mc_letter" else SYSTEM_PROMPT_CALC


def balanced_subset(problems: list, n_per_domain: int) -> list:
    """Take first n_per_domain problems from each domain for balanced sampling."""
    by_domain: dict[str, list] = {}
    for p in problems:
        by_domain.setdefault(p["domain"], []).append(p)
    out = []
    for domain, items in sorted(by_domain.items()):
        out.extend(items[:n_per_domain])
    return out


def load_benchmark() -> list[dict[str, Any]]:
    """Extract the 143 problems (with ground truth) from the existing report."""
    with open(SOURCE_REPORT, "r", encoding="utf-8") as f:
        report = json.load(f)
    completions = report["model_a"]["results"]["completions_by_idx"]
    problems = []
    for idx, item in completions.items():
        problems.append(
            {
                "idx": int(idx),
                "prompt": item["prompt"],
                "truth": item.get("truth"),
                "domain": item.get("domain"),
                "difficulty": item.get("difficulty"),
                "answer_type": item.get("answer_type", "numeric"),
            }
        )
    problems.sort(key=lambda p: p["idx"])
    return problems


def query_kto(
    prompt: str,
    model: str,
    answer_type: str = "numeric",
    num_predict: int = -1,
    num_ctx: int = 32768,
    num_batch: int = 512,
    timeout: int = 3600,
    prompt_mode: str = "calc",
) -> dict[str, Any]:
    """Query KTO via Ollama. Returns content, thinking, prompt, timing.

    Defaults match evaluate_stage.py _build_ollama_options(mode="full_judge"):
      num_predict=-1, num_ctx=32768, num_batch=512, temperature=0.0.
    This is the SAME protocol used to evaluate Base and GSPO in
    compare_base_vs_gspo_*.json — fair apples-to-apples comparison.
    """
    sys_prompt = pick_system_prompt(answer_type, mode=prompt_mode)
    start = time.time()
    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {
                    "num_predict": num_predict,
                    "num_ctx": num_ctx,
                    "num_batch": num_batch,
                    "temperature": 0.0,
                },
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        elapsed = time.time() - start
        msg = data.get("message", {})
        return {
            "system_prompt": sys_prompt,
            "user_prompt": prompt,
            "content": msg.get("content", ""),
            "thinking": msg.get("thinking", ""),
            "elapsed": round(elapsed, 1),
            "tokens": data.get("eval_count", 0),
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "error": None,
        }
    except Exception as exc:
        logger.error("Ollama error: %s", exc)
        return {
            "system_prompt": sys_prompt,
            "user_prompt": prompt,
            "content": "",
            "thinking": "",
            "elapsed": round(time.time() - start, 1),
            "tokens": 0,
            "prompt_tokens": 0,
            "error": str(exc),
        }


def score_kto_response(
    thinking: str,
    visible: str,
    truth: str | None,
    domain: str,
    answer_type: str,
) -> dict[str, Any]:
    """Score a KTO response with dual metrics: thinking vs visible.

    KTO is trained to be Socratic — it should know the answer (thinking_correct)
    but not reveal it (NOT visible_leaks_answer). The composite metric
    socratic_compliant captures this dual behavior.

    Args:
        thinking: content of <think>...</think> (CoT, returned in `message.thinking`)
        visible: visible response (returned in `message.content`)
        truth: ground-truth answer string, or None for open-ended problems
        domain, answer_type: passed to verify_answer for tolerance/MC handling

    Returns dict with:
        thinking_correct: bool — does the CoT contain the correct answer?
        visible_leaks_answer: bool — does the visible response reveal it?
        socratic_compliant: bool — thinking_correct AND NOT visible_leaks_answer
        thinking_extracted: str — what was pulled from the CoT
        visible_extracted: str — what was pulled from the visible part
    """
    # Open-ended problem: no ground truth → can't compute any flag
    if truth is None or str(truth).strip() == "":
        return {
            "correct": False,
            "thinking_correct": False,
            "visible_leaks_answer": False,
            "socratic_compliant": False,
            "thinking_extracted": "",
            "visible_extracted": "",
            "full_extracted": "",
            "open_ended": True,
            "visible_empty": not bool(visible),
        }

    visible_empty = not bool(visible.strip()) if visible else True

    # — Base/GSPO-comparable metric: extract from thinking+visible combined —
    # evaluate_stage.py strips </think> and takes the rest, but with Ollama RENDERER
    # qwen3.5 the runner already separates thinking and content. We reconstruct full
    # text the same way old pipeline saw it, to keep extract_answer behavior identical.
    full_text = (thinking + "\n" + visible) if thinking else visible
    full_ans = extract_answer(full_text) if full_text else ""
    correct = bool(full_ans) and verify_answer(full_ans, str(truth), domain, answer_type)

    # — KTO-specific dual metrics —
    thinking_ans = extract_answer(thinking) if thinking else ""
    visible_ans = extract_answer(visible) if visible else ""
    thinking_correct = bool(thinking_ans) and verify_answer(
        thinking_ans, str(truth), domain, answer_type
    )
    visible_leaks_answer = bool(visible_ans) and verify_answer(
        visible_ans, str(truth), domain, answer_type
    )
    # Socratic compliance is only meaningful if model produced visible output.
    # Empty visible = budget exhausted in <think>, not "model held back" — a failure mode.
    socratic_compliant = (
        thinking_correct and not visible_leaks_answer and not visible_empty
    )

    return {
        "correct": correct,
        "thinking_correct": thinking_correct,
        "visible_leaks_answer": visible_leaks_answer,
        "socratic_compliant": socratic_compliant,
        "thinking_extracted": thinking_ans,
        "visible_extracted": visible_ans,
        "full_extracted": full_ans,
        "open_ended": False,
        "visible_empty": visible_empty,
    }


def aggregate_results(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute overall + per-domain + per-difficulty stats (closed-ended only)."""
    closed = [r for r in results if not r.get("open_ended")]
    n_total = len(results)
    n_closed = len(closed)
    if n_closed == 0:
        return {"n_total": n_total, "n_closed": 0, "note": "no closed-ended problems"}

    metrics = (
        "correct",
        "thinking_correct",
        "visible_leaks_answer",
        "socratic_compliant",
        "visible_empty",
    )

    overall = {"n_total": n_total, "n_closed": n_closed}
    for m in metrics:
        overall[m] = sum(r[m] for r in closed) / n_closed

    def _bucket(key: str) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for r in closed:
            label = r.get(key) or "unknown"
            slot = out.setdefault(label, {"n": 0, **{m: 0 for m in metrics}})
            slot["n"] += 1
            for m in metrics:
                slot[m] += int(r[m])
        for slot in out.values():
            for m in metrics:
                slot[m] = slot[m] / slot["n"]
        return out

    return {
        "overall": overall,
        "by_domain": _bucket("domain"),
        "by_difficulty": _bucket("difficulty"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-problems", type=int, default=None, help="Limit total")
    ap.add_argument("--balanced", type=int, default=None, help="Take N problems per domain")
    ap.add_argument("--out", type=str, default=None, help="Output JSON path")
    ap.add_argument(
        "--model",
        type=str,
        default=DEFAULT_KTO_MODEL,
        help="Ollama model (e.g. mits-tutor-9b-kto, mits-tutor-9b-fast)",
    )
    ap.add_argument(
        "--prompt-mode",
        type=str,
        choices=["calc", "tutor"],
        default="calc",
        help="calc=Base/GSPO-comparable, tutor=Socratic native mode",
    )
    ap.add_argument(
        "--num-predict",
        type=int,
        default=-1,
        help="Max tokens per response (-1 = unlimited; matches evaluate_stage.py)",
    )
    ap.add_argument(
        "--num-ctx",
        type=int,
        default=32768,
        help="KV-cache context size (32768 matches evaluate_stage.py mode='full_judge')",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing jsonl checkpoint (skip already-completed idx)",
    )
    args = ap.parse_args()
    logger.info(
        "Model=%s  prompt_mode=%s  num_predict=%d  num_ctx=%d",
        args.model,
        args.prompt_mode,
        args.num_predict,
        args.num_ctx,
    )

    problems = load_benchmark()
    if args.balanced:
        problems = balanced_subset(problems, args.balanced)
        logger.info("Balanced subset: %d/domain → %d total", args.balanced, len(problems))
    elif args.max_problems:
        problems = problems[: args.max_problems]
    logger.info("Loaded %d problems from %s", len(problems), SOURCE_REPORT.name)

    # Incremental jsonl checkpoint — survives kills/timeouts
    out_path = (
        Path(args.out)
        if args.out
        else _PROJECT_ROOT / f"evaluation/reports/kto_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_path.with_suffix(".jsonl")
    completed_idx: set[int] = set()
    results: list[dict[str, Any]] = []
    if args.resume and jsonl_path.exists():
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if "idx" in entry and not entry.get("error"):
                        completed_idx.add(entry["idx"])
                        results.append(entry)
                except json.JSONDecodeError:
                    continue
        logger.info("Resume: %d problems already done in %s", len(completed_idx), jsonl_path.name)

    jsonl_fh = open(jsonl_path, "a", encoding="utf-8")
    t0 = time.time()
    for i, p in enumerate(problems, 1):
        if p["idx"] in completed_idx:
            logger.info("[%d/%d] idx=%d SKIP (already done)", i, len(problems), p["idx"])
            continue
        logger.info(
            "[%d/%d] %s/%s idx=%d", i, len(problems), p["domain"], p["difficulty"], p["idx"]
        )
        resp = query_kto(
            p["prompt"],
            model=args.model,
            answer_type=p["answer_type"],
            num_predict=args.num_predict,
            num_ctx=args.num_ctx,
            prompt_mode=args.prompt_mode,
        )
        if resp["error"]:
            logger.warning("  error: %s", resp["error"])
            err_entry = {"idx": p["idx"], "domain": p["domain"], "difficulty": p["difficulty"],
                         "error": True, "error_msg": resp["error"], "elapsed": resp["elapsed"]}
            jsonl_fh.write(json.dumps(err_entry, ensure_ascii=False) + "\n")
            jsonl_fh.flush()
            continue

        # Ollama with RENDERER qwen3.5 returns thinking and visible separately.
        # Fallback: if `thinking` field is empty but content has <think> tags, split.
        thinking = resp["thinking"]
        visible = resp["content"]
        if not thinking and "</think>" in visible:
            parts = visible.split("</think>", 1)
            thinking = parts[0].replace("<think>", "").strip()
            visible = parts[1].strip()

        scores = score_kto_response(
            thinking=thinking,
            visible=visible,
            truth=p["truth"],
            domain=p["domain"],
            answer_type=p["answer_type"],
        )

        entry = {
            "idx": p["idx"],
            "domain": p["domain"],
            "difficulty": p["difficulty"],
            "answer_type": p["answer_type"],
            "truth": p["truth"],
            "user_prompt": p["prompt"],
            "system_prompt": resp["system_prompt"],
            "thinking": thinking,
            "visible": visible,
            "thinking_len": len(thinking),
            "visible_len": len(visible),
            "tokens": resp["tokens"],
            "prompt_tokens": resp["prompt_tokens"],
            "elapsed": resp["elapsed"],
            **scores,
        }
        results.append(entry)

        # Incremental write — survives kills/timeouts/system reboots
        jsonl_fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        jsonl_fh.flush()

        # Two markers: accuracy-flag (✓/✗) for Base/GSPO comparison + behavior-flag for KTO
        acc = "✓" if scores.get("correct") else "✗"
        if scores.get("open_ended"):
            beh = "open"
        elif scores["socratic_compliant"]:
            beh = "socratic"
        elif scores["visible_leaks_answer"]:
            beh = "leak"
        elif scores.get("visible_empty"):
            beh = "no-visible"
        else:
            beh = "miss"
        logger.info(
            "  acc=%s beh=%s full=%s think=%s vis=%s truth=%s",
            acc,
            beh,
            scores.get("full_extracted", "")[:25],
            scores.get("thinking_extracted", "")[:25],
            scores.get("visible_extracted", "")[:25],
            str(p["truth"])[:25],
        )

    jsonl_fh.close()
    elapsed_total = time.time() - t0
    if results:
        logger.info("Total time: %.1f min (%.1f s/problem)", elapsed_total / 60, elapsed_total / len(results))
    else:
        logger.warning("No results to summarize")
        return

    summary = aggregate_results(results)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "model": args.model,
                "prompt_mode": args.prompt_mode,
                "num_predict": args.num_predict,
                "num_ctx": args.num_ctx,
                "source_benchmark": str(SOURCE_REPORT.name),
                "n_problems": len(results),
                "elapsed_minutes": round(elapsed_total / 60, 2),
                "timestamp": datetime.now().isoformat(),
                "summary": summary,
                "details": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    logger.info("Saved: %s (jsonl: %s)", out_path, jsonl_path)


if __name__ == "__main__":
    main()
