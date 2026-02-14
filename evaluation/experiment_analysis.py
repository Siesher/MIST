"""
Statistical Analysis for A/B Experiments

Computes group means, t-test, Cohen's d, confidence intervals.

Usage:
    from evaluation.experiment_analysis import analyze_experiment
    results = analyze_experiment(control_scores, treatment_scores)
"""

import math
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class GroupStats:
    """Statistics for one experimental group."""
    group: str
    n: int
    mean: float
    std: float
    min_val: float
    max_val: float
    mean_gain: float  # post - pre mean


@dataclass
class ExperimentAnalysis:
    """Full experiment analysis result."""
    control: GroupStats
    treatment: GroupStats
    t_statistic: float
    p_value: float
    cohens_d: float
    ci_lower: float
    ci_upper: float
    significant: bool  # p < 0.05


def _mean(data: List[float]) -> float:
    return sum(data) / len(data) if data else 0.0


def _std(data: List[float]) -> float:
    if len(data) < 2:
        return 0.0
    m = _mean(data)
    return math.sqrt(sum((x - m) ** 2 for x in data) / (len(data) - 1))


def _t_test_independent(group1: List[float], group2: List[float]) -> tuple:
    """Independent samples t-test (Welch's t-test)."""
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return 0.0, 1.0

    m1, m2 = _mean(group1), _mean(group2)
    s1, s2 = _std(group1), _std(group2)

    se = math.sqrt(s1**2 / n1 + s2**2 / n2)
    if se == 0:
        return 0.0, 1.0

    t = (m1 - m2) / se

    # Welch-Satterthwaite degrees of freedom
    num = (s1**2 / n1 + s2**2 / n2) ** 2
    denom = (s1**2 / n1) ** 2 / (n1 - 1) + (s2**2 / n2) ** 2 / (n2 - 1)
    df = num / denom if denom > 0 else n1 + n2 - 2

    # Approximate p-value using normal distribution (for large samples)
    # For small samples this is an approximation
    p = 2 * (1 - _normal_cdf(abs(t)))

    return t, p


def _normal_cdf(x: float) -> float:
    """Approximate standard normal CDF."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _cohens_d(group1: List[float], group2: List[float]) -> float:
    """Compute Cohen's d effect size."""
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return 0.0

    m1, m2 = _mean(group1), _mean(group2)
    s1, s2 = _std(group1), _std(group2)

    # Pooled standard deviation
    sp = math.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
    if sp == 0:
        return 0.0

    return (m2 - m1) / sp  # Positive = treatment better


def analyze_experiment(
    control_pre: List[float],
    control_post: List[float],
    treatment_pre: List[float],
    treatment_post: List[float],
) -> ExperimentAnalysis:
    """
    Analyze A/B experiment results.

    Computes gain scores (post - pre) and runs statistical tests.

    Args:
        control_pre: Pre-test scores for control group
        control_post: Post-test scores for control group
        treatment_pre: Pre-test scores for treatment group
        treatment_post: Post-test scores for treatment group

    Returns:
        ExperimentAnalysis with statistics and significance
    """
    # Compute gain scores
    control_gains = [post - pre for pre, post in zip(control_pre, control_post)]
    treatment_gains = [post - pre for pre, post in zip(treatment_pre, treatment_post)]

    # Group stats
    control_stats = GroupStats(
        group="control",
        n=len(control_gains),
        mean=_mean(control_post),
        std=_std(control_post),
        min_val=min(control_post) if control_post else 0,
        max_val=max(control_post) if control_post else 0,
        mean_gain=_mean(control_gains),
    )

    treatment_stats = GroupStats(
        group="treatment",
        n=len(treatment_gains),
        mean=_mean(treatment_post),
        std=_std(treatment_post),
        min_val=min(treatment_post) if treatment_post else 0,
        max_val=max(treatment_post) if treatment_post else 0,
        mean_gain=_mean(treatment_gains),
    )

    # Statistical tests on gain scores
    t_stat, p_value = _t_test_independent(control_gains, treatment_gains)
    d = _cohens_d(control_gains, treatment_gains)

    # 95% CI for difference in means
    diff = _mean(treatment_gains) - _mean(control_gains)
    se_diff = math.sqrt(
        _std(treatment_gains)**2 / max(len(treatment_gains), 1) +
        _std(control_gains)**2 / max(len(control_gains), 1)
    )
    ci_lower = diff - 1.96 * se_diff
    ci_upper = diff + 1.96 * se_diff

    return ExperimentAnalysis(
        control=control_stats,
        treatment=treatment_stats,
        t_statistic=t_stat,
        p_value=p_value,
        cohens_d=d,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        significant=p_value < 0.05,
    )


def format_report(analysis: ExperimentAnalysis) -> str:
    """Format analysis as a readable report."""
    lines = [
        "# Результаты A/B эксперимента",
        "",
        "## Описательная статистика",
        "",
        f"| Группа | N | Mean | SD | Mean Gain |",
        f"|--------|--:|-----:|---:|----------:|",
        f"| Control | {analysis.control.n} | {analysis.control.mean:.3f} | {analysis.control.std:.3f} | {analysis.control.mean_gain:+.3f} |",
        f"| Treatment | {analysis.treatment.n} | {analysis.treatment.mean:.3f} | {analysis.treatment.std:.3f} | {analysis.treatment.mean_gain:+.3f} |",
        "",
        "## Статистический анализ",
        "",
        f"- **t-статистика**: {analysis.t_statistic:.4f}",
        f"- **p-value**: {analysis.p_value:.4f}",
        f"- **Cohen's d**: {analysis.cohens_d:.4f}",
        f"- **95% CI**: [{analysis.ci_lower:.4f}, {analysis.ci_upper:.4f}]",
        f"- **Значимость (p<0.05)**: {'Да' if analysis.significant else 'Нет'}",
        "",
    ]

    # Effect size interpretation
    d = abs(analysis.cohens_d)
    if d < 0.2:
        effect = "незначительный"
    elif d < 0.5:
        effect = "малый"
    elif d < 0.8:
        effect = "средний"
    else:
        effect = "большой"
    lines.append(f"Размер эффекта: **{effect}** (|d|={d:.3f})")

    return "\n".join(lines)
