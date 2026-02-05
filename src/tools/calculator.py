"""
MITS Calculator Tool

Provides precise mathematical computations using SymPy.
Supports symbolic and numerical calculations.
"""

import re
from typing import Optional
import time

from sympy import (
    sympify, simplify, expand, factor, solve, diff, integrate,
    limit, series, Matrix, symbols, sqrt, sin, cos, tan, log, exp,
    factorial, binomial, gcd, lcm, pi, E, I, oo,
    Rational, Float, Integer, Symbol
)
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations,
    implicit_multiplication_application, convert_xor
)

from src.tools import BaseTool, ToolResult, ToolType


class CalculatorTool(BaseTool):
    """
    Calculator tool for mathematical computations.

    Supports:
    - Arithmetic: +, -, *, /, **, !, sqrt
    - Algebra: solve, factor, expand, simplify
    - Calculus: diff, integrate, limit, series
    - Special: factorial, binomial, gcd, lcm
    """

    TRANSFORMATIONS = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
    )

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Performs precise mathematical calculations including algebra, calculus, and symbolic math"

    def execute(self, query: str, **kwargs) -> ToolResult:
        """
        Execute a mathematical calculation.

        Args:
            query: Mathematical expression or command

        Returns:
            ToolResult with computed answer
        """
        start_time = time.time()

        try:
            # Clean and normalize query
            cleaned = self._clean_expression(query)

            # Try to detect operation type
            result = self._compute(cleaned)

            execution_time = (time.time() - start_time) * 1000

            return ToolResult(
                success=True,
                result=str(result),
                tool_type=ToolType.CALCULATOR,
                execution_time_ms=execution_time
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return ToolResult(
                success=False,
                result=None,
                error=self._format_error(str(e)),
                tool_type=ToolType.CALCULATOR,
                execution_time_ms=execution_time
            )

    def can_handle(self, query: str) -> bool:
        """Check if query looks like a math calculation."""
        query_lower = query.lower()

        # Math keywords
        math_keywords = [
            'вычисл', 'посчита', 'чему равн', 'сколько будет',
            'calculate', 'compute', 'what is', 'solve', 'find',
            'factorial', 'интеграл', 'производн', 'derive', 'integrate',
            'упрост', 'simplify', 'factor', 'expand',
        ]

        if any(kw in query_lower for kw in math_keywords):
            return True

        # Check for mathematical patterns
        math_patterns = [
            r'\d+\s*[\+\-\*\/\^]\s*\d+',  # 2 + 3, 5 * 4
            r'\d+!',  # factorial
            r'sqrt|sin|cos|tan|log|exp',  # functions
            r'\d+\s*/\s*\d+',  # fractions
            r'x\s*[\+\-\*\/\^=]',  # algebraic
        ]

        for pattern in math_patterns:
            if re.search(pattern, query_lower):
                return True

        return False

    def _clean_expression(self, expr: str) -> str:
        """Clean and normalize expression for parsing."""
        # Remove natural language wrappers
        expr = re.sub(r'(?:вычисли|посчитай|чему равно|what is|calculate)\s*:?\s*', '', expr, flags=re.IGNORECASE)
        expr = expr.strip().strip('?').strip()

        # Replace Russian math notation
        replacements = {
            '×': '*',
            '÷': '/',
            '^': '**',
            ':': '/',  # ratio notation
            ',': '.',  # decimal separator
            'пи': 'pi',
            'е': 'E',  # Euler's number (careful with Cyrillic)
        }

        for old, new in replacements.items():
            expr = expr.replace(old, new)

        return expr

    def _compute(self, expr: str):
        """
        Compute the expression, detecting operation type.
        """
        expr_lower = expr.lower()

        # Detect and handle specific operations
        if 'solve' in expr_lower or 'реши' in expr_lower:
            return self._solve_equation(expr)

        if 'diff' in expr_lower or 'производн' in expr_lower or 'derivative' in expr_lower:
            return self._differentiate(expr)

        if 'integr' in expr_lower or 'интеграл' in expr_lower:
            return self._integrate(expr)

        if 'limit' in expr_lower or 'предел' in expr_lower:
            return self._compute_limit(expr)

        if 'factor' in expr_lower:
            return self._factor(expr)

        if 'expand' in expr_lower or 'раскр' in expr_lower:
            return self._expand(expr)

        if 'simplify' in expr_lower or 'упрост' in expr_lower:
            return self._simplify(expr)

        # Default: evaluate expression
        return self._evaluate(expr)

    def _evaluate(self, expr: str):
        """Evaluate a mathematical expression."""
        # Parse with transformations
        parsed = parse_expr(expr, transformations=self.TRANSFORMATIONS)
        result = simplify(parsed)

        # Try to get numerical value if possible
        try:
            if result.is_number:
                # Return as integer if whole number
                float_val = float(result)
                if float_val == int(float_val):
                    return int(float_val)
                return float_val
        except (TypeError, ValueError):
            pass

        return result

    def _solve_equation(self, expr: str):
        """Solve an equation."""
        # Extract equation part
        expr = re.sub(r'(?:solve|реши)\s*:?\s*', '', expr, flags=re.IGNORECASE)

        # Find the variable
        x = symbols('x')

        # Handle equation with =
        if '=' in expr:
            left, right = expr.split('=', 1)
            left_expr = parse_expr(left.strip(), transformations=self.TRANSFORMATIONS)
            right_expr = parse_expr(right.strip(), transformations=self.TRANSFORMATIONS)
            equation = left_expr - right_expr
        else:
            equation = parse_expr(expr, transformations=self.TRANSFORMATIONS)

        solutions = solve(equation, x)
        return solutions

    def _differentiate(self, expr: str):
        """Compute derivative."""
        # Extract expression
        expr = re.sub(r'(?:diff|derivative|производная)\s*(?:of)?\s*:?\s*', '', expr, flags=re.IGNORECASE)

        x = symbols('x')
        parsed = parse_expr(expr, transformations=self.TRANSFORMATIONS)
        return diff(parsed, x)

    def _integrate(self, expr: str):
        """Compute integral."""
        expr = re.sub(r'(?:integrate|integral|интеграл)\s*(?:of)?\s*:?\s*', '', expr, flags=re.IGNORECASE)

        x = symbols('x')
        parsed = parse_expr(expr, transformations=self.TRANSFORMATIONS)
        return integrate(parsed, x)

    def _compute_limit(self, expr: str):
        """Compute limit."""
        expr = re.sub(r'(?:limit|предел)\s*(?:of)?\s*:?\s*', '', expr, flags=re.IGNORECASE)

        x = symbols('x')
        # Try to find "as x -> value" pattern
        match = re.search(r'as\s+x\s*->\s*(\w+|\d+|inf)', expr, re.IGNORECASE)
        point = oo if match and 'inf' in match.group(1).lower() else 0

        expr = re.sub(r'\s*as\s+x\s*->\s*\w+', '', expr, flags=re.IGNORECASE)
        parsed = parse_expr(expr, transformations=self.TRANSFORMATIONS)

        return limit(parsed, x, point)

    def _factor(self, expr: str):
        """Factor an expression."""
        expr = re.sub(r'factor\s*:?\s*', '', expr, flags=re.IGNORECASE)
        parsed = parse_expr(expr, transformations=self.TRANSFORMATIONS)
        return factor(parsed)

    def _expand(self, expr: str):
        """Expand an expression."""
        expr = re.sub(r'(?:expand|раскрой)\s*:?\s*', '', expr, flags=re.IGNORECASE)
        parsed = parse_expr(expr, transformations=self.TRANSFORMATIONS)
        return expand(parsed)

    def _simplify(self, expr: str):
        """Simplify an expression."""
        expr = re.sub(r'(?:simplify|упрости)\s*:?\s*', '', expr, flags=re.IGNORECASE)
        parsed = parse_expr(expr, transformations=self.TRANSFORMATIONS)
        return simplify(parsed)

    def _format_error(self, error: str) -> str:
        """Format error message for user."""
        if 'invalid syntax' in error.lower():
            return "Неверный синтаксис выражения. Проверьте скобки и операторы."
        if 'division by zero' in error.lower():
            return "Деление на ноль невозможно."
        if 'could not parse' in error.lower():
            return "Не удалось распознать выражение. Попробуйте записать иначе."
        return f"Ошибка вычисления: {error}"


# Convenience function
def calculate(expression: str) -> ToolResult:
    """
    Quick calculation function.

    Args:
        expression: Mathematical expression

    Returns:
        ToolResult with answer or error
    """
    calc = CalculatorTool()
    return calc.execute(expression)
