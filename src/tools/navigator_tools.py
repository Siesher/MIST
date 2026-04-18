"""
Navigator Tools for Ollama Tool Calling.

Provides NAVIGATOR_TOOL_DEFINITIONS (Ollama/OpenAI format) and
NAVIGATOR_FUNCTIONS dispatch dict for 5 tools:
  - explore_concept: concept details + student mastery overlay
  - diagnose_gap: find missing prerequisites
  - suggest_next: best concept to teach next
  - find_learning_path: optimal path to target concept
  - get_learning_frontier: ZPD concepts

These tools are registered alongside SKI tools in tutor_agent.py
and called by the LLM during tutoring sessions.
"""

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from src.knowledge.knowledge_forge import KnowledgeGraph
from src.knowledge.navigator import PersonalizedNavigator

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Navigator Singleton
# ─────────────────────────────────────────────────────────────────────

_GRAPH: Optional[KnowledgeGraph] = None
_NAVIGATOR_CACHE: Dict[str, PersonalizedNavigator] = {}

FORGE_PATH = Path("data/knowledge/forge.json")


def _get_graph() -> Optional[KnowledgeGraph]:
    """Load knowledge graph (cached singleton)."""
    global _GRAPH
    if _GRAPH is not None:
        return _GRAPH

    if not FORGE_PATH.exists():
        logger.warning(f"Knowledge graph not found at {FORGE_PATH}")
        return None

    _GRAPH = KnowledgeGraph(FORGE_PATH)
    logger.info(f"Knowledge graph loaded: {_GRAPH.stats['total_nodes']} nodes")
    return _GRAPH


def get_navigator(mastery_source: Any = None) -> Optional[PersonalizedNavigator]:
    """Get or create a PersonalizedNavigator.

    Args:
        mastery_source: StudentMemory instance or Dict[str, float].
            If None, uses empty dict (no personalization).

    Returns:
        PersonalizedNavigator instance, or None if graph unavailable.
    """
    graph = _get_graph()
    if graph is None:
        return None

    source = mastery_source or {}
    source_key = id(source)

    if source_key not in _NAVIGATOR_CACHE:
        _NAVIGATOR_CACHE[source_key] = PersonalizedNavigator(graph, source)

    return _NAVIGATOR_CACHE[source_key]


def reset_cache() -> None:
    """Clear cached graph and navigators (for testing)."""
    global _GRAPH
    _GRAPH = None
    _NAVIGATOR_CACHE.clear()


# ─────────────────────────────────────────────────────────────────────
# Tool Dispatch Functions
# ─────────────────────────────────────────────────────────────────────

# Mastery source injected by tutor_agent before tool calling.
# Set via set_mastery_source() before each session.
_mastery_source: Any = None


def set_mastery_source(source: Any) -> None:
    """Set the mastery source for tool dispatch (called per session)."""
    global _mastery_source
    _mastery_source = source
    _NAVIGATOR_CACHE.clear()  # Invalidate cached navigators


def explore_concept(concept_id: str, student_id: str) -> str:
    """Explore a concept with student mastery overlay."""
    nav = get_navigator(_mastery_source)
    if nav is None:
        return json.dumps({"error": "Knowledge graph not available"})

    result = nav.get_concept_context(student_id, concept_id)
    if result is None:
        return json.dumps({"error": f"Concept not found: {concept_id}"})

    return json.dumps(result, ensure_ascii=False, default=str)


def diagnose_gap(concept_id: str, student_id: str) -> str:
    """Diagnose why a student failed at a concept."""
    nav = get_navigator(_mastery_source)
    if nav is None:
        return json.dumps({"error": "Knowledge graph not available"})

    gap = nav.diagnose_gap(student_id, concept_id)
    return json.dumps(asdict(gap), ensure_ascii=False, default=str)


def suggest_next(student_id: str, domain: Optional[str] = None) -> str:
    """Suggest the best next concept to teach."""
    nav = get_navigator(_mastery_source)
    if nav is None:
        return json.dumps({"error": "Knowledge graph not available"})

    result = nav.suggest_next(student_id, domain=domain)
    if result is None:
        return json.dumps(
            {"message": "No concepts to suggest — student may have mastered all available topics"}
        )

    return json.dumps(asdict(result), ensure_ascii=False, default=str)


