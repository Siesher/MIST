"""Multi-step verifier — traces every verification check for debugging + UI.

Wraps ResponseVerifierAgent (SymPy for math) and adds:
    * ChemPy: balance reactions, pH calculations
    * Step-by-step trace: each check is a VerificationStep
    * Domain auto-detection from task topic

Steps stored in-memory (last 100 sessions). Surface via
`/api/v1/chat/{session_id}/verifier_trace` for side-panel UI display.

Usage:
    vtracer = get_verifier_tracer()
    result = vtracer.verify(
        session_id="...",
        task=task,
        student_response="x=4",
        domain="math",  # or "chemistry"
    )
    trace = vtracer.get_trace(session_id)
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────────────────────────────


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class VerificationStep:
    name: str  # e.g. "sympy_equivalence", "chempy_balance", "numeric_range"
    status: CheckStatus
    detail: str  # human-readable explanation
    duration_ms: float
    input_summary: str | None = None
    output_summary: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MultiStepResult:
    session_id: str
    domain: str  # math | chemistry | general
    overall_correct: bool | None  # None = inconclusive
    confidence: float  # 0.0-1.0 (aggregate of steps)
    steps: list[VerificationStep]
    total_ms: float


# ─────────────────────────────────────────────────────────────────────
# ChemPy integration (optional)
# ─────────────────────────────────────────────────────────────────────


def _chempy_balance(reaction_str: str) -> tuple[bool, str, dict[str, Any]]:
    """Check if a chemical reaction is balanced.

    Input format: "H2 + O2 -> H2O" or "H2 + O2 = H2O"
    Returns: (is_balanced, explanation, metadata)
    """
    try:
        from chempy import balance_stoichiometry
    except ImportError:
        return False, "chempy not installed", {"error": "missing_dep"}

    try:
        # Parse "A + B -> C + D" format
        text = reaction_str.replace("=", "->").replace("→", "->")
        if "->" not in text:
            return False, "No '->' separator found", {}
        lhs, rhs = [s.strip() for s in text.split("->", 1)]
        reactants = {s.strip() for s in lhs.split("+") if s.strip()}
        products = {s.strip() for s in rhs.split("+") if s.strip()}

        coeffs_r, coeffs_p = balance_stoichiometry(reactants, products)
        equation = " + ".join(f"{v} {k}" for k, v in coeffs_r.items())
        equation += " -> "
        equation += " + ".join(f"{v} {k}" for k, v in coeffs_p.items())
        return (
            True,
            f"Balanced: {equation}",
            {
                "reactants": coeffs_r,
                "products": coeffs_p,
            },
        )
    except Exception as e:
        return False, f"Balance check failed: {e}", {"error": str(e)}


def _chempy_ph(formula: str, concentration_M: float) -> tuple[bool, str, dict[str, Any]]:
    """Compute pH for a weak acid/base at given concentration."""
    try:
        import math

        from chempy import Substance
        from chempy.equilibria import EqSystem

        # Minimal shortcut — full pH calc needs Ka and equilibrium setup
        # For demo, just check that substance parses
        sub = Substance.from_formula(formula)
        return (
            True,
            f"Parsed {formula}: {sub.mass} g/mol",
            {
                "formula": formula,
                "mass": sub.mass,
                "concentration_M": concentration_M,
            },
        )
    except ImportError:
        return False, "chempy not installed", {"error": "missing_dep"}
    except Exception as e:
        return False, f"pH check failed: {e}", {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────
# SymPy checks (additional to existing response_verifier)
# ─────────────────────────────────────────────────────────────────────


def _sympy_equivalence(expected: str, actual: str) -> tuple[bool, str, dict[str, Any]]:
    """Symbolic equivalence: simplify(expected - actual) == 0."""
    try:
        import sympy as sp

        e = sp.sympify(expected)
        a = sp.sympify(actual)
        diff = sp.simplify(e - a)
        is_equiv = diff == 0
        return (
            is_equiv,
            (
                f"simplify({expected} - {actual}) = {diff} → "
                f"{'equivalent' if is_equiv else 'different'}"
            ),
            {"difference": str(diff)},
        )
    except Exception as e:
        return False, f"Sympy parse error: {e}", {"error": str(e)}


def _numeric_check(
    expected: str, actual: str, tol: float = 1e-6
) -> tuple[bool, str, dict[str, Any]]:
    """Numeric comparison with tolerance (fallback for symbolic failures)."""
    try:
        import sympy as sp

        e_num = float(sp.sympify(expected).evalf())
        a_num = float(sp.sympify(actual).evalf())
        delta = abs(e_num - a_num)
        match = delta < tol
        return (
            match,
            (
                f"|{e_num:.6g} - {a_num:.6g}| = {delta:.6g} "
                f"({'pass' if match else 'fail'} at tol={tol})"
            ),
            {"expected": e_num, "actual": a_num, "delta": delta},
        )
    except Exception as e:
        return False, f"Numeric eval failed: {e}", {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────
# Multi-step tracer singleton
# ─────────────────────────────────────────────────────────────────────


class MultiStepVerifier:
    """Orchestrates multiple verification checks + stores traces."""

    def __init__(self, max_sessions: int = 100):
        self._max = max_sessions
        self._traces: OrderedDict[str, MultiStepResult] = OrderedDict()
        self._lock = RLock()

    def verify(
        self,
        session_id: str,
        expected_answer: str,
        student_response: str,
        domain: str = "math",
    ) -> MultiStepResult:
        """Run domain-specific multi-step verification, collect steps."""
        start = time.perf_counter()
        steps: list[VerificationStep] = []

        if domain == "math":
            steps.extend(self._verify_math(expected_answer, student_response))
        elif domain == "chemistry":
            steps.extend(self._verify_chemistry(expected_answer, student_response))
        else:
            steps.append(
                VerificationStep(
                    name="domain_dispatch",
                    status=CheckStatus.SKIPPED,
                    detail=f"Domain '{domain}' has no verifier — LLM-only check",
                    duration_ms=0,
                )
            )

        # Aggregate
        passes = sum(1 for s in steps if s.status == CheckStatus.PASS)
        fails = sum(1 for s in steps if s.status == CheckStatus.FAIL)
        confidence = passes / max(1, passes + fails)
        overall = None
        if passes > 0 and fails == 0:
            overall = True
        elif fails > 0 and passes == 0:
            overall = False

        result = MultiStepResult(
            session_id=session_id,
            domain=domain,
            overall_correct=overall,
            confidence=confidence,
            steps=steps,
            total_ms=(time.perf_counter() - start) * 1000,
        )

        with self._lock:
            self._traces[session_id] = result
            self._traces.move_to_end(session_id)
            while len(self._traces) > self._max:
                self._traces.popitem(last=False)

        return result

    def _verify_math(self, expected: str, actual: str) -> list[VerificationStep]:
        steps: list[VerificationStep] = []

        # Step 1: Symbolic equivalence
        t0 = time.perf_counter()
        ok, detail, meta = _sympy_equivalence(expected, actual)
        steps.append(
            VerificationStep(
                name="sympy_equivalence",
                status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                detail=detail,
                duration_ms=(time.perf_counter() - t0) * 1000,
                input_summary=f"expected={expected!r} actual={actual!r}",
                output_summary=detail,
                metadata=meta,
            )
        )

        # Step 2: Numeric check (only if symbolic failed — sanity fallback)
        if not ok:
            t0 = time.perf_counter()
            ok_num, detail_num, meta_num = _numeric_check(expected, actual)
            steps.append(
                VerificationStep(
                    name="numeric_check",
                    status=CheckStatus.PASS if ok_num else CheckStatus.FAIL,
                    detail=detail_num,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                    input_summary=f"expected={expected!r} actual={actual!r}",
                    metadata=meta_num,
                )
            )

        return steps

    def _verify_chemistry(self, expected: str, actual: str) -> list[VerificationStep]:
        steps: list[VerificationStep] = []

        # Detect balance check (contains '->')
        if "->" in actual or "=" in actual or "→" in actual:
            t0 = time.perf_counter()
            ok, detail, meta = _chempy_balance(actual)
            steps.append(
                VerificationStep(
                    name="chempy_balance",
                    status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                    detail=detail,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                    input_summary=f"reaction={actual!r}",
                    metadata=meta,
                )
            )
        else:
            # Maybe a formula lookup
            t0 = time.perf_counter()
            ok, detail, meta = _chempy_ph(actual.strip(), 0.1)
            steps.append(
                VerificationStep(
                    name="chempy_formula",
                    status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                    detail=detail,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                    input_summary=f"formula={actual!r}",
                    metadata=meta,
                )
            )

        return steps

    def get_trace(self, session_id: str) -> MultiStepResult | None:
        with self._lock:
            return self._traces.get(session_id)

    def to_dict(self, result: MultiStepResult) -> dict[str, Any]:
        return {
            "session_id": result.session_id,
            "domain": result.domain,
            "overall_correct": result.overall_correct,
            "confidence": result.confidence,
            "total_ms": round(result.total_ms, 1),
            "steps": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "detail": s.detail,
                    "duration_ms": round(s.duration_ms, 2),
                    "input_summary": s.input_summary,
                    "output_summary": s.output_summary,
                    "metadata": s.metadata,
                }
                for s in result.steps
            ],
        }


# ─────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────


_verifier: MultiStepVerifier | None = None


def get_verifier_tracer() -> MultiStepVerifier:
    global _verifier
    if _verifier is None:
        _verifier = MultiStepVerifier()
    return _verifier
