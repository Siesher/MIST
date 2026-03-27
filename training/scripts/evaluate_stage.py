#!/usr/bin/env python3
"""
Per-stage model evaluation script for MITS training pipeline.

Evaluates a model checkpoint after each training stage by:
1. Loading the adapter from HuggingFace (or local path)
2. Running evaluation on the eval dataset
3. Optionally converting to GGUF and evaluating via Ollama
4. Producing a JSON report with per-domain accuracy metrics

Supports two modes:
  - colab:  Uses Unsloth to load adapter + evaluate on GPU (fast)
  - local:  Uses Ollama API to evaluate a GGUF/model (no GPU needed)

Usage:
    # Evaluate on Colab (after each training stage)
    python evaluate_stage.py --mode colab \
        --adapter Siesher/mits-qwen3-4b-gspo \
        --stage gspo \
        --eval-data training/data/eval_dataset.jsonl

    # Evaluate locally via Ollama
    python evaluate_stage.py --mode local \
        --model mits-tutor-qwen3-4b-q4_k_m \
        --stage gspo \
        --eval-data training/data/eval_dataset.jsonl

    # Evaluate + export GGUF on Colab
    python evaluate_stage.py --mode colab \
        --adapter Siesher/mits-qwen3-4b-gspo \
        --stage gspo \
        --export-gguf --quantization q4_k_m

    # Compare all stages
    python evaluate_stage.py compare \
        --reports-dir evaluation/reports/
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import json
import logging
import os
import random
import re
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

try:
    from training.cerebras_client import CerebrasClient

    HAS_CEREBRAS = True
except ImportError:
    HAS_CEREBRAS = False
    CerebrasClient = None  # type: ignore[assignment,misc]

# Pipeline stages in order (SFT removed — Instruct base; RAFT++ replaced by KTO)
STAGES = ["base", "gspo", "kto", "dpo"]
STAGE_HF_REPOS = {
    "gspo": "Siesher/mits-qwen3-9b-gspo",
    "kto": "Siesher/mits-qwen3-9b-kto",
    "dpo": "Siesher/mits-qwen3-9b-final",
}

SYSTEM_PROMPT_CALC = (
    "Ты — репетитор по STEM. Реши задачу пошагово и запиши финальный ответ в \\boxed{}."
)
SYSTEM_PROMPT_MC = "Проанализируй задачу и выбери правильный ответ (A, B, C или D)."

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


# ─── Combined correctness + Socratic quality judge ───────────


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


def evaluate_combined_quality(
    question: str,
    response: str,
    ground_truth: str,
    cerebras_client: Any,
) -> Dict[str, Any]:
    """Single Cerebras call: correctness + Socratic quality rubric.

    Args:
        question: STEM problem text.
        response: Visible tutor response (thinking stripped).
        ground_truth: Correct answer (shown only to the judge).
        cerebras_client: CerebrasClient instance.

    Returns:
        Dict with is_correct (bool), guides_student, no_answer_leak, scaffolding,
        engagement (int scores), socratic_score (0-1 composite), explanation (str).
    """
    prompt = COMBINED_JUDGE_PROMPT.format(
        question=question[:400],
        response=response[:800],
        ground_truth=ground_truth,
    )

    try:
        raw = cerebras_client.generate(
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

        # Composite Socratic score: (guides×2 + no_leak×2 + scaffold×2 + engage×1) / 7
        total = (
            scores.get("guides_student", 0)
            + scores.get("no_answer_leak", 0)
            + scores.get("scaffolding", 0)
            + scores.get("engagement", 0)
        )
        scores["socratic_score"] = round(total / 7, 3)
        # Normalise is_correct to bool
        scores["is_correct"] = bool(scores.get("is_correct", False))
        return scores

    except json.JSONDecodeError as e:
        logger.warning(f"Judge returned invalid JSON: {raw[:200]}... Error: {e}")
        logger.warning(f"Combined judge returned invalid JSON: {raw[:200]}... Error: {e}")
        return {"socratic_score": None, "is_correct": None, "error": f"invalid JSON: {e}"}
    except Exception as e:
        logger.warning(f"Combined judge failed: {e}")
        return {"socratic_score": None, "is_correct": None, "error": str(e)}


def stratified_sample(problems: List[Dict], n: int, seed: int = 42) -> List[Dict]:
    """Sample N problems proportionally by (domain, difficulty).

    Groups problems by (domain, difficulty), then allocates samples
    proportionally to each group's size. Handles remainders via
    largest-remainder method to hit exactly N.

    Falls back to random sampling if a group is too small for its allocation.
    """
    if n >= len(problems):
        return problems

    rng = random.Random(seed)

    groups = defaultdict(list)
    for p in problems:
        key = (p.get("domain", "math"), p.get("difficulty", "medium"))
        groups[key].append(p)

    total = len(problems)
    allocations = {}
    remainders = {}

    for key, group in groups.items():
        exact = n * len(group) / total
        base = int(exact)
        base = min(base, len(group))
        allocations[key] = base
        remainders[key] = exact - base

    # Handle remainders via largest-remainder method
    remainder_count = n - sum(allocations.values())
    if remainder_count > 0:
        sorted_keys = sorted(remainders.keys(), key=lambda k: remainders[k], reverse=True)
        for i in range(remainder_count):
            key = sorted_keys[i % len(sorted_keys)]
            allocations[key] += 1

    # Sample from each group and combine results
    result = []
    for key, group in groups.items():
        result.extend(rng.sample(group, allocations[key]))

    rng.shuffle(result)
    return result


def check_format_compliance(completion: str) -> Dict[str, Any]:
    """Check format compliance of a model completion."""
    # Strip thinking block for analysis of the visible response
    visible = completion.split("</think>")[-1].strip() if "</think>" in completion else completion

    has_boxed = bool(re.search(r"\\boxed\{", visible))
    step_markers = [
        r"[Шш]аг\s*\d",  # Шаг 1, шаг 2
        r"[Сс]ледовательно",  # Следовательно
        r"[Пп]одставим",  # Подставим
        r"[Нн]айд[её]м",  # Найдём
        r"[Рр]ешени[ея]",  # Решение
        r"[Оо]твет\s*:",  # Ответ:
        r"\d\)\s",  # 1) 2) numbered steps
        r"(?:во-первых|во-вторых)",  # во-первых, во-вторых
    ]
    has_steps = any(re.search(p, visible) for p in step_markers)
    has_thinking = "<think>" in completion and "</think>" in completion

    return {
        "has_boxed": has_boxed,
        "has_steps": has_steps,
        "has_thinking": has_thinking,
        "response_length": len(completion),
    }


def load_eval_dataset(path: str) -> List[Dict]:
    """Load evaluation dataset from JSONL."""
    problems = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                problems.append(json.loads(line))
    logger.info(f"Loaded {len(problems)} eval problems from {path}")
    return problems


def _clean_boxed(val: str) -> str:
    """Clean boxed value: strip \\text{}, remove comma separators."""
    # \text{...} or \text {...} -> contents
    val = re.sub(r"\\text\s*\{([^}]*)\}", r"\1", val)
    # Remove LaTeX formatting
    val = val.replace("\\,", "").replace("\\;", "").replace("\\!", "")
    # Remove units (руб, $, см, Дж, etc.) but keep the number
    val = re.sub(r"\s*(?:руб|долл|\$|см|м|кг|Дж|л|г)\.?\s*$", "", val).strip()
    # Remove comma thousand-separators: 276,000 -> 276000
    val = re.sub(r"(\d),(\d{3})\b", r"\1\2", val)
    val = re.sub(r"(\d),(\d{3})\b", r"\1\2", val)  # second pass for millions
    return val.strip()


def extract_answer(text: str) -> str:
    """Extract answer from model output."""
    # Strip thinking block
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    if not text:
        return ""
    # Try \boxed{}
    boxed = re.findall(r"\\boxed\{([^}]+)\}", text)
    if boxed:
        return _clean_boxed(boxed[-1])
    # Try "Ответ: X" / "Ответ — X" / "Answer: X" (colon, equals, em-dash, hyphen)
    # First try to extract just a letter/number after ответ marker
    answer_letter = re.search(
        r"(?:правильный\s+)?(?:ответ|answer)\s*[:=—–\-]\s*\*{0,2}\s*([A-DА-Гa-dа-г])\b",
        text,
        re.IGNORECASE,
    )
    if answer_letter:
        return answer_letter.group(1).strip()
    # Then try broader match for numeric/text answers
    answer_match = re.search(
        r"(?:правильный\s+)?(?:ответ|answer|вариант(?:\s+ответа)?)\s*[:=—–\-]\s*(.+?)(?:\.\s|$)",
        text,
        re.IGNORECASE,
    )
    if answer_match:
        return answer_match.group(1).strip()
    # Try "вариант **X**" / "вариант X " pattern (last occurrence)
    variant_match = re.findall(
        r"вариант\s+\*{0,2}([A-DА-Гa-dа-г])\b",
        text,
        re.IGNORECASE,
    )
    if variant_match:
        return variant_match[-1].strip()
    # Try bold letter at end: **X** or **X. ... ** (common GSPO output pattern)
    bold_match = re.findall(r"\*\*\s*([A-DА-Гa-dа-г])\s*[\.\)]?\s*[^*]*\*\*", text)
    if bold_match:
        return bold_match[-1].strip()
    # Try standalone bold letter near end (last 300 chars)
    tail = text[-300:] if len(text) > 300 else text
    bold_tail = re.findall(r"\*\*([A-DА-Гa-dа-г])\*\*", tail)
    if bold_tail:
        return bold_tail[-1].strip()
    # Try last number (strip comma separators first)
    cleaned = re.sub(r"(\d),(\d{3})\b", r"\1\2", text)
    numbers = re.findall(r"[-+]?\d*\.?\d+", cleaned)
    return numbers[-1] if numbers else ""


def _normalize_number(s: str) -> str:
    """Normalize number string: remove comma separators, %, units."""
    s = re.sub(r"(\d),(\d{3})\b", r"\1\2", s)  # 276,000 -> 276000
    s = re.sub(r"(\d),(\d{3})\b", r"\1\2", s)  # second pass (1,234,567)
    s = re.sub(r"(?<=\d),(?=\d)", ".", s)  # European decimal: 0,16 -> 0.16
    s = re.sub(r"\\text\s*\{[^}]*\}", "", s)  # \text{...}
    s = s.replace("\\,", "").replace("\\;", "")
    return s.strip()


def verify_answer(extracted: str, truth: str, domain: str, answer_type: str = "numeric") -> bool:
    """Verify if extracted answer matches ground truth."""
    extracted = str(extracted) if extracted is not None else ""
    truth = str(truth) if truth is not None else ""

    if not extracted or not truth:
        return False

    extracted = extracted.strip().lower()
    truth = truth.strip().lower()

    # Exact match
    if extracted == truth:
        return True

    # MC letter match
    if answer_type == "mc_letter":
        # Normalize Cyrillic АБВГ -> Latin ABCD for comparison
        cyrillic_to_latin = str.maketrans("АБВГабвгАБВГ", "ABCDabcdABCD")

        def find_mc_letter(s: str) -> str | None:
            s_norm = s.translate(cyrillic_to_latin)
            m = re.search(r"[a-d]", s_norm, re.IGNORECASE)
            return m.group(0).upper() if m else None

        ext_l = find_mc_letter(extracted)
        truth_l = find_mc_letter(truth)
        if ext_l and truth_l:
            return ext_l == truth_l
        return False

    # Normalize numbers
    extracted_n = _normalize_number(extracted)
    truth_n = _normalize_number(truth)

    # Handle percentage vs fraction: 50% == 0.5, 25% == 0.25
    def to_float_pct(s: str) -> float | None:
        # Match both real % and escaped \%
        m = re.search(r"([-+]?\d*\.?\d+)\s*\\?%", s)
        if m:
            return float(m.group(1)) / 100.0
        nums = re.findall(r"[-+]?\d*\.?\d+", s)
        return float(nums[-1]) if nums else None

    # Numeric comparison
    try:
        e = to_float_pct(extracted_n)
        t = to_float_pct(truth_n)
        if e is not None and t is not None:
            if abs(t) < 1e-10:
                return abs(e - t) < 1e-6
            return abs(e - t) / max(abs(t), 1e-10) < 0.05
    except (ValueError, IndexError):
        pass

    # Symbolic comparison (if sympy available)
    try:
        import sympy

        pred = sympy.sympify(extracted_n)
        gold = sympy.sympify(truth_n)
        return sympy.simplify(pred - gold) == 0
    except Exception:
        pass

    return False


# ─── Hybrid verification: SymPy + LLM fallback ───────────────


def _verify_with_llm_judge(
    completion: str,
    question: str,
    truth: str,
    domain: str,
    cerebras_client: Any,
) -> bool:
    """Ask Cerebras to verify if the model's full response contains the correct answer.

    Called when extract_answer() failed to find any answer pattern in the completion.
    The LLM sees the full visible response (thinking stripped) and judges correctness.
    """
    visible = completion.split("</think>")[-1].strip() if "</think>" in completion else completion
    prompt = (
        f"A student solved this {domain} problem. Did they get it right?\n\n"
        f"Problem: {question[:300]}\n"
        f"Correct answer: {truth}\n"
        f"Student response: {visible[:600]}\n\n"
        f"Reply ONLY with YES or NO."
    )
    try:
        raw = cerebras_client.generate(prompt=prompt, max_tokens=5)
        return "YES" in raw.strip().upper()
    except Exception as e:
        logger.debug(f"LLM judge fallback failed: {e}")
        return False


def _sample_uniform_150(problems: List[Dict], seed: int = 42) -> List[Dict]:
    """Sample exactly 10 items per (domain, difficulty) cell = 150 total.

    5 domains × 3 difficulties = 15 cells × 10 = 150.
    Cells with fewer than 10 items contribute all available items.
    """
    rng = random.Random(seed)
    groups: Dict[Any, list] = defaultdict(list)
    for p in problems:
        key = (p.get("domain", "math"), p.get("difficulty", "medium"))
        groups[key].append(p)

    result = []
    for key in sorted(groups):
        group = groups[key]
        n = min(10, len(group))
        result.extend(rng.sample(group, n))
    rng.shuffle(result)
    cell_summary = ", ".join(f"{k[0]}/{k[1]}={min(10, len(v))}" for k, v in sorted(groups.items()))
    logger.info(f"eval-150: {len(result)} problems from {len(groups)} cells ({cell_summary})")
    return result


def evaluate_combined_pass(
    model_name: str,
    problems: List[Dict],
    ollama_host: str,
    cerebras_client: Any,
    n_judge: int = 75,
    seed: int = 42,
) -> Dict[str, Any]:
    """Combined Socratic + correctness eval in a single Cerebras call per problem.

    Flow per problem:
      1. Ollama call with SYSTEM_PROMPT_TUTOR → tutoring response (no \boxed{} expected)
      2. Cerebras call with COMBINED_JUDGE_PROMPT → {is_correct, guides_student,
         no_answer_leak, scaffolding, engagement, socratic_score}

    n_judge=75: covers all 15 (domain×difficulty) cells with 5 examples each —
    the minimum for reliable per-cell subgroup analysis (±11% margin at 95% CI).
    """
    import requests

    rng = random.Random(seed)
    sample = rng.sample(problems, min(n_judge, len(problems)))
    scores_list = []

    logger.info(f"Combined judge pass: {len(sample)} problems via {model_name} → Cerebras...")
    session = requests.Session()

    for i, p in enumerate(sample):
        truth = p.get("ground_truth", p.get("answer", ""))
        try:
            # Step 1: tutoring response from Ollama
            resp = session.post(
                f"{ollama_host}/api/chat",
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT_TUTOR},
                        {"role": "user", "content": p["prompt"]},
                    ],
                    "stream": False,
                    "options": _build_ollama_options("socratic"),
                    "think": False,
                    "cache_prompt": True,  # reuse KV for SYSTEM_PROMPT_TUTOR prefix
                },
                timeout=90,
            )
            if resp.status_code != 200:
                continue
            content = resp.json().get("message", {}).get("content", "")

            # Step 2: single Cerebras call — correctness + Socratic rubric
            result = evaluate_combined_quality(
                question=p["prompt"],
                response=content,
                ground_truth=truth,
                cerebras_client=cerebras_client,
            )
            if result.get("socratic_score") is not None:
                result["domain"] = p.get("domain", "unknown")
                result["difficulty"] = p.get("difficulty", "unknown")
                scores_list.append(result)

            if (i + 1) % 10 == 0:
                done = len(scores_list)
                avg_s = sum(s["socratic_score"] for s in scores_list) / done if done else 0
                correct = sum(1 for s in scores_list if s.get("is_correct")) / done if done else 0
                logger.info(f"  [{i + 1}/{len(sample)}] socratic={avg_s:.3f} correct={correct:.2%}")
        except Exception as e:
            logger.debug(f"Combined judge failed for problem {i}: {e}")

    if not scores_list:
        return {"socratic_score": None, "is_correct_rate": None, "n_judged": 0}

    n = len(scores_list)
    avg = lambda key: sum(s.get(key, 0) for s in scores_list) / n

    # Per-domain breakdown
    by_domain: Dict[str, list] = defaultdict(list)
    for s in scores_list:
        by_domain[s["domain"]].append(s)
    domain_summary = {
        d: {
            "socratic_score": round(sum(x["socratic_score"] for x in v) / len(v), 3),
            "is_correct_rate": round(sum(1 for x in v if x.get("is_correct")) / len(v), 3),
            "n": len(v),
        }
        for d, v in by_domain.items()
    }

    return {
        "socratic_score": round(avg("socratic_score"), 3),
        "is_correct_rate": round(sum(1 for s in scores_list if s.get("is_correct")) / n, 3),
        "guides_student": round(avg("guides_student"), 3),
        "no_answer_leak": round(avg("no_answer_leak"), 3),
        "scaffolding": round(avg("scaffolding"), 3),
        "engagement": round(avg("engagement"), 3),
        "per_domain": domain_summary,
        "n_judged": n,
    }


# ─── In-notebook evaluation (model already loaded) ───────────


def evaluate_with_model(
    model,
    tokenizer,
    eval_problems: List[Dict],
    max_samples: int = 0,
    batch_size: int = 4,
    max_new_tokens: int = 768,
    completions_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate an already-loaded model on eval problems (for use inside notebooks).

    Unlike evaluate_colab(), this does NOT load the model — it uses
    the model/tokenizer that are already in GPU memory from training.
    """
    import torch
    from unsloth import FastLanguageModel

    # Qwen3.5 returns Processor (multimodal) — unwrap to plain tokenizer
    if not hasattr(tokenizer, "vocab_size") and hasattr(tokenizer, "tokenizer"):
        tokenizer = tokenizer.tokenizer

    FastLanguageModel.for_inference(model)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    problems = eval_problems[:max_samples] if max_samples > 0 else eval_problems

    # Prepare completions JSONL file for full response logging
    completions_file = None
    if completions_path:
        os.makedirs(os.path.dirname(completions_path) or ".", exist_ok=True)
        completions_file = open(completions_path, "w", encoding="utf-8")
        logger.info(f"Saving full completions to {completions_path}")

    results = defaultdict(lambda: {"total": 0, "correct": 0})
    diff_results = defaultdict(lambda: {"total": 0, "correct": 0})
    completions_log = []
    total_tokens = 0

    logger.info(f"Evaluating {len(problems)} problems (batch_size={batch_size})...")
    start_time = time.time()

    for batch_start in range(0, len(problems), batch_size):
        batch = problems[batch_start : batch_start + batch_size]

        prompts = []
        for p in batch:
            sys_prompt = (
                SYSTEM_PROMPT_MC if p.get("answer_type") == "mc_letter" else SYSTEM_PROMPT_CALC
            )
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": p["prompt"]},
            ]
            prompts.append(
                tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            )

        inputs = tokenizer(
            text=prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        ).to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                temperature=1.0,
            )

        for i, p in enumerate(batch):
            prompt_len = inputs["input_ids"][i].ne(tokenizer.pad_token_id).sum().item()
            completion = tokenizer.decode(outputs[i][prompt_len:], skip_special_tokens=True)
            total_tokens += len(completion.split())

            domain = p.get("domain", "math")
            difficulty = p.get("difficulty", "medium")
            answer_type = p.get("answer_type", "numeric")
            truth = p.get("ground_truth", p.get("answer", ""))

            extracted = extract_answer(completion)
            correct = verify_answer(extracted, truth, domain, answer_type)

            results[domain]["total"] += 1
            results[domain]["correct"] += 1 if correct else 0
            diff_results[difficulty]["total"] += 1
            diff_results[difficulty]["correct"] += 1 if correct else 0

            entry = {
                "prompt": p["prompt"],
                "completion": completion,
                "domain": domain,
                "difficulty": difficulty,
                "answer_type": answer_type,
                "truth": truth,
                "extracted": extracted,
                "correct": correct,
                "source": p.get("source", ""),
            }
            completions_log.append(entry)

            # Write full completion to JSONL
            if completions_file is not None:
                completions_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
                completions_file.flush()

        done = min(batch_start + batch_size, len(problems))
        if done % 40 == 0 or done == len(problems):
            elapsed = time.time() - start_time
            logger.info(f"  {done}/{len(problems)} ({elapsed:.0f}s)")

    elapsed = time.time() - start_time

    if completions_file is not None:
        completions_file.close()
        logger.info(
            f"Full completions saved to {completions_path} ({len(completions_log)} entries)"
        )

    total_correct = sum(r["correct"] for r in results.values())
    total_count = sum(r["total"] for r in results.values())
    overall_accuracy = total_correct / total_count if total_count > 0 else 0

    return {
        "overall_accuracy": overall_accuracy,
        "total_problems": total_count,
        "total_correct": total_correct,
        "per_domain": {
            d: {
                "accuracy": r["correct"] / r["total"] if r["total"] > 0 else 0,
                "correct": r["correct"],
                "total": r["total"],
            }
            for d, r in results.items()
        },
        "per_difficulty": {
            d: {
                "accuracy": r["correct"] / r["total"] if r["total"] > 0 else 0,
                "correct": r["correct"],
                "total": r["total"],
            }
            for d, r in diff_results.items()
        },
        "avg_completion_tokens": total_tokens / total_count if total_count > 0 else 0,
        "elapsed_seconds": elapsed,
        "completions_path": completions_path,
        "sample_completions": completions_log[:20],
    }