def find_learning_path(target_concept_id: str, student_id: str) -> str:
    """Compute optimal learning path to target concept."""
    nav = get_navigator(_mastery_source)
    if nav is None:
        return json.dumps({"error": "Knowledge graph not available"})

    path = nav.find_optimal_path(student_id, target_concept_id)
    if path is None:
        return json.dumps({"error": f"No path found to {target_concept_id}"})

    # Enrich path with titles
    graph = _get_graph()
    path_details = []
    for nid, mastery in zip(path.path, path.mastery_along_path):
        node = graph.get_node(nid)
        path_details.append(
            {
                "id": nid,
                "title": node.title if node else nid,
                "mastery": round(mastery, 2),
                "status": "mastered" if mastery >= 0.7 else "learning" if mastery >= 0.4 else "new",
            }
        )

    result = {
        "target": path.target,
        "path": path_details,
        "total_cost": round(path.total_cost, 2),
        "new_concepts_to_learn": path.estimated_concepts_to_learn,
    }
    return json.dumps(result, ensure_ascii=False, default=str)


def get_learning_frontier(
    student_id: str,
    max_results: int = 5,
    domain: Optional[str] = None,
) -> str:
    """Get concepts at the edge of student's knowledge (ZPD)."""
    nav = get_navigator(_mastery_source)
    if nav is None:
        return json.dumps({"error": "Knowledge graph not available"})

    # Clamp max_results to profile limit
    try:
        from src.resource_profiles import get_active_profile

        profile_cap = get_active_profile().navigator_max_frontier
        max_results = min(max_results, profile_cap)
    except ImportError:
        pass

    frontier = nav.get_learning_frontier(student_id, max_results=max_results, domain=domain)

    result = [
        {
            "id": f.node_id,
            "title": f.title,
            "readiness": round(f.readiness_score, 3),
            "own_mastery": round(f.own_mastery, 2),
            "prereq_mastery_avg": round(f.prereq_mastery_avg, 2),
            "mastered_prereqs": len(f.mastered_prereqs),
            "missing_prereqs": f.missing_prereqs,
            "difficulty": f.difficulty,
        }
        for f in frontier
    ]
    return json.dumps(result, ensure_ascii=False, default=str)


# ─────────────────────────────────────────────────────────────────────
# Ollama Tool Definitions (OpenAI function calling format)
# ─────────────────────────────────────────────────────────────────────

NAVIGATOR_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "explore_concept",
            "description": (
                "Explore a concept in the knowledge graph. Returns the concept definition, "
                "content, difficulty, and all connected nodes (prerequisites, formulas, methods, "
                "examples, misconceptions) enriched with the student's "
                "mastery of each prerequisite. "
                "Use this to understand a topic before explaining it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "concept_id": {
                        "type": "string",
                        "description": (
                            "Knowledge graph node ID (e.g. 'math:derivatives:definition')"
                        ),
                    },
                    "student_id": {
                        "type": "string",
                        "description": "Student identifier for personalized mastery overlay",
                    },
                },
                "required": ["concept_id", "student_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diagnose_gap",
            "description": (
                "Diagnose why a student failed at a concept. Traverses prerequisite edges "
                "backward to find unmastered fundamentals. Returns the root cause, a review path, "
                "and related misconceptions. Use this when a student makes errors or struggles."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "concept_id": {
                        "type": "string",
                        "description": "The concept the student is struggling with",
                    },
                    "student_id": {
                        "type": "string",
                        "description": "Student identifier",
                    },
                },
                "required": ["concept_id", "student_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_next",
            "description": (
                "Suggest the best concept to teach the student next. Returns the concept from "
                "the learning frontier with the highest readiness score. Use this to guide the "
                "learning sequence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": "string",
                        "description": "Student identifier",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Optional domain filter",
                        "enum": ["math", "physics", "cs", "chemistry", "biology"],
                    },
                },
                "required": ["student_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_learning_path",
            "description": (
                "Compute the optimal learning path from the student's current knowledge to a "
                "target concept. Returns an ordered list of concepts to study, skipping already-"
                "mastered ones. Use this when a student asks 'how do I get to topic X?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_concept_id": {
                        "type": "string",
                        "description": "Target concept the student wants to learn",
                    },
                    "student_id": {
                        "type": "string",
                        "description": "Student identifier",
                    },
                },
                "required": ["target_concept_id", "student_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_learning_frontier",
            "description": (
                "Get concepts at the edge of the student's knowledge (Zone of Proximal "
                "Development). Returns up to N concepts where most prerequisites are mastered "
                "but the concept itself is not yet learned, sorted by readiness."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": "string",
                        "description": "Student identifier",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum concepts to return. Default: 5",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Optional domain filter",
                        "enum": ["math", "physics", "cs", "chemistry", "biology"],
                    },
                },
                "required": ["student_id"],
            },
        },
    },
]

NAVIGATOR_FUNCTIONS = {
    "explore_concept": explore_concept,
    "diagnose_gap": diagnose_gap,
    "suggest_next": suggest_next,
    "find_learning_path": find_learning_path,
    "get_learning_frontier": get_learning_frontier,
}
