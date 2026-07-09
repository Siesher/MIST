"""
SymPy Utilities for MITS

Safe wrappers for SymPy operations used in:
- Task synthesis (verified answers)
- Solution verification
- Multi-modal input validation
"""

import logging
from typing import Any, Optional, Tuple

try:
    from sympy import (
        E,
        Eq,
        Ge,
        Gt,
        I,
        Le,
        Lt,
        Ne,
        Symbol,
        acos,
        asin,
        atan,
        cos,
        cot,
        csc,
        diff,
        exp,
        expand,
        factor,
        integrate,
        latex,
        limit,
        ln,
        log,
        oo,
        pi,
        powsimp,
        radsimp,
        sec,
        simplify,
        sin,
        solve,
        sqrt,
        symbols,
        tan,
        trigsimp,
    )
    from sympy.core.sympify import SympifyError
    from sympy.parsing.sympy_parser import (
        convert_xor,
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False

logger = logging.getLogger(__name__)

# Standard transformations for parsing
PARSE_TRANSFORMATIONS = (
    standard_transformations +
    (implicit_multiplication_application, convert_xor)
) if SYMPY_AVAILABLE else None


# ═══════════════════════════════════════════════════════════════════════════
# SAFE PARSING
# ═══════════════════════════════════════════════════════════════════════════

def safe_parse_expr(
    expr_str: str,
    local_dict: Optional[dict] = None
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Safely parse a string expression to SymPy.

    Args:
        expr_str: Mathematical expression as string
        local_dict: Optional dict of local symbols

    Returns:
        (parsed_expr, error_message) - error_message is None if successful
    """
    if not SYMPY_AVAILABLE:
        return None, "SymPy not installed"

    if not expr_str or not expr_str.strip():
        return None, "Empty expression"

    try:
        # Clean up common notation
        cleaned = expr_str.strip()
        cleaned = cleaned.replace("^", "**")  # Power notation
        cleaned = cleaned.replace("×", "*")   # Multiplication
        cleaned = cleaned.replace("÷", "/")   # Division
        cleaned = cleaned.replace("·", "*")   # Dot multiplication

        # Default local dict with common symbols
        if local_dict is None:
            x, y, z, t, n = symbols('x y z t n')
            local_dict = {
                'x': x, 'y': y, 'z': z, 't': t, 'n': n,
                'pi': pi, 'e': E, 'E': E, 'i': I,
                'sin': sin, 'cos': cos, 'tan': tan,
                'cot': cot, 'sec': sec, 'csc': csc,
                'asin': asin, 'acos': acos, 'atan': atan,
                'exp': exp, 'log': log, 'ln': ln, 'sqrt': sqrt,
            }

        parsed = parse_expr(
            cleaned,
            local_dict=local_dict,
            transformations=PARSE_TRANSFORMATIONS,
            evaluate=True
        )
        return parsed, None

    except SympifyError as e:
        return None, f"Parse error: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════
# SAFE DIFFERENTIATION
# ═══════════════════════════════════════════════════════════════════════════

def safe_diff(
    expr_str: str,
    var: str = "x",
    n: int = 1
) -> Tuple[Optional[str], Optional[str]]:
    """
    Safely compute derivative.

    Args:
        expr_str: Expression to differentiate
        var: Variable to differentiate with respect to
        n: Order of derivative

    Returns:
        (result_str, error_message)
    """
    if not SYMPY_AVAILABLE:
        return None, "SymPy not installed"

    expr, err = safe_parse_expr(expr_str)
    if err:
        return None, err

    try:
        variable = Symbol(var)
        result = diff(expr, variable, n)
        result = simplify(result)
        return str(result), None
    except Exception as e:
        return None, f"Differentiation error: {str(e)}"


def safe_diff_latex(
    expr_str: str,
    var: str = "x",
    n: int = 1
) -> Tuple[Optional[str], Optional[str]]:
    """
    Safely compute derivative and return LaTeX.

    Returns:
        (latex_result, error_message)
    """
    if not SYMPY_AVAILABLE:
        return None, "SymPy not installed"

    expr, err = safe_parse_expr(expr_str)
    if err:
        return None, err

    try:
        variable = Symbol(var)
        result = diff(expr, variable, n)
        result = simplify(result)
        return latex(result), None
    except Exception as e:
        return None, f"Differentiation error: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════
# SAFE INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

def safe_integrate(
    expr_str: str,
    var: str = "x",
    lower: Optional[str] = None,
    upper: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Safely compute integral (definite or indefinite).

    Args:
        expr_str: Expression to integrate
        var: Variable of integration
        lower: Lower limit (for definite integral)
        upper: Upper limit (for definite integral)

    Returns:
        (result_str, error_message)
    """
    if not SYMPY_AVAILABLE:
        return None, "SymPy not installed"

    expr, err = safe_parse_expr(expr_str)
    if err:
        return None, err

    try:
        variable = Symbol(var)

        if lower is not None and upper is not None:
            # Definite integral
            low_val, err = safe_parse_expr(lower)
            if err:
                return None, f"Lower limit error: {err}"
            up_val, err = safe_parse_expr(upper)
            if err:
                return None, f"Upper limit error: {err}"
            result = integrate(expr, (variable, low_val, up_val))
        else:
            # Indefinite integral
            result = integrate(expr, variable)

        result = simplify(result)
        return str(result), None
    except Exception as e:
        return None, f"Integration error: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════
# SAFE LIMIT
# ═══════════════════════════════════════════════════════════════════════════

def safe_limit(
    expr_str: str,
    var: str = "x",
    point: str = "0",
    direction: str = "+-"
) -> Tuple[Optional[str], Optional[str]]:
    """
    Safely compute limit.

    Args:
        expr_str: Expression
        var: Variable
        point: Point to approach (can be "oo" for infinity)
        direction: "+", "-", or "+-" for two-sided

    Returns:
        (result_str, error_message)
    """
    if not SYMPY_AVAILABLE:
        return None, "SymPy not installed"

    expr, err = safe_parse_expr(expr_str)
    if err:
        return None, err

    try:
        variable = Symbol(var)

        # Parse point
        if point in ("oo", "inf", "infinity"):
            pt = oo
        elif point in ("-oo", "-inf", "-infinity"):
            pt = -oo
        else:
            pt, err = safe_parse_expr(point)
            if err:
                return None, f"Point error: {err}"

        result = limit(expr, variable, pt, dir=direction)
        return str(result), None
    except Exception as e:
        return None, f"Limit error: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════
# SAFE SOLVE
# ═══════════════════════════════════════════════════════════════════════════

def safe_solve(
    equation_str: str,
    var: str = "x"
) -> Tuple[Optional[list], Optional[str]]:
    """
    Safely solve an equation.

    Args:
        equation_str: Equation (can be "expr = 0" or just "expr" which is set to 0)
        var: Variable to solve for

    Returns:
        (solutions_list, error_message)
    """
    if not SYMPY_AVAILABLE:
        return None, "SymPy not installed"

    try:
        variable = Symbol(var)

        # Handle "expr = value" format
        if "=" in equation_str:
            parts = equation_str.split("=")
            if len(parts) != 2:
                return None, "Invalid equation format"
            lhs, err = safe_parse_expr(parts[0].strip())
            if err:
                return None, f"LHS error: {err}"
            rhs, err = safe_parse_expr(parts[1].strip())
            if err:
                return None, f"RHS error: {err}"
            expr = lhs - rhs
        else:
            expr, err = safe_parse_expr(equation_str)
            if err:
                return None, err

        solutions = solve(expr, variable)
        return [str(s) for s in solutions], None
    except Exception as e:
        return None, f"Solve error: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════
# VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════

def verify_equality(
    expr1_str: str,
    expr2_str: str,
    simplify_first: bool = True
) -> Tuple[bool, float, Optional[str]]:
    """
    Verify if two expressions are mathematically equivalent.

    Args:
        expr1_str: First expression
        expr2_str: Second expression
        simplify_first: Whether to simplify before comparing

    Returns:
        (are_equal, confidence, error_message)
    """
    if not SYMPY_AVAILABLE:
        return False, 0.0, "SymPy not installed"

    expr1, err1 = safe_parse_expr(expr1_str)
    if err1:
        return False, 0.0, f"Expression 1 error: {err1}"

    expr2, err2 = safe_parse_expr(expr2_str)
    if err2:
        return False, 0.0, f"Expression 2 error: {err2}"

    try:
        if simplify_first:
            expr1 = simplify(expr1)
            expr2 = simplify(expr2)

        # Method 1: Direct equality
        if expr1 == expr2:
            return True, 1.0, None

        # Method 2: Simplify difference
        diff_expr = simplify(expr1 - expr2)
        if diff_expr == 0:
            return True, 1.0, None

        # Method 3: Try trigsimp for trig expressions
        diff_trig = trigsimp(expr1 - expr2)
        if diff_trig == 0:
            return True, 0.95, None

        # Method 4: Expand both and compare
        exp1 = expand(expr1)
        exp2 = expand(expr2)
        if simplify(exp1 - exp2) == 0:
            return True, 0.9, None

        # Not equal
        return False, 0.0, None

    except Exception as e:
        return False, 0.0, f"Comparison error: {str(e)}"


def verify_derivative(
    function_str: str,
    claimed_derivative_str: str,
    var: str = "x"
) -> Tuple[bool, float, Optional[str]]:
    """
    Verify if a claimed derivative is correct.

    Args:
        function_str: Original function
        claimed_derivative_str: Claimed derivative
        var: Variable

    Returns:
        (is_correct, confidence, error_message)
    """
    actual_deriv, err = safe_diff(function_str, var)
    if err:
        return False, 0.0, err

    return verify_equality(actual_deriv, claimed_derivative_str)


def verify_integral(
    function_str: str,
    claimed_integral_str: str,
    var: str = "x"
) -> Tuple[bool, float, Optional[str]]:
    """
    Verify if a claimed integral is correct by differentiating it.

    Note: Ignores the constant of integration.

    Args:
        function_str: Original function (integrand)
        claimed_integral_str: Claimed integral
        var: Variable

    Returns:
        (is_correct, confidence, error_message)
    """
    # Differentiate the claimed integral
    derivative, err = safe_diff(claimed_integral_str, var)
    if err:
        return False, 0.0, err

    # Should equal the original function
    return verify_equality(derivative, function_str)


# ═══════════════════════════════════════════════════════════════════════════
# LATEX CONVERSION
# ═══════════════════════════════════════════════════════════════════════════

def to_latex(expr_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Convert expression string to LaTeX.

    Returns:
        (latex_str, error_message)
    """
    if not SYMPY_AVAILABLE:
        return None, "SymPy not installed"

    expr, err = safe_parse_expr(expr_str)
    if err:
        return None, err

    try:
        return latex(expr), None
    except Exception as e:
        return None, f"LaTeX conversion error: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════
# CHECK AVAILABILITY
# ═══════════════════════════════════════════════════════════════════════════

def is_sympy_available() -> bool:
    """Check if SymPy is available."""
    return SYMPY_AVAILABLE


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test parsing
    expr, err = safe_parse_expr("x^2 + 2*x + 1")
    print(f"Parsed: {expr}, Error: {err}")

    # Test differentiation
    deriv, err = safe_diff("x^2 * sin(x)", "x")
    print(f"Derivative: {deriv}, Error: {err}")

    # Test integration
    integral, err = safe_integrate("x^2", "x")
    print(f"Integral: {integral}, Error: {err}")

    # Test limit
    lim, err = safe_limit("sin(x)/x", "x", "0")
    print(f"Limit: {lim}, Error: {err}")

    # Test solve
    solutions, err = safe_solve("x^2 - 4 = 0", "x")
    print(f"Solutions: {solutions}, Error: {err}")

    # Test verification
    is_eq, conf, err = verify_equality("x^2 + 2*x + 1", "(x+1)^2")
    print(f"Equal: {is_eq}, Confidence: {conf}, Error: {err}")

    # Test derivative verification
    is_correct, conf, err = verify_derivative("x^2", "2*x")
    print(f"Derivative correct: {is_correct}, Confidence: {conf}")
