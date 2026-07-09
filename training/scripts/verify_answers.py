"""
Hybrid STEM Verification Module

Domain-aware answer verification for training data quality control.
Supports: Math (SymPy), Physics (numeric+units), Chemistry (ChemPy),
CS (code execution), Biology/MC (exact match), Conceptual (RaR rubric judge).

Usage:
    from training.scripts.verify_answers import verify, extract_answer

    result = verify(
        answer="x = 3",
        truth="3",
        domain="math",
        question_type="calc",
    )
    # result.correct == True
"""

import re
import math
import logging
import subprocess
import tempfile
import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class VerificationResult:
    """Result of answer verification."""
    correct: bool
    confidence: float = 1.0  # 0.0-1.0 for rubric-based
    method: str = ""  # sympy, numeric, chempy, code, mc, rubric
    details: str = ""
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Answer extraction
# ---------------------------------------------------------------------------

def _extract_all_boxed(text: str) -> list:
    """Extract all \\boxed{...} contents, handling nested braces."""
    results = []
    search_from = 0
    while True:
        idx = text.find("\\boxed{", search_from)
        if idx == -1:
            break
        start = idx + len("\\boxed{")
        depth = 1
        pos = start
        while pos < len(text) and depth > 0:
            if text[pos] == "{":
                depth += 1
            elif text[pos] == "}":
                depth -= 1
            pos += 1
        if depth == 0:
            results.append(text[start:pos - 1])
        search_from = pos
    return results


def extract_answer(text: str) -> str:
    """Extract final answer from model completion.

    Handles:
    - Text after </think> tag (Qwen3 format)
    - \\boxed{...} LaTeX answers
    - "Ответ: ..." pattern (Russian)
    - "Answer: ..." pattern (English)
    - Last numeric value in text
    """
    # Strip thinking section
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()

    # Try \\boxed{...} with nested brace support
    boxed = _extract_all_boxed(text)
    if boxed:
        return boxed[-1].strip()

    # Try GSM8K "#### answer" format
    gsm8k_match = re.search(r'####\s*(.+?)$', text.strip(), re.MULTILINE)
    if gsm8k_match:
        return gsm8k_match.group(1).strip().replace(",", "")

    # Try "Ответ: ..."
    answer_ru = re.search(r'(?:Ответ|ответ)\s*[:=]\s*(.+?)(?:\.|$)', text)
    if answer_ru:
        return answer_ru.group(1).strip()

    # Try "Answer: ..."
    answer_en = re.search(r'(?:Answer|answer)\s*[:=]\s*(.+?)(?:\.|$)', text)
    if answer_en:
        return answer_en.group(1).strip()

    # Fallback: last line with content
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    if lines:
        return lines[-1]

    return text.strip()


def extract_gsm8k_answer(text: str) -> Optional[str]:
    """Extract numeric answer after #### from GSM8K-format solution text.

    GSM8K format: "... #### 42" or "... ####42"
    Returns answer string with commas removed, or None if not found.
    """
    match = re.search(r'####\s*(.+?)$', text.strip(), re.MULTILINE)
    if match:
        return match.group(1).strip().replace(",", "")
    return None


# ---------------------------------------------------------------------------
# Math verification (SymPy)
# ---------------------------------------------------------------------------

def verify_math(answer: str, truth: str) -> VerificationResult:
    """Verify math answer using SymPy symbolic comparison."""
    try:
        import sympy
        from sympy.parsing.sympy_parser import (
            parse_expr,
            standard_transformations,
            implicit_multiplication_application,
            convert_xor,
        )

        transformations = standard_transformations + (
            implicit_multiplication_application,
            convert_xor,
        )

        def clean_expr(s: str) -> str:
            """Clean expression string for parsing."""
            s = s.strip()
            s = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1)/(\2)', s)
            s = re.sub(r'\\sqrt\{([^}]+)\}', r'sqrt(\1)', s)
            s = s.replace('\\cdot', '*').replace('\\times', '*')
            s = s.replace('^', '**')
            s = re.sub(r'\\left|\\right', '', s)
            s = s.replace('\\pi', 'pi').replace('π', 'pi')
            s = s.replace('\\infty', 'oo').replace('∞', 'oo')
            return s

        answer_clean = clean_expr(answer)
        truth_clean = clean_expr(truth)

        try:
            ans_expr = parse_expr(answer_clean, transformations=transformations)
            truth_expr = parse_expr(truth_clean, transformations=transformations)
        except Exception:
            # Fallback: string comparison
            if answer.strip() == truth.strip():
                return VerificationResult(
                    correct=True, method="string_match",
                    details="Exact string match",
                )
            return VerificationResult(
                correct=False, method="sympy",
                details="Could not parse expressions",
                error="Parse error",
            )

        # Symbolic comparison
        diff = sympy.simplify(ans_expr - truth_expr)
        if diff == 0:
            return VerificationResult(
                correct=True, method="sympy",
                details=f"Symbolic match: {ans_expr} == {truth_expr}",
            )

        # Try numerical evaluation
        try:
            ans_float = float(ans_expr.evalf())
            truth_float = float(truth_expr.evalf())
            if math.isclose(ans_float, truth_float, rel_tol=1e-6):
                return VerificationResult(
                    correct=True, method="sympy_numeric",
                    details=f"Numeric match: {ans_float} ≈ {truth_float}",
                )
        except (TypeError, ValueError):
            pass

        return VerificationResult(
            correct=False, method="sympy",
            details=f"Mismatch: {ans_expr} != {truth_expr} (diff={diff})",
        )

    except ImportError:
        logger.warning("SymPy not installed, falling back to string comparison")
        return _string_compare(answer, truth, "math")
    except Exception as e:
        return VerificationResult(
            correct=False, method="sympy",
            error=str(e),
        )


