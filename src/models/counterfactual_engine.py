"""
Counterfactual Explanations Engine

Generates XAI-style explanations for student errors:
"If you had applied X, then you would have gotten Y instead of Z"

Integrates with knowledge graph to identify missing skills
and recommend remediation.
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.data.knowledge_graph import (
    SKILL_ERROR_MAPPING,
    SKILL_GRAPH,
    get_all_prerequisites,
    get_skill_name_ru,
)
from src.data.schemas import (
    CounterfactualExplanation,
    Task,
)
from src.utils.sympy_utils import verify_equality

logger = logging.getLogger(__name__)


class CounterfactualEngine:
    """
    Generates counterfactual explanations for errors.

    "Если бы ты применил X, то получил бы Y вместо Z"
    """

    def __init__(
        self,
        llm_client: Optional[object] = None,
        knowledge_graph: Optional[Dict] = None
    ):
        """
        Initialize engine.

        Args:
            llm_client: LLM for explanation generation
            knowledge_graph: Skill prerequisite graph
        """
        self.llm_client = llm_client
        self.knowledge_graph = knowledge_graph or SKILL_GRAPH
        self.error_mapping = SKILL_ERROR_MAPPING

        logger.info("CounterfactualEngine initialized")

    def analyze_error(
        self,
        student_answer: str,
        correct_answer: str,
        task: Task,
        student_steps: Optional[List[str]] = None,
        student_id: str = "",
        session_id: str = ""
    ) -> CounterfactualExplanation:
        """
        Analyze an error and generate counterfactual explanation.

        Args:
            student_answer: What student provided
            correct_answer: Expected answer
            task: The task being solved
            student_steps: Optional intermediate steps
            student_id: Student identifier
            session_id: Session identifier

        Returns:
            CounterfactualExplanation with diagnosis and recommendations
        """
        logger.debug(f"Analyzing error: student='{student_answer}', correct='{correct_answer}'")

        # Parse solutions into steps if not provided
        if student_steps is None:
            student_steps = self._parse_solution_steps(student_answer)

        correct_steps = self._parse_solution_steps(correct_answer)

        # Find divergence point
        divergence_idx = self._find_divergence_point(student_steps, correct_steps)

        # Identify missing skill
        missing_skill, confidence = self._identify_missing_skill(
            student_answer=student_answer,
            correct_answer=correct_answer,
            task_skills=getattr(task, 'skills', [])
        )

        # Generate counterfactual statement
        counterfactual_ru = self._generate_counterfactual_statement(
            missing_skill=missing_skill,
            student_answer=student_answer,
            correct_answer=correct_answer,
            divergence_step=divergence_idx
        )

        # Get prerequisite topics for the missing skill
        prereqs = list(get_all_prerequisites(missing_skill)) if missing_skill else []

        # Get remediation tasks
        remediation = self.get_remediation_tasks(missing_skill) if missing_skill else []

        return CounterfactualExplanation(
            id=str(uuid.uuid4()),
            task_id=getattr(task, 'id', ''),
            student_id=student_id,
            session_id=session_id,
            student_answer=student_answer,
            correct_answer=correct_answer,
            divergence_step=divergence_idx,
            missing_skill=missing_skill or "unknown",
            missing_skill_name_ru=get_skill_name_ru(missing_skill) if missing_skill else "неизвестно",
            counterfactual_statement=counterfactual_ru,
            counterfactual_statement_ru=counterfactual_ru,
            student_path=student_steps,
            correct_path=correct_steps,
            prerequisite_topics=prereqs,
            recommended_practice=remediation,
            created_at=datetime.now(),
        )

    def _parse_solution_steps(self, solution: str) -> List[str]:
        """Split solution into steps."""
        if not solution:
            return []

        # Try to split by common step indicators
        # Russian: "Шаг", "1.", "1)", "="
        steps = []

        # Split by newlines first
        lines = solution.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove step numbering
            line = re.sub(r'^(?:Шаг\s*\d+[.:]?\s*|[\d]+[.)]\s*)', '', line)

            if line:
                steps.append(line)

        # If no steps found, treat the whole thing as one step
        if not steps:
            steps = [solution.strip()]

        return steps

    def _find_divergence_point(
        self,
        student_steps: List[str],
        correct_steps: List[str]
    ) -> int:
        """Find the step where student's solution diverges from correct."""
        for i, (student, correct) in enumerate(zip(student_steps, correct_steps)):
            # Normalize for comparison
            student_norm = self._normalize_expression(student)
            correct_norm = self._normalize_expression(correct)

            if student_norm != correct_norm:
                # Check with SymPy if possible
                is_equal, _, _ = verify_equality(student, correct)
                if not is_equal:
                    return i

        # If student has more/fewer steps
        if len(student_steps) != len(correct_steps):
            return min(len(student_steps), len(correct_steps))

        return 0  # Default to first step

    def _normalize_expression(self, expr: str) -> str:
        """Normalize expression for comparison."""
        # Remove whitespace
        result = re.sub(r'\s+', '', expr.lower())
        # Normalize operators
        result = result.replace('·', '*').replace('×', '*').replace('÷', '/')
        return result

    def _identify_missing_skill(
        self,
        student_answer: str,
        correct_answer: str,
        task_skills: List[str]
    ) -> Tuple[str, float]:
        """
        Identify which skill is missing based on error pattern.

        Returns:
            (skill_id, confidence)
        """
        student_lower = student_answer.lower()
        correct_lower = correct_answer.lower()

        # Check error patterns
        for skill, mapping in self.error_mapping.items():
            for pattern in mapping.get("error_patterns", []):
                try:
                    if isinstance(pattern, str):
                        # Try regex match
                        if re.search(pattern, student_lower, re.IGNORECASE):
                            logger.debug(f"Error pattern matched for skill: {skill}")
                            return skill, 0.8
                except re.error:
                    # Not a valid regex, try literal match
                    if pattern.lower() in student_lower:
                        return skill, 0.7

        # Heuristic matching based on task skills
        if task_skills:
            # Check if answer is missing expected components
            if "sin" in correct_lower and "sin" not in student_lower:
                return "trig_derivatives", 0.6
            if "cos" in correct_lower and "cos" not in student_lower:
                return "trig_derivatives", 0.6
            if "*" in correct_lower and "*" not in student_lower:
                return "product_rule", 0.5

            # Return most advanced skill from task
            return task_skills[-1], 0.5

        return "derivatives_basic", 0.3

    def _generate_counterfactual_statement(
        self,
        missing_skill: str,
        student_answer: str,
        correct_answer: str,
        divergence_step: int
    ) -> str:
        """Generate counterfactual explanation in Russian."""
        # Get template from error mapping
        template = None
        if missing_skill in self.error_mapping:
            template = self.error_mapping[missing_skill].get("counterfactual_template")

        if template:
            # Fill template
            return template.format(
                correct=correct_answer,
                wrong=student_answer,
            )

        # Default template
        skill_name = get_skill_name_ru(missing_skill)
        return (
            f"Если бы ты применил навык «{skill_name}» на шаге {divergence_step + 1}, "
            f"то получил бы {correct_answer} вместо {student_answer}."
        )

    def get_remediation_tasks(
        self,
        missing_skill: str,
        count: int = 3
    ) -> List[str]:
        """
        Get task IDs for practicing the missing skill.

        This is a placeholder - in production, would query task bank.
        """
        # Return skill-related practice suggestions
        skill_tasks = {
            "product_rule": ["task_product_rule_1", "task_product_rule_2", "task_product_rule_3"],
            "chain_rule": ["task_chain_rule_1", "task_chain_rule_2", "task_chain_rule_3"],
            "quotient_rule": ["task_quotient_rule_1", "task_quotient_rule_2"],
            "trig_derivatives": ["task_trig_deriv_1", "task_trig_deriv_2"],
            "substitution": ["task_substitution_1", "task_substitution_2"],
            "integration_by_parts": ["task_parts_1", "task_parts_2"],
        }

        tasks = skill_tasks.get(missing_skill, [])
        return tasks[:count]

    def format_explanation_for_display(
        self,
        explanation: CounterfactualExplanation
    ) -> str:
        """Format explanation for display in chat."""
        output = []

        # Main counterfactual
        output.append("💡 **Объяснение ошибки**")
        output.append("")
        output.append(explanation.counterfactual_statement_ru)
        output.append("")

        # Show comparison if available
        if explanation.student_path and explanation.correct_path:
            output.append("**Сравнение решений:**")
            output.append("")
            output.append("| Твой путь | Правильный путь |")
            output.append("|-----------|-----------------|")

            max_steps = max(len(explanation.student_path), len(explanation.correct_path))
            for i in range(max_steps):
                student = explanation.student_path[i] if i < len(explanation.student_path) else "—"
                correct = explanation.correct_path[i] if i < len(explanation.correct_path) else "—"

                # Highlight divergence
                if i == explanation.divergence_step:
                    student = f"⚠️ {student}"
                    correct = f"✓ {correct}"

                output.append(f"| {student} | {correct} |")

            output.append("")

        # Recommendations
        if explanation.prerequisite_topics:
            output.append("**Рекомендуется повторить:**")
            for topic in explanation.prerequisite_topics[:3]:
                topic_name = get_skill_name_ru(topic)
                output.append(f"- {topic_name}")

        return "\n".join(output)


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    engine = CounterfactualEngine()

    # Simulate an error: student forgot product rule
    class MockTask:
        id = "task_123"
        skills = ["derivatives_basic", "product_rule"]

    task = MockTask()

    explanation = engine.analyze_error(
        student_answer="2x * cos(x)",  # Wrong: forgot f'g term
        correct_answer="2x * sin(x) + x^2 * cos(x)",
        task=task,
        student_id="student_1",
        session_id="session_1"
    )

    print("\n=== Counterfactual Explanation ===")
    print(f"Missing skill: {explanation.missing_skill}")
    print(f"Skill name (RU): {explanation.missing_skill_name_ru}")
    print(f"Divergence step: {explanation.divergence_step}")
    print()
    print("Counterfactual:")
    print(explanation.counterfactual_statement_ru)
    print()
    print("Prerequisites to review:", explanation.prerequisite_topics)
    print()
    print("=== Formatted for Display ===")
    print(engine.format_explanation_for_display(explanation))
