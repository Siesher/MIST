"""
SymPy Solution Verification Pipeline

Parses LaTeX to SymPy expressions, compares steps against expected answer,
and identifies the first error in a multi-step solution.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import sympy
    from sympy.parsing.latex import parse_latex
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False
    logger.warning("SymPy not available — solution verification disabled")


@dataclass
class StepVerification:
    """Verification result for a single step."""
    step_number: int
    latex: str
    parsed_expr: Optional[str] = None
    is_valid_expr: bool = False
    is_correct_transition: bool = True
    error_description: str = ""


@dataclass
class VerificationResult:
    """Full verification result."""
    steps: List[StepVerification]
    is_correct: bool = True
    first_error_step: Optional[int] = None
    final_matches_expected: Optional[bool] = None
    feedback: str = ""


def parse_latex_safe(latex_str: str) -> Tuple[Optional[Any], str]:
    """Safely parse LaTeX string to SymPy expression."""
    if not SYMPY_AVAILABLE:
        return None, "SymPy не доступен"

    # Clean up LaTeX
    clean = latex_str.strip()
    clean = clean.replace("\\cdot", "*")
    clean = clean.replace("\\times", "*")
    clean = re.sub(r"\\text\{[^}]*\}", "", clean)

    # Russian → English math function normalization
    _russian_to_eng = {
        'tg': 'tan', 'ctg': 'cot', 'arctg': 'atan', 'arcctg': 'acot',
        'sh': 'sinh', 'ch': 'cosh', 'th': 'tanh', 'cth': 'coth',
        'lg': 'log10', 'cosec': 'csc',
    }
    for rus, eng in _russian_to_eng.items():
        clean = re.sub(rf'\\{rus}\b', f'\\{eng}', clean)
        clean = re.sub(rf'(?<!\\)\b{rus}\b', eng, clean)

    # Handle equation format: lhs = rhs
    if "=" in clean:
        parts = clean.split("=", 1)
        clean = parts[-1].strip()  # Take RHS

    try:
        expr = parse_latex(clean)
        return expr, ""
    except Exception as e:
        # Fallback: try sympy.sympify
        try:
            expr = sympy.sympify(clean)
            return expr, ""
        except Exception:
            return None, f"Не удалось разобрать: {str(e)[:80]}"


def check_step_transition(prev_expr: Any, curr_expr: Any) -> Tuple[bool, str]:
    """Check if transition from previous to current expression is valid."""
    if not SYMPY_AVAILABLE or prev_expr is None or curr_expr is None:
        return True, ""

    try:
        diff = sympy.simplify(prev_expr - curr_expr)
        if diff == 0:
            return True, ""

        # Check if it's an algebraic simplification
        expanded_prev = sympy.expand(prev_expr)
        expanded_curr = sympy.expand(curr_expr)
        if sympy.simplify(expanded_prev - expanded_curr) == 0:
            return True, ""

        return False, "Выражение не эквивалентно предыдущему шагу"

    except Exception:
        # Can't verify — assume correct
        return True, ""


def verify_solution(
    steps_latex: List[str],
    expected_answer: Optional[str] = None,
) -> VerificationResult:
    """
    Verify a multi-step solution.

    Args:
        steps_latex: List of LaTeX strings, one per step
        expected_answer: Optional expected final answer in LaTeX

    Returns:
        VerificationResult with per-step and overall verification
    """
    verified_steps = []
    prev_expr = None
    first_error = None

    for i, latex in enumerate(steps_latex):
        step_num = i + 1
        expr, parse_error = parse_latex_safe(latex)

        step = StepVerification(
            step_number=step_num,
            latex=latex,
            parsed_expr=str(expr) if expr else None,
            is_valid_expr=expr is not None,
        )

        if parse_error:
            step.error_description = parse_error

        # Check transition from previous step
        if expr is not None and prev_expr is not None:
            is_valid, error = check_step_transition(prev_expr, expr)
            step.is_correct_transition = is_valid
            if not is_valid and first_error is None:
                first_error = step_num
                step.error_description = error

        if expr is not None:
            prev_expr = expr

        verified_steps.append(step)

    # Check final answer
    final_matches = None
    if expected_answer and prev_expr is not None:
        expected_expr, _ = parse_latex_safe(expected_answer)
        if expected_expr is not None:
            try:
                diff = sympy.simplify(prev_expr - expected_expr)
                final_matches = (diff == 0)
                if not final_matches and first_error is None:
                    first_error = len(steps_latex)
                    if verified_steps:
                        verified_steps[-1].error_description = "Финальный ответ не совпадает с ожидаемым"
                        verified_steps[-1].is_correct_transition = False
            except Exception:
                pass

    is_correct = first_error is None and (final_matches is None or final_matches)

    # Build feedback
    feedback_parts = []
    if is_correct:
        feedback_parts.append("Решение верное!")
    elif first_error:
        err_step = verified_steps[first_error - 1] if first_error <= len(verified_steps) else None
        feedback_parts.append(f"Ошибка в шаге {first_error}.")
        if err_step and err_step.error_description:
            feedback_parts.append(err_step.error_description)
    elif final_matches is False:
        feedback_parts.append("Финальный ответ не совпадает с ожидаемым.")

    return VerificationResult(
        steps=verified_steps,
        is_correct=is_correct,
        first_error_step=first_error,
        final_matches_expected=final_matches,
        feedback=" ".join(feedback_parts),
    )
