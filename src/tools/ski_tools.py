"""
SKI Tool Functions for Ollama Native Tool Calling.

Four tools the LLM can invoke to query the Structured Knowledge Index:
- lookup_concept: Get definition, formulas, common errors for a topic
- get_worked_example: Get a step-by-step worked example
- get_formula: Get formulas for a topic
- get_prerequisites: Get prerequisite chain for a topic

Each function returns a JSON string suitable for role='tool' messages.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy-loaded SKI instance
_ski = None


def _get_ski():
    """Lazy-load the SKI singleton."""
    global _ski
    if _ski is None:
        try:
            from src.knowledge.ski import get_ski
            _ski = get_ski()
        except Exception as e:
            logger.warning("SKI not available: %s", e)
    return _ski


# ── Tool Functions ───────────────────────────────────────────────

def lookup_concept(topic: str, domain: Optional[str] = None) -> str:
    """
    Look up a concept by topic. Returns definition, key formulas,
    and common student errors.
    """
    ski = _get_ski()
    if ski is None:
        return json.dumps({"error": "Knowledge base not available"}, ensure_ascii=False)

    cards = ski.lookup_by_topic(topic, domain=domain)
    if not cards:
        # Try search as fallback
        cards = ski.search(topic, domain=domain, limit=1)

    if not cards:
        return json.dumps(
            {"error": f"Тема '{topic}' не найдена в базе знаний"},
            ensure_ascii=False,
        )

    card = cards[0]
    return json.dumps({
        "topic": card.topic,
        "definition": card.definition,
        "key_formulas": card.key_formulas[:5],
        "common_errors": card.common_errors[:3],
        "difficulty": card.difficulty,
        "tags": card.tags,
    }, ensure_ascii=False)


def get_worked_example(topic: str, difficulty: Optional[str] = None) -> str:
    """
    Get a worked example with step-by-step solution for a topic.
    """
    ski = _get_ski()
    if ski is None:
        return json.dumps({"error": "Knowledge base not available"}, ensure_ascii=False)

    examples = ski.get_worked_examples(topic, difficulty=difficulty)
    if not examples:
        return json.dumps(
            {"error": f"Примеры для '{topic}' не найдены"},
            ensure_ascii=False,
        )

    # Return the first matching example
    ex = examples[0]
    return json.dumps({
        "topic": topic,
        "difficulty": ex.get("difficulty", "medium"),
        "problem": ex.get("problem", ""),
        "steps": ex.get("steps", []),
        "answer": ex.get("answer", ""),
    }, ensure_ascii=False)


def get_formula(topic: str, **kwargs) -> str:
    """
    Get all key formulas for a topic.
    """
    ski = _get_ski()
    if ski is None:
        return json.dumps({"error": "Knowledge base not available"}, ensure_ascii=False)

    formulas = ski.get_formulas(topic)
    if not formulas:
        return json.dumps(
            {"error": f"Формулы для '{topic}' не найдены"},
            ensure_ascii=False,
        )

    return json.dumps({
        "topic": topic,
        "formulas": formulas,
    }, ensure_ascii=False)


def get_solution_method(topic: str, method_id: Optional[str] = None, **kwargs) -> str:
    """
    Get step-by-step solution algorithm for a topic.
    Returns method name, steps, when_to_use, and common_pitfalls.
    """
    ski = _get_ski()
    if ski is None:
        return json.dumps({"error": "Knowledge base not available"}, ensure_ascii=False)

    methods = ski.get_solution_methods(topic, method_id=method_id)
    if not methods:
        return json.dumps(
            {"error": f"Методы решения для '{topic}' не найдены"},
            ensure_ascii=False,
        )

    # Return first matching method (or all if no method_id filter)
    if method_id:
        m = methods[0]
        return json.dumps({
            "topic": topic,
            "method_id": m.get("method_id", ""),
            "name": m.get("name", ""),
            "steps": m.get("steps", []),
            "when_to_use": m.get("when_to_use", ""),
            "common_pitfalls": m.get("common_pitfalls", []),
        }, ensure_ascii=False)

    return json.dumps({
        "topic": topic,
        "methods": [
            {
                "method_id": m.get("method_id", ""),
                "name": m.get("name", ""),
                "when_to_use": m.get("when_to_use", ""),
                "steps_count": len(m.get("steps", [])),
            }
            for m in methods
        ],
    }, ensure_ascii=False)


def get_prerequisites(topic: str, **kwargs) -> str:
    """
    Get prerequisite topics needed before studying this topic.
    """
    ski = _get_ski()
    if ski is None:
        return json.dumps({"error": "Knowledge base not available"}, ensure_ascii=False)

    prereqs = ski.get_prerequisites(topic)
    if not prereqs:
        # Topic may not have prerequisites, or not found
        cards = ski.lookup_by_topic(topic)
        if not cards:
            return json.dumps(
                {"error": f"Тема '{topic}' не найдена в базе знаний"},
                ensure_ascii=False,
            )
        return json.dumps({
            "topic": topic,
            "prerequisites": [],
            "note": "Пререквизиты не указаны",
        }, ensure_ascii=False)

    return json.dumps({
        "topic": topic,
        "prerequisites": prereqs,
    }, ensure_ascii=False)


# ── Ollama Tool Definitions ─────────────────────────────────────

SKI_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_concept",
            "description": "Найти определение, формулы и типичные ошибки по теме. "
                           "Используй когда нужно вспомнить теорию или подготовить объяснение.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Название темы, например 'derivatives', 'quadratic_equations', 'integrals'",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Предметная область: 'math', 'physics', 'cs'. Необязательно.",
                        "enum": ["math", "physics", "cs", "chemistry", "biology"],
                    },
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_worked_example",
            "description": "Получить разобранный пример с пошаговым решением. "
                           "Используй когда нужен образец решения похожей задачи.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Тема задачи",
                    },
                    "difficulty": {
                        "type": "string",
                        "description": "Сложность: 'easy', 'medium', 'hard'. Необязательно.",
                        "enum": ["easy", "medium", "hard"],
                    },
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_formula",
            "description": "Получить список ключевых формул по теме. "
                           "Используй когда студенту нужно напомнить формулу.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Тема, для которой нужны формулы",
                    },
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_solution_method",
            "description": "Получить пошаговый АЛГОРИТМ решения задачи. "
                           "Используй когда нужно напомнить МЕТОД, а не формулу.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Тема задачи, например 'quadratic_equations', 'derivatives'",
                    },
                    "method_id": {
                        "type": "string",
                        "description": "ID конкретного метода (необязательно). Например 'quadratic_discriminant'.",
                    },
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_prerequisites",
            "description": "Получить список пререквизитов (предварительных тем) для изучения данной темы. "
                           "Используй когда студент не понимает базовые концепции.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Тема, для которой нужны пререквизиты",
                    },
                },
                "required": ["topic"],
            },
        },
    },
]

# Map function names to callables
SKI_FUNCTIONS = {
    "lookup_concept": lookup_concept,
    "get_worked_example": get_worked_example,
    "get_formula": get_formula,
    "get_solution_method": get_solution_method,
    "get_prerequisites": get_prerequisites,
}
