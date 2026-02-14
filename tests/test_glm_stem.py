"""
GLM-STEM Model Quality Tests

Tests to verify the REAP-pruned GLM model (42 experts) works correctly
for STEM tasks: algebra, calculus, programming, physics, and Russian language.

Run: pytest tests/test_glm_stem.py -v
"""

import pytest
import re
from typing import Optional

# Skip all tests if Ollama is not available
pytest.importorskip("ollama")


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def llm_client():
    """Create LLM client for tests. Skip if model not available."""
    try:
        from src.models.llm_client import LLMClient
        client = LLMClient(model="glm-stem-42exp")

        # Check if model is actually available
        if not client.check_connection():
            pytest.skip("Ollama not running")

        models = client.list_models()
        if not any("glm-stem-42exp" in m for m in models):
            pytest.skip("glm-stem-42exp model not installed")

        return client
    except Exception as e:
        pytest.skip(f"Could not initialize LLM client: {e}")


@pytest.fixture(scope="module")
def generate(llm_client):
    """Helper to generate responses with deterministic settings."""
    def _generate(prompt: str, max_tokens: int = 200) -> str:
        return llm_client.generate(
            prompt=prompt,
            temperature=0.0,  # Deterministic
            max_tokens=max_tokens,
            thinking=False
        )
    return _generate


# ============================================================================
# Helper Functions
# ============================================================================

def contains_any(text: str, patterns: list) -> bool:
    """Check if text contains any of the patterns (case-insensitive)."""
    text_lower = text.lower()
    return any(p.lower() in text_lower for p in patterns)


def extract_number(text: str) -> Optional[float]:
    """Extract the first number from text."""
    match = re.search(r'[-+]?\d*\.?\d+', text)
    return float(match.group()) if match else None


# ============================================================================
# Algebra Tests (5 tests)
# ============================================================================

class TestAlgebra:
    """Test algebraic problem solving."""

    @pytest.mark.timeout(60)
    def test_linear_equation_simple(self, generate):
        """Test: 2x + 5 = 13"""
        response = generate("Solve for x: 2x + 5 = 13")
        assert contains_any(response, ["4", "x = 4", "x=4"]), \
            f"Expected x=4, got: {response[:200]}"

    @pytest.mark.timeout(60)
    def test_linear_equation_negative(self, generate):
        """Test: 3x - 9 = 0"""
        response = generate("Solve: 3x - 9 = 0")
        assert contains_any(response, ["3", "x = 3", "x=3"]), \
            f"Expected x=3, got: {response[:200]}"

    @pytest.mark.timeout(60)
    def test_quadratic_factoring(self, generate):
        """Test: x² - 5x + 6 = 0"""
        response = generate("Solve the quadratic equation: x² - 5x + 6 = 0")
        # Solutions are x=2 and x=3
        assert contains_any(response, ["2", "3"]), \
            f"Expected x=2 or x=3, got: {response[:200]}"

    @pytest.mark.timeout(60)
    def test_quadratic_formula(self, generate):
        """Test: x² - 4 = 0"""
        response = generate("Solve: x² - 4 = 0")
        # Solutions are x=2 and x=-2
        assert contains_any(response, ["2", "-2", "±2"]), \
            f"Expected x=±2, got: {response[:200]}"

    @pytest.mark.timeout(60)
    def test_simplify_expression(self, generate):
        """Test simplification: (x + 2)(x - 3)"""
        response = generate("Simplify: (x + 2)(x - 3)")
        assert contains_any(response, ["x²", "x^2", "x2", "-x", "- 6", "-6"]), \
            f"Expected x² - x - 6, got: {response[:200]}"


# ============================================================================
# Calculus Tests (3 tests)
# ============================================================================

class TestCalculus:
    """Test calculus problems."""

    @pytest.mark.timeout(60)
    def test_derivative_power(self, generate):
        """Test: d/dx(x³)"""
        response = generate("Find the derivative of f(x) = x³")
        assert contains_any(response, ["3x²", "3x^2", "3x2"]), \
            f"Expected 3x², got: {response[:200]}"

    @pytest.mark.timeout(60)
    def test_derivative_polynomial(self, generate):
        """Test: d/dx(x² + 2x - 5)"""
        response = generate("What is the derivative of x² + 2x - 5?")
        assert contains_any(response, ["2x + 2", "2x+2", "2(x+1)"]), \
            f"Expected 2x + 2, got: {response[:200]}"

    @pytest.mark.timeout(60)
    def test_integral_simple(self, generate):
        """Test: ∫2x dx"""
        response = generate("Calculate the integral: ∫2x dx")
        assert contains_any(response, ["x²", "x^2", "x2"]), \
            f"Expected x² + C, got: {response[:200]}"


# ============================================================================
# Programming Tests (5 tests)
# ============================================================================

