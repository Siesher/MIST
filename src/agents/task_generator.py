"""
MITS Task Generator Agent

Generates mathematical and programming tasks with solutions, hints, and common mistakes.
Supports adaptive difficulty selection based on student knowledge state.

Based on research:
- RL-DKT (2025) - adaptive task selection improves learning outcomes by 12.5%
- GenMentor (WWW 2025) - multi-agent task selection
"""

import json
import logging
import random
import re
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.agents.base_agent import BaseAgent
from src.data.schemas import Difficulty, Subject, Task
from src.models.llm_client import LLMClient
from src.models.prompts import TASK_GENERATOR_PROMPT, TASK_GENERATOR_SYSTEM


def _parse_task_json(response: str, agent_logger=None) -> Optional[Dict[str, Any]]:
    """Robust JSON parser for LLM task generation output.

    Tries in order:
      1. Plain json.loads (happy path)
      2. Extract from markdown fence (```json ... ```)
      3. Extract largest {...} balanced block via regex
      4. json5.loads (tolerates trailing commas, unquoted keys, comments)
      5. None on total failure — caller should retry or raise

    The LLM often returns malformed JSON on long tasks (line 4 col 4584-style
    errors typically come from unescaped quotes/newlines in LaTeX strings).
    """
    if not response:
        return None
    text = response.strip()

    # 1. Fast path
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown fences (```json ... ``` or ``` ... ```)
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if fence:
        inner = fence.group(1)
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            text = inner  # keep for downstream attempts

    # 3. Extract outermost {...} balanced block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            text = candidate

    # 4. json5 fallback — handles trailing commas, unquoted keys, single quotes
    try:
        import json5

        return json5.loads(text)
    except Exception as e:
        if agent_logger is not None:
            try:
                agent_logger.debug(
                    "json5_parse_failed",
                    error=str(e)[:100],
                    preview=text[:120].replace("\n", " "),
                )
            except Exception:
                pass

    return None


# SKI for textbook grounding
try:
    from src.knowledge.ski import get_ski

    HAS_SKI = True
except ImportError:
    HAS_SKI = False
    get_ski = None

if TYPE_CHECKING:
    from src.models.knowledge_tracing import KnowledgeTracker

logger = logging.getLogger(__name__)