def log_eval_to_wandb(
    eval_results: Dict,
    stage: str,
    mode: str,
    model_or_adapter: str,
    project: str = "mits-eval",
) -> None:
    """Log evaluation results to WandB as a single summary run."""
    try:
        import wandb
    except ImportError:
        logger.warning("wandb not installed — skipping WandB logging")
        return

    domains = eval_results.get("per_domain", {})
    difficulties = eval_results.get("per_difficulty", {})

    run = wandb.init(
        project=project,
        name=f"eval-{stage}-{mode}",
        tags=["eval", stage, mode],
        config={
            "stage": stage,
            "mode": mode,
            "model_or_adapter": model_or_adapter,
            "total_problems": eval_results.get("total_problems", 0),
        },
        reinit=True,
    )

    metrics: Dict[str, Any] = {
        "eval/overall_accuracy": eval_results.get("overall_accuracy", 0),
        "eval/elapsed_seconds": eval_results.get("elapsed_seconds", 0),
    }
    for domain, vals in domains.items():
        metrics[f"eval/domain/{domain}"] = vals.get("accuracy", 0)
    for diff, vals in difficulties.items():
        metrics[f"eval/difficulty/{diff}"] = vals.get("accuracy", 0)

    wandb.log(metrics)
    wandb.finish()
    logger.info(f"WandB eval run logged: {project}/eval-{stage}-{mode}")


