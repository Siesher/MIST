"""
MITS Response Verifier Agent

Verifies student answers using symbolic math (SymPy) and LLM fallback.
"""

from typing import Optional, Dict, Any
import json
import re
import sympy as sp
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication

from src.agents.base_agent import BaseAgent
from src.models.llm_client import LLMClient
from src.models.prompts import VERIFIER_SYSTEM, VERIFIER_PROMPT, VERIFIER_METHOD_PROMPT
from src.data.schemas import Task, VerificationResult

# SKI for method verification
try:
    from src.knowledge.ski import get_ski
    HAS_SKI = True
except ImportError:
    HAS_SKI = False
    get_ski = None


class ResponseVerifierAgent(BaseAgent):
    """
    Agent for verifying student answers.
    
    Uses a hybrid approach:
    1. SymPy for symbolic/numeric verification
    2. LLM fallback for complex/text answers
    """
    
    def __init__(self, llm_client: LLMClient):
        super().__init__(
            name="ResponseVerifier",
            llm_client=llm_client,
            system_prompt=VERIFIER_SYSTEM
        )
        
        # SymPy parsing transformations
        self.transformations = standard_transformations + (implicit_multiplication,)
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify student response.
        
        Args:
            input_data: {
                "task": Task,
                "student_response": str
            }
            
        Returns:
            {"result": VerificationResult}
        """
        task = input_data["task"]
        student_response = input_data["student_response"]
        
        result = self.verify(task, student_response)
        return {"result": result}
    
    def verify(
        self,
        task: Task,
        student_response: str,
        expected_method_id: Optional[str] = None,
    ) -> VerificationResult:
        """
        Verify if student's response is correct.

        Tries symbolic verification first, falls back to LLM.
        After answer is confirmed correct, optionally checks solution method.
        """
        # Try symbolic verification first (faster, more reliable)
        symbolic_result = self._verify_symbolic(task.answer, student_response)

        if symbolic_result is not None:
            self._log_action("symbolic_verification", {
                "success": True,
                "result": symbolic_result.is_correct
            })
            result = symbolic_result
        else:
            # Fallback to LLM verification
            self._log_action("llm_verification_fallback")
            result = self._verify_with_llm(task, student_response)

        # Method verification: only when answer is correct and method check requested
        if result.is_correct and expected_method_id:
            method_info = self.verify_method(task, student_response, expected_method_id)
            if method_info:
                result.method_used = method_info.get("method_used")
                result.expected_method = expected_method_id
                result.method_correct = method_info.get("matches_expected", None)
                result.method_feedback = method_info.get("feedback")
                if result.method_correct is False:
                    result.error_type = "wrong_method"

        return result

    def verify_method(
        self,
        task: Task,
        student_response: str,
        expected_method_id: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Check if student used the expected solution method.
        Returns dict with {method_used, matches_expected, feedback} or None.
        """
        if not HAS_SKI or not expected_method_id:
            return None

        try:
            ski = get_ski()
            topic = task.topic if hasattr(task, 'topic') else None
            if not topic:
                return None

            methods = ski.get_solution_methods(topic, method_id=expected_method_id)
            if not methods:
                return None

            m = methods[0]
            steps_text = "\n".join(
                f"{s.get('step', '')}: {s.get('action', '')}"
                for s in m.get("steps", [])
            )

            prompt = VERIFIER_METHOD_PROMPT.format(
                problem=task.problem,
                method_name=m.get("name", expected_method_id),
                method_steps=steps_text,
                student_response=student_response,
            )

            response = self._call_llm(prompt, json_mode=True, thinking=False)
            data = json.loads(response)
            return {
                "method_used": data.get("method_used", "unknown"),
                "matches_expected": data.get("matches_expected", None),
                "feedback": data.get("feedback", ""),
            }
        except Exception as e:
            self.logger.debug("method_verification_failed", error=str(e))
            return None
    
    def _verify_symbolic(
        self,
        correct_answer: str,
        student_response: str
    ) -> Optional[VerificationResult]:
        """
        Try to verify answer using SymPy.
        
        Returns None if symbolic verification not possible.
        """
        try:
            # Clean expressions
            correct_clean = self._clean_expression(correct_answer)
            student_clean = self._extract_answer(student_response)
            
            if not student_clean:
                return None
            
            student_clean = self._clean_expression(student_clean)
            
            # Try numeric comparison first
            try:
                correct_val = float(eval(correct_clean.replace('^', '**')))
                student_val = float(eval(student_clean.replace('^', '**')))
                
                is_correct = abs(correct_val - student_val) < 0.001
                
                return VerificationResult(
                    is_correct=is_correct,
                    confidence=0.95,
                    has_error=not is_correct,
                    error_type="arithmetic" if not is_correct else None
                )
            except (ValueError, SyntaxError, ZeroDivisionError):
                pass
            
            # Try symbolic comparison
            correct_sym = parse_expr(correct_clean, transformations=self.transformations)
            student_sym = parse_expr(student_clean, transformations=self.transformations)
            
            diff = sp.simplify(correct_sym - student_sym)
            is_correct = diff == 0
            
            return VerificationResult(
                is_correct=is_correct,
                confidence=0.9,
                has_error=not is_correct,
                error_type="algebraic" if not is_correct else None
            )
            
        except Exception as e:
            self.logger.debug("symbolic_verification_failed", error=str(e))
            return None
    
    def _verify_with_llm(
        self,
        task: Task,
        student_response: str
    ) -> VerificationResult:
        """Verify answer using LLM."""
        
        prompt = VERIFIER_PROMPT.format(
            problem=task.problem,
            correct_answer=task.answer,
            student_response=student_response
        )
        
        try:
            response = self._call_llm(prompt, json_mode=True, thinking=False)
            data = json.loads(response)
            
            return VerificationResult(
                is_correct=data.get("is_correct", False),
                is_partial=data.get("is_partial", False),
                confidence=data.get("confidence", 0.7),
                has_error=data.get("has_error", False),
                error_type=data.get("error_type"),
                error_location=data.get("error_location"),
                feedback=data.get("feedback")
            )
            
        except (json.JSONDecodeError, Exception) as e:
            self.logger.error("llm_verification_failed", error=str(e))
            
            # Conservative fallback
            return VerificationResult(
                is_correct=False,
                confidence=0.3,
                feedback="Could not verify answer automatically."
            )
    
    # Russian math notation → SymPy-compatible names
    RUSSIAN_TO_SYMPY = {
        'tg': 'tan', 'ctg': 'cot', 'arctg': 'atan', 'arcctg': 'acot',
        'sh': 'sinh', 'ch': 'cosh', 'th': 'tanh', 'cth': 'coth',
        'lg': 'log10', 'cosec': 'csc',
    }

    def _clean_expression(self, expr: str) -> str:
        """Clean expression for SymPy parsing."""
        expr = expr.strip()

        # Russian → SymPy function name normalization
        for rus, eng in self.RUSSIAN_TO_SYMPY.items():
            # Replace as whole word (avoid replacing 'ch' inside 'char' etc.)
            expr = re.sub(rf'\b{rus}\b', eng, expr)

        # Replace common notations
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

        # Handle implicit multiplication: 2x -> 2*x
        expr = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr)

        # Handle parentheses multiplication: 2(x) -> 2*(x)
        expr = re.sub(r'(\d)\(', r'\1*(', expr)

        return expr
    
    def _extract_answer(self, response: str) -> Optional[str]:
        """
        Extract mathematical answer from student response.
        
        Handles formats like:
        - "The answer is 42"
        - "x = 5"
        - "f'(x) = 2x + 3"
        - Just the number/expression
        """
        response = response.strip()
        
        # Try to find answer patterns
        patterns = [
            r'(?:answer|result|solution)\s*(?:is|=|:)\s*(.+?)(?:\.|$)',
            r'(?:x|y|f\([^)]*\)|f\'?\([^)]*\))\s*=\s*(.+?)(?:\.|$)',
            r'=\s*(.+?)(?:\.|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # If response is short, treat whole thing as answer
        if len(response) < 50 and not ' ' in response.strip():
            return response
        
        # Look for the last mathematical expression
        math_pattern = r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?|[-+]?\d*[a-zA-Z]+(?:\^?\d+)?'
        matches = re.findall(math_pattern, response)
        
        if matches:
            return matches[-1]
        
        return None