# ---------------------------------------------------------------------------
# Physics verification (numeric with tolerance + units)
# ---------------------------------------------------------------------------

def verify_physics(
    answer: str, truth: str, tol: float = 0.02
) -> VerificationResult:
    """Verify physics answer: numeric comparison with tolerance.

    Supports unit-aware comparison if Pint is available.
    """
    def extract_numeric(s: str) -> Tuple[Optional[float], str]:
        """Extract numeric value and unit from string."""
        s = s.strip()
        # Replace comma decimal separator
        s = s.replace(',', '.')
        match = re.match(
            r'([+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)\s*(.*)', s
        )
        if match:
            return float(match.group(1)), match.group(2).strip()
        return None, s

    ans_val, ans_unit = extract_numeric(answer)
    truth_val, truth_unit = extract_numeric(truth)

    if ans_val is None:
        return VerificationResult(
            correct=False, method="numeric",
            details=f"Cannot parse numeric value from: {answer}",
        )

    if truth_val is None:
        return VerificationResult(
            correct=False, method="numeric",
            details=f"Cannot parse truth value: {truth}",
        )

    # Try Pint for unit-aware comparison
    if ans_unit and truth_unit:
        try:
            import pint
            ureg = pint.UnitRegistry()
            ans_q = ureg.Quantity(ans_val, ans_unit)
            truth_q = ureg.Quantity(truth_val, truth_unit)
            ans_converted = ans_q.to(truth_q.units).magnitude
            if math.isclose(ans_converted, truth_val, rel_tol=tol):
                return VerificationResult(
                    correct=True, method="pint",
                    details=f"{ans_q} ≈ {truth_q} (tol={tol})",
                )
            return VerificationResult(
                correct=False, method="pint",
                details=f"{ans_q} != {truth_q}",
            )
        except ImportError:
            logger.debug("Pint not available, ignoring units")
        except Exception as e:
            logger.debug(f"Pint comparison failed: {e}")

    # Pure numeric comparison
    if math.isclose(ans_val, truth_val, rel_tol=tol):
        return VerificationResult(
            correct=True, method="numeric",
            details=f"{ans_val} ≈ {truth_val} (tol={tol})",
        )

    return VerificationResult(
        correct=False, method="numeric",
        details=f"{ans_val} != {truth_val} (tol={tol})",
    )


# ---------------------------------------------------------------------------
# Chemistry verification (ChemPy stoichiometry)
# ---------------------------------------------------------------------------

