"""
MITS Math Utilities

Helper functions for mathematical operations using SymPy.
"""

import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr, 
    standard_transformations, 
    implicit_multiplication
)
from typing import Optional, Tuple
import re


TRANSFORMATIONS = standard_transformations + (implicit_multiplication,)


def clean_expression(expr: str) -> str:
    """Clean mathematical expression for parsing."""
    expr = expr.strip()
    
    replacements = [
        ('^', '**'),
        ('×', '*'),
        ('÷', '/'),
        ('·', '*'),
        ('−', '-'),
        ('√', 'sqrt'),
    ]
    
    for old, new in replacements:
        expr = expr.replace(old, new)
    
    # 2x -> 2*x
    expr = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr)
    # 2(x) -> 2*(x)
    expr = re.sub(r'(\d)\(', r'\1*(', expr)
    
    return expr


def parse_math(expr: str) -> Optional[sp.Expr]:
    """Parse string to SymPy expression."""
    try:
        cleaned = clean_expression(expr)
        return parse_expr(cleaned, transformations=TRANSFORMATIONS)
    except Exception:
        return None


def simplify_expression(expr: str) -> str:
    """Simplify mathematical expression."""
    parsed = parse_math(expr)
    if parsed:
        return str(sp.simplify(parsed))
    return expr


def compute_derivative(expr: str, var: str = 'x') -> Optional[str]:
    """Compute derivative of expression."""
    try:
        parsed = parse_math(expr)
        if parsed:
            x = sp.Symbol(var)
            deriv = sp.diff(parsed, x)
            return str(deriv)
    except Exception:
        pass
    return None


def compute_integral(expr: str, var: str = 'x') -> Optional[str]:
    """Compute indefinite integral."""
    try:
        parsed = parse_math(expr)
        if parsed:
            x = sp.Symbol(var)
            integral = sp.integrate(parsed, x)
            return str(integral) + " + C"
    except Exception:
        pass
    return None


def expressions_equal(expr1: str, expr2: str) -> Tuple[bool, float]:
    """
    Check if two expressions are mathematically equal.
    
    Returns:
        (is_equal, confidence)
    """
    try:
        p1 = parse_math(expr1)
        p2 = parse_math(expr2)
        
        if p1 is None or p2 is None:
            return False, 0.0
        
        diff = sp.simplify(p1 - p2)
        is_equal = diff == 0
        
        return is_equal, 0.95 if is_equal else 0.1
        
    except Exception:
        return False, 0.0


def evaluate_numeric(expr: str) -> Optional[float]:
    """Evaluate expression to numeric value."""
    try:
        parsed = parse_math(expr)
        if parsed:
            result = float(parsed.evalf())
            return result
    except Exception:
        pass
    return None