def append_summary_csv(
    eval_results: Dict,
    stage: str,
    csv_path: str = "evaluation/reports/summary.csv",
):
    """Append a row to the summary CSV for graph building."""
    import csv

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    domains = eval_results.get("per_domain", {})
    difficulties = eval_results.get("per_difficulty", {})

    row = {
        "stage": stage,
        "overall": f"{eval_results['overall_accuracy']:.4f}",
        "math": f"{domains.get('math', {}).get('accuracy', 0):.4f}",
        "physics": f"{domains.get('physics', {}).get('accuracy', 0):.4f}",
        "chemistry": f"{domains.get('chemistry', {}).get('accuracy', 0):.4f}",
        "biology": f"{domains.get('biology', {}).get('accuracy', 0):.4f}",
        "cs": f"{domains.get('cs', {}).get('accuracy', 0):.4f}",
        "easy": f"{difficulties.get('easy', {}).get('accuracy', 0):.4f}",
        "medium": f"{difficulties.get('medium', {}).get('accuracy', 0):.4f}",
        "hard": f"{difficulties.get('hard', {}).get('accuracy', 0):.4f}",
        "total_problems": eval_results["total_problems"],
        "elapsed_s": f"{eval_results.get('elapsed_seconds', 0):.0f}",
        "timestamp": datetime.now().isoformat(),
    }

    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    logger.info(f"Summary row appended to {csv_path}")


def print_comparison(eval_results: Dict, stage: str, baseline: Optional[Dict] = None):
    """Print a comparison table with optional baseline."""
    overall = eval_results["overall_accuracy"]
    domains = eval_results.get("per_domain", {})

    base_overall = baseline["overall_accuracy"] if baseline else None

    header = f"  {stage.upper()} | Accuracy: {overall:.1%}"
    if base_overall is not None:
        header += f" (base: {base_overall:.1%}) | Δ={overall - base_overall:+.1%}"

    print(f"\n{'=' * 60}")
    print(header)
    print(f"{'=' * 60}")
    print(f"  {'Domain':<12} {'Score':>7} {'Base':>7} {'Delta':>7}")
    print(f"  {'-' * 36}")

    for d in ["math", "physics", "chemistry", "biology", "cs"]:
        acc = domains.get(d, {}).get("accuracy", 0)
        if baseline:
            base_d = baseline.get("per_domain", {}).get(d, {}).get("accuracy", 0)
            delta = acc - base_d
            arrow = "▲" if delta > 0.005 else "▼" if delta < -0.005 else "="
            print(f"  {d:<12} {acc:>6.1%} {base_d:>6.1%} {arrow}{abs(delta):>5.1%}")
        else:
            print(f"  {d:<12} {acc:>6.1%}")

    print(f"{'=' * 60}")
    print(
        f"  Time: {eval_results.get('elapsed_seconds', 0):.0f}s | Problems: {eval_results['total_problems']}"
    )


# ─── Colab mode: Unsloth evaluation ──────────────────────────


