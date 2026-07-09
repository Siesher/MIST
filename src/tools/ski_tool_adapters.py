"""
BaseTool adapters for SKI tools.

Wraps the native SKI tool functions as BaseTool subclasses
so they integrate with the existing ToolRegistry pattern.
"""

import json
import logging
import time

from src.tools import BaseTool, ToolResult, ToolType
from src.tools.ski_tools import (
    get_formula,
    get_prerequisites,
    get_worked_example,
    lookup_concept,
)

logger = logging.getLogger(__name__)


class ConceptLookupTool(BaseTool):
    """Look up concept definitions, formulas, and common errors."""

    @property
    def name(self) -> str:
        return "concept_lookup"

    @property
    def description(self) -> str:
        return "Поиск определений, формул и типичных ошибок по теме"

    def can_handle(self, query: str) -> bool:
        keywords = [
            "определение", "что такое", "формула", "теория",
            "definition", "concept", "what is",
        ]
        return any(kw in query.lower() for kw in keywords)

    def execute(self, query: str, **kwargs) -> ToolResult:
        start = time.time()
        try:
            domain = kwargs.get("domain")
            result = lookup_concept(topic=query, domain=domain)
            parsed = json.loads(result)
            success = "error" not in parsed
            return ToolResult(
                success=success,
                result=parsed,
                error=parsed.get("error"),
                tool_type=ToolType.CONCEPT_LOOKUP,
                execution_time_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                result=None,
                error=str(e),
                tool_type=ToolType.CONCEPT_LOOKUP,
                execution_time_ms=(time.time() - start) * 1000,
            )


class WorkedExampleTool(BaseTool):
    """Get step-by-step worked examples for a topic."""

    @property
    def name(self) -> str:
        return "worked_example"

    @property
    def description(self) -> str:
        return "Получение разобранных примеров с пошаговым решением"

    def can_handle(self, query: str) -> bool:
        keywords = [
            "пример", "покажи", "решение", "разбор",
            "example", "show me", "worked",
        ]
        return any(kw in query.lower() for kw in keywords)

    def execute(self, query: str, **kwargs) -> ToolResult:
        start = time.time()
        try:
            difficulty = kwargs.get("difficulty")
            result = get_worked_example(topic=query, difficulty=difficulty)
            parsed = json.loads(result)
            success = "error" not in parsed
            return ToolResult(
                success=success,
                result=parsed,
                error=parsed.get("error"),
                tool_type=ToolType.WORKED_EXAMPLE,
                execution_time_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                result=None,
                error=str(e),
                tool_type=ToolType.WORKED_EXAMPLE,
                execution_time_ms=(time.time() - start) * 1000,
            )


class FormulaTool(BaseTool):
    """Get key formulas for a topic."""

    @property
    def name(self) -> str:
        return "formula_lookup"

    @property
    def description(self) -> str:
        return "Получение ключевых формул по теме"

    def can_handle(self, query: str) -> bool:
        keywords = ["формул", "formula", "формулу", "формулы"]
        return any(kw in query.lower() for kw in keywords)

    def execute(self, query: str, **kwargs) -> ToolResult:
        start = time.time()
        try:
            result = get_formula(topic=query)
            parsed = json.loads(result)
            success = "error" not in parsed
            return ToolResult(
                success=success,
                result=parsed,
                error=parsed.get("error"),
                tool_type=ToolType.FORMULA_LOOKUP,
                execution_time_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                result=None,
                error=str(e),
                tool_type=ToolType.FORMULA_LOOKUP,
                execution_time_ms=(time.time() - start) * 1000,
            )


class PrerequisitesTool(BaseTool):
    """Get prerequisite topics for studying a given topic."""

    @property
    def name(self) -> str:
        return "prerequisites"

    @property
    def description(self) -> str:
        return "Получение пререквизитов (предварительных тем) для изучения"

    def can_handle(self, query: str) -> bool:
        keywords = [
            "пререквизит", "prerequisite", "что нужно знать",
            "базовые знания", "перед", "before",
        ]
        return any(kw in query.lower() for kw in keywords)

    def execute(self, query: str, **kwargs) -> ToolResult:
        start = time.time()
        try:
            result = get_prerequisites(topic=query)
            parsed = json.loads(result)
            success = "error" not in parsed
            return ToolResult(
                success=success,
                result=parsed,
                error=parsed.get("error"),
                tool_type=ToolType.PREREQUISITES,
                execution_time_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                result=None,
                error=str(e),
                tool_type=ToolType.PREREQUISITES,
                execution_time_ms=(time.time() - start) * 1000,
            )