def verify_chemistry(answer: str, truth: str) -> VerificationResult:
    """Verify chemistry answer using ChemPy for equations, numeric for values."""
    # Try numeric first (molarity, mass, etc.)
    try:
        ans_val = float(re.search(r'([+-]?\d+\.?\d*)', answer.replace(',', '.')).group(1))
        truth_val = float(re.search(r'([+-]?\d+\.?\d*)', truth.replace(',', '.')).group(1))
        if math.isclose(ans_val, truth_val, rel_tol=0.02):
            return VerificationResult(
                correct=True, method="numeric",
                details=f"Numeric match: {ans_val} ≈ {truth_val}",
            )
    except (AttributeError, ValueError, TypeError):
        pass

    # Try ChemPy for chemical equation balancing
    try:
        from chempy import balance_stoichiometry

        def parse_equation(eq_str: str) -> Tuple[set, set]:
            """Parse 'A + B -> C + D' into (reactants, products)."""
            sides = re.split(r'\s*[-=→>]+\s*', eq_str)
            if len(sides) != 2:
                raise ValueError(f"Cannot split equation: {eq_str}")
            reactants = {s.strip() for s in sides[0].split('+')}
            products = {s.strip() for s in sides[1].split('+')}
            return reactants, products

        ans_r, ans_p = parse_equation(answer)
        truth_r, truth_p = parse_equation(truth)

        # Check same species
        if ans_r == truth_r and ans_p == truth_p:
            # Both balance to the same thing
            balanced_r, balanced_p = balance_stoichiometry(truth_r, truth_p)
            return VerificationResult(
                correct=True, method="chempy",
                details=f"Equation balanced: {balanced_r} → {balanced_p}",
            )

    except ImportError:
        logger.debug("ChemPy not available")
    except Exception as e:
        logger.debug(f"ChemPy verification failed: {e}")

    # Fallback: normalized string comparison
    return _string_compare(answer, truth, "chemistry")


# ---------------------------------------------------------------------------
# CS verification (code execution)
# ---------------------------------------------------------------------------

def verify_code(
    code: str,
    test_cases: List[Dict[str, Any]],
    timeout: int = 10,
) -> VerificationResult:
    """Verify code by running against test cases in a subprocess.

    Args:
        code: Python code to test
        test_cases: List of {"input": ..., "expected_output": ...}
        timeout: Execution timeout in seconds
    """
    if not test_cases:
        return VerificationResult(
            correct=False, method="code",
            details="No test cases provided",
        )

    passed = 0
    total = len(test_cases)
    failures: List[str] = []

    for i, tc in enumerate(test_cases):
        test_input = tc.get("input", "")
        expected = str(tc.get("expected_output", "")).strip()

        # Create test script
        test_script = f"""{code}

# Test case {i}
import sys
sys.stdin = __import__('io').StringIO({repr(test_input)})
"""
        # If there's a function to call
        if "function" in tc:
            fn_name = tc["function"]
            fn_args = tc.get("args", [])
            args_str = ", ".join(repr(a) for a in fn_args)
            test_script += f"\nresult = {fn_name}({args_str})\nprint(result)"

        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.py', delete=False, encoding='utf-8'
            ) as f:
                f.write(test_script)
                tmp_path = f.name

            result = subprocess.run(
                ["python", tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )

            actual = result.stdout.strip()
            if actual == expected:
                passed += 1
            else:
                failures.append(
                    f"TC{i}: expected={expected!r}, got={actual!r}"
                    + (f" stderr={result.stderr[:100]}" if result.stderr else "")
                )

        except subprocess.TimeoutExpired:
            failures.append(f"TC{i}: timeout ({timeout}s)")
        except Exception as e:
            failures.append(f"TC{i}: error={e}")
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    correct = passed == total
    return VerificationResult(
        correct=correct,
        confidence=passed / total if total > 0 else 0.0,
        method="code",
        details=f"Passed {passed}/{total}" + (
            f" | Failures: {'; '.join(failures[:3])}" if failures else ""
        ),
    )


# ---------------------------------------------------------------------------
# Multiple choice verification
# ---------------------------------------------------------------------------

def verify_mc(answer: str, truth: str) -> VerificationResult:
    """Verify multiple choice answer via exact match."""
    def normalize_mc(s: str) -> str:
        s = s.strip().upper()
        # Extract just the letter if surrounded by text
        match = re.search(r'\b([A-GА-Г])\b', s)
        if match:
            return match.group(1)
        return s

    ans_norm = normalize_mc(answer)
    truth_norm = normalize_mc(truth)

    correct = ans_norm == truth_norm
    return VerificationResult(
        correct=correct,
        method="mc",
        details=f"Answer={ans_norm}, Truth={truth_norm}",
    )


# ---------------------------------------------------------------------------
# Rubric-based judge (RaR: Rubrics as Rewards)
# ---------------------------------------------------------------------------

@dataclass
class RubricCriterion:
    """Single rubric criterion for RaR evaluation."""
    name: str
    description: str
    weight: float = 1.0  # Essential=3, Important=2, Optional=1
    category: str = "important"  # essential, important, optional, pitfall


def rubric_judge(
    completion: str,
    reference: str,
    rubric: Optional[List[Dict[str, Any]]] = None,
    judge_model: Optional[str] = None,
) -> VerificationResult:
    """Evaluate response against structured rubric using LLM-as-judge.

    This is the RaR (Rubrics as Rewards) approach.
    For training data filtering and GRPO conceptual rewards.

    Args:
        completion: Model's response to evaluate
        reference: Reference answer or key concepts
        rubric: List of criterion dicts with name, description, weight
        judge_model: Ollama model name for judging (default: use configured)
    """
    if rubric is None:
        rubric = _default_rubric()

    # Build rubric prompt
    criteria_text = "\n".join(
        f"- [{c.get('category', 'important').upper()}] {c['name']}: {c['description']} "
        f"(weight: {c.get('weight', 1.0)})"
        for c in rubric
    )

    judge_prompt = f"""Evaluate the following response against the rubric criteria.
For each criterion, answer YES or NO.

## Reference answer (key concepts):
{reference}

## Response to evaluate:
{completion}

## Rubric criteria:
{criteria_text}

## Evaluation:
For each criterion, provide:
CRITERION_NAME: YES/NO

Then provide:
TOTAL_SCORE: <number 0.0-1.0>
"""

    # Try to use Ollama for judging
    try:
        import requests
        model = judge_model or "qwen3:8b"
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

        resp = requests.post(
            f"{host}/api/generate",
            json={
                "model": model,
                "prompt": judge_prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 512},
            },
            timeout=60,
        )

        if resp.status_code == 200:
            judge_output = resp.json().get("response", "")
            score = _parse_rubric_score(judge_output, rubric)
            return VerificationResult(
                correct=score >= 0.6,
                confidence=score,
                method="rubric",
                details=f"RaR score={score:.2f}, threshold=0.6",
            )

    except Exception as e:
        logger.warning(f"Rubric judge failed: {e}")

    # Fallback: keyword overlap scoring
    score = _keyword_overlap_score(completion, reference)
    return VerificationResult(
        correct=score >= 0.5,
        confidence=score,
        method="rubric_fallback",
        details=f"Keyword overlap score={score:.2f} (judge unavailable)",
    )


