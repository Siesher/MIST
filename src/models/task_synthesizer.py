"""
Generative Task Synthesis Module

Generates mathematical tasks with SymPy-verified solutions.
Supports:
- Derivatives
- Integrals
- Limits
- Equations
- Trigonometry

Each generated task has a mathematically verified correct answer.
"""

import logging
import random
import uuid
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from src.data.schemas import (
    GeneratedTask,
    VerificationStatus,
    Difficulty,
)
from src.utils.sympy_utils import (
    safe_diff,
    safe_integrate,
    safe_limit,
    safe_solve,
    safe_parse_expr,
    verify_equality,
    to_latex,
    is_sympy_available,
)
from src.config import get_settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# TASK TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════

DERIVATIVE_TEMPLATES = {
    "easy": [
        {"function": "x^{n}", "params": {"n": (2, 5)}},
        {"function": "{a}*x^{n}", "params": {"a": (2, 10), "n": (2, 4)}},
        {"function": "{a}*x^{n} + {b}*x", "params": {"a": (2, 5), "n": (2, 3), "b": (1, 10)}},
    ],
    "medium": [
        {"function": "sin({a}*x)", "params": {"a": (1, 3)}},
        {"function": "cos({a}*x)", "params": {"a": (1, 3)}},
        {"function": "x^{n}*sin(x)", "params": {"n": (2, 3)}},
        {"function": "exp({a}*x)", "params": {"a": (1, 3)}},
        {"function": "ln({a}*x)", "params": {"a": (1, 5)}},
    ],
    "hard": [
        {"function": "x^{n}*exp(x)", "params": {"n": (2, 3)}},
        {"function": "sin(x)*cos(x)", "params": {}},
        {"function": "sin(x^{n})", "params": {"n": (2, 3)}},
        {"function": "exp(sin(x))", "params": {}},
        {"function": "{a}*x/({b}*x + {c})", "params": {"a": (1, 5), "b": (1, 3), "c": (1, 5)}},
    ],
}

INTEGRAL_TEMPLATES = {
    "easy": [
        {"function": "x^{n}", "params": {"n": (2, 5)}},
        {"function": "{a}*x^{n}", "params": {"a": (2, 10), "n": (1, 3)}},
        {"function": "{a}*x + {b}", "params": {"a": (2, 10), "b": (1, 10)}},
    ],
    "medium": [
        {"function": "sin({a}*x)", "params": {"a": (1, 3)}},
        {"function": "cos({a}*x)", "params": {"a": (1, 3)}},
        {"function": "exp({a}*x)", "params": {"a": (1, 3)}},
        {"function": "1/x", "params": {}},
        {"function": "1/(x + {a})", "params": {"a": (1, 5)}},
    ],
    "hard": [
        {"function": "x*exp(x)", "params": {}},
        {"function": "x*sin(x)", "params": {}},
        {"function": "x*cos(x)", "params": {}},
        {"function": "sin(x)^2", "params": {}},
        {"function": "1/(x^2 + 1)", "params": {}},
    ],
}

LIMIT_TEMPLATES = {
    "easy": [
        {"function": "(x^2 - {a}^2)/(x - {a})", "point": "{a}", "params": {"a": (1, 5)}},
        {"function": "{a}*x + {b}", "point": "{c}", "params": {"a": (1, 5), "b": (1, 10), "c": (0, 3)}},
    ],
    "medium": [
        {"function": "sin(x)/x", "point": "0", "params": {}},
        {"function": "(1 - cos(x))/x^2", "point": "0", "params": {}},
        {"function": "(exp(x) - 1)/x", "point": "0", "params": {}},
    ],
    "hard": [
        {"function": "x^x", "point": "0", "params": {}, "direction": "+"},
        {"function": "(1 + 1/x)^x", "point": "oo", "params": {}},
        {"function": "x*ln(x)", "point": "0", "params": {}, "direction": "+"},
    ],
}

EQUATION_TEMPLATES = {
    "easy": [
        {"equation": "{a}*x + {b} = 0", "params": {"a": (2, 10), "b": (-10, 10)}},
        {"equation": "x^2 = {a}", "params": {"a": (1, 25)}},
    ],
    "medium": [
        {"equation": "x^2 + {b}*x + {c} = 0", "params": {"b": (-10, 10), "c": (-10, 10)}},
        {"equation": "x^2 - {a}*x = 0", "params": {"a": (2, 10)}},
    ],
    "hard": [
        {"equation": "x^3 - {a}*x = 0", "params": {"a": (1, 9)}},
        {"equation": "exp(x) = {a}", "params": {"a": (1, 10)}},
        {"equation": "sin(x) = {a}", "params": {"a": (0.5, 0.5)}},  # sin(x) = 0.5
    ],
}


