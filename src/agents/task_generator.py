"""
MITS Task Generator Agent

Generates mathematical and programming tasks with solutions, hints, and common mistakes.
"""

from typing import List, Optional, Dict, Any
import json
import uuid

from src.agents.base_agent import BaseAgent
from src.models.llm_client import LLMClient
from src.models.prompts import TASK_GENERATOR_SYSTEM, TASK_GENERATOR_PROMPT
from src.data.schemas import Task, Difficulty, Subject
from src.config import settings


class TaskGeneratorAgent(BaseAgent):
    """
    Agent for generating educational tasks.
    
    Features:
    - Topic-based task generation
    - Difficulty scaling
    - Automatic hint generation
    - Common mistake identification
    """
    
    def __init__(self, llm_client: LLMClient):
        super().__init__(
            name="TaskGenerator",
            llm_client=llm_client,
            system_prompt=TASK_GENERATOR_SYSTEM
        )
        
        # Skill taxonomy for math
        self.math_skills = {
            "algebra": [
                "linear_equations", "quadratic_equations", 
                "systems", "inequalities", "factoring"
            ],
            "calculus": [
                "limits", "derivatives", "chain_rule", 
                "product_rule", "quotient_rule", "integrals"
            ],
            "geometry": [
                "triangles", "circles", "vectors", 
                "coordinate_geometry", "trigonometry"
            ],
            "number_theory": [
                "divisibility", "primes", "modular_arithmetic", "gcd_lcm"
            ],
        }
    
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
            student_level=student_level
        )
        
        return {"task": task}
    
    def generate_task(
        self,
        topic: str,
        difficulty: Difficulty = Difficulty.MEDIUM,
        skills: List[str] = None,
        subject: Subject = Subject.MATH,
        student_level: dict = None
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
        
        prompt = TASK_GENERATOR_PROMPT.format(
            subject=subject.value,
            topic=topic,
            difficulty=difficulty.value,
            skills=", ".join(skills) if skills else "appropriate for topic",
            num_steps=self._get_steps_for_difficulty(difficulty)
        )
        
        self._log_action("generating_task", {
            "topic": topic,
            "difficulty": difficulty.value
        })
        
        response = self._call_llm(prompt, json_mode=True, thinking=False)
        
        try:
            task_data = json.loads(response)
            
            task = Task(
                id=str(uuid.uuid4()),
                subject=subject,
                topic=topic,
                difficulty=difficulty,
                skills=task_data.get("skills", skills or [topic]),
                problem=task_data["problem"],
                solution=task_data["solution"],
                answer=task_data["answer"],
                hints=task_data.get("hints", [])[:3],
                common_mistakes=task_data.get("common_mistakes", []),
                estimated_time_minutes=self._estimate_time(difficulty)
            )
            
            self._log_action("task_generated", {"task_id": task.id})
            return task
            
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error("task_generation_failed", error=str(e))
            raise ValueError(f"Failed to generate valid task: {e}")
    
    def generate_batch(
        self,
        topic: str,
        difficulty: Difficulty,
        count: int = 5,
        **kwargs
    ) -> List[Task]:
        """Generate multiple tasks for a topic."""
        tasks = []
        
        for i in range(count):
            try:
                task = self.generate_task(
                    topic=topic,
                    difficulty=difficulty,
                    **kwargs
                )
                tasks.append(task)
            except Exception as e:
                self.logger.warning(
                    "batch_task_failed",
                    index=i,
                    error=str(e)
                )
        
        return tasks
    
    def _get_steps_for_difficulty(self, difficulty: Difficulty) -> int:
        """Get expected solution steps for difficulty."""
        return {
            Difficulty.EASY: 2,
            Difficulty.MEDIUM: 4,
            Difficulty.HARD: 6,
            Difficulty.OLYMPIAD: 8
        }.get(difficulty, 4)
    
    def _estimate_time(self, difficulty: Difficulty) -> int:
        """Estimate solving time in minutes."""
        return {
            Difficulty.EASY: 5,
            Difficulty.MEDIUM: 10,
            Difficulty.HARD: 20,
            Difficulty.OLYMPIAD: 30
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