def _default_rubric() -> List[Dict[str, Any]]:
    """Default rubric for conceptual STEM questions."""
    return [
        {"name": "factual_accuracy", "description": "Response contains factually correct information", "weight": 3.0, "category": "essential"},
        {"name": "key_concepts", "description": "Covers the main concepts from the reference", "weight": 2.0, "category": "important"},
        {"name": "no_hallucination", "description": "Does not contain invented terms or incorrect facts", "weight": 3.0, "category": "essential"},
        {"name": "clear_explanation", "description": "Explanation is logical and easy to follow", "weight": 1.0, "category": "optional"},
        {"name": "appropriate_depth", "description": "Level of detail matches the question difficulty", "weight": 1.0, "category": "optional"},
    ]


def _parse_rubric_score(judge_output: str, rubric: List[Dict]) -> float:
    """Parse rubric score from judge LLM output."""
    # Try to find explicit TOTAL_SCORE
    score_match = re.search(r'TOTAL_SCORE\s*[:=]\s*([\d.]+)', judge_output)
    if score_match:
        return min(1.0, max(0.0, float(score_match.group(1))))

    # Count YES/NO per criterion
    total_weight = sum(c.get("weight", 1.0) for c in rubric)
    earned_weight = 0.0

    for c in rubric:
        name = c["name"]
        pattern = rf'{name}\s*[:=]\s*(YES|NO)'
        match = re.search(pattern, judge_output, re.IGNORECASE)
        if match and match.group(1).upper() == "YES":
            earned_weight += c.get("weight", 1.0)

    return earned_weight / total_weight if total_weight > 0 else 0.0


def _keyword_overlap_score(completion: str, reference: str) -> float:
    """Simple keyword overlap scoring as fallback."""
    def tokenize(text: str) -> set:
        words = re.findall(r'\w{3,}', text.lower())
        return set(words)

    comp_tokens = tokenize(completion)
    ref_tokens = tokenize(reference)

    if not ref_tokens:
        return 0.5

    overlap = len(comp_tokens & ref_tokens)
    return min(1.0, overlap / len(ref_tokens))


# ---------------------------------------------------------------------------
# String comparison fallback
# ---------------------------------------------------------------------------

def _string_compare(answer: str, truth: str, domain: str) -> VerificationResult:
    """Normalized string comparison as fallback."""
    def normalize(s: str) -> str:
        s = s.strip().lower()
        s = re.sub(r'\s+', ' ', s)
        s = s.replace(',', '.')
        return s

    if normalize(answer) == normalize(truth):
        return VerificationResult(
            correct=True, method="string_match",
            details=f"Normalized string match ({domain})",
        )

    return VerificationResult(
        correct=False, method="string_match",
        details=f"String mismatch: {answer!r} != {truth!r}",
    )