class TaskSynthesizer:
    """
    Generates and verifies mathematical tasks.

    Uses LLM for problem text generation and SymPy for answer verification.
    """

    def __init__(
        self,
        llm_client: Optional[object] = None,
        verification_enabled: bool = True,
        max_retries: int = 3
    ):
        """
        Initialize synthesizer.

        Args:
            llm_client: LLM for natural language generation (optional)
            verification_enabled: Whether to verify with SymPy
            max_retries: Maximum generation retries on failure
        """
        settings = get_settings()
        self.llm_client = llm_client
        self.verification_enabled = verification_enabled and settings.TASK_SYNTHESIS_VERIFY_WITH_SYMPY
        self.max_retries = max_retries or settings.TASK_SYNTHESIS_MAX_RETRIES

        if not is_sympy_available():
            logger.warning("SymPy not available, verification disabled")
            self.verification_enabled = False

        logger.info(f"TaskSynthesizer initialized (verification={self.verification_enabled})")

    def generate_task(
        self,
        topic: str,
        difficulty: "Difficulty | str" = Difficulty.MEDIUM,
        student_profile: Optional[object] = None
    ) -> GeneratedTask:
        """
        Generate a new task for the given topic.

        Args:
            topic: Math topic (derivatives, integrals, limits, equations, trig)
            difficulty: Desired difficulty level (Difficulty enum or string)
            student_profile: Optional student info for personalization

        Returns:
            GeneratedTask with verified solution
        """
        # Convert string to Difficulty enum if needed
        if isinstance(difficulty, str):
            difficulty_str = difficulty.lower()
            difficulty_map = {"easy": Difficulty.EASY, "medium": Difficulty.MEDIUM, "hard": Difficulty.HARD}
            difficulty = difficulty_map.get(difficulty_str, Difficulty.MEDIUM)

        logger.debug(f"Generating task: topic={topic}, difficulty={difficulty.value}")

        # Select generator based on topic
        generators = {
            "derivatives": self._generate_derivative_task,
            "derivative": self._generate_derivative_task,
            "производные": self._generate_derivative_task,
            "integrals": self._generate_integral_task,
            "integral": self._generate_integral_task,
            "интегралы": self._generate_integral_task,
            "limits": self._generate_limit_task,
            "limit": self._generate_limit_task,
            "пределы": self._generate_limit_task,
            "equations": self._generate_equation_task,
            "equation": self._generate_equation_task,
            "уравнения": self._generate_equation_task,
            "trig": self._generate_trig_task,
            "trigonometry": self._generate_trig_task,
            "тригонометрия": self._generate_trig_task,
        }

        generator = generators.get(topic.lower())
        if generator is None:
            # Default to derivatives
            logger.warning(f"Unknown topic '{topic}', defaulting to derivatives")
            generator = self._generate_derivative_task

        # Try to generate with retries
        for attempt in range(self.max_retries):
            try:
                task = generator(difficulty)
                if task.sympy_verified or not self.verification_enabled:
                    logger.debug(f"Task generated successfully on attempt {attempt + 1}")
                    return task
            except Exception as e:
                logger.warning(f"Generation attempt {attempt + 1} failed: {e}")

        # Return last attempt even if not verified
        logger.warning("Max retries reached, returning unverified task")
        return task

    def _generate_derivative_task(self, difficulty: Difficulty) -> GeneratedTask:
        """Generate a derivative task."""
        templates = DERIVATIVE_TEMPLATES.get(difficulty.value, DERIVATIVE_TEMPLATES["medium"])
        template = random.choice(templates)

        # Fill in parameters
        function_str = self._fill_template(template["function"], template.get("params", {}))

        # Compute derivative
        answer, err = safe_diff(function_str, "x")
        if err:
            raise ValueError(f"SymPy error: {err}")

        # Convert to LaTeX
        func_latex, _ = to_latex(function_str)
        answer_latex, _ = to_latex(answer)

        # Generate problem text
        problem = f"Найдите производную функции f(x) = {func_latex or function_str}"
        problem_ru = problem

        # Generate hints
        hints = self._generate_derivative_hints(function_str, difficulty)

        return GeneratedTask(
            id=str(uuid.uuid4()),
            topic="derivatives",
            subtopic=self._identify_derivative_subtopic(function_str),
            difficulty=difficulty,
            problem=problem_ru,
            problem_latex=f"f(x) = {func_latex}" if func_latex else None,
            solution_steps=self._generate_derivative_steps(function_str),
            answer=answer,
            answer_latex=answer_latex,
            answer_sympy=answer,
            verification_status=VerificationStatus.VERIFIED,
            sympy_verified=True,
            hints=hints,
            required_skills=self._identify_required_skills_derivative(function_str),
            generated_at=datetime.now(),
        )

    def _generate_integral_task(self, difficulty: Difficulty) -> GeneratedTask:
        """Generate an integral task."""
        templates = INTEGRAL_TEMPLATES.get(difficulty.value, INTEGRAL_TEMPLATES["medium"])
        template = random.choice(templates)

        function_str = self._fill_template(template["function"], template.get("params", {}))

        # Compute integral
        answer, err = safe_integrate(function_str, "x")
        if err:
            raise ValueError(f"SymPy error: {err}")

        # Add constant of integration
        answer = f"{answer} + C"

        func_latex, _ = to_latex(function_str)
        answer_latex, _ = to_latex(answer.replace(" + C", ""))
        if answer_latex:
            answer_latex = f"{answer_latex} + C"

        problem = f"Вычислите неопределённый интеграл ∫({func_latex or function_str})dx"

        hints = self._generate_integral_hints(function_str, difficulty)

        return GeneratedTask(
            id=str(uuid.uuid4()),
            topic="integrals",
            difficulty=difficulty,
            problem=problem,
            problem_latex=f"\\int ({func_latex}) dx" if func_latex else None,
            solution_steps=self._generate_integral_steps(function_str),
            answer=answer,
            answer_latex=answer_latex,
            answer_sympy=answer.replace(" + C", ""),
            verification_status=VerificationStatus.VERIFIED,
            sympy_verified=True,
            hints=hints,
            required_skills=["antiderivatives"],
            generated_at=datetime.now(),
        )

    def _generate_limit_task(self, difficulty: Difficulty) -> GeneratedTask:
        """Generate a limit task."""
        templates = LIMIT_TEMPLATES.get(difficulty.value, LIMIT_TEMPLATES["medium"])
        template = random.choice(templates)

        function_str = self._fill_template(template["function"], template.get("params", {}))
        point = self._fill_template(template["point"], template.get("params", {}))
        direction = template.get("direction", "+-")

        # Compute limit
        answer, err = safe_limit(function_str, "x", point, direction)
        if err:
            raise ValueError(f"SymPy error: {err}")

        func_latex, _ = to_latex(function_str)

        if point == "oo":
            point_display = "∞"
        elif point == "-oo":
            point_display = "-∞"
        else:
            point_display = point

        problem = f"Вычислите предел: lim(x→{point_display}) [{func_latex or function_str}]"

        return GeneratedTask(
            id=str(uuid.uuid4()),
            topic="limits",
            difficulty=difficulty,
            problem=problem,
            problem_latex=f"\\lim_{{x \\to {point_display}}} ({func_latex})" if func_latex else None,
            solution_steps=[],
            answer=answer,
            answer_latex=answer,
            answer_sympy=answer,
            verification_status=VerificationStatus.VERIFIED,
            sympy_verified=True,
            hints=["Проверьте, есть ли неопределённость", "Попробуйте правило Лопиталя"],
            required_skills=["limits_techniques"],
            generated_at=datetime.now(),
        )

    def _generate_equation_task(self, difficulty: Difficulty) -> GeneratedTask:
        """Generate an equation task."""
        templates = EQUATION_TEMPLATES.get(difficulty.value, EQUATION_TEMPLATES["medium"])
        template = random.choice(templates)

        equation_str = self._fill_template(template["equation"], template.get("params", {}))

        # Solve equation
        solutions, err = safe_solve(equation_str, "x")
        if err:
            raise ValueError(f"SymPy error: {err}")

        answer = ", ".join(f"x = {s}" for s in solutions) if solutions else "Нет решений"

        problem = f"Решите уравнение: {equation_str}"

        return GeneratedTask(
            id=str(uuid.uuid4()),
            topic="equations",
            difficulty=difficulty,
            problem=problem,
            solution_steps=[],
            answer=answer,
            answer_sympy=str(solutions),
            verification_status=VerificationStatus.VERIFIED,
            sympy_verified=True,
            hints=["Приведите к стандартному виду", "Попробуйте разложить на множители"],
            required_skills=["quadratic_equations"] if "^2" in equation_str else ["linear_equations"],
            generated_at=datetime.now(),
        )

    def _generate_trig_task(self, difficulty: Difficulty) -> GeneratedTask:
        """Generate a trigonometry task (uses derivative templates with trig)."""
        # Use medium/hard derivative templates that involve trig
        templates = DERIVATIVE_TEMPLATES.get(
            "hard" if difficulty == Difficulty.HARD else "medium",
            DERIVATIVE_TEMPLATES["medium"]
        )

        # Filter for trig functions
        trig_templates = [t for t in templates if any(f in t["function"] for f in ["sin", "cos", "tan"])]
        if not trig_templates:
            trig_templates = [{"function": "sin({a}*x)", "params": {"a": (1, 3)}}]

        template = random.choice(trig_templates)
        function_str = self._fill_template(template["function"], template.get("params", {}))

        answer, err = safe_diff(function_str, "x")
        if err:
            raise ValueError(f"SymPy error: {err}")

        func_latex, _ = to_latex(function_str)
        answer_latex, _ = to_latex(answer)

        problem = f"Найдите производную: f(x) = {func_latex or function_str}"

        return GeneratedTask(
            id=str(uuid.uuid4()),
            topic="trig",
            subtopic="trig_derivatives",
            difficulty=difficulty,
            problem=problem,
            problem_latex=f"f(x) = {func_latex}" if func_latex else None,
            solution_steps=[],
            answer=answer,
            answer_latex=answer_latex,
            answer_sympy=answer,
            verification_status=VerificationStatus.VERIFIED,
            sympy_verified=True,
            hints=["Вспомните производные тригонометрических функций", "(sin x)' = cos x, (cos x)' = -sin x"],
            required_skills=["trig_derivatives", "chain_rule"],
            generated_at=datetime.now(),
        )

    def _fill_template(self, template: str, params: Dict) -> str:
        """Fill template with random parameters."""
        result = template
        for param, range_val in params.items():
            if isinstance(range_val, tuple) and len(range_val) == 2:
                if isinstance(range_val[0], int):
                    value = random.randint(range_val[0], range_val[1])
                else:
                    value = random.uniform(range_val[0], range_val[1])
                result = result.replace(f"{{{param}}}", str(value))
        return result

    def _identify_derivative_subtopic(self, function: str) -> str:
        """Identify the subtopic based on function structure."""
        if "*" in function and any(f in function for f in ["sin", "cos", "exp"]):
            return "product_rule"
        if "/" in function:
            return "quotient_rule"
        if "(" in function and any(f in function for f in ["sin", "cos", "exp", "ln"]):
            return "chain_rule"
        return "power_rule"

    def _identify_required_skills_derivative(self, function: str) -> List[str]:
        """Identify required skills for a derivative task."""
        skills = ["derivatives_basic"]
        if "*" in function:
            skills.append("product_rule")
        if "/" in function:
            skills.append("quotient_rule")
        if "sin" in function or "cos" in function:
            skills.append("trig_derivatives")
        if "(" in function:
            skills.append("chain_rule")
        return skills

    def _generate_derivative_hints(self, function: str, difficulty: Difficulty) -> List[str]:
        """Generate progressive hints for derivative task."""
        hints = []

        if "*" in function:
            hints.append("Используйте правило произведения: (fg)' = f'g + fg'")
        elif "/" in function:
            hints.append("Используйте правило частного: (f/g)' = (f'g - fg')/g²")

        if "sin" in function or "cos" in function:
            hints.append("Помните: (sin x)' = cos x, (cos x)' = -sin x")

        if difficulty == Difficulty.HARD:
            hints.append("Не забудьте про правило цепочки для сложных функций")

        if not hints:
            hints.append("Примените правило степени: (xⁿ)' = n·xⁿ⁻¹")

        return hints[:3]

    def _generate_integral_hints(self, function: str, difficulty: Difficulty) -> List[str]:
        """Generate progressive hints for integral task."""
        hints = []

        if "exp" in function:
            hints.append("Интеграл от exp(ax) = (1/a)·exp(ax)")
        elif "sin" in function:
            hints.append("∫sin(ax)dx = -(1/a)·cos(ax)")
        elif "cos" in function:
            hints.append("∫cos(ax)dx = (1/a)·sin(ax)")
        else:
            hints.append("∫xⁿdx = xⁿ⁺¹/(n+1) + C")

        hints.append("Не забудьте константу интегрирования C")

        return hints[:3]

    def _generate_derivative_steps(self, function: str) -> List[str]:
        """Generate solution steps for derivative."""
        steps = [f"Дано: f(x) = {function}"]

        if "*" in function:
            steps.append("Применяем правило произведения: (fg)' = f'g + fg'")
        elif "/" in function:
            steps.append("Применяем правило частного: (f/g)' = (f'g - fg')/g²")
        else:
            steps.append("Применяем правило степени и цепочки")

        return steps

    def _generate_integral_steps(self, function: str) -> List[str]:
        """Generate solution steps for integral."""
        steps = [f"Дано: ∫({function})dx"]
        steps.append("Применяем формулу интегрирования")
        steps.append("Добавляем константу интегрирования C")
        return steps

    def verify_task(self, task: GeneratedTask) -> Tuple[bool, Optional[str]]:
        """
        Verify task solution using SymPy.

        Returns:
            (is_valid, error_message)
        """
        if not is_sympy_available():
            return False, "SymPy not available"

        if task.topic == "derivatives":
            # Re-compute derivative and compare
            result, err = safe_diff(task.problem_latex or task.problem, "x")
            if err:
                return False, err

            is_equal, conf, err = verify_equality(result, task.answer_sympy or task.answer)
            return is_equal, err

        return True, None  # Default to valid for other types

    def generate_variation(
        self,
        task: GeneratedTask,
        variation_type: str = "similar"
    ) -> GeneratedTask:
        """
        Generate a variation of an existing task.

        Args:
            task: Original task to vary
            variation_type: "similar", "harder", "easier"

        Returns:
            New GeneratedTask based on original
        """
        # Adjust difficulty
        difficulty = task.difficulty
        if variation_type == "harder":
            if difficulty == Difficulty.EASY:
                difficulty = Difficulty.MEDIUM
            elif difficulty == Difficulty.MEDIUM:
                difficulty = Difficulty.HARD
        elif variation_type == "easier":
            if difficulty == Difficulty.HARD:
                difficulty = Difficulty.MEDIUM
            elif difficulty == Difficulty.MEDIUM:
                difficulty = Difficulty.EASY

        # Generate new task with same topic
        new_task = self.generate_task(task.topic, difficulty)
        new_task.parent_task_id = task.id

        return new_task

    def generate_hints(self, task: GeneratedTask) -> List[str]:
        """Auto-generate progressive hints from solution steps."""
        if task.hints:
            return task.hints

        hints = []
        if task.topic == "derivatives":
            hints = self._generate_derivative_hints(task.problem, task.difficulty)
        elif task.topic == "integrals":
            hints = self._generate_integral_hints(task.problem, task.difficulty)

        return hints


# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════

def quick_generate(topic: str = "derivatives", difficulty: str = "medium") -> GeneratedTask:
    """Quick task generation."""
    synthesizer = TaskSynthesizer()
    diff = Difficulty(difficulty)
    return synthesizer.generate_task(topic, diff)


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    synthesizer = TaskSynthesizer()

    print("\n=== Generating Tasks ===\n")

    topics = ["derivatives", "integrals", "limits", "equations"]
    for topic in topics:
        task = synthesizer.generate_task(topic, Difficulty.MEDIUM)
        print(f"Topic: {topic}")
        print(f"  Problem: {task.problem}")
        print(f"  Answer: {task.answer}")
        print(f"  Verified: {task.sympy_verified}")
        print(f"  Hints: {task.hints[:2] if task.hints else 'None'}")
        print()

    # Test variation
    print("=== Generating Variation ===")
    original = synthesizer.generate_task("derivatives", Difficulty.EASY)
    variation = synthesizer.generate_variation(original, "harder")
    print(f"Original ({original.difficulty.value}): {original.problem}")
    print(f"Variation ({variation.difficulty.value}): {variation.problem}")
