"""
Hybrid STEM Reward Module for GRPO Training

Provides reward functions for TRL GRPOTrainer that combine:
- Domain-specific correctness verification (imports from verify_answers.py)
- Reasoning quality scoring (step count, coherence)
- Socratic style scoring (guiding questions in visible answer)

Combined reward: 1.0*correct + 0.2*reasoning + 0.1*socratic - 0.5*wrong

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
        correct: +1.0, wrong: -0.5, reasoning: +0.2, socratic: +0.1

    Returns: float reward value
    """
    w = weights or {
        "correct": 1.0,
        "wrong": -0.5,
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