def evaluate_colab(
    adapter_source: str,
    eval_problems: List[Dict],
    max_samples: int = 0,
    batch_size: int = 4,
    max_new_tokens: int = 768,
    completions_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate using Unsloth on GPU (Colab mode)."""
    import torch
    from unsloth import FastLanguageModel

    logger.info(f"Loading adapter from {adapter_source}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=adapter_source,
        max_seq_length=512 + max_new_tokens,
        load_in_4bit=True,
        dtype=torch.bfloat16,
    )

    # Qwen3.5 returns Processor (multimodal) — unwrap to plain tokenizer
    if not hasattr(tokenizer, "vocab_size") and hasattr(tokenizer, "tokenizer"):
        tokenizer = tokenizer.tokenizer

    FastLanguageModel.for_inference(model)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    problems = eval_problems[:max_samples] if max_samples > 0 else eval_problems

    # Prepare completions JSONL file for full response logging
    completions_file = None
    if completions_path:
        os.makedirs(os.path.dirname(completions_path) or ".", exist_ok=True)
        completions_file = open(completions_path, "w", encoding="utf-8")
        logger.info(f"Saving full completions to {completions_path}")

    results = defaultdict(lambda: {"total": 0, "correct": 0})
    diff_results = defaultdict(lambda: {"total": 0, "correct": 0})
    completions_log = []
    total_tokens = 0

    logger.info(f"Evaluating {len(problems)} problems (batch_size={batch_size})...")
    start_time = time.time()

    for batch_start in range(0, len(problems), batch_size):
        batch = problems[batch_start : batch_start + batch_size]

        # Format prompts
        prompts = []
        for p in batch:
            sys_prompt = (
                SYSTEM_PROMPT_MC if p.get("answer_type") == "mc_letter" else SYSTEM_PROMPT_CALC
            )
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": p["prompt"]},
            ]
            prompts.append(
                tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            )

        # Batch tokenize
        inputs = tokenizer(
            text=prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        ).to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,  # Greedy for reproducibility
                temperature=1.0,
            )

        # Decode and verify
        for i, p in enumerate(batch):
            prompt_len = inputs["input_ids"][i].ne(tokenizer.pad_token_id).sum().item()
            completion = tokenizer.decode(outputs[i][prompt_len:], skip_special_tokens=True)
            total_tokens += len(completion.split())

            domain = p.get("domain", "math")
            difficulty = p.get("difficulty", "medium")
            answer_type = p.get("answer_type", "numeric")
            truth = p.get("ground_truth", p.get("answer", ""))

            extracted = extract_answer(completion)
            correct = verify_answer(extracted, truth, domain, answer_type)

            results[domain]["total"] += 1
            results[domain]["correct"] += 1 if correct else 0
            diff_results[difficulty]["total"] += 1
            diff_results[difficulty]["correct"] += 1 if correct else 0

            entry = {
                "prompt": p["prompt"],
                "completion": completion,
                "domain": domain,
                "difficulty": difficulty,
                "answer_type": answer_type,
                "truth": truth,
                "extracted": extracted,
                "correct": correct,
                "source": p.get("source", ""),
            }
            completions_log.append(entry)

            if completions_file is not None:
                completions_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
                completions_file.flush()

        done = min(batch_start + batch_size, len(problems))
        if done % 20 == 0 or done == len(problems):
            elapsed = time.time() - start_time
            logger.info(f"  {done}/{len(problems)} ({elapsed:.0f}s)")

    elapsed = time.time() - start_time

    if completions_file is not None:
        completions_file.close()
        logger.info(
            f"Full completions saved to {completions_path} ({len(completions_log)} entries)"
        )

    # Compile results
    total_correct = sum(r["correct"] for r in results.values())
    total_count = sum(r["total"] for r in results.values())
    overall_accuracy = total_correct / total_count if total_count > 0 else 0

    return {
        "overall_accuracy": overall_accuracy,
        "total_problems": total_count,
        "total_correct": total_correct,
        "per_domain": {
            d: {
                "accuracy": r["correct"] / r["total"] if r["total"] > 0 else 0,
                "correct": r["correct"],
                "total": r["total"],
            }
            for d, r in results.items()
        },
        "per_difficulty": {
            d: {
                "accuracy": r["correct"] / r["total"] if r["total"] > 0 else 0,
                "correct": r["correct"],
                "total": r["total"],
            }
            for d, r in diff_results.items()
        },
        "avg_completion_tokens": total_tokens / total_count if total_count > 0 else 0,
        "elapsed_seconds": elapsed,
        "completions_path": completions_path,
        "sample_completions": completions_log[:20],
    }


def export_gguf_from_adapter(
    adapter_source: str,
    output_dir: str,
    quantization: str = "q4_k_m",
) -> str:
    """Export adapter to GGUF format. Returns path to GGUF file."""
    import torch
    from unsloth import FastLanguageModel

    logger.info(f"Loading adapter for GGUF export: {adapter_source}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=adapter_source,
        max_seq_length=2048,
        load_in_4bit=True,
        dtype=torch.bfloat16,
    )

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"model-{quantization}")

    logger.info(f"Exporting GGUF ({quantization}) to {output_path}...")
    model.save_pretrained_gguf(output_path, tokenizer, quantization_method=quantization)

    # Find the .gguf file
    for f in os.listdir(output_path):
        if f.endswith(".gguf"):
            gguf_path = os.path.join(output_path, f)
            size_mb = os.path.getsize(gguf_path) / (1024 * 1024)
            logger.info(f"GGUF exported: {gguf_path} ({size_mb:.0f} MB)")
            return gguf_path

    raise FileNotFoundError(f"No .gguf file found in {output_path}")


# ─── Local mode: Ollama evaluation ───────────────────────────


def _eval_single_problem(args):
    """Evaluate a single problem via Ollama (used by ThreadPoolExecutor)."""
    import requests

    idx, p, model_name, ollama_host, session, cerebras_client, full_judge = args
    domain = p.get("domain", "math")
    difficulty = p.get("difficulty", "medium")
    answer_type = p.get("answer_type", "numeric")
    truth = p.get("ground_truth", p.get("answer", ""))
    sys_prompt = SYSTEM_PROMPT_MC if answer_type == "mc_letter" else SYSTEM_PROMPT_CALC

    try:
        http = session if session is not None else requests
        resp = http.post(
            f"{ollama_host}/api/chat",
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": p["prompt"]},
                ],
                "stream": False,
                "options": _build_ollama_options("full_judge" if full_judge else "accuracy"),
                # full_judge: think=False — judge sees student-facing response only;
                # accuracy:   think=True  — \boxed{} extraction needs full reasoning.
                "think": not full_judge,
                "cache_prompt": True,  # reuse KV for shared system-prompt prefix
            },
            timeout=600,  # 10 min: thinking models can be slow locally
        )

        if resp.status_code != 200:
            return {"idx": idx, "error": True}

        msg = resp.json().get("message", {})
        # Ollama 0.7+: thinking models return reasoning in 'thinking' field
        thinking = msg.get("thinking", "")
        content = msg.get("content", "")
        if thinking:
            completion = f"<think>\n{thinking}\n</think>\n{content}"
        else:
            completion = content
        fmt = check_format_compliance(completion)
        # Visible response: strip <think> block before sending to judge
        visible = re.sub(r"<think>.*?</think>", "", completion, flags=re.DOTALL).strip()

        socratic_scores: Dict[str, Any] = {}
        if full_judge and cerebras_client is not None:
            # Full LLM judge: accuracy + Socratic in one Cerebras call
            combined = evaluate_combined_quality(p["prompt"], visible, truth, cerebras_client)
            correct = bool(combined.get("is_correct", False))
            extracted = None
            socratic_scores = {
                k: combined.get(k)
                for k in (
                    "socratic_score",
                    "guides_student",
                    "no_answer_leak",
                    "scaffolding",
                    "engagement",
                    "explanation",
                )
            }
        else:
            # Hybrid: SymPy/exact first, LLM only if answer not found
            extracted = extract_answer(completion)
            if extracted:
                correct = verify_answer(extracted, truth, domain, answer_type)
            elif cerebras_client is not None:
                correct = _verify_with_llm_judge(
                    completion, p["prompt"], truth, domain, cerebras_client
                )
            else:
                correct = False

        return {
            "idx": idx,
            "error": False,
            "domain": domain,
            "difficulty": difficulty,
            "correct": correct,
            "tokens": len(completion.split()),
            "format": fmt,
            "socratic": socratic_scores,
            "log": {
                "prompt": p["prompt"],
                "completion": completion,
                "visible": visible,
                "domain": domain,
                "difficulty": difficulty,
                "answer_type": p.get("answer_type", "numeric"),
                "truth": truth,
                "extracted": extracted,
                "correct": correct,
                "has_boxed": fmt["has_boxed"],
                "has_thinking": fmt["has_thinking"],
                "source": p.get("source", ""),
                **socratic_scores,
            },
        }
    except Exception as e:
        return {"idx": idx, "error": True, "error_msg": str(e)}


def _build_ollama_options(mode: str = "accuracy") -> Dict[str, Any]:
    """Return Ollama inference options tuned for evaluation speed.

    Two modes:
      accuracy  — thinking model (\boxed{} expected), generous ctx for <think> block.
                  num_ctx 8192 vs default 16384: halves KV cache size → ~2x faster
                  prefill; num_batch 512 fills GPU compute units during prefill.
      socratic  — tutoring response, think=False, short output: tiny ctx sufficient.

    cache_prompt (set at request level, not here) tells Ollama to reuse KV for the
    shared system-prompt prefix across requests — saves re-encoding it 150 times.

    Server-side: set OLLAMA_KV_CACHE_TYPE=q8_0 to halve KV memory with no quality
    loss (int8 attention keys/values). Combined with num_ctx=8192: ~4x less memory
    than the original f16/16384 baseline.
    PowerShell: $env:OLLAMA_KV_CACHE_TYPE = "q8_0"  (before ollama serve)
    bash/zsh:   export OLLAMA_KV_CACHE_TYPE=q8_0
    """
    if mode == "accuracy":
        return {
            "temperature": 0.0,
            "num_predict": -1,  # unlimited — model stops at EOS
            "num_ctx": 8192,
            "num_batch": 512,
        }
    if mode == "full_judge":
        # think=False: judge evaluates student-facing response, not internal reasoning.
        # num_predict=-1: model decides when it's done (timeout=600s as safety net).
        return {
            "temperature": 0.0,
            "num_predict": -1,  # unlimited — model stops at EOS
            "num_ctx": 8192,
            "num_batch": 512,
        }
    # socratic: think=False, short tutoring response
    return {
        "temperature": 0.7,
        "num_predict": 1024,
        "num_ctx": 2048,  # system_tutor (~100t) + problem (~200t) + response (~500t)
        "num_batch": 512,
    }


def _preflight_check(model_name: str, ollama_host: str) -> bool:
    """Verify Ollama is running and the model is available."""
    import requests

    try:
        resp = requests.get(f"{ollama_host}/api/tags", timeout=10)
        if resp.status_code != 200:
            logger.error(f"Ollama not reachable at {ollama_host} (status {resp.status_code})")
            return False
        models = [m["name"] for m in resp.json().get("models", [])]
        # Match with or without ":latest" tag
        matched = any(model_name in m or m.startswith(model_name) for m in models)
        if not matched:
            logger.error(
                f"Model '{model_name}' not found in Ollama. Available: {', '.join(models[:10])}"
            )
            logger.error(f"Run: ollama pull {model_name}")
            return False
        logger.info(f"Preflight OK: Ollama running, model '{model_name}' available")
        return True
    except requests.ConnectionError:
        logger.error(f"Cannot connect to Ollama at {ollama_host}. Is it running? (ollama serve)")
        return False
    except Exception as e:
        logger.error(f"Preflight check failed: {e}")
        return False


def _checkpoint_path(
    model_name: str, stage: str, checkpoint_dir: str = "evaluation/checkpoints"
) -> str:
    """Auto-generate checkpoint file path from model name and stage."""
    tag = model_name.replace("/", "_").replace(":", "_")
    os.makedirs(checkpoint_dir, exist_ok=True)
    return os.path.join(checkpoint_dir, f"{tag}_{stage}.jsonl")


def _load_checkpoint(path: str) -> Tuple[Set[int], List[Dict]]:
    """Load completed problem indices and their log entries from a checkpoint file.

    Returns (completed_idxs, prior_logs). Only entries with 'idx' and no 'error'
    are loaded — failed problems are retried on resume.
    """
    completed_idxs: Set[int] = set()
    prior_logs: List[Dict] = []
    if not os.path.exists(path):
        return completed_idxs, prior_logs
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if "idx" in entry and not entry.get("error"):
                    completed_idxs.add(entry["idx"])
                    prior_logs.append(entry)
            except json.JSONDecodeError:
                continue
    logger.info(f"Checkpoint loaded: {len(completed_idxs)} problems already done from {path}")
    return completed_idxs, prior_logs


def evaluate_local(
    model_name: str,
    eval_problems: List[Dict],
    ollama_host: str = "http://localhost:11434",
    max_samples: int = 0,
    num_workers: int = 2,
    completions_path: Optional[str] = None,
    cerebras_client: Any = None,
    checkpoint_path: Optional[str] = None,
    resume: bool = False,
    full_judge: bool = False,
) -> Dict[str, Any]:
    """Evaluate using Ollama API with parallel requests."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not _preflight_check(model_name, ollama_host):
        return {
            "overall_accuracy": 0,
            "total_problems": 0,
            "total_correct": 0,
            "errors": len(eval_problems),
            "per_domain": {},
            "per_difficulty": {},
            "avg_completion_tokens": 0,
            "elapsed_seconds": 0,
            "sample_completions": [],
            "error_message": f"Preflight failed: Ollama not running or model '{model_name}' not found",
        }

    problems = eval_problems[:max_samples] if max_samples > 0 else eval_problems

    # Prepare completions JSONL file for full response logging
    completions_file = None
    if completions_path:
        os.makedirs(os.path.dirname(completions_path) or ".", exist_ok=True)
        completions_file = open(completions_path, "w", encoding="utf-8")
        logger.info(f"Saving full completions to {completions_path}")

    results = defaultdict(lambda: {"total": 0, "correct": 0})
    diff_results = defaultdict(lambda: {"total": 0, "correct": 0})
    completions_log = []
    completions_by_idx: Dict[int, Dict] = {}  # idx -> log entry, for side-by-side comparison
    total_tokens = 0
    errors = 0
    done_count = 0
    fmt_counts = {"has_boxed": 0, "has_steps": 0, "has_thinking": 0, "total_length": 0, "count": 0}
    socratic_agg: Dict[str, List[float]] = {
        "socratic_score": [],
        "guides_student": [],
        "no_answer_leak": [],
        "scaffolding": [],
        "engagement": [],
    }

    # ── Checkpoint: load prior results if resuming ──────────────
    completed_idxs: Set[int] = set()
    ckpt_file = None
    if checkpoint_path:
        if resume:
            completed_idxs, prior_logs = _load_checkpoint(checkpoint_path)
            # Reconstruct stats from already-done problems
            for entry in prior_logs:
                domain = entry.get("domain", "math")
                difficulty = entry.get("difficulty", "medium")
                correct = entry.get("correct", False)
                results[domain]["total"] += 1
                results[domain]["correct"] += 1 if correct else 0
                diff_results[difficulty]["total"] += 1
                diff_results[difficulty]["correct"] += 1 if correct else 0
                total_tokens += len(entry.get("completion", "").split())
                fmt_counts["count"] += 1
                fmt_counts["has_boxed"] += 1 if entry.get("has_boxed") else 0
                fmt_counts["has_steps"] += 1 if entry.get("has_steps") else 0
                fmt_counts["has_thinking"] += 1 if entry.get("has_thinking") else 0
                fmt_counts["total_length"] += len(entry.get("completion", ""))
            done_count = len(completed_idxs)
        ckpt_mode = "a" if resume and os.path.exists(checkpoint_path) else "w"
        os.makedirs(os.path.dirname(checkpoint_path) or ".", exist_ok=True)
        ckpt_file = open(checkpoint_path, ckpt_mode, encoding="utf-8")

    remaining = len(problems) - len(completed_idxs)
    logger.info(
        f"Evaluating {remaining}/{len(problems)} problems via Ollama ({model_name}), "
        f"{num_workers} workers..."
        + (f" [{len(completed_idxs)} skipped from checkpoint]" if completed_idxs else "")
    )
    _opts_mode = "full_judge" if full_judge else "accuracy"
    opts = _build_ollama_options(_opts_mode)
    logger.info(
        f"  Options [{_opts_mode}]: num_predict={opts['num_predict']}, num_ctx={opts['num_ctx']}, "
        f"num_batch={opts['num_batch']}, cache_prompt=True, timeout=600s"
    )
    start_time = time.time()

    import requests as _requests

    session = _requests.Session()
    # Connection pooling: reuse TCP connections to Ollama
    adapter = _requests.adapters.HTTPAdapter(
        pool_connections=num_workers,
        pool_maxsize=num_workers + 2,
    )
    session.mount("http://", adapter)

    tasks = [
        (i, p, model_name, ollama_host, session, cerebras_client, full_judge)
        for i, p in enumerate(problems)
        if i not in completed_idxs
    ]

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(_eval_single_problem, t): t for t in tasks}

        for future in as_completed(futures):
            result = future.result()
            done_count += 1

            if result["error"]:
                errors += 1
                if errors <= 3:
                    logger.warning(
                        f"  Error on problem {result['idx']}: {result.get('error_msg', 'unknown')}"
                    )
                elif errors == 4:
                    logger.warning("  Suppressing further error messages...")
            else:
                domain = result["domain"]
                difficulty = result["difficulty"]
                results[domain]["total"] += 1
                results[domain]["correct"] += 1 if result["correct"] else 0
                diff_results[difficulty]["total"] += 1
                diff_results[difficulty]["correct"] += 1 if result["correct"] else 0
                total_tokens += result["tokens"]
                # Track format compliance
                fmt = result.get("format", {})
                fmt_counts["count"] += 1
                fmt_counts["has_boxed"] += 1 if fmt.get("has_boxed") else 0
                fmt_counts["has_steps"] += 1 if fmt.get("has_steps") else 0
                fmt_counts["has_thinking"] += 1 if fmt.get("has_thinking") else 0
                fmt_counts["total_length"] += fmt.get("response_length", 0)
                if len(completions_log) < 20:
                    completions_log.append(result["log"])
                # Store for side-by-side comparison (all problems)
                completions_by_idx[result["idx"]] = result["log"]

                # Aggregate Socratic scores if full judge was used
                soc = result.get("socratic", {})
                for key in socratic_agg:
                    val = soc.get(key)
                    if val is not None:
                        socratic_agg[key].append(float(val))

                # Write full completion to JSONL
                if completions_file is not None:
                    completions_file.write(json.dumps(result["log"], ensure_ascii=False) + "\n")
                    completions_file.flush()

                # Write checkpoint entry (always, for resume support)
                if ckpt_file is not None:
                    ckpt_entry = {**result["log"], "idx": result["idx"]}
                    ckpt_file.write(json.dumps(ckpt_entry, ensure_ascii=False) + "\n")
                    ckpt_file.flush()

                # Per-problem logging
                log = result["log"]
                mark = "+" if log["correct"] else "x"
                boxed = "[B]" if fmt.get("has_boxed") else "[ ]"
                think = "[T]" if fmt.get("has_thinking") else "   "
                soc_str = f"soc={soc.get('socratic_score', 0):.2f}" if soc else ""
                logger.info(
                    f"  [{mark}] #{result['idx']:>4d} {domain:<10s} {difficulty:<6s} | "
                    f"truth={str(log['truth']):<12s} pred={str(log['extracted']):<12s} "
                    f"| {boxed} boxed {think} {soc_str} | {result['tokens']} tok"
                )
                if done_count <= 10:
                    preview = log.get("visible", log.get("completion", ""))[:150].replace("\n", " ")
                    logger.info(f"    >> {preview}")

            if done_count % 50 == 0 or done_count == len(problems):
                elapsed = time.time() - start_time
                rate = done_count / elapsed if elapsed > 0 else 0
                eta = (len(problems) - done_count) / rate if rate > 0 else 0
                logger.info(
                    f"  {done_count}/{len(problems)} ({elapsed:.0f}s, "
                    f"{rate:.1f} prob/s, ETA {eta:.0f}s, {errors} errors)"
                )

    elapsed = time.time() - start_time

    if completions_file is not None:
        completions_file.close()
        logger.info(f"Full completions saved to {completions_path} ({done_count - errors} entries)")

    if ckpt_file is not None:
        ckpt_file.close()
        logger.info(f"Checkpoint saved to {checkpoint_path} (resume with --resume)")

    total_correct = sum(r["correct"] for r in results.values())
    total_count = sum(r["total"] for r in results.values())
    overall_accuracy = total_correct / total_count if total_count > 0 else 0

    fc = fmt_counts["count"]
    format_compliance = {
        "boxed_pct": fmt_counts["has_boxed"] / fc if fc > 0 else 0,
        "steps_pct": fmt_counts["has_steps"] / fc if fc > 0 else 0,
        "thinking_pct": fmt_counts["has_thinking"] / fc if fc > 0 else 0,
        "avg_response_length": fmt_counts["total_length"] / fc if fc > 0 else 0,
        "total_evaluated": fc,
    }

    return {
        "overall_accuracy": overall_accuracy,
        "total_problems": total_count,
        "total_correct": total_correct,
        "errors": errors,
        "per_domain": {
            d: {
                "accuracy": r["correct"] / r["total"] if r["total"] > 0 else 0,
                "correct": r["correct"],
                "total": r["total"],
            }
            for d, r in results.items()
        },
        "per_difficulty": {
            d: {
                "accuracy": r["correct"] / r["total"] if r["total"] > 0 else 0,
                "correct": r["correct"],
                "total": r["total"],
            }
            for d, r in diff_results.items()
        },
        "format_compliance": format_compliance,
        "avg_completion_tokens": total_tokens / total_count if total_count > 0 else 0,
        "elapsed_seconds": elapsed,
        "completions_path": completions_path,
        "sample_completions": completions_log[:20],
        "completions_by_idx": completions_by_idx,
        "socratic": {
            key: round(sum(vals) / len(vals), 3) if vals else None
            for key, vals in socratic_agg.items()
        }
        if any(socratic_agg.values())
        else None,
    }