class TaskGeneratorAgent(BaseAgent):
    """
    Agent for generating educational tasks with adaptive difficulty selection.

    Features:
    - Topic-based task generation
    - Adaptive difficulty scaling based on knowledge state
    - Automatic hint generation
    - Common mistake identification
    - Zone of Proximal Development (ZPD) targeting
    - Cognitive load-aware task selection
    """

    # Optimal mastery range for learning (Zone of Proximal Development)
    ZPD_MIN = 0.3  # Below this, task too hard
    ZPD_MAX = 0.8  # Above this, task too easy

    # Difficulty mapping for adaptive selection
    DIFFICULTY_ORDER = [Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD, Difficulty.OLYMPIAD]

    # Mastery thresholds for difficulty recommendation
    MASTERY_TO_DIFFICULTY = {
        (0.0, 0.3): Difficulty.EASY,
        (0.3, 0.5): Difficulty.MEDIUM,
        (0.5, 0.7): Difficulty.HARD,
        (0.7, 1.0): Difficulty.OLYMPIAD,
    }

    def __init__(
        self, llm_client: LLMClient, knowledge_tracker: Optional["KnowledgeTracker"] = None
    ):
        super().__init__(
            name="TaskGenerator", llm_client=llm_client, system_prompt=TASK_GENERATOR_SYSTEM
        )

        self.knowledge_tracker = knowledge_tracker

        # Skill taxonomy for math
        self.math_skills = {
            "algebra": [
                "linear_equations",
                "quadratic_equations",
                "systems",
                "inequalities",
                "factoring",
            ],
            "calculus": [
                "limits",
                "derivatives",
                "chain_rule",
                "product_rule",
                "quotient_rule",
                "integrals",
            ],
            "geometry": ["triangles", "circles", "vectors", "coordinate_geometry", "trigonometry"],
            "number_theory": ["divisibility", "primes", "modular_arithmetic", "gcd_lcm"],
        }

        # Skill prerequisites (for ZPD-aware selection)
        self.skill_prerequisites = {
            "quadratic_equations": ["linear_equations", "factoring"],
            "systems": ["linear_equations"],
            "derivatives": ["limits"],
            "chain_rule": ["derivatives"],
            "product_rule": ["derivatives"],
            "quotient_rule": ["derivatives"],
            "integrals": ["derivatives"],
            "trigonometry": ["triangles", "algebra"],
        }

    def set_knowledge_tracker(self, tracker: "KnowledgeTracker"):
        """Set or update the knowledge tracker."""
        self.knowledge_tracker = tracker

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a task based on specifications.

        Args:
            input_data: {
                "topic": str,
                "difficulty": Difficulty,
                "skills": List[str] (optional),
                "subject": Subject (optional),
                "student_level": dict (optional)
            }

        Returns:
            {"task": Task}
        """
        topic = input_data.get("topic", "derivatives")
        difficulty = input_data.get("difficulty", Difficulty.MEDIUM)
        skills = input_data.get("skills", [])
        subject = input_data.get("subject", Subject.MATH)
        student_level = input_data.get("student_level", {})

        task = self.generate_task(
            topic=topic,
            difficulty=difficulty,
            skills=skills,
            subject=subject,
            student_level=student_level,
        )

        return {"task": task}

    def generate_task(
        self,
        topic: str,
        difficulty: Difficulty = Difficulty.MEDIUM,
        skills: List[str] = None,
        subject: Subject = Subject.MATH,
        student_level: dict = None,
    ) -> Task:
        """
        Generate a single educational task.

        Args:
            topic: Math topic (e.g., "derivatives", "integrals")
            difficulty: Task difficulty level
            skills: Specific skills to test
            subject: Subject area
            student_level: Student's current mastery levels

        Returns:
            Generated Task object
        """
        skills = skills or []
        student_level = student_level or {}

        # Try template-based generation first
        template_task = self._generate_from_template(topic, difficulty)
        if template_task is not None:
            self._log_action("template_task_generated", {"task_id": template_task.id})
            return template_task

        # Build method context from SKI
        method_context = ""
        notation_context = ""
        if HAS_SKI:
            try:
                ski = get_ski()
                methods = ski.get_solution_methods(topic)
                if methods:
                    lines = ["## МЕТОДЫ РЕШЕНИЯ (из учебника):"]
                    for m in methods[:3]:
                        lines.append(f"- **{m.get('name', '')}**: {m.get('when_to_use', '')}")
                        for step in m.get("steps", [])[:4]:
                            lines.append(f"  {step.get('step', '')}: {step.get('action', '')}")
                    method_context = "\n".join(lines)

                notation = ski.get_notation_context(topic)
                if notation:
                    lines = ["## НОТАЦИЯ (используй эти обозначения):"]
                    for sym, desc in notation.items():
                        lines.append(f"- {sym}: {desc}")
                    notation_context = "\n".join(lines)
            except Exception as e:
                logger.debug(f"SKI context retrieval skipped: {e}")

        prompt = TASK_GENERATOR_PROMPT.format(
            subject=subject.value,
            topic=topic,
            difficulty=difficulty.value,
            skills=", ".join(skills) if skills else "appropriate for topic",
            num_steps=self._get_steps_for_difficulty(difficulty),
            method_context=method_context,
            notation_context=notation_context,
        )

        self._log_action("generating_task", {"topic": topic, "difficulty": difficulty.value})

        response = self._call_llm(prompt, json_mode=True, thinking=False)
        task_data = _parse_task_json(response, self.logger)
        if task_data is None:
            # One retry with a gentler temperature before giving up
            self.logger.warning("task_json_parse_failed_retrying")
            response = self._call_llm(
                prompt + "\n\nВажно: возвращай ТОЛЬКО валидный JSON-объект.",
                json_mode=True,
                thinking=False,
                temperature=0.5,
            )
            task_data = _parse_task_json(response, self.logger)

        if task_data is None:
            preview = (response or "")[:300].replace("\n", " ")
            self.logger.error("task_generation_failed_all_attempts", preview=preview)
            raise ValueError(
                f"Failed to generate valid task after 2 attempts. Response preview: {preview}"
            )

        try:
            # Normalize fields - LLM may return lists instead of strings
            solution = task_data.get("solution", "")
            if isinstance(solution, list):
                solution = "\n".join(str(s) for s in solution)

            answer = task_data.get("answer", "")
            if isinstance(answer, list):
                answer = ", ".join(str(a) for a in answer)

            problem = task_data.get("problem", "")
            if isinstance(problem, list):
                problem = "\n".join(str(p) for p in problem)

            task = Task(
                id=str(uuid.uuid4()),
                subject=subject,
                topic=topic,
                difficulty=difficulty,
                skills=task_data.get("skills", skills or [topic]),
                problem=problem,
                solution=solution,
                answer=str(answer),
                hints=task_data.get("hints", [])[:3],
                common_mistakes=task_data.get("common_mistakes", []),
                estimated_time_minutes=self._estimate_time(difficulty),
            )

            self._log_action("task_generated", {"task_id": task.id})
            return task

        except (KeyError, TypeError) as e:
            self.logger.error("task_generation_failed", error=str(e))
            raise ValueError(f"Failed to generate valid task: {e}")

    def generate_batch(
        self, topic: str, difficulty: Difficulty, count: int = 5, **kwargs
    ) -> List[Task]:
        """Generate multiple tasks for a topic."""
        tasks = []

        for i in range(count):
            try:
                task = self.generate_task(topic=topic, difficulty=difficulty, **kwargs)
                tasks.append(task)
            except Exception as e:
                self.logger.warning("batch_task_failed", index=i, error=str(e))

        return tasks

    # ── Template-based task generation ─────────────────────────────

    def _generate_from_template(self, topic: str, difficulty: Difficulty) -> Optional[Task]:
        """
        Try to generate a task from a problem template.
        Returns None if no template available or sampling fails.
        """
        if not HAS_SKI:
            return None

        try:
            ski = get_ski()
            templates = ski.get_problem_templates(topic, difficulty=difficulty.value)
            if not templates:
                return None

            template = random.choice(templates)
            params = self._sample_template_params(template)
            if params is None:
                return None

            # Fill pattern with sampled params
            problem = template["pattern"].format(**params)
            answer = template.get("answer_template", "").format(**params)

            # Build solution from linked method
            solution = ""
            method_id = template.get("solution_method_id")
            if method_id:
                methods = ski.get_solution_methods(topic, method_id=method_id)
                if methods:
                    m = methods[0]
                    steps = []
                    for s in m.get("steps", []):
                        step_text = f"{s.get('step', '')}: {s.get('action', '')}"
                        if s.get("formula"):
                            step_text += f" → {s['formula']}"
                        steps.append(step_text)
                    solution = "\n".join(steps)

            return Task(
                id=str(uuid.uuid4()),
                subject=Subject.MATH,
                topic=topic,
                difficulty=difficulty,
                skills=[topic],
                problem=problem,
                solution=solution,
                answer=answer,
                hints=template.get("hints", [])[:3],
                common_mistakes=[],
                estimated_time_minutes=self._estimate_time(difficulty),
            )
        except Exception as e:
            logger.debug(f"Template generation failed: {e}")
            return None

    def _sample_template_params(
        self, template: Dict[str, Any], max_retries: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Sample random parameters from template ranges, respecting constraints.
        Returns None if no valid sample found after max_retries.
        """
        param_specs = template.get("parameters", {})
        constraints = template.get("constraints", [])

        for _ in range(max_retries):
            params: Dict[str, Any] = {}
            valid = True

            for name, spec in param_specs.items():
                ptype = spec.get("type", "int")
                prange = spec.get("range", [1, 10])
                exclude = set(spec.get("exclude", []))

                if ptype == "int":
                    val = random.randint(prange[0], prange[1])
                    while val in exclude and prange[1] - prange[0] > len(exclude):
                        val = random.randint(prange[0], prange[1])
                    if val in exclude:
                        valid = False
                        break
                elif ptype == "float":
                    val = round(random.uniform(prange[0], prange[1]), 2)
                else:
                    val = random.randint(prange[0], prange[1])

                params[name] = val

            if not valid:
                continue

            # Compute derived params
            params = self._compute_derived_params(template, params)

            # Check constraints
            if self._check_constraints(constraints, params):
                return params

        return None

    def _compute_derived_params(
        self, template: Dict[str, Any], params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate derived_params expressions (e.g. 'D': 'b*b - 4*a*c')."""
        derived = template.get("derived_params", {})
        safe_ns = {"__builtins__": {}, "abs": abs, "round": round}
        safe_ns.update(params)

        for name, expr in derived.items():
            try:
                params[name] = eval(expr, safe_ns)  # noqa: S307
                safe_ns[name] = params[name]
            except Exception:
                pass
        return params

    @staticmethod
    def _check_constraints(constraints: List[str], params: Dict[str, Any]) -> bool:
        """Check all constraint expressions evaluate to True."""
        safe_ns = {"__builtins__": {}, "abs": abs, "round": round}
        safe_ns.update(params)
        for expr in constraints:
            try:
                if not eval(expr, safe_ns):  # noqa: S307
                    return False
            except Exception:
                return False
        return True

    def _get_steps_for_difficulty(self, difficulty: Difficulty) -> int:
        """Get expected solution steps for difficulty."""
        return {
            Difficulty.EASY: 2,
            Difficulty.MEDIUM: 4,
            Difficulty.HARD: 6,
            Difficulty.OLYMPIAD: 8,
        }.get(difficulty, 4)

    def _estimate_time(self, difficulty: Difficulty) -> int:
        """Estimate solving time in minutes."""
        return {
            Difficulty.EASY: 5,
            Difficulty.MEDIUM: 10,
            Difficulty.HARD: 20,
            Difficulty.OLYMPIAD: 30,
        }.get(difficulty, 10)

    def get_available_topics(self, subject: Subject = Subject.MATH) -> List[str]:
        """Get list of available topics."""
        if subject == Subject.MATH:
            topics = []
            for category, skills in self.math_skills.items():
                topics.append(category)
                topics.extend(skills)
            return topics
        return []

    def select_adaptive_difficulty(
        self, student_id: str, topic: str, cognitive_load_level: str = "optimal"
    ) -> Difficulty:
        """
        Select appropriate difficulty based on student's knowledge state.

        Uses Zone of Proximal Development (ZPD) principle:
        - Tasks should be challenging but achievable
        - Considers mastery level for the specific topic
        - Adjusts for cognitive load

        Args:
            student_id: Student identifier
            topic: Topic for the task
            cognitive_load_level: Current cognitive load (low/optimal/high/overload)

        Returns:
            Recommended Difficulty level
        """
        # Default difficulty
        recommended = Difficulty.MEDIUM

        if self.knowledge_tracker:
            try:
                student = self.knowledge_tracker.get_student(student_id)
                mastery = student.get_mastery(topic)

                # Map mastery to difficulty
                for (min_m, max_m), difficulty in self.MASTERY_TO_DIFFICULTY.items():
                    if min_m <= mastery < max_m:
                        recommended = difficulty
                        break

                logger.debug(
                    f"Adaptive difficulty for {topic}: mastery={mastery:.2f} -> {recommended.value}"
                )

            except Exception as e:
                logger.warning(f"Error getting student mastery: {e}")

        # Adjust for cognitive load
        recommended = self._adjust_for_cognitive_load(recommended, cognitive_load_level)

        return recommended

    def _adjust_for_cognitive_load(self, difficulty: Difficulty, cognitive_load: str) -> Difficulty:
        """
        Adjust difficulty based on cognitive load.

        If student is overloaded, reduce difficulty.
        If load is low, can increase difficulty.
        """
        diff_index = self.DIFFICULTY_ORDER.index(difficulty)

        if cognitive_load == "overload":
            # Reduce by 2 levels
            diff_index = max(0, diff_index - 2)
        elif cognitive_load == "high":
            # Reduce by 1 level
            diff_index = max(0, diff_index - 1)
        elif cognitive_load == "low":
            # Can increase by 1 level
            diff_index = min(len(self.DIFFICULTY_ORDER) - 1, diff_index + 1)
        # "optimal" - no change

        adjusted = self.DIFFICULTY_ORDER[diff_index]

        if adjusted != difficulty:
            logger.debug(
                f"Difficulty adjusted for cognitive load {cognitive_load}: "
                f"{difficulty.value} -> {adjusted.value}"
            )

        return adjusted

    def select_adaptive_topic(
        self, student_id: str, subject: Subject = Subject.MATH, prefer_weak: bool = True
    ) -> str:
        """
        Select topic based on student's knowledge state.

        Uses ZPD principle to find topics where:
        - Prerequisites are mastered (>0.6)
        - Topic itself has room for improvement (<0.8)

        Args:
            student_id: Student identifier
            subject: Subject area
            prefer_weak: Prioritize weaker skills

        Returns:
            Recommended topic
        """
        available_topics = self.get_available_topics(subject)

        if not self.knowledge_tracker:
            return random.choice(available_topics)

        try:
            student = self.knowledge_tracker.get_student(student_id)

            # Find topics in ZPD
            zpd_topics = []
            for topic in available_topics:
                mastery = student.get_mastery(topic)

                # Check if in ZPD range
                if self.ZPD_MIN <= mastery <= self.ZPD_MAX:
                    # Check prerequisites
                    prereqs = self.skill_prerequisites.get(topic, [])
                    prereqs_met = all(student.get_mastery(p) > 0.6 for p in prereqs)

                    if prereqs_met or not prereqs:
                        zpd_topics.append((topic, mastery))

            if not zpd_topics:
                # Fallback: use KT recommendation
                recommended = student.recommend_next_skill()
                if recommended:
                    return recommended
                return random.choice(available_topics)

            # Sort by mastery (weakest first if prefer_weak)
            zpd_topics.sort(key=lambda x: x[1], reverse=not prefer_weak)

            # Add some randomization among top candidates
            top_candidates = zpd_topics[:3]
            selected = random.choice(top_candidates)[0]

            logger.debug(
                f"Adaptive topic selected: {selected} from {len(zpd_topics)} ZPD candidates"
            )

            return selected

        except Exception as e:
            logger.warning(f"Error in adaptive topic selection: {e}")
            return random.choice(available_topics)

    def generate_adaptive_task(
        self,
        student_id: str,
        topic: Optional[str] = None,
        subject: Subject = Subject.MATH,
        cognitive_load_level: str = "optimal",
    ) -> Task:
        """
        Generate a task with adaptive difficulty and topic selection.

        This is the main entry point for adaptive task generation.

        Args:
            student_id: Student identifier
            topic: Optional topic (if None, selects adaptively)
            subject: Subject area
            cognitive_load_level: Current cognitive load level

        Returns:
            Generated Task with appropriate difficulty
        """
        # Select topic if not provided
        if topic is None:
            topic = self.select_adaptive_topic(student_id, subject)

        # Select difficulty based on knowledge state
        difficulty = self.select_adaptive_difficulty(student_id, topic, cognitive_load_level)

        # Get student level for context
        student_level = {}
        if self.knowledge_tracker:
            try:
                summary = self.knowledge_tracker.get_knowledge_state_summary(student_id)
                student_level = {
                    skill: data["mastery"]
                    for skill, data in summary.get("mastery_by_skill", {}).items()
                }
            except Exception as e:
                logger.warning(f"Could not get student level: {e}")

        # Generate task
        task = self.generate_task(
            topic=topic, difficulty=difficulty, subject=subject, student_level=student_level
        )

        logger.info(
            f"Adaptive task generated: topic={topic}, difficulty={difficulty.value}, "
            f"student={student_id}"
        )

        return task

    def get_recommended_practice(
        self, student_id: str, count: int = 3, subject: Subject = Subject.MATH
    ) -> List[Dict[str, Any]]:
        """
        Get recommended practice tasks based on student's knowledge state.

        Returns a mix of:
        - Weak skill reinforcement (60%)
        - Strong skill maintenance (20%)
        - New skill introduction (20%)

        Args:
            student_id: Student identifier
            count: Number of recommendations
            subject: Subject area

        Returns:
            List of recommended task specifications
        """
        recommendations = []

        if not self.knowledge_tracker:
            # Fallback: random topics
            topics = self.get_available_topics(subject)
            for _ in range(count):
                recommendations.append(
                    {
                        "topic": random.choice(topics),
                        "difficulty": Difficulty.MEDIUM,
                        "reason": "general_practice",
                    }
                )
            return recommendations

        try:
            student = self.knowledge_tracker.get_student(student_id)

            # Get weak skills (60% of recommendations)
            weak_count = max(1, int(count * 0.6))
            weak_skills = student.get_weakest_skills(weak_count)
            for skill, mastery in weak_skills:
                difficulty = self.select_adaptive_difficulty(student_id, skill)
                recommendations.append(
                    {
                        "topic": skill,
                        "difficulty": difficulty,
                        "mastery": mastery,
                        "reason": "weak_skill_reinforcement",
                    }
                )

            # Get ready-to-learn skills (20% new skills)
            new_count = max(1, int(count * 0.2))
            ready_skills = student.get_ready_skills()
            for skill in ready_skills[:new_count]:
                if skill not in [r["topic"] for r in recommendations]:
                    recommendations.append(
                        {
                            "topic": skill,
                            "difficulty": Difficulty.EASY,  # Start easy for new skills
                            "mastery": student.get_mastery(skill),
                            "reason": "new_skill_introduction",
                        }
                    )

            # Strong skill maintenance (remaining)
            strong_count = count - len(recommendations)
            if strong_count > 0:
                strong_skills = student.get_strongest_skills(strong_count)
                for skill, mastery in strong_skills:
                    if skill not in [r["topic"] for r in recommendations]:
                        recommendations.append(
                            {
                                "topic": skill,
                                "difficulty": Difficulty.HARD,  # Challenge on strong skills
                                "mastery": mastery,
                                "reason": "strong_skill_maintenance",
                            }
                        )

            # Trim to requested count
            recommendations = recommendations[:count]

            logger.debug(f"Generated {len(recommendations)} practice recommendations")

        except Exception as e:
            logger.warning(f"Error generating recommendations: {e}")

        return recommendations
