"""
Discrete Lévy flight sampler for PathSlime (feature 018).

Lévy flights — random walks с heavy-tailed step length distribution, которые
доказано эффективны для exploration в графах (Viswanathan 1999). В отличие
от Gaussian walks, Lévy генерирует occasional длинные прыжки → естественная
diversity между путями через один и тот же граф.

Используем для перекодировки ожиданий при выборе рёбер: Lévy-scaled multiplier
умножается на базовую вероятность перехода, делая "дальние" (low-probability)
рёбра иногда доминирующими.

References:
- Viswanathan et al. (1999). Optimizing the success of random searches.
  Nature 401:911-914
- Mantegna (1994). Fast, accurate algorithm for numerical simulation of
  Lévy stable stochastic processes. Phys. Rev. E 49:4677
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# Default Lévy stability parameter.
# α=2.0 → Gaussian (no heavy tail);
# α=1.5 → classic Lévy flight (moderate heavy tail, biologically plausible);
# α=1.0 → Cauchy distribution (very heavy tail, too volatile для graph).
DEFAULT_ALPHA: float = 1.5

# Clip bounds для Lévy samples — предотвращают numerical explosions.
# Graph edge probabilities ∈ [0, 1], multiplier вне [0.05, 20] не имеет смысла.
MIN_MULTIPLIER: float = 0.05
MAX_MULTIPLIER: float = 20.0


def levy_multiplier(
    alpha: float = DEFAULT_ALPHA,
    n: int = 1,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """Генерирует n samples из Lévy-stable distribution для масштабирования.

    Implementation: Mantegna (1994) algorithm — быстрый приближённый метод,
    работает для α ∈ (0, 2). Не требует scipy.stats для базового случая,
    но внутри используем scipy.stats.levy_stable когда доступно.

    Args:
        alpha: Stability parameter. 1 < α ≤ 2. Default 1.5 (biologically
            plausible from Viswanathan 1999 foraging studies).
        n: Number of samples to generate.
        rng: Optional numpy Generator для reproducibility.

    Returns:
        Array shape (n,) с absolute-value Lévy samples в [MIN_MULTIPLIER,
        MAX_MULTIPLIER]. Positive values only (берём |x|), подходит для
        scaling рёберных весов.
    """
    if rng is None:
        rng = np.random.default_rng()

    if not 0 < alpha <= 2:
        raise ValueError(f"alpha must be in (0, 2], got {alpha}")

    # Mantegna 1994 algorithm — fast approximate Lévy-stable sampling.
    # Works for 1 < α ≤ 2 (включая наш diapason).
    # sigma_u scales Gaussian numerator; v — Gaussian denominator.
    from math import gamma, pi, sin

    sigma_u = (
        gamma(1 + alpha)
        * sin(pi * alpha / 2)
        / (gamma((1 + alpha) / 2) * alpha * 2 ** ((alpha - 1) / 2))
    ) ** (1 / alpha)

    u = rng.normal(0, sigma_u, n)
    v = rng.normal(0, 1, n)
    # Take absolute value to guarantee positive multipliers
    samples = np.abs(u / (np.abs(v) ** (1 / alpha)))

    # Clip to safe range
    return np.clip(samples, MIN_MULTIPLIER, MAX_MULTIPLIER)


def weighted_choice_with_levy(
    choices: list,
    weights: np.ndarray,
    alpha: float = DEFAULT_ALPHA,
    rng: Optional[np.random.Generator] = None,
) -> int:
    """Выбор одного индекса из choices с Lévy-perturbed probabilities.

    Стандартный weighted random choice, но веса умножаются на Lévy samples,
    что occasionally создаёт долгие прыжки по maldow-probability рёбрам.

    Args:
        choices: List of items (used only for length; возвращаемый index в него).
        weights: Base weights (non-negative, need not sum to 1).
        alpha: Lévy stability parameter.
        rng: Optional RNG.

    Returns:
        Selected index into `choices`.
    """
    if rng is None:
        rng = np.random.default_rng()
    if len(choices) == 0:
        raise ValueError("cannot choose from empty list")
    if len(weights) != len(choices):
        raise ValueError(f"weights length {len(weights)} != choices {len(choices)}")

    w = np.asarray(weights, dtype=float).clip(min=0.0)
    if w.sum() <= 0:
        # Uniform fallback
        return int(rng.integers(0, len(choices)))

    levy = levy_multiplier(alpha=alpha, n=len(choices), rng=rng)
    perturbed = w * levy
    # Normalize
    perturbed = perturbed / perturbed.sum()

    return int(rng.choice(len(choices), p=perturbed))