# ---------------------------------------------------------------------------
# Domain router
# ---------------------------------------------------------------------------

def verify(
    answer: str,
    truth: str,
    domain: str,
    question_type: str = "calc",
    test_cases: Optional[List[Dict]] = None,
    rubric: Optional[List[Dict]] = None,
    reference: Optional[str] = None,
    tolerance: float = 0.02,
) -> VerificationResult:
    """Main verification router. Dispatches to domain-specific verifier.

    Args:
        answer: Student/model answer to verify
        truth: Ground truth answer
        domain: One of 'math', 'physics', 'chemistry', 'cs', 'biology'
        question_type: One of 'calc', 'code', 'mc', 'conceptual'
        test_cases: For CS code verification
        rubric: For conceptual question rubric judge
        reference: Reference text for rubric judge
        tolerance: Numeric tolerance for physics/chemistry
    """
    answer = answer.strip()
    truth = truth.strip()

    # Multiple choice — any domain
    if question_type == "mc":
        return verify_mc(answer, truth)

    # Conceptual — any domain, use rubric judge
    if question_type == "conceptual":
        return rubric_judge(
            completion=answer,
            reference=reference or truth,
            rubric=rubric,
        )

    # Domain-specific verification
    if domain == "math":
        return verify_math(answer, truth)

    elif domain == "physics":
        return verify_physics(answer, truth, tol=tolerance)

    elif domain == "chemistry":
        return verify_chemistry(answer, truth)

    elif domain == "cs":
        if question_type == "code" and test_cases:
            return verify_code(answer, test_cases)
        return verify_math(answer, truth)  # CS calc questions use SymPy

    elif domain == "biology":
        # Biology is mostly MC or conceptual
        return verify_mc(answer, truth)

    else:
        logger.warning(f"Unknown domain: {domain}, using string comparison")
        return _string_compare(answer, truth, domain)


# ---------------------------------------------------------------------------
# Batch verification for dataset filtering
# ---------------------------------------------------------------------------

def verify_dataset(
    data_path: str,
    output_path: Optional[str] = None,
    min_confidence: float = 0.6,
) -> Dict[str, Any]:
    """Verify an entire JSONL dataset. Filter to verified-correct only.

    Args:
        data_path: Path to input JSONL
        output_path: Path to output filtered JSONL (if None, just stats)
        min_confidence: Minimum confidence for rubric-based verification
    """
    import json
    from pathlib import Path

    stats = {
        "total": 0, "verified": 0, "rejected": 0,
        "by_domain": {}, "by_method": {},
    }

    verified_rows = []
    input_path = Path(data_path)

    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            stats["total"] += 1

            domain = row.get("domain", "math")
            q_type = row.get("type", "calc")
            answer = extract_answer(row.get("output", row.get("completion", "")))
            truth = row.get("ground_truth", row.get("answer", ""))

            result = verify(
                answer=answer,
                truth=truth,
                domain=domain,
                question_type=q_type,
                test_cases=row.get("test_cases"),
                rubric=row.get("rubric"),
                reference=row.get("reference"),
            )

            if result.correct and result.confidence >= min_confidence:
                stats["verified"] += 1
                row["verified"] = True
                row["verification_method"] = result.method
                row["verification_confidence"] = result.confidence
                verified_rows.append(row)
            else:
                stats["rejected"] += 1

            # Update per-domain stats
            d_stats = stats["by_domain"].setdefault(domain, {"total": 0, "verified": 0})
            d_stats["total"] += 1
            if result.correct:
                d_stats["verified"] += 1

            # Update per-method stats
            m_stats = stats["by_method"].setdefault(result.method, {"total": 0, "correct": 0})
            m_stats["total"] += 1
            if result.correct:
                m_stats["correct"] += 1

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for row in verified_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    stats["verification_rate"] = (
        stats["verified"] / stats["total"] if stats["total"] > 0 else 0
    )
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="STEM Answer Verification")
    parser.add_argument("--input", required=True, help="Input JSONL dataset")
    parser.add_argument("--output", help="Output filtered JSONL")
    parser.add_argument("--min-confidence", type=float, default=0.6)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    stats = verify_dataset(args.input, args.output, args.min_confidence)
    print(json.dumps(stats, indent=2, ensure_ascii=False))