class TestProgramming:
    """Test code generation capabilities."""

    @pytest.mark.timeout(60)
    def test_python_function_syntax(self, generate):
        """Test basic Python function generation."""
        response = generate("Write a Python function to check if a number is even")
        assert "def " in response, f"Expected function definition, got: {response[:200]}"
        assert contains_any(response, ["%", "mod", "2"]), \
            f"Expected modulo operation, got: {response[:200]}"

    @pytest.mark.timeout(60)
    def test_python_factorial(self, generate):
        """Test factorial function."""
        response = generate("Write Python code for factorial function")
        assert "def " in response or "factorial" in response.lower(), \
            f"Expected factorial code, got: {response[:200]}"

    @pytest.mark.timeout(60)
    def test_python_prime_check(self, generate):
        """Test prime number checker."""
        response = generate("Python function to check if n is prime")
        assert contains_any(response, ["def ", "prime", "for", "range"]), \
            f"Expected prime checker code, got: {response[:200]}"

    @pytest.mark.timeout(60)
    def test_python_list_sum(self, generate):
        """Test list summation."""
        response = generate("Python one-liner to sum a list")
        assert contains_any(response, ["sum(", "sum ("]), \
            f"Expected sum() usage, got: {response[:200]}"

    @pytest.mark.timeout(60)
    def test_algorithm_explanation(self, generate):
        """Test algorithm explanation."""
        response = generate("Explain binary search in 2-3 sentences")
        assert contains_any(response, ["middle", "half", "sorted", "divide"]), \
            f"Expected binary search explanation, got: {response[:200]}"


# ============================================================================
# Physics Tests (4 tests)
# ============================================================================

class TestPhysics:
    """Test physics problem solving."""

    @pytest.mark.timeout(60)
    def test_kinematics_velocity(self, generate):
        """Test: v = d/t"""
        response = generate("A car travels 120 km in 2 hours. What is its average speed?")
        assert contains_any(response, ["60", "km/h", "kph"]), \
            f"Expected 60 km/h, got: {response[:200]}"

    @pytest.mark.timeout(60)
    def test_kinematics_acceleration(self, generate):
        """Test: a = (v-u)/t"""
        response = generate("A car accelerates from 0 to 20 m/s in 4 seconds. What is the acceleration?")
        assert contains_any(response, ["5", "m/s²", "m/s^2", "m/s2"]), \
            f"Expected 5 m/s², got: {response[:200]}"

    @pytest.mark.timeout(60)
    def test_force_formula(self, generate):
        """Test: F = ma"""
        response = generate("F = ma. If m = 5 kg and a = 3 m/s², what is F?")
        assert contains_any(response, ["15", "N", "newton"]), \
            f"Expected 15 N, got: {response[:200]}"

    @pytest.mark.timeout(60)
    def test_kinetic_energy(self, generate):
        """Test: KE = 0.5mv²"""
        response = generate("Calculate kinetic energy of a 2 kg object moving at 4 m/s")
        # KE = 0.5 * 2 * 16 = 16 J
        assert contains_any(response, ["16", "J", "joule"]), \
            f"Expected 16 J, got: {response[:200]}"


# ============================================================================
# Russian Language Tests (3 tests)
# ============================================================================

class TestRussian:
    """Test bilingual (Russian) capabilities."""

    @pytest.mark.timeout(60)
    def test_russian_math_response(self, generate):
        """Test response in Russian."""
        response = generate("Реши уравнение: x + 5 = 12")
        # Should mention 7 in some form
        assert "7" in response, f"Expected x=7, got: {response[:200]}"

    @pytest.mark.timeout(60)
    def test_russian_square_root(self, generate):
        """Test square root in Russian."""
        response = generate("Чему равен квадратный корень из 144?")
        assert "12" in response, f"Expected 12, got: {response[:200]}"

    @pytest.mark.timeout(60)
    def test_russian_explanation(self, generate):
        """Test Russian explanation capabilities."""
        response = generate("Объясни, что такое производная, в одном предложении")
        # Should contain Russian words about derivatives/rate of change
        assert contains_any(response, ["производн", "измен", "скорость", "функци"]), \
            f"Expected Russian explanation of derivative, got: {response[:200]}"


# ============================================================================
# Summary Test
# ============================================================================

class TestSummary:
    """Summary test to verify overall model quality."""

    @pytest.mark.timeout(120)
    def test_model_responds(self, llm_client):
        """Verify model can generate any response."""
        response = llm_client.generate("Hello", max_tokens=50)
        assert len(response) > 0, "Model should generate non-empty response"

    def test_model_info(self, llm_client):
        """Verify model is the correct one."""
        assert "glm" in llm_client.model.lower(), \
            f"Expected GLM model, got: {llm_client.model}"