# ─── Report generation ───────────────────────────────────────


def save_report(
    eval_results: Dict,
    stage: str,
    mode: str,
    adapter_source: str,
    output_dir: str = "evaluation/reports",
):
    """Save evaluation report as JSON."""
    os.makedirs(output_dir, exist_ok=True)

    report = {
        "stage": stage,
        "mode": mode,
        "adapter_source": adapter_source,
        "evaluated_at": datetime.now().isoformat(),
        "results": eval_results,
    }

    filename = f"stage_{stage}_{mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Print summary
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Stage: {stage.upper()} | Mode: {mode}")
    logger.info(f"Overall accuracy: {eval_results['overall_accuracy']:.1%}")
    logger.info(f"{'=' * 60}")
    for domain, metrics in eval_results["per_domain"].items():
        logger.info(
            f"  {domain:12s}: {metrics['accuracy']:.1%} ({metrics['correct']}/{metrics['total']})"
        )

    # Print format compliance if available
    fc = eval_results.get("format_compliance")
    if fc:
        logger.info("\n  Format compliance:")
        logger.info(f"    \\boxed{{}} usage: {fc['boxed_pct']:.1%}")
        logger.info(f"    Step markers:   {fc['steps_pct']:.1%}")
        logger.info(f"    <think> tags:   {fc['thinking_pct']:.1%}")
        logger.info(f"    Avg response:   {fc['avg_response_length']:.0f} chars")

    logger.info(f"\nReport saved to {path}")

    return path


