"""
Hybrid STEM Reward Module for GRPO Training

Provides reward functions for TRL GRPOTrainer that combine:
- Domain-specific correctness verification (imports from verify_answers.py)
- Reasoning quality scoring (step count, coherence)
- Socratic style scoring (guiding questions in visible answer)

Combined reward: 1.0*correct + 0.2*reasoning + 0.1*socratic + 0.0*wrong (no negative penalties)

GDPO-compatible reward functions (arXiv 2601.05242):
    from training.scripts.stem_rewards import make_gdpo_reward_fns

    reward_fns = make_gdpo_reward_fns(problems_list, tokenizer)
    trainer = GRPOTrainer(
        ...,
        reward_funcs=reward_fns,          # [correctness_fn, format_fn, socratic_fn]
        reward_weights=[0.7, 0.15, 0.15],
    )

Usage with TRL GRPOTrainer:
    from training.scripts.stem_rewards import make_reward_fn

    reward_fn = make_reward_fn(problems_dataset)
    trainer = GRPOTrainer(
        ...,
        reward_funcs=[reward_fn],
    )
"""

import re
import logging
from typing import List, Dict, Any, Optional, Callable

import numpy as np

logger = logging.getLogger(__name__)

# Import verification primitives from T002
from training.scripts.verify_answers import (
    verify,
    verify_math,
    verify_physics,
    verify_chemistry,
    verify_code,
    verify_mc,
    rubric_judge,
    extract_answer,
    VerificationResult,
)


# ---------------------------------------------------------------------------
# Reasoning quality scoring
# ---------------------------------------------------------------------------

def score_reasoning(completion: str) -> float:
    """Score reasoning quality in model completion (0.0-1.0).

    Evaluates:
    - Presence of thinking tags
    - Step count and structure
    - Logical connectors
    """
    score = 0.0

    # Has thinking section?
    has_thinking = "<think>" in completion and "</think>" in completion
    if has_thinking:
        thinking = completion.split("<think>")[1].split("</think>")[0]
    else:
        thinking = completion

    # Step count (numbered steps, bullet points)
    step_patterns = [
        r'\d+[.)]\s',           # 1. or 1)
        r'шаг\s*\d',            # шаг 1
        r'step\s*\d',           # step 1
        r'во-первых|во-вторых|в-третьих',  # firstly, secondly
        r'далее|затем|потом',   # then, next
    ]
    step_count = sum(len(re.findall(p, thinking, re.IGNORECASE)) for p in step_patterns)

    if step_count >= 3:
        score += 0.4
    elif step_count >= 1:
        score += 0.2

    # Logical connectors
    connectors = [
        r'потому что|так как|поскольку',  # because
        r'следовательно|значит|поэтому',  # therefore
        r'если.*то',                       # if...then
        r'подставим|применим|используем',  # let's substitute/apply/use
    ]
    connector_count = sum(
        len(re.findall(p, thinking, re.IGNORECASE)) for p in connectors
    )
    if connector_count >= 2:
        score += 0.3
    elif connector_count >= 1:
        score += 0.15

    # Has structured thinking
    if has_thinking:
        score += 0.2

    # Penalize extremely short thinking
    if len(thinking.split()) < 10:
        score *= 0.5

    # Penalize repetition
    lines = thinking.strip().split('\n')
    if len(lines) > 3:
        unique_lines = set(l.strip().lower() for l in lines if l.strip())
        repetition_ratio = len(unique_lines) / len(lines)
        if repetition_ratio < 0.5:
            score *= 0.5

    return min(1.0, score)


# ---------------------------------------------------------------------------
# Socratic style scoring
# ---------------------------------------------------------------------------

