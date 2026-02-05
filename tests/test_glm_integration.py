#!/usr/bin/env python3
"""
Quick integration test for GLM-4.7-Flash model.

Run: python -m pytest tests/test_glm_integration.py -v
Or:  python tests/test_glm_integration.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.llm_client import LLMClient
from src.config import settings


def test_glm_connection():
    """Test that GLM model is accessible."""
    client = LLMClient()
    assert client.check_connection(), "Ollama server not reachable"

    models = client.list_models()
    assert any("glm" in m.lower() for m in models), f"GLM model not found. Available: {models}"
    print(f"[OK] GLM model found. Available models: {models}")


def test_glm_basic_inference():
    """Test basic math problem solving."""
    client = LLMClient(model="glm-4.7-flash")

    response = client.generate(
        prompt="Calculate: 2 + 2 = ?",
        thinking=False,  # Disable thinking for simple math
        temperature=0.1,
        max_tokens=50
    )

    assert "4" in response, f"Expected '4' in response, got: {response}"
    print(f"[OK] Basic inference works: {response.strip()}")


def test_glm_socratic_hint():
    """Test Socratic hint generation."""
    client = LLMClient(model="glm-4.7-flash")

    response = client.generate(
        prompt="""A student is solving the equation: 5x + 3 = 18
Give a Socratic question to help them think about the next step.
Do not reveal the answer.""",
        thinking=False,  # Get direct response
        temperature=0.3,
        max_tokens=300
    )

    # Should contain a question or guiding text
    has_question = "?" in response
    has_guidance = any(word in response.lower() for word in
                       ["think", "what", "how", "try", "consider", "subtract", "isolate"])

    assert has_question or has_guidance, f"Expected guidance, got: {response}"
    print(f"[OK] Socratic hint generated:\n{response.strip()[:200]}...")


def test_glm_step_by_step():
    """Test step-by-step solution generation."""
    client = LLMClient(model="glm-4.7-flash")

    response = client.generate(
        prompt="Solve step by step: 4x - 8 = 12",
        thinking=False,  # Get direct response without thinking
        temperature=0.2,
        max_tokens=800  # More tokens for full solution
    )

    # Should contain step markers
    has_steps = any(marker in response.lower() for marker in
                    ["step", "1.", "2.", "first", "add", "divide", "isolate"])
    assert has_steps, f"Expected step-by-step, got: {response}"

    # Should contain the calculation (4x = 20 leads to x = 5)
    has_math = "20" in response or "5" in response
    assert has_math, f"Expected math content, got: {response}"

    print(f"[OK] Step-by-step solution works (length: {len(response)} chars)")


def test_glm_model_specific_params():
    """Test that GLM-specific parameters are applied."""
    client = LLMClient(model="glm-4.7-flash")

    # Check that GLM defaults are applied
    assert client._temperature == 0.2, f"Expected temp 0.2, got {client._temperature}"
    assert client._repetition_penalty == 1.0, f"Expected rep_penalty 1.0, got {client._repetition_penalty}"

    print(f"[OK] GLM-specific params: temp={client._temperature}, rep_penalty={client._repetition_penalty}")


def run_all_tests():
    """Run all tests manually."""
    print("\n" + "="*60)
    print("GLM-4.7-Flash Integration Tests")
    print("="*60 + "\n")

    tests = [
        test_glm_connection,
        test_glm_model_specific_params,
        test_glm_basic_inference,
        test_glm_socratic_hint,
        test_glm_step_by_step,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            print(f"\n--- {test.__name__} ---")
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] FAILED: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