def compare_stages(reports_dir: str = "evaluation/reports"):
    """Compare results across all pipeline stages."""
    reports_path = Path(reports_dir)
    if not reports_path.exists():
        logger.error(f"Reports directory not found: {reports_dir}")
        return

    # Load latest report per stage
    stage_reports = {}
    for f in sorted(reports_path.glob("stage_*.json")):
        with open(f) as fh:
            report = json.load(fh)
        stage = report["stage"]
        stage_reports[stage] = report

    if not stage_reports:
        logger.info("No reports found.")
        return

    # Print comparison table
    logger.info(f"\n{'=' * 70}")
    logger.info("Pipeline Stage Comparison")
    logger.info(f"{'=' * 70}")
    header = f"{'Stage':>8s} | {'Overall':>8s} | {'Math':>6s} | {'Physics':>7s} | {'Chem':>6s} | {'Bio':>6s} | {'CS':>6s}"
    logger.info(header)
    logger.info("-" * 70)

    for stage in STAGES:
        if stage not in stage_reports:
            continue
        r = stage_reports[stage]["results"]
        domains = r.get("per_domain", {})
        row = (
            f"{stage:>8s} | "
            f"{r['overall_accuracy']:>7.1%} | "
            f"{domains.get('math', {}).get('accuracy', 0):>5.1%} | "
            f"{domains.get('physics', {}).get('accuracy', 0):>6.1%} | "
            f"{domains.get('chemistry', {}).get('accuracy', 0):>5.1%} | "
            f"{domains.get('biology', {}).get('accuracy', 0):>5.1%} | "
            f"{domains.get('cs', {}).get('accuracy', 0):>5.1%}"
        )
        logger.info(row)

    logger.info(f"{'=' * 70}")

    # Save comparison
    comparison_path = os.path.join(reports_dir, "stage_comparison.json")
    with open(comparison_path, "w", encoding="utf-8") as f:
        json.dump(stage_reports, f, indent=2, ensure_ascii=False)
    logger.info(f"Comparison saved to {comparison_path}")


