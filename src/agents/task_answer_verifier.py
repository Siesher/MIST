"""Generation-time answer verification for TaskGenerator.

Independently re-derives the reference answer of a generated task with SymPy
(derivative / integral / limit / equation topics) and compares it against the
LLM-provided ``answer`` via the existing MultiStepVerifier (SymPy symbolic
equivalence + numeric fallback).

Verdicts:
    True   — answer verified correct
    False  — answer provably wrong (ground truth differs)
    None   — task is not machine-checkable (parse failure / unsupported topic);
             callers must treat this as "accept" (no regeneration loop on it).

Design notes (WHY):
    * The problem statement is Russian NL + LaTeX. We only trust a verdict when
      BOTH the problem expression and the answer parse cleanly — otherwise we
      return None instead of guessing (false regenerations are worse than
      letting an unverifiable task through).
    * Comparison is routed through ``MultiStepVerifier.verify`` so the check
      trace is uniform with the rest of the system.
    * Indefinite integrals are compared modulo the integration constant by
      differentiating the candidate answer back to the integrand.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional

import sympy as sp

from src.agents.multistep_verifier import get_verifier_tracer

logger = logging.getLogger(__name__)

_X = sp.Symbol("x")

# Topics we know how to re-derive. Everything else → None (unverifiable).
_DERIVATIVE_TOPICS = {"derivatives", "chain_rule", "product_rule", "quotient_rule"}
_INTEGRAL_TOPICS = {"integrals"}
_LIMIT_TOPICS = {"limits"}
_EQUATION_TOPICS = {"equations", "linear_equations", "quadratic_equations", "algebra"}


# ─────────────────────────────────────────────────────────────────────
# LaTeX → SymPy
# ─────────────────────────────────────────────────────────────────────


def _latex_to_sympy(latex: str) -> Optional[sp.Expr]:
    """Parse a LaTeX fragment to a SymPy expression; None on failure."""
    cleaned = latex.strip()
    # Strip surrounding $...$ / $$...$$ and \( \)
    cleaned = re.sub(r"^\${1,2}|\${1,2}$", "", cleaned).strip()
    cleaned = cleaned.replace(r"\left", "").replace(r"\right", "")
    # Bracket groups → parens, but keep root indices \sqrt[3]{...} intact.
    cleaned = re.sub(r"\\sqrt\[(\d+)\]", r"\\sqrt\0\1\0", cleaned)
    cleaned = cleaned.replace("[", "(").replace("]", ")")
    cleaned = re.sub("\0(\\d+)\0", r"[\1]", cleaned)
    cleaned = cleaned.replace(r"\dfrac", r"\frac").replace(r"\tfrac", r"\frac")
    cleaned = cleaned.replace(r"\,", " ").replace(r"\;", " ").replace(r"\!", "")
    cleaned = cleaned.replace(r"\operatorname{tg}", r"\tan").replace(r"\tg", r"\tan")
    cleaned = cleaned.replace(r"\operatorname{ctg}", r"\cot").replace(r"\ctg", r"\cot")
    cleaned = cleaned.replace(r"\text{d}", "d").replace(r"\mathrm{d}", "d")
    if not cleaned:
        return None
    try:
        from sympy.parsing.latex import parse_latex

        expr = parse_latex(cleaned)
        # parse_latex leaves unknown commands as Symbols with backslashes → reject
        if expr is None or any("\\" in str(s) for s in expr.free_symbols):
            return None
        # `e` is Euler's number in task LaTeX, not a free variable.
        return expr.subs(sp.Symbol("e"), sp.E)
    except Exception:
        return None


def _extract_math_segments(text: str) -> list[str]:
    """All $...$ / $$...$$ segments, longest first."""
    segs = re.findall(r"\$\$(.+?)\$\$", text, flags=re.S) + re.findall(r"\$(.+?)\$", text, flags=re.S)
    return sorted({s.strip() for s in segs if s.strip()}, key=len, reverse=True)


def _only_x(expr: sp.Expr) -> bool:
    return expr.free_symbols <= {_X}


# ─────────────────────────────────────────────────────────────────────
# Ground-truth derivation per topic
# ─────────────────────────────────────────────────────────────────────


def _find_function_body(problem: str) -> Optional[sp.Expr]:
    """Find `f(x) = <expr>` (or `y = <expr>`) inside problem LaTeX segments."""
    for seg in _extract_math_segments(problem):
        m = re.search(r"(?:f\s*\(\s*x\s*\)|y)\s*=\s*(.+)$", seg, flags=re.S)
        if not m:
            continue
        expr = _latex_to_sympy(m.group(1))
        if expr is not None and _only_x(expr) and expr.free_symbols:
            return expr
    return None


def _find_point(problem: str) -> Optional[sp.Expr]:
    """Find evaluation point: `x_0 = a` or `в точке x = a`."""
    m = re.search(r"x\s*_?\{?0\}?\s*=\s*([^$,;]+)", problem)
    if m:
        return _latex_to_sympy(m.group(1))
    m = re.search(r"точке\s*\$?\s*x\s*=\s*([^$,;]+?)\s*\$", problem)
    if m:
        return _latex_to_sympy(m.group(1))
    return None


def _gt_derivative(problem: str) -> Optional[sp.Expr]:
    body = _find_function_body(problem)
    if body is None:
        return None
    order = 2 if re.search(r"втор\w+\s+производн|f''", problem) else 1
    gt = sp.diff(body, _X, order)
    point = _find_point(problem)
    if point is not None and not point.free_symbols:
        gt = gt.subs(_X, point)
    return sp.simplify(gt)


def _gt_limit(problem: str) -> Optional[sp.Expr]:
    for seg in _extract_math_segments(problem):
        m = re.search(r"\\lim\s*_\{?\s*x\s*\\to\s*([^}]+)\}?\s*(.+)$", seg, flags=re.S)
        if not m:
            continue
        target_raw, body_raw = m.group(1).strip(), m.group(2).strip()
        direction = "+-"
        if target_raw.endswith("^+") or target_raw.endswith("^{+}"):
            direction, target_raw = "+", target_raw.rstrip("^{+}").rstrip("^+")
        elif target_raw.endswith("^-") or target_raw.endswith("^{-}"):
            direction, target_raw = "-", target_raw.rstrip("^{-}").rstrip("^-")
        target = _latex_to_sympy(target_raw)
        body = _latex_to_sympy(body_raw)
        if target is None or body is None or not _only_x(body):
            continue
        try:
            if direction == "+-":
                lp = sp.limit(body, _X, target, dir="+")
                lm = sp.limit(body, _X, target, dir="-")
                if lp != lm:
                    # Two-sided limit does not exist → any finite claimed answer is wrong.
                    return sp.nan
                return lp
            return sp.limit(body, _X, target, dir=direction)
        except Exception:
            return None
    return None


def _gt_integral(problem: str) -> Optional[tuple[str, Any]]:
    r"""Return ("definite", value) or ("indefinite", integrand)."""
    for seg in _extract_math_segments(problem):
        m = re.search(
            r"\\int\s*(?:_(\{[^}]+\}|[^\s{^])\s*\^(\{[^}]+\}|[^\s{]))?\s*(.+?)\s*(?:\\[,;])?\s*d\s*x",
            seg,
            flags=re.S,
        )
        if not m:
            continue
        lo_raw, hi_raw, body_raw = m.group(1), m.group(2), m.group(3)
        body = _latex_to_sympy(body_raw)
        if body is None or not _only_x(body):
            continue
        if lo_raw and hi_raw:
            lo, hi = _latex_to_sympy(lo_raw.strip("{}")), _latex_to_sympy(hi_raw.strip("{}"))
            if lo is None or hi is None:
                continue
            try:
                val = sp.integrate(body, (_X, lo, hi))
                if val.has(sp.Integral):
                    return None
                return ("definite", sp.simplify(val))
            except Exception:
                return None
        return ("indefinite", body)
    return None


def _gt_equation_roots(problem: str) -> Optional[list[sp.Expr]]:
    for seg in _extract_math_segments(problem):
        if "=" not in seg or r"\lim" in seg or r"\int" in seg:
            continue
        lhs_raw, _, rhs_raw = seg.partition("=")
        lhs, rhs = _latex_to_sympy(lhs_raw), _latex_to_sympy(rhs_raw)
        if lhs is None or rhs is None:
            continue
        if not (_only_x(lhs) and _only_x(rhs)) or _X not in (lhs.free_symbols | rhs.free_symbols):
            continue
        try:
            roots = sp.solve(sp.Eq(lhs, rhs), _X)
        except Exception:
            return None
        if not isinstance(roots, list) or not roots:
            return None
        real = [r for r in roots if r.is_real is not False]
        return real or None
    return None


# ─────────────────────────────────────────────────────────────────────
# Answer parsing
# ─────────────────────────────────────────────────────────────────────

_ANSWER_JUNK = re.compile(r"(ответ|answer|или|and|переменн\w+|где|при)\s*[:：]?", flags=re.I)


def _parse_answer_exprs(answer: str) -> list[sp.Expr]:
    """Extract SymPy expressions from an answer string (LaTeX and/or plain)."""
    text = _ANSWER_JUNK.sub(" ", answer or "").strip()
    exprs: list[sp.Expr] = []

    segments = _extract_math_segments(text)
    if not segments:
        segments = [text]
    # Split multi-part answers ("x_1 = 2, x_2 = 3") into individual candidates.
    candidates: list[str] = []
    for seg in segments:
        candidates.extend(c for c in re.split(r"[,;]|\\quad|\\qquad", seg) if c.strip())

    for cand in candidates:
        # Drop leading assignments like "x =", "x_1 =", "f'(x) =", "y' ="
        cand = re.sub(r"^[^=]{0,20}=", "", cand.strip()).strip() if "=" in cand else cand.strip()
        expr = _latex_to_sympy(cand)
        if expr is None:
            try:
                expr = sp.sympify(cand.replace("^", "**"), rational=True)
            except Exception:
                expr = None
        # Allow the integration constant C/c alongside x (indefinite integrals).
        if expr is not None and expr.free_symbols <= {_X, sp.Symbol("C"), sp.Symbol("c")}:
            exprs.append(expr.subs({sp.Symbol("C"): 0, sp.Symbol("c"): 0}))
    return exprs


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────


def _equiv(expected: sp.Expr, actual: sp.Expr) -> bool:
    """Compare via MultiStepVerifier (symbolic + numeric fallback)."""
    try:
        result = get_verifier_tracer().verify(
            session_id=f"taskgen-verify-{uuid.uuid4().hex[:8]}",
            expected_answer=str(expected),
            student_response=str(actual),
            domain="math",
        )
        if result.overall_correct is not None:
            return bool(result.overall_correct)
    except Exception:  # pragma: no cover - defensive
        pass
    try:
        return sp.simplify(expected - actual) == 0
    except Exception:
        return False


def verify_task_answer(topic: str, problem: str, answer: str) -> Optional[bool]:
    """Verify a generated task's reference answer against SymPy ground truth.

    Args:
        topic: Task topic (e.g. "derivatives").
        problem: Problem statement (Russian NL with $LaTeX$ math).
        answer: LLM-provided reference answer.

    Returns:
        True / False when a verdict is possible, None when unverifiable.
    """
    try:
        return _verify(topic, problem, answer)
    except Exception as e:  # noqa: BLE001 - verifier must never crash generation
        logger.debug("task answer verification errored: %s", e)
        return None


def _verify(topic: str, problem: str, answer: str) -> Optional[bool]:
    topic = (topic or "").lower()
    answer_exprs = _parse_answer_exprs(answer)

    if topic in _DERIVATIVE_TOPICS or topic == "calculus":
        gt = _gt_derivative(problem)
        if gt is None or not answer_exprs:
            return None
        return any(_equiv(gt, a) for a in answer_exprs)

    if topic in _LIMIT_TOPICS:
        gt = _gt_limit(problem)
        if gt is None or not answer_exprs:
            return None
        if gt is sp.nan:
            # Limit does not exist; a parsed (finite/infinite) answer claim is wrong.
            return False
        if gt.is_infinite:
            return any(a == gt for a in answer_exprs)
        return any(_equiv(gt, a) for a in answer_exprs)

    if topic in _INTEGRAL_TOPICS:
        res = _gt_integral(problem)
        if res is None or not answer_exprs:
            return None
        kind, payload = res
        if kind == "definite":
            return any(_equiv(payload, a) for a in answer_exprs)
        # Indefinite: candidate F(x) is correct iff F'(x) == integrand (mod +C,
        # already stripped in _parse_answer_exprs).
        return any(_equiv(payload, sp.diff(a, _X)) for a in answer_exprs)

    if topic in _EQUATION_TOPICS:
        roots = _gt_equation_roots(problem)
        if roots is None:
            return None
        nums = [a for a in answer_exprs if not a.free_symbols]
        if not nums:
            return None
        if len(nums) != len(set(map(str, roots))) and len(set(map(str, nums))) != len(set(map(str, roots))):
            # Root count mismatch → wrong (missing/extra roots)
            return False
        unmatched = list(roots)
        for n in nums:
            hit = next((r for r in unmatched if _equiv(r, n)), None)
            if hit is None:
                return False
            unmatched.remove(hit)
        return not unmatched

    return None
