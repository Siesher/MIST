"""
Learning Path Optimization Module

Builds personalized learning paths based on:
- Knowledge graph prerequisites
- Student's current mastery levels
- Learning rate and preferences

Uses topological sorting and graph traversal to find optimal paths.
"""

import logging
from typing import Optional, List, Dict, Any, Set, Tuple
from datetime import datetime
import uuid

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

from src.data.schemas import (
    LearningPathStatus,
    SkillNode,
    LearningPath,
)
from src.data.knowledge_graph import (
    SKILL_GRAPH,
    get_skill_name_ru,
    get_all_prerequisites,
)

logger = logging.getLogger(__name__)


class LearningPathOptimizer:
    """
    Optimizes learning paths for students.

    Creates personalized curricula by analyzing:
    - Target skill requirements
    - Current mastery levels
    - Prerequisite dependencies
    """

    def __init__(
        self,
        knowledge_graph: Optional[Dict] = None,
        knowledge_tracer: Optional[object] = None,
        mastery_threshold: float = 0.7,
    ):
        """
        Initialize the optimizer.

        Args:
            knowledge_graph: Skill prerequisite graph
            knowledge_tracer: Optional knowledge tracer for mastery data
            mastery_threshold: Threshold above which skill is considered mastered
        """
        self.knowledge_graph = knowledge_graph or SKILL_GRAPH
        self.knowledge_tracer = knowledge_tracer
        self.mastery_threshold = mastery_threshold

        # Build NetworkX graph for analysis
        self._build_graph()

        logger.info(f"LearningPathOptimizer initialized with {len(self.knowledge_graph)} skills")

    def _build_graph(self) -> None:
        """Build NetworkX directed graph from knowledge graph."""
        if not NETWORKX_AVAILABLE:
            logger.warning("NetworkX not available - path optimization will be limited")
            self.graph = None
            return

        self.graph = nx.DiGraph()

        for skill_id, skill_data in self.knowledge_graph.items():
            self.graph.add_node(
                skill_id,
                difficulty=skill_data.get("difficulty", 0.5),
                name_ru=skill_data.get("name_ru", skill_id),
            )

            # Add edges from prerequisites to skill
            for prereq in skill_data.get("prerequisites", []):
                if prereq in self.knowledge_graph:
                    self.graph.add_edge(prereq, skill_id)

        logger.debug(f"Built graph with {self.graph.number_of_nodes()} nodes, "
                     f"{self.graph.number_of_edges()} edges")

    def _get_transitive_prerequisites(self, skill_id: str) -> Set[str]:
        """
        Get all transitive prerequisites for a skill.

        Args:
            skill_id: Target skill

        Returns:
            Set of all prerequisite skill IDs
        """
        if self.graph and NETWORKX_AVAILABLE:
            # Use NetworkX ancestors (all nodes that can reach this node)
            try:
                return nx.ancestors(self.graph, skill_id)
            except nx.NetworkXError:
                pass

        # Fallback to recursive DFS
        return set(get_all_prerequisites(skill_id))

    def _filter_mastered_skills(
        self,
        skills: Set[str],
        student_mastery: Dict[str, float],
    ) -> Set[str]:
        """
        Filter out skills that are already mastered.

        Args:
            skills: Set of skill IDs
            student_mastery: Dict of skill_id -> mastery level

        Returns:
            Set of unmastered skill IDs
        """
        return {
            skill for skill in skills
            if student_mastery.get(skill, 0.0) < self.mastery_threshold
        }

    def _topological_sort_skills(self, skills: Set[str]) -> List[str]:
        """
        Sort skills in prerequisite order.

        Args:
            skills: Set of skill IDs to sort

        Returns:
            List of skills in learning order
        """
        if not skills:
            return []

        if self.graph and NETWORKX_AVAILABLE:
            # Get subgraph with only these skills
            subgraph = self.graph.subgraph(skills)
            try:
                return list(nx.topological_sort(subgraph))
            except nx.NetworkXUnfeasible:
                logger.warning("Cycle detected in skill graph")

        # Fallback: sort by difficulty
        return sorted(
            skills,
            key=lambda s: self.knowledge_graph.get(s, {}).get("difficulty", 0.5)
        )

    def create_path(
        self,
        target_skill: str,
        student_mastery: Dict[str, float],
        student_id: str = "",
        max_skills: int = 10,
    ) -> LearningPath:
        """
        Create optimal learning path to target skill.

        Args:
            target_skill: The skill the student wants to learn
            student_mastery: Current mastery levels for skills
            student_id: Student identifier
            max_skills: Maximum skills in path

        Returns:
            LearningPath with ordered skills
        """
        logger.debug(f"Creating path to {target_skill} for student {student_id}")

        # Check if target is valid
        if target_skill not in self.knowledge_graph:
            logger.warning(f"Unknown target skill: {target_skill}")
            # Return minimal path
            return LearningPath(
                id=str(uuid.uuid4()),
                student_id=student_id,
                target_skill=target_skill,
                target_skill_name_ru=target_skill,
                skills=[],
                current_skill_index=0,
                status=LearningPathStatus.NOT_STARTED,
                estimated_hours=0,
                created_at=datetime.now(),
            )

        # Get all prerequisites
        all_prereqs = self._get_transitive_prerequisites(target_skill)
        all_prereqs.add(target_skill)

        # Filter out mastered skills
        needed_skills = self._filter_mastered_skills(all_prereqs, student_mastery)

        # Sort in learning order
        ordered_skills = self._topological_sort_skills(needed_skills)

        # Limit path length
        if len(ordered_skills) > max_skills:
            # Keep the most essential skills
            ordered_skills = ordered_skills[:max_skills]
            logger.info(f"Truncated path to {max_skills} skills")

        # Build skill nodes
        skill_nodes = []
        for i, skill_id in enumerate(ordered_skills):
            skill_data = self.knowledge_graph.get(skill_id, {})
            skill_nodes.append(SkillNode(
                skill_id=skill_id,
                skill_name_ru=get_skill_name_ru(skill_id),
                difficulty=skill_data.get("difficulty", 0.5),
                prerequisites=[
                    p for p in skill_data.get("prerequisites", [])
                    if p in ordered_skills
                ],
                current_mastery=student_mastery.get(skill_id, 0.0),
                target_mastery=self.mastery_threshold,
                estimated_tasks=self._estimate_tasks_needed(
                    skill_id,
                    student_mastery.get(skill_id, 0.0)
                ),
                order=i,
            ))

        # Estimate total time
        total_tasks = sum(node.estimated_tasks for node in skill_nodes)
        estimated_hours = total_tasks * 0.15  # ~9 min per task average

        return LearningPath(
            id=str(uuid.uuid4()),
            student_id=student_id,
            target_skill=target_skill,
            target_skill_name_ru=get_skill_name_ru(target_skill),
            skills=skill_nodes,
            current_skill_index=0,
            status=LearningPathStatus.NOT_STARTED if skill_nodes else LearningPathStatus.COMPLETED,
            estimated_hours=estimated_hours,
            created_at=datetime.now(),
        )

    def _estimate_tasks_needed(
        self,
        skill_id: str,
        current_mastery: float,
    ) -> int:
        """
        Estimate number of tasks needed to master skill.

        Args:
            skill_id: Skill identifier
            current_mastery: Current mastery level

        Returns:
            Estimated number of tasks
        """
        skill_data = self.knowledge_graph.get(skill_id, {})
        difficulty = skill_data.get("difficulty", 0.5)

        # Base tasks by difficulty
        base_tasks = int(3 + difficulty * 7)  # 3-10 tasks

        # Adjust for current mastery
        remaining = self.mastery_threshold - current_mastery
        mastery_factor = max(0.3, remaining / self.mastery_threshold)

        return max(1, int(base_tasks * mastery_factor))

    def get_next_skill(self, path: LearningPath) -> Optional[SkillNode]:
        """
        Get the next skill to study in the path.

        Args:
            path: The learning path

        Returns:
            Next SkillNode or None if path complete
        """
        if path.current_skill_index >= len(path.skills):
            return None

        return path.skills[path.current_skill_index]

    def update_progress(
        self,
        path: LearningPath,
        skill_id: str,
        new_mastery: float,
    ) -> LearningPath:
        """
        Update path progress when a skill is practiced.

        Args:
            path: Learning path to update
            skill_id: Skill that was practiced
            new_mastery: New mastery level

        Returns:
            Updated learning path
        """
        # Find skill in path
        for i, node in enumerate(path.skills):
            if node.skill_id == skill_id:
                node.current_mastery = new_mastery

                # Check if skill is now mastered
                if new_mastery >= node.target_mastery:
                    # Move to next skill if this was current
                    if i == path.current_skill_index:
                        path.current_skill_index += 1

                        # Check if path is complete
                        if path.current_skill_index >= len(path.skills):
                            path.status = LearningPathStatus.COMPLETED
                        else:
                            path.status = LearningPathStatus.IN_PROGRESS

                break

        path.updated_at = datetime.now()
        return path

    def visualize_path(
        self,
        path: LearningPath,
        format: str = "mermaid"
    ) -> str:
        """
        Generate visualization of the learning path.

        Args:
            path: Learning path to visualize
            format: Output format ("mermaid" or "ascii")

        Returns:
            Visualization string
        """
        if not path.skills:
            return "Путь пуст - все навыки уже освоены!"

        if format == "mermaid":
            return self._visualize_mermaid(path)
        else:
            return self._visualize_ascii(path)

    def _visualize_mermaid(self, path: LearningPath) -> str:
        """Generate Mermaid diagram."""
        lines = ["```mermaid", "flowchart TD"]

        for node in path.skills:
            # Node style based on mastery
            if node.current_mastery >= node.target_mastery:
                style = ":::completed"
                label = f"{node.skill_name_ru} ✓"
            elif node.order == path.current_skill_index:
                style = ":::current"
                label = f"{node.skill_name_ru} 👈"
            else:
                style = ""
                pct = int(node.current_mastery * 100)
                label = f"{node.skill_name_ru} ({pct}%)"

            lines.append(f'    {node.skill_id}["{label}"]{style}')

        # Add edges for prerequisites
        for node in path.skills:
            for prereq in node.prerequisites:
                lines.append(f"    {prereq} --> {node.skill_id}")

        # Styles
        lines.append("")
        lines.append("    classDef completed fill:#90EE90")
        lines.append("    classDef current fill:#FFD700")
        lines.append("```")

        return "\n".join(lines)

    def _visualize_ascii(self, path: LearningPath) -> str:
        """Generate ASCII visualization."""
        lines = ["📚 Путь обучения", "=" * 40, ""]

        for node in path.skills:
            # Status indicator
            if node.current_mastery >= node.target_mastery:
                status = "✅"
            elif node.order == path.current_skill_index:
                status = "👉"
            else:
                status = "⬜"

            # Progress bar
            pct = int(node.current_mastery * 100)
            filled = int(node.current_mastery * 10)
            bar = "█" * filled + "░" * (10 - filled)

            lines.append(f"{status} {node.skill_name_ru}")
            lines.append(f"   [{bar}] {pct}% → {int(node.target_mastery * 100)}%")
            lines.append(f"   Задач: ~{node.estimated_tasks}")
            lines.append("")

        # Summary
        completed = sum(1 for n in path.skills if n.current_mastery >= n.target_mastery)
        lines.append("=" * 40)
        lines.append(f"Прогресс: {completed}/{len(path.skills)} навыков")
        lines.append(f"Оценка времени: ~{path.estimated_hours:.1f} часов")

        return "\n".join(lines)

    def get_skill_recommendations(
        self,
        student_mastery: Dict[str, float],
        count: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Get recommended skills to study based on current mastery.

        Args:
            student_mastery: Current mastery levels
            count: Number of recommendations

        Returns:
            List of recommended skills with rationale
        """
        recommendations = []

        # Find skills that are almost ready (prerequisites mostly mastered)
        for skill_id, skill_data in self.knowledge_graph.items():
            # Skip already mastered
            if student_mastery.get(skill_id, 0) >= self.mastery_threshold:
                continue

            # Check prerequisites
            prereqs = skill_data.get("prerequisites", [])
            if not prereqs:
                prereq_mastery = 1.0
            else:
                prereq_mastery = sum(
                    student_mastery.get(p, 0) for p in prereqs
                ) / len(prereqs)

            # Readiness score
            readiness = prereq_mastery * (1 - skill_data.get("difficulty", 0.5))

            recommendations.append({
                "skill_id": skill_id,
                "skill_name_ru": get_skill_name_ru(skill_id),
                "difficulty": skill_data.get("difficulty", 0.5),
                "readiness": readiness,
                "prereq_mastery": prereq_mastery,
                "rationale": self._get_recommendation_rationale(
                    skill_id, prereq_mastery, skill_data.get("difficulty", 0.5)
                ),
            })

        # Sort by readiness (highest first)
        recommendations.sort(key=lambda x: x["readiness"], reverse=True)

        return recommendations[:count]

    def _get_recommendation_rationale(
        self,
        skill_id: str,
        prereq_mastery: float,
        difficulty: float,
    ) -> str:
        """Generate rationale for skill recommendation."""
        if prereq_mastery >= 0.9:
            return "Все пререквизиты освоены — идеальный момент для изучения"
        elif prereq_mastery >= 0.7:
            return "Большинство пререквизитов освоено — хорошее время начать"
        elif difficulty < 0.4:
            return "Простой навык — можно начать изучение"
        else:
            return "Рекомендуется после освоения базовых навыков"


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    optimizer = LearningPathOptimizer()

    # Simulate student mastery
    student_mastery = {
        "arithmetic": 0.95,
        "algebra_basic": 0.8,
        "functions": 0.6,
        "limits_intro": 0.3,
        "limits_techniques": 0.1,
        "derivatives_basic": 0.0,
    }

    # Create path to integration
    path = optimizer.create_path(
        target_skill="integration_basic",
        student_mastery=student_mastery,
        student_id="student_1",
    )

    print("=== Learning Path ===")
    print(f"Target: {path.target_skill_name_ru}")
    print(f"Skills to learn: {len(path.skills)}")
    print(f"Estimated hours: {path.estimated_hours:.1f}")
    print()

    print("=== Visualization (ASCII) ===")
    print(optimizer.visualize_path(path, format="ascii"))
    print()

    print("=== Visualization (Mermaid) ===")
    print(optimizer.visualize_path(path, format="mermaid"))
    print()

    print("=== Next Skill ===")
    next_skill = optimizer.get_next_skill(path)
    if next_skill:
        print(f"Next: {next_skill.skill_name_ru}")
        print(f"Tasks needed: ~{next_skill.estimated_tasks}")
    print()

    print("=== Recommendations ===")
    recs = optimizer.get_skill_recommendations(student_mastery)
    for rec in recs:
        print(f"- {rec['skill_name_ru']}: {rec['rationale']}")