def _print_comparison(
    results_a: Dict,
    label_a: str,
    results_b: Dict,
    label_b: str,
    show_responses: int = 3,
) -> None:
    """Print a side-by-side comparison table with deltas and sample responses."""
    W = 72
    col = 10

    def pct(v: Optional[float]) -> str:
        return f"{v:.1%}" if v is not None else "  n/a  "

    def flt(v: Optional[float]) -> str:
        return f"{v:.3f}" if v is not None else "  n/a  "

    def delta_pct(a: Optional[float], b: Optional[float]) -> str:
        if a is None or b is None:
            return "   n/a"
        d = b - a
        return f"{'+' if d >= 0 else ''}{d:.1%}"

    def delta_flt(a: Optional[float], b: Optional[float]) -> str:
        if a is None or b is None:
            return "   n/a"
        d = b - a
        return f"{'+' if d >= 0 else ''}{d:.3f}"

    sep = "─" * W
    logger.info("=" * W)
    logger.info(f"Live Comparison: {label_a}  vs  {label_b}")
    logger.info("=" * W)
    logger.info(f"{'Metric':<18} | {label_a[:col]:>{col}} | {label_b[:col]:>{col}} | {'delta':>8}")
    logger.info(sep)

    # Accuracy metrics
    acc_a = results_a.get("overall_accuracy")
    acc_b = results_b.get("overall_accuracy")
    logger.info(
        f"{'overall':18} | {pct(acc_a):>{col}} | {pct(acc_b):>{col}} | {delta_pct(acc_a, acc_b):>8}"
    )

    for domain in ("math", "physics", "chemistry", "biology", "cs"):
        da = results_a.get("per_domain", {}).get(domain, {}).get("accuracy")
        db = results_b.get("per_domain", {}).get(domain, {}).get("accuracy")
        logger.info(
            f"  {domain:<16} | {pct(da):>{col}} | {pct(db):>{col}} | {delta_pct(da, db):>8}"
        )

    # Socratic metrics (optional)
    soc_a = results_a.get("socratic")
    soc_b = results_b.get("socratic")
    if soc_a or soc_b:
        logger.info(sep)
        for key, fmt in [
            ("socratic_score", flt),
            ("is_correct_rate", pct),
            ("guides_student", flt),
            ("no_answer_leak", flt),
            ("scaffolding", flt),
            ("engagement", flt),
        ]:
            va = soc_a.get(key) if soc_a else None
            vb = soc_b.get(key) if soc_b else None
            df = delta_pct if fmt == pct else delta_flt
            logger.info(f"  {key:<16} | {fmt(va):>{col}} | {fmt(vb):>{col}} | {df(va, vb):>8}")

    logger.info("=" * W)
    na = results_a.get("total_problems", 0)
    nb = results_b.get("total_problems", 0)
    logger.info(f"Problems: {label_a}={na}, {label_b}={nb}  (same seed — identical sets)")

    # ── Side-by-side sample responses ───────────────────────────
    if show_responses > 0:
        cmp_a = results_a.get("completions_by_idx", {})
        cmp_b = results_b.get("completions_by_idx", {})
        shared_idxs = sorted(set(cmp_a) & set(cmp_b))
        if shared_idxs:
            # Prioritise: B correct & A wrong → B wrong & A correct → both wrong
            def _priority(idx: int) -> int:
                ca = cmp_a[idx].get("correct", False)
                cb = cmp_b[idx].get("correct", False)
                if cb and not ca:
                    return 0  # GSPO improved
                if ca and not cb:
                    return 1  # regression
                if not ca and not cb:
                    return 2  # both fail
                return 3  # both pass (least interesting)

            sample_idxs = sorted(shared_idxs, key=_priority)[:show_responses]
            logger.info("\n" + "─" * W)
            logger.info("SAMPLE RESPONSES (truncated to 400 chars)")
            logger.info("─" * W)
            for idx in sample_idxs:
                ea = cmp_a[idx]
                eb = cmp_b[idx]
                ca = ea.get("correct", False)
                cb = eb.get("correct", False)
                domain = ea.get("domain", "?")
                difficulty = ea.get("difficulty", "?")
                truth = ea.get("truth", "?")
                prompt_preview = str(ea.get("prompt", ""))[:120].replace("\n", " ")
                logger.info(f"\n[#{idx} | {domain}/{difficulty} | truth={truth}]")
                logger.info(f"Q: {prompt_preview}...")
                logger.info(f"── {label_a[:30]} [{'✓' if ca else '✗'}] ──")
                resp_a = ea.get("visible", ea.get("completion", ""))[:400].replace("\n", " ")
                logger.info(f"  {resp_a}")
                logger.info(f"── {label_b[:30]} [{'✓' if cb else '✗'}] ──")
                resp_b = eb.get("visible", eb.get("completion", ""))[:400].replace("\n", " ")
                logger.info(f"  {resp_b}")
            logger.info("─" * W)