def score_socratic(completion: str) -> float:
    """Score Socratic tutoring style in visible answer (0.0-1.0).

    Checks for guiding questions in the part AFTER </think>.
    A good Socratic tutor asks questions, not gives answers directly.
    """
    # Get visible answer (after thinking)
    if "</think>" in completion:
        visible = completion.split("</think>")[-1].strip()
    else:
        visible = completion.strip()

    if not visible:
        return 0.0

    score = 0.0

    # Has question marks (guiding questions)?
    question_count = visible.count("?")
    if question_count >= 2:
        score += 0.5
    elif question_count >= 1:
        score += 0.3

    # Socratic patterns (Russian)
    socratic_patterns = [
        r"как ты думаешь",
        r"что ты.*думаешь",
        r"попробуй",
        r"подумай",
        r"вспомни",
        r"давай разберём",
        r"давай подумаем",
        r"а если",
        r"что будет если",
        r"как можно",
        r"какой.*способ",
        r"почему",
    ]
    pattern_hits = sum(
        1 for p in socratic_patterns
        if re.search(p, visible, re.IGNORECASE)
    )
    if pattern_hits >= 2:
        score += 0.4
    elif pattern_hits >= 1:
        score += 0.2

    # Penalty for direct telling
    telling_patterns = [
        r"ответ\s*[:=]",
        r"правильный ответ",
        r"решение\s*[:=]",
        r"запомни\s*[:=]",
    ]
    telling_hits = sum(
        1 for p in telling_patterns
        if re.search(p, visible, re.IGNORECASE)
    )
    if telling_hits > 0:
        score -= 0.3 * telling_hits

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Combined reward function
# ---------------------------------------------------------------------------

