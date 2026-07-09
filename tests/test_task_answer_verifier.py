"""Unit tests for generation-time task answer verification (SymPy-based)."""

import pytest

from src.agents.task_answer_verifier import verify_task_answer


@pytest.mark.parametrize(
    ("topic", "problem", "answer", "expected"),
    [
        # Derivatives
        (
            "derivatives",
            r"Найдите производную функции $f(x) = x^2 \sin(x)$",
            r"$2x\sin(x) + x^2\cos(x)$",
            True,
        ),
        ("derivatives", r"Найдите производную функции $f(x) = x^3$ в точке $x_0 = 2$", "$12$", True),
        ("derivatives", r"Найдите производную функции $f(x) = x^3$", "$3x$", False),
        (
            "derivatives",
            r"Найдите производную функции $f(x) = \frac{x^2+1}{x}$",
            r"$1 - \frac{1}{x^2}$",
            True,
        ),
        # Limits
        ("limits", r"Вычислите предел $\lim_{x \to 0} \frac{\sin(x)}{x}$", "$1$", True),
        ("limits", r"Вычислите предел $\lim_{x \to 2} \frac{x^2-4}{x-2}$", "$4$", True),
        ("limits", r"Вычислите предел $\lim_{x \to \infty} \frac{2x^2+1}{x^2}$", "$3$", False),
        ("limits", r"Вычислите предел $\lim_{x \to 0} \frac{1 - \cos(x)}{x^2}$", r"$\frac{1}{2}$", True),
        # Ill-posed two-sided limit (±∞) with a finite claimed answer → wrong
        ("limits", r"Найдите предел $\lim_{x \to 0} \frac{1}{x}$", "$0$", False),
        # Integrals
        ("integrals", r"Вычислите интеграл $\int_0^1 x^2 \, dx$", r"$\frac{1}{3}$", True),
        ("integrals", r"Вычислите $\int_{0}^{\pi} \sin(x) \, dx$", "$2$", True),
        ("integrals", r"Найдите интеграл $\int x \cos(x) \, dx$", r"$x\sin(x) + \cos(x) + C$", True),
        ("integrals", r"Найдите интеграл $\int x \cos(x) \, dx$", r"$x\sin(x) - \cos(x) + C$", False),
        # Equations
        ("equations", r"Решите уравнение $x^2 - 5x + 6 = 0$", "$x_1 = 2, x_2 = 3$", True),
        ("equations", r"Решите уравнение $x^2 - 5x + 6 = 0$", "$x = 2$; $x = 3$", True),
        ("equations", r"Решите уравнение $x^2 - 5x + 6 = 0$", "$x = 2$", False),
        ("equations", r"Решите уравнение $x^2 - 5x + 6 = 0$", "$x_1 = 2, x_2 = 4$", False),
        ("equations", r"Решите уравнение $2x + 3 = 7$", "$x = 2$", True),
    ],
)
def test_verdicts(topic: str, problem: str, answer: str, expected: bool) -> None:
    assert verify_task_answer(topic, problem, answer) is expected


def test_unverifiable_topic_returns_none() -> None:
    assert verify_task_answer("geometry", "Найдите площадь треугольника", "$6$") is None


def test_unparseable_problem_returns_none() -> None:
    assert verify_task_answer("derivatives", "Задача без формул", "$3x^2$") is None


def test_verifier_never_raises_on_garbage() -> None:
    assert verify_task_answer("limits", "$\\lim_{x \\to$ broken", "мусор }{") is None