def compare_live(
    model_a: str,
    stage_a: str,
    model_b: str,
    stage_b: str,
    eval_problems: List[Dict],
    ollama_host: str = "http://localhost:11434",
    num_workers: int = 2,
    cerebras_client: Any = None,
    run_judge: bool = False,
    judge_n: int = 75,
    reports_dir: str = "evaluation/reports",
    completions_dir: str = "evaluation/completions",
    save_completions: bool = False,
    resume: bool = False,
    checkpoint_dir: str = "evaluation/checkpoints",
    full_judge: bool = False,
) -> Dict[str, Any]:
    """Run evaluation for two local models on the same problem set and compare.

    Models are evaluated sequentially (GPU runs one at a time).
    The problem set is identical for both — same objects, same order.
    Combined judge (if run_judge=True) uses same 75-problem subsample for both.
    """
    label_a = f"{model_a} ({stage_a})"
    label_b = f"{model_b} ({stage_b})"

    def _completions_path(stage: str, model: str) -> Optional[str]:
        if not save_completions:
            return None
        os.makedirs(completions_dir, exist_ok=True)
        tag = model.replace("/", "_").replace(":", "_")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(completions_dir, f"compare_{stage}_{tag}_{ts}.jsonl")

    logger.info(f"compare-live: evaluating {label_a} ...")
    results_a = evaluate_local(
        model_name=model_a,
        eval_problems=eval_problems,
        ollama_host=ollama_host,
        num_workers=num_workers,
        completions_path=_completions_path(stage_a, model_a),
        cerebras_client=cerebras_client,
        checkpoint_path=_checkpoint_path(model_a, stage_a, checkpoint_dir),
        resume=resume,
        full_judge=full_judge,
    )
    # Separate socratic pass only if not using full_judge (avoid double-counting)
    if run_judge and not full_judge and cerebras_client is not None:
        results_a["socratic"] = evaluate_combined_pass(
            model_name=model_a,
            problems=eval_problems,
            ollama_host=ollama_host,
            cerebras_client=cerebras_client,
            n_judge=judge_n,
        )

    logger.info(f"compare-live: evaluating {label_b} ...")
    results_b = evaluate_local(
        model_name=model_b,
        eval_problems=eval_problems,
        ollama_host=ollama_host,
        num_workers=num_workers,
        completions_path=_completions_path(stage_b, model_b),
        cerebras_client=cerebras_client,
        checkpoint_path=_checkpoint_path(model_b, stage_b, checkpoint_dir),
        resume=resume,
        full_judge=full_judge,
    )
    if run_judge and not full_judge and cerebras_client is not None:
        results_b["socratic"] = evaluate_combined_pass(
            model_name=model_b,
            problems=eval_problems,
            ollama_host=ollama_host,
            cerebras_client=cerebras_client,
            n_judge=judge_n,
        )

    _print_comparison(results_a, label_a, results_b, label_b, show_responses=5)

    # Save individual reports and a combined comparison
    save_report(results_a, stage_a, "local", model_a, reports_dir)
    save_report(results_b, stage_b, "local", model_b, reports_dir)
    append_summary_csv(results_a, stage_a)
    append_summary_csv(results_b, stage_b)

    comparison = {
        "model_a": {"label": label_a, "stage": stage_a, "model": model_a, "results": results_a},
        "model_b": {"label": label_b, "stage": stage_b, "model": model_b, "results": results_b},
        "n_problems": len(eval_problems),
        "timestamp": datetime.now().isoformat(),
    }
    cmp_path = os.path.join(
        reports_dir,
        f"compare_{stage_a}_vs_{stage_b}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    )
    os.makedirs(reports_dir, exist_ok=True)
    with open(cmp_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)
    logger.info(f"Comparison saved → {cmp_path}")

    return comparison


# ─── CLI ──────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="MITS per-stage model evaluation")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Evaluate command
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate a model stage")
    eval_parser.add_argument("--mode", choices=["colab", "local"], required=True)
    eval_parser.add_argument("--adapter", help="HF repo or local path (colab mode)")
    eval_parser.add_argument("--model", help="Ollama model name (local mode)")
    eval_parser.add_argument("--stage", required=True, choices=STAGES)
    eval_parser.add_argument("--eval-data", default="training/data/eval_dataset.jsonl")
    eval_parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Use eval_benchmark.jsonl (alias for --eval-data training/data/eval_benchmark.jsonl)",
    )
    eval_parser.add_argument("--max-samples", type=int, default=0, help="Limit eval size (0=all)")
    eval_parser.add_argument(
        "--stratified",
        action="store_true",
        help="Use stratified sampling by (domain, difficulty) instead of first N",
    )
    eval_parser.add_argument("--ollama-host", default="http://localhost:11434")
    eval_parser.add_argument(
        "--workers", type=int, default=2, help="Parallel workers for local mode (2 for CPU)"
    )
    eval_parser.add_argument("--export-gguf", action="store_true", help="Also export GGUF (colab)")
    eval_parser.add_argument("--quantization", default="q4_k_m")
    eval_parser.add_argument("--reports-dir", default="evaluation/reports")
    eval_parser.add_argument(
        "--save-completions",
        action="store_true",
        help="Save ALL model completions to JSONL for later comparison",
    )
    eval_parser.add_argument(
        "--completions-dir",
        default="evaluation/completions",
        help="Directory for completion JSONL files",
    )
    eval_parser.add_argument(
        "--problem-file",
        default="",
        help="JSONL file with exact problems to evaluate (for paired comparison)",
    )
    eval_parser.add_argument(
        "--eval-150",
        action="store_true",
        help="Use stratified 150-problem preset: 10 per (domain, difficulty) cell",
    )
    eval_parser.add_argument(
        "--hybrid-verify",
        action="store_true",
        help="SymPy + Cerebras LLM fallback for numeric/latex answer verification",
    )
    eval_parser.add_argument(
        "--judge",
        action="store_true",
        help="Run Cerebras Socratic quality judge on a subsample (needs Cerebras keys)",
    )
    eval_parser.add_argument(
        "--judge-n",
        type=int,
        default=75,
        help="Number of problems to score with combined judge (default: 75)",
    )
    eval_parser.add_argument(
        "--full-judge",
        action="store_true",
        help=(
            "Send ALL responses to Cerebras combined judge (accuracy + Socratic in one pass). "
            "More accurate than SymPy-only but requires Cerebras API keys."
        ),
    )
    eval_parser.add_argument(
        "--kv-quant",
        action="store_true",
        help=(
            "Print KV cache quantization setup instructions. "
            "Set OLLAMA_KV_CACHE_TYPE=q8_0 server-side for ~2x KV memory reduction."
        ),
    )
    eval_parser.add_argument(
        "--wandb",
        action="store_true",
        help="Log evaluation results to WandB",
    )
    eval_parser.add_argument(
        "--wandb-project",
        default="mits-eval",
        help="WandB project name (default: mits-eval)",
    )
    eval_parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint: skip already-evaluated problems",
    )
    eval_parser.add_argument(
        "--checkpoint-dir",
        default="evaluation/checkpoints",
        help="Directory for checkpoint files (default: evaluation/checkpoints)",
    )

    # Compare (from saved reports)
    cmp_parser = subparsers.add_parser("compare", help="Compare all stages from saved reports")
    cmp_parser.add_argument("--reports-dir", default="evaluation/reports")

    # Compare-live: run both models now, same problem set
    cmp_live = subparsers.add_parser(
        "compare-live", help="Run and compare two local models on identical problems"
    )
    cmp_live.add_argument("--model-a", required=True, help="First Ollama model name")
    cmp_live.add_argument("--stage-a", required=True, choices=STAGES)
    cmp_live.add_argument("--model-b", required=True, help="Second Ollama model name")
    cmp_live.add_argument("--stage-b", required=True, choices=STAGES)
    cmp_live.add_argument("--eval-data", default="training/data/eval_dataset.jsonl")
    cmp_live.add_argument("--benchmark", action="store_true")
    cmp_live.add_argument("--eval-150", action="store_true")
    cmp_live.add_argument("--ollama-host", default="http://localhost:11434")
    cmp_live.add_argument("--workers", type=int, default=2)
    cmp_live.add_argument("--hybrid-verify", action="store_true")
    cmp_live.add_argument("--judge", action="store_true")
    cmp_live.add_argument("--judge-n", type=int, default=75)
    cmp_live.add_argument(
        "--full-judge",
        action="store_true",
        help="Send ALL responses to Cerebras combined judge (accuracy + Socratic in one pass)",
    )
    cmp_live.add_argument("--reports-dir", default="evaluation/reports")
    cmp_live.add_argument("--save-completions", action="store_true")
    cmp_live.add_argument("--completions-dir", default="evaluation/completions")
    cmp_live.add_argument("--wandb", action="store_true")
    cmp_live.add_argument("--wandb-project", default="mits-eval")
    cmp_live.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint: skip already-evaluated problems",
    )
    cmp_live.add_argument(
        "--checkpoint-dir",
        default="evaluation/checkpoints",
        help="Directory for checkpoint files",
    )

    args = parser.parse_args()

    if args.command == "compare":
        compare_stages(args.reports_dir)
        return

    if args.command == "compare-live":
        # Load problems once — both models get the same set
        eval_data_path = args.eval_data
        if args.benchmark:
            eval_data_path = str(_PROJECT_ROOT / "training" / "data" / "eval_benchmark.jsonl")
        eval_problems = load_eval_dataset(eval_data_path)
        if args.eval_150:
            eval_problems = _sample_uniform_150(eval_problems)

        cerebras_client = None
        if (args.hybrid_verify or args.judge) and HAS_CEREBRAS:
            try:
                cerebras_client = CerebrasClient()
            except Exception as e:
                logger.warning(f"Cerebras init failed: {e}")

        comparison = compare_live(
            model_a=args.model_a,
            stage_a=args.stage_a,
            model_b=args.model_b,
            stage_b=args.stage_b,
            eval_problems=eval_problems,
            ollama_host=args.ollama_host,
            num_workers=args.workers,
            cerebras_client=cerebras_client,
            run_judge=args.judge,
            judge_n=args.judge_n,
            reports_dir=args.reports_dir,
            completions_dir=args.completions_dir,
            save_completions=args.save_completions,
            resume=args.resume,
            checkpoint_dir=args.checkpoint_dir,
            full_judge=args.full_judge,
        )
        if args.wandb and HAS_CEREBRAS:
            for side in ("model_a", "model_b"):
                m = comparison[side]
                log_eval_to_wandb(m["results"], m["stage"], "local", m["model"], args.wandb_project)
        return

    if args.command is None:
        parser.print_help()
        return

    # Resolve eval data path
    eval_data_path = args.eval_data
    if args.benchmark:
        eval_data_path = str(_PROJECT_ROOT / "training" / "data" / "eval_benchmark.jsonl")

    # Load eval dataset
    if args.problem_file:
        eval_problems = load_eval_dataset(args.problem_file)
        logger.info(f"Loaded {len(eval_problems)} problems from --problem-file {args.problem_file}")
    else:
        eval_problems = load_eval_dataset(eval_data_path)

        # --eval-150: uniform 10-per-(domain,difficulty)-cell preset
        if args.eval_150:
            eval_problems = _sample_uniform_150(eval_problems)
        # Legacy stratified sampling
        elif args.stratified and args.max_samples > 0:
            eval_problems = stratified_sample(eval_problems, args.max_samples)
            logger.info(f"Stratified sample: {len(eval_problems)} problems selected")

    # KV cache quantization: server-side env var recommendation
    kv_type = os.environ.get("OLLAMA_KV_CACHE_TYPE", "f16")
    if args.kv_quant or kv_type != "q8_0":
        opts = _build_ollama_options("accuracy")
        logger.info(
            f"KV cache: num_ctx={opts['num_ctx']}, type={kv_type}. "
            f"For ~4x less memory vs baseline (f16/16384): "
            f"PowerShell: $env:OLLAMA_KV_CACHE_TYPE = 'q8_0' (before ollama serve). "
            f"Current saving vs baseline: "
            f"{'2x (ctx only)' if kv_type == 'f16' else '4x (ctx + q8_0)'}"
        )

    # Init Cerebras client when needed (hybrid verify or socratic judge)
    cerebras_client: Any = None
    if (args.hybrid_verify or args.judge) and HAS_CEREBRAS:
        try:
            cerebras_client = CerebrasClient()
            logger.info("Cerebras client initialized (hybrid verify + socratic judge)")
        except Exception as e:
            logger.warning(f"Cerebras client init failed: {e} — falling back to SymPy-only")
    elif (args.hybrid_verify or args.judge) and not HAS_CEREBRAS:
        logger.warning(
            "--hybrid-verify/--judge requested but training.cerebras_client not importable"
        )

    # Auto-resolve adapter from stage name
    adapter_source = args.adapter or STAGE_HF_REPOS.get(args.stage, "")
    if args.mode == "colab" and not adapter_source:
        logger.error("--adapter is required for colab mode (or use a known stage name)")
        return

    # Build completions path: evaluation/completions/{stage}_{model}_{timestamp}.jsonl
    completions_path = None
    if args.save_completions:
        os.makedirs(args.completions_dir, exist_ok=True)
        model_tag = (args.model or adapter_source or args.stage).replace("/", "_").replace(":", "_")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        completions_path = os.path.join(
            args.completions_dir, f"{args.stage}_{model_tag}_{ts}.jsonl"
        )

    if args.mode == "colab":
        results = evaluate_colab(
            adapter_source=adapter_source,
            eval_problems=eval_problems,
            max_samples=args.max_samples,
            completions_path=completions_path,
        )

        report_path = save_report(results, args.stage, "colab", adapter_source, args.reports_dir)
        append_summary_csv(results, args.stage)
        if args.wandb:
            log_eval_to_wandb(results, args.stage, "colab", adapter_source, args.wandb_project)

        if args.export_gguf:
            gguf_dir = os.path.join("evaluation", "gguf", args.stage)
            gguf_path = export_gguf_from_adapter(adapter_source, gguf_dir, args.quantization)
            logger.info(f"GGUF exported: {gguf_path}")

    elif args.mode == "local":
        model_name = args.model
        if not model_name:
            logger.error("--model is required for local mode")
            return

        results = evaluate_local(
            model_name=model_name,
            eval_problems=eval_problems,
            ollama_host=args.ollama_host,
            max_samples=args.max_samples,
            num_workers=args.workers,
            completions_path=completions_path,
            cerebras_client=cerebras_client,
            checkpoint_path=_checkpoint_path(model_name, args.stage, args.checkpoint_dir),
            resume=args.resume,
            full_judge=args.full_judge,
        )

        # Optional: combined Socratic quality + correctness pass
        if args.judge and cerebras_client is not None:
            socratic = evaluate_combined_pass(
                model_name=model_name,
                problems=eval_problems,
                ollama_host=args.ollama_host,
                cerebras_client=cerebras_client,
                n_judge=args.judge_n,
            )
            results["socratic"] = socratic
            logger.info(
                f"Combined judge (n={socratic['n_judged']}): "
                f"socratic={socratic.get('socratic_score')}, "
                f"is_correct={socratic.get('is_correct_rate')}, "
                f"guides={socratic.get('guides_student')}, "
                f"no_leak={socratic.get('no_answer_leak')}"
            )

        report_path = save_report(results, args.stage, "local", model_name, args.reports_dir)
        append_summary_csv(results, args.stage)
        if args.wandb:
            log_eval_to_wandb(results, args.stage, "local", model_name, args.wandb_project)


if __name__ == "__main__":
    main()