def compute_reward(
    completion: str,
    ground_truth: str,
    domain: str,
    question_type: str = "calc",
    test_cases: Optional[List[Dict]] = None,
    rubric: Optional[List[Dict]] = None,
    reference: Optional[str] = None,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Compute combined reward for a single completion.

    Default weights:
        correct: +1.0, wrong: 0.0, reasoning: +0.2, socratic: +0.1

    Returns: float reward value
    """
    w = weights or {
        "correct": 1.0,
        "wrong": 0.0,       # No negative penalties (DRPO arXiv 2510.04474, GRPO-LEAD)
        "reasoning": 0.2,
        "socratic": 0.1,
    }

    # 1. Correctness (domain-specific)
    answer = extract_answer(completion)
    result = verify(
        answer=answer,
        truth=ground_truth,
        domain=domain,
        question_type=question_type,
        test_cases=test_cases,
        rubric=rubric,
        reference=reference,
    )

    if result.correct:
        reward = w["correct"]
    else:
        reward = w["wrong"]

    # 2. Reasoning quality bonus
    reasoning_score = score_reasoning(completion)
    reward += w["reasoning"] * reasoning_score

    # 3. Socratic style bonus (only for correct answers)
    if result.correct:
        socratic_score = score_socratic(completion)
        reward += w["socratic"] * socratic_score

    return reward


# ---------------------------------------------------------------------------
# GRPOTrainer-compatible reward function factory
# ---------------------------------------------------------------------------

def make_reward_fn(
    problems: List[Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None,
) -> Callable:
    """Create a reward function compatible with TRL GRPOTrainer.

    Args:
        problems: List of problem dicts with ground_truth, domain, type fields.
                  Must be aligned with the prompts in the same order.
        weights: Optional custom reward weights.

    Returns:
        A function(completions, **kwargs) -> list[float]

    Usage:
        reward_fn = make_reward_fn(problems_list)
        trainer = GRPOTrainer(
            ...,
            reward_funcs=[reward_fn],
        )
    """
    # Build lookup by prompt text
    problem_lookup: Dict[str, Dict] = {}
    for p in problems:
        prompt = p.get("prompt", p.get("instruction", ""))
        problem_lookup[prompt.strip()] = p

    def reward_fn(completions: List[str], prompts: Optional[List[str]] = None, **kwargs) -> List[float]:
        """Compute rewards for a batch of completions."""
        rewards = []

        for i, completion in enumerate(completions):
            # Find matching problem
            prompt = prompts[i].strip() if prompts and i < len(prompts) else ""
            problem = problem_lookup.get(prompt)

            if problem is None:
                # Try to find by index
                if i < len(problems):
                    problem = problems[i]
                else:
                    logger.warning(f"No problem found for completion {i}")
                    rewards.append(0.0)
                    continue

            reward = compute_reward(
                completion=completion,
                ground_truth=problem.get("ground_truth", problem.get("answer", "")),
                domain=problem.get("domain", "math"),
                question_type=problem.get("type", "calc"),
                test_cases=problem.get("test_cases"),
                rubric=problem.get("rubric"),
                reference=problem.get("reference"),
                weights=weights,
            )
            rewards.append(reward)

        return rewards

    return reward_fn


def make_domain_reward_fns(
    problems: List[Dict[str, Any]],
) -> Dict[str, Callable]:
    """Create separate reward functions per domain for monitoring.

    Returns dict mapping domain -> reward_fn for per-domain reward tracking.
    """
    domain_problems: Dict[str, List[Dict]] = {}
    for p in problems:
        domain = p.get("domain", "math")
        domain_problems.setdefault(domain, []).append(p)

    return {
        domain: make_reward_fn(probs)
        for domain, probs in domain_problems.items()
    }


# ---------------------------------------------------------------------------
# GDPO-compatible reward functions (arXiv 2601.05242)
# Each function is passed separately to TRL GRPOTrainer so that rewards
# are normalized independently, preventing reward hacking/collapse.
# ---------------------------------------------------------------------------

def make_gdpo_correctness_fn(
    problems: List[Dict[str, Any]],
    tokenizer: Any,
    system_prompt: str = "Ты — репетитор по STEM. Реши задачу пошагово и запиши финальный ответ в \\boxed{}.",
    dithering_sigma: float = 0.0,
) -> Callable:
    """Create a correctness reward function for GDPO-style training.

    Returns a callable matching TRL GRPOTrainer signature:
        (completions, prompts=None, **kwargs) -> list[float]

    Uses verify_answers.py for domain-specific verification.
    Rewards: correct=1.0, wrong=0.0 (no negative penalties per DRPO/GRPO-LEAD).

    When dithering_sigma > 0, applies Reward Dithering (ReDit, arXiv:2506.18631):
    small Gaussian noise is added to binary rewards to create continuous gradient
    landscape, preventing zero-variance groups and improving convergence ~10x.

    Supports multiple answer types: problems with answer_type="mc_letter" are
    registered with an MC-specific system prompt for correct prompt lookup.

    Args:
        problems: List of problem dicts with prompt, answer, domain, type fields.
        tokenizer: HuggingFace tokenizer for chat template formatting.
        system_prompt: System prompt used for calc/numeric problems.
        dithering_sigma: Gaussian noise std for reward dithering (0.0 = disabled).
                         Recommended: 0.05 per ReDit paper (arXiv:2506.18631).
    """
    MC_SYSTEM_PROMPT = "Проанализируй задачу и выбери правильный ответ (A, B, C или D)."

    # Build lookup by formatted prompt text — route by answer_type
    prompt_to_problem: Dict[str, Dict] = {}
    for p in problems:
        answer_type = p.get("answer_type", "numeric")
        if answer_type == "mc_letter":
            sys_prompt = MC_SYSTEM_PROMPT
        else:
            sys_prompt = system_prompt

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": p.get("prompt", p.get("instruction", ""))},
        ]
        formatted = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        prompt_to_problem[formatted.strip()] = p

    def correctness_fn(completions: List[str], prompts: Optional[List[str]] = None, **kwargs) -> List[float]:
        """Compute correctness rewards: 1.0 (correct) or 0.0 (wrong)."""
        if prompts is None:
            prompts = [""] * len(completions)
        rewards = []
        for prompt_text, completion_text in zip(prompts, completions):
            problem = prompt_to_problem.get(prompt_text.strip())
            if problem is None:
                rewards.append(0.0)
                continue

            answer_text = extract_answer(completion_text)
            truth = problem.get("ground_truth", problem.get("answer", ""))
            domain = problem.get("domain", "math")
            answer_type = problem.get("answer_type", "numeric")

            # Map answer_type to question_type for verify() router
            if answer_type == "mc_letter":
                q_type = "mc"
            else:
                q_type = problem.get("type", "calc")

            result = verify(
                answer=answer_text,
                truth=truth,
                domain=domain,
                question_type=q_type,
                test_cases=problem.get("test_cases"),
                rubric=problem.get("rubric"),
                reference=problem.get("reference"),
            )
            rewards.append(1.0 if result.correct else 0.0)

        # ReDit: Reward Dithering (arXiv:2506.18631)
        # Add small Gaussian noise to break ties in zero-variance groups,
        # creating continuous gradient landscape for better RL convergence.
        if dithering_sigma > 0:
            noise = np.random.normal(0.0, dithering_sigma, size=len(rewards))
            rewards = [r + n for r, n in zip(rewards, noise)]

        return rewards

    return correctness_fn


def make_gdpo_format_fn(
    problems: Optional[List[Dict[str, Any]]] = None,
    tokenizer: Any = None,
    system_prompts: Optional[Dict[str, str]] = None,
) -> Callable:
    """Create a format reward function for GDPO-style training.

    Answer-type-aware scoring:
    - calc/numeric/latex: \\boxed{} presence (0.5) + step markers (0.3) + length (0.2)
    - MC (mc_letter): "Answer: X" pattern (0.5) + reasoning markers (0.3) + length (0.2)
    - physics with units: \\boxed{} (0.4) + unit mention (0.2) + step markers (0.2) + length (0.2)

    Args:
        problems: Optional list of problem dicts with answer_type field.
                  When provided, enables type-aware scoring via prompt lookup.
        tokenizer: Required if problems is provided, for chat template formatting.
        system_prompts: Optional dict mapping answer_type to system prompt string.
                        Used for prompt-to-problem lookup.

    Returns a callable matching TRL GRPOTrainer signature:
        (completions, prompts=None, **kwargs) -> list[float]
    """
    # Build prompt-to-answer-type lookup if problems provided
    prompt_to_type: Dict[str, str] = {}
    if problems is not None and tokenizer is not None:
        default_prompts = system_prompts or {}
        for p in problems:
            answer_type = p.get("answer_type", "numeric")
            sys_prompt = default_prompts.get(
                answer_type,
                "Ты — репетитор по STEM. Реши задачу пошагово и запиши финальный ответ в \\boxed{}.",
            )
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": p.get("prompt", p.get("instruction", ""))},
            ]
            formatted = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            prompt_to_type[formatted.strip()] = answer_type

    def format_fn(completions: List[str], prompts: Optional[List[str]] = None, **kwargs) -> List[float]:
        """Score format quality of completions, returns values in [0, 1]."""
        rewards = []
        for i, completion in enumerate(completions):
            text = completion if isinstance(completion, str) else str(completion)

            # Determine answer type from prompt lookup
            answer_type = "numeric"  # default: calc-style scoring
            if prompts is not None and i < len(prompts) and prompt_to_type:
                answer_type = prompt_to_type.get(prompts[i].strip(), "numeric")

            score = _score_format_by_type(text, answer_type)
            rewards.append(min(1.0, score))
        return rewards

    return format_fn


def _score_format_by_type(text: str, answer_type: str) -> float:
    """Score format quality based on answer type."""
    text_lower = text.lower()
    word_count = len(text.split())

    # Shared: step-by-step reasoning markers
    step_markers = [
        "step", "therefore", "thus", "hence", "because",
        "шаг", "следовательно", "значит", "потому что", "так как",
        "далее", "подставим", "найдём", "получим", "вычислим",
    ]
    has_steps = any(m in text_lower for m in step_markers)
    reasonable_length = 50 < word_count < 800

    if answer_type == "mc_letter":
        score = 0.0
        # MC: reward "Answer: X" or "Ответ: X" pattern with letter
        mc_pattern = re.search(
            r'(?:answer|ответ)\s*[:=]\s*[A-DА-Г]', text, re.IGNORECASE
        )
        if mc_pattern:
            score += 0.5
        # Reasoning before answer
        if has_steps:
            score += 0.3
        if reasonable_length:
            score += 0.2
        return score

    elif answer_type == "numeric_with_unit":
        score = 0.0
        # Physics: boxed answer
        if "\\boxed{" in text:
            score += 0.4
        # Unit mention (common physics units)
        unit_patterns = [
            r'\b(м/с|кг|Дж|Н|Па|Вт|А|В|Ом|Гц|м²|м³|моль|К)\b',
            r'\b(m/s|kg|J|N|Pa|W|A|V|Hz|mol|K|eV|cm|mm)\b',
        ]
        if any(re.search(p, text) for p in unit_patterns):
            score += 0.2
        if has_steps:
            score += 0.2
        if reasonable_length:
            score += 0.2
        return score

    else:
        # Default calc/numeric/latex_boxed scoring
        score = 0.0
        if "\\boxed{" in text:
            score += 0.5
        if has_steps:
            score += 0.3
        if reasonable_length:
            score += 0.2
        return score


def make_gdpo_socratic_fn() -> Callable:
    """Create a Socratic style reward function for GDPO-style training.

    Scores pedagogical quality of the visible answer (after </think>):
    - Guiding questions (? marks)
    - Socratic patterns (Russian: "как ты думаешь", "попробуй", etc.)
    - Penalty for direct telling ("ответ:", "правильный ответ")

    This is the 3rd GDPO reward signal, normalized independently from
    correctness and format. Encourages the model to guide rather than tell.

    Returns a callable matching TRL GRPOTrainer signature:
        (completions, prompts=None, **kwargs) -> list[float]
    """
    def socratic_fn(completions: List[str], prompts: Optional[List[str]] = None, **kwargs) -> List[float]:
        """Score Socratic tutoring quality for each completion."""
        return [score_socratic(c if isinstance(c, str) else str(c)) for c in completions]

    return socratic_fn


def make_gdpo_reward_fns(
    problems: List[Dict[str, Any]],
    tokenizer: Any,
    system_prompt: str = "Ты — репетитор по STEM. Реши задачу пошагово и запиши финальный ответ в \\boxed{}.",
    dithering_sigma: float = 0.0,
    include_socratic: bool = True,
) -> List[Callable]:
    """Create GDPO-compatible reward function list for TRL GRPOTrainer.

    Returns [correctness_fn, format_fn, socratic_fn] — three separate callables
    that TRL normalizes independently before combining with reward_weights.

    This is the GDPO approach (arXiv 2601.05242): decoupled normalization
    preserves each reward's relative differences, preventing reward hacking
    that occurs when summing rewards before normalization.

    The Socratic reward (3rd signal) encourages pedagogical tutoring style:
    guiding questions, scaffolding patterns, penalizes direct answer-giving.

    Usage:
        reward_fns = make_gdpo_reward_fns(problems, tokenizer, dithering_sigma=0.05)
        trainer = GRPOTrainer(
            ...,
            reward_funcs=reward_fns,          # [correctness, format, socratic]
            reward_weights=[0.7, 0.15, 0.15], # GDPO decoupled weights
        )

    Args:
        problems: List of problem dicts with prompt, answer, domain, type fields.
        tokenizer: HuggingFace tokenizer for chat template formatting.
        system_prompt: System prompt used in chat template.
        dithering_sigma: Gaussian noise std for ReDit reward dithering (0.0 = off).
        include_socratic: Whether to include Socratic reward (default True).
                          Set False for backward compat with 2-reward setup.

    Returns:
        List of callables: [correctness_fn, format_fn] or
        [correctness_fn, format_fn, socratic_fn] if include_socratic=True
    """
    correctness_fn = make_gdpo_correctness_fn(
        problems, tokenizer, system_prompt, dithering_sigma=dithering_sigma,
    )
    format_fn = make_gdpo_format_fn(
        problems=problems,
        tokenizer=tokenizer,
        system_prompts={"mc_letter": "Проанализируй задачу и выбери правильный ответ (A, B, C или D)."},
    )
    fns = [correctness_fn, format_fn]
    if include_socratic:
        fns.append(make_gdpo_socratic_fn())
    return fns


# ---------------------------------------------------------------------------
# Batch evaluation utility
# ---------------------------------------------------------------------------

def evaluate_completions(
    completions: List[str],
    problems: List[Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Evaluate a batch of completions and return detailed statistics.

    Returns:
        Dict with overall_reward, per_domain stats, correctness rate, etc.
    """
    from collections import defaultdict

    domain_stats = defaultdict(lambda: {
        "total": 0, "correct": 0, "rewards": [],
        "reasoning_scores": [], "socratic_scores": [],
    })
    all_rewards = []

    for completion, problem in zip(completions, problems):
        domain = problem.get("domain", "math")
        q_type = problem.get("type", "calc")
        truth = problem.get("ground_truth", problem.get("answer", ""))

        answer = extract_answer(completion)
        result = verify(
            answer=answer, truth=truth,
            domain=domain, question_type=q_type,
            test_cases=problem.get("test_cases"),
            rubric=problem.get("rubric"),
            reference=problem.get("reference"),
        )

        reward = compute_reward(
            completion=completion,
            ground_truth=truth,
            domain=domain,
            question_type=q_type,
            test_cases=problem.get("test_cases"),
            rubric=problem.get("rubric"),
            reference=problem.get("reference"),
            weights=weights,
        )

        r_score = score_reasoning(completion)
        s_score = score_socratic(completion)

        stats = domain_stats[domain]
        stats["total"] += 1
        if result.correct:
            stats["correct"] += 1
        stats["rewards"].append(reward)
        stats["reasoning_scores"].append(r_score)
        stats["socratic_scores"].append(s_score)
        all_rewards.append(reward)

    # Aggregate
    overall = {
        "total": len(completions),
        "mean_reward": sum(all_rewards) / len(all_rewards) if all_rewards else 0,
        "correct_rate": sum(
            1 for d in domain_stats.values() for _ in range(d["correct"])
        ) / len(completions) if completions else 0,
    }

    per_domain = {}
    for domain, stats in domain_stats.items():
        per_domain[domain] = {
            "total": stats["total"],
            "correct": stats["correct"],
            "accuracy": stats["correct"] / stats["total"] if stats["total"] else 0,
            "mean_reward": sum(stats["rewards"]) / len(stats["rewards"]) if stats["rewards"] else 0,
            "mean_reasoning": sum(stats["reasoning_scores"]) / len(stats["reasoning_scores"]) if stats["reasoning_scores"] else 0,
            "mean_socratic": sum(stats["socratic_scores"]) / len(stats["socratic_scores"]) if stats["socratic_scores"] else 0,
        }

    return {"overall": overall, "per_domain": per_domain}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import argparse

    parser = argparse.ArgumentParser(description="STEM Rewards Evaluation")
    parser.add_argument("--completions", required=True,
                        help="JSONL with completions (fields: completion, prompt)")
    parser.add_argument("--problems", required=True,
                        help="JSONL with problems (fields: prompt, ground_truth, domain, type)")
    parser.add_argument("--output", default="evaluation/reports/rewards.json")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # Load data
    with open(args.completions, "r", encoding="utf-8") as f:
        completions_data = [json.loads(l) for l in f]
    with open(args.problems, "r", encoding="utf-8") as f:
        problems_data = [json.loads(l) for l in f]

    completions = [c.get("completion", c.get("output", "")) for c in completions_data]
    results = evaluate_completions(completions, problems_data)

    from pathlib import Path
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(json.dumps(results, indent=2, ensure_ascii=False))
